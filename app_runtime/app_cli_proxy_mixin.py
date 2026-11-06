"""CLI-прокси операции VideoRecorderApp (#176).

Режимы --start/--stop/--status, планировщик/пресеты/плагины/сервис
проксируются в работающий экземпляр через REST API; при
недоступности API выполняется локальный fallback-старт."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass
from cli.exit_codes import (
    EXIT_RUNTIME_ERROR,
    EXIT_STATE_CONFLICT,
    EXIT_USAGE,
)
from cli.parser import (
    print_json,
    print_schedule_list,
    print_status,
    validate_recording_params,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


from app_runtime.app_shared_state import AppSharedState


class CliProxyMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def _use_json_output(self) -> bool:
        """Включён ли machine-readable JSON-вывод (--json, #206)."""
        return bool(self._config.get("json_output"))

    def _exit_code_for_http(self, status_code: int) -> int:
        """Маппинг HTTP-статуса API в контракт exit-кодов (#206).

        Args:
            status_code: HTTP-статус ответа API.

        Returns:
            2 для 409 (конфликт состояния), 1 для 400/401/404
            (использование), 3 для остальных (исполнение).
        """
        if status_code == 409:
            return EXIT_STATE_CONFLICT
        if status_code in (400, 401, 404, 422):
            return EXIT_USAGE
        return EXIT_RUNTIME_ERROR

    def _get_api_headers(self) -> dict:
        from api.auth import API_KEY_HEADER  # лениво: flask-цепочка (#184)

        """
        Получение заголовков для API запросов с аутентификацией.

        Returns:
            Словарь с заголовками, включая API ключ если он установлен.
        """
        api_key = self._get_effective_api_key()
        if api_key:
            return {API_KEY_HEADER: api_key}
        return {}

    def _sync_api_key_env(self, api_key: str | None) -> None:
        """Синхронизирует API ключ через менеджер runtime."""
        self._api_runtime_coordinator.sync_api_key_env(api_key)

    def _get_effective_api_key(self) -> str | None:
        """Возвращает актуальный API ключ через менеджер runtime."""
        return self._api_runtime_coordinator.get_effective_api_key()

    def _handle_unauthorized_response(self) -> int:
        """
        Обработка ответа 401 Unauthorized.

        Returns:
            Код выхода (1) с выводом сообщения об ошибке.
        """
        print(
            "Ошибка: Требуется аутентификация. Установите переменную окружения "
            "MIA_API_KEY с API ключом.",
            file=sys.stderr,
        )
        return 1

    def _run_start(self) -> int:
        """Запуск записи через CLI."""
        params = self._config.get("recording", {})

        # Валидация параметров
        is_valid, error = validate_recording_params(params)
        if not is_valid:
            print(f"Ошибка: {error}", file=sys.stderr)
            return EXIT_USAGE

        # Попытка подключения к запущенному экземпляру через API
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            # Проверка запущен ли API
            try:
                response = requests.get(f"{api_url}/health", timeout=2)
                if response.status_code == 200:
                    # Отправка команды запуска через API
                    headers = self._get_api_headers()
                    response = requests.post(
                        f"{api_url}/api/start",
                        json={
                            "area": params["area_type"],
                            "rect": params["rect_coords"],
                            "window_title": params["window_title"],
                            "audio": params["audio_type"],
                            "output_path": params["output_path"],
                            "fps": params["fps"],
                            "codec": params["codec"],
                            "bitrate": params["bitrate"],
                            "duration": params["duration"],
                            "countdown": params.get("countdown", 0),
                        },
                        headers=headers,
                        timeout=10,
                    )

                    if response.status_code == 401:
                        return self._handle_unauthorized_response()

                    if response.json().get("success"):
                        print("Запись начата")
                        return 0
                    else:
                        print(
                            f"Ошибка: {response.json().get('error', 'Неизвестная ошибка')}",
                            file=sys.stderr,
                        )
                        # 409 — запись уже идёт (#206)
                        return self._exit_code_for_http(response.status_code)
            except requests.exceptions.ConnectionError:
                pass  # API не запущен, запуск нового экземпляра
        except ImportError:
            pass  # requests недоступен

        # Запуск нового экземпляра в режиме без интерфейса
        logger.info("Запуск нового экземпляра записи")

        # Запускаем запись в текущем экземпляре без GUI
        result = self._recording_service.start_recording(params)
        if not result.get("success"):
            print(
                f"Ошибка: {result.get('error', 'Не удалось начать запись')}",
                file=sys.stderr,
            )
            return EXIT_RUNTIME_ERROR

        print("Запись начата")
        return self._run_headless()

    def _run_stop(self) -> int:
        """Остановка записи через CLI."""
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            headers = self._get_api_headers()
            response = requests.post(
                f"{api_url}/api/stop", headers=headers, timeout=10
            )

            if response.status_code == 401:
                return self._handle_unauthorized_response()

            if response.json().get("success"):
                print("Запись остановлена")
                return 0
            else:
                print(
                    f"Ошибка: {response.json().get('error', 'Неизвестная ошибка')}",
                    file=sys.stderr,
                )
                # 409 — запись не активна (#206)
                return self._exit_code_for_http(response.status_code)

        except requests.exceptions.ConnectionError:
            print("Ошибка: Запущенный экземпляр не найден", file=sys.stderr)
            return EXIT_RUNTIME_ERROR
        except ImportError:
            print("Ошибка: библиотека requests недоступна", file=sys.stderr)
            return EXIT_RUNTIME_ERROR

    def _run_status(self) -> int:
        """Показ статуса записи через CLI."""
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            headers = self._get_api_headers()
            response = requests.get(
                f"{api_url}/api/status", headers=headers, timeout=10
            )

            if response.status_code == 401:
                return self._handle_unauthorized_response()

            if response.json().get("success"):
                status = response.json().get("data", {})
                if self._use_json_output():
                    print_json(status)
                else:
                    print_status(status)
                return 0
            else:
                print("Ошибка: Не удалось получить статус", file=sys.stderr)
                return self._exit_code_for_http(response.status_code)

        except requests.exceptions.ConnectionError:
            if self._use_json_output():
                print_json({"is_recording": False, "running": False})
            else:
                print("Статус: Не запущен (API сервер не найден)")
            return 0
        except ImportError:
            print("Ошибка: библиотека requests недоступна", file=sys.stderr)
            return EXIT_RUNTIME_ERROR

    def _run_schedule_list(self) -> int:
        """Список запланированных задач через CLI."""
        api_url = f"http://{self._config['api']['host']}:{self._config['api']['port']}"

        try:
            import requests

            headers = self._get_api_headers()
            response = requests.get(
                f"{api_url}/api/schedule", headers=headers, timeout=10
            )

            if response.status_code == 401:
                return self._handle_unauthorized_response()

            if response.json().get("success"):
                tasks = response.json().get("data", [])
                if self._use_json_output():
                    print_json(tasks)
                else:
                    print_schedule_list(tasks)
                return 0
            else:
                print(
                    "Ошибка: Не удалось получить расписание", file=sys.stderr
                )
                return self._exit_code_for_http(response.status_code)

        except requests.exceptions.ConnectionError:
            print("Ошибка: Запущенный экземпляр не найден", file=sys.stderr)
            return EXIT_RUNTIME_ERROR
        except ImportError:
            print("Ошибка: библиотека requests недоступна", file=sys.stderr)
            return EXIT_RUNTIME_ERROR

    def _run_schedule_create(self) -> int:
        """Создание запланированной задачи через CLI."""
        from cli.scheduler import create_schedule

        return int(create_schedule(self._config))

    def _run_schedule_update(self) -> int:
        """Обновление запланированной задачи через CLI."""
        from cli.scheduler import update_schedule

        return int(update_schedule(self._config))

    def _run_schedule_delete(self) -> int:
        """Удаление запланированной задачи через CLI."""
        from cli.scheduler import delete_schedule

        return int(delete_schedule(self._config))

    def _run_schedule_toggle(self) -> int:
        """Включение/выключение запланированной задачи через CLI."""
        from cli.scheduler import toggle_schedule

        return int(toggle_schedule(self._config))

    def _run_schedule_preview(self) -> int:
        """Просмотр предстоящих запусков через CLI."""
        from cli.scheduler import preview_upcoming_runs

        return int(preview_upcoming_runs(self._config))

    def _run_list_presets(self) -> int:
        """Показ списка preset шаблонов."""
        from cli.templates import list_presets, print_presets_help

        if self._use_json_output():
            print_json(list_presets())
        else:
            print_presets_help()
        return 0

    def _run_plugins_list(self) -> int:
        """Показ списка обнаруженных плагинов через CLI."""
        from cli.parser import print_json, print_plugins_list

        plugins = [p.to_dict() for p in self._plugin_manager.get_all_plugins()]
        if self._use_json_output():
            print_json(plugins)
        else:
            print_plugins_list(plugins)
        return 0

    def _run_plugins_info(self) -> int:
        """Показ информации о плагине через CLI."""
        from cli.parser import print_json, print_plugin_info

        name = self._config.get("plugin_name")
        if not name:
            logger.error("Не указано имя плагина")
            return EXIT_USAGE
        meta = self._plugin_manager.get_plugin_metadata(name)
        if not meta:
            logger.error("Плагин '%s' не найден", name)
            return EXIT_USAGE
        if self._use_json_output():
            print_json(meta.to_dict())
        else:
            print_plugin_info(meta.to_dict())
        return 0

    def _run_plugins_enable(self) -> int:
        """Включение плагина через CLI."""
        name = self._config.get("plugin_name")
        if not name:
            logger.error("Не указано имя плагина")
            return EXIT_USAGE
        success = self._plugin_manager.enable_plugin(name)
        if success:
            print(f"Плагин '{name}' успешно включён.")
            return 0
        else:
            print(f"Не удалось включить плагин '{name}'.")
            return EXIT_RUNTIME_ERROR

    def _run_plugins_disable(self) -> int:
        """Отключение плагина через CLI."""
        name = self._config.get("plugin_name")
        if not name:
            logger.error("Не указано имя плагина")
            return EXIT_USAGE
        success = self._plugin_manager.disable_plugin(name)
        if success:
            print(f"Плагин '{name}' успешно отключён.")
            return 0
        else:
            print(f"Не удалось отключить плагин '{name}'.")
            return EXIT_RUNTIME_ERROR

    def _run_service(self) -> int:
        """Управление службой Windows (#122)."""
        from cli.windows_service import handle_service_command

        action = self._config.get("service_action", "status")
        startup = self._config.get("service_startup", "auto")
        return handle_service_command(action, startup)
