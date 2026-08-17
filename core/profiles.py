"""
Модуль профилей записи
======================

Определяет модель профиля записи (RecordingProfile), предустановленные
системные профили и потокобезопасное хранилище (ProfileStorage) с
сохранением в config/profiles.json.
"""

from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config import (
    AudioSettings,
    CaptureSettings,
    ConfigManager,
    VideoSettings,
    get_config,
)
from logger_config import get_module_logger
from utils import atomic_write_json

logger = get_module_logger(__name__)

PROFILES_DIR = Path(__file__).resolve().parent.parent / "config"
PROFILES_FILE = PROFILES_DIR / "profiles.json"


def _utc_now_iso() -> str:
    """Возвращает текущую дату и время в UTC (ISO 8601)."""
    return datetime.now(UTC).isoformat()


@dataclass
class RecordingProfile:
    """Профиль настроек записи."""

    id: str
    name: str
    description: str = ""
    icon: str = "⚙️"
    video: VideoSettings = field(default_factory=VideoSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    is_default: bool = False
    is_builtin: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Преобразует профиль в сериализуемый словарь."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "video": asdict(self.video),
            "audio": asdict(self.audio),
            "capture": asdict(self.capture),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_default": self.is_default,
            "is_builtin": self.is_builtin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RecordingProfile:
        """Создает профиль из словаря."""
        video_data = data.get("video") or {}
        audio_data = data.get("audio") or {}
        capture_data = data.get("capture") or {}

        # Очистка неизвестных полей для совместимости
        video = VideoSettings(
            fps=video_data.get("fps", 30),
            codec=video_data.get("codec", "libx264"),
            bitrate=video_data.get("bitrate", "2M"),
            format=video_data.get("format", "mp4"),
            compression=video_data.get("compression", True),
            preset=video_data.get("preset", "medium"),
            verify_on_complete=video_data.get("verify_on_complete", True),
            auto_repair_corrupted=video_data.get(
                "auto_repair_corrupted", False
            ),
        )

        audio = AudioSettings(
            record_mic=audio_data.get("record_mic", True),
            record_system=audio_data.get("record_system", False),
            mic_device=audio_data.get("mic_device"),
            system_device=audio_data.get("system_device"),
            sample_rate=audio_data.get("sample_rate", 44100),
            channels=audio_data.get("channels", 2),
        )

        capture = CaptureSettings(
            area_type=capture_data.get("area_type", "full"),
            window_title=capture_data.get("window_title"),
            rect_coords=capture_data.get("rect_coords"),
        )

        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:8])),
            name=str(data.get("name", "Новый профиль")),
            description=str(data.get("description", "")),
            icon=str(data.get("icon", "⚙️")),
            video=video,
            audio=audio,
            capture=capture,
            created_at=str(data.get("created_at", _utc_now_iso())),
            updated_at=str(data.get("updated_at", _utc_now_iso())),
            is_default=bool(data.get("is_default", False)),
            is_builtin=bool(data.get("is_builtin", False)),
        )


def get_builtin_profiles() -> list[RecordingProfile]:
    """Возвращает список стандартных предустановленных профилей."""
    return [
        RecordingProfile(
            id="default",
            name="Стандартный",
            description="Универсальный профиль: 30 FPS, H.264, микрофон, весь экран",
            icon="🎥",
            video=VideoSettings(
                fps=30,
                codec="libx264",
                bitrate="2M",
                format="mp4",
                preset="medium",
            ),
            audio=AudioSettings(
                record_mic=True,
                record_system=False,
                sample_rate=44100,
                channels=2,
            ),
            capture=CaptureSettings(
                area_type="full",
                window_title=None,
                rect_coords=None,
            ),
            is_default=True,
            is_builtin=True,
        ),
        RecordingProfile(
            id="gaming",
            name="Игровой",
            description="Высокая частота и качество: 60 FPS, 8M битрейт, системный звук",
            icon="🎮",
            video=VideoSettings(
                fps=60,
                codec="libx264",
                bitrate="8M",
                format="mp4",
                preset="faster",
            ),
            audio=AudioSettings(
                record_mic=False,
                record_system=True,
                sample_rate=48000,
                channels=2,
            ),
            capture=CaptureSettings(
                area_type="full",
                window_title=None,
                rect_coords=None,
            ),
            is_default=False,
            is_builtin=True,
        ),
        RecordingProfile(
            id="presentation",
            name="Презентация",
            description="Вебинары и доклады: 30 FPS, микрофон и системный звук, окно",
            icon="📊",
            video=VideoSettings(
                fps=30,
                codec="libx264",
                bitrate="3M",
                format="mp4",
                preset="medium",
            ),
            audio=AudioSettings(
                record_mic=True,
                record_system=True,
                sample_rate=44100,
                channels=2,
            ),
            capture=CaptureSettings(
                area_type="window",
                window_title=None,
                rect_coords=None,
            ),
            is_default=False,
            is_builtin=True,
        ),
    ]


