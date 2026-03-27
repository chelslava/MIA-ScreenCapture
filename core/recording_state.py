"""
Core-модель состояния записи.

Не зависит от GUI-слоя и используется в сервисах, контроллерах и GUI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any

from core.recording_types import AudioMode, CaptureMode


class RecordingStatus(Enum):
    """Статус записи."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


# Aliases для обратной совместимости с GUI
CaptureType = CaptureMode
AudioType = AudioMode


@dataclass
class CaptureSettings:
    """Настройки области захвата."""

    capture_type: CaptureMode = CaptureMode.FULL
    window_title: str = ""
    rect_coords: tuple[int, int, int, int] = (0, 0, 1920, 1080)


@dataclass
class AudioSettings:
    """Настройки аудио."""

    audio_type: AudioMode = AudioMode.NONE
    mic_device_index: int | None = None
    mic_device_name: str = ""


@dataclass
class VideoSettings:
    """Настройки видео."""

    fps: int = 30
    codec: str = "libx264"
    bitrate: str = "2M"
    format: str = "mp4"
    preset: str = "medium"


@dataclass
class OutputSettings:
    """Настройки вывода."""

    output_path: str = ""
    default_path: str = ""


@dataclass
class RecentRecording:
    """Информация о недавней записи."""

    path: Path
    size: int
    date: str


@dataclass
class RecordingState:
    """
    Полное состояние записи.

    Содержит все настройки и текущий статус записи.
    Потокобезопасно — все операции защищены RLock.
    """

    status: RecordingStatus = RecordingStatus.IDLE
    elapsed_time: float = 0.0
    current_output: Path | None = None

    capture: CaptureSettings = field(default_factory=CaptureSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    output: OutputSettings = field(default_factory=OutputSettings)

    recent_recordings: list[RecentRecording] = field(default_factory=list)
    recording_start_time: datetime | None = None

    _lock: RLock = field(default_factory=RLock, repr=False, compare=False)

    def is_recording(self) -> bool:
        """Проверка, идёт ли запись."""
        with self._lock:
            return self.status == RecordingStatus.RECORDING

    def is_paused(self) -> bool:
        """Проверка, на паузе ли запись."""
        with self._lock:
            return self.status == RecordingStatus.PAUSED

    def is_idle(self) -> bool:
        """Проверка, что запись не активна."""
        with self._lock:
            return self.status == RecordingStatus.IDLE

    def start_recording(self, output_path: Path) -> None:
        """Перевести в состояние записи."""
        with self._lock:
            self.status = RecordingStatus.RECORDING
            self.current_output = output_path
            self.recording_start_time = datetime.now()
            self.elapsed_time = 0.0

    def pause_recording(self) -> None:
        """Приостановить запись."""
        with self._lock:
            if self.status == RecordingStatus.RECORDING:
                self.status = RecordingStatus.PAUSED

    def resume_recording(self) -> None:
        """Возобновить запись."""
        with self._lock:
            if self.status == RecordingStatus.PAUSED:
                self.status = RecordingStatus.RECORDING

    def stop_recording(self) -> None:
        """Остановить запись."""
        with self._lock:
            self.status = RecordingStatus.IDLE
            self.recording_start_time = None

    def set_audio_type(self, audio_type: AudioMode) -> None:
        """Установить тип источника аудио."""
        with self._lock:
            self.audio.audio_type = audio_type

    def add_recent_recording(self, path: Path, size: int) -> None:
        """Добавить недавнюю запись."""
        with self._lock:
            recording = RecentRecording(
                path=path,
                size=size,
                date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
            self.recent_recordings.insert(0, recording)
            if len(self.recent_recordings) > 20:
                self.recent_recordings = self.recent_recordings[:20]

    def get_output_filename(self) -> str:
        """Получить имя выходного файла по умолчанию."""
        with self._lock:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            return f"recording_{timestamp}.{self.video.format}"

    def get_status(self) -> dict[str, Any]:
        """Получить слепок текущего состояния."""
        with self._lock:
            return {
                "status": self.status.value,
                "is_recording": self.status == RecordingStatus.RECORDING,
                "is_paused": self.status == RecordingStatus.PAUSED,
                "elapsed_time": self.elapsed_time,
                "current_output": str(self.current_output)
                if self.current_output
                else None,
            }

    def set_elapsed_time(self, elapsed: float) -> None:
        """Установить время записи."""
        with self._lock:
            self.elapsed_time = elapsed
