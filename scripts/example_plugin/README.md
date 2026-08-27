# MIA Plugin Example (Watermark & Metadata)

Пример создания внешнего плагина для расширения возможностей постобработки в **MIA-ScreenCapture**.

## Структура плагина

Для регистрации плагина в системе MIA-ScreenCapture достаточно:
1. Реализовать протокол `MIAPlugin` (методы `initialize`, `process`, `get_settings_schema`).
2. Объявить точку входа в `pyproject.toml` в группе `mia.plugins`:
   ```toml
   [project.entry-points."mia.plugins"]
   my_plugin_name = "my_package.module:PluginClass"
   ```
3. Установить пакет в окружение (`pip install -e .` или `uv pip install -e .`).

MIA-ScreenCapture автоматически обнаружит плагин при запуске через `importlib.metadata.entry_points(group="mia.plugins")`.
