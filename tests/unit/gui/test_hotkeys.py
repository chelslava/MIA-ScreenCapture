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

    def test_on_activate_logs_and_dispatches(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Срабатывание хоткея логируется и вызывает callback (#159).

        Fake-GlobalHotKeys сохраняет переданный mapping колбеков;
        вызов любого из них выполняет настоящее замыкание on_activate
        внутри start() — покрытие лог-строки без реального хука.
        """
        import gui.hotkeys as hk
        from gui.hotkeys import HotkeyAction

        captured: dict = {}

        class FakeListener:
            def __init__(self, mapping: dict) -> None:
                captured.update(mapping)

            def start(self) -> None:
                pass

            def stop(self) -> None:
                pass

        monkeypatch.setattr(hk, "PYNPUT_AVAILABLE", True)
        monkeypatch.setattr(
            hk.keyboard, "GlobalHotKeys", FakeListener, raising=False
        )

        hotkeys = GlobalHotkeys()
        fired: list[str] = []
        hotkeys.register(
            HotkeyAction.TOGGLE_DRAW_OVERLAY,
            lambda: fired.append("draw"),
        )

        with caplog.at_level("INFO"):
            assert hotkeys.start() is True
            for callback in captured.values():
                callback()

        assert fired == ["draw"]
        assert "Хоткей сработал" in caplog.text
