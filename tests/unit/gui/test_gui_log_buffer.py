"""Тесты для GuiLogBuffer — потокобезопасного кольцевого буфера логов."""

from __future__ import annotations

import threading

import pytest

from gui.log_buffer import GuiLogBuffer


class TestGuiLogBufferInit:
    """Тесты инициализации буфера."""

    def test_default_values(self) -> None:
        buf = GuiLogBuffer()
        assert buf.max_lines == 2000
        assert len(buf) == 0
        assert buf.evicted_count == 0

    def test_custom_max_lines(self) -> None:
        buf = GuiLogBuffer(max_lines=100)
        assert buf.max_lines == 100

    def test_invalid_max_lines_raises(self) -> None:
        with pytest.raises(ValueError, match="max_lines"):
            GuiLogBuffer(max_lines=0)

    def test_invalid_max_line_length_raises(self) -> None:
        with pytest.raises(ValueError, match="max_line_length"):
            GuiLogBuffer(max_lines=10, max_line_length=0)


class TestGuiLogBufferAppend:
    """Тесты добавления строк в буфер."""

    def test_append_single_line(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("line 1")
        assert len(buf) == 1
        assert buf.get_text() == "line 1"

    def test_append_multiline_text(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("line 1\nline 2\nline 3")
        assert len(buf) == 3

    def test_append_empty_string_noop(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("")
        assert len(buf) == 0
        assert not buf.is_dirty()

    def test_empty_lines_inside_text_ignored(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("line 1\n\nline 2")
        # Пустые строки пропускаются
        assert len(buf) == 2

    def test_long_line_truncated(self) -> None:
        buf = GuiLogBuffer(max_lines=10, max_line_length=10)
        buf.append("a" * 20)
        text = buf.get_text()
        assert len(text) <= 10
        assert text.endswith("…")

    def test_line_exactly_at_limit_not_truncated(self) -> None:
        buf = GuiLogBuffer(max_lines=10, max_line_length=5)
        buf.append("a" * 5)
        assert buf.get_text() == "a" * 5


class TestGuiLogBufferEviction:
    """Тесты вытеснения старых строк (ring-buffer поведение)."""

    def test_evicts_oldest_when_full(self) -> None:
        buf = GuiLogBuffer(max_lines=3)
        for i in range(5):
            buf.append(f"line {i}")
        # Должны остаться только последние 3
        lines = buf.get_text().splitlines()
        assert len(lines) == 3
        assert lines[-1] == "line 4"
        assert lines[-2] == "line 3"
        assert lines[-3] == "line 2"

    def test_evicted_count_tracks_overflow(self) -> None:
        buf = GuiLogBuffer(max_lines=3)
        for i in range(5):
            buf.append(f"line {i}")
        # 5 добавлено, лимит 3, вытеснено 2
        assert buf.evicted_count == 2

    def test_evicted_count_zero_when_no_overflow(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("line 1\nline 2")
        assert buf.evicted_count == 0

    def test_evicted_count_accumulates(self) -> None:
        buf = GuiLogBuffer(max_lines=2)
        buf.append("a\nb\nc")  # Вытеснено 1 с первого батча
        buf.append("d\ne\nf")  # Вытеснено ещё
        assert buf.evicted_count > 0


class TestGuiLogBufferDirtyFlag:
    """Тесты dirty-флага для дебаунса UI."""

    def test_initially_not_dirty(self) -> None:
        buf = GuiLogBuffer()
        assert not buf.is_dirty()

    def test_dirty_after_append(self) -> None:
        buf = GuiLogBuffer()
        buf.append("line 1")
        assert buf.is_dirty()

    def test_clear_dirty_resets_flag(self) -> None:
        buf = GuiLogBuffer()
        buf.append("line 1")
        buf.clear_dirty()
        assert not buf.is_dirty()

    def test_append_empty_does_not_set_dirty(self) -> None:
        buf = GuiLogBuffer()
        buf.append("")
        assert not buf.is_dirty()

    def test_dirty_again_after_new_append(self) -> None:
        buf = GuiLogBuffer()
        buf.append("line 1")
        buf.clear_dirty()
        buf.append("line 2")
        assert buf.is_dirty()


class TestGuiLogBufferClear:
    """Тесты полной очистки буфера."""

    def test_clear_empties_buffer(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("line 1\nline 2")
        buf.clear()
        assert len(buf) == 0
        assert buf.get_text() == ""

    def test_clear_resets_dirty(self) -> None:
        buf = GuiLogBuffer()
        buf.append("line 1")
        buf.clear()
        assert not buf.is_dirty()

    def test_clear_resets_evicted_count(self) -> None:
        buf = GuiLogBuffer(max_lines=2)
        buf.append("a\nb\nc")
        buf.clear()
        assert buf.evicted_count == 0


class TestGuiLogBufferGetText:
    """Тесты получения текста из буфера."""

    def test_get_text_empty_buffer(self) -> None:
        buf = GuiLogBuffer()
        assert buf.get_text() == ""

    def test_get_text_joins_lines(self) -> None:
        buf = GuiLogBuffer(max_lines=10)
        buf.append("line 1\nline 2\nline 3")
        assert buf.get_text() == "line 1\nline 2\nline 3"

    def test_get_text_does_not_reset_dirty(self) -> None:
        buf = GuiLogBuffer()
        buf.append("line 1")
        _ = buf.get_text()
        assert buf.is_dirty()


class TestGuiLogBufferThreadSafety:
    """Тесты потокобезопасности буфера."""

    def test_concurrent_appends_no_data_race(self) -> None:
        """Параллельные записи не должны приводить к данным гонки."""
        buf = GuiLogBuffer(max_lines=1000)
        errors: list[Exception] = []

        def writer(prefix: str) -> None:
            try:
                for i in range(50):
                    buf.append(f"{prefix}-{i}")
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer, args=(f"t{j}",))
            for j in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(buf) <= buf.max_lines

    def test_concurrent_read_write_no_exception(self) -> None:
        """Параллельные чтение и запись не должны вызывать исключений."""
        buf = GuiLogBuffer(max_lines=100)
        errors: list[Exception] = []

        def writer() -> None:
            try:
                for i in range(30):
                    buf.append(f"line {i}")
            except Exception as e:
                errors.append(e)

        def reader() -> None:
            try:
                for _ in range(30):
                    _ = buf.get_text()
                    _ = buf.is_dirty()
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
