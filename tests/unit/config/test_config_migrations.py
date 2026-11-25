"""
Тесты миграций схемы config.json, backup и восстановления (#190)
================================================================

Проверяет инвариант issue #190: настройки пользователя не теряются
молча — миграции версий схемы, backup перед каждой записью,
восстановление из backup при повреждении и уведомления пользователю.
"""

import json
from pathlib import Path
from typing import Any

import pytest

import config_migrations
from config import (
    KIND_MIGRATED,
    KIND_RESET_CORRUPTED,
    KIND_RESTORED_FROM_BACKUP,
    AppSettings,
    ConfigManager,
)
from config_migrations import (
    CONFIG_MIGRATIONS,
    CURRENT_SCHEMA_VERSION,
    LEGACY_SCHEMA_VERSION,
    MigrationResult,
    detect_schema_version,
    migrate_config_data,
    parse_config_file,
)

#: Значение «версии из будущего» для тестов forward-совместимости
FUTURE_SCHEMA_VERSION: int = CURRENT_SCHEMA_VERSION + 99

# Реалистичный конфиг эпохи v1 (до v1.9.0): без schema_version,
# со значениями, которые встречались в реальных установках
LEGACY_V1_CONFIG: dict[str, Any] = {
    "video": {
        "fps": 60,
        "codec": "libx264",
        "bitrate": "2M",
        "format": "mp4",
        "preset": "medium",
    },
    "audio": {"record_mic": True, "sample_rate": 44100},
    "capture": {
        "area_type": "rect",
        "rect_coords": [10, 20, 800, 600],
    },
    "output": {"default_path": "D:\\Записи", "filename_template": "rec"},
    "language": " RU",
    "theme": "dark",
    "recent_recordings": [
        {"path": "D:\\Записи\\demo.mp4", "date": "2026-01-01", "size": 123}
    ],
}


def _write_config(path: Path, data: dict[str, Any]) -> None:
    """Записывает словарь данных в JSON-файл конфигурации."""
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class TestDetectSchemaVersion:
    """Тесты определения версии схемы."""

    @pytest.mark.parametrize(
        "raw,expected",
        [
            (None, LEGACY_SCHEMA_VERSION),
            (1, 1),
            (2, 2),
            (True, LEGACY_SCHEMA_VERSION),
            (0, LEGACY_SCHEMA_VERSION),
            (-5, LEGACY_SCHEMA_VERSION),
            ("2", LEGACY_SCHEMA_VERSION),
            (2.0, LEGACY_SCHEMA_VERSION),
        ],
    )
    def test_version_variants(self, raw: Any, expected: int) -> None:
        """Битые типы/значения версии трактованы как legacy."""
        assert detect_schema_version({"schema_version": raw}) == expected

    def test_missing_field_is_legacy(self) -> None:
        """Конфиг без schema_version — это v1 (до v1.9.0)."""
        assert detect_schema_version({}) == LEGACY_SCHEMA_VERSION


