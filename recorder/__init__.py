"""
Пакет видеозаписи
=================

Этот пакет содержит основной функционал записи:
- VideoRecorder: Захват экрана и кодирование видео
- AudioRecorder: Захват аудио с микрофона/системы
- Encoder: Объединение видео/аудио на базе FFmpeg
- Utils: Вспомогательные функции и утилиты
"""

from .audio_recorder import AudioRecorder
from .encoder import Encoder
from .utils import check_ffmpeg, get_audio_devices, get_available_windows
from .video_recorder import VideoRecorder

__all__ = [
    "VideoRecorder",
    "AudioRecorder",
    "Encoder",
    "get_available_windows",
    "get_audio_devices",
    "check_ffmpeg",
]

__version__ = "1.0.0"
