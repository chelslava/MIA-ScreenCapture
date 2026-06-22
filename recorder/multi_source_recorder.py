"""
Мультиисточниковая запись (#51).

Запускает несколько независимых `VideoRecorder` (один на каждый источник —
монитор/окно/прямоугольник), каждый со своим файлом и своим
`_WindowsCaptureSession`/`FFmpegVideoWriter`. Источники не синхронизируются
по кадрам друг с другом — каждый идёт по своим таймингам, что надёжнее, чем
зависимость от самого медленного источника.

Не делает аудио-merge (как `RecordingEncoder`/`RecordingController`) —
`VideoRecorder` сам по себе пишет только видео.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from logger_config import get_module_logger
from recorder.video_recorder import CaptureArea, VideoRecorder

logger = get_module_logger(__name__)


@dataclass(frozen=True)
class MultiCaptureSourceSpec:
    """Спецификация одного источника для мультиисточниковой записи."""

    label: str
    area_type: Literal["full", "window", "rect"] = "full"
    monitor_index: int = 0
    window_title: str = ""
    rect_coords: tuple[int, int, int, int] = (0, 0, 1920, 1080)

    def build_capture_area(self) -> CaptureArea:
        """Строит `CaptureArea` для этого источника."""
        if self.area_type == "window":
            return CaptureArea.from_window(
                self.window_title, raise_if_not_found=True
            )
        if self.area_type == "rect":
            return CaptureArea.from_rect(*self.rect_coords)
        return CaptureArea.full_screen(monitor_index=self.monitor_index)


@dataclass
class _ActiveSource:
    """Запущенный источник с привязанными рекордером и путём вывода."""

    recorder: VideoRecorder
    output_path: Path


class MultiSourceRecorder:
    """
    Управляет N независимыми `VideoRecorder` как одной логической сессией.

    При неудаче запуска любого источника откатывает уже запущенные —
    ничего не остаётся в наполовину запущенном состоянии.
    """

    def __init__(
        self,
        fps: int = 30,
        codec: str = "libx264",
        bitrate: str = "2M",
        preset: str = "medium",
    ) -> None:
        self._fps = fps
        self._codec = codec
        self._bitrate = bitrate
        self._preset = preset
        self._sources: dict[str, _ActiveSource] = {}

    @property
    def is_active(self) -> bool:
        """Признак, что хотя бы один источник запущен."""
        return bool(self._sources)

    def _build_output_path(self, base_output_path: Path, label: str) -> Path:
        """Строит путь вывода для источника на основе базового пути."""
        return base_output_path.with_name(
            f"{base_output_path.stem}_{label}{base_output_path.suffix}"
        )

    def start(
        self,
        sources: list[MultiCaptureSourceSpec],
        base_output_path: Path,
        duration: float | None = None,
    ) -> tuple[bool, dict[str, Path] | None, str | None]:
        """
        Запускает запись всех источников.

        При неудаче любого источника останавливает уже запущенные и
        возвращает понятную ошибку — частично запущенной сессии не
        остаётся.

        Args:
            sources: Источники захвата (минимум 2, уникальные `label`).
            base_output_path: Базовый путь вывода — каждый источник
                получает свой файл `{stem}_{label}{suffix}`.
            duration: Опциональная длительность записи в секундах.

        Returns:
            Кортеж `(success, {label: output_path}, error_message)`.
        """
        if self.is_active:
            return False, None, "Мультиисточниковая запись уже активна"

        if len(sources) < 2:
            return False, None, "Нужно минимум 2 источника"

        labels = [s.label for s in sources]
        if len(labels) != len(set(labels)):
            return False, None, "Метки источников должны быть уникальными"

        started: dict[str, _ActiveSource] = {}
        try:
            for source in sources:
                capture_area = source.build_capture_area()
                output_path = self._build_output_path(
                    base_output_path, source.label
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)

                recorder = VideoRecorder(
                    fps=self._fps,
                    codec=self._codec,
                    bitrate=self._bitrate,
                    use_ffmpeg=True,
                    preset=self._preset,
                )
                if not recorder.start(output_path, capture_area, duration):
                    raise RuntimeError(
                        f"Не удалось запустить запись источника '{source.label}'"
                    )
                started[source.label] = _ActiveSource(
                    recorder=recorder, output_path=output_path
                )
        except (ValueError, RuntimeError) as e:
            logger.error(
                "Ошибка запуска мультиисточниковой записи, откат: %s", e
            )
            for active in started.values():
                try:
                    active.recorder.stop()
                except (OSError, RuntimeError) as stop_error:
                    logger.warning(
                        "Ошибка остановки источника при откате: %s",
                        stop_error,
                    )
            return False, None, str(e)

        self._sources = started
        logger.info(
            "Мультиисточниковая запись запущена: %s", list(started.keys())
        )
        return (
            True,
            {label: active.output_path for label, active in started.items()},
            None,
        )

    def stop(self) -> dict[str, dict[str, Any]]:
        """
        Останавливает все источники.

        Returns:
            `{label: {"success": bool, "output_path": str | None}}`.
        """
        results: dict[str, dict[str, Any]] = {}
        for label, active in self._sources.items():
            success = active.recorder.stop()
            results[label] = {
                "success": success,
                "output_path": str(active.output_path) if success else None,
            }
        self._sources = {}
        logger.info("Мультиисточниковая запись остановлена: %s", results)
        return results

    def get_status(self) -> dict[str, Any]:
        """Возвращает агрегированный статус по всем источникам."""
        return {
            "active": self.is_active,
            "sources": {
                label: {
                    "state": active.recorder.state.value,
                    "elapsed_time": active.recorder.elapsed_time,
                    "output_path": str(active.output_path),
                }
                for label, active in self._sources.items()
            },
        }