class TestMigrateConfigData:
    """Тесты цепочки миграций."""

    def test_v1_fixture_migrated_to_current(self) -> None:
        """Фикстура старого конфига поднимается до текущей версии."""
        result = migrate_config_data(LEGACY_V1_CONFIG)

        assert isinstance(result, MigrationResult)
        assert result.from_version == LEGACY_SCHEMA_VERSION
        assert result.to_version == CURRENT_SCHEMA_VERSION
        assert result.data["schema_version"] == CURRENT_SCHEMA_VERSION
        assert result.notes, "шаги миграции должны попадать в notes"

    def test_migration_preserves_user_data(self) -> None:
        """Миграция не теряет пользовательские настройки и кириллицу."""
        result = migrate_config_data(LEGACY_V1_CONFIG)
        data = result.data

        assert data["video"]["fps"] == 60
        assert data["capture"]["rect_coords"] == [10, 20, 800, 600]
        assert data["output"]["default_path"] == "D:\\Записи"
        assert data["recent_recordings"][0]["path"] == "D:\\Записи\\demo.mp4"

    def test_migration_normalizes_language(self) -> None:
        """Legacy-значение language нормализуется явно."""
        result = migrate_config_data(LEGACY_V1_CONFIG)

        assert result.data["language"] == "ru"

    def test_migration_does_not_mutate_input(self) -> None:
        """Входные данные не мутируются (глубокая копия)."""
        original = json.dumps(LEGACY_V1_CONFIG, ensure_ascii=False)
        migrate_config_data(LEGACY_V1_CONFIG)

        assert json.dumps(LEGACY_V1_CONFIG, ensure_ascii=False) == original

    def test_current_version_config_untouched(self) -> None:
        """Конфиг актуальной версии не мигрируется и без notes."""
        data = dict(LEGACY_V1_CONFIG, schema_version=CURRENT_SCHEMA_VERSION)
        result = migrate_config_data(data)

        assert result.from_version == CURRENT_SCHEMA_VERSION
        assert result.to_version == CURRENT_SCHEMA_VERSION
        assert result.notes == []

    def test_future_version_untouched(self) -> None:
        """Схема новее поддерживаемой не переписывается старой."""
        future = dict(LEGACY_V1_CONFIG, schema_version=FUTURE_SCHEMA_VERSION)
        result = migrate_config_data(future)

        assert result.to_version == FUTURE_SCHEMA_VERSION
        assert result.data["schema_version"] == FUTURE_SCHEMA_VERSION
        assert result.notes == []

    def test_migration_chain_applies_stepwise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Цепочка применяет каждую миграцию последовательно."""
        calls: list[int] = []

        def _fake_v2_to_v3(data: dict[str, Any]) -> dict[str, Any]:
            """Тестовая миграция v2 -> v3."""
            calls.append(2)
            data["schema_version"] = 3
            return data

        monkeypatch.setitem(CONFIG_MIGRATIONS, 2, _fake_v2_to_v3)
        monkeypatch.setattr(config_migrations, "CURRENT_SCHEMA_VERSION", 3)
        # config.py импортировал константу по значению — для чистоты
        # теста вызываем миграции напрямую через config_migrations
        result = config_migrations.migrate_config_data(
            {"schema_version": 1, "video": {"fps": 30}}
        )

        assert result.to_version == 3
        assert calls == [2]
        assert len(result.notes) == 2
        assert "1 -> 2" in result.notes[0]
        assert "2 -> 3" in result.notes[1]

    def test_missing_migration_stops_chain(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Дыра в реестре миграций останавливает цепочку без потерь."""
        monkeypatch.delitem(CONFIG_MIGRATIONS, LEGACY_SCHEMA_VERSION)
        result = migrate_config_data({"schema_version": 1})

        assert result.to_version == LEGACY_SCHEMA_VERSION
        assert result.notes == []


class TestParseConfigFile:
    """Тесты разбора JSON-файла конфигурации."""

    def test_parses_object(self, temp_dir: Path) -> None:
        """Корректный JSON-объект разбирается в словарь."""
        path = temp_dir / "config.json"
        _write_config(path, {"video": {"fps": 30}})

        assert parse_config_file(path) == {"video": {"fps": 30}}

    def test_cyrillic_content(self, temp_dir: Path) -> None:
        """Кириллица (UTF-8) читается без потерь."""
        path = temp_dir / "config.json"
        _write_config(path, {"output": {"default_path": "D:\\Экран"}})

        assert parse_config_file(path)["output"]["default_path"] == (
            "D:\\Экран"
        )

    def test_invalid_json_raises(self, temp_dir: Path) -> None:
        """Битый JSON вызывает исключение (не молчаливый сброс)."""
        path = temp_dir / "config.json"
        path.write_text("{битый", encoding="utf-8")

        with pytest.raises(ValueError):
            parse_config_file(path)

    def test_non_object_json_raises(self, temp_dir: Path) -> None:
        """JSON не-объект (например, список) отклоняется."""
        path = temp_dir / "config.json"
        path.write_text("[1, 2, 3]", encoding="utf-8")

        with pytest.raises(ValueError):
            parse_config_file(path)


