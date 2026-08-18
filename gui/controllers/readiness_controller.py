"""
Контроллер готовности системы к записи и диагностики
===================================================

Отвечает за:
- асинхронную проверку зависимостей (FFmpeg, кодеки);
- оценку параметров готовности (preflight readiness snapshot);
- кэширование и разрешение результатов проверок готовности;
- диспетчеризацию быстрых действий (one-click fixes) из readiness center.
"""

from __future__ import annotations

import threading
import webbrowser
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.readiness import (
    ReadinessSnapshot,
    RecordingReadinessService,
)
from gui.models.recording_state import AudioSettings, CaptureSettings
from logger_config import get_module_logger
from recorder.utils import FFmpegStatus, check_ffmpeg

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)


class ReadinessController:
    """Контроллер готовности к записи и проверки зависимостей."""

    def __init__(
        self,
        readiness_service: RecordingReadinessService,
        track_thread: Callable[[threading.Thread], threading.Thread]
        | None = None,
    ) -> None:
        self._readiness_service = readiness_service
        self._track_thread = track_thread or (lambda t: t)
        self._readiness_request_id: int = 0
        self._latest_readiness_snapshot: ReadinessSnapshot | None = None
        self._latest_readiness_inputs: dict[str, Any] | None = None

    @property
    def latest_snapshot(self) -> ReadinessSnapshot | None:
        """Последний полученный readiness snapshot."""
        return self._latest_readiness_snapshot

    @property
    def latest_inputs(self) -> dict[str, Any] | None:
        """Входные параметры последнего readiness snapshot."""
        return self._latest_readiness_inputs

    def check_dependencies(
        self,
        on_completed: Callable[[FFmpegStatus | None, str | None], None],
    ) -> None:
        """Запуск асинхронной проверки внешних зависимостей (FFmpeg)."""

        def worker() -> None:
            try:
                result = check_ffmpeg()
                on_completed(result, None)
            except Exception as error:
                on_completed(None, str(error))

        t = threading.Thread(target=worker, daemon=True)
        self._track_thread(t)
        t.start()

    def request_readiness_refresh(
        self,
        capture: CaptureSettings,
        audio: AudioSettings,
        output_path: Path,
        on_completed: Callable[
            [
                int,
                ReadinessSnapshot | None,
                str | None,
                CaptureSettings,
                AudioSettings,
            ],
            None,
        ],
    ) -> int:
        """Запуск фоновой оценки параметров готовности к записи."""
        self._readiness_request_id += 1
        request_id = self._readiness_request_id

        def worker() -> None:
            try:
                snapshot = self._readiness_service.evaluate(
                    capture=capture,
                    audio=audio,
                    output_path=output_path,
                )
                on_completed(request_id, snapshot, None, capture, audio)
            except Exception as error:
                on_completed(request_id, None, str(error), capture, audio)

        t = threading.Thread(target=worker, daemon=True)
        self._track_thread(t)
        t.start()
        return request_id

    def is_request_current(self, request_id: int) -> bool:
        """Проверяет, актуален ли ID запроса готовности."""
        return request_id == self._readiness_request_id

    def store_readiness_result(
        self,
        snapshot: ReadinessSnapshot,
        capture: CaptureSettings,
        audio: AudioSettings,
        output_path: Path,
    ) -> None:
        """Сохраняет актуальный снимок готовности в кэш."""
        self._latest_readiness_snapshot = snapshot
        self._latest_readiness_inputs = {
            "capture": capture,
            "audio": audio,
            "output_path": output_path,
        }

    def resolve_cached_snapshot(
        self,
        capture: CaptureSettings | None,
        audio: AudioSettings,
        output_path: Path,
    ) -> ReadinessSnapshot | None:
        """Возвращает закэшированный снимок готовности, если входные параметры совпадают."""
        latest_inputs = self._latest_readiness_inputs
        if latest_inputs is None or self._latest_readiness_snapshot is None:
            return None

        if (
            latest_inputs.get("capture") == capture
            and latest_inputs.get("audio") == audio
            and latest_inputs.get("output_path") == output_path
        ):
            return self._latest_readiness_snapshot
        return None

    def handle_readiness_action(
        self,
        action_key: str,
        action_handlers: dict[str, Callable[[], None]],
    ) -> None:
        """Выполнить быстрый переход/действие по исправлению проблемы готовности."""
        if action_key == "open_ffmpeg_docs":
            webbrowser.open("https://ffmpeg.org/download.html")
            return

        fallback_action_map = {
            "Папка вывода": "choose_output_path",
            "Аудиоустройства": "refresh_audio_devices",
            "Окно захвата": "refresh_windows",
            "FFmpeg": "open_ffmpeg_docs",
        }
        resolved_key = fallback_action_map.get(action_key, action_key)
        handler = action_handlers.get(resolved_key)
        if handler:
            handler()
