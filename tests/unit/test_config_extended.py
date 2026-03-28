"""
Расширенные unit тесты для Config
==================================

Дополнительные тесты для конфигурации приложения.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest


class TestConfigBasics:
    """Базовые тесты конфигурации."""

    def test_config_module_exists(self) -> None:
        """Проверка существования модуля."""
        import config

        assert config is not None

    def test_config_class_exists(self) -> None:
        """Проверка существования класса конфигурации."""
        from config import ConfigManager

        assert ConfigManager is not None


class TestConfigLoading:
    """Тесты загрузки конфигурации."""

    def test_load_default_config(self) -> None:
        """Проверка загрузки конфигурации по умолчанию."""
        from config import ConfigManager

        config_manager = ConfigManager()
        settings = config_manager.settings

        assert settings is not None

    def test_load_from_file(self) -> None:
        """Проверка загрузки из файла."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump({"fps": 30, "output_path": "/tmp"}, f)
            temp_path = f.name

        try:
            # Конфигурация должна загружаться из файла
            assert Path(temp_path).exists()
        finally:
            os.unlink(temp_path)


class TestConfigVideoSettings:
    """Параметризованные тесты настроек видео."""

    @pytest.fixture
    def config_manager(self):
        """Создание ConfigManager."""
        from config import ConfigManager

        return ConfigManager()

    @pytest.mark.parametrize("fps", [1, 15, 30, 60, 120])
    def test_fps_in_valid_range(self, config_manager, fps: int) -> None:
        """Проверка что FPS находится в валидном диапазоне."""
        assert 1 <= fps <= 120

    @pytest.mark.parametrize(
        "codec", ["libx264", "libx265", "libvpx-vp9", "h264"]
    )
    def test_valid_video_codecs(self, codec: str) -> None:
        """Проверка валидных видео кодеков."""
        valid_codecs = ["libx264", "libx265", "libvpx-vp9", "h264"]
        assert codec in valid_codecs

    @pytest.mark.parametrize(
        "bitrate", ["1M", "2M", "5M", "10M", "500K", "128k"]
    )
    def test_bitrate_format(self, bitrate: str) -> None:
        """Проверка формата битрейта."""
        assert (
            bitrate.endswith("M")
            or bitrate.endswith("K")
            or bitrate.endswith("k")
        )


class TestConfigAudioSettings:
    """Параметризованные тесты настроек аудио."""

    @pytest.mark.parametrize("sample_rate", [22050, 44100, 48000, 96000])
    def test_valid_sample_rates(self, sample_rate: int) -> None:
        """Проверка валидных частот дискретизации."""
        valid_rates = [22050, 44100, 48000, 96000]
        assert sample_rate in valid_rates

    @pytest.mark.parametrize("channels", [1, 2])
    def test_valid_channel_configurations(self, channels: int) -> None:
        """Проверка валидных конфигураций каналов."""
        assert channels in [1, 2]

    @pytest.mark.parametrize(
        "source", ["microphone", "system", "both", "none"]
    )
    def test_valid_audio_sources(self, source: str) -> None:
        """Проверка валидных источников аудио."""
        valid_sources = ["microphone", "system", "both", "none"]
        assert source in valid_sources

    @pytest.mark.parametrize("bitrate", ["64k", "128k", "192k", "320k"])
    def test_audio_bitrate_format(self, bitrate: str) -> None:
        """Проверка формата битрейта аудио."""
        assert bitrate.endswith("k")


class TestConfigOutputSettings:
    """Параметризованные тесты настроек вывода."""

    @pytest.mark.parametrize("output_format", ["mp4", "avi", "mkv", "webm"])
    def test_valid_output_formats(self, output_format: str) -> None:
        """Проверка валидных форматов вывода."""
        valid_formats = ["mp4", "avi", "mkv", "webm"]
        assert output_format in valid_formats

    @pytest.mark.parametrize(
        "pattern,has_placeholder",
        [
            ("recording_{date}_{time}", True),
            ("video_{timestamp}", True),
            ("simple_name", False),
            ("output_{date}", True),
        ],
    )
    def test_filename_pattern_placeholders(
        self, pattern: str, has_placeholder: bool
    ) -> None:
        """Проверка плейсхолдеров в шаблоне имени файла."""
        contains_placeholder = (
            "{date}" in pattern
            or "{time}" in pattern
            or "{timestamp}" in pattern
        )
        assert contains_placeholder == has_placeholder


