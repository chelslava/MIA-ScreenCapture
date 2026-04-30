"""Совместимый фасад для legacy-импортов scheduler_tab.

Новые реализации находятся в `gui.scheduler.scheduler_tab` и
`gui.scheduler.task_dialog`.
"""

from __future__ import annotations

from PyQt6.QtCore import QDate, QTime
from PyQt6.QtWidgets import QDialog, QMessageBox

from gui.scheduler.scheduler_tab import SchedulerTab
from gui.scheduler.task_dialog import TaskDialog

__all__ = [
    "SchedulerTab",
    "TaskDialog",
    "QDialog",
    "QMessageBox",
    "QDate",
    "QTime",
]
