"""
Абстракции backend-слоя для выполнения записи.

Позволяют сервисному слою работать через стабильный core-порт,
не завися напрямую от GUI-контроллеров и моделей.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from core.recording_types import AudioRequest, CaptureRequest, VideoRequest


@dataclass(frozen=True)
class RecordingStatusSnapshot:
    """Снимок текущего состояния backend-а записи."""

    is_recording: bool
    is_paused: bool
    elapsed_time: float
    current_file: Path | None


class RecordingBackend(Protocol):
    """Порт для backend-реализации записи."""

    def get_status(self) -> RecordingStatusSnapshot:
        """Возвращает текущий снимок состояния записи."""
        ...

    def start(
        self,
        output_path: Path,
        capture: CaptureRequest,
        audio: AudioRequest,
        video: VideoRequest,
        duration: int | None = None,
    ) -> tuple[bool, str | None]:
        """Запускает запись."""
        ...

    def stop(self) -> Path | None:
        """Останавливает запись и возвращает путь к итоговому файлу."""
        ...

    def pause(self) -> bool:
        """Ставит запись на паузу."""
        ...

    def resume(self) -> bool:
        """Возобновляет запись после паузы."""
        ...
