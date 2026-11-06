"""Настройки и операции над записями (#176).

Webhook, verify/repair файла, конфигурация, профили, постобработка."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass
from config import get_config
from core.webhook import (
    WebhookSender,
    generate_webhook_secret,
)
from exceptions import (
    ConfigValidationError,
)
from logger_config import get_module_logger
from recorder.utils import (
    attempt_repair_video,
    verify_video_integrity,
)

logger = get_module_logger(__name__)


from app_runtime.app_shared_state import AppSharedState


class SettingsOpsMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def _configure_webhook(
        self, url: str | None, secret: str | None, enabled: bool
    ) -> dict[str, Any]:
        """
        Настройка webhook-уведомлений.

        Если `secret` не передан явно: при наличии уже сохранённого секрета
        он сохраняется как есть; если секрета нет и `enabled=True` —
        генерируется новый (возвращается в ответе один раз, далее не
        раскрывается через `get_webhook_config`).
        """
        current_secret = get_config().settings.api.webhook_secret
        generated_secret: str | None = None

        if secret:
            resolved_secret = secret
        elif current_secret:
            resolved_secret = current_secret
        elif enabled:
            resolved_secret = generate_webhook_secret()
            generated_secret = resolved_secret
        else:
            resolved_secret = None

        result = self._update_config(
            {
                "api": {
                    "webhook_url": url,
                    "webhook_secret": resolved_secret,
                    "webhook_enabled": enabled,
                }
            }
        )
        if not result.get("success"):
            return result

        response: dict[str, Any] = {
            "success": True,
            "url": url,
            "enabled": enabled,
            "has_secret": bool(resolved_secret),
        }
        if generated_secret is not None:
            response["secret"] = generated_secret
        return response

    def _test_webhook(self) -> dict[str, Any]:
        """Отправка тестового webhook-уведомления текущими настройками."""
        api_settings = get_config().settings.api
        if not api_settings.webhook_url:
            return {"success": False, "error": "Webhook URL не настроен"}

        sender = WebhookSender()
        success, response_time_ms = sender.send(
            url=api_settings.webhook_url,
            event="webhook.test",
            data={"message": "Тестовое уведомление MIA-ScreenCapture"},
            secret=api_settings.webhook_secret,
        )
        return {"success": success, "response_time_ms": response_time_ms}

    def _verify_recording_file(self, file_path: str) -> dict[str, Any]:
        """Проверка целостности произвольного видеофайла по пути."""
        resolved_path = self._resolve_recording_file_path(file_path)
        check = verify_video_integrity(resolved_path)
        return {
            "valid": check.valid,
            "duration_s": check.duration_s,
            "codec_name": check.codec_name,
            "width": check.width,
            "height": check.height,
            "error": check.error,
        }

    def _repair_recording_file(self, file_path: str) -> dict[str, Any]:
        """Попытка восстановления произвольного видеофайла по пути."""
        resolved_path = self._resolve_recording_file_path(file_path)
        repair = attempt_repair_video(resolved_path)
        return {
            "repaired": repair.repaired,
            "original_size_bytes": repair.original_size_bytes,
            "repaired_size_bytes": repair.repaired_size_bytes,
            "error": repair.error,
        }

    def _resolve_recording_file_path(self, file_path: str) -> Path:
        """Разрешает относительный путь внутри каталога вывода записей."""
        output_root = get_config().get_output_path().parent.resolve()
        resolved_path = (output_root / file_path).resolve()
        if (
            resolved_path == output_root
            or not resolved_path.is_relative_to(output_root)
            or resolved_path.is_dir()
        ):
            raise ValueError(
                "Путь к записи должен быть файлом внутри каталога вывода"
            )
        return resolved_path

    def _get_config(self) -> dict[str, Any]:
        """Получение текущей конфигурации."""
        config = get_config()
        from dataclasses import asdict

        return asdict(config.settings)

    def _update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Обновление конфигурации.

        Поддерживает обновление вложенных секций (video, audio, capture, output, api, scheduler).
        Некоторые изменения требуют перезапуска соответствующих компонентов.
        """
        from config import (
            APISettings,
            APISettingsSchema,
            AudioSettings,
            AudioSettingsSchema,
            CaptureSettings,
            CaptureSettingsSchema,
            OutputSettings,
            OutputSettingsSchema,
            RateLimitSettings,
            SchedulerSettings,
            SchedulerSettingsSchema,
            VideoSettings,
            VideoSettingsSchema,
        )

        config = get_config()
        restart_required: list[str] = []
        updated_sections: list[str] = []
        staged_sections: dict[str, dict[str, Any]] = {}
        simple_updates: dict[str, Any] = {}
        original_sections: dict[str, dict[str, Any]] = {}
        original_simple: dict[str, Any] = {}

        # Обновление вложенных секций
        section_classes = {
            "video": VideoSettings,
            "audio": AudioSettings,
            "capture": CaptureSettings,
            "output": OutputSettings,
            "api": APISettings,
            "scheduler": SchedulerSettings,
        }
        section_schemas: dict[str, Any] = {
            "video": VideoSettingsSchema,
            "audio": AudioSettingsSchema,
            "capture": CaptureSettingsSchema,
            "output": OutputSettingsSchema,
            "api": APISettingsSchema,
            "scheduler": SchedulerSettingsSchema,
        }

        try:
            for section_name, _section_class in section_classes.items():
                if section_name not in data:
                    continue
                section_data = data[section_name]
                if not isinstance(section_data, dict):
                    continue
                current_section = getattr(config.settings, section_name, None)
                if current_section is None:
                    continue

                current_values = vars(current_section).copy()
                original_sections[section_name] = current_values.copy()
                merged_values = current_values.copy()
                for key, value in section_data.items():
                    if key in merged_values:
                        merged_values[key] = value

                # Вложенный dataclass (rate_limit, #152) сериализуем
                # в словарь для Pydantic-валидации
                if section_name == "api":
                    rl_value = merged_values.get("rate_limit")
                    if isinstance(rl_value, RateLimitSettings):
                        merged_values["rate_limit"] = asdict(rl_value)

                validated = section_schemas[section_name].model_validate(
                    merged_values
                )
                staged_values = validated.model_dump()
                if section_name == "api" and isinstance(
                    staged_values.get("rate_limit"), dict
                ):
                    staged_values["rate_limit"] = RateLimitSettings(
                        **staged_values["rate_limit"]
                    )
                staged_sections[section_name] = staged_values
                updated_sections.append(section_name)

                # Проверка, нужен ли перезапуск
                if (
                    section_name == "api"
                    and self._api_server
                    and any(
                        k in section_data for k in ["host", "port", "enabled"]
                    )
                ):
                    restart_required.append("api")
        except (ConfigValidationError, ValueError, TypeError) as e:
            return {"success": False, "error": str(e)}

        # Обновление простых полей
        simple_fields = [
            "minimize_to_tray",
            "show_notifications",
            "notification_sounds",
            "language",
        ]
        for field_name in simple_fields:
            if field_name in data:
                original_simple[field_name] = getattr(
                    config.settings, field_name
                )
                simple_updates[field_name] = data[field_name]
                updated_sections.append(field_name)

        # Apply
        for section_name, values in staged_sections.items():
            target = getattr(config.settings, section_name, None)
            if target is None:
                continue
            for key, value in values.items():
                if hasattr(target, key):
                    setattr(target, key, value)

        for field_name, value in simple_updates.items():
            setattr(config.settings, field_name, value)

        # Сохранение
        if not config.save():
            for section_name, values in original_sections.items():
                target = getattr(config.settings, section_name, None)
                if target is None:
                    continue
                for key, value in values.items():
                    if hasattr(target, key):
                        setattr(target, key, value)
            for field_name, value in original_simple.items():
                setattr(config.settings, field_name, value)
            return {
                "success": False,
                "error": "Не удалось сохранить конфигурацию",
            }

        # Уведомление о требуемом перезапуске
        if restart_required:
            logger.warning(
                f"Для применения изменений требуется перезапуск: {', '.join(restart_required)}"
            )

        return {
            "success": True,
            "updated_sections": updated_sections,
            "restart_required": restart_required,
        }

    # === Управление профилями записи ===

    def get_profiles(self) -> list[dict[str, Any]]:
        """Возвращает список всех профилей записи."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        return [p.to_dict() for p in storage.list_profiles()]

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Возвращает профиль по идентификатору."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        profile = storage.get_profile(profile_id)
        return profile.to_dict() if profile else None

    def create_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создает новый профиль записи."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        video = None
        if "video" in data and isinstance(data["video"], dict):
            from config import VideoSettings

            video = VideoSettings(**data["video"])
        audio = None
        if "audio" in data and isinstance(data["audio"], dict):
            from config import AudioSettings

            audio = AudioSettings(**data["audio"])
        capture = None
        if "capture" in data and isinstance(data["capture"], dict):
            from config import CaptureSettings

            capture = CaptureSettings(**data["capture"])

        profile = storage.create_profile(
            name=data.get("name", "Новый профиль"),
            description=data.get("description", ""),
            icon=data.get("icon", "⚙️"),
            video=video,
            audio=audio,
            capture=capture,
            is_default=bool(data.get("is_default", False)),
        )
        return {"success": True, "profile": profile.to_dict()}

    def update_profile(
        self, profile_id: str, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Обновляет существующий профиль записи."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        video = None
        if "video" in data and isinstance(data["video"], dict):
            from config import VideoSettings

            video = VideoSettings(**data["video"])
        audio = None
        if "audio" in data and isinstance(data["audio"], dict):
            from config import AudioSettings

            audio = AudioSettings(**data["audio"])
        capture = None
        if "capture" in data and isinstance(data["capture"], dict):
            from config import CaptureSettings

            capture = CaptureSettings(**data["capture"])

        profile = storage.update_profile(
            profile_id=profile_id,
            name=data.get("name"),
            description=data.get("description"),
            icon=data.get("icon"),
            video=video,
            audio=audio,
            capture=capture,
            is_default=data.get("is_default"),
        )
        if profile is None:
            return {"success": False, "error": "Профиль не найден"}
        return {"success": True, "profile": profile.to_dict()}

    def delete_profile(self, profile_id: str) -> dict[str, Any]:
        """Удаляет профиль записи."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        success, error = storage.delete_profile(profile_id)
        if not success:
            return {
                "success": False,
                "error": error or "Не удалось удалить профиль",
            }
        return {"success": True}

    def apply_profile(self, profile_id: str) -> dict[str, Any]:
        """Применяет профиль записи к активной конфигурации и GUI (если открыт)."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        profile = storage.get_profile(profile_id)
        if profile is None:
            return {"success": False, "error": "Профиль не найден"}

        success = storage.apply_profile_to_config(profile_id)
        if not success:
            return {"success": False, "error": "Не удалось применить профиль"}

        if self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.apply_profile_settings(profile)
            )

        return {"success": True, "applied_profile": profile.to_dict()}

    def export_profile(self, profile_id: str) -> dict[str, Any] | None:
        """Экспортирует профиль записи."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        return storage.export_profile(profile_id)

    def import_profile(self, data: dict[str, Any]) -> dict[str, Any]:
        """Импортирует профиль записи."""
        from core.profiles import get_profile_storage

        storage = get_profile_storage()
        profile = storage.import_profile(data)
        return {"success": True, "profile": profile.to_dict()}

    # === Постобработка записей ===

    def get_post_processing_config(self) -> dict[str, Any]:
        """Возвращает текущие настройки постобработки."""
        config = get_config()
        return asdict(config.settings.post_processing)

    def update_post_processing_config(
        self, data: dict[str, Any]
    ) -> dict[str, Any]:
        """Обновляет настройки постобработки."""
        from config import PostProcessingSettingsSchema

        try:
            validated = PostProcessingSettingsSchema.model_validate(data)
            config = get_config()
            for k, v in validated.model_dump().items():
                setattr(config.settings.post_processing, k, v)
            saved = config.save()
            return {
                "success": saved,
                "config": asdict(config.settings.post_processing),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_post_processing_status(self) -> dict[str, Any]:
        """Возвращает статус конвейера постобработки."""
        last_res = self._post_processing_manager.last_result
        return {
            "is_running": self._post_processing_manager.is_running,
            "last_result": last_res.to_dict() if last_res else None,
        }

    def run_post_processing(
        self, file_path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Запускает постобработку для указанного файла."""
        path = Path(file_path)
        if not path.exists():
            return {
                "success": False,
                "error": f"Файл не найден: {file_path}",
            }
        config = get_config()
        settings = config.settings.post_processing
        if params:
            from config import PostProcessingSettings

            settings_dict = asdict(settings)
            settings_dict.update(params)
            settings = PostProcessingSettings(**settings_dict)

        steps = self._post_processing_manager.build_steps_from_settings(
            settings
        )
        if not steps:
            return {
                "success": False,
                "error": "Нет активных шагов постобработки",
            }
        from core.post_processing.pipeline import PostRecordingPipeline

        pipeline = PostRecordingPipeline(
            steps=steps, event_bus=self._recording_service.event_bus
        )
        pipeline.run_in_background(path)
        return {
            "success": True,
            "message": "Постобработка запущена в фоновом режиме",
            "file_path": str(path),
        }

    # === Авто-обновление приложения (#128) ===
