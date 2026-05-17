"""Тесты асинхронного обновления CaptureView."""

from typing import Any

import pytest
from PyQt6.QtWidgets import QApplication

from gui.models.recording_state import CaptureType
from gui.views.capture_view import CaptureView


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

    def find_text(text: str) -> int:
        items = getattr(combo, "_items", [])
        return items.index(text) if text in items else -1

    def clear() -> None:
        combo._items = []
        combo._current_index = -1
        combo._current_text = ""

    def set_current_index(index: int) -> None:
        combo._current_index = index
        items = getattr(combo, "_items", [])
        if 0 <= index < len(items):
            combo._current_text = items[index]

    combo.clear = clear
    combo.findText = find_text
    combo.setCurrentIndex = set_current_index


def _patch_view_runtime(view: CaptureView) -> CaptureView:
    """Подготовить mock CaptureView к unit-проверкам."""
    _patch_combo_runtime(view._window_combo)
    return view


@pytest.fixture
def capture_view_environment(monkeypatch) -> None:
    """Добавить недостающие методы mock QLabel для CaptureView."""

    def set_style_sheet(self, style: str) -> None:
        self._style_sheet = style

    monkeypatch.setattr(
        "gui.views.capture_view.QLabel.setStyleSheet",
        set_style_sheet,
        raising=False,
    )


class TestCaptureViewAsyncLoading:
    """Проверки асинхронной загрузки списка окон."""

    def test_init_starts_in_loading_state(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """На старте показывается loading state без блокирующей загрузки."""
        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )

        view = _patch_view_runtime(CaptureView())

        assert view._window_status_label.text() == "Загрузка списка окон..."
        assert view._window_combo.count() == 0
        assert view._window_combo.isEnabled() is False

    def test_apply_loaded_windows_restores_pending_selection(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """После загрузки восстанавливается ранее выбранный заголовок окна."""
        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())
        view.set_capture_type(CaptureType.WINDOW)
        view.set_window_title("Browser")

        view._on_windows_load_completed(
            view._window_request_id,
            [
                {"title": "Editor"},
                {"title": "Browser"},
            ],
            None,
        )

        assert view._window_combo.count() == 2
        assert view.get_window_title() == "Browser"
        assert view._window_status_label.text() == "Доступно окон: 2"

    def test_apply_empty_windows_result_sets_empty_state(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """Пустой результат переводит view в empty state."""
        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())

        view._on_windows_load_completed(view._window_request_id, [], None)

        assert (
            view._window_status_label.text() == "Окна для захвата не найдены."
        )
        assert view._window_combo.count() == 0

    def test_stale_window_result_is_ignored(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """Устаревший результат refresh не должен перетирать новый state."""
        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())

        current_request_id = view._window_request_id
        view._refresh_windows()
        view._on_windows_load_completed(
            current_request_id,
            [{"title": "Old"}],
            None,
        )

        assert view._window_combo.count() == 0
        assert view._window_status_label.text() == "Загрузка списка окон..."

    def test_window_error_state_is_rendered(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """Ошибка фоновой загрузки должна показываться пользователю."""
        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())

        view._on_windows_load_completed(
            view._window_request_id,
            None,
            "boom",
        )

        assert "boom" in view._window_status_label.text()

    def test_accessibility_metadata_is_assigned(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """Ключевые controls захвата получают accessibility metadata."""
        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())

        assert view._window_combo._accessible_name == "Список доступных окон"
        assert view._refresh_windows_btn._accessible_name == (
            "Обновить список окон"
        )
        assert view._select_rect_btn._accessible_name == (
            "Выбрать область захвата"
        )

    def test_refresh_windows_public_delegates_to_private(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """refresh_windows() — публичный proxy к _refresh_windows()."""
        from unittest.mock import patch

        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())

        with patch.object(view, "_refresh_windows") as mock_private:
            view.refresh_windows()
            mock_private.assert_called_once_with()

    def test_focus_window_combo_sets_focus(
        self,
        qapp: QApplication,
        monkeypatch,
        capture_view_environment,
    ) -> None:
        """focus_window_combo() вызывает setFocus на _window_combo."""
        from unittest.mock import MagicMock

        monkeypatch.setattr(
            "gui.views.capture_view.threading.Thread",
            _NoopThread,
        )
        view = _patch_view_runtime(CaptureView())
        view._window_combo.setFocus = MagicMock()

        view.focus_window_combo()
        view._window_combo.setFocus.assert_called_once_with()
