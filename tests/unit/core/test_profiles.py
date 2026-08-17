"""
Unit-тесты для модуля профилей записи (core/profiles.py)
"""

from __future__ import annotations

from pathlib import Path

from config import (
    AudioSettings,
    CaptureSettings,
    ConfigManager,
    VideoSettings,
)
from core.profiles import (
    ProfileStorage,
    RecordingProfile,
    get_profile_storage,
    set_profile_storage,
)


class TestRecordingProfile:
    """Тесты модели RecordingProfile."""

    def test_default_creation(self) -> None:
        profile = RecordingProfile(id="test_id", name="Тест")
        assert profile.id == "test_id"
        assert profile.name == "Тест"
        assert profile.icon == "⚙️"
        assert profile.is_default is False
        assert profile.is_builtin is False
        assert isinstance(profile.video, VideoSettings)
        assert isinstance(profile.audio, AudioSettings)
        assert isinstance(profile.capture, CaptureSettings)

    def test_to_and_from_dict(self) -> None:
        orig = RecordingProfile(
            id="p1",
            name="Профиль 1",
            description="Описание",
            icon="🎮",
            video=VideoSettings(fps=60, codec="libx264", bitrate="8M"),
            audio=AudioSettings(record_mic=False, record_system=True),
            capture=CaptureSettings(
                area_type="window", window_title="App Window"
            ),
            is_default=True,
            is_builtin=False,
        )
        data = orig.to_dict()
        assert data["id"] == "p1"
        assert data["name"] == "Профиль 1"
        assert data["icon"] == "🎮"
        assert data["video"]["fps"] == 60
        assert data["audio"]["record_system"] is True
        assert data["capture"]["window_title"] == "App Window"

        restored = RecordingProfile.from_dict(data)
        assert restored.id == orig.id
        assert restored.name == orig.name
        assert restored.video.fps == 60
        assert restored.audio.record_system is True
        assert restored.capture.window_title == "App Window"
        assert restored.is_default is True


class TestProfileStorage:
    """Тесты хранилища ProfileStorage."""

    def test_init_creates_builtin_profiles(self, tmp_path: Path) -> None:
        storage_file = tmp_path / "profiles.json"
        storage = ProfileStorage(storage_path=storage_file)

        profiles = storage.list_profiles()
        assert len(profiles) >= 3
        ids = [p.id for p in profiles]
        assert "default" in ids
        assert "gaming" in ids
        assert "presentation" in ids
        assert any(p.is_default for p in profiles)
        assert storage_file.exists()

    def test_get_profile(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        default_prof = storage.get_profile("default")
        assert default_prof is not None
        assert default_prof.name == "Стандартный"
        assert default_prof.is_builtin is True

        missing = storage.get_profile("non_existent")
        assert missing is None

    def test_create_and_update_profile(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        created = storage.create_profile(
            name="Кастомный 4K",
            description="Запись в 4K",
            icon="🎬",
            video=VideoSettings(fps=60, bitrate="16M"),
        )
        assert created.id in [p.id for p in storage.list_profiles()]
        assert created.name == "Кастомный 4K"
        assert created.video.fps == 60
        assert created.is_builtin is False

        # Обновление
        updated = storage.update_profile(
            profile_id=created.id,
            name="Кастомный 4K Ultra",
            video=VideoSettings(fps=120, bitrate="20M"),
        )
        assert updated is not None
        assert updated.name == "Кастомный 4K Ultra"
        assert updated.video.fps == 120

        # Обновление несуществующего
        missing = storage.update_profile(profile_id="missing_id", name="Test")
        assert missing is None

    def test_delete_profile(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        created = storage.create_profile(name="Временный")

        # Удаление пользовательского профиля
        success, error = storage.delete_profile(created.id)
        assert success is True
        assert error is None
        assert storage.get_profile(created.id) is None

        # Запрет удаления встроенного системного профиля
        success, error = storage.delete_profile("default")
        assert success is False
        assert error is not None
        assert "Нельзя удалить встроенный" in error

        # Удаление несуществующего
        success, error = storage.delete_profile("unknown_id")
        assert success is False
        assert "не найден" in (error or "")

    def test_set_default_profile(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        created = storage.create_profile(name="Мой любимый")

        assert storage.set_default_profile(created.id) is True
        assert storage.get_default_profile().id == created.id
        assert storage.get_profile("default").is_default is False

        # Несуществующий профиль
        assert storage.set_default_profile("non_existent") is False

    def test_duplicate_profile(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        copy = storage.duplicate_profile("gaming", new_name="Игровой 2.0")
        assert copy is not None
        assert copy.name == "Игровой 2.0"
        assert copy.id != "gaming"
        assert copy.is_builtin is False
        assert copy.video.fps == 60

        missing = storage.duplicate_profile("missing_id")
        assert missing is None

    def test_export_and_import_profile(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        exported = storage.export_profile("presentation")
        assert exported is not None
        assert exported.get("schema") == "mia.profile.v1"
        assert "profile" in exported

        # Импорт
        imported = storage.import_profile(exported)
        assert imported is not None
        assert imported.name == "Презентация"
        assert imported.id != "presentation"
        assert imported.is_builtin is False

    def test_apply_profile_to_config(self, tmp_path: Path) -> None:
        storage = ProfileStorage(storage_path=tmp_path / "profiles.json")
        config_file = tmp_path / "config.json"
        cfg = ConfigManager(config_path=config_file)

        assert storage.apply_profile_to_config("gaming", cfg) is True
        assert cfg.settings.video.fps == 60
        assert cfg.settings.video.bitrate == "8M"
        assert cfg.settings.audio.record_system is True
        assert cfg.settings.audio.record_mic is False

        assert storage.apply_profile_to_config("non_existent", cfg) is False


class TestGlobalSingleton:
    """Тесты глобального синглтона get_profile_storage / set_profile_storage."""

    def test_singleton_get_and_set(self, tmp_path: Path) -> None:
        custom_storage = ProfileStorage(storage_path=tmp_path / "custom.json")
        set_profile_storage(custom_storage)
        assert get_profile_storage() is custom_storage
        set_profile_storage(None)
