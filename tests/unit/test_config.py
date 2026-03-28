"""
Тесты для модуля конфигурации
=============================

Проверяет функциональность ConfigManager и связанных dataclasses.
"""

import json
import threading
from pathlib import Path

from config import (
    APISettings,
    AppSettings,
    AudioSettings,
    CaptureSettings,
    ConfigManager,
    OutputSettings,
    SchedulerSettings,
    VideoSettings,
    get_config,
    init_config,
)


class TestVideoSettings:
    """Тесты для VideoSettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = VideoSettings()

        assert settings.fps == 30
        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.format == "mp4"
        assert settings.compression is True

    def test_custom_values(self):
        """Проверка пользовательских значений."""
        settings = VideoSettings(
            fps=60, codec="h264", bitrate="5M", format="mkv", compression=False
        )

        assert settings.fps == 60
        assert settings.codec == "h264"
        assert settings.bitrate == "5M"
        assert settings.format == "mkv"
        assert settings.compression is False


class TestAudioSettings:
    """Тесты для AudioSettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = AudioSettings()

        assert settings.record_mic is True
        assert settings.record_system is False
        assert settings.mic_device is None
        assert settings.system_device is None
        assert settings.sample_rate == 44100
        assert settings.channels == 2

    def test_custom_values(self):
        """Проверка пользовательских значений."""
        settings = AudioSettings(
            record_mic=False,
            record_system=True,
            mic_device="device_1",
            sample_rate=48000,
            channels=1,
        )

        assert settings.record_mic is False
        assert settings.record_system is True
        assert settings.mic_device == "device_1"
        assert settings.sample_rate == 48000
        assert settings.channels == 1


class TestCaptureSettings:
    """Тесты для CaptureSettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = CaptureSettings()

        assert settings.area_type == "full"
        assert settings.window_title is None
        assert settings.rect_coords is None

    def test_custom_values(self):
        """Проверка пользовательских значений."""
        settings = CaptureSettings(
            area_type="rect", rect_coords=[100, 100, 800, 600]
        )

        assert settings.area_type == "rect"
        assert settings.rect_coords == [100, 100, 800, 600]


class TestOutputSettings:
    """Тесты для OutputSettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = OutputSettings()

        assert settings.default_path == ""
        assert settings.filename_template == "recording_{datetime}"

    def test_custom_values(self):
        """Проверка пользовательских значений."""
        settings = OutputSettings(
            default_path="/home/user/videos",
            filename_template="screen_{datetime}_test",
        )

        assert settings.default_path == "/home/user/videos"
        assert settings.filename_template == "screen_{datetime}_test"


class TestAPISettings:
    """Тесты для APISettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = APISettings()

        assert settings.enabled is True
        assert settings.host == "127.0.0.1"
        assert settings.port == 5000

    def test_custom_values(self):
        """Проверка пользовательских значений."""
        settings = APISettings(enabled=False, host="0.0.0.0", port=8080)

        assert settings.enabled is False
        assert settings.host == "0.0.0.0"
        assert settings.port == 8080


class TestSchedulerSettings:
    """Тесты для SchedulerSettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = SchedulerSettings()

        assert settings.enabled is True
        assert settings.persist_tasks is True
        assert settings.max_concurrent_tasks == 1


