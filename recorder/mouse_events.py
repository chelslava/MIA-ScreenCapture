"""Сбор событий мыши для авто-zoom и расчёт сегментов зума (#170).

Sidecar-запись (JSONL: ``{"t": <сек от начала>, "x": .., "y": ..}``)
ведётся рядом с видео только при явном включении — по умолчанию
выключена. Чистые функции модуля детерминированы и покрыты тестами.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)

DEFAULT_ACTIVITY_WINDOW_S = 1.0
DEFAULT_MIN_SEGMENT_S = 0.5
DEFAULT_ZOOM_LEVEL = 1.5
SEGMENT_MERGE_GAP_S = 0.75


@dataclass(frozen=True)
class MouseEvent:
    """Событие перемещения/клика мыши с таймкодом от начала записи."""

    t: float
    x: int
    y: int


@dataclass(frozen=True)
class ZoomSegment:
    """Непрерывный сегмент с активностью мыши для наложения зума."""

    start_s: float
    end_s: float

    @property
    def duration_s(self) -> float:
        """Длительность сегмента в секундах."""
        return self.end_s - self.start_s


def parse_mouse_events(raw_lines: list[str]) -> list[MouseEvent]:
    """Разобрать строки sidecar-файла в события (#170).

    Args:
        raw_lines: Строки JSONL (битые строки пропускаются).

    Returns:
        События, отсортированные по времени.
    """
    events: list[MouseEvent] = []
    for line in raw_lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            events.append(
                MouseEvent(
                    t=float(payload["t"]),
                    x=int(payload.get("x", 0)),
                    y=int(payload.get("y", 0)),
                )
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            logger.debug("Битая строка sidecar мыши пропущена: %r", line)
    events.sort(key=lambda event: event.t)
    return events


def build_zoom_segments(
    events: list[MouseEvent],
    video_duration_s: float,
    activity_window_s: float = DEFAULT_ACTIVITY_WINDOW_S,
    min_segment_s: float = DEFAULT_MIN_SEGMENT_S,
) -> list[ZoomSegment]:
    """Рассчитать сегменты зума по событиям мыши (#170).

    Активность — события, идущие чаще, чем раз в `activity_window_s`;
    соседние активные точки сливаются, затем сегменты короче
    `min_segment_s` отбрасываются (хвост последней активности
    расширяется на окно — реакция после последнего события).

    Args:
        events: События мыши с таймкодами.
        video_duration_s: Длительность видео (сегменты обрезаются ею).
        activity_window_s: Окно «тишины», закрывающее сегмент.
        min_segment_s: Минимальная длительность сегмента зума.

    Returns:
        Непересекающиеся сегменты по возрастанию времени.
    """
    if not events or video_duration_s <= 0:
        return []

    # Кластеризация: события ближе activity_window_s — одна активность
    clusters: list[list[MouseEvent]] = [[events[0]]]
    for event in events[1:]:
        if event.t - clusters[-1][-1].t <= activity_window_s:
            clusters[-1].append(event)
        else:
            clusters.append([event])

    segments: list[ZoomSegment] = []
    for cluster in clusters:
        start = max(cluster[0].t - activity_window_s / 2, 0.0)
        end = min(cluster[-1].t + activity_window_s, video_duration_s)
        if end <= start:
            continue
        segments.append(
            ZoomSegment(start_s=round(start, 3), end_s=round(end, 3))
        )

    # Слияние пересекающихся после расширения окон
    merged: list[ZoomSegment] = []
    for segment in segments:
        if (
            merged
            and segment.start_s - merged[-1].end_s <= SEGMENT_MERGE_GAP_S
        ):
            prev = merged[-1]
            merged[-1] = ZoomSegment(
                start_s=prev.start_s,
                end_s=max(prev.end_s, segment.end_s),
            )
        else:
            merged.append(segment)

    return [s for s in merged if s.duration_s >= min_segment_s]


class MouseEventsRecorder:
    """Sidecar-запись событий мыши во время записи (#170).

    Таймкоды — от `start()`; события пишутся JSONL-строками.
    Слушатель pynput в фоновом потоке; при недоступности pynput
    запись событий не ведётся (зум просто не будет наложен).
    """

    def __init__(self, sidecar_path: Path) -> None:
        """Инициализировать рекордер событий.

        Args:
            sidecar_path: Путь JSONL-файла событий.
        """
        self._sidecar_path = sidecar_path
        self._listener: Any = None
        self._file: Any = None
        self._started_at: float = 0.0

    @property
    def is_running(self) -> bool:
        """Ведётся ли запись событий."""
        return self._listener is not None

    def start(self) -> bool:
        """Начать сбор событий мыши.

        Returns:
            `True`, если слушатель запущен и файл открыт.
        """
        if self.is_running:
            return False
        try:
            from pynput import mouse
        except ImportError:
            logger.warning(
                "pynput недоступен — sidecar событий мыши не ведётся"
            )
            return False

        try:
            self._sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self._sidecar_path.open("w", encoding="utf-8")
        except OSError as e:
            logger.warning("Не удалось открыть sidecar мыши: %s", e)
            return False

        self._started_at = time.monotonic()

        listener = mouse.Listener(on_move=self._on_move)
        listener.daemon = True
        listener.start()
        self._listener = listener
        logger.info("Сбор событий мыши запущен: %s", self._sidecar_path)
        return True

    def stop(self) -> Path | None:
        """Остановить сбор и закрыть sidecar.

        Returns:
            Путь sidecar при наличии событий, иначе `None`.
        """
        if self._listener is not None:
            try:
                self._listener.stop()
            except (OSError, RuntimeError) as e:
                logger.warning("Ошибка остановки слушателя мыши: %s", e)
            self._listener = None
        file = self._file
        self._file = None
        if file is not None:
            try:
                file.close()
            except OSError as e:
                logger.warning("Ошибка закрытия sidecar мыши: %s", e)
        if self._sidecar_path.exists() and self._sidecar_path.stat().st_size:
            return self._sidecar_path
        return None

    def _on_move(self, x: int, y: int) -> None:
        """Колбэк pynput: записать событие с таймкодом (#170).

        Args:
            x: Абсцисса курсора.
            y: Ордината курсора.
        """
        file = self._file
        if file is None:
            return
        elapsed = time.monotonic() - self._started_at
        try:
            file.write(
                json.dumps({"t": round(elapsed, 3), "x": int(x), "y": int(y)})
                + "\n"
            )
        except (OSError, ValueError):
            return
