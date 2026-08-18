"""
Конвейер выполнения шагов постобработки видеозаписей
====================================================

Инкапсулирует:
- последовательное или изолированное выполнение шагов;
- обработку критических (fatal) и некритических ошибок;
- публикацию событий в EventBus;
- запуск конвейера в отдельном потоке (фоновое исполнение).
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from core.event_bus import EventBus, RecordingEvent, RecordingEventType
from core.post_processing.steps import PostProcessingStep
from core.post_processing.types import (
    PipelineResult,
    PostProcessingStatus,
    StepResult,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class PostRecordingPipeline:
    """Конвейер шагов постобработки видеофайла после завершения записи."""

    def __init__(
        self,
        steps: list[PostProcessingStep] | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._steps: list[PostProcessingStep] = list(steps or [])
        self._event_bus = event_bus
        self._is_cancelled = False
        self._lock = threading.Lock()
        self._current_thread: threading.Thread | None = None

    @property
    def steps(self) -> list[PostProcessingStep]:
        """Список шагов конвейера."""
        return self._steps

    def add_step(self, step: PostProcessingStep) -> None:
        """Добавить шаг в конвейер."""
        self._steps.append(step)

    def cancel(self) -> None:
        """Запросить отмену конвейера."""
        with self._lock:
            self._is_cancelled = True

    def execute(self, initial_path: Path) -> PipelineResult:
        """
        Синхронное последовательное выполнение всех шагов конвейера.

        Args:
            initial_path: Путь к исходному видеофайлу.

        Returns:
            PipelineResult с результатами всех шагов.
        """
        start_time = time.monotonic()
        step_results: list[StepResult] = []
        current_path = initial_path

        with self._lock:
            if self._is_cancelled:
                logger.warning("Постобработка была отменена до запуска")
                result = PipelineResult(
                    status=PostProcessingStatus.CANCELLED,
                    initial_input_path=initial_path,
                    final_output_path=current_path,
                    step_results=[],
                    total_duration_seconds=0.0,
                    error_message="Постобработка отменена",
                )
                self._emit_event(
                    RecordingEventType.WARNING,
                    "post_processing.cancelled",
                    result.to_dict(),
                )
                return result

        self._emit_event(
            RecordingEventType.PROGRESS,
            "post_processing.started",
            {
                "input_path": str(initial_path),
                "steps_count": len(self._steps),
            },
        )

        logger.info(
            "Старт постобработки для %s (шагов: %d)",
            initial_path.name,
            len(self._steps),
        )

        for step in self._steps:
            with self._lock:
                if self._is_cancelled:
                    logger.warning("Постобработка отменена пользователем")
                    total_dur = time.monotonic() - start_time
                    result = PipelineResult(
                        status=PostProcessingStatus.CANCELLED,
                        initial_input_path=initial_path,
                        final_output_path=current_path,
                        step_results=step_results,
                        total_duration_seconds=total_dur,
                        error_message="Постобработка отменена",
                    )
                    self._emit_event(
                        RecordingEventType.WARNING,
                        "post_processing.cancelled",
                        result.to_dict(),
                    )
                    return result

            logger.info(
                "Выполнение шага постобработки: %s", step.step_type.value
            )
            try:
                step_res = step.execute(current_path)
            except Exception as e:
                logger.error(
                    "Исключение в шаге %s: %s", step.step_type.value, e
                )
                step_res = StepResult(
                    step_type=step.step_type,
                    success=False,
                    input_path=current_path,
                    error_message=str(e),
                    is_fatal=step.is_fatal,
                )

            step_results.append(step_res)

            self._emit_event(
                RecordingEventType.PROGRESS
                if step_res.success
                else RecordingEventType.WARNING,
                "post_processing.step_completed",
                step_res.to_dict(),
            )

            if step_res.success:
                # Если шаг породил новый файл видео, используем его как вход для следующих
                if step_res.output_path and step_res.output_path.exists():
                    current_path = step_res.output_path
            else:
                logger.warning(
                    "Шаг %s завершился с ошибкой: %s (fatal=%s)",
                    step.step_type.value,
                    step_res.error_message,
                    step.is_fatal,
                )
                if step.is_fatal:
                    total_dur = time.monotonic() - start_time
                    result = PipelineResult(
                        status=PostProcessingStatus.FAILED,
                        initial_input_path=initial_path,
                        final_output_path=current_path,
                        step_results=step_results,
                        total_duration_seconds=total_dur,
                        error_message=step_res.error_message,
                    )
                    self._emit_event(
                        RecordingEventType.ERROR,
                        "post_processing.failed",
                        result.to_dict(),
                    )
                    return result

        total_dur = time.monotonic() - start_time
        final_result = PipelineResult(
            status=PostProcessingStatus.COMPLETED,
            initial_input_path=initial_path,
            final_output_path=current_path,
            step_results=step_results,
            total_duration_seconds=total_dur,
        )

        self._emit_event(
            RecordingEventType.PROGRESS,
            "post_processing.completed",
            final_result.to_dict(),
        )

        logger.info(
            "Постобработка для %s успешно завершена за %.2fс. Итоговый файл: %s",
            initial_path.name,
            total_dur,
            current_path.name,
        )
        return final_result

    def run_in_background(
        self,
        initial_path: Path,
        on_finished: Callable[[PipelineResult], None] | None = None,
    ) -> threading.Thread:
        """
        Запуск выполнения конвейера в отдельном потоке.

        Args:
            initial_path: Путь к исходному видеофайлу.
            on_finished: Callback при завершении конвейера.

        Returns:
            Объект запущенного потока threading.Thread.
        """

        def _worker() -> None:
            try:
                res = self.execute(initial_path)
            except Exception as e:
                logger.error(
                    "Критическая ошибка конвейера постобработки: %s", e
                )
                res = PipelineResult(
                    status=PostProcessingStatus.FAILED,
                    initial_input_path=initial_path,
                    final_output_path=initial_path,
                    total_duration_seconds=0.0,
                    error_message=str(e),
                )
            if on_finished is not None:
                try:
                    on_finished(res)
                except Exception as cb_err:
                    logger.error("Ошибка в callback постобработки: %s", cb_err)

        thread = threading.Thread(
            target=_worker,
            name=f"PostProcessingPipeline-{initial_path.name}",
            daemon=True,
        )
        self._current_thread = thread
        thread.start()
        return thread

    def _emit_event(
        self,
        event_type: RecordingEventType,
        action: str,
        data: dict[str, Any],
    ) -> None:
        """Вспомогательный метод публикации доменных событий."""
        if self._event_bus is None:
            return
        payload = {"action": action, **data}
        self._event_bus.publish(
            RecordingEvent(
                event_type=event_type,
                payload=payload,
            )
        )
