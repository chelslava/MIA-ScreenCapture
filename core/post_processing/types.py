"""
Типы данных, перечисления и результаты шагов постобработки записей
==================================================================

Определяет:
- перечисление типов шагов PostProcessingStepType;
- состояния выполнения конвейера PostProcessingStatus;
- структуры данных результатов выполнения шага StepResult и конвейера PipelineResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class PostProcessingStepType(StrEnum):
    """Типы поддерживаемых шагов постобработки."""

    TRANSCODE = "transcode"
    COMPRESS = "compress"
    TRIM_SILENCE = "trim_silence"
    GENERATE_GIF = "generate_gif"
    COPY_TO_DIR = "copy_to_dir"
    OPEN_EXPLORER = "open_explorer"
    WEBHOOK = "webhook"
    PLUGIN = "plugin"
    TRANSCRIPTION = "transcription"


class PostProcessingStatus(StrEnum):
    """Статусы конвейера постобработки."""

    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StepResult:
    """Результат выполнения отдельного шага постобработки."""

    step_type: PostProcessingStepType
    success: bool
    input_path: Path
    output_path: Path | None = None
    duration_seconds: float = 0.0
    error_message: str | None = None
    is_fatal: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Сериализация результата шага в словарь."""
        return {
            "step_type": self.step_type.value,
            "success": self.success,
            "input_path": str(self.input_path),
            "output_path": str(self.output_path) if self.output_path else None,
            "duration_seconds": round(self.duration_seconds, 3),
            "error_message": self.error_message,
            "is_fatal": self.is_fatal,
            "details": self.details,
        }


@dataclass
class PipelineResult:
    """Итоговый результат выполнения всего конвейера постобработки."""

    status: PostProcessingStatus
    initial_input_path: Path
    final_output_path: Path
    step_results: list[StepResult] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    error_message: str | None = None

    @property
    def success(self) -> bool:
        """Успешность конвейера (завершен без критических ошибок)."""
        return self.status == PostProcessingStatus.COMPLETED

    def to_dict(self) -> dict[str, Any]:
        """Сериализация результата конвейера в словарь."""
        return {
            "status": self.status.value,
            "initial_input_path": str(self.initial_input_path),
            "final_output_path": str(self.final_output_path),
            "success": self.success,
            "total_duration_seconds": round(self.total_duration_seconds, 3),
            "error_message": self.error_message,
            "steps": [s.to_dict() for s in self.step_results],
        }
