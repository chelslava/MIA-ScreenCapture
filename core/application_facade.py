"""
Явный публичный фасад приложения для GUI/runtime/API интеграций.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ApplicationFacade(Protocol):
    """Контракт публичных команд и запросов приложения."""

    def request_start_recording(self) -> dict[str, Any]:
        """Запускает запись с текущими GUI-настройками."""
        ...

    def request_stop_recording(self) -> dict[str, Any]:
        """Запрашивает остановку записи из интерактивного UI."""
        ...

    def request_toggle_pause_recording(self) -> dict[str, Any]:
        """Переключает паузу записи из интерактивного UI."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус записи."""
        ...

    def get_recording_metrics(self) -> dict[str, Any]:
        """Возвращает текущие метрики кадров записи (#114)."""
        ...

    def start_recording(
        self, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Запускает запись с явными параметрами."""
        ...

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись."""
        ...

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу."""
        ...

    def get_recordings(self) -> list[Any]:
        """Возвращает список последних записей."""
        ...

    def get_schedule(self) -> list[Any]:
        """Возвращает список задач планировщика."""
        ...

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создаёт задачу планировщика."""
        ...

    def delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаляет задачу планировщика."""
        ...

    def update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет задачу планировщика."""
        ...

    def toggle_schedule(self, task_id: str, enabled: bool) -> dict[str, Any]:
        """Переключает состояние задачи планировщика."""
        ...

    def get_devices(self) -> dict[str, list[Any]]:
        """Возвращает аудиоустройства."""
        ...

    def get_windows(self) -> list[Any]:
        """Возвращает список окон."""
        ...

    def get_monitors(self) -> list[Any]:
        """Возвращает список доступных мониторов (#48)."""
        ...

    def get_disk_space(self) -> dict[str, Any]:
        """Возвращает статус свободного места на диске для пути записи."""
        ...

    def get_webhook_config(self) -> dict[str, Any]:
        """Возвращает настройки webhook (без значения секрета)."""
        ...

    def configure_webhook(
        self, url: str | None, secret: str | None, enabled: bool
    ) -> dict[str, Any]:
        """Настраивает webhook-уведомления."""
        ...

    def test_webhook(self) -> dict[str, Any]:
        """Отправляет тестовое webhook-уведомление."""
        ...

    def verify_recording(self, file_path: str) -> dict[str, Any]:
        """Проверяет целостность видеофайла по указанному пути."""
        ...

    def repair_recording(self, file_path: str) -> dict[str, Any]:
        """Пытается восстановить видеофайл по указанному пути."""
        ...

    def switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """Переключает источник захвата активной записи без остановки."""
        ...

    def start_multi_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Запускает запись с нескольких источников одновременно."""
        ...

    def stop_multi_recording(self) -> dict[str, Any]:
        """Останавливает мультиисточниковую запись."""
        ...

    def get_multi_recording_status(self) -> dict[str, Any]:
        """Возвращает статус мультиисточниковой записи."""
        ...

    def get_config_snapshot(self) -> dict[str, Any]:
        """Возвращает snapshot конфигурации."""
        ...

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет конфигурацию."""
        ...

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API."""
        ...

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API."""
        ...

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер."""
        ...

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер."""
        ...

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер."""
        ...

    def open_api_logs_folder(self) -> None:
        """Открывает каталог логов API."""
        ...

    def get_profiles(self) -> list[dict[str, Any]]:
        """Возвращает список всех профилей записи."""
        ...

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Возвращает профиль записи по идентификатору."""
        ...

    def create_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создает новый профиль записи."""
        ...

    def update_profile(
        self, profile_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Обновляет существующий профиль записи."""
        ...

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        """Удаляет профиль записи."""
        ...

    def apply_profile(self, profile_id: str) -> dict[str, Any]:
        """Применяет профиль записи к активной конфигурации."""
        ...

    def export_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Экспортирует профиль записи."""
        ...

    def import_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Импортирует профиль записи."""
        ...

    def get_post_processing_config(self) -> dict[str, Any]:
        """Возвращает настройки постобработки записей."""
        ...

    def update_post_processing_config(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Обновляет настройки постобработки записей."""
        ...

    def get_post_processing_status(self) -> dict[str, Any]:
        """Возвращает статус конвейера постобработки."""
        ...

    def run_post_processing(
        self, file_path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Запускает постобработку для указанного файла."""
        ...

    def check_for_updates(self, force: bool = False) -> dict[str, Any]:
        """Проверяет наличие новой версии приложения."""
        ...

    def download_update(self, version: str | None = None) -> dict[str, Any]:
        """Скачивает доступное обновление."""
        ...

    def apply_update(self) -> dict[str, Any]:
        """Применяет скачанное обновление."""
        ...

    def get_update_status(self) -> dict[str, Any]:
        """Возвращает текущий статус подсистемы обновлений."""
        ...

    def get_update_config(self) -> dict[str, Any]:
        """Возвращает настройки авто-обновлений."""
        ...

    def update_update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет настройки авто-обновлений."""
        ...

    def get_plugins(self) -> list[dict[str, Any]]:
        """Возвращает список метаданных всех зарегистрированных плагинов."""
        ...

    def get_plugin_info(self, name: str) -> dict[str, Any] | None:
        """Возвращает метаданные и настройки конкретного плагина."""
        ...

    def enable_plugin(self, name: str) -> bool:
        """Включает плагин."""
        ...

    def disable_plugin(self, name: str) -> bool:
        """Отключает плагин."""
        ...

    def configure_plugin(self, name: str, config: dict[str, Any]) -> bool:
        """Обновляет конфигурацию плагина."""
        ...

    def get_library_items(
        self,
        query: str | None = None,
        tag: str | None = None,
        sort_by: str = "date",
        sort_desc: bool = True,
    ) -> list[dict[str, Any]]:
        """Возвращает список записей в библиотеке."""
        ...

    def get_library_tags(self) -> list[str]:
        """Возвращает список всех тегов библиотеки."""
        ...

    def add_library_tag(self, path: str, tag: str) -> bool:
        """Добавляет тег к записи в библиотеке."""
        ...

    def remove_library_tag(self, path: str, tag: str) -> bool:
        """Удаляет тег из записи в библиотеке."""
        ...

    def delete_library_recording(
        self, path: str, delete_file: bool = True
    ) -> bool:
        """Удаляет запись из библиотеки и опционально файл с диска."""
        ...

    def get_cloud_status(self) -> dict[str, Any]:
        """Возвращает статус облачной синхронизации."""
        ...

    def configure_cloud(
        self,
        provider: str,
        credentials: dict[str, Any],
        auto_sync: bool = False,
        min_file_size_mb: float = 0.0,
        remote_folder: str = "Recordings",
    ) -> bool:
        """Настраивает параметры облачной синхронизации."""
        ...

    def test_cloud_connection(self) -> bool:
        """Проверяет соединение с облачным провайдером."""
        ...

    def queue_cloud_sync(self, file_path: Path) -> bool:
        """Добавляет файл в очередь облачной загрузки."""
        ...
