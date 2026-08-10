"""Тесты FinalizationProgressDialog на моках PyQt6.

В проекте PyQt6 мокируется через conftest.py (см. MockQDialog в tests/).
Реальные Qt-методы (setWindowFlag, show/hide и т.п.) в mock-окружении
недоступны, поэтому тесты ограничены логической частью: cancel-signal,
propagation tracker-а, guard флагом _cancel_in_progress.
"""

from unittest.mock import MagicMock

import pytest

from gui.views.finalization_progress_dialog import FinalizationProgressDialog
from recorder.encoder import FinalizationProgressTracker


@pytest.fixture
def tracker() -> FinalizationProgressTracker:
    return FinalizationProgressTracker()


def _make_dialog(tracker: FinalizationProgressTracker) -> FinalizationProgressDialog:
    """Создать диалог с предустановленными mock-виджетами.

    MockQDialog из conftest не даёт setWindowFlag/setModal — инициализируем
    объект вручную через ``__new__`` и атрибуты, необходимые для логики.
    """
    dlg = FinalizationProgressDialog.__new__(FinalizationProgressDialog)
    # Ручная инициализация атрибутов, не требующих Qt runtime
    dlg._tracker = tracker
    dlg._poll_interval_ms = 250
    dlg._cancel_in_progress = False
    dlg._stage_label = MagicMock()
    dlg._progress = MagicMock()
    dlg._cancel_btn = MagicMock()
    dlg._poll_timer = MagicMock()
    dlg.hide = MagicMock()  # type: ignore[method-assign]
    dlg.show = MagicMock()  # type: ignore[method-assign]
    return dlg


class TestDialogConstruction:
    def test_import_and_class_exists(self) -> None:
        """Класс диалога импортируется без ошибок."""
        assert FinalizationProgressDialog is not None
        assert hasattr(FinalizationProgressDialog, "cancel_requested")


class TestDialogCancelLogic:
    def test_cancel_click_emits_signal(
        self, tracker: FinalizationProgressTracker
    ) -> None:
        dlg = _make_dialog(tracker)
        emitted: list[bool] = []
        # Сигнал — MagicMock
        dlg.cancel_requested = MagicMock()
        dlg.cancel_requested.emit = lambda: emitted.append(True)

        dlg._on_cancel_clicked()

        assert emitted == [True]
        assert dlg._cancel_in_progress is True
        dlg._cancel_btn.setEnabled.assert_called_once_with(False)

    def test_cancel_twice_emits_once(
        self, tracker: FinalizationProgressTracker
    ) -> None:
        dlg = _make_dialog(tracker)
        emitted: list[bool] = []
        dlg.cancel_requested = MagicMock()
        dlg.cancel_requested.emit = lambda: emitted.append(True)

        dlg._on_cancel_clicked()
        dlg._on_cancel_clicked()

        assert emitted == [True], "Повторный клик не должен эмитить сигнал"


class TestFinalizationProgressTrackerUIContract:
    """Контракт трекера, на который опирается диалог."""

    def test_percent_key_present(
        self, tracker: FinalizationProgressTracker
    ) -> None:
        snapshot = tracker.snapshot()
        assert "percent" in snapshot
        assert "stage" in snapshot
        assert "active" in snapshot

    def test_active_true_during_progress(
        self, tracker: FinalizationProgressTracker
    ) -> None:
        tracker.update(percent=42.0, stage="X")
        assert tracker.snapshot()["active"] is True

    def test_percent_reaches_100(
        self, tracker: FinalizationProgressTracker
    ) -> None:
        tracker.update(percent=100.0, stage="Готово")
        snapshot = tracker.snapshot()
        assert snapshot["percent"] == 100.0
        # Завершение финализации интерпретируется диалогом как завершение,
        # даже если active=True — покрытие через _poll_percent_100

