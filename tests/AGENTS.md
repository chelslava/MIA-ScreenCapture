<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# tests/

## Purpose
Тестовая инфраструктура проекта. Содержит unit-тесты (с мокированием зависимостей) и интеграционные тесты (реальные компоненты). Общие фикстуры в `conftest.py`, включая мок PyQt6 для headless тестирования.

## Key Files

| Файл | Описание |
|------|----------|
| `conftest.py` | Общие pytest-фикстуры: `temp_dir`, `mock_config_manager`, мок PyQt6 |

## Subdirectories

| Директория | Назначение |
|-----------|---------|
| `unit/` | 65+ unit-тестов с моками внешних зависимостей (см. `unit/AGENTS.md`) |
| `integration/` | 10 интеграционных тестов с реальными компонентами (см. `integration/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Используй фикстуры из `conftest.py` вместо дублирования setup-логики.
- PyQt6 мокируется глобально в `conftest.py` — не импортируй реальный PyQt6 в unit-тестах.
- Имена тестовых классов: `Test<FeatureName>`.
- Имена тестовых методов: `test_<описание>`.
- Параметризацию делай через `@pytest.mark.parametrize`.
- Для моков используй `pytest-mock` (`mocker` фикстура).

### Testing Requirements
```bash
# Все тесты
uv run pytest

# Только unit
uv run pytest tests/unit/

# Только интеграционные
uv run pytest tests/integration/

# С покрытием
uv run pytest --cov=. --cov-report=html

# Конкретный файл
uv run pytest tests/unit/test_config.py -v
```

### Common Patterns
```python
import pytest

class TestMyFeature:
    def test_happy_path(self, mock_config_manager):
        # arrange
        ...
        # act
        result = my_func()
        # assert
        assert result == expected

    @pytest.mark.parametrize("input,expected", [
        (1, "one"),
        (2, "two"),
    ])
    def test_parametrized(self, input, expected):
        assert format_number(input) == expected
```

## Dependencies

### Internal
- Все модули проекта через фикстуры и моки

### External
- `pytest` — тестовый фреймворк
- `pytest-mock` — `mocker` фикстура
- `pytest-cov` — покрытие кода
- `pytest-qt` — тесты PyQt6 виджетов (если используется)

<!-- MANUAL: -->
