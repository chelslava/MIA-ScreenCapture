"""
Модуль API сервера
==================

REST API сервер на базе Flask для удалённого управления рекордером.
Работает в отдельном потоке, чтобы не блокировать GUI.
"""

import threading
from typing import Callable, Dict, Optional

from flask import Flask, jsonify
from flask_cors import CORS
from waitress import serve

from logger_config import get_module_logger

logger = get_module_logger(__name__)


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
        self._running = False

        # Обратные вызовы
        self._callbacks: Dict[str, Callable] = {}

        # Создание Flask приложения
        self._create_app()

    def _create_app(self) -> None:
        """Создание и настройка Flask приложения."""
        from api.auth import init_api_auth

        self.app = Flask(__name__)
        CORS(self.app)

        # Инициализация API аутентификации
        init_api_auth(self.app)

        # Логирование API ключа для пользователя (частично, для безопасности)
        api_key = self.get_api_key()
        if api_key:
            # Показываем только начало и конец ключа для идентификации
            masked_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
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
            logger.error(f"Ошибка API: {e}")
            return jsonify({"error": str(e)}), 500

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

    def start(self) -> bool:
        """
        Запуск API сервера в фоновом потоке.

        Returns:
            True если сервер успешно запущен
        """
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
            # Использование waitress как production-ready WSGI сервера
            serve(
                self.app,
                host=self.host,
                port=self.port,
                threads=4,
                _quiet=True,
            )
        except Exception as e:
            logger.error(f"Ошибка сервера: {e}")
            self._running = False

    def stop(self) -> None:
        """Остановка API сервера."""
        self._running = False
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
