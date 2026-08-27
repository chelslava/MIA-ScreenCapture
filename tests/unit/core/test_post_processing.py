"""
Unit-тесты для модуля постобработки видеозаписей (core/post_processing).
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

from config import PostProcessingSettings
from core.event_bus import InMemoryEventBus, RecordingEventType
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


class _MockStep(PostProcessingStep):
    """Тестовый шаг для изолированного тестирования pipeline."""

    def __init__(
        self,
        step_type: PostProcessingStepType = PostProcessingStepType.TRANSCODE,
        success: bool = True,
        output_path: Path | None = None,
        is_fatal: bool = False,
        error_message: str | None = None,
        raise_exception: Exception | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        super().__init__(step_type=step_type, is_fatal=is_fatal)
        self._success = success
        self._output_path = output_path
        self._error_message = error_message
        self._raise_exception = raise_exception
        self._delay_seconds = delay_seconds
        self.executed_with: list[Path] = []

    def execute(self, input_path: Path) -> StepResult:
        self.executed_with.append(input_path)
        if self._delay_seconds > 0:
            time.sleep(self._delay_seconds)
        if self._raise_exception:
            raise self._raise_exception
        return StepResult(
            step_type=self.step_type,
            success=self._success,
            input_path=input_path,
            output_path=self._output_path or input_path,
            error_message=self._error_message,
            is_fatal=self.is_fatal,
        )


class TestPostProcessingTypes:
    """Тесты структур данных типов постобработки."""

    def test_step_result_to_dict(self) -> None:
        res = StepResult(
            step_type=PostProcessingStepType.TRANSCODE,
            success=True,
            input_path=Path("input.mp4"),
            output_path=Path("output.webm"),
            duration_seconds=1.5,
            details={"codec": "vp9"},
        )
        data = res.to_dict()
        assert data["step_type"] == "transcode"
        assert data["success"] is True
        assert data["input_path"] == "input.mp4"
        assert data["output_path"] == "output.webm"
        assert data["duration_seconds"] == 1.5
        assert data["details"] == {"codec": "vp9"}

    def test_pipeline_result_to_dict_and_success_property(self) -> None:
        res = PipelineResult(
            status=PostProcessingStatus.COMPLETED,
            initial_input_path=Path("in.mp4"),
            final_output_path=Path("out.mp4"),
            total_duration_seconds=5.0,
        )
        assert res.success is True
        data = res.to_dict()
        assert data["status"] == "completed"
        assert data["success"] is True

        failed_res = PipelineResult(
            status=PostProcessingStatus.FAILED,
            initial_input_path=Path("in.mp4"),
            final_output_path=Path("in.mp4"),
            error_message="Fatal error",
        )
        assert failed_res.success is False


class TestPostRecordingPipeline:
    """Тесты конвейера постобработки PostRecordingPipeline."""

    def test_steps_executed_in_order(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        step1 = _MockStep(step_type=PostProcessingStepType.TRANSCODE)
        step2 = _MockStep(step_type=PostProcessingStepType.COMPRESS)
        step3 = _MockStep(step_type=PostProcessingStepType.COPY_TO_DIR)

        pipeline = PostRecordingPipeline(steps=[step1, step2, step3])
        result = pipeline.execute(input_file)

        assert result.status == PostProcessingStatus.COMPLETED
        assert len(result.step_results) == 3
        assert len(step1.executed_with) == 1
        assert len(step2.executed_with) == 1
        assert len(step3.executed_with) == 1

    def test_fatal_step_error_stops_execution(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        step1 = _MockStep(
            step_type=PostProcessingStepType.TRANSCODE,
            success=False,
            is_fatal=True,
            error_message="Transcode failed",
        )
        step2 = _MockStep(step_type=PostProcessingStepType.COMPRESS)

        pipeline = PostRecordingPipeline(steps=[step1, step2])
        result = pipeline.execute(input_file)

        assert result.status == PostProcessingStatus.FAILED
        assert result.error_message == "Transcode failed"
        assert len(result.step_results) == 1
        assert len(step2.executed_with) == 0

    def test_non_fatal_step_error_continues(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        step1 = _MockStep(
            step_type=PostProcessingStepType.WEBHOOK,
            success=False,
            is_fatal=False,
            error_message="Webhook 500",
        )
        step2 = _MockStep(
            step_type=PostProcessingStepType.OPEN_EXPLORER, success=True
        )

        pipeline = PostRecordingPipeline(steps=[step1, step2])
        result = pipeline.execute(input_file)

        assert result.status == PostProcessingStatus.COMPLETED
        assert len(result.step_results) == 2
        assert result.step_results[0].success is False
        assert result.step_results[1].success is True
        assert len(step2.executed_with) == 1

    def test_step_exception_handled_as_failure(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        step1 = _MockStep(
            step_type=PostProcessingStepType.COMPRESS,
            raise_exception=RuntimeError("FFmpeg crashed"),
            is_fatal=True,
        )

        pipeline = PostRecordingPipeline(steps=[step1])
        result = pipeline.execute(input_file)

        assert result.status == PostProcessingStatus.FAILED
        assert "FFmpeg crashed" in str(result.error_message)

    def test_cancel_before_start_returns_cancelled(
        self, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        step1 = _MockStep()
        pipeline = PostRecordingPipeline(steps=[step1])
        pipeline.cancel()

        result = pipeline.execute(input_file)
        assert result.status == PostProcessingStatus.CANCELLED
        assert len(step1.executed_with) == 0

    def test_cancel_during_execution_returns_cancelled(
        self, tmp_path: Path
    ) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        step1 = _MockStep(delay_seconds=0.05)
        step2 = _MockStep()

        pipeline = PostRecordingPipeline(steps=[step1, step2])

        def _cancel_after_delay() -> None:
            time.sleep(0.01)
            pipeline.cancel()

        cancel_thread = threading.Thread(target=_cancel_after_delay)
        cancel_thread.start()

        result = pipeline.execute(input_file)
        cancel_thread.join()

        assert result.status == PostProcessingStatus.CANCELLED
        assert len(step2.executed_with) == 0

    def test_event_bus_emits_events(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        bus = InMemoryEventBus()
        events: list = []
        bus.subscribe(RecordingEventType.PROGRESS, events.append)
        bus.subscribe(RecordingEventType.ERROR, events.append)
        bus.subscribe(RecordingEventType.WARNING, events.append)

        step1 = _MockStep()
        pipeline = PostRecordingPipeline(steps=[step1], event_bus=bus)
        result = pipeline.execute(input_file)

        assert result.status == PostProcessingStatus.COMPLETED
        assert len(events) >= 3  # started, step_completed, completed

    def test_run_in_background(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        finished_result: list[PipelineResult] = []
        done_event = threading.Event()

        def _on_done(res: PipelineResult) -> None:
            finished_result.append(res)
            done_event.set()

        step1 = _MockStep()
        pipeline = PostRecordingPipeline(steps=[step1])
        thread = pipeline.run_in_background(input_file, on_finished=_on_done)

        assert thread.is_alive() or done_event.is_set()
        assert done_event.wait(timeout=3.0) is True
        assert len(finished_result) == 1
        assert finished_result[0].status == PostProcessingStatus.COMPLETED


class TestPostProcessingManager:
    """Тесты PostProcessingManager."""

    def test_process_file_async_disabled_returns_none(
        self, tmp_path: Path
    ) -> None:
        settings = PostProcessingSettings(enabled=False)
        manager = PostProcessingManager()
        result = manager.process_file_async(tmp_path / "rec.mp4", settings)
        assert result is None
        assert manager.is_running is False

    def test_process_file_async_no_steps_returns_none(
        self, tmp_path: Path
    ) -> None:
        settings = PostProcessingSettings(enabled=True)
        manager = PostProcessingManager()
        result = manager.process_file_async(tmp_path / "rec.mp4", settings)
        assert result is None
        assert manager.is_running is False

    def test_build_steps_from_settings_all_enabled(self) -> None:
        settings = PostProcessingSettings(
            enabled=True,
            transcode_enabled=True,
            compress_enabled=True,
            trim_silence_enabled=True,
            generate_gif_enabled=True,
            copy_enabled=True,
            copy_target_folder=r"C:\Backup",
            open_explorer_on_finish=True,
            webhook_enabled=True,
            webhook_url="https://example.com/hook",
        )
        manager = PostProcessingManager()
        steps = manager.build_steps_from_settings(settings)
        assert len(steps) == 7
        types = [s.step_type for s in steps]
        assert PostProcessingStepType.TRANSCODE in types
        assert PostProcessingStepType.COMPRESS in types
        assert PostProcessingStepType.TRIM_SILENCE in types
        assert PostProcessingStepType.GENERATE_GIF in types
        assert PostProcessingStepType.COPY_TO_DIR in types
        assert PostProcessingStepType.OPEN_EXPLORER in types
        assert PostProcessingStepType.WEBHOOK in types

    def test_build_steps_from_settings_none_enabled(self) -> None:
        settings = PostProcessingSettings(enabled=True)
        manager = PostProcessingManager()
        steps = manager.build_steps_from_settings(settings)
        assert len(steps) == 0

    def test_process_file_async_happy_path(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        settings = PostProcessingSettings(
            enabled=True,
            copy_enabled=True,
            copy_target_folder=str(tmp_path / "dest"),
        )
        manager = PostProcessingManager()
        finished_results: list[PipelineResult] = []
        done_event = threading.Event()

        def _on_done(res: PipelineResult) -> None:
            finished_results.append(res)
            done_event.set()

        thread = manager.process_file_async(
            input_file, settings, on_finished=_on_done
        )
        assert thread is not None
        assert done_event.wait(timeout=3.0) is True
        assert manager.is_running is False
        assert manager.last_result is not None
        assert manager.last_result.status == PostProcessingStatus.COMPLETED

    def test_cancel_stops_running_pipeline(self, tmp_path: Path) -> None:
        input_file = tmp_path / "rec.mp4"
        input_file.write_bytes(b"data")

        settings = PostProcessingSettings(
            enabled=True,
            copy_enabled=True,
            copy_target_folder=str(tmp_path / "dest"),
        )
        manager = PostProcessingManager()

        # Подменим шаг на долгий
        slow_step = _MockStep(delay_seconds=0.2)
        with patch.object(
            manager,
            "build_steps_from_settings",
            return_value=[slow_step, _MockStep()],
        ):
            done_event = threading.Event()
            thread = manager.process_file_async(
                input_file,
                settings,
                on_finished=lambda _: done_event.set(),
            )
            assert thread is not None
            time.sleep(0.02)
            manager.cancel()

            assert done_event.wait(timeout=3.0) is True
            assert manager.last_result is not None
            assert manager.last_result.status == PostProcessingStatus.CANCELLED


class TestPostProcessingSteps:
    """Тесты конкретных шагов постобработки."""

    def test_transcode_step_non_existent_file(self) -> None:
        step = TranscodeStep(target_format="webm")
        res = step.execute(Path("non_existent_file.mp4"))
        assert res.success is False
        assert res.error_message is not None
        assert "не существует" in res.error_message

    def test_compress_step_non_existent_file(self) -> None:
        step = CompressStep(crf=28)
        res = step.execute(Path("non_existent_file.mp4"))
        assert res.success is False
        assert res.error_message is not None
        assert "не существует" in res.error_message

    def test_trim_silence_step_non_existent_file(self) -> None:
        step = TrimSilenceStep()
        res = step.execute(Path("non_existent_file.mp4"))
        assert res.success is False
        assert res.error_message is not None
        assert "не существует" in res.error_message

    def test_generate_gif_step_non_existent_file(self) -> None:
        step = GenerateGifPreviewStep()
        res = step.execute(Path("non_existent_file.mp4"))
        assert res.success is False
        assert res.error_message is not None
        assert "не существует" in res.error_message

    def test_copy_to_folder_step_success(self, tmp_path: Path) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"content")
        dest_dir = tmp_path / "copied_dir"

        step = CopyToFolderStep(target_folder=str(dest_dir))
        res = step.execute(src)

        assert res.success is True
        assert res.output_path is not None
        assert res.output_path.exists()
        assert res.output_path.read_bytes() == b"content"

    def test_copy_to_folder_step_missing_file(self, tmp_path: Path) -> None:
        step = CopyToFolderStep(target_folder=str(tmp_path / "dest"))
        res = step.execute(tmp_path / "missing.mp4")
        assert res.success is False
        assert res.error_message is not None
        assert "не существует" in res.error_message

    def test_open_in_explorer_step_missing_file(self, tmp_path: Path) -> None:
        step = OpenInExplorerStep()
        res = step.execute(tmp_path / "missing.mp4")
        assert res.success is False
        assert res.error_message is not None
        assert "не существует" in res.error_message

    def test_webhook_step_missing_url(self, tmp_path: Path) -> None:
        step = WebhookNotificationStep(webhook_url="")
        res = step.execute(tmp_path / "missing.mp4")
        assert res.success is False
        assert res.error_message is not None
        assert "не указан" in res.error_message

    def test_webhook_step_network_failure_handled(
        self, tmp_path: Path
    ) -> None:
        src = tmp_path / "test.mp4"
        src.write_bytes(b"content")

        step = WebhookNotificationStep(
            webhook_url="https://invalid.example.com"
        )
        with patch.object(
            step._sender,
            "send",
            return_value=(False, 100.0),
        ):
            res = step.execute(src)
            assert res.success is False
            assert res.is_fatal is False
