"""
Пакет постобработки видеозаписей (Post-Recording Flow)
=====================================================
"""

from core.post_processing.manager import PostProcessingManager
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
    PostProcessingStatus,
    PostProcessingStepType,
    StepResult,
)

__all__ = [
    "CompressStep",
    "CopyToFolderStep",
    "GenerateGifPreviewStep",
    "OpenInExplorerStep",
    "PipelineResult",
    "PostProcessingManager",
    "PostRecordingPipeline",
    "PostProcessingStatus",
    "PostProcessingStep",
    "PostProcessingStepType",
    "StepResult",
    "TranscodeStep",
    "TrimSilenceStep",
    "WebhookNotificationStep",
]
