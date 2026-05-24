"""
Сервис управления записью для API/CLI/Headless режимов.

Отделяет логику записи от GUI окна и предоставляет единый интерфейс
для запуска/остановки/паузы и получения статуса.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, cast

from config import get_config
from core.event_bus import (
    EventBus,
    InMemoryEventBus,
    RecordingEvent,
    RecordingEventType,
)
from core.geometry import validate_rect_coords
from core.recording_backend import RecordingBackend
from core.recording_types import (
    AudioMode,
    AudioRequest,
    CaptureMode,
    CaptureRequest,
    VideoRequest,
)
from exceptions import RecordingError
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class RecordingService:
    """Сервис записи, не требующий инициализации GUI."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        backend: RecordingBackend | None = None,
    ) -> None:
        if backend is None:
            raise ValueError(
                "backend обязателен. Передайте GUIRecordingBackend или другой "
                "implementation RecordingBackend."
            )
        self._backend = backend
        self._lock = threading.Lock()
        self._event_bus = event_bus or InMemoryEventBus()

    @property
    def event_bus(self) -> EventBus:
        """Возвращает event bus для интеграции с транспортами (например, WebSocket)."""
        return self._event_bus

    def get_status(self) -> dict[str, Any]:
        """Возвращает текущий статус записи."""
        backend_status = self._backend.get_status()
        status = {
            "is_recording": backend_status.is_recording,
            "is_paused": backend_status.is_paused,
            "elapsed_time": backend_status.elapsed_time,
            "current_file": str(backend_status.current_file)
            if backend_status.current_file
            else None,
        }
        self._publish_event(RecordingEventType.STATUS, status)
        return status

    def start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Запускает запись из API/планировщика параметров.

        Поддерживает как API-формат, так и internal-формат ключей:
        - area / area_type
        - rect / rect_coords
        - audio / audio_type
        """
        with self._lock:
            backend_status = self._backend.get_status()
            if backend_status.is_recording or backend_status.is_paused:
                result = {"success": False, "error": "Запись уже идёт"}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            try:
                normalized = self._normalize_params(params)
                capture = self._build_capture_settings(normalized)
                audio = self._build_audio_settings(normalized)
                video = self._build_video_settings(normalized)
                output_path = self._build_output_path(normalized)
                duration = normalized.get("duration")

                success, error_msg = self._backend.start(
                    output_path=output_path,
                    capture=capture,
                    audio=audio,
                    video=video,
                    duration=duration,
                )
                if not success:
                    result = {
                        "success": False,
                        "error": error_msg or "Не удалось запустить запись",
                    }
                    self._publish_event(RecordingEventType.ERROR, result)
                    return result

                logger.info(f"Запись запущена: {output_path}")
                result = {"success": True, "output_path": str(output_path)}
                self._publish_event(RecordingEventType.STARTED, result)
                return result

            except RecordingError as e:
                logger.error(f"Ошибка запуска записи: {e}")
                result = {"success": False, "error": str(e)}
                self._publish_event(RecordingEventType.ERROR, result)
                return result
            except (OSError, ValueError) as e:
                logger.error(
                    f"Системная ошибка запуска записи: {e}", exc_info=True
                )
                result = {"success": False, "error": str(e)}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает текущую запись."""
        with self._lock:
            backend_status = self._backend.get_status()
            if (
                not backend_status.is_recording
                and not backend_status.is_paused
            ):
                result = {"success": False, "error": "Запись не идёт"}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            output_path = self._backend.stop()
            if not output_path:
                result = {
                    "success": False,
                    "error": "Не удалось сохранить запись",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            try:
                if output_path.exists():
                    get_config().add_recent_recording(
                        str(output_path), output_path.stat().st_size
                    )
            except OSError as e:
                # Ошибка обновления recent recordings не должна ломать stop.
                logger.warning(f"Не удалось обновить список записей: {e}")

            logger.info(f"Запись остановлена: {output_path}")
            result = {"success": True, "filepath": str(output_path)}
            self._publish_event(RecordingEventType.STOPPED, result)
            return result

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу текущей записи."""
        with self._lock:
            backend_status = self._backend.get_status()
            if (
                not backend_status.is_recording
                and not backend_status.is_paused
            ):
                result = {"success": False, "error": "Запись не идёт"}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            if backend_status.is_paused:
                resumed = self._backend.resume()
                if not resumed:
                    result = {
                        "success": False,
                        "error": "Не удалось возобновить",
                    }
                    self._publish_event(RecordingEventType.ERROR, result)
                    return result
                result = {"success": True, "is_paused": False}
                self._publish_event(RecordingEventType.RESUMED, result)
                return result

            paused = self._backend.pause()
            if not paused:
                result = {
                    "success": False,
                    "error": "Не удалось поставить на паузу",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result
            result = {"success": True, "is_paused": True}
            self._publish_event(RecordingEventType.PAUSED, result)
            return result

    def get_recordings(self) -> list[dict[str, Any]]:
        """Возвращает список последних записей из конфигурации."""
        return cast(
            list[dict[str, Any]], get_config().settings.recent_recordings
        )

    def stop_active_recording_if_any(self) -> dict[str, Any] | None:
        """Безопасно останавливает активную запись, если она есть."""
        with self._lock:
            backend_status = self._backend.get_status()
            if (
                not backend_status.is_recording
                and not backend_status.is_paused
            ):
                return None
        return self.stop_recording()

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(params)
        normalized["area"] = params.get(
            "area", params.get("area_type", "full")
        )
        normalized["rect"] = params.get("rect", params.get("rect_coords"))
        normalized["audio"] = params.get(
            "audio", params.get("audio_type", "none")
        )
        return normalized

    def _validate_rect_coords(
        self, rect: list[int] | tuple[int, ...]
    ) -> tuple[int, int, int, int]:
        """
        Валидирует координаты области захвата.

        Использует общую функцию validate_rect_coords из core.geometry
        в строгом режиме для проверки корректности порядка координат.

        Args:
            rect: Список или кортеж из 4 координат [x1, y1, x2, y2].

        Returns:
            Кортеж (x1, y1, x2, y2).

        Raises:
            ValueError: Если координаты некорректны.
        """
        if len(rect) != 4:
            raise ValueError(
                f"rect должен содержать 4 координаты [x1, y1, x2, y2], "
                f"получено {len(rect)}"
            )
        x1, y1, x2, y2 = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
        # Используем общую функцию с strict=True для валидации
        return validate_rect_coords(x1, y1, x2, y2, strict=True)

    def _build_capture_settings(
        self, params: dict[str, Any]
    ) -> CaptureRequest:
        area = params.get("area", "full")
        capture_mode_map = {
            "full": CaptureMode.FULL,
            "window": CaptureMode.WINDOW,
            "rect": CaptureMode.RECT,
        }
        capture_mode = capture_mode_map.get(area, CaptureMode.FULL)

        rect_value = params.get("rect")
        rect_coords: tuple[int, int, int, int]
        if isinstance(rect_value, list | tuple) and len(rect_value) >= 4:
            rect_coords = self._validate_rect_coords(rect_value)
        elif area == "rect":
            raise ValueError(
                "Для area='rect' необходимо указать корректные rect_coords "
                "в формате [x1, y1, x2, y2]"
            )
        else:
            rect_coords = (0, 0, 1920, 1080)

        return CaptureRequest(
            mode=capture_mode,
            window_title=params.get("window_title", "") or "",
            rect_coords=rect_coords,
        )

    def _build_audio_settings(self, params: dict[str, Any]) -> AudioRequest:
        audio_map = {
            "none": AudioMode.NONE,
            "mic": AudioMode.MIC,
            "system": AudioMode.SYSTEM,
            "both": AudioMode.BOTH,
        }
        audio_mode = audio_map.get(
            str(params.get("audio", "none")), AudioMode.NONE
        )
        return AudioRequest(
            mode=audio_mode,
            mic_device_index=params.get("mic_device_index"),
        )

    def _build_video_settings(self, params: dict[str, Any]) -> VideoRequest:
        config = get_config().settings.video
        return VideoRequest(
            fps=int(params.get("fps", config.fps)),
            codec=str(params.get("codec", config.codec)),
            bitrate=str(params.get("bitrate", config.bitrate)),
            format=str(params.get("format", config.format)),
        )

    def _build_output_path(self, params: dict[str, Any]) -> Path:
        config_manager = get_config()
        value = params.get("output_path")
        if not value:
            return cast(Path, config_manager.get_output_path())

        raw_path = str(value).strip()
        if not raw_path:
            return cast(Path, config_manager.get_output_path())

        candidate = Path(raw_path)
        is_dir_hint = raw_path.endswith(("/", "\\"))
        if is_dir_hint or (candidate.exists() and candidate.is_dir()):
            generated_name = str(config_manager.get_output_path().name)
            return candidate / generated_name

        if candidate.suffix:
            return candidate

        default_format = str(config_manager.settings.video.format)
        extension = f".{default_format.lstrip('.')}"
        return candidate.with_suffix(extension)

    def _publish_event(
        self, event_type: RecordingEventType, payload: dict[str, Any]
    ) -> None:
        try:
            self._event_bus.publish(
                RecordingEvent(event_type=event_type, payload=dict(payload))
            )
        except Exception as e:
            logger.warning(f"Ошибка публикации события {event_type}: {e}")
