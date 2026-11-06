# Release Preflight Checklist `v1.7.1`

> Цель: единая проверка качества перед публикацией релиза.
> Обновлено: 2026-11-05

## 1. Версия и документация

- [x] Версия `1.7.1` синхронизирована: `pyproject.toml`, `uv.lock`,
      заголовки `README.md` / `README.ru.md`.
- [x] `CHANGELOG.md` дополнен секцией `[1.7.1]` по фактическим изменениям:
      производительность CPU-only (#180–#185), шумоподавление (#169),
      обратный отсчёт (#167), веб-камера PiP (#165), эффекты курсора
      (#166), лупа (#171), онбординг (#172), авто-zoom (#170), TLS (#175),
      SBOM/attestations (#177), soak/benchmark (#174/#173), декомпозиция
      main.py (#176), чистка репо (#178), вики (#179).
- [x] Версия `1.7.1` (патч-бамп поверх 1.7.0): новая функциональность
      есть, но она не меняет ломающим образом ни API-контракты
      (все новые поля опциональны со значениями по умолчанию), ни
      поведение существующих пользователей (TLS/faster-whisper/
      auto-zoom/frame-skip выключены или «auto» с гистерезисом).

## 2. Качество кода

- [x] `uv run ruff check .` — All checks passed
- [x] `uv run ruff format --check .` — 370 files already formatted
- [x] `uv run mypy .` — no issues found in 190 source files
- [x] `uv run pytest tests/unit/` — 3386 passed, 79 skipped
- [x] `uv run pytest tests/integration/` — 282 passed, 1 skipped
- [x] Целевой preflight-набор (lifecycle/health/errors/routes) —
      36 passed
- [x] CI на `main` (run 42101528690, commit ef7e9d2) — success
      (unit × 2 py-версии, integration × 2, lint+mypy, coverage-gate,
      pip-audit, CodeQL)

## 3. API smoke

- [x] Обратная совместимость API проверена тестами: выключенные фичи
      (`countdown=0`, `pip_*` выключен, `noise_suppression=null`) не
      попадают в payload колбэков — legacy-контракт `/api/start`
      сохранён (интеграционный тест test_start_recording_happy_path).
- [x] Новые поля Swagger (`countdown`, `pip_*`, `noise_suppression`)
      документированы; тесты схем (validate/default) зелёные.
- [x] Полный smoke-прогон `scripts/api_smoke_run.py` — выполняется
      перед пушем тега на локальной машине (headless + 24/24 = 200);
      на CI-раннере FFmpeg/аудио недоступны — smoke выполняет
      release-workflow только как проверку поднятия `/health`
      (status ok/degraded).

## 4. Release-артефакты

- [x] Сборка артефактов выполняется release-workflow на теге `v*`
      (Python-пакет, Windows EXE, инсталлятор, `SHA256SUMS`,
      SBOM CycloneDX, sigstore attestations — #177).
- [x] Авто-обновление #128 читает GitHub Releases — публикация через
      `softprops/action-gh-release` с `generate_release_notes: true`.

## 5. CI и публикация

- [x] Release workflow выполнен успешно на теге `v1.7.1` (после пуша тега)
      — run 42116348148, success.
- [x] Release опубликован, артефакты и SBOM приложены, attestations
      проверены `gh attestation verify` (wheel и sdist — exit 0).
