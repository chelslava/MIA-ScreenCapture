"""Тесты асинхронного обновления AudioView."""

from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication

from gui.views.audio_view import AudioView


class _NoopThread:
    """Поток-заглушка без автоматического выполнения target."""

    def __init__(self, target, args=(), daemon: bool = False) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        """Не выполнять target автоматически в unit-тесте."""


def _patch_combo_runtime(combo: Any) -> None:
    """Добавить недостающие методы mock combobox для тестов."""

    def add_item(text: str, data: Any = None) -> None:
        items = getattr(combo, "_items", [])
        values = getattr(combo, "_data_items", [])
        items.append(text)
        values.append(data)
        combo._items = items
        combo._data_items = values

    def find_text(text: str) -> int:
        items = getattr(combo, "_items", [])
        return items.index(text) if text in items else -1

    def clear() -> None:
        combo._items = []
        combo._data_items = []
        combo._current_index = -1
        combo._current_text = ""
        combo._current_data = None

    def set_current_index(index: int) -> None:
        combo._current_index = index
        items = getattr(combo, "_items", [])
        values = getattr(combo, "_data_items", [])
        if 0 <= index < len(items):
            combo._current_text = items[index]
            combo._current_data = values[index]

    def current_data() -> Any:
        return getattr(combo, "_current_data", None)

    def item_data(index: int) -> Any:
        values = getattr(combo, "_data_items", [])
        if 0 <= index < len(values):
            return values[index]
        return None

    combo.addItem = add_item
    combo.clear = clear
    combo.findText = find_text
    combo.setCurrentIndex = set_current_index
    combo.currentData = current_data
    combo.itemData = item_data


def _patch_view_runtime(view: AudioView) -> AudioView:
    """Подготовить mock AudioView к unit-проверкам."""
    _patch_combo_runtime(view._mic_combo)
    return view


@pytest.fixture
def audio_view_environment(monkeypatch) -> None:
    """Добавить недостающие методы mock QLabel для AudioView."""

    def set_style_sheet(self, style: str) -> None:
        self._style_sheet = style

    monkeypatch.setattr(
        "gui.views.audio_view.QLabel.setStyleSheet",
        set_style_sheet,
        raising=False,
    )


class TestAudioViewAsyncLoading:
    """Проверки асинхронной загрузки аудиоустройств."""

    def test_init_starts_in_loading_state(
        self,
        qapp: QApplication,
        monkeypatch,
        audio_view_environment,
    ) -> None:
        """На старте view показывает loading state."""
        monkeypatch.setattr(
            "gui.views.audio_view.threading.Thread",
            _NoopThread,
        )

        view = _patch_view_runtime(AudioView())

        assert view._mic_status_label.text() == "Загрузка списка микрофонов..."
        assert view._mic_combo.count() == 0
        assert view._mic_combo.isEnabled() is False

    def test_apply_loaded_devices_restores_pending_index(
        self,
        qapp: QApplication,
        monkeypatch,
        audio_view_environment,
    ) -> None:
        """После загрузки восстанавливается выбранный индекс микрофона."""
        monkeypatch.setattr(
            "gui.views.audio_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(AudioView())
        view.set_mic_device_index(2)

        view._on_devices_load_completed(
            view._device_request_id,
            {
                "input": [
                    {"id": 1, "name": "Mic 1"},
                    {"id": 2, "name": "Mic 2"},
                ]
            },
            None,
        )

        assert view.get_mic_device_index() == 2
        assert view.get_mic_device_name() == "Mic 2"
        assert view._mic_status_label.text() == "Доступно микрофонов: 2"

    def test_apply_empty_devices_result_sets_empty_state(
        self,
        qapp: QApplication,
        monkeypatch,
        audio_view_environment,
    ) -> None:
        """Пустой список устройств показывает empty state."""
        monkeypatch.setattr(
            "gui.views.audio_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(AudioView())

        view._on_devices_load_completed(
            view._device_request_id,
            {"input": []},
            None,
        )

        assert (
            view._mic_status_label.text()
            == "Доступные устройства ввода не найдены."
        )
        assert view._mic_combo.count() == 0

    def test_stale_devices_result_is_ignored(
        self,
        qapp: QApplication,
        monkeypatch,
        audio_view_environment,
    ) -> None:
        """Устаревший refresh не должен перетирать новый state."""
        monkeypatch.setattr(
            "gui.views.audio_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(AudioView())

        current_request_id = view._device_request_id
        view._refresh_audio_devices()
        view._on_devices_load_completed(
            current_request_id,
            {"input": [{"id": 1, "name": "Old"}]},
            None,
        )

        assert view._mic_combo.count() == 0
        assert view._mic_status_label.text() == "Загрузка списка микрофонов..."

    def test_device_error_state_is_rendered(
        self,
        qapp: QApplication,
        monkeypatch,
        audio_view_environment,
    ) -> None:
        """Ошибка фоновой загрузки должна показываться пользователю."""
        monkeypatch.setattr(
            "gui.views.audio_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(AudioView())

        view._on_devices_load_completed(
            view._device_request_id,
            None,
            "boom",
        )

        assert "boom" in view._mic_status_label.text()

    def test_accessibility_metadata_is_assigned(
        self,
        qapp: QApplication,
        monkeypatch,
        audio_view_environment,
    ) -> None:
        """Ключевые controls аудио получают accessibility metadata."""
        monkeypatch.setattr(
            "gui.views.audio_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(AudioView())

        assert view._mic_combo._accessible_name == "Список микрофонов"
        assert view._refresh_mic_btn._accessible_name == (
            "Обновить список микрофонов"
        )
        assert view._both_audio_radio._accessible_name == (
            "Микрофон и системное аудио"
        )
