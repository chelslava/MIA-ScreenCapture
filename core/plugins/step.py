"""
Шаг постобработки, выполняемый внешним плагином
===============================================
"""

from __future__ import annotations

import time
from pathlib import Path

from core.plugins.protocol import MIAPlugin
from core.post_processing.steps import PostProcessingStep
from core.post_processing.types import PostProcessingStepType, StepResult
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class PluginPostProcessingStep(PostProcessingStep):
    """Шаг конвейера постобработки, делегирующий выполнение экземпляру MIAPlugin."""

    def __init__(
        self,
        plugin: MIAPlugin,
        is_fatal: bool = False,
        timeout_seconds: int = 300,
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.PLUGIN,
            is_fatal=is_fatal,
            timeout_seconds=timeout_seconds,
        )
        self.plugin = plugin

    def execute(self, input_path: Path) -> StepResult:
        """
        Выполнение шага плагина.

        Args:
            input_path: Путь к входному видеофайлу.

        Returns:
            StepResult с результатом работы плагина.
        """
        start_time = time.monotonic()
        if not input_path.exists():
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                error_message=f"Файл {input_path} не существует",
                is_fatal=self.is_fatal,
                details={"plugin_name": self.plugin.name},
            )

        try:
            logger.info(
                "Запуск плагина постобработки '%s' для %s",
                self.plugin.name,
                input_path.name,
            )
            output_path = self.plugin.process(input_path)
            duration = time.monotonic() - start_time

            resolved_output = (
                output_path
                if (output_path and output_path.exists())
                else input_path
            )

            return StepResult(
                step_type=self.step_type,
                success=True,
                input_path=input_path,
                output_path=resolved_output,
                duration_seconds=duration,
                details={
                    "plugin_name": self.plugin.name,
                    "plugin_version": getattr(
                        self.plugin, "version", "unknown"
                    ),
                },
            )
        except Exception as e:
            duration = time.monotonic() - start_time
            error_msg = f"Ошибка в плагине '{self.plugin.name}': {e}"
            logger.exception(error_msg)
            return StepResult(
                step_type=self.step_type,
                success=False,
                input_path=input_path,
                duration_seconds=duration,
                error_message=error_msg,
                is_fatal=self.is_fatal,
                details={"plugin_name": self.plugin.name},
            )
