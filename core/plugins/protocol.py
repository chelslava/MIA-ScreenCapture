"""
Протоколы и структуры данных для плагин-системы MIA-ScreenCapture
=================================================================

Определяет:
- MIAPlugin: базовый протокол, реализуемый всеми внешними плагинами;
- PluginStatus: перечисление состояний плагина;
- PluginMetadata: метаданные и настройки плагина для GUI/API/CLI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


class PluginStatus(StrEnum):
    """Статусы плагина в системе."""

    LOADED = "loaded"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@runtime_checkable
class MIAPlugin(Protocol):
    """
    Протокол плагина для расширения возможностей постобработки MIA-ScreenCapture.

    Сторонний плагин должен объявлять имя, версию, описание, и реализовывать
    методы инициализации настроек, обработки файла и схемы конфигурации.
    """

    name: str
    version: str
    description: str

    def initialize(self, config: dict[str, Any]) -> None:
        """
        Инициализация плагина со словарём пользовательских настроек.

        Args:
            config: Словарь настроек плагина.
        """
        ...

    def process(self, recording_path: Path) -> Path:
        """
        Обработка файла записи.

        Args:
            recording_path: Путь к входному видеофайлу.

        Returns:
            Путь к результирующему файлу (исходному или созданному новому).
        """
        ...

    def get_settings_schema(self) -> dict[str, Any]:
        """
        Возвращает JSON Schema для валидации и отображения настроек в GUI/API.

        Returns:
            Словарь формата JSON Schema (Draft 7/2020-12).
        """
        ...


@dataclass
class PluginMetadata:
    """Метаданные и текущее состояние плагина."""

    name: str
    version: str
    description: str
    status: PluginStatus = PluginStatus.DISABLED
    author: str = ""
    homepage: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    settings_schema: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Сериализация метаданных плагина в словарь."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "status": self.status.value,
            "author": self.author,
            "homepage": self.homepage,
            "config": self.config,
            "settings_schema": self.settings_schema,
            "error_message": self.error_message,
        }
