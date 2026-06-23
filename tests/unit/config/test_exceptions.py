"""
Тесты для модуля исключений
===========================

Проверяет иерархию и функциональность кастомных исключений.
"""

import pytest

from exceptions import (
    APIAuthenticationError,
    APIAuthorizationError,
    APIError,
    APINotFoundError,
    APIRateLimitError,
    APIValidationError,
    AudioCaptureError,
    AudioDeviceError,
    AudioDeviceNotFoundError,
    AudioError,
    CaptureAreaError,
    CaptureAreaInvalidError,
    CaptureAreaNotFoundError,
    CaptureError,
    ConfigFileError,
    ConfigurationError,
    ConfigValidationError,
    DiskSpaceError,
    EncoderError,
    EncoderNotAvailableError,
    EncoderProcessError,
    EncoderTimeoutError,
    FileSystemError,
    FileWriteError,
    MIAError,
    OutputPathError,
    RecordingError,
    RecordingNotActiveError,
    RecordingStateError,
    SchedulerError,
    ScreenCaptureError,
    TaskNotFoundError,
    TaskScheduleError,
    TaskValidationError,
    WindowNotFoundError,
)


class TestMIAError:
    """Тесты базового исключения MIAError."""

    def test_basic_error(self):
        """Проверка создания базового исключения."""
        error = MIAError("Тестовая ошибка")

        assert error.message == "Тестовая ошибка"
        assert error.details is None
        assert str(error) == "Тестовая ошибка"

    def test_error_with_details(self):
        """Проверка исключения с деталями."""
        error = MIAError("Тестовая ошибка", "Дополнительная информация")

        assert error.message == "Тестовая ошибка"
        assert error.details == "Дополнительная информация"
        assert str(error) == "Тестовая ошибка (Дополнительная информация)"

    def test_inheritance(self):
        """Проверка наследования от Exception."""
        error = MIAError("Ошибка")

        assert isinstance(error, Exception)

    def test_raise_and_catch(self):
        """Проверка выброса и перехвата исключения."""
        with pytest.raises(MIAError) as exc_info:
            raise MIAError("Тест")

        assert str(exc_info.value) == "Тест"


class TestConfigurationErrors:
    """Тесты ошибок конфигурации."""

    def test_configuration_error(self):
        """Проверка ConfigurationError."""
        error = ConfigurationError("Ошибка конфигурации")

        assert isinstance(error, MIAError)
        assert error.message == "Ошибка конфигурации"

    def test_config_file_error(self):
        """Проверка ConfigFileError."""
        error = ConfigFileError("Файл не найден", "/path/to/config.json")

        assert isinstance(error, ConfigurationError)
        assert isinstance(error, MIAError)
        assert error.details == "/path/to/config.json"

    def test_config_validation_error(self):
        """Проверка ConfigValidationError."""
        error = ConfigValidationError("Неверный формат", "fps должен быть > 0")

        assert isinstance(error, ConfigurationError)
        assert "fps" in error.details


class TestRecordingErrors:
    """Тесты ошибок записи."""

    def test_recording_error(self):
        """Проверка RecordingError."""
        error = RecordingError("Ошибка записи")

        assert isinstance(error, MIAError)
        assert error.message == "Ошибка записи"

    def test_recording_state_error(self):
        """Проверка RecordingStateError."""
        error = RecordingStateError("Запись уже запущена")

        assert isinstance(error, RecordingError)
        assert isinstance(error, MIAError)

    def test_recording_not_active_error(self):
        """Проверка RecordingNotActiveError."""
        error = RecordingNotActiveError("Нет активной записи")

        assert isinstance(error, RecordingError)


