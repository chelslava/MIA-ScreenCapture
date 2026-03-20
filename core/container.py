"""
Модуль Dependency Injection контейнера
======================================

Предоставляет контейнер зависимостей для управления компонентами приложения.
"""

from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

if TYPE_CHECKING:
    from pathlib import Path

    from gui.models.recording_state import (
        AudioSettings,
        CaptureSettings,
        VideoSettings,
    )

T = TypeVar("T")


@runtime_checkable
class IConfigManager(Protocol):
    """Протокол менеджера конфигурации."""

    def get_settings(self) -> Any:
        """Возвращает текущие настройки."""
        ...

    def save(self) -> bool:
        """Сохраняет настройки."""
        ...


@runtime_checkable
class IRecordingState(Protocol):
    """Протокол модели состояния записи."""

    def is_recording(self) -> bool:
        """Проверка, идёт ли запись."""
        ...

    def is_paused(self) -> bool:
        """Проверка, на паузе ли запись."""
        ...


@runtime_checkable
class IRecordingController(Protocol):
    """Протокол контроллера записи."""

    def start_recording(
        self,
        output_path: "Path",
        capture: "CaptureSettings",
        audio: "AudioSettings",
        video: "VideoSettings",
        duration: int | None = None,
    ) -> tuple[bool, Optional[str]]:
        """Запускает запись. Возвращает (успех, сообщение об ошибке)."""
        ...

    def stop_recording(self) -> Optional["Path"]:
        """Останавливает запись. Возвращает путь к файлу или None."""
        ...

    def pause_recording(self) -> bool:
        """Приостанавливает запись."""
        ...

    def resume_recording(self) -> bool:
        """Возобновляет запись."""
        ...


@runtime_checkable
class ISettingsController(Protocol):
    """Протокол контроллера настроек."""

    def load_settings(self) -> None:
        """Загружает настройки."""
        ...

    def save_settings(self) -> None:
        """Сохраняет настройки."""
        ...


@runtime_checkable
class IRecordingManager(Protocol):
    """Протокол менеджера записи."""

    def start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Запускает запись."""
        ...

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись."""
        ...

    def pause_recording(self) -> dict[str, Any]:
        """Приостанавливает запись."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус записи."""
        ...


@runtime_checkable
class ITaskScheduler(Protocol):
    """Протокол планировщика задач."""

    def add_task(self, task: Any) -> str:
        """Добавляет задачу."""
        ...

    def remove_task(self, task_id: str) -> bool:
        """Удаляет задачу."""
        ...

    def get_all_tasks(self) -> list[Any]:
        """Возвращает все задачи."""
        ...


@runtime_checkable
class IAPIServer(Protocol):
    """Протокол API сервера."""

    def start(self) -> None:
        """Запускает сервер."""
        ...

    def stop(self) -> None:
        """Останавливает сервер."""
        ...


