"""
Менеджер жизненного цикла плагинов MIA-ScreenCapture
===================================================

Обеспечивает:
- обнаружение установленных плагинов через entry_points ("mia.plugins");
- загрузку, регистрацию и конфигурацию плагинов;
- управление статусом (включение/отключение);
- сохранение состояния в config/plugins.json;
- генерацию шагов постобработки для конвейера.
"""

from __future__ import annotations

import json
import threading
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any

from core.event_bus import EventBus
from core.plugins.protocol import MIAPlugin, PluginMetadata, PluginStatus
from core.plugins.step import PluginPostProcessingStep
from core.post_processing.steps import PostProcessingStep
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class PluginManager:
    """Централизованный менеджер для управления плагинами постобработки."""

    def __init__(
        self,
        config_path: Path | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._config_path = config_path or Path("config/plugins.json")
        self._event_bus = event_bus
        self._plugins: dict[str, MIAPlugin] = {}
        self._metadata: dict[str, PluginMetadata] = {}
        self._lock = threading.RLock()
        self._load_saved_state()

    @property
    def config_path(self) -> Path:
        """Путь к файлу сохранения состояния плагинов."""
        return self._config_path

    def discover_and_load(self) -> int:
        """
        Обнаруживает плагины через entry points 'mia.plugins' и регистрирует их.

        Returns:
            Количество успешно загруженных плагинов.
        """
        with self._lock:
            count = 0
            try:
                eps = entry_points(group="mia.plugins")
            except Exception as e:
                logger.error(
                    "Ошибка при получении entry_points 'mia.plugins': %s", e
                )
                return 0

            for ep in eps:
                try:
                    plugin_factory = ep.load()
                    plugin_instance = (
                        plugin_factory()
                        if callable(plugin_factory)
                        else plugin_factory
                    )
                    if self.register_plugin(plugin_instance):
                        count += 1
                except Exception as e:
                    logger.error(
                        "Не удалось загрузить плагин из точки входа %s: %s",
                        ep.name,
                        e,
                    )
                    self._metadata[ep.name] = PluginMetadata(
                        name=ep.name,
                        version="unknown",
                        description=f"Ошибка загрузки: {e}",
                        status=PluginStatus.ERROR,
                        error_message=str(e),
                    )
            return count

    def register_plugin(self, plugin: MIAPlugin) -> bool:
        """
        Регистрирует экземпляр плагина в менеджере.

        Args:
            plugin: Объект, реализующий протокол MIAPlugin.

        Returns:
            True при успешной регистрации, иначе False.
        """
        if not hasattr(plugin, "name") or not plugin.name:
            logger.error("Попытка регистрации плагина без имени: %s", plugin)
            return False

        name = plugin.name
        with self._lock:
            self._plugins[name] = plugin

            existing_meta = self._metadata.get(name)
            saved_enabled = (
                existing_meta.status == PluginStatus.ENABLED
                if existing_meta
                else False
            )
            saved_config = existing_meta.config if existing_meta else {}

            schema = {}
            if hasattr(plugin, "get_settings_schema") and callable(
                plugin.get_settings_schema
            ):
                try:
                    schema = plugin.get_settings_schema() or {}
                except Exception as e:
                    logger.warning(
                        "Ошибка получения схемы для плагина %s: %s", name, e
                    )

            try:
                if hasattr(plugin, "initialize") and callable(
                    plugin.initialize
                ):
                    plugin.initialize(saved_config)
                status = (
                    PluginStatus.ENABLED
                    if saved_enabled
                    else PluginStatus.DISABLED
                )
                err_msg = None
            except Exception as e:
                status = PluginStatus.ERROR
                err_msg = str(e)
                logger.error("Ошибка инициализации плагина %s: %s", name, e)

            meta = PluginMetadata(
                name=name,
                version=getattr(plugin, "version", "1.0.0"),
                description=getattr(plugin, "description", ""),
                status=status,
                author=getattr(plugin, "author", ""),
                homepage=getattr(plugin, "homepage", ""),
                config=saved_config,
                settings_schema=schema,
                error_message=err_msg,
            )
            self._metadata[name] = meta
            logger.info(
                "Плагин '%s' v%s зарегистрирован (status=%s)",
                name,
                meta.version,
                status.value,
            )
            return True

    def get_plugin(self, name: str) -> MIAPlugin | None:
        """Возвращает зарегистрированный объект плагина по имени."""
        with self._lock:
            return self._plugins.get(name)

    def get_plugin_metadata(self, name: str) -> PluginMetadata | None:
        """Возвращает метаданные плагина по имени."""
        with self._lock:
            return self._metadata.get(name)

    def get_all_plugins(self) -> list[PluginMetadata]:
        """Возвращает метаданные всех зарегистрированных плагинов."""
        with self._lock:
            return list(self._metadata.values())

    def get_enabled_plugins(self) -> list[MIAPlugin]:
        """Возвращает список всех активных плагинов."""
        with self._lock:
            enabled: list[MIAPlugin] = []
            for name, meta in self._metadata.items():
                if (
                    meta.status == PluginStatus.ENABLED
                    and name in self._plugins
                ):
                    enabled.append(self._plugins[name])
            return enabled

    def enable_plugin(self, name: str) -> bool:
        """Включает плагин."""
        with self._lock:
            meta = self._metadata.get(name)
            plugin = self._plugins.get(name)
            if not meta or not plugin:
                logger.warning("Плагин '%s' не найден для включения", name)
                return False

            try:
                plugin.initialize(meta.config)
                meta.status = PluginStatus.ENABLED
                meta.error_message = None
                self._save_state()
                logger.info("Плагин '%s' успешно включён", name)
                return True
            except Exception as e:
                meta.status = PluginStatus.ERROR
                meta.error_message = str(e)
                self._save_state()
                logger.error("Ошибка при включении плагина '%s': %s", name, e)
                return False

    def disable_plugin(self, name: str) -> bool:
        """Отключает плагин."""
        with self._lock:
            meta = self._metadata.get(name)
            if not meta:
                logger.warning("Плагин '%s' не найден для отключения", name)
                return False
            meta.status = PluginStatus.DISABLED
            self._save_state()
            logger.info("Плагин '%s' отключён", name)
            return True

    def configure_plugin(self, name: str, config: dict[str, Any]) -> bool:
        """Обновляет конфигурацию плагина и повторно его инициализирует."""
        with self._lock:
            meta = self._metadata.get(name)
            plugin = self._plugins.get(name)
            if not meta or not plugin:
                logger.warning("Плагин '%s' не найден для настройки", name)
                return False

            try:
                meta.config = config
                if meta.status == PluginStatus.ENABLED:
                    plugin.initialize(config)
                self._save_state()
                logger.info("Конфигурация плагина '%s' обновлена", name)
                return True
            except Exception as e:
                meta.error_message = str(e)
                self._save_state()
                logger.error("Ошибка при настройке плагина '%s': %s", name, e)
                return False

    def create_post_processing_steps(self) -> list[PostProcessingStep]:
        """Создает шаги постобработки для всех включённых плагинов."""
        with self._lock:
            steps: list[PostProcessingStep] = []
            for plugin in self.get_enabled_plugins():
                steps.append(PluginPostProcessingStep(plugin=plugin))
            return steps

    def _load_saved_state(self) -> None:
        """Загружает сохранённые статусы и конфигурации плагинов из JSON."""
        if not self._config_path.exists():
            return
        try:
            with open(self._config_path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for name, item in data.items():
                    if isinstance(item, dict):
                        is_enabled = item.get("enabled", False)
                        self._metadata[name] = PluginMetadata(
                            name=name,
                            version=item.get("version", "1.0.0"),
                            description=item.get("description", ""),
                            status=(
                                PluginStatus.ENABLED
                                if is_enabled
                                else PluginStatus.DISABLED
                            ),
                            author=item.get("author", ""),
                            homepage=item.get("homepage", ""),
                            config=item.get("config", {}),
                        )
        except Exception as e:
            logger.warning(
                "Не удалось прочитать состояние плагинов из %s: %s",
                self._config_path,
                e,
            )

    def _save_state(self) -> None:
        """Сохраняет состояние плагинов в JSON файл."""
        try:
            self._config_path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, Any] = {}
            for name, meta in self._metadata.items():
                payload[name] = {
                    "enabled": meta.status == PluginStatus.ENABLED,
                    "version": meta.version,
                    "description": meta.description,
                    "config": meta.config,
                    "author": meta.author,
                    "homepage": meta.homepage,
                }
            with open(self._config_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(
                "Не удалось сохранить состояние плагинов в %s: %s",
                self._config_path,
                e,
            )
