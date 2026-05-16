<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# api/

## Purpose
REST API слой на базе Flask для удалённого управления рекордером. Сервер работает в отдельном потоке (Waitress WSGI), чтобы не блокировать GUI. Реализует аутентификацию по API-ключу, rate limiting, идемпотентность, WebSocket для Server-Sent Events и Swagger-документацию.

## Key Files

| Файл | Описание |
|------|----------|
| `server.py` | Flask-приложение, Waitress WSGI, CORS, регистрация blueprints, запуск/остановка сервера |
| `routes.py` | Главный blueprint, агрегирует все маршруты |
| `routes_recording.py` | Маршруты управления записью (`/api/v1/recording/*`) |
| `routes_schedule.py` | Маршруты планировщика (`/api/v1/schedule/*`) |
| `routes_config.py` | Маршруты конфигурации (`/api/v1/config/*`) |
| `routes_resources.py` | Маршруты ресурсов: мониторы, окна, кодеки (`/api/v1/resources/*`) |
| `auth.py` | Аутентификация по API-ключу (`X-API-Key` / `Authorization: Bearer`) |
| `schemas.py` | Pydantic-схемы для валидации запросов и ответов |
| `runtime_models.py` | Датаклассы `APIOperation`, `IdempotencyBeginResult` для runtime состояния |
| `websocket.py` | WebSocket / SSE endpoint для стриминга событий |
| `websocket_transport.py` | Транспортный адаптер WebSocket → EventBus |
| `request_lifecycle.py` | Before/after request хуки: логирование, request-id, rate limit |
| `request_context.py` | Thread-local контекст запроса (request_id, timing) |
| `rate_limiter.py` | Rate limiter на основе sliding window |
| `error_mapping.py` | Маппинг доменных исключений → HTTP-коды ошибок |
| `operation_store.py` | In-memory хранилище текущих операций (concurrent protection) |
| `idempotency_store.py` | Хранилище ключей идемпотентности (`Idempotency-Key` header) |
| `observability.py` | Метрики сервера: счётчики запросов, latency, статус |
| `swagger.py` | Swagger/OpenAPI 3.0 документация (`/api/docs`) |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Все публичные ответы формируй через `jsonify({"success": True, "data": ...})` (успех) или `_error_response(code, "type", "message")` (ошибка).
- Новые маршруты добавляй в соответствующий `routes_*.py` файл и регистрируй blueprint в `routes.py`.
- Валидацию входных данных делай через Pydantic-схемы из `schemas.py`.
- При изменении маршрутов обновляй `swagger.py`.
- Не вызывай бизнес-логику напрямую — только через `ApplicationFacade` (передаётся при инициализации сервера).
- Idempotency-Key обрабатывается в `request_lifecycle.py` — не дублируй в маршрутах.

### Testing Requirements
- Тесты API: `tests/unit/test_api_*.py`, `tests/integration/test_api*.py`
- Integration тесты: `tests/integration/test_api.py`, `test_api_extended.py`, `test_api_error_handling.py`
- Запуск: `uv run pytest tests/unit/test_api_server.py tests/integration/test_api.py`

### Common Patterns
```python
# Стандартный успешный ответ
return jsonify({"success": True, "data": result}), 200

# Ошибка через _error_response
return _error_response(400, "validation_error", "Invalid fps", details=[...])

# Защита маршрута API-ключом
@require_api_key
def my_route():
    ...
```

## Dependencies

### Internal
- `core/application_facade.py` — все команды идут через `ApplicationFacade`
- `core/event_bus.py` — подписка WebSocket на доменные события
- `config.py` — настройки порта, API-ключа, CORS
- `exceptions.py` — доменные исключения для маппинга в HTTP

### External
- `flask` — веб-фреймворк
- `waitress` — production WSGI сервер
- `flask-cors` — CORS middleware
- `pydantic` — валидация схем
- `werkzeug` — HTTP утилиты

<!-- MANUAL: -->