class TestConfigManagerSchemaVersion:
    """Тесты schema_version в ConfigManager."""

    def test_load_migrates_legacy_config(self, temp_dir: Path) -> None:
        """Старый конфиг v1 мигрирует и сохраняется с новой версией."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)

        manager = ConfigManager(path)

        assert manager.settings.schema_version == CURRENT_SCHEMA_VERSION
        saved = parse_config_file(path)
        assert saved["schema_version"] == CURRENT_SCHEMA_VERSION
        # Пользовательские настройки пережили миграцию
        assert manager.settings.video.fps == 60

    def test_migration_notice_published(self, temp_dir: Path) -> None:
        """Миграция публикует уведомление ровно один раз."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)

        notice = manager.pop_load_notice()
        assert notice is not None
        assert notice.kind == KIND_MIGRATED
        assert manager.pop_load_notice() is None

    def test_actual_config_no_notice(self, temp_dir: Path) -> None:
        """Актуальный конфиг загружается без уведомлений."""
        path = temp_dir / "config.json"
        _write_config(
            path, dict(LEGACY_V1_CONFIG, schema_version=CURRENT_SCHEMA_VERSION)
        )
        manager = ConfigManager(path)

        assert manager.settings.schema_version == CURRENT_SCHEMA_VERSION
        assert manager.pop_load_notice() is None

    def test_future_version_loads_and_restamps_on_save(
        self, temp_dir: Path
    ) -> None:
        """Конфиг из будущего загружается как есть, но при записи
        получает текущую версию схемы."""
        path = temp_dir / "config.json"
        _write_config(
            path,
            dict(LEGACY_V1_CONFIG, schema_version=FUTURE_SCHEMA_VERSION),
        )
        manager = ConfigManager(path)
        manager.save()

        assert parse_config_file(path)["schema_version"] == (
            CURRENT_SCHEMA_VERSION
        )


