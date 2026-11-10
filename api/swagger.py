"""Модуль Swagger документации API (переходный shim).

Рукописная спецификация удалена (issue #214): OpenAPI теперь
генерируется в api/openapi.py из Pydantic-схем и метаданных
маршрутов. Импорты сохранены для обратной совместимости.
"""

from api.openapi import (  # noqa: F401
    SWAGGER_SPEC,
    build_spec,
    get_swagger_spec,
    register_swagger_routes,
)
