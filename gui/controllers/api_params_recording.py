"""
Запуск записи по параметрам из API (#164)
=========================================

Миксин ``ApiParamsRecordingMixin`` вынесен из ``gui/main_window.py``:
публичные методы ``start_recording_with_params``/``switch_capture_source``,
вызываемые ``ApplicationFacade`` в headless/API-режиме.
``MainWindow`` наследует миксин — методы доступны как раньше.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.recording_types import AudioMode, CaptureMode
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    VideoSettings,
)
from logger_config import get_module_logger

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QMainWindow

    from core.readiness import RecordingReadinessService
    from gui.controllers.recording_controller import RecordingController
    from gui.controllers.settings_controller import SettingsController
    from gui.models.recording_state import RecordingState
    from gui.views.video_view import VideoView

logger = get_module_logger(__name__)


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class ApiParamsRecordingMixin(_QWindowBase):
    """Параметрический старт записи и переключение источника захвата."""

    if TYPE_CHECKING:
        # Общие атрибуты окна
        _state: RecordingState
        _recording_controller: RecordingController
        _settings_controller: SettingsController
        _readiness_service: RecordingReadinessService
        _video_view: VideoView

        # Методы MainWindow (реализация — в RecordingFlowControllerMixin)
        _on_recording_started: Callable[..., None]

    def start_recording_with_params(self, params: dict) -> dict:
        """
        Запуск записи с параметрами из API.

        Args:
            params: Словарь с параметрами записи
                - area: "full" | "window" | "rect"
                - window_title: str (опционально)
                - rect: [x1, y1, x2, y2] (опционально)
                - audio: "mic" | "system" | "none" | "both"
                - fps: int (опционально)
                - codec: str (опционально)
                - bitrate: str (опционально)
                - duration: int (опционально)
                - output_path: str (опционально)

        Returns:
            Словарь с результатом операции
        """
        if self._state.is_recording():
            return {"success": False, "error": "Запись уже идёт"}

        try:
            # Определение типа захвата
            area_type = params.get("area", "full")
            capture_type_map = {
                "full": CaptureMode.FULL,
                "window": CaptureMode.WINDOW,
                "rect": CaptureMode.RECT,
            }
            capture_type = capture_type_map.get(area_type, CaptureMode.FULL)

            # Координаты прямоугольника
            rect_coords = None
            if area_type == "rect" and "rect" in params:
                r = params["rect"]
                if isinstance(r, list | tuple) and len(r) >= 4:
                    rect_coords = (r[0], r[1], r[2], r[3])
                else:
                    return {
                        "success": False,
                        "error": "rect должен содержать 4 координаты [x1, y1, x2, y2]",
                    }

            # Настройки захвата
            capture = CaptureSettings(
                capture_type=capture_type,
                window_title=params.get("window_title") or "",
                rect_coords=rect_coords or (0, 0, 1920, 1080),
            )

            # Настройки аудио
            audio_type_map = {
                "mic": AudioMode.MIC,
                "system": AudioMode.SYSTEM,
                "none": AudioMode.NONE,
                "both": AudioMode.BOTH,
            }
            audio_type = audio_type_map.get(
                params.get("audio", "mic"), AudioMode.MIC
            )
            # Используем метод состояния для thread-safe изменения
            self._state.set_audio_type(audio_type)
            audio_settings = AudioSettings(
                audio_type=audio_type,
                mic_device_index=params.get("mic_device_index"),
            )

            # Настройки видео (создаём копию для избежания race condition)
            base_settings = self._video_view.get_settings()
            video_settings = VideoSettings(
                fps=params.get("fps", base_settings.fps),
                codec=params.get("codec", base_settings.codec),
                bitrate=params.get("bitrate", base_settings.bitrate),
                format=base_settings.format,
            )

            # Путь вывода
            output_path = self._resolve_requested_output_path(
                params.get("output_path"),
                video_settings.format,
            )
            readiness = self._readiness_service.evaluate(
                capture=capture,
                audio=audio_settings,
                output_path=output_path,
            )
            if not readiness.is_ready:
                return {
                    "success": False,
                    "error": readiness.summary_text(),
                    "details": [issue.message for issue in readiness.issues],
                }

            # Запуск записи
            success, error_msg = self._recording_controller.start_recording(
                output_path=output_path,
                capture=capture,
                audio=audio_settings,
                video=video_settings,
            )

            if success:
                self._on_recording_started(output_path, capture)
                return {
                    "success": True,
                    "output_path": str(output_path),
                }
            else:
                return {
                    "success": False,
                    "error": error_msg or "Не удалось запустить запись",
                }

        except Exception as e:
            logger.error(f"Ошибка запуска записи: {e}")
            return {"success": False, "error": str(e)}

    def switch_capture_source(self, params: dict) -> dict:
        """
        Переключает источник захвата активной записи без остановки (#48).

        Args:
            params: Словарь с параметрами нового источника захвата
                - area: "full" | "window" | "rect"
                - window_title: str (опционально)
                - rect: [x1, y1, x2, y2] (опционально)

        Returns:
            Словарь с результатом операции.
        """
        if not self._state.is_recording():
            return {"success": False, "error": "Запись не активна"}

        area_type = params.get("area", "full")
        capture_type_map = {
            "full": CaptureMode.FULL,
            "window": CaptureMode.WINDOW,
            "rect": CaptureMode.RECT,
        }
        capture_type = capture_type_map.get(area_type, CaptureMode.FULL)

        rect_coords = None
        if area_type == "rect" and "rect" in params:
            r = params["rect"]
            if isinstance(r, list | tuple) and len(r) >= 4:
                rect_coords = (r[0], r[1], r[2], r[3])
            else:
                return {
                    "success": False,
                    "error": "rect должен содержать 4 координаты [x1, y1, x2, y2]",
                }

        capture = CaptureSettings(
            capture_type=capture_type,
            window_title=params.get("window_title") or "",
            rect_coords=rect_coords or (0, 0, 1920, 1080),
            strict_window_match=True,
        )

        success, error_msg = self._recording_controller.switch_capture_source(
            capture
        )
        if success:
            return {"success": True}
        return {
            "success": False,
            "error": error_msg or "Не удалось переключить источник захвата",
        }

    def _resolve_requested_output_path(
        self,
        requested_output_path: Any,
        output_format: str,
    ) -> Path:
        """Преобразование output_path из API в конечный путь файла."""
        if requested_output_path is None:
            return Path(str(self._settings_controller.get_output_path()))

        raw_path = str(requested_output_path).strip()
        if not raw_path:
            return Path(str(self._settings_controller.get_output_path()))

        candidate = Path(raw_path)
        is_dir_hint = raw_path.endswith(("/", "\\"))
        if is_dir_hint or (candidate.exists() and candidate.is_dir()):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = output_format.lstrip(".")
            return Path(candidate, f"recording_{timestamp}.{extension}")

        if candidate.suffix:
            return Path(str(candidate))

        extension = output_format.lstrip(".")
        return Path(str(candidate.with_suffix(f".{extension}")))
