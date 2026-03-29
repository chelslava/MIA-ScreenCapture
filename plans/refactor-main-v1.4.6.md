# План Декомпозиции `VideoRecorderApp` (`v1.4.6`)

> Дата: 2026-03-29  
> Цель: поэтапно убрать «god class» в `main.py` без поведенческих регрессий

## PR1: API Runtime (низкий риск)

- Вынести в `ApiRuntimeManager`:
  `_get_api_headers`, `_sync_api_key_env`, `_get_effective_api_key`,
  `_start_api_server`, `_get_api_runtime_settings`, `_get_api_status`,
  `_apply_api_settings`, `_stop_api_server`, `_restart_api_server`,
  `_open_api_logs_folder`, `get_api_controls`, `_setup_api_callbacks`.
- Сохранить `VideoRecorderApp` как фасад с делегированием.
- Закрепить тесты:
  `tests/unit/test_main_api_runtime.py` + проверка полной регистрации callbacks.

## PR2: Recording Orchestration (средний риск)

- Вынести в `RecordingRuntimeManager`:
  `_run_on_gui_thread`, `_get_status`, `_start_recording`,
  `_stop_recording`, `_toggle_pause`, `_get_recordings`,
  `_execute_scheduled_task`.
- Явно разделить адаптеры GUI и headless.
- Добавить тесты на timeout/fallback сценарии `stop`.

## PR3: Lifecycle + Scheduler + GUI bootstrap (средний риск)

- Вынести:
  `_run_gui`, hotkeys setup, scheduler CRUD callbacks, shutdown/cleanup.
- Ввести `ApplicationLifecycle` и `SchedulerFacade`.
- Добавить characterization-тесты на close/shutdown order.

## Критерии Готовности

- Для каждого PR:
  - все старые тесты зелёные;
  - добавлены characterization-тесты на вынесенный блок;
  - нет изменения публичных контрактов API/CLI.
- Для финала:
  - `main.py` заметно уменьшен;
  - ответственность класса `VideoRecorderApp` ограничена orchestration.
