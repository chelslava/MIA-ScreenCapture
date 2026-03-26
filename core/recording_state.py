"""
Core-модель состояния записи.

Не зависит от GUI-слоя и используется в сервисах, контроллерах и GUI.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class RecordingStatus(Enum):
    """Статус записи."""

    IDLE = "idle"
    RECORDING = "recording"
    PAUSED = "paused"


class CaptureType(Enum):
    """Тип области захвата."""

    FULL_SCREEN = "full_screen"
    WINDOW = "window"
    RECTANGLE = "rectangle"


class AudioType(Enum):
    """Тип источника аудио."""

    NONE = "none"
    MICROPHONE = "mic"
    SYSTEM = "system"
    BOTH = "both"


@dataclass
class CaptureSettings:
    """Настройки области захвата."""

    capture_type: CaptureType = CaptureType.FULL_SCREEN
    window_title: str = ""
    rect_coords: tuple[int, int, int, int] = (0, 0, 1920, 1080)


@dataclass
class AudioSettings:
    """Настройки аудио."""

    audio_type: AudioType = AudioType.NONE
    mic_device_index: Optional[int] = None
    mic_device_name: str = ""


@dataclass
class VideoSettings:
    """Настройки видео."""

    fps: int = 30
    codec: str = "libx264"
    bitrate: str = "2M"
    format: str = "mp4"


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
    """

    status: RecordingStatus = RecordingStatus.IDLE
    elapsed_time: float = 0.0
    current_output: Optional[Path] = None

    capture: CaptureSettings = field(default_factory=CaptureSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    video: VideoSettings = field(default_factory=VideoSettings)
    output: OutputSettings = field(default_factory=OutputSettings)

    recent_recordings: list[RecentRecording] = field(default_factory=list)
    recording_start_time: Optional[datetime] = None

    def is_recording(self) -> bool:
        """Проверка, идёт ли запись."""
        return self.status == RecordingStatus.RECORDING

    def is_paused(self) -> bool:
        """Проверка, на паузе ли запись."""
        return self.status == RecordingStatus.PAUSED

    def is_idle(self) -> bool:
        """Проверка, что запись не активна."""
        return self.status == RecordingStatus.IDLE

    def start_recording(self, output_path: Path) -> None:
        """Перевести в состояние записи."""
        self.status = RecordingStatus.RECORDING
        self.current_output = output_path
        self.recording_start_time = datetime.now()
        self.elapsed_time = 0.0

    def pause_recording(self) -> None:
        """Приостановить запись."""
        if self.status == RecordingStatus.RECORDING:
            self.status = RecordingStatus.PAUSED

    def resume_recording(self) -> None:
        """Возобновить запись."""
        if self.status == RecordingStatus.PAUSED:
            self.status = RecordingStatus.RECORDING

    def stop_recording(self) -> None:
        """Остановить запись."""
        self.status = RecordingStatus.IDLE
        self.recording_start_time = None

    def set_audio_type(self, audio_type: AudioType) -> None:
        """Установить тип источника аудио."""
        self.audio.audio_type = audio_type

    def add_recent_recording(self, path: Path, size: int) -> None:
        """Добавить недавнюю запись."""
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"recording_{timestamp}.{self.video.format}"
