"""
Сервис управления записью для API/CLI/Headless режимов.

Отделяет логику записи от GUI окна и предоставляет единый интерфейс
для запуска/остановки/паузы и получения статуса.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any, Optional

from config import get_config
from gui.controllers.recording_controller import RecordingController
from gui.models.recording_state import (
    AudioSettings,
    AudioType,
    CaptureSettings,
    CaptureType,
    RecordingState,
    VideoSettings,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class RecordingService:
    """Сервис записи, не требующий инициализации GUI."""

    def __init__(self) -> None:
        self._state = RecordingState()
        self._controller = RecordingController(self._state)
        self._lock = threading.Lock()

    def get_status(self) -> dict[str, Any]:
        """Возвращает текущий статус записи."""
        return {
            "is_recording": self._state.is_recording(),
            "is_paused": self._state.is_paused(),
            "elapsed_time": self._controller.elapsed_time,
            "current_file": str(self._state.current_output)
            if self._state.current_output
            else None,
        }

    def start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Запускает запись из API/планировщика параметров.

        Поддерживает как API-формат, так и internal-формат ключей:
        - area / area_type
        - rect / rect_coords
        - audio / audio_type
        """
        with self._lock:
            if self._state.is_recording():
                return {"success": False, "error": "Запись уже идёт"}

            try:
                normalized = self._normalize_params(params)
                capture = self._build_capture_settings(normalized)
                audio = self._build_audio_settings(normalized)
                video = self._build_video_settings(normalized)
                output_path = self._build_output_path(normalized)
                duration = normalized.get("duration")

                success, error_msg = self._controller.start_recording(
                    output_path=output_path,
                    capture=capture,
                    audio=audio,
                    video=video,
                    duration=duration,
                )
                if not success:
                    return {
                        "success": False,
                        "error": error_msg or "Не удалось запустить запись",
                    }

                logger.info(f"Запись запущена: {output_path}")
                return {"success": True, "output_path": str(output_path)}

            except Exception as e:
                logger.error(f"Ошибка запуска записи: {e}", exc_info=True)
                return {"success": False, "error": str(e)}

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает текущую запись."""
        with self._lock:
            if not self._state.is_recording() and not self._state.is_paused():
                return {"success": False, "error": "Запись не идёт"}

            output_path = self._controller.stop_recording()
            if not output_path:
                return {"success": False, "error": "Не удалось сохранить запись"}

            try:
                if output_path.exists():
                    get_config().add_recent_recording(
                        str(output_path), output_path.stat().st_size
                    )
            except Exception as e:
                # Ошибка обновления recent recordings не должна ломать stop.
                logger.warning(f"Не удалось обновить список записей: {e}")

            logger.info(f"Запись остановлена: {output_path}")
            return {"success": True, "filepath": str(output_path)}

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу текущей записи."""
        with self._lock:
            if not self._state.is_recording() and not self._state.is_paused():
                return {"success": False, "error": "Запись не идёт"}

            if self._state.is_paused():
                resumed = self._controller.resume_recording()
                if not resumed:
                    return {"success": False, "error": "Не удалось возобновить"}
                return {"success": True, "is_paused": False}

            paused = self._controller.pause_recording()
            if not paused:
                return {"success": False, "error": "Не удалось поставить на паузу"}
            return {"success": True, "is_paused": True}

    def get_recordings(self) -> list[dict[str, Any]]:
        """Возвращает список последних записей из конфигурации."""
        return get_config().settings.recent_recordings

    def stop_active_recording_if_any(self) -> Optional[dict[str, Any]]:
        """Безопасно останавливает активную запись, если она есть."""
        with self._lock:
            if not self._state.is_recording() and not self._state.is_paused():
                return None
        return self.stop_recording()

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(params)
        normalized["area"] = params.get("area", params.get("area_type", "full"))
        normalized["rect"] = params.get("rect", params.get("rect_coords"))
        normalized["audio"] = params.get("audio", params.get("audio_type", "none"))
        return normalized

    def _build_capture_settings(self, params: dict[str, Any]) -> CaptureSettings:
        area = params.get("area", "full")
        capture_type_map = {
            "full": CaptureType.FULL_SCREEN,
            "window": CaptureType.WINDOW,
            "rect": CaptureType.RECTANGLE,
        }
        capture_type = capture_type_map.get(area, CaptureType.FULL_SCREEN)

        rect_value = params.get("rect")
        rect_coords: tuple[int, int, int, int]
        if isinstance(rect_value, (list, tuple)) and len(rect_value) >= 4:
            rect_coords = (
                int(rect_value[0]),
                int(rect_value[1]),
                int(rect_value[2]),
                int(rect_value[3]),
            )
        else:
            # fallback на full-hd, если координаты не переданы
            rect_coords = (0, 0, 1920, 1080)

        return CaptureSettings(
            capture_type=capture_type,
            window_title=params.get("window_title", "") or "",
            rect_coords=rect_coords,
        )

    def _build_audio_settings(self, params: dict[str, Any]) -> AudioSettings:
        audio_map = {
            "none": AudioType.NONE,
            "mic": AudioType.MICROPHONE,
            "system": AudioType.SYSTEM,
            "both": AudioType.BOTH,
        }
        audio_type = audio_map.get(str(params.get("audio", "none")), AudioType.NONE)
        return AudioSettings(
            audio_type=audio_type,
            mic_device_index=params.get("mic_device_index"),
        )

    def _build_video_settings(self, params: dict[str, Any]) -> VideoSettings:
        config = get_config().settings.video
        return VideoSettings(
            fps=int(params.get("fps", config.fps)),
            codec=str(params.get("codec", config.codec)),
            bitrate=str(params.get("bitrate", config.bitrate)),
            format=str(params.get("format", config.format)),
        )

    def _build_output_path(self, params: dict[str, Any]) -> Path:
        value = params.get("output_path")
        if value:
            return Path(value)
        return get_config().get_output_path()

