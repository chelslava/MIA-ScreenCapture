"""Единый реестр desktop-действий для GUI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class DesktopActionId(StrEnum):
    """Идентификаторы desktop-действий GUI."""

    START_RECORDING = "start_recording"
    TOGGLE_PAUSE = "toggle_pause"
    STOP_RECORDING = "stop_recording"
    OPEN_LATEST_RECORDING = "open_latest_recording"
    OPEN_RECORDING_FOLDER = "open_recording_folder"
    SHOW_RECORDING_TAB = "show_recording_tab"
    SHOW_SCHEDULER_TAB = "show_scheduler_tab"
    SHOW_DIAGNOSTICS_TAB = "show_diagnostics_tab"
    SHOW_API_TAB = "show_api_tab"
    OPEN_APP_LOGS = "open_app_logs"


@dataclass(frozen=True, slots=True)
class DesktopAction:
    """Описание одного доступного desktop-действия."""

    action_id: DesktopActionId
    title: str
    description: str
    callback: Callable[[], None]
    shortcut: str | None = None
    enabled_when: Callable[[], bool] | None = None

    def is_enabled(self) -> bool:
        """Проверить, доступно ли действие в текущий момент."""
        if self.enabled_when is None:
            return True
        return bool(self.enabled_when())


@dataclass(frozen=True, slots=True)
class DesktopActionSpec:
    """Статическая metadata desktop-действия."""

    title: str
    description: str
    shortcut: str | None = None


DESKTOP_ACTION_SPECS: dict[DesktopActionId, DesktopActionSpec] = {
    DesktopActionId.START_RECORDING: DesktopActionSpec(
        title="Начать запись",
        description="Запускает запись с текущими настройками.",
        shortcut="Ctrl+R",
    ),
    DesktopActionId.TOGGLE_PAUSE: DesktopActionSpec(
        title="Пауза или продолжение",
        description="Приостанавливает или возобновляет запись.",
        shortcut="Ctrl+P",
    ),
    DesktopActionId.STOP_RECORDING: DesktopActionSpec(
        title="Остановить запись",
        description="Останавливает активную запись.",
        shortcut="Ctrl+S",
    ),
    DesktopActionId.OPEN_LATEST_RECORDING: DesktopActionSpec(
        title="Открыть последнюю запись",
        description="Открывает самый свежий файл записи.",
        shortcut="Ctrl+Shift+O",
    ),
    DesktopActionId.OPEN_RECORDING_FOLDER: DesktopActionSpec(
        title="Открыть папку записи",
        description="Открывает папку выбранной записи.",
        shortcut="Ctrl+Alt+O",
    ),
    DesktopActionId.SHOW_RECORDING_TAB: DesktopActionSpec(
        title="Перейти на вкладку записи",
        description="Открывает вкладку записи.",
        shortcut="Alt+1",
    ),
    DesktopActionId.SHOW_SCHEDULER_TAB: DesktopActionSpec(
        title="Перейти на вкладку планировщика",
        description="Открывает вкладку планировщика.",
        shortcut="Alt+2",
    ),
    DesktopActionId.SHOW_DIAGNOSTICS_TAB: DesktopActionSpec(
        title="Перейти на вкладку диагностики",
        description="Открывает вкладку диагностики.",
        shortcut="Alt+3",
    ),
    DesktopActionId.SHOW_API_TAB: DesktopActionSpec(
        title="Перейти на вкладку API",
        description="Открывает вкладку управления API.",
        shortcut="Alt+4",
    ),
    DesktopActionId.OPEN_APP_LOGS: DesktopActionSpec(
        title="Открыть логи приложения",
        description="Открывает папку с логами приложения.",
        shortcut="Ctrl+Alt+L",
    ),
}


def get_desktop_action_spec(action_id: DesktopActionId) -> DesktopActionSpec:
    """
    Получить статическую metadata desktop-действия.

    Args:
        action_id: Идентификатор действия.

    Returns:
        Описание действия.
    """
    return DESKTOP_ACTION_SPECS[action_id]


class DesktopActionRegistry:
    """Реестр desktop-действий с единым dispatch API."""

    def __init__(self) -> None:
        self._actions: dict[DesktopActionId, DesktopAction] = {}

    def register(self, action: DesktopAction) -> None:
        """
        Зарегистрировать desktop-действие.

        Args:
            action: Описание действия.
        """
        self._actions[action.action_id] = action

    def get(self, action_id: DesktopActionId) -> DesktopAction:
        """
        Получить описание действия.

        Args:
            action_id: Идентификатор действия.

        Returns:
            Описание действия.
        """
        return self._actions[action_id]

    def execute(self, action_id: DesktopActionId) -> bool:
        """
        Выполнить зарегистрированное действие.

        Args:
            action_id: Идентификатор действия.

        Returns:
            `True`, если действие найдено и выполнено.
        """
        action = self._actions.get(action_id)
        if action is None or not action.is_enabled():
            return False
        action.callback()
        return True

    def all(self) -> tuple[DesktopAction, ...]:
        """Вернуть все зарегистрированные действия."""
        return tuple(self._actions.values())