class Container:
    """
    Контейнер зависимостей для управления компонентами приложения.

    Поддерживает:
    - Регистрацию экземпляров
    - Регистрацию фабрик
    - Синглтон фабрики
    - Получение по типу

    Example:
        container = Container()
        container.register_instance("config", config_manager)
        container.register_factory("recorder", lambda: RecordingManager())

        config = container.get("config")
        recorder = container.get("recorder")
    """

    def __init__(self) -> None:
        """Инициализация контейнера."""
        self._instances: dict[str, Any] = {}
        self._factories: dict[str, Callable[[], Any]] = {}
        self._singletons: dict[str, Callable[[], Any]] = {}
        self._singleton_cache: dict[str, Any] = {}

    def register_instance(self, name: str, instance: Any) -> None:
        """
        Регистрирует экземпляр объекта.

        Args:
            name: Имя зависимости
            instance: Экземпляр объекта
        """
        self._instances[name] = instance

    def register_factory(
        self, name: str, factory: Callable[[], Any]
    ) -> None:
        """
        Регистрирует фабрику для создания объектов.

        Каждый вызов get() будет создавать новый экземпляр.

        Args:
            name: Имя зависимости
            factory: Функция-фабрика для создания объекта
        """
        self._factories[name] = factory

    def register_singleton(
        self, name: str, factory: Callable[[], Any]
    ) -> None:
        """
        Регистрирует синглтон фабрику.

        При первом вызове get() создаётся экземпляр, который
        возвращается при всех последующих вызовах.

        Args:
            name: Имя зависимости
            factory: Функция-фабрика для создания объекта
        """
        self._singletons[name] = factory

    def get(self, name: str) -> Any:
        """
        Получает зависимость по имени.

        Приоритет поиска:
        1. Зарегистрированные экземпляры
        2. Синглтон фабрики (с кэшированием)
        3. Обычные фабрики

        Args:
            name: Имя зависимости

        Returns:
            Запрошенный объект

        Raises:
            KeyError: Если зависимость не найдена
        """
        # Сначала проверяем экземпляры
        if name in self._instances:
            return self._instances[name]

        # Затем синглтоны
        if name in self._singletons:
            if name not in self._singleton_cache:
                self._singleton_cache[name] = self._singletons[name]()
            return self._singleton_cache[name]

        # Затем фабрики
        if name in self._factories:
            return self._factories[name]()

        raise KeyError(f"Зависимость '{name}' не найдена в контейнере")

    def has(self, name: str) -> bool:
        """
        Проверяет наличие зависимости.

        Args:
            name: Имя зависимости

        Returns:
            True если зависимость зарегистрирована
        """
        return (
            name in self._instances
            or name in self._factories
            or name in self._singletons
        )

    def remove(self, name: str) -> bool:
        """
        Удаляет зависимость из контейнера.

        Args:
            name: Имя зависимости

        Returns:
            True если зависимость была удалена
        """
        removed = False
        if name in self._instances:
            del self._instances[name]
            removed = True
        if name in self._factories:
            del self._factories[name]
            removed = True
        if name in self._singletons:
            del self._singletons[name]
            removed = True
        if name in self._singleton_cache:
            del self._singleton_cache[name]
        return removed

    def clear(self) -> None:
        """Очищает все зарегистрированные зависимости."""
        self._instances.clear()
        self._factories.clear()
        self._singletons.clear()
        self._singleton_cache.clear()

    def get_instance(
        self, name: str, default: Any = None
    ) -> Any:
        """
        Получает зависимость или возвращает default.

        Args:
            name: Имя зависимости
            default: Значение по умолчанию

        Returns:
            Запрошенный объект или default
        """
        try:
            return self.get(name)
        except KeyError:
            return default

    def get_typed(self, name: str, expected_type: type[T]) -> T:
        """
        Получает зависимость с проверкой типа.

        Args:
            name: Имя зависимости
            expected_type: Ожидаемый тип

        Returns:
            Запрошенный объект

        Raises:
            KeyError: Если зависимость не найдена
            TypeError: Если тип не соответствует ожидаемому
        """
        instance = self.get(name)
        if not isinstance(instance, expected_type):
            raise TypeError(
                f"Зависимость '{name}' имеет тип {type(instance).__name__}, "
                f"ожидался {expected_type.__name__}"
            )
        return instance

    def list_dependencies(self) -> list[str]:
        """
        Возвращает список всех зарегистрированных зависимостей.

        Returns:
            Список имён зависимостей
        """
        all_names = set()
        all_names.update(self._instances.keys())
        all_names.update(self._factories.keys())
        all_names.update(self._singletons.keys())
        return sorted(all_names)


# Глобальный контейнер приложения
_container: Container | None = None


def get_container() -> Container:
    """
    Возвращает глобальный контейнер зависимостей.

    Создаёт контейнер при первом вызове.

    Returns:
        Глобальный контейнер
    """
    global _container
    if _container is None:
        _container = Container()
    return _container


def reset_container() -> None:
    """Сбрасывает глобальный контейнер."""
    global _container
    if _container is not None:
        _container.clear()
    _container = None
