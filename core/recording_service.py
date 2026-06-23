"""
Recording management service for API/CLI/Headless modes.

Decouples recording logic from the GUI window and provides a unified interface
for start/stop/pause and status retrieval.
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
from recorder.utils import attempt_repair_video, verify_video_integrity

logger = get_module_logger(__name__)


def build_recording_output_path(params: dict[str, Any]) -> Path:
    """
    Строит путь вывода записи из params API/CLI (`output_path` опционален).

    Общая логика для `RecordingService` и `MultiRecordingService` (#51) —
    оба принимают одинаковый необязательный `output_path` (файл, директория
    или пусто — тогда генерируется путь по умолчанию).
    """
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


class RecordingService:
    """Recording service that does not require GUI initialization."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        backend: RecordingBackend | None = None,
    ) -> None:
        """
        Initializes the recording service.

        Args:
            event_bus: Event bus for transport integration (e.g. WebSocket).
                Defaults to a fresh `InMemoryEventBus()` if not provided.
            backend: `RecordingBackend` implementation (e.g. `GUIRecordingBackend`).

        Raises:
            ValueError: If `backend` is not provided.
        """
        if backend is None:
            raise ValueError(
                "backend is required. Pass a GUIRecordingBackend or another "
                "RecordingBackend implementation."
            )
        self._backend = backend
        self._lock = threading.Lock()
        self._event_bus = event_bus or InMemoryEventBus()

    @property
    def event_bus(self) -> EventBus:
        """Returns event bus for integration with transports (e.g., WebSocket)."""
        return self._event_bus

    def get_status(self) -> dict[str, Any]:
        """
        Returns current recording status.

        Raises:
            Не выбрасывает исключений напрямую — делегирует в
            `backend.get_status()` без собственной обработки ошибок;
            любое исключение реализации `RecordingBackend` распространяется
            вызывающему как есть.
        """
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
        Start recording from API/scheduler parameters.

        Supports both API-format and internal-format keys:
        - area / area_type
        - rect / rect_coords
        - audio / audio_type

        Raises:
            Не выбрасывает исключений в штатной работе: `RecordingError`,
            `OSError` и `ValueError` от валидации параметров/backend
            перехватываются внутри и сообщаются через
            `result["success"] = False` / `result["error"]`.
        """
        with self._lock:
            backend_status = self._backend.get_status()
            if backend_status.is_recording or backend_status.is_paused:
                result = {
                    "success": False,
                    "error": "Recording already in progress",
                }
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
                        "error": error_msg or "Failed to start recording",
                    }
                    self._publish_event(RecordingEventType.ERROR, result)
                    return result

                logger.info(f"Recording started: {output_path}")
                result = {"success": True, "output_path": str(output_path)}
                self._publish_event(RecordingEventType.STARTED, result)
                return result

            except RecordingError as e:
                logger.error(f"Recording start error: {e}")
                result = {"success": False, "error": str(e)}
                self._publish_event(RecordingEventType.ERROR, result)
                return result
            except (OSError, ValueError) as e:
                logger.error(
                    f"System error starting recording: {e}", exc_info=True
                )
                result = {"success": False, "error": str(e)}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

    def stop_recording(self) -> dict[str, Any]:
        """
        Stops current recording.

        Raises:
            Не выбрасывает исключений в штатной работе: ошибка обновления
            списка последних записей (`OSError`) и сбой верификации
            целостности (любой `Exception`) перехватываются внутри и
            только логируются — на результат `stop()` не влияют.
        """
        with self._lock:
            backend_status = self._backend.get_status()
            if (
                not backend_status.is_recording
                and not backend_status.is_paused
            ):
                result = {"success": False, "error": "Recording is not active"}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            output_path = self._backend.stop()
            if not output_path:
                result = {
                    "success": False,
                    "error": "Failed to save recording",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            try:
                if output_path.exists():
                    get_config().add_recent_recording(
                        str(output_path), output_path.stat().st_size
                    )
            except OSError as e:
                # Recording recent update failure must not abort stop.
                logger.warning(f"Failed to update recordings list: {e}")

            logger.info(f"Recording stopped: {output_path}")
            result = {
                "success": True,
                "filepath": str(output_path),
            }
            try:
                integrity = self._verify_recording(output_path)
                if integrity is not None:
                    result["integrity"] = integrity
            except Exception as e:
                # Верификация не должна мешать успешному завершению stop().
                logger.warning(
                    f"Integrity verification failed unexpectedly: {e}"
                )

            self._publish_event(RecordingEventType.STOPPED, result)
            return result

    def _verify_recording(self, output_path: Path) -> dict[str, Any] | None:
        """
        Проверяет целостность записанного файла через ffprobe (#46).

        При включённом `auto_repair_corrupted` и невалидном результате
        пытается восстановить файл ремуксом. Никогда не удаляет и не
        блокирует сохранение исходного файла — только репортит результат.

        Returns:
            Словарь с результатом проверки, либо `None`, если проверка
            отключена в настройках (`verify_on_complete=False`).
        """
        video_settings = get_config().settings.video
        if not video_settings.verify_on_complete:
            return None

        check = verify_video_integrity(output_path)
        if check.valid:
            return {"valid": True, "repaired": False}

        if not video_settings.auto_repair_corrupted:
            logger.warning(
                f"Запись не прошла проверку целостности: {output_path} "
                f"({check.error})"
            )
            return {"valid": False, "repaired": False, "error": check.error}

        repair = attempt_repair_video(output_path)
        if not repair.repaired:
            logger.warning(
                f"Не удалось восстановить повреждённую запись: "
                f"{output_path} ({repair.error})"
            )
            return {
                "valid": False,
                "repaired": False,
                "error": repair.error or check.error,
            }

        logger.info(
            f"Запись восстановлена после проверки целостности: {output_path}"
        )
        return {"valid": True, "repaired": True}

    def toggle_pause(self) -> dict[str, Any]:
        """
        Toggles pause of current recording.

        Raises:
            Не выбрасывает исключений — `backend.pause()`/`backend.resume()`
            сообщают о неудаче через возвращаемое булево значение, а не
            исключение.
        """
        with self._lock:
            backend_status = self._backend.get_status()
            if (
                not backend_status.is_recording
                and not backend_status.is_paused
            ):
                result = {"success": False, "error": "Recording is not active"}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            if backend_status.is_paused:
                resumed = self._backend.resume()
                if not resumed:
                    result = {
                        "success": False,
                        "error": "Failed to resume",
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
                    "error": "Failed to pause",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result
            result = {"success": True, "is_paused": True}
            self._publish_event(RecordingEventType.PAUSED, result)
            return result

    def switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Переключает источник захвата активной записи без остановки (#48).

        Raises:
            Не выбрасывает исключений: `ValueError` от валидации параметров
            перехватывается внутри и сообщается через `result["error"]`.
        """
        with self._lock:
            backend_status = self._backend.get_status()
            if (
                not backend_status.is_recording
                and not backend_status.is_paused
            ):
                result = {"success": False, "error": "Recording is not active"}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            try:
                normalized = self._normalize_params(params)
                capture = self._build_capture_settings(normalized)
            except ValueError as e:
                result = {"success": False, "error": str(e)}
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            success, error_msg = self._backend.switch_capture_source(capture)
            if not success:
                result = {
                    "success": False,
                    "error": error_msg or "Failed to switch capture source",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            result = {"success": True}
            self._publish_event(
                RecordingEventType.CAPTURE_SOURCE_SWITCHED, result
            )
            return result

    def get_recordings(self) -> list[dict[str, Any]]:
        """
        Returns list of recent recordings from configuration.

        Raises:
            Не выбрасывает исключений напрямую — распространяет любое
            исключение `get_config()` (например, при повреждённом
            конфиге), если оно возникнет.
        """
        return cast(
            list[dict[str, Any]], get_config().settings.recent_recordings
        )

    def stop_active_recording_if_any(self) -> dict[str, Any] | None:
        """
        Safely stops active recording if any.

        Raises:
            Не выбрасывает исключений напрямую — см. `stop_recording()`
            (вызывается внутри при активной записи).
        """
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
        Validates capture area coordinates.

        Uses common validate_rect_coords from core.geometry
        in strict mode to check coordinate order correctness.

        Args:
            rect: List or tuple of 4 coordinates [x1, y1, x2, y2].

        Returns:
            Tuple (x1, y1, x2, y2).

        Raises:
            ValueError: If coordinates are invalid.
        """
        if len(rect) != 4:
            raise ValueError(
                f"rect must contain 4 coordinates [x1, y1, x2, y2], "
                f"got {len(rect)}"
            )
        x1, y1, x2, y2 = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
        # Use common function with strict=True for validation
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
                "area='rect' requires valid rect_coords "
                "in format [x1, y1, x2, y2]"
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
        return build_recording_output_path(params)

    def _publish_event(
        self, event_type: RecordingEventType, payload: dict[str, Any]
    ) -> None:
        try:
            self._event_bus.publish(
                RecordingEvent(event_type=event_type, payload=dict(payload))
            )
        except Exception as e:
            logger.warning(f"Failed to publish event {event_type}: {e}")
