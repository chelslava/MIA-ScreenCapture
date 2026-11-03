"""Тесты устойчивости менеджера глобальных горячих клавиш."""

from unittest.mock import MagicMock

import pytest

from gui.hotkeys import (
    MOD_ALT,
    MOD_CONTROL,
    WM_HOTKEY,
    WM_QUIT,
    GlobalHotkeys,
)


class FakeThreadWin32:
    """Поток-заглушка: listener_loop выполняется синхронно."""

    def __init__(self, target=None, name=None, daemon=None):
        self.native_id = 424242
        self._target = target

    def start(self) -> None:
        self._target()


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
        monkeypatch.setattr(hk.platform, "system", lambda: "Linux")
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
        from gui.hotkeys import parse_hotkey_string

        assert parse_hotkey_string("<ctrl>+<alt>+d") == (
            MOD_CONTROL | MOD_ALT,
            0x44,
        )
        assert parse_hotkey_string("<ctrl>+<alt>+r") == (
            MOD_CONTROL | MOD_ALT,
            0x52,
        )
        assert parse_hotkey_string("<shift>+<alt>+p")[1] == 0x50
        assert parse_hotkey_string("justkey") is None
        assert parse_hotkey_string("<f5>") is None
        assert parse_hotkey_string("<ctrl>") is None

    def test_win32_start_registers_and_fires(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ) -> None:
        """Win32-слушатель регистрирует хоткеи и зажигает колбеки."""
        import gui.hotkeys as hk
        from gui.hotkeys import HotkeyAction

        registered: list[tuple[int, int, int]] = []
        fired: list[int] = []

        class FakeUser32:
            def RegisterHotKey(self, hwnd, hotkey_id, mod, vk) -> int:
                registered.append((hotkey_id, mod, vk))
                return 1

            def UnregisterHotKey(self, hwnd, hotkey_id) -> int:
                return 1

            def PostThreadMessageW(
                self, thread_id, msg, wparam, lparam
            ) -> int:
                return 1

            def GetMessageW(self, msg_ref, hwnd, lo, hi) -> int:
                # byref-объект хранит исходную структуру в _obj
                real = msg_ref._obj
                if len(fired) == 0:
                    real.message = WM_HOTKEY
                    real.wParam = registered[0][0]
                else:
                    real.message = WM_QUIT
                fired.append(len(fired))
                return 1

        # ctypes импортируется внутри _start_win32 — патчим модуль
        monkeypatch.setattr("ctypes.windll", MagicMock(user32=FakeUser32()))
        monkeypatch.setattr(hk.threading, "Thread", FakeThreadWin32)

        hotkeys = GlobalHotkeys()
        got: list[str] = []
        hotkeys.register(
            HotkeyAction.TOGGLE_DRAW_OVERLAY, lambda: got.append("d")
        )

        with caplog.at_level("INFO"):
            assert hotkeys.start() is True

        # Сообщение обработано в том же потоке (Thread замокан)
        assert got == ["d"]
        assert "Хоткей сработал" in caplog.text
        assert hotkeys._win32_thread is not None

        hotkeys.stop()
        assert hotkeys._win32_thread is None
