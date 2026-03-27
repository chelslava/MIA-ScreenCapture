"""
Модуль исключений MIA-ScreenCapture
====================================

Определяет иерархию кастомных исключений для приложения.
"""



class MIAError(Exception):
    """
    Базовое исключение приложения MIA-ScreenCapture.

    Все кастомные исключения наследуются от этого класса.

    Attributes:
        message: Человекочитаемое описание ошибки
        details: Дополнительные детали ошибки (опционально)
    """

    def __init__(self, message: str, details: str | None = None) -> None:
        self.message = message
        self.details = details
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} ({self.details})"
        return self.message


# ============================================================================
# Ошибки конфигурации
# ============================================================================


class ConfigurationError(MIAError):
    """Ошибка конфигурации приложения."""

    pass


class ConfigFileError(ConfigurationError):
    """Ошибка при работе с файлом конфигурации."""

    pass


class ConfigValidationError(ConfigurationError):
    """Ошибка валидации конфигурации."""

    pass


# ============================================================================
# Ошибки записи
# ============================================================================


class RecordingError(MIAError):
    """Базовая ошибка записи."""

    pass


class RecordingStateError(RecordingError):
    """Ошибка состояния записи (например, попытка запустить уже запущенную запись)."""

    pass


class RecordingNotActiveError(RecordingError):
    """Ошибка при попытке выполнить действие с неактивной записью."""

    pass


# ============================================================================
# Ошибки захвата
# ============================================================================


class CaptureError(RecordingError):
    """Базовая ошибка захвата."""

    pass


class CaptureAreaError(CaptureError):
    """Ошибка области захвата."""

    pass


class CaptureAreaNotFoundError(CaptureAreaError):
    """Область захвата не найдена (например, окно не существует)."""

    pass


class CaptureAreaInvalidError(CaptureAreaError):
    """Некорректные параметры области захвата."""

    pass


class ScreenCaptureError(CaptureError):
    """Ошибка захвата экрана."""

    pass


class WindowNotFoundError(CaptureError):
    """Окно не найдено."""

    pass


# ============================================================================
# Ошибки кодирования
# ============================================================================


class EncoderError(RecordingError):
    """Базовая ошибка кодирования."""

    pass


class EncoderNotAvailableError(EncoderError):
    """Кодировщик недоступен (например, FFmpeg не найден)."""

    pass


class EncoderProcessError(EncoderError):
    """Ошибка процесса кодирования."""

    pass


class EncoderTimeoutError(EncoderError):
    """Таймаут кодирования."""

    pass


# ============================================================================
# Ошибки аудио
# ============================================================================


class AudioError(RecordingError):
    """Базовая ошибка аудио."""

    pass


class AudioDeviceError(AudioError):
    """Ошибка аудиоустройства."""

    pass


class AudioDeviceNotFoundError(AudioDeviceError):
    """Аудиоустройство не найдено."""

    pass


class AudioCaptureError(AudioError):
    """Ошибка захвата аудио."""

    pass


# ============================================================================
# Ошибки API
# ============================================================================


class APIError(MIAError):
    """Базовая ошибка API."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: str | None = None,
    ) -> None:
        self.status_code = status_code
        super().__init__(message, details)


class APIAuthenticationError(APIError):
    """Ошибка аутентификации API."""

    def __init__(
        self,
        message: str = "Требуется аутентификация",
        details: str | None = None,
    ) -> None:
        super().__init__(message, 401, details)


class APIAuthorizationError(APIError):
    """Ошибка авторизации API."""

    def __init__(
        self, message: str = "Доступ запрещён", details: str | None = None
    ) -> None:
        super().__init__(message, 403, details)


class APIValidationError(APIError):
    """Ошибка валидации данных API."""

    def __init__(
        self,
        message: str = "Некорректные данные",
        details: str | None = None,
    ) -> None:
        super().__init__(message, 400, details)


class APINotFoundError(APIError):
    """Ошибка ресурс не найден."""

    def __init__(
        self, message: str = "Ресурс не найден", details: str | None = None
    ) -> None:
        super().__init__(message, 404, details)


class APIRateLimitError(APIError):
    """Ошибка превышения лимита запросов."""

    def __init__(
        self,
        message: str = "Превышен лимит запросов",
        details: str | None = None,
    ) -> None:
        super().__init__(message, 429, details)


# ============================================================================
# Ошибки планировщика
# ============================================================================


class SchedulerError(MIAError):
    """Базовая ошибка планировщика."""

    pass


class TaskNotFoundError(SchedulerError):
    """Задача не найдена."""

    pass


class TaskValidationError(SchedulerError):
    """Ошибка валидации задачи."""

    pass


class TaskScheduleError(SchedulerError):
    """Ошибка планирования задачи."""

    pass


# ============================================================================
# Ошибки файловой системы
# ============================================================================


class FileSystemError(MIAError):
    """Базовая ошибка файловой системы."""

    pass


class OutputPathError(FileSystemError):
    """Ошибка выходного пути."""

    pass


class DiskSpaceError(FileSystemError):
    """Недостаточно места на диске."""

    pass


class FileWriteError(FileSystemError):
    """Ошибка записи файла."""

    pass
