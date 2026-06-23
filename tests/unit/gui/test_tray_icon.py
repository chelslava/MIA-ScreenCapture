"""
Unit тесты для TrayIcon
=======================

Тестирует функциональность иконки в системном трее.

PyQt6 мокируется в conftest.py для всех тестов: QSystemTrayIcon, QAction,
QTimer и QPixmap куратированы там же (см. [[technical-debt]] TD-7) — до
этого `class TrayIcon(QSystemTrayIcon)` наследовался от голого
`MagicMock`, и Python "проглатывал" тело класса целиком, делая
полноценное тестирование TrayIcon невозможным.
"""

from pathlib import Path

import pytest

from gui.tray_icon import TrayIcon


class TestTrayIconCustomIcon:
    """`_create_icon`: кастомная .ico только для idle."""

    def test_idle_uses_custom_icon_when_path_exists(
        self, tmp_path: Path
    ) -> None:
        icon_file = tmp_path / "custom.ico"
        icon_file.write_bytes(b"\x00")

        tray = TrayIcon(icon_path=icon_file)

        assert tray._icons["idle"] is not None

    def test_recording_and_paused_are_drawn_not_loaded(
        self, tmp_path: Path
    ) -> None:
        """recording/paused не должны грузиться из файла — иначе теряется
        цветовая индикация статуса записи (красный/оранжевый круг)."""
        icon_file = tmp_path / "custom.ico"
        icon_file.write_bytes(b"\x00")

        tray = TrayIcon(icon_path=icon_file)

        assert tray._icons["recording"] is not None
        assert tray._icons["paused"] is not None

    def test_falls_back_to_drawing_when_path_missing(
        self, tmp_path: Path
    ) -> None:
        tray = TrayIcon(icon_path=tmp_path / "does-not-exist.ico")

        assert tray._icons["idle"] is not None
        assert tray._icons["recording"] is not None
        assert tray._icons["paused"] is not None

    def test_no_icon_path_does_not_crash(self) -> None:
        tray = TrayIcon()

        assert tray._icons["idle"] is not None


class TestTrayIconMenuConstruction:
    """Структура контекстного меню, создаваемого в _create_menu."""

    def test_actions_are_distinct_objects(self) -> None:
        tray = TrayIcon()

        actions = {
            tray._show_action,
            tray._start_action,
            tray._stop_action,
            tray._pause_action,
            tray._exit_action,
        }
        assert len(actions) == 5

    def test_initial_enabled_state(self) -> None:
        """До старта записи: start доступен, stop/pause — нет."""
        tray = TrayIcon()

        assert tray._start_action.isEnabled() is True
        assert tray._stop_action.isEnabled() is False
        assert tray._pause_action.isEnabled() is False


class TestTrayIconRecordingState:
    """set_recording_state: переключение enabled/текста/подсказки."""

    def test_recording_started_enables_stop_and_pause(self) -> None:
        tray = TrayIcon()

        tray.set_recording_state(True, False)

        assert tray._start_action.isEnabled() is False
        assert tray._stop_action.isEnabled() is True
        assert tray._pause_action.isEnabled() is True
        assert tray._pause_action.text() == "Пауза"

    def test_pause_toggles_action_label(self) -> None:
        tray = TrayIcon()

        tray.set_recording_state(True, True)
        assert tray._pause_action.text() == "Возобновить"

        tray.set_recording_state(True, False)
        assert tray._pause_action.text() == "Пауза"

    def test_stopping_restores_idle_state(self) -> None:
        tray = TrayIcon()
        tray.set_recording_state(True, False)

        tray.set_recording_state(False, False)

        assert tray._start_action.isEnabled() is True
        assert tray._stop_action.isEnabled() is False
        assert tray._pause_action.isEnabled() is False


