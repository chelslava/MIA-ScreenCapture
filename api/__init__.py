"""
Пакет API
=========

Этот пакет содержит реализацию REST API:
- Flask сервер для удалённого управления
- Маршруты API для управления записью
"""

from .server import APIServer
from .routes import register_routes

__all__ = ['APIServer', 'register_routes']
