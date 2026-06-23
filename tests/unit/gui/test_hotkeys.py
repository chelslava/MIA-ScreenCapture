"""Тесты устойчивости менеджера глобальных горячих клавиш."""

import pytest

from gui.hotkeys import GlobalHotkeys


class TestGlobalHotkeysResilience:
    """Проверки поведения в ветках ошибок stop/listener."""

    def test_stop_logs_warning_when_listener_stop_fails(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ошибка остановки listener должна логироваться и не падать."""
        hotkeys = GlobalHotkeys()

        class BrokenListener:
            """Слушатель, имитирующий сбой в stop()."""

            @staticmethod
            def stop() -> None:
                raise RuntimeError("listener stop failed")

        hotkeys._listener = BrokenListener()
        hotkeys._running = True

        with caplog.at_level("WARNING"):
            hotkeys.stop()

        assert "Не удалось корректно остановить hotkey listener" in caplog.text
        assert hotkeys._listener is None
        assert hotkeys._running is False
