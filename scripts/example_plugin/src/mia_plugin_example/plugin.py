"""Пример плагина добавления водяного знака / метаданных для MIA-ScreenCapture."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class ExampleWatermarkPlugin:
    """Пример плагина постобработки для демонстрации MIAPlugin Protocol."""

    name: str = "example_watermark"
    version: str = "1.0.0"
    description: str = "Пример плагина постобработки (добавление водяного знака или метаданных)"
    author: str = "MIA Team"
    homepage: str = "https://github.com/chelslava/MIA-ScreenCapture"

    def __init__(self) -> None:
        self.watermark_text: str = "MIA-ScreenCapture"
        self.opacity: float = 0.8

    def initialize(self, config: dict[str, Any]) -> None:
        """Инициализация плагина с пользовательскими настройками."""
        self.watermark_text = config.get("watermark_text", "MIA-ScreenCapture")
        self.opacity = float(config.get("opacity", 0.8))

    def process(self, recording_path: Path) -> Path:
        """
        Обработка видеозаписи.

        В реальном плагине здесь может вызываться FFmpeg для наложения
        водяного знака или утилита записи метаданных.
        """
        # Возвращаем путь к файлу после обработки
        return recording_path

    def get_settings_schema(self) -> dict[str, Any]:
        """Возвращает схему настроек в формате JSON Schema."""
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "Настройки водяного знака",
            "type": "object",
            "properties": {
                "watermark_text": {
                    "type": "string",
                    "title": "Текст водяного знака",
                    "default": "MIA-ScreenCapture",
                },
                "opacity": {
                    "type": "number",
                    "title": "Прозрачность (0.0 - 1.0)",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.8,
                },
            },
            "required": ["watermark_text"],
        }