class TestCaptureErrors:
    """Тесты ошибок захвата."""

    def test_capture_error(self):
        """Проверка CaptureError."""
        error = CaptureError("Ошибка захвата")

        assert isinstance(error, RecordingError)
        assert isinstance(error, MIAError)

    def test_capture_area_error(self):
        """Проверка CaptureAreaError."""
        error = CaptureAreaError("Ошибка области")

        assert isinstance(error, CaptureError)
        assert isinstance(error, RecordingError)

    def test_capture_area_not_found_error(self):
        """Проверка CaptureAreaNotFoundError."""
        error = CaptureAreaNotFoundError("Окно не найдено", "Browser")

        assert isinstance(error, CaptureAreaError)
        assert error.details == "Browser"

    def test_capture_area_invalid_error(self):
        """Проверка CaptureAreaInvalidError."""
        error = CaptureAreaInvalidError("Неверные координаты", "x2 < x1")

        assert isinstance(error, CaptureAreaError)
        assert "x2 < x1" in error.details

    def test_screen_capture_error(self):
        """Проверка ScreenCaptureError."""
        error = ScreenCaptureError("Не удалось захватить экран")

        assert isinstance(error, CaptureError)

    def test_window_not_found_error(self):
        """Проверка WindowNotFoundError."""
        error = WindowNotFoundError("Окно не найдено", "Chrome")

        assert isinstance(error, CaptureError)
        assert error.details == "Chrome"


class TestEncoderErrors:
    """Тесты ошибок кодирования."""

    def test_encoder_error(self):
        """Проверка EncoderError."""
        error = EncoderError("Ошибка кодирования")

        assert isinstance(error, RecordingError)
        assert isinstance(error, MIAError)

    def test_encoder_not_available_error(self):
        """Проверка EncoderNotAvailableError."""
        error = EncoderNotAvailableError("FFmpeg не найден")

        assert isinstance(error, EncoderError)

    def test_encoder_process_error(self):
        """Проверка EncoderProcessError."""
        error = EncoderProcessError("Процесс упал", "exit code: 1")

        assert isinstance(error, EncoderError)
        assert error.details == "exit code: 1"

    def test_encoder_timeout_error(self):
        """Проверка EncoderTimeoutError."""
        error = EncoderTimeoutError("Таймаут кодирования", "30 секунд")

        assert isinstance(error, EncoderError)


class TestAudioErrors:
    """Тесты ошибок аудио."""

    def test_audio_error(self):
        """Проверка AudioError."""
        error = AudioError("Ошибка аудио")

        assert isinstance(error, RecordingError)
        assert isinstance(error, MIAError)

    def test_audio_device_error(self):
        """Проверка AudioDeviceError."""
        error = AudioDeviceError("Ошибка устройства")

        assert isinstance(error, AudioError)

    def test_audio_device_not_found_error(self):
        """Проверка AudioDeviceNotFoundError."""
        error = AudioDeviceNotFoundError("Микрофон не найден", "device_id: 5")

        assert isinstance(error, AudioDeviceError)
        assert error.details == "device_id: 5"

    def test_audio_capture_error(self):
        """Проверка AudioCaptureError."""
        error = AudioCaptureError("Ошибка захвата аудио")

        assert isinstance(error, AudioError)


