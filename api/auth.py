"""
Модуль аутентификации API
=========================

Обеспечивает безопасность REST API через API Key аутентификацию.
"""

import os
import secrets
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Flask, current_app, g, jsonify, request

from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Константы для конфигурации
API_KEY_HEADER = "X-API-Key"
API_KEY_ENV_VAR = "MIA_API_KEY"
API_KEY_CONFIG_KEY = "api_key"
API_KEY_LENGTH = 32  # Длина ключа в байтах (256 бит)
AUTH_DISABLED_CONFIG_KEY = "AUTH_DISABLED"  # Явное отключение аутентификации


def generate_api_key() -> str:
    """
    Генерация криптографически безопасного API ключа.

    Returns:
        URL-безопасная строка длиной ~43 символа
    """
    return secrets.token_urlsafe(API_KEY_LENGTH)


def get_stored_api_key() -> str | None:
    """
    Получение сохранённого API ключа из переменных окружения.

    Returns:
        API ключ или None если не установлен
    """
    return os.environ.get(API_KEY_ENV_VAR)


def init_api_auth(app: Flask, api_key: str | None = None) -> str:
    """
    Инициализация аутентификации API для Flask приложения.

    Args:
        app: Экземпляр Flask приложения
        api_key: API ключ (если None, генерируется или берётся из env)

    Returns:
        Установленный API ключ
    """
    if api_key is None:
        # Пытаемся получить из переменной окружения
        api_key = get_stored_api_key()

    if api_key is None:
        # Генерируем новый ключ
        api_key = generate_api_key()
        logger.warning(
            f"API ключ не установлен. Сгенерирован новый ключ. "
            f"Установите переменную окружения {API_KEY_ENV_VAR} для постоянного ключа."
        )
        # Примечание: сам ключ не логируется в целях безопасности

    # Сохраняем в конфигурации приложения
    app.config[API_KEY_CONFIG_KEY] = api_key

    logger.info("API аутентификация инициализирована")
    return api_key


def require_api_key(f: Callable) -> Callable:
    """
    Декоратор для защиты эндпоинтов API ключом.

    Проверяет наличие и валидность API ключа в заголовке запроса.

    Usage:
        @app.route('/api/protected')
        @require_api_key
        def protected_endpoint():
            return {'data': 'sensitive'}

    Args:
        f: Функция для защиты

    Returns:
        Декорированная функция с проверкой аутентификации
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        # Получаем ключ из заголовка
        provided_key = request.headers.get(API_KEY_HEADER)

        # Получаем ожидаемый ключ из конфигурации
        expected_key = current_app.config.get(API_KEY_CONFIG_KEY)

        # Если ключ не настроен, проверяем режим тестирования с явным отключением
        if expected_key is None:
            # Требуем оба флага (TESTING=True И AUTH_DISABLED=True) для защиты
            # от случайного отключения аутентификации в production окружении.
            # Это обеспечивает безопасность: в production TESTING=False, поэтому
            # даже если AUTH_DISABLED=True, аутентификация не будет отключена.
            if current_app.config.get("TESTING") and current_app.config.get(
                AUTH_DISABLED_CONFIG_KEY
            ):
                # Аутентификация явно отключена для тестирования
                logger.debug(
                    f"Аутентификация отключена для тестирования: {request.endpoint}"
                )
                return f(*args, **kwargs)
            # В production режиме или без явного отключения - ошибка
            logger.error(
                "API аутентификация не инициализирована. "
                "Вызовите init_api_auth() при инициализации приложения."
            )
            return jsonify(
                {
                    "success": False,
                    "error": "Сервер не настроен",
                    "message": "API аутентификация не инициализирована",
                }
            ), 500

        # Проверяем наличие ключа
        if provided_key is None:
            logger.warning(
                f"Попытка доступа без API ключа: {request.endpoint}"
            )
            return jsonify(
                {
                    "success": False,
                    "error": "Требуется API ключ",
                    "message": f"Добавьте заголовок {API_KEY_HEADER} с вашим API ключом",
                }
            ), 401

        # Проверяем валидность ключа (constant-time comparison для защиты от timing attacks)
        if not secrets.compare_digest(provided_key, expected_key):
            logger.warning(f"Неверный API ключ: {request.endpoint}")
            return jsonify(
                {"success": False, "error": "Неверный API ключ"}
            ), 401

        # Ключ валиден, выполняем функцию
        return f(*args, **kwargs)

    return decorated_function


def optional_api_key(f: Callable) -> Callable:
    """
    Декоратор для опциональной аутентификации.

    Если API ключ предоставлен и валиден, добавляет информацию в контекст.
    Если ключ не предоставлен или невалиден, всё равно выполняет функцию.

    Полезно для эндпоинтов, которые возвращают разный контент
    для авторизованных и неавторизованных пользователей.

    Args:
        f: Функция для декорирования

    Returns:
        Декорированная функция
    """

    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        provided_key = request.headers.get(API_KEY_HEADER)
        expected_key = current_app.config.get(API_KEY_CONFIG_KEY)

        # Устанавливаем флаг аутентификации
        g.is_authenticated = False

        if (
            provided_key
            and expected_key
            and secrets.compare_digest(provided_key, expected_key)
        ):
            g.is_authenticated = True
            logger.debug(f"Успешная аутентификация: {request.endpoint}")

        return f(*args, **kwargs)

    return decorated_function


def get_api_key(app: Flask | None = None) -> str | None:
    """
    Получение текущего API ключа из конфигурации.

    Args:
        app: Flask приложение (если None, используется current_app)

    Returns:
        API ключ или None если не установлен
    """
    if app is None:
        try:
            return current_app.config.get(API_KEY_CONFIG_KEY)
        except RuntimeError:
            # Вне контекста приложения
            return get_stored_api_key()
    return app.config.get(API_KEY_CONFIG_KEY)


def check_api_key(provided_key: str, app: Flask | None = None) -> bool:
    """
    Проверка API ключа без декоратора.

    Полезно для проверки в middleware или других контекстах.

    Args:
        provided_key: Ключ для проверки
        app: Flask приложение (если None, используется current_app)

    Returns:
        True если ключ валиден

    Raises:
        ValueError: Если аутентификация не инициализирована
    """
    if app is None:
        try:
            expected_key = current_app.config.get(API_KEY_CONFIG_KEY)
        except RuntimeError:
            # Вне контекста приложения
            expected_key = get_stored_api_key()
    else:
        expected_key = app.config.get(API_KEY_CONFIG_KEY)

    if expected_key is None:
        # Аутентификация не настроена — это ошибка конфигурации
        logger.error(
            "Попытка проверки API ключа без инициализированной аутентификации. "
            "Вызовите init_api_auth() при инициализации приложения."
        )
        raise ValueError("API аутентификация не инициализирована")

    if not provided_key:
        # Пустой или None ключ считается невалидным
        return False

    return secrets.compare_digest(provided_key, expected_key)
