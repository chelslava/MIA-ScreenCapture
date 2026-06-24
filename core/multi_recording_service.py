"""
Сервис мультиисточниковой записи для API/CLI/headless режимов (#51).

Не зависит от GUI и от основного single-recording стека
(`RecordingService`/`RecordingController`/`MainWindow`) — управляет
`MultiSourceRecorder` напрямую как отдельной логической сессией.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

from config import get_config
from core.event_bus import (
    EventBus,
    InMemoryEventBus,
    RecordingEvent,
    RecordingEventType,
)
from core.geometry import validate_rect_coords
from core.recording_service import build_recording_output_path
from logger_config import get_module_logger
from recorder.multi_source_recorder import (
    MultiCaptureSourceSpec,
    MultiSourceRecorder,
)

logger = get_module_logger(__name__)


class MultiRecordingService:
    """Headless-friendly сервис мультиисточниковой записи."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._lock = threading.Lock()
        self._event_bus = event_bus or InMemoryEventBus()
        self._recorder: MultiSourceRecorder | None = None

    @property
    def event_bus(self) -> EventBus:
        """Event bus, используемый этим сервисом (по умолчанию — свой)."""
        return self._event_bus

    def start_multi_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Запускает запись с нескольких источников одновременно."""
        with self._lock:
            if self._recorder is not None and self._recorder.is_active:
                result = {
                    "success": False,
                    "error": "Мультиисточниковая запись уже активна",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            sources_raw = params.get("sources")
            if not isinstance(sources_raw, list) or len(sources_raw) < 2:
                result = {
                    "success": False,
                    "error": "Нужно минимум 2 источника (sources)",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            try:
                sources = [self._build_source_spec(raw) for raw in sources_raw]
            except (KeyError, ValueError, TypeError) as e:
                result = {
                    "success": False,
                    "error": f"Некорректный источник: {e}",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            base_output_path = build_recording_output_path(params)
            fps = int(params.get("fps", 30))
            codec = str(params.get("codec", "libx264"))
            bitrate = str(params.get("bitrate", "2M"))
            duration = params.get("duration")
            audio_type = str(params.get("audio_type", "none"))

            recorder = MultiSourceRecorder(
                fps=fps, codec=codec, bitrate=bitrate
            )
            success, outputs, error = recorder.start(
                sources, base_output_path, duration, audio_type=audio_type
            )
            if not success:
                result = {
                    "success": False,
                    "error": error
                    or "Не удалось начать мультиисточниковую запись",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            self._recorder = recorder
            assert outputs is not None
            result = {
                "success": True,
                "outputs": {
                    label: str(path) for label, path in outputs.items()
                },
            }
            logger.info(
                f"Мультиисточниковая запись начата: {result['outputs']}"
            )
            self._publish_event(RecordingEventType.STARTED, result)
            return result

    def stop_multi_recording(self) -> dict[str, Any]:
        """Останавливает текущую мультиисточниковую запись."""
        with self._lock:
            if self._recorder is None or not self._recorder.is_active:
                result = {
                    "success": False,
                    "error": "Мультиисточниковая запись не активна",
                }
                self._publish_event(RecordingEventType.ERROR, result)
                return result

            outputs = self._recorder.stop()
            self._recorder = None

            for info in outputs.values():
                output_path = info.get("output_path")
                if not info.get("success") or not output_path:
                    continue
                try:
                    path = Path(output_path)
                    if path.exists():
                        get_config().add_recent_recording(
                            str(path), path.stat().st_size
                        )
                except OSError as e:
                    logger.warning(
                        f"Failed to update recordings list for {output_path}: {e}"
                    )

            result = {"success": True, "outputs": outputs}
            logger.info(f"Мультиисточниковая запись остановлена: {outputs}")
            self._publish_event(RecordingEventType.STOPPED, result)
            return result

    def get_multi_status(self) -> dict[str, Any]:
        """Возвращает текущий статус мультиисточниковой записи."""
        if self._recorder is None:
            return {"active": False, "sources": {}}
        return self._recorder.get_status()

    def _build_source_spec(
        self, raw: dict[str, Any]
    ) -> MultiCaptureSourceSpec:
        """Строит `MultiCaptureSourceSpec` из словаря параметров источника."""
        label = str(raw.get("label", "")).strip()
        if not label:
            raise ValueError("у источника отсутствует обязательное поле label")

        area_type = str(raw.get("area", "full"))
        if area_type not in ("full", "window", "rect"):
            area_type = "full"

        rect_value = raw.get("rect")
        rect_coords: tuple[int, int, int, int] = (0, 0, 1920, 1080)
        if isinstance(rect_value, list | tuple) and len(rect_value) >= 4:
            x1, y1, x2, y2 = (
                int(rect_value[0]),
                int(rect_value[1]),
                int(rect_value[2]),
                int(rect_value[3]),
            )
            rect_coords = validate_rect_coords(x1, y1, x2, y2, strict=True)
        elif area_type == "rect":
            raise ValueError(
                f"источник '{label}': area='rect' требует rect "
                "в формате [x1, y1, x2, y2]"
            )

        return MultiCaptureSourceSpec(
            label=label,
            area_type=area_type,  # type: ignore[arg-type]
            monitor_index=int(raw.get("monitor_index", 0)),
            window_title=str(raw.get("window_title") or ""),
            rect_coords=rect_coords,
        )

    def _publish_event(
        self, event_type: RecordingEventType, payload: dict[str, Any]
    ) -> None:
        try:
            self._event_bus.publish(
                RecordingEvent(event_type=event_type, payload=dict(payload))
            )
        except Exception as e:
            logger.warning(f"Failed to publish event {event_type}: {e}")