class TestConfigBackup:
    """Тесты backup-механики перед записью."""

    def test_save_creates_backup(self, temp_dir: Path) -> None:
        """Каждая запись создаёт/обновляет config.json.bak."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.settings.video.fps = 90

        assert manager.save() is True
        backup = parse_config_file(manager.backup_path)
        # В backup — содержимое ДО записи (мигрированный конфиг с fps=60)
        assert backup["video"]["fps"] == 60

    def test_backup_preserves_cyrillic(self, temp_dir: Path) -> None:
        """Backup сохраняет кириллицу без \\u-экранирования."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.save()

        raw = manager.backup_path.read_text(encoding="utf-8")
        assert "Записи" in raw
        # ensure_ascii=False: кириллица не превращается в \uXXXX
        assert "\\u0417" not in raw

    def test_corrupt_main_not_copied_to_backup(self, temp_dir: Path) -> None:
        """Битый основной файл не затирает валидный backup."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.save()
        good_backup = manager.backup_path.read_text(encoding="utf-8")

        # Внешнее повреждение основного файла между запусками
        path.write_text("{повреждено", encoding="utf-8")
        manager2 = ConfigManager(path)
        manager2.save()

        assert manager2.backup_path.read_text(encoding="utf-8") == (
            good_backup
        )


class TestConfigRestoreFromBackup:
    """Тесты восстановления конфига из backup (#190)."""

    def test_corrupted_main_restored_from_backup(self, temp_dir: Path) -> None:
        """Битый main восстанавливается из .bak, данные не теряются."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.save()

        path.write_text("{повреждено", encoding="utf-8")
        manager2 = ConfigManager(path)

        notice = manager2.pop_load_notice()
        assert notice is not None
        assert notice.kind == KIND_RESTORED_FROM_BACKUP
        assert manager2.settings.video.fps == 60
        # Основной файл перезаписан валидным содержимым
        assert parse_config_file(path)["video"]["fps"] == 60

    def test_corrupt_copy_saved(self, temp_dir: Path) -> None:
        """Повреждённый файл сохраняется как .corrupt-<метка времени>."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.save()

        path.write_text("{повреждено", encoding="utf-8")
        ConfigManager(path)

        corrupt_copies = list(temp_dir.glob("config.json.corrupt-*"))
        assert len(corrupt_copies) == 1
        # Исходное (битое) содержимое сохранено для анализа
        assert "повреждено" in (corrupt_copies[0].read_text(encoding="utf-8"))

    def test_notice_message_mentions_paths(self, temp_dir: Path) -> None:
        """Уведомление содержит имена backup и битой копии."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.save()

        path.write_text("{повреждено", encoding="utf-8")
        manager2 = ConfigManager(path)
        notice = manager2.pop_load_notice()

        assert notice is not None
        assert "config.json.bak" in notice.message
        assert "config.json.corrupt-" in notice.message

    def test_corrupt_main_and_backup_resets_to_defaults(
        self, temp_dir: Path
    ) -> None:
        """Битые main и backup — сброс к дефолтам с уведомлением."""
        path = temp_dir / "config.json"
        path.write_text("{повреждено", encoding="utf-8")
        (temp_dir / "config.json.bak").write_text(
            "{тоже повреждено", encoding="utf-8"
        )

        manager = ConfigManager(path)

        notice = manager.pop_load_notice()
        assert notice is not None
        assert notice.kind == KIND_RESET_CORRUPTED
        assert manager.settings == AppSettings()
        assert list(temp_dir.glob("config.json.corrupt-*"))

    def test_empty_file_treated_as_corrupted(self, temp_dir: Path) -> None:
        """Пустой файл — это повреждение (раньше терялся молча)."""
        path = temp_dir / "config.json"
        path.write_text("", encoding="utf-8")

        manager = ConfigManager(path)

        notice = manager.pop_load_notice()
        assert notice is not None
        assert notice.kind == KIND_RESET_CORRUPTED

    def test_corrupted_main_without_backup_resets(
        self, temp_dir: Path
    ) -> None:
        """Битый main без backup — сброс, но копия сохраняется."""
        path = temp_dir / "config.json"
        path.write_text("{повреждено", encoding="utf-8")

        manager = ConfigManager(path)

        notice = manager.pop_load_notice()
        assert notice is not None
        assert notice.kind == KIND_RESET_CORRUPTED
        assert manager.settings.video.fps == 30
        assert list(temp_dir.glob("config.json.corrupt-*"))

    def test_invalid_schema_falls_back_to_backup(self, temp_dir: Path) -> None:
        """Валидный JSON с невалидной схемой восстанавливается из .bak."""
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)
        manager.save()

        # JSON корректен, но схема ломает Pydantic-валидацию
        _write_config(path, dict(LEGACY_V1_CONFIG, theme="несуществующая"))
        manager2 = ConfigManager(path)

        notice = manager2.pop_load_notice()
        assert notice is not None
        assert notice.kind == KIND_RESTORED_FROM_BACKUP
        assert manager2.settings.theme == "dark"
        # Усиленный guard: восстановление не затёрло валидный .bak
        assert parse_config_file(manager2.backup_path)["theme"] == "dark"


class TestNotifyConfigLoadNotice:
    """Тесты доведения события загрузки конфига до пользователя."""

    def test_notice_logged_and_notified(
        self,
        temp_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Событие из ConfigManager доходит до системного toast и лога."""
        from main import notify_config_load_notice

        shown: list[tuple[str, str]] = []

        def _fake_send(title: str, message: str) -> bool:
            """Перехват системного уведомления."""
            shown.append((title, message))
            return True

        monkeypatch.setattr("gui.notifications.send_notification", _fake_send)
        path = temp_dir / "config.json"
        _write_config(path, LEGACY_V1_CONFIG)
        manager = ConfigManager(path)

        notify_config_load_notice(manager)

        assert len(shown) == 1
        assert shown[0][0] == "MIA-ScreenCapture"
        assert "схемы" in shown[0][1]
        assert any("конфигурации" in r.message.lower() for r in caplog.records)

    def test_no_notice_is_silent(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Без событий загрузки уведомления не отправляются."""
        from main import notify_config_load_notice

        shown: list[tuple[str, str]] = []

        def _fake_send(title: str, message: str) -> bool:
            """Перехват системного уведомления."""
            shown.append((title, message))
            return True

        monkeypatch.setattr("gui.notifications.send_notification", _fake_send)
        path = temp_dir / "config.json"
        _write_config(
            path, dict(LEGACY_V1_CONFIG, schema_version=CURRENT_SCHEMA_VERSION)
        )

        notify_config_load_notice(ConfigManager(path))

        assert shown == []

    def test_missing_pop_method_is_safe(self) -> None:
        """Объект без pop_load_notice не роняет точку входа."""
        from main import notify_config_load_notice

        # Не должно выбрасывать исключений
        notify_config_load_notice(object())


class TestConfirmPendingUpdateEntrypoint:
    """Тесты health-check обновления на старте приложения (#191)."""

    @staticmethod
    def _capture_send(
        monkeypatch: pytest.MonkeyPatch,
    ) -> list[tuple[str, str]]:
        """Ставит перехватчик системного уведомления."""
        shown: list[tuple[str, str]] = []

        def _fake_send(title: str, message: str) -> bool:
            """Перехват системного уведомления."""
            shown.append((title, message))
            return True

        monkeypatch.setattr("gui.notifications.send_notification", _fake_send)
        return shown

    def test_confirmed_update_notifies(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Маркер обновления подтверждается с toast и чисткой backup."""
        from core.updater.rollback import (
            UpdateState,
            read_update_state,
            write_update_state,
        )
        from main import confirm_pending_update

        shown = self._capture_send(monkeypatch)
        backup = temp_dir / "app.backup-1"
        backup.mkdir()
        write_update_state(
            temp_dir, UpdateState(version="2.1.0", backup_dir=str(backup))
        )

        confirm_pending_update(temp_dir)

        assert len(shown) == 1
        assert "2.1.0" in shown[0][1]
        assert read_update_state(temp_dir) is None
        assert not backup.exists()

    def test_rollback_notice_notifies(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Маркер отката от установщика доходит до пользователя."""
        from core.updater.rollback import UPDATE_ROLLBACK_FILENAME
        from main import confirm_pending_update

        shown = self._capture_send(monkeypatch)
        (temp_dir / UPDATE_ROLLBACK_FILENAME).write_text(
            json.dumps(
                {"reason": "распаковка: битый архив", "version": "2.1.0"},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        confirm_pending_update(temp_dir)

        assert len(shown) == 1
        assert "отменено" in shown[0][1]
        assert "битый архив" in shown[0][1]
        # Маркер одноразовый: повторный старт молчит
        confirm_pending_update(temp_dir)
        assert len(shown) == 1

    def test_no_markers_is_silent(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Без маркеров обновления старт не уведомляет."""
        from main import confirm_pending_update

        shown = self._capture_send(monkeypatch)

        confirm_pending_update(temp_dir)

        assert shown == []

    def test_notification_failure_is_tolerated(
        self, temp_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Отказ toast не роняет старт приложения."""
        from core.updater.rollback import (
            UpdateState,
            write_update_state,
        )
        from main import confirm_pending_update

        def _broken_send(title: str, message: str) -> bool:
            """Имитация отказа системы уведомлений."""
            raise RuntimeError("toast недоступен")

        monkeypatch.setattr(
            "gui.notifications.send_notification", _broken_send
        )
        write_update_state(
            temp_dir,
            UpdateState(version="2.1.0", backup_dir=str(temp_dir / "b")),
        )

        # Не должно выбрасывать исключений
        confirm_pending_update(temp_dir)