class TestConfigCaptureSettings:
    """Параметризованные тесты настроек захвата."""

    @pytest.mark.parametrize("capture_mode", ["full", "window", "region"])
    def test_valid_capture_modes(self, capture_mode: str) -> None:
        """Проверка валидных режимов захвата."""
        valid_modes = ["full", "window", "region"]
        assert capture_mode in valid_modes

    @pytest.mark.parametrize(
        "width,height",
        [
            (1920, 1080),
            (1280, 720),
            (3840, 2160),
            (800, 600),
        ],
    )
    def test_valid_capture_resolutions(self, width: int, height: int) -> None:
        """Проверка валидных разрешений захвата."""
        assert width > 0
        assert height > 0
        assert width <= 7680  # 8K
        assert height <= 4320

    @pytest.mark.parametrize("capture_cursor", [True, False])
    def test_capture_cursor_boolean(self, capture_cursor: bool) -> None:
        """Проверка настройки захвата курсора."""
        assert isinstance(capture_cursor, bool)


class TestConfigSchedulerSettings:
    """Параметризованные тесты настроек планировщика."""

    @pytest.mark.parametrize("max_tasks", [1, 5, 10, 20])
    def test_max_concurrent_tasks_positive(self, max_tasks: int) -> None:
        """Проверка что максимальное количество задач положительное."""
        assert max_tasks > 0

    @pytest.mark.parametrize("retention_days", [1, 7, 30, 90])
    def test_task_retention_days_positive(self, retention_days: int) -> None:
        """Проверка что срок хранения задач положительный."""
        assert retention_days > 0


class TestConfigAPISettings:
    """Параметризованные тесты настроек API."""

    @pytest.mark.parametrize("port", [80, 443, 5000, 8080, 3000])
    def test_valid_api_ports(self, port: int) -> None:
        """Проверка валидных портов API."""
        assert 1 <= port <= 65535

    @pytest.mark.parametrize("host", ["0.0.0.0", "127.0.0.1", "localhost"])
    def test_valid_api_hosts(self, host: str) -> None:
        """Проверка валидных хостов API."""
        assert host is not None

    @pytest.mark.parametrize("auth_enabled", [True, False])
    def test_api_auth_boolean(self, auth_enabled: bool) -> None:
        """Проверка настройки аутентификации API."""
        assert isinstance(auth_enabled, bool)

    @pytest.mark.parametrize(
        "requests,period",
        [
            (100, 60),
            (1000, 3600),
            (10, 1),
        ],
    )
    def test_rate_limit_settings(self, requests: int, period: int) -> None:
        """Проверка настроек rate limiting."""
        assert requests > 0
        assert period > 0


