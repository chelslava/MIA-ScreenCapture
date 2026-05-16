<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# tests/integration/

## Purpose
Интеграционные тесты с реальными компонентами. Тестируют взаимодействие API сервера, Flask маршрутов, аутентификации и жизненного цикла сервера. Запускают реальный Flask тестовый клиент без моков HTTP-слоя.

## Key Files

| Файл | Описание |
|------|----------|
| `test_api.py` | Базовые интеграционные тесты REST API endpoint'ов |
| `test_api_extended.py` | Расширенные сценарии API: edge cases, concurrent requests |
| `test_api_error_handling.py` | Тесты обработки ошибок и HTTP статус-кодов |
| `test_api_contract_snapshots.py` | Snapshot-тесты контракта API (структура ответов) |
| `test_api_health_metrics.py` | Тесты `/health` и `/api/v1/observability` endpoint'ов |
| `test_api_recording_routes.py` | Тесты маршрутов записи с реальным Flask клиентом |
| `test_api_server_lifecycle.py` | Тесты жизненного цикла сервера: запуск, остановка, рестарт |
| `test_full_workflow.py` | End-to-end сценарий: старт → запись → стоп |
| `test_recording_flow.py` | Интеграция компонентов записи |
| `test_scheduler_integration.py` | Интеграционные тесты планировщика с реальным APScheduler |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Интеграционные тесты медленнее unit-тестов — запускай их отдельно в CI.
- Используй Flask `app.test_client()` для тестирования API без реального HTTP.
- `test_api_contract_snapshots.py` — при изменении структуры ответа API обновляй snapshots.
- `test_full_workflow.py` — самый полный тест; если он падает, значит сломана интеграция.
- Не мокируй Flask/HTTP слой — только внешние зависимости (файловую систему, аудио, экран).

### Testing Requirements
```bash
# Все интеграционные тесты
uv run pytest tests/integration/ -v

# Конкретный сценарий
uv run pytest tests/integration/test_api.py -v

# Только быстрые интеграционные
uv run pytest tests/integration/ -m "not slow"
```

### Common Patterns
```python
@pytest.fixture
def client(app):
    return app.test_client()

class TestApiIntegration:
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
```

## Dependencies

### Internal
- `conftest.py` в `tests/` — общие фикстуры
- `api/server.py` — реальный Flask app
- `core/` — реальные доменные сервисы

### External
- `pytest`, `flask` (test client)

<!-- MANUAL: -->
