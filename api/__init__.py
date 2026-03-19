"""
Пакет API
=========

Этот пакет содержит реализацию REST API:
- Flask сервер для удалённого управления
- Маршруты API для управления записью
"""

from .routes import register_routes
from .server import APIServer

__all__ = ["APIServer", "register_routes"]