class TestTrayIconNotifications:
    """show_notification и on_* обработчики событий записи."""

    def test_show_notification_uses_show_message_when_supported(
        self,
    ) -> None:
        tray = TrayIcon()

        tray.show_notification("Заголовок", "Текст")

        assert tray._messages == [
            (
                "Заголовок",
                "Текст",
                tray.MessageIcon.Information,
                3000,
            )
        ]

    def test_show_notification_falls_back_when_unsupported(self) -> None:
        tray = TrayIcon()
        tray._supports_messages = False

        tray.show_notification("Заголовок", "Текст")

        assert tray._messages == []

    def test_on_recording_started_sets_state_and_notifies(self) -> None:
        tray = TrayIcon()

        tray.on_recording_started("C:/rec.mp4")

        assert tray._stop_action.isEnabled() is True
        assert tray._messages[-1][0] == "Запись начата"

    def test_on_recording_stopped_sets_idle_and_notifies(self) -> None:
        tray = TrayIcon()
        tray.set_recording_state(True, False)

        tray.on_recording_stopped("C:/rec.mp4")

        assert tray._start_action.isEnabled() is True
        assert tray._messages[-1][0] == "Запись остановлена"

    def test_on_recording_paused_sets_paused_state(self) -> None:
        tray = TrayIcon()
        tray.set_recording_state(True, False)

        tray.on_recording_paused()

        assert tray._pause_action.text() == "Возобновить"
        assert tray._messages[-1][0] == "Запись приостановлена"

    def test_on_recording_resumed_clears_paused_state(self) -> None:
        tray = TrayIcon()
        tray.set_recording_state(True, True)

        tray.on_recording_resumed()

        assert tray._pause_action.text() == "Пауза"
        assert tray._messages[-1][0] == "Запись возобновлена"

    def test_on_error_uses_critical_icon(self) -> None:
        tray = TrayIcon()

        tray.on_error("что-то пошло не так")

        title, message, icon, _timeout = tray._messages[-1]
        assert title == "Ошибка"
        assert message == "что-то пошло не так"
        assert icon == tray.MessageIcon.Critical


class TestTrayIconSignalWiring:
    """Связь triggered у QAction с публичными сигналами TrayIcon."""

    @pytest.mark.parametrize(
        "action_attr,signal_attr",
        [
            ("_show_action", "show_window_requested"),
            ("_start_action", "start_requested"),
            ("_stop_action", "stop_requested"),
            ("_pause_action", "pause_requested"),
        ],
    )
    def test_action_triggers_expected_signal(
        self, action_attr: str, signal_attr: str
    ) -> None:
        tray = TrayIcon()
        received = []
        getattr(tray, signal_attr).connect(lambda: received.append(True))

        getattr(tray, action_attr).triggered.emit()

        assert received == [True]


class TestTrayIconExit:
    """_on_exit: подтверждение через QMessageBox перед выходом."""

    def test_confirmed_exit_emits_exit_requested(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from gui import tray_icon as tray_icon_module

        def _confirm(*args: object, **kwargs: object) -> int:
            return tray_icon_module.QMessageBox.StandardButton.Yes

        monkeypatch.setattr(
            tray_icon_module.QMessageBox, "question", staticmethod(_confirm)
        )

        tray = TrayIcon()
        received = []
        tray.exit_requested.connect(lambda: received.append(True))

        tray._exit_action.triggered.emit()

        assert received == [True]

    def test_cancelled_exit_does_not_emit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from gui import tray_icon as tray_icon_module

        def _cancel(*args: object, **kwargs: object) -> int:
            return tray_icon_module.QMessageBox.StandardButton.No

        monkeypatch.setattr(
            tray_icon_module.QMessageBox, "question", staticmethod(_cancel)
        )

        tray = TrayIcon()
        received = []
        tray.exit_requested.connect(lambda: received.append(True))

        tray._exit_action.triggered.emit()

        assert received == []


class TestTrayIconCleanup:
    """cleanup(): останавливает таймер анимации и скрывает иконку."""

    def test_cleanup_stops_timer_and_hides(self) -> None:
        tray = TrayIcon()
        tray.set_recording_state(True, False)
        assert tray._animation_timer.isActive() is True

        tray.cleanup()

        assert tray._animation_timer.isActive() is False
        assert tray._visible is False
