"""Тесты генератора OpenAPI из Pydantic-схем (#214).

Проверяют: соответствие сгенерированной спецификации golden-файлу
(переходный период), разрешимость всех $ref, полноту метаданных
для зарегистрированных маршрутов (расхождение модель↔маршрут —
падение теста) и валидность структуры OpenAPI 3.0.3.
"""

import json
from pathlib import Path
from typing import Any

from api.openapi import SWAGGER_SPEC, build_spec
from api.openapi_endpoints import ENDPOINTS

GOLDEN_PATH = Path(__file__).parent / "data" / "openapi_spec.json"

# Маршруты, у которых OpenAPI-описание отсутствует намеренно:
# служебные endpoints и ещё не задокументированные разделы API
# (техдолг документации, см. issue #214). Пути в OpenAPI-нотации.
UNDOCUMENTED_ROUTES: frozenset[str] = frozenset(
    {
        "/api/docs",
        "/api/swagger.json",
        "/static/{filename}",
        "/ws",
        # Легаси-алиасы v1-маршрутов: документируются версией /api/v1/*
        "/api/status",
        "/api/start",
        "/api/stop",
        "/api/pause",
        "/api/schedule",
        "/api/schedule/{task_id}",
        "/api/schedule/{task_id}/toggle",
        "/api/devices",
        "/api/windows",
        "/api/config",
        "/api/config/webhook",
        "/api/config/webhook/test",
        "/api/events/recent",
        "/api/events/stats",
        "/api/observability/metrics",
        "/api/observability/baseline",
        "/api/post-processing/config",
        "/api/post-processing/status",
        "/api/post-processing/run",
        "/api/recording/{recording_id}/post-processing",
        "/api/profiles",
        "/api/profiles/{profile_id}",
        "/api/profiles/{profile_id}/apply",
        "/api/updates/config",
        "/api/updates/check",
        "/api/updates/download",
        "/api/updates/apply",
        "/api/updates/status",
        "/api/recordings",
        "/api/recordings/verify",
        "/api/recordings/repair",
        "/api/recording/metrics",
        "/api/recording/finalization-status",
        # Ещё не задокументированные разделы API (техдолг #214):
        # plugins, library, cloud, multi-recording, resources
        "/api/v1/plugins",
        "/api/v1/plugins/{name}",
        "/api/v1/plugins/{name}/config",
        "/api/v1/plugins/{name}/enable",
        "/api/v1/plugins/{name}/disable",
        "/api/v1/library",
        "/api/v1/library/recording",
        "/api/v1/library/tags",
        "/api/v1/cloud/sync",
        "/api/v1/cloud/test",
        "/api/v1/cloud/status",
        "/api/v1/cloud/config",
        "/api/v1/config/webhook",
        "/api/v1/config/webhook/test",
        "/api/v1/metrics",
        "/api/v1/operations/{operation_id}",
        "/api/v1/profiles/import",
        "/api/v1/profiles/{profile_id}/export",
        "/api/v1/recording/start-multi",
        "/api/v1/recording/status-multi",
        "/api/v1/recording/stop-multi",
        "/api/v1/recording/switch-source",
        "/api/v1/recordings/repair",
        "/api/v1/recordings/verify",
        "/api/v1/resources/monitors",
        "/api/v1/resources/disk-space",
        "/api/v1/circuit-breakers",
    }
)


def _flask_to_openapi_path(rule: str) -> str:
    """Преобразует путь Flask (`<task_id>`) в OpenAPI (`{task_id}`)."""
    import re

    return re.sub(r"<(?:[^:<>]+:)?([^<>]+)>", r"{\1}", rule)


def _collect_app_paths() -> dict[str, set[str]]:
    """Собирает пути реального Flask-приложения с маршрутами API.

    Returns:
        Словарь «OpenAPI-путь -> множество методов».
    """
    from unittest.mock import MagicMock

    from api.routes import register_routes
    from api.server import APIServer

    server = APIServer(host="127.0.0.1", port=5099, api_key="test-openapi")
    server.set_callback("status", MagicMock(return_value={}))
    register_routes(server.app, server)

    paths: dict[str, set[str]] = {}
    for rule in server.app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = _flask_to_openapi_path(rule.rule)
        methods = {
            m.lower() for m in rule.methods if m not in {"HEAD", "OPTIONS"}
        }
        paths.setdefault(path, set()).update(methods)
    return paths


class TestGoldenSpec:
    """Golden-файл: зафиксированная сгенерированная схема."""

    def test_generated_spec_matches_golden(self) -> None:
        """Сгенерированная спецификация совпадает с golden-файлом.

        Версия подставляется из runtime — golden-файл переиспользуется
        между релизами, а версия проверяется отдельным тестом.
        """
        golden: dict[str, Any] = json.loads(
            GOLDEN_PATH.read_text(encoding="utf-8")
        )
        spec = build_spec()
        spec["info"]["version"] = golden["info"]["version"]

        assert spec == golden

    def test_spec_refs_resolve(self) -> None:
        """Все $ref указывают на существующие компоненты."""

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                ref = node.get("$ref")
                if isinstance(ref, str):
                    assert ref.startswith("#/components/schemas/"), ref
                    name = ref.rsplit("/", 1)[-1]
                    assert name in SWAGGER_SPEC["components"]["schemas"], ref
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(SWAGGER_SPEC)

    def test_every_operation_has_responses(self) -> None:
        """У каждой операции есть непустой словарь responses."""
        for path, ops in SWAGGER_SPEC["paths"].items():
            for method, operation in ops.items():
                assert operation.get("responses"), f"{method.upper()} {path}"


class TestEndpointCoverage:
    """Полнота метаданных относительно зарегистрированных маршрутов."""

    def test_all_documented_paths_exist_in_app(self) -> None:
        """Каждый задокументированный путь реально зарегистрирован.

        Расхождение в обратную сторону: операция есть в ENDPOINTS,
        но маршрут удалён/переименован — документация врёт.
        """
        app_paths = _collect_app_paths()
        for key in ENDPOINTS:
            _method, path = key.split(" ", 1)
            assert path in app_paths, (
                f"Задокументированный путь отсутствует в приложении: {path}"
            )

    def test_app_routes_have_openapi_metadata(self) -> None:
        """Каждый маршрут приложения задокументирован или в изключениях.

        Новый эндпоинт без метаданных ломает этот тест — расхождение
        модель↔маршрут всплывает сразу (issue #214).
        """
        app_paths = _collect_app_paths()
        documented = {key.split(" ", 1)[1] for key in ENDPOINTS}

        for path, methods in sorted(app_paths.items()):
            if path in UNDOCUMENTED_ROUTES:
                continue
            assert path in documented, (
                f"Маршрут без OpenAPI-метаданных: {path} ({sorted(methods)})"
            )
