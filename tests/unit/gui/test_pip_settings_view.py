"""Тесты настроек PiP-оверлея веб-камеры (#165)."""

from typing import Any
from unittest.mock import patch

import pytest
from PyQt6.QtWidgets import QApplication

from core.recording_types import PiPPosition
from gui.views.pip_settings_view import PipSettingsView


class _NoopThread:
    """Поток-заглушка без автоматического выполнения target."""

    def __init__(self, target: Any, args: Any = (), daemon: Any = False):
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        """Не выполнять target автоматически в unit-тесте."""


@pytest.fixture
def view(qapp: QApplication, monkeypatch) -> PipSettingsView:  # type: ignore[no-untyped-def]
    """Создать PipSettingsView без фоновых потоков."""
    monkeypatch.setattr(
        "gui.views.pip_settings_view.threading.Thread",
        _NoopThread,
    )
    return PipSettingsView()


class TestPipSettingsView:
    """Группа настроек PiP на странице записи (#165)."""

    def test_get_settings_returns_none_when_disabled(
        self, view: PipSettingsView
    ) -> None:
        """Выключенный чекбокс — наложение не активно."""
        assert view.get_pip_settings() is None

    def test_get_settings_when_enabled(self, view: PipSettingsView) -> None:
        """Включённое наложение собирает значения контролов."""
        view._enabled_check.setChecked(True)
        view._device_combo.clear()
        view._device_combo.addItem("USB Camera")
        view._device_combo.setCurrentIndex(0)
        view._position_combo.setCurrentIndex(2)  # Справа сверху
        view._size_spin.setValue(30)

        pip = view.get_pip_settings()

        assert pip is not None
        assert pip.enabled is True
        assert pip.device_name == "USB Camera"
        assert pip.position == PiPPosition.TOP_RIGHT
        assert pip.size_percent == 30

    def test_placeholder_devices_ignored(self, view: PipSettingsView) -> None:
        """Заглушка «Камеры не найдены» не попадает в настройки."""
        view._enabled_check.setChecked(True)
        view._on_devices_load_completed([])

        pip = view.get_pip_settings()

        assert pip is not None
        assert pip.device_name == ""

    def test_devices_loaded_from_worker(self, view: PipSettingsView) -> None:
        """Результат фоновой загрузки заполняет комбобокс."""
        view._on_devices_load_completed(["Cam A", "Cam B"])

        assert view._device_combo.count() == 2
        assert view._device_combo.itemText(0) == "Cam A"

    def test_devices_preserve_current_selection(
        self, view: PipSettingsView
    ) -> None:
        """Повторная загрузка сохраняет выбранную камеру."""
        view._on_devices_load_completed(["Cam A", "Cam B"])
        view._device_combo.setCurrentIndex(1)

        view._on_devices_load_completed(["Cam A", "Cam B", "Cam C"])

        assert view._device_combo.currentText() == "Cam B"

    def test_enabling_triggers_device_refresh(
        self, view: PipSettingsView
    ) -> None:
        """Первое включение запускает фоновое перечисление камер."""
        with patch.object(PipSettingsView, "_refresh_devices") as mock_refresh:
            view._on_enabled_toggled(True)

        mock_refresh.assert_called_once()

    def test_worker_reports_errors_as_empty_list(
        self, view: PipSettingsView, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Ошибка перечисления камер не ломает поток."""

        def boom() -> list:
            raise OSError("boom")

        monkeypatch.setattr("gui.views.pip_settings_view.list_cameras", boom)
        emitted: list[list] = []
        view.devices_load_completed.connect(emitted.append)

        view._load_devices_worker()

        assert emitted == [[]]

    def test_worker_lists_cameras(
        self, view: PipSettingsView, monkeypatch
    ) -> None:  # type: ignore[no-untyped-def]
        """Рабочий поток публикует имена найденных камер."""
        from recorder.camera_capture import CameraDeviceInfo

        monkeypatch.setattr(
            "gui.views.pip_settings_view.list_cameras",
            lambda: [CameraDeviceInfo(name="Cam A")],
        )
        emitted: list[list] = []
        view.devices_load_completed.connect(emitted.append)

        view._load_devices_worker()

        assert emitted == [["Cam A"]]
