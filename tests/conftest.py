"""
Конфигурация pytest и общие fixtures
====================================

Содержит общие fixtures для использования в тестах.
"""

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

# Добавление родительской директории в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Создание временной директории для тестов.
    
    Yields:
        Путь к временной директории
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_config_file(temp_dir: Path) -> Path:
    """
    Создание временного файла конфигурации.
    
    Args:
        temp_dir: Временная директория
        
    Returns:
        Путь к файлу конфигурации
    """
    config_data = {
        "video": {
            "fps": 30,
            "codec": "libx264",
            "bitrate": "2M",
            "format": "mp4",
            "compression": True
        },
        "audio": {
            "record_mic": True,
            "record_system": False,
            "mic_device": None,
            "system_device": None,
            "sample_rate": 44100,
            "channels": 2
        },
        "capture": {
            "area_type": "full",
            "window_title": None,
            "rect_coords": None
        },
        "output": {
            "default_path": str(temp_dir / "recordings"),
            "filename_template": "recording_{datetime}"
        },
        "api": {
            "enabled": True,
            "host": "127.0.0.1",
            "port": 5000
        },
        "scheduler": {
            "enabled": True,
            "persist_tasks": True,
            "max_concurrent_tasks": 1
        },
        "minimize_to_tray": True,
        "show_notifications": True,
        "language": "en",
        "recent_recordings": [],
        "max_recent_recordings": 20
    }

    config_path = temp_dir / "config.json"
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)

    return config_path


@pytest.fixture
def sample_recording_params() -> Dict[str, Any]:
    """
    Пример параметров записи для тестов.
    
    Returns:
        Словарь с параметрами записи
    """
    return {
        "area_type": "full",
        "window_title": None,
        "rect_coords": None,
        "audio_type": "none",
        "output_path": None,
        "fps": 30,
        "codec": "libx264",
        "bitrate": "2M",
        "duration": None
    }


@pytest.fixture
def sample_schedule_task() -> Dict[str, Any]:
    """
    Пример задачи планировщика для тестов.
    
    Returns:
        Словарь с данными задачи
    """
    return {
        "id": "test-task-001",
        "name": "Тестовая запись",
        "schedule_type": "once",
        "params": {
            "area_type": "full",
            "audio_type": "none",
            "fps": 30,
            "codec": "libx264",
            "bitrate": "2M"
        },
        "enabled": True,
        "start_time": "2026-03-18T12:00:00",
        "time_of_day": None,
        "days_of_week": None,
        "interval_minutes": None,
        "interval_hours": None
    }


@pytest.fixture
def temp_video_file(temp_dir: Path) -> Path:
    """
    Создание временного видеофайла (пустой файл с расширением .mp4).
    
    Args:
        temp_dir: Временная директория
        
    Returns:
        Путь к видеофайлу
    """
    video_path = temp_dir / "test_video.mp4"
    video_path.write_bytes(b"fake video content")
    return video_path


@pytest.fixture
def temp_audio_file(temp_dir: Path) -> Path:
    """
    Создание временного аудиофайла (пустой файл с расширением .wav).
    
    Args:
        temp_dir: Временная директория
        
    Returns:
        Путь к аудиофайлу
    """
    audio_path = temp_dir / "test_audio.wav"
    audio_path.write_bytes(b"fake audio content")
    return audio_path


@pytest.fixture
def mock_config_manager(temp_config_file: Path):
    """
    Создание mock ConfigManager для тестов.
    
    Args:
        temp_config_file: Путь к временному файлу конфигурации
        
    Returns:
        Экземпляр ConfigManager
    """
    from config import ConfigManager
    return ConfigManager(temp_config_file)


@pytest.fixture
def mock_logger():
    """
    Создание mock логгера для тестов.
    
    Returns:
        Mock логгер
    """
    import logging

    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)

    # Добавление handler для вывода в консоль
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


@pytest.fixture
def tasks_file(temp_dir: Path) -> Path:
    """
    Создание временного файла задач планировщика.
    
    Args:
        temp_dir: Временная директория
        
    Returns:
        Путь к файлу задач
    """
    tasks_path = temp_dir / "tasks.json"
    tasks_path.write_text("[]")
    return tasks_path
