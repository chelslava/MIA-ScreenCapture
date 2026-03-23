"""
Модуль API сервера
==================

REST API сервер на базе Flask для удалённого управления рекордером.
Работает в отдельном потоке, чтобы не блокировать GUI.
"""

import re
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from waitress.server import create_server

from logger_config import get_module_logger

logger = get_module_logger(__name__)

_VERSION_FALLBACK = "unknown"
_REQUEST_ID_HEADER = "X-Request-ID"
_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"


class APIServer:
    """
    REST API сервер для управления рекордером.

    Предоставляет эндпоинты для:
    - Запуска/остановки/паузы записей
    - Получения статуса и списка записей
    - Управления запланированными задачами
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 5000):
        """
        Инициализация API сервера.

        Args:
            host: Адрес хоста для привязки
            port: Номер порта для прослушивания
        """
        self.host = host
        self.port = port

        # Flask приложение
        self.app: Optional[Flask] = None
        self._server_thread: Optional[threading.Thread] = None
        self._wsgi_server: Optional[Any] = None
        self._running = False
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._version = self._load_version()

        # Обратные вызовы
        self._callbacks: Dict[str, Callable] = {}
        self._websocket_manager: Optional[Any] = None

        # Создание Flask приложения
        self._create_app()

    def _create_app(self) -> None:
        """Создание и настройка Flask приложения."""
        from api.auth import init_api_auth
        from api.rate_limiter import init_rate_limiter

        self.app = Flask(__name__)
        CORS(self.app)

        # Инициализация API аутентификации
        init_api_auth(self.app)
        # Инициализация rate limiter (применяется декораторами в routes.py)
        init_rate_limiter(self.app)

        # Логирование API ключа для пользователя (частично, для безопасности)
        api_key = self.get_api_key()
        if api_key:
            # Показываем только начало и конец ключа для идентификации
            masked_key = (
                f"{api_key[:8]}...{api_key[-4:]}"
                if len(api_key) > 12
                else "***"
            )
            logger.info(f"API ключ: {masked_key}")
            logger.warning(
                "Сохраните этот ключ для использования с CLI! "
                "Установите переменную окружения MIA_API_KEY для постоянного ключа."
            )

        # Регистрация обработчиков ошибок
        @self.app.errorhandler(404)
        def not_found(e):
            return jsonify({"error": "Не найдено"}), 404

        @self.app.errorhandler(500)
        def server_error(e):
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.exception(f"Ошибка API: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

        @self.app.before_request
        def assign_request_id() -> None:
            request_id = request.headers.get(_REQUEST_ID_HEADER, "").strip()
            if not request_id:
                request_id = uuid.uuid4().hex
            g.request_id = request_id

            if request.path == "/health":
                return jsonify(self._get_health_payload())

        @self.app.after_request
        def add_request_id_header(response):
            request_id = getattr(g, "request_id", None)
            if not request_id:
                request_id = uuid.uuid4().hex
                g.request_id = request_id
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response

        logger.info("Flask приложение создано")

    def set_callback(self, action: str, callback: Callable) -> None:
        """
        Установка функции обратного вызова для действия.

        Args:
            action: Имя действия (start, stop, pause, status и т.д.)
            callback: Функция обратного вызова
        """
        self._callbacks[action] = callback

    def get_callback(self, action: str) -> Optional[Callable]:
        """
        Получение обратного вызова для действия.

        Args:
            action: Имя действия

        Returns:
            Функция обратного вызова или None
        """
        return self._callbacks.get(action)

    def set_websocket_manager(self, manager: Any) -> None:
        """Устанавливает менеджер событий для real-time уведомлений."""
        self._websocket_manager = manager

    def get_websocket_manager(self) -> Optional[Any]:
        """Возвращает менеджер real-time уведомлений."""
        return self._websocket_manager

    def start(self) -> bool:
        """
        Запуск API сервера в фоновом потоке.

        Returns:
            True если сервер успешно запущен
        """
        with self._lock:
            if self._running:
                logger.warning("API сервер уже запущен")
                return False

            try:
                self._running = True
                self._server_thread = threading.Thread(
                    target=self._run_server, daemon=True
                )
                self._server_thread.start()

                logger.info(f"API сервер запущен на {self.host}:{self.port}")
                return True

            except Exception as e:
                logger.error(f"Не удалось запустить API сервер: {e}")
                self._running = False
                return False

    def _run_server(self) -> None:
        """Запуск WSGI сервера."""
        try:
            # Создаём управляемый waitress сервер, чтобы корректно остановить его через stop().
            self._wsgi_server = create_server(
                self.app,
                _start=False,
                host=self.host,
                port=self.port,
                threads=4,
                clear_untrusted_proxy_headers=True,
            )
            self._wsgi_server.run()
        except Exception as e:
            logger.error(f"Ошибка сервера: {e}")
        finally:
            self._running = False
            self._wsgi_server = None

    def stop(self) -> None:
        """Остановка API сервера."""
        with self._lock:
            self._running = False
            if self._wsgi_server is not None:
                try:
                    self._wsgi_server.close()
                except Exception as e:
                    logger.warning(f"Ошибка закрытия API сервера: {e}")

        if self._server_thread and self._server_thread.is_alive():
            self._server_thread.join(timeout=3)

        logger.info("API сервер остановлен")

    def is_running(self) -> bool:
        """Проверка работы сервера."""
        return self._running

    def get_url(self) -> str:
        """Получение URL сервера."""
        return f"http://{self.host}:{self.port}"

    def get_api_key(self) -> Optional[str]:
        """
        Получение текущего API ключа.

        Returns:
            API ключ или None если не установлен
        """
        from api.auth import get_api_key

        return get_api_key(self.app)

    def _load_version(self) -> str:
        """Читает версию из pyproject.toml или возвращает fallback."""
        try:
            text = _PYPROJECT_PATH.read_text(encoding="utf-8")
            match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception as e:
            logger.debug(f"Не удалось прочитать версию из pyproject.toml: {e}")
        return _VERSION_FALLBACK

    def _get_health_payload(self) -> Dict[str, Any]:
        """Возвращает расширенный health payload."""
        websocket = (
            self._websocket_manager.get_stats()
            if self._websocket_manager is not None
            else {"transport_ready": False}
        )
        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": self._version,
            "uptime_seconds": round(time.monotonic() - self._start_time, 3),
            "websocket": websocket,
        }
