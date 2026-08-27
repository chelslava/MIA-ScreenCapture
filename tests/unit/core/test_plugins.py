"""
Unit-тесты для плагин-системы MIA-ScreenCapture (Issue #124).
============================================================
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import PostProcessingSettings
from core.plugins.manager import PluginManager
from core.plugins.protocol import (
    MIAPlugin,
    PluginStatus,
)
from core.plugins.step import PluginPostProcessingStep
from core.post_processing.manager import PostProcessingManager
from core.post_processing.types import (
    PostProcessingStepType,
)


class DummyPlugin:
    """Тестовый плагин, реализующий MIAPlugin."""

    name = "dummy_plugin"
    version = "1.2.0"
    description = "Тестовый плагин для unit-тестов"
    author = "Tester"
    homepage = "https://example.com"

    def __init__(self) -> None:
        self.init_called = False
        self.last_config: dict[str, Any] = {}

    def initialize(self, config: dict[str, Any]) -> None:
        self.init_called = True
        self.last_config = config

    def process(self, recording_path: Path) -> Path:
        return recording_path

    def get_settings_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tag": {"type": "string"},
            },
        }


class FaultyPlugin:
    """Плагин, выбрасывающий ошибки."""

    name = "faulty_plugin"
    version = "0.1.0"
    description = "Сбойный плагин"

    def initialize(self, config: dict[str, Any]) -> None:
        raise ValueError("Ошибка инициализации")

    def process(self, recording_path: Path) -> Path:
        raise RuntimeError("Ошибка обработки")

    def get_settings_schema(self) -> dict[str, Any]:
        return {}


def test_protocol_runtime_checkable() -> None:
    """DummyPlugin должен соответствовать протоколу MIAPlugin."""
    plugin = DummyPlugin()
    assert isinstance(plugin, MIAPlugin)


def test_plugin_manager_register_and_get(tmp_path: Path) -> None:
    """Регистрация и получение плагина через PluginManager."""
    cfg_file = tmp_path / "plugins.json"
    manager = PluginManager(config_path=cfg_file)

    plugin = DummyPlugin()
    assert manager.register_plugin(plugin) is True

    retrieved = manager.get_plugin("dummy_plugin")
    assert retrieved is plugin

    meta = manager.get_plugin_metadata("dummy_plugin")
    assert meta is not None
    assert meta.name == "dummy_plugin"
    assert meta.version == "1.2.0"
    assert meta.status == PluginStatus.DISABLED
    assert meta.author == "Tester"
    assert meta.settings_schema.get("properties", {}).get("tag") is not None


def test_plugin_manager_enable_and_disable(tmp_path: Path) -> None:
    """Включение и отключение плагина с сохранением состояния."""
    cfg_file = tmp_path / "plugins.json"
    manager = PluginManager(config_path=cfg_file)
    plugin = DummyPlugin()
    manager.register_plugin(plugin)

    assert manager.enable_plugin("dummy_plugin") is True
    assert plugin.init_called is True
    meta = manager.get_plugin_metadata("dummy_plugin")
    assert meta is not None and meta.status == PluginStatus.ENABLED
    assert manager.get_enabled_plugins() == [plugin]

    assert cfg_file.exists()
    with open(cfg_file, encoding="utf-8") as f:
        saved = json.load(f)
    assert saved["dummy_plugin"]["enabled"] is True

    # Отключение
    assert manager.disable_plugin("dummy_plugin") is True
    meta = manager.get_plugin_metadata("dummy_plugin")
    assert meta is not None and meta.status == PluginStatus.DISABLED
    assert manager.get_enabled_plugins() == []


def test_plugin_manager_configure(tmp_path: Path) -> None:
    """Конфигурация плагина обновляет настройки и повторно инициализирует его при активности."""
    cfg_file = tmp_path / "plugins.json"
    manager = PluginManager(config_path=cfg_file)
    plugin = DummyPlugin()
    manager.register_plugin(plugin)
    manager.enable_plugin("dummy_plugin")

    assert manager.configure_plugin("dummy_plugin", {"tag": "val123"}) is True
    assert plugin.last_config == {"tag": "val123"}
    meta = manager.get_plugin_metadata("dummy_plugin")
    assert meta is not None
    assert meta.config == {"tag": "val123"}


def test_plugin_manager_faulty_plugin(tmp_path: Path) -> None:
    """Регистрация плагина с ошибкой инициализации переводит статус в ERROR."""
    cfg_file = tmp_path / "plugins.json"
    manager = PluginManager(config_path=cfg_file)
    plugin = FaultyPlugin()
    assert manager.register_plugin(plugin) is True

    meta = manager.get_plugin_metadata("faulty_plugin")
    assert meta is not None
    assert meta.status == PluginStatus.ERROR
    assert "Ошибка инициализации" in (meta.error_message or "")


def test_plugin_post_processing_step_execute_success(tmp_path: Path) -> None:
    """Выполнение шага плагина при успешной обработке."""
    test_file = tmp_path / "video.mp4"
    test_file.write_text("fake video content", encoding="utf-8")

    plugin = DummyPlugin()
    step = PluginPostProcessingStep(plugin=plugin)
    assert step.step_type == PostProcessingStepType.PLUGIN

    result = step.execute(test_file)
    assert result.success is True
    assert result.output_path == test_file
    assert result.details.get("plugin_name") == "dummy_plugin"


def test_plugin_post_processing_step_file_not_found(tmp_path: Path) -> None:
    """Выполнение шага плагина для несуществующего файла возвращает ошибку."""
    non_existent = tmp_path / "does_not_exist.mp4"
    plugin = DummyPlugin()
    step = PluginPostProcessingStep(plugin=plugin)

    result = step.execute(non_existent)
    assert result.success is False
    assert "не существует" in (result.error_message or "")


def test_plugin_post_processing_step_exception_handling(
    tmp_path: Path,
) -> None:
    """Исключение внутри плагина корректно перехватывается шагом."""
    test_file = tmp_path / "video.mp4"
    test_file.write_text("fake content", encoding="utf-8")

    plugin = FaultyPlugin()
    step = PluginPostProcessingStep(plugin=plugin)

    result = step.execute(test_file)
    assert result.success is False
    assert "Ошибка обработки" in (result.error_message or "")


def test_post_processing_manager_includes_plugin_steps(tmp_path: Path) -> None:
    """PostProcessingManager добавляет шаги активных плагинов в build_steps_from_settings."""
    cfg_file = tmp_path / "plugins.json"
    plugin_mgr = PluginManager(config_path=cfg_file)
    plugin = DummyPlugin()
    plugin_mgr.register_plugin(plugin)
    plugin_mgr.enable_plugin("dummy_plugin")

    ppm = PostProcessingManager(plugin_manager=plugin_mgr)
    settings = PostProcessingSettings(enabled=True)

    steps = ppm.build_steps_from_settings(settings)
    plugin_steps = [
        s for s in steps if isinstance(s, PluginPostProcessingStep)
    ]
    assert len(plugin_steps) == 1
    assert plugin_steps[0].plugin.name == "dummy_plugin"
