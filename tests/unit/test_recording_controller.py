"""
Тесты RecordingController
==========================

Юнит-тесты контроллера управления записью.
Мокируют Qt-зависимости и файловую систему.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.recording_types import AudioMode, CaptureMode
from gui.controllers.recording_controller import RecordingController
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    RecordingStatus,
    VideoSettings,
)
from recorder.utils import FFmpegStatus


class TestRecordingControllerInit:
    """Тесты инициализации контроллера."""

    def test_init_creates_own_state_when_none_given(self) -> None:
        ctrl = RecordingController()
        assert isinstance(ctrl.state, RecordingState)

    def test_init_uses_provided_state(self) -> None:
        state = RecordingState()
        ctrl = RecordingController(state)
        assert ctrl.state is state

    def test_elapsed_time_is_zero_without_recorder(self) -> None:
        ctrl = RecordingController()
        assert ctrl.elapsed_time == 0.0

    def test_dropped_audio_chunks_is_zero_without_recorder(self) -> None:
        ctrl = RecordingController()
        assert ctrl.dropped_audio_chunks == 0


class TestRecordingControllerBuildCaptureArea:
    """Тесты построения области захвата."""

    def test_full_screen_returns_capture_area(self) -> None:
        ctrl = RecordingController()
        capture = CaptureSettings(capture_type=CaptureMode.FULL)
        area = ctrl.build_capture_area(capture)
        assert area is not None

    def test_window_capture_delegates_to_from_window(self) -> None:
        ctrl = RecordingController()
        capture = CaptureSettings(
            capture_type=CaptureMode.WINDOW,
            window_title="MyApp",
        )
        with patch(
            "gui.controllers.recording_controller.CaptureArea.from_window"
        ) as mock_from_window:
            mock_from_window.return_value = MagicMock()
            ctrl.build_capture_area(capture)
            mock_from_window.assert_called_once_with(
                "MyApp", raise_if_not_found=False
            )

    def test_rect_capture_delegates_to_from_rect(self) -> None:
        ctrl = RecordingController()
        capture = CaptureSettings(
            capture_type=CaptureMode.RECT,
            rect_coords=(10, 20, 300, 400),
        )
        with patch(
            "gui.controllers.recording_controller.CaptureArea.from_rect"
        ) as mock_from_rect:
            mock_from_rect.return_value = MagicMock()
            ctrl.build_capture_area(capture)
            mock_from_rect.assert_called_once_with(10, 20, 300, 400)


class TestRecordingControllerStartRecording:
    """Тесты запуска записи."""

    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    @patch("gui.controllers.recording_controller.check_ffmpeg")
    def test_start_success_sets_state_to_recording(
        self,
        mock_ffmpeg,
        mock_video_recorder_cls,
        mock_encoder_cls,
    ) -> None:
        mock_ffmpeg.return_value = FFmpegStatus(available=True, version="5.0")
        encoder = MagicMock()
        encoder.setup.return_value = (Path("/tmp/v.mp4"), Path("/tmp/a.wav"))
        mock_encoder_cls.return_value = encoder
        video_recorder = MagicMock()
        video_recorder.start.return_value = True
        mock_video_recorder_cls.return_value = video_recorder

        ctrl = RecordingController()
        success, err = ctrl.start_recording(
            Path("/out/test.mp4"),
            CaptureSettings(),
            AudioSettings(),
            VideoSettings(),
        )

        assert success is True
        assert err is None
        assert ctrl.state.status == RecordingStatus.RECORDING

    @patch("gui.controllers.recording_controller.check_ffmpeg")
    def test_start_fails_when_ffmpeg_missing(self, mock_ffmpeg) -> None:
        mock_ffmpeg.return_value = FFmpegStatus(available=False)
        ctrl = RecordingController()

        success, err = ctrl.start_recording(
            Path("/out/test.mp4"),
            CaptureSettings(),
            AudioSettings(),
            VideoSettings(),
        )

        assert success is False
        assert err is not None
        assert "FFmpeg" in err
        assert ctrl.state.status == RecordingStatus.IDLE

    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    @patch("gui.controllers.recording_controller.check_ffmpeg")
    def test_start_fails_when_video_recorder_start_fails(
        self,
        mock_ffmpeg,
        mock_video_recorder_cls,
        mock_encoder_cls,
    ) -> None:
        mock_ffmpeg.return_value = FFmpegStatus(available=True, version="5.0")
        encoder = MagicMock()
        encoder.setup.return_value = (Path("/tmp/v.mp4"), Path("/tmp/a.wav"))
        mock_encoder_cls.return_value = encoder
        video_recorder = MagicMock()
        video_recorder.start.return_value = False
        mock_video_recorder_cls.return_value = video_recorder

        ctrl = RecordingController()
        success, err = ctrl.start_recording(
            Path("/out/test.mp4"),
            CaptureSettings(),
            AudioSettings(),
            VideoSettings(),
        )

        assert success is False
        assert "видеозапись" in (err or "")

    @patch("gui.controllers.recording_controller.AudioRecorder")
    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    @patch("gui.controllers.recording_controller.check_ffmpeg")
    def test_start_fails_when_mic_audio_start_fails(
        self,
        mock_ffmpeg,
        mock_video_recorder_cls,
        mock_encoder_cls,
        mock_audio_recorder_cls,
    ) -> None:
        mock_ffmpeg.return_value = FFmpegStatus(available=True, version="5.0")
        encoder = MagicMock()
        encoder.setup.return_value = (Path("/tmp/v.mp4"), Path("/tmp/a.wav"))
        mock_encoder_cls.return_value = encoder
        video_recorder = MagicMock()
        video_recorder.start.return_value = True
        mock_video_recorder_cls.return_value = video_recorder
        audio_recorder = MagicMock()
        audio_recorder.start.return_value = False
        mock_audio_recorder_cls.return_value = audio_recorder

        ctrl = RecordingController()
        success, err = ctrl.start_recording(
            Path("/out/test.mp4"),
            CaptureSettings(),
            AudioSettings(audio_type=AudioMode.MIC),
            VideoSettings(),
        )

        assert success is False
        assert "аудиозапись" in (err or "")


class TestRecordingControllerPauseResume:
    """Тесты паузы и возобновления записи."""

    def test_pause_when_recording_returns_true_and_sets_paused(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.RECORDING

        result = ctrl.pause_recording()

        assert result is True
        assert ctrl.state.status == RecordingStatus.PAUSED

    def test_pause_when_idle_returns_false(self) -> None:
        ctrl = RecordingController()
        result = ctrl.pause_recording()
        assert result is False
        assert ctrl.state.status == RecordingStatus.IDLE

    def test_pause_when_already_paused_returns_false(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.PAUSED
        result = ctrl.pause_recording()
        assert result is False

    def test_resume_when_paused_returns_true_and_sets_recording(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.PAUSED

        result = ctrl.resume_recording()

        assert result is True
        assert ctrl.state.status == RecordingStatus.RECORDING

    def test_resume_when_not_paused_returns_false(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.IDLE
        result = ctrl.resume_recording()
        assert result is False

    def test_pause_calls_video_recorder_pause(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.RECORDING
        ctrl._video_recorder = MagicMock()
        ctrl._audio_recorder = None

        ctrl.pause_recording()

        ctrl._video_recorder.pause.assert_called_once()

    def test_resume_calls_video_recorder_resume(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.PAUSED
        ctrl._video_recorder = MagicMock()
        ctrl._audio_recorder = None

        ctrl.resume_recording()

        ctrl._video_recorder.resume.assert_called_once()


class TestRecordingControllerStop:
    """Тесты остановки записи."""

    def test_stop_when_idle_returns_none(self) -> None:
        ctrl = RecordingController()
        result = ctrl.stop_recording()
        assert result is None

    def test_stop_when_video_stop_fails_returns_none_and_cancels_encoder(
        self,
    ) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.RECORDING
        ctrl._video_recorder = MagicMock()
        ctrl._video_recorder.stop.return_value = False
        ctrl._audio_recorder = None
        ctrl._encoder = MagicMock()

        result = ctrl.stop_recording()

        assert result is None
        ctrl._encoder.cancel.assert_called_once()
        ctrl._encoder.finalize.assert_not_called()
        assert ctrl.state.status == RecordingStatus.IDLE

    def test_stop_when_paused_resumes_first(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.PAUSED
        video_recorder = MagicMock()
        video_recorder.stop.return_value = True
        ctrl._video_recorder = video_recorder
        ctrl._audio_recorder = None
        encoder = MagicMock()
        encoder.finalize.return_value = (True, None)
        encoder.output_path = Path("/out/test.mp4")
        ctrl._encoder = encoder

        ctrl.stop_recording()

        video_recorder.resume.assert_called_once()


class TestRecordingControllerCancellation:
    """Тесты отмены операций."""

    def test_cancel_recording_sets_state_to_idle(self) -> None:
        ctrl = RecordingController()
        ctrl.state.status = RecordingStatus.RECORDING

        ctrl.cancel_recording()

        assert ctrl.state.status == RecordingStatus.IDLE

    def test_request_stop_cancellation_during_finalization_returns_true(
        self,
    ) -> None:
        ctrl = RecordingController()
        ctrl._encoder = MagicMock()
        ctrl._encoder.is_finalizing = True

        result = ctrl.request_stop_cancellation()

        assert result is True
        ctrl._encoder.cancel.assert_called_once()

    def test_request_stop_cancellation_without_finalization_returns_false(
        self,
    ) -> None:
        ctrl = RecordingController()
        ctrl._encoder = MagicMock()
        ctrl._encoder.is_finalizing = False

        result = ctrl.request_stop_cancellation()

        assert result is False
        ctrl._encoder.cancel.assert_not_called()

    def test_request_stop_cancellation_without_encoder_returns_false(
        self,
    ) -> None:
        ctrl = RecordingController()
        ctrl._encoder = None

        result = ctrl.request_stop_cancellation()

        assert result is False


class TestRecordingControllerFfmpegCache:
    """Тесты кэширования проверки FFmpeg."""

    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    @patch("gui.controllers.recording_controller.check_ffmpeg")
    def test_ffmpeg_cache_reused_within_ttl(
        self,
        mock_ffmpeg,
        mock_video_recorder_cls,
        mock_encoder_cls,
    ) -> None:
        mock_ffmpeg.return_value = FFmpegStatus(available=True, version="5.0")
        encoder = MagicMock()
        encoder.setup.return_value = (Path("/tmp/v.mp4"), Path("/tmp/a.wav"))
        mock_encoder_cls.return_value = encoder
        video_recorder = MagicMock()
        video_recorder.start.return_value = True
        video_recorder.stop.return_value = True
        mock_video_recorder_cls.return_value = video_recorder

        ctrl = RecordingController()
        with patch(
            "gui.controllers.recording_controller.time.monotonic"
        ) as mock_time:
            mock_time.side_effect = [100.0, 100.5]
            ctrl.start_recording(
                Path("/out/test.mp4"),
                CaptureSettings(),
                AudioSettings(),
                VideoSettings(),
            )
            ctrl._state.stop_recording()
            ctrl._video_recorder = None
            ctrl._encoder = None
            ctrl.start_recording(
                Path("/out/test.mp4"),
                CaptureSettings(),
                AudioSettings(),
                VideoSettings(),
            )

        mock_ffmpeg.assert_called_once()

    @patch("gui.controllers.recording_controller.RecordingEncoder")
    @patch("gui.controllers.recording_controller.VideoRecorder")
    @patch("gui.controllers.recording_controller.check_ffmpeg")
    def test_ffmpeg_cache_refreshed_after_ttl(
        self,
        mock_ffmpeg,
        mock_video_recorder_cls,
        mock_encoder_cls,
    ) -> None:
        mock_ffmpeg.return_value = FFmpegStatus(available=True, version="5.0")
        encoder = MagicMock()
        encoder.setup.return_value = (Path("/tmp/v.mp4"), Path("/tmp/a.wav"))
        mock_encoder_cls.return_value = encoder
        video_recorder = MagicMock()
        video_recorder.start.return_value = True
        video_recorder.stop.return_value = True
        mock_video_recorder_cls.return_value = video_recorder

        ctrl = RecordingController()
        with patch(
            "gui.controllers.recording_controller.time.monotonic"
        ) as mock_time:
            mock_time.side_effect = [100.0, 131.0]
            ctrl.start_recording(
                Path("/out/test.mp4"),
                CaptureSettings(),
                AudioSettings(),
                VideoSettings(),
            )
            ctrl._state.stop_recording()
            ctrl._video_recorder = None
            ctrl._encoder = None
            ctrl.start_recording(
                Path("/out/test.mp4"),
                CaptureSettings(),
                AudioSettings(),
                VideoSettings(),
            )

        assert mock_ffmpeg.call_count == 2