class ProfileStorage:
    """
    Потокобезопасное хранилище профилей записи с персистентностью в JSON.
    """

    def __init__(self, storage_path: Path | str | None = None) -> None:
        """
        Инициализирует хранилище профилей.

        Args:
            storage_path: Путь к файлу profiles.json (по умолчанию config/profiles.json).
        """
        if storage_path is None:
            self.storage_path = PROFILES_FILE
        else:
            self.storage_path = Path(storage_path)

        self._lock = threading.RLock()
        self._profiles: dict[str, RecordingProfile] = {}
        self.load()

    def load(self) -> bool:
        """
        Загружает профили из файла JSON. При отсутствии или ошибке
        инициализирует хранилище встроенными профилями.

        Returns:
            True, если загрузка или первичная инициализация успешна.
        """
        with self._lock:
            self._profiles.clear()
            if self.storage_path.exists():
                try:
                    with open(
                        self.storage_path, encoding="utf-8"
                    ) as file_handle:
                        content = file_handle.read().strip()
                        if content:
                            payload = json.loads(content)
                            profiles_list = payload.get("profiles", [])
                            for p_data in profiles_list:
                                if (
                                    isinstance(p_data, dict)
                                    and "id" in p_data
                                    and "name" in p_data
                                ):
                                    profile = RecordingProfile.from_dict(
                                        p_data
                                    )
                                    self._profiles[profile.id] = profile
                except Exception as e:
                    logger.warning(
                        "Ошибка чтения profiles.json (%s), fallback на builtin профили: %s",
                        self.storage_path,
                        e,
                    )

            # Если профили не загрузились или файл пуст, добавляем builtin
            if not self._profiles:
                for builtin in get_builtin_profiles():
                    self._profiles[builtin.id] = builtin
                self.save()
                return True

            # Гарантируем наличие хотя бы одного дефолтного профиля
            has_default = any(p.is_default for p in self._profiles.values())
            if not has_default and "default" in self._profiles:
                self._profiles["default"].is_default = True
            elif not has_default and self._profiles:
                next(iter(self._profiles.values())).is_default = True

            return True

    def save(self) -> bool:
        """
        Атомарно сохраняет текущие профили в JSON-файл.

        Returns:
            True, если сохранение успешно.
        """
        with self._lock:
            payload = {
                "version": "1.0",
                "updated_at": _utc_now_iso(),
                "profiles": [p.to_dict() for p in self._profiles.values()],
            }
            success = atomic_write_json(self.storage_path, payload)
            if not success:
                logger.error(
                    "Не удалось сохранить профили в %s", self.storage_path
                )
            return success

    def list_profiles(self) -> list[RecordingProfile]:
        """Возвращает копию списка всех профилей."""
        with self._lock:
            return list(self._profiles.values())

    def get_profile(self, profile_id: str) -> RecordingProfile | None:
        """Возвращает профиль по идентификатору или None."""
        with self._lock:
            return self._profiles.get(profile_id)

    def get_default_profile(self) -> RecordingProfile:
        """Возвращает профиль по умолчанию."""
        with self._lock:
            for p in self._profiles.values():
                if p.is_default:
                    return p
            if "default" in self._profiles:
                return self._profiles["default"]
            if self._profiles:
                return next(iter(self._profiles.values()))
            builtin = get_builtin_profiles()[0]
            self._profiles[builtin.id] = builtin
            return builtin

    def set_default_profile(self, profile_id: str) -> bool:
        """
        Устанавливает указанный профиль как профиль по умолчанию.

        Args:
            profile_id: Идентификатор профиля.

        Returns:
            True, если профиль найден и установлен.
        """
        with self._lock:
            if profile_id not in self._profiles:
                return False

            for pid, profile in self._profiles.items():
                profile.is_default = pid == profile_id
                if pid == profile_id:
                    profile.updated_at = _utc_now_iso()

            self.save()
            return True

    def create_profile(
        self,
        name: str,
        description: str = "",
        icon: str = "⚙️",
        video: VideoSettings | None = None,
        audio: AudioSettings | None = None,
        capture: CaptureSettings | None = None,
        is_default: bool = False,
        profile_id: str | None = None,
    ) -> RecordingProfile:
        """
        Создает и сохраняет новый профиль.

        Args:
            name: Название профиля.
            description: Описание профиля.
            icon: Иконка или эмодзи.
            video: Настройки видео.
            audio: Настройки аудио.
            capture: Настройки захвата.
            is_default: Сделать ли профилем по умолчанию.
            profile_id: Опциональный идентификатор (генерируется при отсутствии).

        Returns:
            Созданный экземпляр RecordingProfile.
        """
        with self._lock:
            pid = profile_id or uuid.uuid4().hex[:8]
            while pid in self._profiles and profile_id is None:
                pid = uuid.uuid4().hex[:8]

            profile = RecordingProfile(
                id=pid,
                name=name,
                description=description,
                icon=icon,
                video=video or VideoSettings(),
                audio=audio or AudioSettings(),
                capture=capture or CaptureSettings(),
                created_at=_utc_now_iso(),
                updated_at=_utc_now_iso(),
                is_default=is_default,
                is_builtin=False,
            )

            if is_default:
                for p in self._profiles.values():
                    p.is_default = False

            self._profiles[pid] = profile
            self.save()
            logger.info("Создан новый профиль записи: %s (%s)", name, pid)
            return profile

    def update_profile(
        self,
        profile_id: str,
        name: str | None = None,
        description: str | None = None,
        icon: str | None = None,
        video: VideoSettings | None = None,
        audio: AudioSettings | None = None,
        capture: CaptureSettings | None = None,
        is_default: bool | None = None,
    ) -> RecordingProfile | None:
        """
        Обновляет существующий профиль.

        Args:
            profile_id: Идентификатор профиля.
            name: Новое название.
            description: Новое описание.
            icon: Новая иконка.
            video: Новые настройки видео.
            audio: Новые настройки аудио.
            capture: Новые настройки захвата.
            is_default: Флаг профиля по умолчанию.

        Returns:
            Обновленный экземпляр RecordingProfile или None, если профиль не найден.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None

            if name is not None:
                profile.name = name
            if description is not None:
                profile.description = description
            if icon is not None:
                profile.icon = icon
            if video is not None:
                profile.video = video
            if audio is not None:
                profile.audio = audio
            if capture is not None:
                profile.capture = capture

            if is_default is not None:
                if is_default:
                    for pid, p in self._profiles.items():
                        p.is_default = pid == profile_id
                else:
                    profile.is_default = False

            profile.updated_at = _utc_now_iso()
            self.save()
            logger.info(
                "Обновлен профиль записи: %s (%s)", profile.name, profile_id
            )
            return profile

    def delete_profile(self, profile_id: str) -> tuple[bool, str | None]:
        """
        Удаляет профиль. Встроенные профили удалять запрещено.

        Args:
            profile_id: Идентификатор профиля.

        Returns:
            Кортеж (success, error_message).
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return False, "Профиль не найден"

            if profile.is_builtin:
                return False, "Нельзя удалить встроенный системный профиль"

            was_default = profile.is_default
            del self._profiles[profile_id]

            if was_default and self._profiles:
                # Назначаем default профиль
                default_target = self._profiles.get(
                    "default", next(iter(self._profiles.values()))
                )
                default_target.is_default = True

            self.save()
            logger.info("Удален профиль записи: %s", profile_id)
            return True, None

    def duplicate_profile(
        self, profile_id: str, new_name: str | None = None
    ) -> RecordingProfile | None:
        """
        Создает копию существующего профиля.

        Args:
            profile_id: Идентификатор исходного профиля.
            new_name: Название копии (по умолчанию "{Исходное имя} (Копия)").

        Returns:
            Новый экземпляр RecordingProfile или None, если оригинал не найден.
        """
        with self._lock:
            source = self._profiles.get(profile_id)
            if source is None:
                return None

            copy_name = new_name or f"{source.name} (Копия)"
            return self.create_profile(
                name=copy_name,
                description=source.description,
                icon=source.icon,
                video=VideoSettings(**asdict(source.video)),
                audio=AudioSettings(**asdict(source.audio)),
                capture=CaptureSettings(**asdict(source.capture)),
                is_default=False,
            )

    def export_profile(self, profile_id: str) -> dict[str, Any] | None:
        """
        Экспортирует профиль в словарь для сохранения во внешнем файле.

        Args:
            profile_id: Идентификатор профиля.

        Returns:
            Словарь профиля с метаданными схемы.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return None
            return {
                "schema": "mia.profile.v1",
                "exported_at": _utc_now_iso(),
                "profile": profile.to_dict(),
            }

    def import_profile(self, data: dict[str, Any]) -> RecordingProfile:
        """
        Импортирует профиль из внешнего словаря/файла.

        Args:
            data: Данные профиля (экспортированный формат или прямой dict).

        Returns:
            Созданный или обновленный экземпляр RecordingProfile.
        """
        with self._lock:
            profile_data = data.get("profile", data)
            name = str(profile_data.get("name", "Импортированный профиль"))
            description = str(profile_data.get("description", ""))
            icon = str(profile_data.get("icon", "⚙️"))

            # Генерируем новый ID, чтобы не перетереть существующие встроенные
            new_id = uuid.uuid4().hex[:8]

            profile = RecordingProfile.from_dict(profile_data)
            profile.id = new_id
            profile.name = name
            profile.description = description
            profile.icon = icon
            profile.is_builtin = False
            profile.is_default = False
            profile.created_at = _utc_now_iso()
            profile.updated_at = _utc_now_iso()

            self._profiles[new_id] = profile
            self.save()
            logger.info("Импортирован профиль записи: %s (%s)", name, new_id)
            return profile

    def apply_profile_to_config(
        self, profile_id: str, config_manager: ConfigManager | None = None
    ) -> bool:
        """
        Применяет параметры профиля к активной конфигурации приложения.

        Args:
            profile_id: Идентификатор профиля.
            config_manager: Экземпляр ConfigManager (по умолчанию get_config()).

        Returns:
            True, если профиль найден и успешно применен к конфигурации.
        """
        with self._lock:
            profile = self._profiles.get(profile_id)
            if profile is None:
                return False

            cfg = config_manager or get_config()
            cfg.settings.video = VideoSettings(**asdict(profile.video))
            cfg.settings.audio = AudioSettings(**asdict(profile.audio))
            cfg.settings.capture = CaptureSettings(**asdict(profile.capture))
            cfg.save()
            logger.info(
                "Профиль %s (%s) применен к конфигурации приложения",
                profile.name,
                profile_id,
            )
            return True


_global_profile_storage: ProfileStorage | None = None
_global_profile_lock = threading.Lock()


def get_profile_storage() -> ProfileStorage:
    """Возвращает глобальный синглтон ProfileStorage."""
    global _global_profile_storage
    with _global_profile_lock:
        if _global_profile_storage is None:
            _global_profile_storage = ProfileStorage()
        return _global_profile_storage


def set_profile_storage(storage: ProfileStorage | None) -> None:
    """Устанавливает или сбрасывает глобальный ProfileStorage (для тестов)."""
    global _global_profile_storage
    with _global_profile_lock:
        _global_profile_storage = storage
