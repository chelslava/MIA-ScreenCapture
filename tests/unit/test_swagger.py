"""
Unit тесты для Swagger документации
====================================

Тестирует OpenAPI/Swagger спецификацию и эндпоинты.
"""

import re
from pathlib import Path
from unittest.mock import MagicMock

from flask import Flask

from api.routes import register_routes
from api.schemas import (
    CreateScheduleRequest,
    StartRecordingRequest,
    ToggleScheduleRequest,
    UpdateConfigRequest,
    UpdateScheduleRequest,
)
from api.server import APIServer
from api.swagger import SWAGGER_SPEC, get_swagger_spec, register_swagger_routes

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_version_from_pyproject() -> str:
    """Возвращает версию проекта из pyproject.toml."""
    pyproject_text = (PROJECT_ROOT / "pyproject.toml").read_text(
        encoding="utf-8",
    )
    match = re.search(
        r'^version\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE
    )
    if match is None:
        raise AssertionError("Не удалось прочитать версию из pyproject.toml")
    return match.group(1)


def _load_version_from_readme() -> str:
    """Возвращает версию из заголовка README."""
    readme_text = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(
        r"^#\s+MIA-ScreenCapture\s+v(\d+\.\d+\.\d+)\s*$",
        readme_text,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError("Не удалось прочитать версию из README.md")
    return match.group(1)


class TestSwaggerSpec:
    """Тесты спецификации OpenAPI."""

    def test_swagger_spec_exists(self) -> None:
        """Проверка существования спецификации."""
        assert SWAGGER_SPEC is not None
        assert isinstance(SWAGGER_SPEC, dict)

    def test_swagger_spec_openapi_version(self) -> None:
        """Проверка версии OpenAPI."""
        assert "openapi" in SWAGGER_SPEC
        assert SWAGGER_SPEC["openapi"].startswith("3.")

    def test_swagger_spec_info(self) -> None:
        """Проверка информации о API."""
        assert "info" in SWAGGER_SPEC
        info = SWAGGER_SPEC["info"]

        assert "title" in info
        assert "version" in info
        assert "description" in info

        assert "MIA-ScreenCapture" in info["title"]
        assert info["version"] == "1.4.5"

    def test_swagger_spec_servers(self) -> None:
        """Проверка списка серверов."""
        assert "servers" in SWAGGER_SPEC
        servers = SWAGGER_SPEC["servers"]

        assert isinstance(servers, list)
        assert len(servers) > 0

        for server in servers:
            assert "url" in server

    def test_swagger_spec_security(self) -> None:
        """Проверка настроек безопасности."""
        assert "security" in SWAGGER_SPEC
        security = SWAGGER_SPEC["security"]

        assert isinstance(security, list)
        assert {"ApiKeyAuth": []} in security

    def test_swagger_spec_components(self) -> None:
        """Проверка компонентов."""
        assert "components" in SWAGGER_SPEC
        components = SWAGGER_SPEC["components"]

        assert "securitySchemes" in components
        assert "schemas" in components

    def test_swagger_spec_security_schemes(self) -> None:
        """Проверка схем безопасности."""
        security_schemes = SWAGGER_SPEC["components"]["securitySchemes"]

        assert "ApiKeyAuth" in security_schemes
        api_key_auth = security_schemes["ApiKeyAuth"]

        assert api_key_auth["type"] == "apiKey"
        assert api_key_auth["in"] == "header"
        assert api_key_auth["name"] == "X-API-Key"

    def test_swagger_spec_error_schema(self) -> None:
        """Проверка схемы Error."""
        schemas = SWAGGER_SPEC["components"]["schemas"]

        assert "Error" in schemas
        error_schema = schemas["Error"]

        assert "properties" in error_schema
        assert "success" in error_schema["properties"]
        assert "error" in error_schema["properties"]
        assert "trace_id" in error_schema["properties"]

        error_props = error_schema["properties"]["error"]["properties"]
        assert {"code", "message", "details"}.issubset(error_props.keys())

    def test_swagger_spec_validation_error_schema(self) -> None:
        """Проверка схемы ValidationError."""
        schemas = SWAGGER_SPEC["components"]["schemas"]

        assert "ValidationError" in schemas
        validation_error = schemas["ValidationError"]

        assert "properties" in validation_error
        assert "trace_id" in validation_error["properties"]

        error_props = validation_error["properties"]["error"]["properties"]
        assert "details" in error_props
        item_props = error_props["details"]["items"]["properties"]
        assert {"field", "message", "type"}.issubset(item_props.keys())

    def test_swagger_spec_health_schema(self) -> None:
        """Проверка схемы Health."""
        schemas = SWAGGER_SPEC["components"]["schemas"]

        assert "Health" in schemas
        health_schema = schemas["Health"]

        assert "websocket" in health_schema["properties"]
        assert health_schema["properties"]["websocket"]["$ref"].endswith(
            "/WebSocketStats"
        )

    def test_swagger_spec_status_schema(self) -> None:
        """Проверка схемы Status."""
        schemas = SWAGGER_SPEC["components"]["schemas"]

        assert "Status" in schemas

    def test_swagger_spec_paths(self) -> None:
        """Проверка наличия путей."""
        assert "paths" in SWAGGER_SPEC
        paths = SWAGGER_SPEC["paths"]

        assert isinstance(paths, dict)
        assert len(paths) > 0


class TestGetSwaggerSpec:
    """Тесты функции get_swagger_spec."""

    def test_get_swagger_spec_returns_dict(self) -> None:
        """Проверка что функция возвращает словарь."""
        spec = get_swagger_spec()

        assert isinstance(spec, dict)

    def test_get_swagger_spec_returns_copy(self) -> None:
        """Проверка что функция возвращает копию."""
        spec1 = get_swagger_spec()
        spec2 = get_swagger_spec()

        # Изменение одной копии не должно влиять на другую
        spec1["test_key"] = "test_value"
        assert "test_key" not in spec2

    def test_get_swagger_spec_complete(self) -> None:
        """Проверка полноты спецификации."""
        spec = get_swagger_spec()

        required_keys = ["openapi", "info", "servers", "paths", "components"]
        for key in required_keys:
            assert key in spec


class TestRegisterSwaggerRoutes:
    """Тесты регистрации маршрутов Swagger."""

    def test_register_swagger_routes(self) -> None:
        """Проверка регистрации маршрутов."""
        app = Flask(__name__)

        register_swagger_routes(app)

        # Проверяем что маршруты зарегистрированы
        rules = [rule.rule for rule in app.url_map.iter_rules()]

        assert "/api/swagger.json" in rules
        assert "/api/docs" in rules

    def test_swagger_json_endpoint(self) -> None:
        """Проверка эндпоинта swagger.json."""
        app = Flask(__name__)
        register_swagger_routes(app)

        client = app.test_client()
        response = client.get("/api/swagger.json")

        assert response.status_code == 200
        assert response.content_type == "application/json"

        data = response.get_json()
        assert "openapi" in data

    def test_swagger_ui_endpoint(self) -> None:
        """Проверка эндпоинта Swagger UI."""
        app = Flask(__name__)
        register_swagger_routes(app)

        client = app.test_client()
        response = client.get("/api/docs")

        assert response.status_code == 200
        assert response.content_type == "text/html; charset=utf-8"

    def test_swagger_ui_contains_title(self) -> None:
        """Проверка что Swagger UI содержит заголовок."""
        app = Flask(__name__)
        register_swagger_routes(app)

        client = app.test_client()
        response = client.get("/api/docs")

        html = response.get_data(as_text=True)
        assert "Swagger UI" in html or "swagger" in html.lower()

    def test_swagger_ui_contains_spec_url(self) -> None:
        """Проверка что Swagger UI ссылается на спецификацию."""
        app = Flask(__name__)
        register_swagger_routes(app)

        client = app.test_client()
        response = client.get("/api/docs")

        html = response.get_data(as_text=True)
        assert "/api/swagger.json" in html


class TestSwaggerPaths:
    """Тесты путей в спецификации."""

    def test_status_path_exists(self) -> None:
        """Проверка наличия пути /api/status."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/status" in paths

    def test_health_path_exists(self) -> None:
        """Проверка наличия пути /health."""
        paths = SWAGGER_SPEC["paths"]

        assert "/health" in paths

    def test_start_path_exists(self) -> None:
        """Проверка наличия пути /api/start."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/start" in paths

    def test_stop_path_exists(self) -> None:
        """Проверка наличия пути /api/stop."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/stop" in paths

    def test_pause_path_exists(self) -> None:
        """Проверка наличия пути /api/pause."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/pause" in paths

    def test_schedule_path_exists(self) -> None:
        """Проверка наличия пути /api/schedule."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/schedule" in paths

    def test_devices_path_exists(self) -> None:
        """Проверка наличия пути /api/devices."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/devices" in paths

    def test_windows_path_exists(self) -> None:
        """Проверка наличия пути /api/windows."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/windows" in paths

    def test_config_path_exists(self) -> None:
        """Проверка наличия пути /api/config."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/config" in paths

    def test_recent_events_path_exists(self) -> None:
        """Проверка наличия пути /api/events/recent."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/events/recent" in paths

    def test_events_stats_path_exists(self) -> None:
        """Проверка наличия пути /api/events/stats."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/events/stats" in paths

    def test_observability_paths_exist(self) -> None:
        """Проверка наличия observability путей."""
        paths = SWAGGER_SPEC["paths"]

        assert "/api/observability/metrics" in paths
        assert "/api/observability/baseline" in paths


class TestSwaggerPathMethods:
    """Тесты HTTP методов в путях."""

    def test_status_has_get(self) -> None:
        """Проверка GET метода для /api/status."""
        status_path = SWAGGER_SPEC["paths"]["/api/status"]

        assert "get" in status_path

    def test_start_has_post(self) -> None:
        """Проверка POST метода для /api/start."""
        start_path = SWAGGER_SPEC["paths"]["/api/start"]

        assert "post" in start_path

    def test_stop_has_post(self) -> None:
        """Проверка POST метода для /api/stop."""
        stop_path = SWAGGER_SPEC["paths"]["/api/stop"]

        assert "post" in stop_path

    def test_config_has_get_and_put(self) -> None:
        """Проверка GET и PUT методов для /api/config."""
        config_path = SWAGGER_SPEC["paths"]["/api/config"]

        assert "get" in config_path
        assert "put" in config_path

    def test_health_has_get(self) -> None:
        """Проверка GET метода для /health."""
        health_path = SWAGGER_SPEC["paths"]["/health"]

        assert "get" in health_path

    def test_recent_events_has_get(self) -> None:
        """Проверка GET метода для /api/events/recent."""
        recent_events_path = SWAGGER_SPEC["paths"]["/api/events/recent"]

        assert "get" in recent_events_path

    def test_events_stats_has_get(self) -> None:
        """Проверка GET метода для /api/events/stats."""
        events_stats_path = SWAGGER_SPEC["paths"]["/api/events/stats"]

        assert "get" in events_stats_path

    def test_observability_paths_have_get(self) -> None:
        """Проверка GET метода для observability путей."""
        metrics_path = SWAGGER_SPEC["paths"]["/api/observability/metrics"]
        baseline_path = SWAGGER_SPEC["paths"]["/api/observability/baseline"]

        assert "get" in metrics_path
        assert "get" in baseline_path


class TestSwaggerPathResponses:
    """Тесты ответов в путях."""

    def test_status_has_200_response(self) -> None:
        """Проверка ответа 200 для /api/status."""
        status_path = SWAGGER_SPEC["paths"]["/api/status"]["get"]

        assert "responses" in status_path
        assert "200" in status_path["responses"]

    def test_start_has_400_response(self) -> None:
        """Проверка ответа 400 для /api/start."""
        start_path = SWAGGER_SPEC["paths"]["/api/start"]["post"]

        assert "responses" in start_path
        assert "400" in start_path["responses"]

    def test_unauthorized_response(self) -> None:
        """Проверка ответа 401 для защищённых эндпоинтов."""
        start_path = SWAGGER_SPEC["paths"]["/api/start"]["post"]

        assert "401" in start_path["responses"]


class TestSwaggerDescriptions:
    """Тесты описаний в спецификации."""

    def test_status_has_description(self) -> None:
        """Проверка описания для /api/status."""
        status_path = SWAGGER_SPEC["paths"]["/api/status"]["get"]

        assert "description" in status_path
        assert "summary" in status_path

    def test_start_has_description(self) -> None:
        """Проверка описания для /api/start."""
        start_path = SWAGGER_SPEC["paths"]["/api/start"]["post"]

        assert "description" in start_path
        assert "summary" in start_path

    def test_info_has_description(self) -> None:
        """Проверка описания API."""
        info = SWAGGER_SPEC["info"]

        assert "description" in info
        assert len(info["description"]) > 0


class TestSwaggerRequestBodies:
    """Тесты тел запросов в спецификации."""

    def test_start_has_request_body(self) -> None:
        """Проверка тела запроса для /api/start."""
        start_path = SWAGGER_SPEC["paths"]["/api/start"]["post"]

        assert "requestBody" in start_path

    def test_schedule_post_has_request_body(self) -> None:
        """Проверка тела запроса для POST /api/schedule."""
        schedule_path = SWAGGER_SPEC["paths"]["/api/schedule"]["post"]

        assert "requestBody" in schedule_path

    def test_config_put_has_request_body(self) -> None:
        """Проверка тела запроса для PUT /api/config."""
        config_path = SWAGGER_SPEC["paths"]["/api/config"]["put"]

        assert "requestBody" in config_path

    def test_request_examples_are_valid_for_pydantic_schemas(self) -> None:
        """Проверка, что примеры requestBody проходят валидацию схем."""
        spec = get_swagger_spec()

        start_examples = spec["paths"]["/api/v1/start"]["post"]["requestBody"][
            "content"
        ]["application/json"]["examples"]
        for example in start_examples.values():
            StartRecordingRequest(**example["value"])

        schedule_examples = spec["paths"]["/api/v1/schedule"]["post"][
            "requestBody"
        ]["content"]["application/json"]["examples"]
        for example in schedule_examples.values():
            CreateScheduleRequest(**example["value"])

        update_schedule_examples = spec["paths"]["/api/v1/schedule/{task_id}"][
            "put"
        ]["requestBody"]["content"]["application/json"]["examples"]
        for example in update_schedule_examples.values():
            UpdateScheduleRequest(id="task_123", **example["value"])

        toggle_examples = spec["paths"]["/api/v1/schedule/{task_id}/toggle"][
            "post"
        ]["requestBody"]["content"]["application/json"]["examples"]
        for example in toggle_examples.values():
            ToggleScheduleRequest(**example["value"])

        config_examples = spec["paths"]["/api/v1/config"]["put"][
            "requestBody"
        ]["content"]["application/json"]["examples"]
        for example in config_examples.values():
            UpdateConfigRequest(**example["value"])


class TestVersionConsistency:
    """Тесты консистентности версии в runtime и документации."""

    def test_version_is_consistent_in_docs_and_swagger(self) -> None:
        """Проверяет версию в pyproject, README и swagger-спецификации."""
        expected_version = _load_version_from_pyproject()

        assert expected_version == "1.4.5"
        assert _load_version_from_readme() == expected_version
        assert SWAGGER_SPEC["info"]["version"] == expected_version
        assert (
            SWAGGER_SPEC["components"]["schemas"]["Health"]["properties"][
                "version"
            ]["example"]
            == expected_version
        )

    def test_runtime_health_and_swagger_use_project_version(self) -> None:
        """Проверяет версию в /health и /api/swagger.json."""
        expected_version = _load_version_from_pyproject()

        server = APIServer(
            host="127.0.0.1", port=5014, api_key="test-version-key"
        )
        server.set_callback(
            "status",
            MagicMock(
                return_value={
                    "is_recording": False,
                    "is_paused": False,
                    "elapsed_time": 0,
                    "current_file": None,
                }
            ),
        )
        register_routes(server.app, server)
        server.app.config["TESTING"] = True
        client = server.app.test_client()

        health_response = client.get("/health")
        swagger_response = client.get("/api/swagger.json")

        assert health_response.status_code == 200
        assert swagger_response.status_code == 200
        assert health_response.get_json()["version"] == expected_version
        assert (
            swagger_response.get_json()["info"]["version"] == expected_version
        )
