"""Генератор OpenAPI 3.0.3 из Pydantic-схем и метаданных маршрутов.

Источник истины (issue #214):
- компоненты — Pydantic-модели (api/schemas.py + api/response_schemas.py);
- пути и операции — декларативный словарь ENDPOINTS
  (api/openapi_endpoints.py) рядом с описанием маршрутов.

Модуль заменяет рукописную спецификацию на ~2000 строк: схема поля
теперь описывается один раз — в модели, из которой она валидируется.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.openapi_endpoints import ENDPOINTS
from api.response_schemas import COMPONENT_MODELS, INLINE_NESTED_COMPONENTS
from version import get_version

# Строки методов, для которых добавляется заголовок Idempotency-Key
_IDEMPOTENT_METHODS = frozenset({"post", "put", "patch", "delete"})
# Операции без метаданных в ENDPOINTS и служебные маршруты,
# у которых OpenAPI-описание отсутствует намеренно
_UNDOCUMENTED_PATH_PREFIXES = ("/api/docs", "/api/swagger.json", "/ws")


def _strip_titles(schema: dict[str, Any]) -> dict[str, Any]:
    """Убирает автогенерируемые Pydantic `title` на всех уровнях.

    Args:
        schema: JSON-схема произвольной вложенности.

    Returns:
        Та же схема без ключей `title` (мутирует и возвращает).
    """
    schema.pop("title", None)
    for value in schema.values():
        if isinstance(value, dict):
            _strip_titles(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _strip_titles(item)
    return schema


def _flatten_null_anyof(schema: dict[str, Any]) -> dict[str, Any]:
    """anyOf[..., null] -> nullable: true (совместимость с OpenAPI 3.0).

    Args:
        schema: JSON-схема поля.

    Returns:
        Схема в нотации OpenAPI 3.0.3.
    """
    any_of = schema.get("anyOf")
    if not isinstance(any_of, list):
        return schema
    non_null = [item for item in any_of if item != {"type": "null"}]
    if len(non_null) == len(any_of):
        return schema
    merged: dict[str, Any] = {
        key: value for key, value in schema.items() if key != "anyOf"
    }
    merged["nullable"] = True
    if len(non_null) == 1:
        base = non_null[0]
        for key, value in base.items():
            merged.setdefault(key, value)
    else:
        merged["anyOf"] = non_null
    return merged


def _to_openapi30(schema: dict[str, Any]) -> dict[str, Any]:
    """Приводит JSON-схему Pydantic к нотации OpenAPI 3.0.3.

    Args:
        schema: Схема из `model_json_schema`.

    Returns:
        Схема без title, с nullable вместо anyOf-null и булевыми
        exclusiveMinimum/exclusiveMaximum.
    """
    schema = _flatten_null_anyof(schema)
    for key in ("exclusiveMinimum", "exclusiveMaximum"):
        value = schema.get(key)
        if isinstance(value, (int, float)):
            bound = "minimum" if key == "exclusiveMinimum" else "maximum"
            schema.pop(key, None)
            schema[bound] = value
            schema[f"{bound}Exclusive"] = True
    for value in schema.values():
        if isinstance(value, dict):
            _to_openapi30(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _to_openapi30(item)
    return schema


def _inline_defs(
    schema: dict[str, Any], defs: dict[str, Any]
) -> dict[str, Any]:
    """Заменяет $ref на #/$defs/X инлайновым телом определения.

    Args:
        schema: Схема компонента.
        defs: Словарь `$defs` из `model_json_schema`.

    Returns:
        Схема без ссылок на `$defs` (новый словарь).
    """
    ref = schema.get("$ref", "")
    if ref.startswith("#/$defs/"):
        name = ref.removeprefix("#/$defs/")
        return _inline_defs(deepcopy(defs[name]), defs)
    for key, value in schema.items():
        if isinstance(value, dict):
            schema[key] = _inline_defs(value, defs)
        elif isinstance(value, list):
            schema[key] = [
                _inline_defs(item, defs) if isinstance(item, dict) else item
                for item in value
            ]
    return schema


def _hoist_defs(
    schema: dict[str, Any], defs: dict[str, Any]
) -> dict[str, Any]:
    """Переписывает #/$defs/X на #/components/schemas/X.

    Args:
        schema: Схема компонента (мутируется).
        defs: Имена `$defs` (для проверки, ожидается поднятый компонент).

    Returns:
        Та же схема с переписанными ссылками.
    """
    for value in schema.values():
        if isinstance(value, dict):
            _hoist_defs(value, defs)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _hoist_defs(item, defs)
    ref = schema.get("$ref", "")
    if ref.startswith("#/$defs/"):
        name = ref.removeprefix("#/$defs/")
        if name not in defs:
            raise KeyError(f"$defs '{name}' не поднят в компоненты")
        schema["$ref"] = f"#/components/schemas/{name}"
    return schema


def _build_component_schemas() -> dict[str, dict[str, Any]]:
    """Строит components.schemas из реестра Pydantic-моделей.

    Returns:
        Компоненты в нотации OpenAPI 3.0.3.
    """
    components: dict[str, dict[str, Any]] = {}
    for name, model in COMPONENT_MODELS.items():
        raw = model.model_json_schema(by_alias=True)
        raw.pop("$schema", None)
        defs: dict[str, Any] = raw.pop("$defs", {})
        if name in INLINE_NESTED_COMPONENTS:
            schema = _inline_defs(raw, defs)
        else:
            # Вложенные модели поднимаются в компоненты по имени класса
            for def_name, def_body in defs.items():
                components.setdefault(
                    def_name, _strip_titles(_to_openapi30(deepcopy(def_body)))
                )
            schema = _hoist_defs(raw, defs)
        components[name] = _strip_titles(_to_openapi30(schema))
    return components


def _resolve_schema(entry: dict[str, Any] | None) -> dict[str, Any] | None:
    """Разрешает описание схемы ответа из метаданных операции.

    Args:
        entry: `{"ref": имя}` — компонент реестра, `{"inline": ...}` —
            инлайновая схема переходного периода.

    Returns:
        OpenAPI-схема или None.
    """
    if entry is None:
        return None
    if "ref" in entry:
        name = entry["ref"]
        if name not in COMPONENT_MODELS:
            raise KeyError(f"Неизвестный компонент '{name}' в метаданных")
        return {"$ref": f"#/components/schemas/{name}"}
    inline: dict[str, Any] = entry["inline"]
    return deepcopy(inline)


def build_spec() -> dict[str, Any]:
    """Собирает полную OpenAPI-спецификацию.

    Returns:
        Спецификация OpenAPI 3.0.3 (свежий словарь при каждом вызове).
    """
    components = _build_component_schemas()
    paths: dict[str, dict[str, Any]] = {}
    for key, meta in ENDPOINTS.items():
        method, path = key.split(" ", 1)
        operation: dict[str, Any] = {"summary": meta["summary"]}
        if meta.get("description"):
            operation["description"] = meta["description"]
        if meta.get("operation_id"):
            operation["operationId"] = meta["operation_id"]
        if meta.get("tags"):
            operation["tags"] = list(meta["tags"])

        request_model = meta.get("request")
        request_inline = meta.get("request_inline")
        if request_model is not None or request_inline is not None:
            if request_model is not None:
                if request_model not in COMPONENT_MODELS:
                    raise KeyError(
                        f"Неизвестная модель запроса '{request_model}'"
                    )
                request_schema: dict[str, Any] = {
                    "$ref": f"#/components/schemas/{request_model}"
                }
            else:
                # Инлайновая схема переходного периода (issue #214):
                # тело не покрыто Pydantic-моделью
                inline_request: dict[str, Any] = request_inline or {}
                request_schema = deepcopy(inline_request)
            body: dict[str, Any] = {
                "content": {"application/json": {"schema": request_schema}}
            }
            if meta.get("request_examples"):
                body["content"]["application/json"]["examples"] = deepcopy(
                    meta["request_examples"]
                )
            operation["requestBody"] = body

        responses: dict[str, Any] = {}
        for code, resp in meta.get("responses", {}).items():
            entry: dict[str, Any] = {"description": resp["description"]}
            schema = _resolve_schema(resp.get("schema"))
            if schema is not None:
                entry["content"] = {"application/json": {"schema": schema}}
            responses[code] = entry
        operation["responses"] = responses

        paths.setdefault(path, {})[method.lower()] = operation

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "MIA-ScreenCapture API",
            "description": (
                "REST API для управления записью экрана.\n\n"
                "**Rate limiting (#152):** write-операции ограничиваются "
                "лимитами из `api.rate_limit` в config.json. Заголовки "
                "ответа: `Retry-After` (секунды до снятия блокировки) и "
                "`X-RateLimit-Limit` (применённый лимит окна). При "
                "превышении возвращается 429 с кодом `rate_limited`."
            ),
            "version": get_version(),
            "contact": {"name": "MIA Development Team"},
            "license": {"name": "MIT"},
        },
        "servers": [
            {"url": "http://localhost:5000", "description": "Локальный сервер"}
        ],
        "security": [{"ApiKeyAuth": []}],
        "components": {
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API ключ для аутентификации",
                }
            },
            "headers": {
                "X-Trace-ID": {
                    "description": "Идентификатор сквозной трассировки запроса",
                    "schema": {"type": "string"},
                },
                "X-Request-ID": {
                    "description": "Уникальный идентификатор HTTP-запроса",
                    "schema": {"type": "string"},
                },
            },
            "schemas": components,
        },
        "paths": paths,
    }


def get_swagger_spec() -> dict[str, Any]:
    """Возвращает спецификацию с заголовками идемпотентности.

    Копия спецификации, где каждый write-эндпоинт получает описание
    заголовка `Idempotency-Key`, а сервер заменяется относительным
    URL (Swagger UI подставляет текущий хост).

    Returns:
        Копия словаря с OpenAPI спецификацией.
    """
    spec = build_spec()
    spec["servers"] = [{"url": "/", "description": "Текущий API сервер"}]

    idempotency_header = {
        "name": "Idempotency-Key",
        "in": "header",
        "required": False,
        "schema": {"type": "string", "maxLength": 128},
        "description": (
            "Идемпотентный ключ для безопасных ретраев write-запросов. "
            "Одинаковый ключ + одинаковый payload вернёт cached-ответ."
        ),
    }
    for path_spec in spec["paths"].values():
        for method_name, operation in path_spec.items():
            if method_name not in _IDEMPOTENT_METHODS:
                continue
            parameters = operation.setdefault("parameters", [])
            if not any(
                item.get("in") == "header"
                and item.get("name") == "Idempotency-Key"
                for item in parameters
            ):
                parameters.append(deepcopy(idempotency_header))
    return spec


# Структурные тесты (tests/unit/api/test_swagger.py) читают константу;
# get_swagger_spec() надстраивает над ней идемпотентность и servers.
SWAGGER_SPEC: dict[str, Any] = build_spec()


def register_swagger_routes(app: Any) -> None:
    """Регистрирует маршруты документации (JSON + Swagger UI).

    Args:
        app: Экземпляр Flask приложения.
    """
    from flask import jsonify, request

    @app.route("/api/swagger.json", methods=["GET"])
    def get_swagger_json() -> Any:
        """Возвращает OpenAPI спецификацию в формате JSON."""
        spec = get_swagger_spec()
        # Для удобства в UI показываем абсолютный URL текущего хоста/порта.
        spec["servers"] = [
            {
                "url": request.host_url.rstrip("/"),
                "description": "Текущий API сервер",
            }
        ]
        return jsonify(spec)

    @app.route("/api/docs", methods=["GET"])
    def swagger_ui() -> Any:
        """Возвращает Swagger UI страницу."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>MIA-ScreenCapture API Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: "/api/swagger.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                deepLinking: true,
                persistAuthorization: true,
                displayRequestDuration: true,
                tryItOutEnabled: true,
                displayOperationId: false,
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
            });
        }
    </script>
</body>
</html>
        """
