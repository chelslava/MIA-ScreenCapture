# Миграция OpenAPI: рукописная схема → генерация из Pydantic (#214)

## Что было

`api/swagger.py` — 2069 строк рукописной OpenAPI-спецификации,
дублирующей Pydantic-схемы из `api/schemas.py` (1100 строк). Каждое
изменение контракта правилось в двух местах: в модели валидации и в
документации — с риском расхождений.

## Что стало

| Модуль | Строк | Роль |
|---|---|---|
| `api/openapi.py` | ~400 | Генератор: компоненты из Pydantic, пути из метаданных, конверсия в OpenAPI 3.0.3, Swagger UI |
| `api/openapi_endpoints.py` | ~970 | Декларативные метаданные 39 операций (summary/description/примеры/ответы), мигрированы из рукописной спеки без потерь |
| `api/response_schemas.py` | ~240 | Pydantic-модели компонентов ответов, не покрытых `schemas.py` |
| `api/swagger.py` | 13 | Shim обратной совместимости (импорты) |

Источник истины один: поле описывается в Pydantic-модели, из которой
одновременно работают валидация запроса и документация.

## Отличия сгенерированной схемы от рукописной

Структурно (пути, методы, коды ответов, имена `$ref`) — идентична,
кроме:

1. **`/api/v1/recording/{id}/post-processing` →
   `/api/v1/recording/{recording_id}/post-processing`** — рукописная
   спека использовала параметр `{id}`, тогда как реальный маршрут
   принимает `recording_id`. Дрейф документации поймал тест покрытия
   (`test_all_documented_paths_exist_in_app`) и исправлен.
2. **Новые компоненты** `StatusData`, `ConfigVideo`, `ConfigAudio`,
   `ConfigOutput` — вложенные модели, которые генератор поднимает из
   `$defs` в `components.schemas` по имени класса.
3. **Тела ответов компонентов теперь генерируются из моделей**:
   - `required` отражает реальную опциональность полей (например, у
     `Status` поля `success`/`data` стали обязательными; у
     `WebSocketStats` необязательные поля получили `nullable`);
   - `anyOf: [{...}, null]` Pydantic конвертируется в `nullable: true`
     (нотация OpenAPI 3.0.3);
   - числовые `exclusiveMinimum/exclusiveMaximum` → булевы
     `minimumExclusive/maximumExclusive`;
   - автогенерируемые `title` удаляются, `example` и `description`
     сохраняются;
   - вложенные тела `Error`/`ValidationError` инлайнятся (как в
     рукописной версии), остальные вложения — по `$ref`.

## Механика переходного периода

- **Golden-файл** `tests/unit/api/data/openapi_spec.json` —
  зафиксированный вывод генератора; тест сравнивает его со свежей
  генерацией (версия подставляется из runtime). Любое изменение
  контракта требует явного обновления golden-файла.
- **Тест покрытия** (`TestEndpointCoverage`): каждый маршрут
  приложения должен иметь метаданные в ENDPOINTS либо явно числиться
  в `UNDOCUMENTED_ROUTES`; каждая задокументированная операция —
  иметь реальный маршрут. Новый эндпоинт без документации ломает тест.
- **Резолв `$ref`** проверяется тестом: каждая ссылка указывает на
  существующий компонент.
- Примеры запросов валидируются Pydantic-моделями (тест перенесён из
  `test_swagger.py` без изменений).

## Остаток техдолга

Не задокументированы (перечислены в `UNDOCUMENTED_ROUTES`): plugins,
library, cloud, multi-recording, resources/monitors, disk-space,
circuit-breakers, operations, profiles import/export, recordings
verify/repair, webhook test, metrics. Каждый новый раздел API
документируется через ENDPOINTS + Pydantic-модель ответа.
