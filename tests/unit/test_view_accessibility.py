"""Тесты accessibility metadata для secondary views."""

import pytest
from PyQt6.QtWidgets import QApplication

from gui.scheduler_tab import SchedulerTab
from gui.views.diagnostics_view import DiagnosticsView
from gui.views.output_view import OutputView
from gui.views.readiness_center_view import ReadinessCenterView
from gui.views.video_view import VideoView


@pytest.fixture
def view_accessibility_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подготовить mock-окружение для secondary views."""

    def set_style_sheet(self, style: str) -> None:
        self._style_sheet = style

    def set_widget_resizable(self, value: bool) -> None:
        self._widget_resizable = value

    def set_horizontal_scroll_bar_policy(self, policy) -> None:
        self._scroll_policy = policy

    def set_widget(self, widget) -> None:
        self._child_widget = widget

    def set_object_name(self, name: str) -> None:
        self._object_name = name

    def set_alignment(self, alignment) -> None:
        self._alignment = alignment

    monkeypatch.setattr(
        "gui.views.diagnostics_view.QLabel.setStyleSheet",
        set_style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.diagnostics_view.QGroupBox.setStyleSheet",
        set_style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.diagnostics_view.QScrollArea.setWidgetResizable",
        set_widget_resizable,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.diagnostics_view.QScrollArea.setHorizontalScrollBarPolicy",
        set_horizontal_scroll_bar_policy,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.diagnostics_view.QScrollArea.setWidget",
        set_widget,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.diagnostics_view.QLabel.setObjectName",
        set_object_name,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.diagnostics_view.QPushButton.setObjectName",
        set_object_name,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.readiness_center_view.QLabel.setStyleSheet",
        set_style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.views.readiness_center_view.QGroupBox.setStyleSheet",
        set_style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        "gui.scheduler.scheduler_tab.QLabel.setAlignment",
        set_alignment,
        raising=False,
    )


class TestSecondaryViewAccessibility:
    """Проверки accessible metadata на secondary views."""

    def test_output_view_accessibility_metadata(
        self,
        qapp: QApplication,
        view_accessibility_environment,
    ) -> None:
        """OutputView получает metadata для поля пути и кнопки обзора."""
        view = OutputView()

        assert view._output_edit._accessible_name == "Путь вывода записи"
        assert view._browse_btn._accessible_name == "Выбрать путь вывода"

    def test_video_view_accessibility_metadata(
        self,
        qapp: QApplication,
        view_accessibility_environment,
    ) -> None:
        """VideoView получает metadata для основных видеонастроек."""
        view = VideoView()

        assert view._fps_spin._accessible_name == "Частота кадров"
        assert view._codec_combo._accessible_name == "Видеокодек"
        assert view._preset_combo._accessible_name == "Скорость кодирования"

    def test_diagnostics_view_accessibility_metadata(
        self,
        qapp: QApplication,
        view_accessibility_environment,
    ) -> None:
        """DiagnosticsView получает metadata для кнопок действий."""
        view = DiagnosticsView()

        assert view._recheck_btn._accessible_name == "Повторить диагностику"
        assert view._logs_btn._accessible_name == "Открыть логи приложения"

    def test_readiness_center_accessibility_metadata(
        self,
        qapp: QApplication,
        view_accessibility_environment,
    ) -> None:
        """ReadinessCenterView получает metadata для summary и действий."""
        view = ReadinessCenterView()

        assert (
            view._summary_label._accessible_name
            == "Сводка готовности к записи"
        )
        assert (
            view._refresh_btn._accessible_name
            == "Повторить readiness-проверку"
        )
        assert (
            view._details_btn._accessible_name == "Открыть полную диагностику"
        )

    def test_scheduler_tab_accessibility_metadata(
        self,
        qapp: QApplication,
        view_accessibility_environment,
    ) -> None:
        """SchedulerTab получает metadata для toolbar и таблицы задач."""
        view = SchedulerTab()

        assert view.add_btn._accessible_name == "Добавить задачу планировщика"
        assert (
            view.edit_btn._accessible_name
            == "Редактировать задачу планировщика"
        )
        assert view.table._accessible_name == "Список задач планировщика"