class TestAPIErrors:
    """Тесты ошибок API."""

    def test_api_error(self):
        """Проверка APIError."""
        error = APIError("Ошибка API", 500)

        assert isinstance(error, MIAError)
        assert error.status_code == 500

    def test_api_error_default_status(self):
        """Проверка APIError с кодом по умолчанию."""
        error = APIError("Ошибка")

        assert error.status_code == 500

    def test_api_authentication_error(self):
        """Проверка APIAuthenticationError."""
        error = APIAuthenticationError()

        assert isinstance(error, APIError)
        assert error.status_code == 401
        assert "аутентификация" in error.message.lower()

    def test_api_authentication_error_custom_message(self):
        """Проверка APIAuthenticationError с кастомным сообщением."""
        error = APIAuthenticationError("Неверный API ключ")

        assert error.message == "Неверный API ключ"
        assert error.status_code == 401

    def test_api_authorization_error(self):
        """Проверка APIAuthorizationError."""
        error = APIAuthorizationError()

        assert isinstance(error, APIError)
        assert error.status_code == 403

    def test_api_validation_error(self):
        """Проверка APIValidationError."""
        error = APIValidationError("Неверный формат", "fps: expected int")

        assert isinstance(error, APIError)
        assert error.status_code == 400
        assert error.details == "fps: expected int"

    def test_api_not_found_error(self):
        """Проверка APINotFoundError."""
        error = APINotFoundError("Задача не найдена", "task_id: 123")

        assert isinstance(error, APIError)
        assert error.status_code == 404

    def test_api_rate_limit_error(self):
        """Проверка APIRateLimitError."""
        error = APIRateLimitError()

        assert isinstance(error, APIError)
        assert error.status_code == 429


class TestSchedulerErrors:
    """Тесты ошибок планировщика."""

    def test_scheduler_error(self):
        """Проверка SchedulerError."""
        error = SchedulerError("Ошибка планировщика")

        assert isinstance(error, MIAError)

    def test_task_not_found_error(self):
        """Проверка TaskNotFoundError."""
        error = TaskNotFoundError("Задача не найдена", "task_123")

        assert isinstance(error, SchedulerError)
        assert error.details == "task_123"

    def test_task_validation_error(self):
        """Проверка TaskValidationError."""
        error = TaskValidationError("Неверные параметры задачи")

        assert isinstance(error, SchedulerError)

    def test_task_schedule_error(self):
        """Проверка TaskScheduleError."""
        error = TaskScheduleError("Не удалось запланировать задачу")

        assert isinstance(error, SchedulerError)


class TestFileSystemErrors:
    """Тесты ошибок файловой системы."""

    def test_file_system_error(self):
        """Проверка FileSystemError."""
        error = FileSystemError("Ошибка файловой системы")

        assert isinstance(error, MIAError)

    def test_output_path_error(self):
        """Проверка OutputPathError."""
        error = OutputPathError("Неверный путь", "/invalid/path")

        assert isinstance(error, FileSystemError)
        assert error.details == "/invalid/path"

    def test_disk_space_error(self):
        """Проверка DiskSpaceError."""
        error = DiskSpaceError("Недостаточно места", "100MB required")

        assert isinstance(error, FileSystemError)
        assert error.details == "100MB required"

    def test_file_write_error(self):
        """Проверка FileWriteError."""
        error = FileWriteError("Ошибка записи файла")

        assert isinstance(error, FileSystemError)


class TestExceptionHierarchy:
    """Тесты иерархии исключений."""

    def test_can_catch_base_exception(self):
        """Проверка перехвата по базовому классу."""
        with pytest.raises(MIAError):
            raise RecordingError("Ошибка записи")

    def test_can_catch_recording_exception(self):
        """Проверка перехвата по промежуточному классу."""
        with pytest.raises(RecordingError):
            raise EncoderError("Ошибка кодировщика")

    def test_can_catch_capture_exception(self):
        """Проверка перехвата CaptureError."""
        with pytest.raises(CaptureError):
            raise WindowNotFoundError("Окно не найдено")

    def test_can_catch_api_exception(self):
        """Проверка перехвата APIError."""
        with pytest.raises(APIError) as exc_info:
            raise APIAuthenticationError("Не авторизован")

        assert exc_info.value.status_code == 401

    def test_specific_catch(self):
        """Проверка специфичного перехвата."""
        try:
            raise EncoderNotAvailableError("FFmpeg не найден")
        except EncoderNotAvailableError as e:
            assert e.message == "FFmpeg не найден"
        except EncoderError:
            pytest.fail("Должен быть перехвачен EncoderNotAvailableError")
        except MIAError:
            pytest.fail("Должен быть перехвачен EncoderNotAvailableError")
