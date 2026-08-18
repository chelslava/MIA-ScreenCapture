"""
Unit-тесты для конвейера постобработки PostRecordingPipeline и PostProcessingManager (Issue #118)
================================================================================================
"""

from __future__ import annotations

from pathlib import Path

from config import PostProcessingSettings
from core.event_bus import InMemoryEventBus
from core.post_processing.manager import PostProcessingManager
from core.post_processing.pipeline import PostRecordingPipeline
from core.post_processing.steps import PostProcessingStep
from core.post_processing.types import (
    PostProcessingStatus,
    PostProcessingStepType,
    StepResult,
)


class DummySuccessStep(PostProcessingStep):
    """Тестовый успешный шаг."""

    def __init__(
        self, new_output_name: str | None = None, is_fatal: bool = False
    ) -> None:
        super().__init__(
            step_type=PostProcessingStepType.TRANSCODE, is_fatal=is_fatal
        )
        self.new_output_name = new_output_name

    def execute(self, input_path: Path) -> StepResult:
        out = (
            input_path.with_name(self.new_output_name)
            if self.new_output_name
            else input_path
        )
        if self.new_output_name:
            out.write_bytes(b"dummy")
        return StepResult(
            step_type=self.step_type,
            success=True,
            input_path=input_path,
            output_path=out,
        )


class DummyFailingStep(PostProcessingStep):
    """Тестовый шаг с ошибкой."""

    def __init__(self, is_fatal: bool = False) -> None:
        super().__init__(
            step_type=PostProcessingStepType.COMPRESS, is_fatal=is_fatal
        )

    def execute(self, input_path: Path) -> StepResult:
        return StepResult(
            step_type=self.step_type,
            success=False,
            input_path=input_path,
            error_message="Dummy failure",
            is_fatal=self.is_fatal,
        )


class TestPostRecordingPipeline:
    """Тестирование выполнения конвейера."""

    def test_empty_pipeline_completes_instantly(self, tmp_path: Path) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        pipeline = PostRecordingPipeline()
        res = pipeline.execute(file)

        assert res.success
        assert res.status == PostProcessingStatus.COMPLETED
        assert res.final_output_path == file
        assert len(res.step_results) == 0

    def test_pipeline_chains_output_files(self, tmp_path: Path) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        step1 = DummySuccessStep(new_output_name="video_step1.mp4")
        step2 = DummySuccessStep(new_output_name="video_step2.mp4")

        pipeline = PostRecordingPipeline([step1, step2])
        res = pipeline.execute(file)

        assert res.success
        assert res.final_output_path.name == "video_step2.mp4"
        assert len(res.step_results) == 2

    def test_non_fatal_step_failure_continues_pipeline(
        self, tmp_path: Path
    ) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        step1 = DummyFailingStep(is_fatal=False)
        step2 = DummySuccessStep(new_output_name="video_step2.mp4")

        pipeline = PostRecordingPipeline([step1, step2])
        res = pipeline.execute(file)

        # Конвейер завершается успешно, пропустив некритичную ошибку
        assert res.status == PostProcessingStatus.COMPLETED
        assert len(res.step_results) == 2
        assert not res.step_results[0].success
        assert res.step_results[1].success

    def test_fatal_step_failure_aborts_pipeline(self, tmp_path: Path) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        step1 = DummyFailingStep(is_fatal=True)
        step2 = DummySuccessStep(new_output_name="video_step2.mp4")

        pipeline = PostRecordingPipeline([step1, step2])
        res = pipeline.execute(file)

        assert res.status == PostProcessingStatus.FAILED
        assert not res.success
        assert len(res.step_results) == 1

    def test_pipeline_cancellation(self, tmp_path: Path) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        step1 = DummySuccessStep()
        step2 = DummySuccessStep()

        pipeline = PostRecordingPipeline([step1, step2])
        pipeline.cancel()
        res = pipeline.execute(file)

        assert res.status == PostProcessingStatus.CANCELLED
        assert not res.success

    def test_pipeline_publishes_events(self, tmp_path: Path) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        event_bus = InMemoryEventBus()
        events = []
        from core.event_bus import RecordingEventType

        event_bus.subscribe(
            RecordingEventType.PROGRESS, lambda e: events.append(e)
        )

        pipeline = PostRecordingPipeline(
            [DummySuccessStep()], event_bus=event_bus
        )
        res = pipeline.execute(file)

        assert res.success
        assert len(events) >= 2  # started, completed

    def test_run_in_background(self, tmp_path: Path) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        finished_result = []
        pipeline = PostRecordingPipeline([DummySuccessStep()])
        thread = pipeline.run_in_background(
            file, on_finished=lambda r: finished_result.append(r)
        )

        thread.join(timeout=5)
        assert len(finished_result) == 1
        assert finished_result[0].success


class TestPostProcessingManager:
    """Тестирование менеджера постобработки."""

    def test_manager_build_steps_from_settings(self) -> None:
        mgr = PostProcessingManager()
        settings = PostProcessingSettings(
            enabled=True,
            transcode_enabled=True,
            compress_enabled=True,
            trim_silence_enabled=True,
            generate_gif_enabled=True,
            copy_enabled=True,
            copy_target_folder="D:/Backup",
            open_explorer_on_finish=True,
            webhook_enabled=True,
            webhook_url="https://example.com",
        )
        steps = mgr.build_steps_from_settings(settings)
        assert len(steps) == 7

    def test_process_file_async_disabled_settings_returns_none(
        self, tmp_path: Path
    ) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")
        mgr = PostProcessingManager()
        settings = PostProcessingSettings(enabled=False)
        thread = mgr.process_file_async(file, settings)
        assert thread is None

    def test_process_file_async_executes_and_stores_last_result(
        self, tmp_path: Path
    ) -> None:
        file = tmp_path / "video.mp4"
        file.write_bytes(b"data")

        mgr = PostProcessingManager()
        settings = PostProcessingSettings(
            enabled=True,
            open_explorer_on_finish=True,  # быстрый шаг
        )

        completed = []
        thread = mgr.process_file_async(
            file, settings, on_finished=lambda r: completed.append(r)
        )
        assert thread is not None

        thread.join(timeout=5)
        assert len(completed) == 1
        assert mgr.last_result is not None
        assert not mgr.is_running
