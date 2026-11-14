"""Юнит-тесты отчётов о падениях (#192).

Проверяют установку глобальных хуков, запись отчёта о необработанном
исключении (включая стеки потоков), best-effort поведение мини-дампа
и жизненный цикл «нового отчёта» через маркер показанности.
"""

import sys
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from core import crash_reporting
from core.crash_reporting import (
    _make_excepthook,
    _write_crash_report,
    consume_pending_crash_report,
    get_crash_dir,
    install_crash_handlers,
)


@pytest.fixture
def crash_dir(tmp_path: Path) -> Path:
    """Изолированная директория отчётов о падениях."""
    return tmp_path / "logs" / "crash"


@pytest.fixture
def restored_hooks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Восстановление глобальных хуков после теста.

    setattr на старте фиксирует оригинал: после теста monkeypatch
    вернёт именно его, а не хук, установленный тестом.
    """
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)
    monkeypatch.setattr(threading, "excepthook", threading.__excepthook__)


class TestWriteCrashReport:
    """Запись текстового отчёта о падении."""

    def test_report_contains_exception_and_stack(
        self, crash_dir: Path
    ) -> None:
        """Отчёт содержит тип исключения и полный трейсбэк."""
        try:
            raise ValueError("падение приложения")
        except ValueError:
            report = _write_crash_report(crash_dir, *sys.exc_info())

        text = report.read_text(encoding="utf-8")
        assert report.exists()
        assert "ValueError: падение приложения" in text
        assert "Traceback" in text
        assert "Стеки потоков" in text

    def test_report_includes_other_thread_stacks(
        self, crash_dir: Path
    ) -> None:
        """В отчёт попадают стеки посторонних живых потоков."""
        holder: list[threading.Thread] = []

        def _spin() -> None:
            # Живый поток ждёт флага, чтобы его стек попал в отчёт
            while not holder:
                threading.Event().wait(0.01)

        thread = threading.Thread(target=_spin, name="crash-test-thread")
        thread.start()
        try:
            try:
                raise RuntimeError("boom")
            except RuntimeError:
                report = _write_crash_report(crash_dir, *sys.exc_info())
        finally:
            holder.append(thread)
            thread.join(timeout=5)

        text = report.read_text(encoding="utf-8")
        assert "crash-test-thread" in text


class TestCrashHandlers:
    """Установка глобальных хуков падений."""

    def test_install_replaces_hooks_and_returns_dir(
        self, crash_dir: Path, restored_hooks: None
    ) -> None:
        """Хуки заменяются, директория создаётся."""
        old_sys_hook = sys.excepthook
        result = install_crash_handlers(crash_dir)

        assert result == crash_dir
        assert crash_dir.exists()
        assert sys.excepthook is not old_sys_hook
        assert sys.excepthook is not sys.__excepthook__

    def test_excepthook_writes_report(
        self, crash_dir: Path, restored_hooks: None
    ) -> None:
        """Необработанное исключение оставляет отчёт в logs/crash."""
        install_crash_handlers(crash_dir)
        hook = sys.excepthook
        try:
            raise IndexError("проверка excepthook")
        except IndexError:
            with (
                patch.object(
                    crash_reporting, "_write_minidump", return_value=None
                ),
                patch.object(crash_reporting.logger, "error") as mock_error,
            ):
                hook(*sys.exc_info())

        reports = list(crash_dir.glob("crash_*.txt"))
        assert len(reports) == 1
        assert "IndexError: проверка excepthook" in reports[0].read_text(
            encoding="utf-8"
        )
        mock_error.assert_called_once()

    def test_excepthook_survives_report_write_failure(
        self, crash_dir: Path, restored_hooks: None
    ) -> None:
        """Сбой записи отчёта не роняет хук (исключение глотается)."""
        hook = _make_excepthook(sys.__excepthook__, crash_dir)
        with (
            patch.object(
                crash_reporting,
                "_write_crash_report",
                side_effect=OSError("диск недоступен"),
            ),
            patch.object(crash_reporting.logger, "exception") as mock_log,
        ):
            try:
                raise RuntimeError("x")
            except RuntimeError:
                hook(*sys.exc_info())
        mock_log.assert_called_once()

    def test_threading_excepthook_writes_report(
        self, crash_dir: Path, restored_hooks: None
    ) -> None:
        """Исключение в потоке оставляет отчёт с именем потока."""
        install_crash_handlers(crash_dir)
        hook = threading.excepthook

        try:
            raise KeyError("ошибка потока")
        except KeyError:
            # ExceptHookArgs — structseq, не конструируется напрямую;
            # хук читает атрибуты утиной типизацией
            args = SimpleNamespace(
                exc_type=KeyError,
                exc_value=KeyError("ошибка потока"),
                exc_traceback=sys.exc_info()[2],
                thread=threading.current_thread(),
            )
        hook(args)

        reports = list(crash_dir.glob("crash_*.txt"))
        assert len(reports) == 1
        assert "KeyError" in reports[0].read_text(encoding="utf-8")

    def test_faulthandler_enabled_with_file(
        self, crash_dir: Path, restored_hooks: None, tmp_path: Path
    ) -> None:
        """faulthandler включается с файлом в директории падений."""
        fake_fh = MagicMock(is_enabled=MagicMock(return_value=False))
        with (
            patch.object(crash_reporting, "faulthandler", fake_fh),
            patch.object(crash_reporting, "threading") as _,
        ):
            install_crash_handlers(crash_dir)
        fake_fh.enable.assert_called_once()
        (file_handle,) = fake_fh.enable.call_args.kwargs.values()
        assert file_handle.name.startswith(str(crash_dir))
        assert (
            crash_reporting.FAULTHANDLER_LOG_PREFIX
            in Path(file_handle.name).name
        )


class TestMinidump:
    """Мини-дамп: best effort, безопасные отказы."""

    def test_non_windows_returns_none(self, tmp_path: Path) -> None:
        """На не-Windows платформе дамп не создаётся."""
        with patch.object(crash_reporting.sys, "platform", "linux"):
            assert (
                crash_reporting._write_minidump(tmp_path / "crash.txt") is None
            )

    def test_api_failure_returns_none(self, tmp_path: Path) -> None:
        """Недоступность dbghelp не роняет обработчик падения."""
        with (
            patch.object(crash_reporting.sys, "platform", "win32"),
            patch.object(
                crash_reporting.ctypes,
                "WinDLL",
                side_effect=OSError("dbghelp отсутствует"),
            ),
        ):
            assert (
                crash_reporting._write_minidump(tmp_path / "crash.txt") is None
            )

    def test_failed_dump_returns_none(self, tmp_path: Path) -> None:
        """Нулевой результат MiniDumpWriteDump — отказ без исключения."""

        class FakeKernel32:
            @staticmethod
            def CreateFileW(*_args: object) -> int:
                return 123

            @staticmethod
            def GetCurrentProcess() -> int:
                return -1

            @staticmethod
            def GetCurrentProcessId() -> int:
                return 4242

            @staticmethod
            def CloseHandle(_handle: object) -> int:
                return 1

        class FakeDbgHelp:
            @staticmethod
            def MiniDumpWriteDump(*_args: object) -> int:
                return 0

        def fake_windll(name: str) -> object:
            return FakeKernel32() if name == "kernel32" else FakeDbgHelp()

        with (
            patch.object(crash_reporting.sys, "platform", "win32"),
            patch.object(crash_reporting.ctypes, "WinDLL", fake_windll),
        ):
            assert (
                crash_reporting._write_minidump(tmp_path / "crash.txt") is None
            )


class TestConsumePendingCrashReport:
    """Жизненный цикл «нового отчёта о падении»."""

    def test_empty_dir_returns_none(self, crash_dir: Path) -> None:
        """Без отчётов нового нет."""
        assert consume_pending_crash_report(crash_dir) is None

    def test_first_report_is_pending(self, crash_dir: Path) -> None:
        """Первый отчёт считается непоказанным."""
        crash_dir.mkdir(parents=True)
        report = crash_dir / "crash_20260101_120000.txt"
        report.write_text("x", encoding="utf-8")

        assert consume_pending_crash_report(crash_dir) == report

    def test_second_call_returns_none(self, crash_dir: Path) -> None:
        """Повторный вызов с тем же отчётом возвращает None."""
        crash_dir.mkdir(parents=True)
        report = crash_dir / "crash_20260101_120000.txt"
        report.write_text("x", encoding="utf-8")

        consume_pending_crash_report(crash_dir)
        assert consume_pending_crash_report(crash_dir) is None

    def test_newer_report_is_returned(self, crash_dir: Path) -> None:
        """После нового падения возвращается свежий отчёт."""
        crash_dir.mkdir(parents=True)
        (crash_dir / "crash_20260101_120000.txt").write_text(
            "старый", encoding="utf-8"
        )
        consume_pending_crash_report(crash_dir)
        newer = crash_dir / "crash_20260102_120000.txt"
        newer.write_text("новый", encoding="utf-8")

        assert consume_pending_crash_report(crash_dir) == newer

    def test_unreadable_marker_still_returns_report(
        self, crash_dir: Path
    ) -> None:
        """Сбой чтения маркера не скрывает свежий отчёт."""
        crash_dir.mkdir(parents=True)
        report = crash_dir / "crash_20260101_120000.txt"
        report.write_text("x", encoding="utf-8")
        (crash_dir / crash_reporting.SEEN_MARKER_FILE).write_text(
            "crash_99999999_000000.txt", encoding="utf-8"
        )

        # Маркер не совпадает с отчётом — отчёт считается новым
        assert consume_pending_crash_report(crash_dir) == report


class TestGetCrashDir:
    """Директория отчётов внутри стандартных логов."""

    def test_crash_dir_under_log_dir(self, tmp_path: Path) -> None:
        """logs/crash относительно get_log_dir()."""
        with patch.object(
            crash_reporting, "get_log_dir", return_value=tmp_path / "logs"
        ):
            result = get_crash_dir()
        assert result == tmp_path / "logs" / "crash"
        assert result.exists()
