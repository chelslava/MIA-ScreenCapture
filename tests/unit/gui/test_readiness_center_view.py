"""Тесты compact readiness center view."""

import pytest
from PyQt6.QtWidgets import QApplication

from core.readiness import ReadinessAction, ReadinessCheck
from gui.views.readiness_center_view import ReadinessCenterView


@pytest.fixture
def readiness_center_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подготовить mock-окружение для readiness center."""

    def set_style_sheet(self, style: str) -> None:
        self._style_sheet = style

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


class TestReadinessCenterView:
    """Проверки inline readiness center."""

    def test_loading_state_is_visible_on_init(
        self,
        qapp: QApplication,
        readiness_center_environment,
    ) -> None:
        """На старте readiness center показывает loading state."""
        view = ReadinessCenterView()

        assert view._summary_label.text() == "Проверяем готовность к записи…"
        status_label = view._row_widgets["ffmpeg"]["status_label"]
        assert status_label.text() == "Проверяем…"

    def test_apply_checks_renders_blocking_and_action(
        self,
        qapp: QApplication,
        readiness_center_environment,
    ) -> None:
        """Blocking-check должен показать summary и кнопку действия."""
        view = ReadinessCenterView()
        checks = (
            ReadinessCheck(
                key="ffmpeg",
                title="FFmpeg",
                status="blocking",
                message="FFmpeg недоступен.",
                next_step="Установите FFmpeg и проверьте PATH.",
                action=ReadinessAction(
                    key="open_ffmpeg_docs",
                    label="Открыть инструкцию",
                ),
            ),
            ReadinessCheck(
                key="output",
                title="Путь вывода",
                status="ready",
                message="Путь вывода доступен.",
            ),
            ReadinessCheck(
                key="capture",
                title="Окно захвата",
                status="not_required",
                message="Не требуется.",
            ),
            ReadinessCheck(
                key="audio",
                title="Микрофон",
                status="ready",
                message="Микрофон готов.",
            ),
        )

        view.apply_checks(checks)

        assert "Старт заблокирован" in view._summary_label.text()
        status_label = view._row_widgets["ffmpeg"]["status_label"]
        action_btn = view._row_widgets["ffmpeg"]["action_btn"]
        assert status_label.text() == "Требует внимания"
        assert action_btn.isVisible() is True
        assert action_btn.text() == "Открыть инструкцию"

    def test_row_action_emits_requested_key(
        self,
        qapp: QApplication,
        readiness_center_environment,
    ) -> None:
        """Нажатие action-кнопки должно эмитить action key."""
        view = ReadinessCenterView()
        received: list[str] = []
        view.action_requested.connect(received.append)
        view._row_actions["ffmpeg"] = "open_ffmpeg_docs"

        view._emit_row_action("ffmpeg")

        assert received == ["open_ffmpeg_docs"]