class TestAppSettings:
    """Тесты для AppSettings dataclass."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        settings = AppSettings()

        assert isinstance(settings.video, VideoSettings)
        assert isinstance(settings.audio, AudioSettings)
        assert isinstance(settings.capture, CaptureSettings)
        assert isinstance(settings.output, OutputSettings)
        assert isinstance(settings.api, APISettings)
        assert isinstance(settings.scheduler, SchedulerSettings)
        assert settings.minimize_to_tray is True
        assert settings.show_notifications is True
        assert settings.language == "en"
        assert settings.recent_recordings == []
        assert settings.max_recent_recordings == 20

    def test_nested_settings(self):
        """Проверка вложенных настроек."""
        settings = AppSettings(
            video=VideoSettings(fps=60), audio=AudioSettings(sample_rate=48000)
        )

        assert settings.video.fps == 60
        assert settings.audio.sample_rate == 48000


class TestConfigManager:
    """Тесты для ConfigManager."""

    def test_init_with_default_path(self, temp_dir: Path, monkeypatch):
        """Проверка инициализации с путём по умолчанию."""
        # Создаём директорию config во временной директории
        config_dir = temp_dir / "config"
        config_dir.mkdir(exist_ok=True)

        # Подменяем путь к конфигурации
        monkeypatch.setattr("config.CONFIG_DIR", config_dir)
        monkeypatch.setattr("config.CONFIG_FILE", config_dir / "config.json")

        manager = ConfigManager()

        assert manager.config_path == config_dir / "config.json"
        assert isinstance(manager.settings, AppSettings)

    def test_init_with_custom_path(self, temp_config_file: Path):
        """Проверка инициализации с пользовательским путём."""
        manager = ConfigManager(temp_config_file)

        assert manager.config_path == temp_config_file
        assert isinstance(manager.settings, AppSettings)

    def test_load_existing_config(self, temp_config_file: Path):
        """Проверка загрузки существующей конфигурации."""
        manager = ConfigManager(temp_config_file)

        assert manager.settings.video.fps == 30
        assert manager.settings.video.codec == "libx264"
        assert manager.settings.api.port == 5000

    def test_load_nonexistent_config(self, temp_dir: Path):
        """Проверка загрузки несуществующей конфигурации (создание по умолчанию)."""
        config_path = temp_dir / "nonexistent_config.json"
        manager = ConfigManager(config_path)

        assert isinstance(manager.settings, AppSettings)
        assert manager.settings.video.fps == 30  # Значение по умолчанию

    def test_save_config(self, temp_config_file: Path):
        """Проверка сохранения конфигурации."""
        manager = ConfigManager(temp_config_file)

        # Изменение настроек
        manager.settings.video.fps = 60
        manager.settings.api.port = 8080

        # Сохранение
        result = manager.save()

        assert result is True

        # Перезагрузка и проверка
        manager2 = ConfigManager(temp_config_file)
        assert manager2.settings.video.fps == 60
        assert manager2.settings.api.port == 8080

    def test_save_config_uses_atomic_replace(
        self, temp_config_file: Path, monkeypatch
    ):
        """Проверка атомарной записи через os.replace."""
        manager = ConfigManager(temp_config_file)
        replace_calls: list[tuple[Path, Path]] = []

        def fake_replace(src, dst):
            replace_calls.append((Path(src), Path(dst)))
            Path(dst).write_text(
                Path(src).read_text(encoding="utf-8"), encoding="utf-8"
            )

        monkeypatch.setattr("utils.os.replace", fake_replace)

        assert manager.save() is True
        assert replace_calls
        src, dst = replace_calls[0]
        assert src.parent == dst.parent
        assert src != dst
        assert dst == temp_config_file

    def test_save_config_returns_false_on_atomic_failure(
        self, temp_config_file: Path, monkeypatch
    ):
        """Проверка обработки ошибки при атомарной записи."""
        manager = ConfigManager(temp_config_file)
        temp_config_file.write_text('{"keep": true}', encoding="utf-8")

        def failing_replace(src, dst):
            raise OSError("replace failed")

        monkeypatch.setattr("utils.os.replace", failing_replace)

        assert manager.save() is False
        assert json.loads(temp_config_file.read_text(encoding="utf-8")) == {
            "keep": True
        }

    def test_update_settings(self, temp_config_file: Path):
        """Проверка обновления настроек."""
        manager = ConfigManager(temp_config_file)

        # Обновление настроек
        manager.update(minimize_to_tray=False, language="ru")

        assert manager.settings.minimize_to_tray is False
        assert manager.settings.language == "ru"

        # Проверка сохранения
        manager2 = ConfigManager(temp_config_file)
        assert manager2.settings.minimize_to_tray is False
        assert manager2.settings.language == "ru"

    def test_add_recent_recording(self, temp_config_file: Path):
        """Проверка добавления недавней записи."""
        manager = ConfigManager(temp_config_file)

        # Добавление записи
        manager.add_recent_recording("/path/to/video.mp4", 1024000)

        assert len(manager.settings.recent_recordings) == 1
        assert (
            manager.settings.recent_recordings[0]["path"]
            == "/path/to/video.mp4"
        )
        assert manager.settings.recent_recordings[0]["size"] == 1024000
        assert "date" in manager.settings.recent_recordings[0]

    def test_add_recent_recording_removes_duplicate(
        self, temp_config_file: Path
    ):
        """Проверка удаления дубликатов при добавлении недавней записи."""
        manager = ConfigManager(temp_config_file)

        # Добавление записи дважды
        manager.add_recent_recording("/path/to/video.mp4", 1024000)
        manager.add_recent_recording("/path/to/video.mp4", 2048000)

        assert len(manager.settings.recent_recordings) == 1
        assert manager.settings.recent_recordings[0]["size"] == 2048000

    def test_max_recent_recordings_limit(self, temp_config_file: Path):
        """Проверка ограничения количества недавних записей."""
        manager = ConfigManager(temp_config_file)
        manager.settings.max_recent_recordings = 5

        # Добавление 10 записей
        for i in range(10):
            manager.add_recent_recording(f"/path/video_{i}.mp4", 1000 * i)

        assert len(manager.settings.recent_recordings) == 5
        # Первая должна быть последняя добавленная
        assert (
            manager.settings.recent_recordings[0]["path"]
            == "/path/video_9.mp4"
        )

    def test_clear_recent_recordings(self, temp_config_file: Path):
        """Проверка очистки списка недавних записей."""
        manager = ConfigManager(temp_config_file)
        manager.add_recent_recording("/path/to/video.mp4", 1024)

        manager.clear_recent_recordings()

        assert manager.settings.recent_recordings == []

    def test_add_recent_recording_thread_safe(self, temp_config_file: Path):
        """Проверка конкурентного добавления recent-записей."""
        manager = ConfigManager(temp_config_file)
        manager.settings.max_recent_recordings = 20

        def worker(start_index: int) -> None:
            for idx in range(start_index, start_index + 10):
                manager.add_recent_recording(f"/tmp/video_{idx}.mp4", idx)

        threads = [
            threading.Thread(target=worker, args=(index * 10,))
            for index in range(4)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        paths = [
            entry["path"] for entry in manager.settings.recent_recordings
        ]
        assert len(paths) <= manager.settings.max_recent_recordings
        assert len(paths) == len(set(paths))

    def test_get_output_path_default(
        self, temp_config_file: Path, temp_dir: Path, monkeypatch
    ):
        """Проверка получения пути вывода по умолчанию."""
        manager = ConfigManager(temp_config_file)
        manager.settings.output.default_path = str(temp_dir / "recordings")

        output_path = manager.get_output_path()

        assert output_path.parent.exists()
        assert output_path.suffix == ".mp4"
        assert "recording_" in output_path.name

    def test_get_output_path_custom_filename(
        self, temp_config_file: Path, temp_dir: Path
    ):
        """Проверка получения пути вывода с пользовательским именем."""
        manager = ConfigManager(temp_config_file)
        manager.settings.output.default_path = str(temp_dir / "recordings")

        output_path = manager.get_output_path("my_video")

        assert output_path.name == "my_video.mp4"

    def test_get_output_path_creates_directory(
        self, temp_config_file: Path, temp_dir: Path
    ):
        """Проверка создания директории вывода."""
        manager = ConfigManager(temp_config_file)
        manager.settings.output.default_path = str(temp_dir / "new_recordings")

        output_path = manager.get_output_path()

        assert output_path.parent.exists()

    def test_reset_config(self, temp_config_file: Path):
        """Проверка сброса конфигурации."""
        manager = ConfigManager(temp_config_file)

        # Изменение настроек
        manager.settings.video.fps = 60
        manager.save()

        # Сброс
        manager.reset()

        assert manager.settings.video.fps == 30  # Значение по умолчанию

        # Проверка сохранения
        manager2 = ConfigManager(temp_config_file)
        assert manager2.settings.video.fps == 30

    def test_settings_property(self, temp_config_file: Path):
        """Проверка свойства settings."""
        manager = ConfigManager(temp_config_file)

        settings = manager.settings

        assert isinstance(settings, AppSettings)
        # Проверка что возвращается тот же объект
        assert settings is manager._settings


class TestGlobalFunctions:
    """Тесты для глобальных функций."""

    def test_init_config(self, temp_config_file: Path, monkeypatch):
        """Проверка функции init_config."""
        # Сброс глобального экземпляра
        monkeypatch.setattr("config._config", None)

        manager = init_config(temp_config_file)

        assert isinstance(manager, ConfigManager)
        assert manager.config_path == temp_config_file

    def test_get_config(self, temp_config_file: Path, monkeypatch):
        """Проверка функции get_config."""
        # Сброс глобального экземпляра
        monkeypatch.setattr("config._config", None)

        # Первый вызов создаёт экземпляр
        manager1 = get_config()

        # Второй вызов возвращает тот же экземпляр
        manager2 = get_config()

        assert manager1 is manager2

    def test_init_config_then_get_config(
        self, temp_config_file: Path, monkeypatch
    ):
        """Проверка что init_config и get_config работают вместе."""
        # Сброс глобального экземпляра
        monkeypatch.setattr("config._config", None)

        # Инициализация с пользовательским путём
        init_manager = init_config(temp_config_file)

        # Получение должно вернуть тот же экземпляр
        get_manager = get_config()

        assert init_manager is get_manager
        assert get_manager.config_path == temp_config_file


class TestConfigManagerInvalidData:
    """Тесты для обработки некорректных данных."""

    def test_load_invalid_json(self, temp_dir: Path):
        """Проверка загрузки некорректного JSON."""
        config_path = temp_dir / "invalid_config.json"
        config_path.write_text("{ invalid json }")

        manager = ConfigManager(config_path)

        # Должны быть загружены значения по умолчанию
        assert isinstance(manager.settings, AppSettings)
        assert manager.settings.video.fps == 30

    def test_load_partial_config(self, temp_dir: Path):
        """Проверка загрузки частичной конфигурации."""
        config_path = temp_dir / "partial_config.json"
        partial_data = {"video": {"fps": 60}, "api": {"port": 9000}}
        config_path.write_text(json.dumps(partial_data))

        manager = ConfigManager(config_path)

        # Указанные значения должны быть загружены
        assert manager.settings.video.fps == 60
        assert manager.settings.api.port == 9000
        # Остальные должны быть по умолчанию
        assert manager.settings.video.codec == "libx264"
        assert manager.settings.audio.sample_rate == 44100

    def test_load_extra_fields(self, temp_dir: Path):
        """Проверка загрузки конфигурации с лишними полями."""
        config_path = temp_dir / "extra_config.json"
        extra_data = {
            "video": {"fps": 30},
            "extra_field": "should be ignored",
            "another_extra": 123,
        }
        config_path.write_text(json.dumps(extra_data))

        # Не должно вызывать ошибку
        manager = ConfigManager(config_path)

        assert isinstance(manager.settings, AppSettings)
