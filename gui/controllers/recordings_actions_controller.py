"""
Открытие записей из главного окна (#164, #186)
==============================================

Миксин ``RecordingsActionsControllerMixin``: открытие последней записи
и папки записи через desktop-действия (хоткеи, трей). Раньше операции
работали со списком ``RecordingsListWidget``; страница «Записи» заменена
на ``LibraryView`` (#186), поэтому действия читают недавние записи
из состояния приложения, а операции над файлами (теги, переименование,
удаление, постобработка) выполняются в контекстном меню библиотеки.
"""

from __future__ import annotations

import os
import platform
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow

    from gui.models.recording_state import RecordingState


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class RecordingsActionsControllerMixin(_QWindowBase):
    """Открытие последних записей через desktop-действия окна."""

    if TYPE_CHECKING:
        # Общие атрибуты окна
        _state: RecordingState

    def _open_latest_recording(self) -> None:
        """Открытие самой свежей существующей записи."""
        for rec in self._state.recent_recordings:
            if rec.path.exists():
                self._open_file(str(rec.path))
                return

    def _open_recording_folder(self) -> None:
        """Открытие папки со самой свежей записью."""
        for rec in self._state.recent_recordings:
            if rec.path.exists():
                self._open_folder(str(rec.path.parent))
                return

    def _open_file(self, path: str) -> None:
        """Открытие файла с помощью системного приложения по умолчанию."""
        system = platform.system()
        if system == "Windows":
            # os.startfile is Windows-specific and not in type stubs
            os.startfile(path)  # type: ignore[attr-defined, unused-ignore]
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def _open_folder(self, path: str) -> None:
        """Открытие папки в файловом менеджере."""
        system = platform.system()
        if system == "Windows":
            subprocess.run(["explorer", path])
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])
