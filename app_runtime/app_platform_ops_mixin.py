"""Сервисные операции VideoRecorderApp (#176).

Обновления, плагины, библиотека записей, облако, показ окна."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass
from config import get_config
from logger_config import get_module_logger

logger = get_module_logger(__name__)


from app_runtime.app_shared_state import AppSharedState


class PlatformOpsMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def check_for_updates(self, force: bool = False) -> dict[str, Any]:
        """Проверяет наличие новой версии приложения."""
        res = self._updater.check_for_updates(force=force)
        return res.to_dict()

    def download_update(self, version: str | None = None) -> dict[str, Any]:
        """Скачивает доступное обновление."""
        release = None
        if version and self._updater.latest_release:
            if self._updater.latest_release.version == version:
                release = self._updater.latest_release
        self._updater.download_update_async(release=release)
        return {
            "success": True,
            "message": "Загрузка обновления запущена в фоновом режиме",
            "status": self._updater.get_status(),
        }

    def apply_update(self) -> dict[str, Any]:
        """Применяет скачанное обновление."""
        success = self._updater.apply_update()
        return {
            "success": success,
            "message": (
                "Процесс обновления запущен. Приложение будет обновлено."
                if success
                else "Не удалось запустить процесс обновления"
            ),
        }

    def get_update_status(self) -> dict[str, Any]:
        """Возвращает текущий статус подсистемы обновлений."""
        return self._updater.get_status()

    def get_update_config(self) -> dict[str, Any]:
        """Возвращает настройки авто-обновлений."""
        config = get_config()
        return asdict(config.settings.updates)

    def update_update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет настройки авто-обновлений."""
        from config import UpdateSettingsSchema

        try:
            validated = UpdateSettingsSchema.model_validate(data)
            config = get_config()
            for k, v in validated.model_dump().items():
                setattr(config.settings.updates, k, v)
            saved = config.save()
            return {
                "success": saved,
                "config": asdict(config.settings.updates),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === Управление плагинами (#124) ===

    def get_plugins(self) -> list[dict[str, Any]]:
        """Возвращает список метаданных всех зарегистрированных плагинов."""
        return [p.to_dict() for p in self._plugin_manager.get_all_plugins()]

    def get_plugin_info(self, name: str) -> dict[str, Any] | None:
        """Возвращает метаданные и настройки конкретного плагина."""
        meta = self._plugin_manager.get_plugin_metadata(name)
        return meta.to_dict() if meta else None

    def enable_plugin(self, name: str) -> bool:
        """Включает плагин."""
        return self._plugin_manager.enable_plugin(name)

    def disable_plugin(self, name: str) -> bool:
        """Отключает плагин."""
        return self._plugin_manager.disable_plugin(name)

    def configure_plugin(self, name: str, config: dict[str, Any]) -> bool:
        """Обновляет конфигурацию плагина."""
        return self._plugin_manager.configure_plugin(name, config)

    # === Управление библиотекой записей (#119) ===

    def get_library_items(
        self,
        query: str | None = None,
        tag: str | None = None,
        sort_by: str = "date",
        sort_desc: bool = True,
    ) -> list[dict[str, Any]]:
        """Возвращает список записей библиотеки."""
        items = self._library_manager.get_items(
            query=query, tag=tag, sort_by=sort_by, sort_desc=sort_desc
        )
        return [it.to_dict() for it in items]

    def get_library_tags(self) -> list[str]:
        """Возвращает список всех тегов библиотеки."""
        return self._library_manager.get_all_tags()

    def add_library_tag(self, path: str, tag: str) -> bool:
        """Добавляет тег к записи."""
        return self._library_manager.add_tag(path, tag)

    def remove_library_tag(self, path: str, tag: str) -> bool:
        """Удаляет тег из записи."""
        return self._library_manager.remove_tag(path, tag)

    def delete_library_recording(
        self, path: str, delete_file: bool = True
    ) -> bool:
        """Удаляет запись из библиотеки."""
        return self._library_manager.delete_recording(path, delete_file)

    # === Управление облачной синхронизацией (#54) ===

    def get_cloud_status(self) -> dict[str, Any]:
        """Возвращает статус облачной синхронизации."""
        return self._cloud_sync_manager.get_status()

    def configure_cloud(
        self,
        provider: str,
        credentials: dict[str, Any],
        auto_sync: bool = False,
        min_file_size_mb: float = 0.0,
        remote_folder: str = "Recordings",
    ) -> bool:
        """Настраивает параметры облачной синхронизации."""
        return self._cloud_sync_manager.configure(
            provider_type=provider,
            credentials=credentials,
            auto_sync=auto_sync,
            min_file_size_mb=min_file_size_mb,
            remote_folder=remote_folder,
        )

    def test_cloud_connection(self) -> bool:
        """Проверяет соединение с облачным провайдером."""
        return self._cloud_sync_manager.test_connection()

    def queue_cloud_sync(self, file_path: Path) -> bool:
        """Добавляет файл в очередь облачной загрузки."""
        return self._cloud_sync_manager.queue_upload(file_path)

    # Вспомогательные методы GUI

    def _show_window(self) -> None:
        """Показ главного окна."""
        if self._main_window:
            self._main_window.show()
            self._main_window.activateWindow()