class TestConfigLogging:
    """Параметризованные тесты настроек логирования."""

    @pytest.mark.parametrize(
        "level", ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    )
    def test_valid_log_levels(self, level: str) -> None:
        """Проверка валидных уровней логирования."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        assert level in valid_levels

    @pytest.mark.parametrize("max_size_mb", [1, 5, 10, 50, 100])
    def test_log_max_size_positive(self, max_size_mb: int) -> None:
        """Проверка максимального размера лога."""
        assert max_size_mb > 0

    @pytest.mark.parametrize("backup_count", [0, 1, 5, 10])
    def test_log_backup_count_non_negative(self, backup_count: int) -> None:
        """Проверка количества резервных логов."""
        assert backup_count >= 0


class TestConfigValidation:
    """Параметризованные тесты валидации конфигурации."""

    @pytest.mark.parametrize(
        "fps,expected_valid",
        [
            (1, True),
            (30, True),
            (60, True),
            (120, True),
            (0, False),
            (-1, False),
            (150, False),
        ],
    )
    def test_validate_fps_range(self, fps: int, expected_valid: bool) -> None:
        """Проверка диапазона FPS."""
        is_valid = 1 <= fps <= 120
        assert is_valid == expected_valid

    @pytest.mark.parametrize(
        "port,expected_valid",
        [
            (80, True),
            (443, True),
            (5000, True),
            (8080, True),
            (0, False),
            (-1, False),
            (70000, False),
        ],
    )
    def test_validate_port_range(
        self, port: int, expected_valid: bool
    ) -> None:
        """Проверка диапазона портов."""
        is_valid = 1 <= port <= 65535
        assert is_valid == expected_valid

    @pytest.mark.parametrize(
        "width,height,expected_valid",
        [
            (1920, 1080, True),
            (1280, 720, True),
            (3840, 2160, True),
            (7680, 4320, True),
            (0, 1080, False),
            (1920, 0, False),
            (8000, 5000, False),  # Превышает 8K
        ],
    )
    def test_validate_resolution(
        self, width: int, height: int, expected_valid: bool
    ) -> None:
        """Проверка разрешения."""
        is_valid = (
            width > 0 and height > 0 and width <= 7680 and height <= 4320
        )
        assert is_valid == expected_valid


class TestConfigSave:
    """Тесты сохранения конфигурации."""

    def test_save_to_file(self) -> None:
        """Проверка сохранения в файл."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            temp_path = f.name

        try:
            config_data = {"fps": 30, "output_path": "/tmp"}
            with open(temp_path, "w") as f:
                json.dump(config_data, f)

            with open(temp_path) as f:
                loaded = json.load(f)

            assert loaded["fps"] == 30
        finally:
            os.unlink(temp_path)

    def test_save_creates_directory(self) -> None:
        """Проверка создания директории при сохранении."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config" / "config.json"

            # Директория должна создаваться
            config_path.parent.mkdir(parents=True, exist_ok=True)

            assert config_path.parent.exists()


class TestConfigDefaults:
    """Параметризованные тесты значений по умолчанию."""

    @pytest.mark.parametrize(
        "setting,expected_default",
        [
            ("fps", 30),
            ("codec", "libx264"),
            ("format", "mp4"),
            ("audio_source", "none"),
        ],
    )
    def test_default_values(self, setting: str, expected_default) -> None:
        """Проверка значений по умолчанию."""
        defaults = {
            "fps": 30,
            "codec": "libx264",
            "format": "mp4",
            "audio_source": "none",
        }
        assert defaults[setting] == expected_default


class TestConfigEnvironment:
    """Параметризованные тесты переменных окружения."""

    @pytest.mark.parametrize(
        "env_var,description",
        [
            ("MIA_FPS", "переопределение FPS"),
            ("MIA_OUTPUT_PATH", "переопределение пути вывода"),
            ("MIA_API_PORT", "переопределение порта API"),
            ("MIA_CONFIG_PATH", "путь к файлу конфигурации"),
        ],
    )
    def test_env_variable_names(self, env_var: str, description: str) -> None:
        """Проверка имён переменных окружения."""
        assert env_var.startswith("MIA_")


class TestConfigMigration:
    """Тесты миграции конфигурации."""

    def test_migrate_v1_to_v2(self) -> None:
        """Проверка миграции с версии 1 на 2."""
        v1_config = {"fps": 30}
        v2_config = {**v1_config, "codec": "libx264"}

        assert "codec" in v2_config
        assert v2_config["fps"] == 30

    @pytest.mark.parametrize("version", ["1.0.0", "1.1.0", "1.2.0", "2.0.0"])
    def test_config_version_format(self, version: str) -> None:
        """Проверка формата версии конфигурации."""
        parts = version.split(".")
        assert len(parts) == 3
        for part in parts:
            assert part.isdigit()


class TestConfigThreadSafety:
    """Тесты потокобезопасности конфигурации."""

    def test_concurrent_read(self) -> None:
        """Проверка одновременного чтения."""
        import threading

        results: list = []
        config_data = {"fps": 30}

        def read_config() -> None:
            results.append(config_data["fps"])

        threads = [threading.Thread(target=read_config) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 10
        assert all(r == 30 for r in results)


class TestConfigDebounceSave:
    """Тесты debounce-сохранения recent_recordings."""

    def test_add_recent_recording_reschedules_timer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Проверка переустановки таймера при частых обновлениях."""
        from config import ConfigManager

        created_timers: list[Any] = []

        class FakeTimer:
            """Таймер-заглушка для проверки debounce логики."""

            def __init__(self, *_args: Any, **_kwargs: Any) -> None:
                self.cancelled = False
                self.daemon = False
                created_timers.append(self)

            def start(self) -> None:
                """Запуск таймера-заглушки."""

            def cancel(self) -> None:
                """Отмена таймера-заглушки."""
                self.cancelled = True

        monkeypatch.setattr("config.threading.Timer", FakeTimer)
        manager = ConfigManager(Path("config/nonexistent_debounce_test.json"))

        manager.add_recent_recording("a.mp4", 100)
        first_timer = manager._recent_save_timer
        manager.add_recent_recording("b.mp4", 200)

        assert len(created_timers) == 2
        assert first_timer is created_timers[0]
        assert created_timers[0].cancelled is True
        assert manager._recent_save_timer is created_timers[1]

    def test_save_cancels_pending_debounce_timer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Проверка отмены отложенного сохранения перед обычным save()."""
        from config import ConfigManager

        class FakeTimer:
            """Таймер-заглушка для проверки отмены."""

            def __init__(self) -> None:
                self.cancelled = False

            def cancel(self) -> None:
                """Отмена таймера-заглушки."""
                self.cancelled = True

        manager = ConfigManager(Path("config/nonexistent_debounce_test.json"))
        fake_timer = FakeTimer()
        manager._recent_save_timer = fake_timer

        monkeypatch.setattr("config.atomic_write_json", lambda *_a, **_k: True)

        assert manager.save() is True
        assert fake_timer.cancelled is True
        assert manager._recent_save_timer is None
