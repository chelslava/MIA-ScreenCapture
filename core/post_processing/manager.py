"""
Менеджер конвейера постобработки и фабрика шагов
================================================

Предоставляет:
- сборку конвейера PostRecordingPipeline из настроек PostProcessingSettings;
- управление жизненным циклом и хранение истории результатов;
- потокобезопасный запуск и отмену фоновых задач.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from core.event_bus import EventBus
from core.post_processing.pipeline import PostRecordingPipeline
from core.post_processing.steps import (
    CompressStep,
    CopyToFolderStep,
    GenerateGifPreviewStep,
    OpenInExplorerStep,
    PostProcessingStep,
    TranscodeStep,
    TrimSilenceStep,
    WebhookNotificationStep,
)
from core.post_processing.types import (
    PipelineResult,
)
from logger_config import get_module_logger

if TYPE_CHECKING:
    from config import PostProcessingSettings

logger = get_module_logger(__name__)


class PostProcessingManager:
    """Менеджер управления процессами постобработки видеофайлов."""

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus
        self._current_pipeline: PostRecordingPipeline | None = None
        self._last_result: PipelineResult | None = None
        self._is_running = False
        self._lock = threading.RLock()

    @property
    def is_running(self) -> bool:
        """Флаг активности постобработки."""
        with self._lock:
            return self._is_running

    @property
    def last_result(self) -> PipelineResult | None:
        """Последний полученный результат конвейера."""
        with self._lock:
            return self._last_result

    def build_steps_from_settings(
        self, settings: PostProcessingSettings
    ) -> list[PostProcessingStep]:
        """
        Создает список активных шагов постобработки на основе настроек.

        Args:
            settings: Объект настроек PostProcessingSettings.

        Returns:
            Список сконфигурированных шагов PostProcessingStep.
        """
        steps: list[PostProcessingStep] = []
        timeout = settings.step_timeout_seconds

        # 1. Перекодирование
        if settings.transcode_enabled:
            steps.append(
                TranscodeStep(
                    target_format=settings.transcode_format,
                    target_codec=settings.transcode_codec,
                    is_fatal=False,
                    timeout_seconds=timeout,
                )
            )

        # 2. Сжатие
        if settings.compress_enabled:
            steps.append(
                CompressStep(
                    crf=settings.compress_crf,
                    is_fatal=False,
                    timeout_seconds=timeout,
                )
            )

        # 3. Обрезка тишины
        if settings.trim_silence_enabled:
            steps.append(
                TrimSilenceStep(
                    threshold_db=settings.trim_silence_threshold_db,
                    is_fatal=False,
                    timeout_seconds=timeout,
                )
            )

        # 4. Генерация GIF
        if settings.generate_gif_enabled:
            steps.append(
                GenerateGifPreviewStep(
                    duration_seconds=settings.gif_duration_seconds,
                    fps=settings.gif_fps,
                    is_fatal=False,
                    timeout_seconds=min(timeout, 120),
                )
            )

        # 5. Копирование в папку
        if settings.copy_enabled and settings.copy_target_folder:
            steps.append(
                CopyToFolderStep(
                    target_folder=settings.copy_target_folder,
                    is_fatal=False,
                    timeout_seconds=min(timeout, 120),
                )
            )

        # 6. Открытие в проводнике
        if settings.open_explorer_on_finish:
            steps.append(
                OpenInExplorerStep(
                    is_fatal=False,
                    timeout_seconds=10,
                )
            )

        # 7. Webhook-уведомление
        if settings.webhook_enabled and settings.webhook_url:
            steps.append(
                WebhookNotificationStep(
                    webhook_url=settings.webhook_url,
                    is_fatal=False,
                    timeout_seconds=15,
                )
            )

        return steps

    def process_file_async(
        self,
        file_path: Path,
        settings: PostProcessingSettings,
        on_finished: Callable[[PipelineResult], None] | None = None,
    ) -> threading.Thread | None:
        """
        Запускает конвейер постобработки в фоновом потоке, если постобработка включена.

        Args:
            file_path: Путь к исходному видеофайлу.
            settings: Настройки постобработки.
            on_finished: Callback по завершению.

        Returns:
            Поток выполнения или None, если постобработка выключена или нет шагов.
        """
        if not settings.enabled:
            logger.debug("Постобработка выключена в настройках")
            return None

        steps = self.build_steps_from_settings(settings)
        if not steps:
            logger.debug("Нет активных шагов постобработки")
            return None

        with self._lock:
            self._is_running = True
            pipeline = PostRecordingPipeline(
                steps=steps, event_bus=self._event_bus
            )
            self._current_pipeline = pipeline

        def _handle_finished(result: PipelineResult) -> None:
            with self._lock:
                self._is_running = False
                self._last_result = result
                self._current_pipeline = None
            if on_finished is not None:
                try:
                    on_finished(result)
                except Exception as e:
                    logger.error("Ошибка в on_finished callback: %s", e)

        return pipeline.run_in_background(
            initial_path=file_path,
            on_finished=_handle_finished,
        )

    def cancel(self) -> None:
        """Отменить текущую выполняющуюся постобработку."""
        with self._lock:
            if self._current_pipeline is not None:
                self._current_pipeline.cancel()
