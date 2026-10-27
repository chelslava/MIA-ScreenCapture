"""
Unit-тесты для подсистемы аппаратного кодирования (Hardware Encoding).

Проверяет детекцию поддерживаемых энкодеров FFmpeg, probe-тестирование
доступности GPU-кодеков и автоматический fallback на программные кодеки.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.event_bus import InMemoryEventBus, RecordingEventType
from recorder.ffmpeg_writer import FFmpegVideoWriter
from recorder.utils import (
    _PROBED_ENCODERS_CACHE,
    get_supported_video_encoders,
    probe_encoder_availability,
)
from recorder.video_recorder import VideoRecorder


class TestHardwareEncoderDetection:
    """Тесты функций детекции и пробного запуска кодеков."""

    def setup_method(self) -> None:
        """Очистка кэша перед каждым тестом."""
        _PROBED_ENCODERS_CACHE.clear()

    def test_get_supported_video_encoders_parses_ffmpeg_output(self) -> None:
        """Парсинг вывода ffmpeg -encoders возвращает ожидаемый набор видеокодеков."""
        fake_stdout = """
Encoders:
 V..... = Video
 A..... = Audio
 ------
 V..... h264_nvenc           NVIDIA NVENC H.264 encoder (codec h264)
 V..... h264_amf             AMD AMF H.264 Encoder (codec h264)
 V..... h264_qsv             Intel Quick Sync H.264 (codec h264)
 V..... libx264              libx264 H.264 (codec h264)
 A..... aac                  AAC (Advanced Audio Coding)
 V..... libx265              libx265 H.265 (codec hevc)
 V..... hevc_nvenc           NVIDIA NVENC hevc encoder (codec hevc)
"""
        with patch("recorder.utils.get_ffmpeg_path", return_value="ffmpeg"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout=fake_stdout
                )
                encoders = get_supported_video_encoders()

                assert "h264_nvenc" in encoders
                assert "h264_amf" in encoders
                assert "h264_qsv" in encoders
                assert "libx264" in encoders
                assert "libx265" in encoders
                assert "hevc_nvenc" in encoders
                assert "aac" not in encoders  # аудио кодеки исключаются

    def test_get_supported_video_encoders_handles_missing_ffmpeg(self) -> None:
        """При отсутствии FFmpeg возвращается пустое множество."""
        with patch("recorder.utils.get_ffmpeg_path", return_value=None):
            assert get_supported_video_encoders() == set()

    def test_probe_encoder_availability_success(self) -> None:
        """Успешный пробный запуск возвращает True и кэширует результат."""
        with patch("recorder.utils.get_ffmpeg_path", return_value="ffmpeg"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                assert probe_encoder_availability("h264_nvenc") is True
                assert mock_run.call_count == 1

                # Второй вызов должен использовать кэш
                assert probe_encoder_availability("h264_nvenc") is True
                assert mock_run.call_count == 1

    def test_probe_encoder_availability_failure(self) -> None:
        """Неудачный пробный запуск возвращает False."""
        with patch("recorder.utils.get_ffmpeg_path", return_value="ffmpeg"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1)

                assert (
                    probe_encoder_availability("h264_amf", use_cache=False)
                    is False
                )


class TestHardwareEncoderFallback:
    """Тесты автоматического fallback на программные кодеки при сбое GPU."""

    def test_ffmpeg_writer_falls_back_from_nvenc_to_libx264(
        self, tmp_path: Path
    ) -> None:
        """При ошибке запуска h264_nvenc происходит переключение на libx264."""
        out = tmp_path / "test.mp4"
        event_bus = InMemoryEventBus()
        events: list[dict] = []
        event_bus.subscribe(
            RecordingEventType.WARNING,
            lambda ev: events.append(ev.payload),
        )

        # Патчим get_ffmpeg_path ДО конструирования writer: путь
        # разрешается в __init__ (self._ffmpeg_path), и на CI без
        # установленного ffmpeg он был бы None.
        with patch(
            "recorder.ffmpeg_writer.get_ffmpeg_path", return_value="ffmpeg"
        ):
            writer = FFmpegVideoWriter(
                output_path=out,
                width=1920,
                height=1080,
                codec="h264_nvenc",
                event_bus=event_bus,
            )

        call_count = 0

        def fake_popen(*_args: object, **_kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock_proc = MagicMock()
            # Первый вызов (h264_nvenc) падает мгновенно
            if call_count == 1:
                mock_proc.poll.return_value = 1
                mock_proc.stderr = MagicMock()
                mock_proc.stderr.readline.return_value = b""
                return mock_proc
            # Второй вызов (libx264) успешен
            mock_proc.poll.return_value = None
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.readline.return_value = b""
            return mock_proc

        with patch("subprocess.Popen", side_effect=fake_popen):
            ok = writer._open_process(out)
            assert ok is True
            assert writer.codec == "h264_nvenc"
            assert writer.actual_codec == "libx264"
            assert writer.fallback_occurred is True
            assert call_count == 2

            # Проверяем публикацию события в EventBus
            assert len(events) == 1
            assert events[0]["type"] == "hardware_encoder_fallback"
            assert events[0]["requested_codec"] == "h264_nvenc"
            assert events[0]["fallback_codec"] == "libx264"

    def test_ffmpeg_writer_falls_back_from_hevc_amf_to_libx265(
        self, tmp_path: Path
    ) -> None:
        """При ошибке запуска hevc_amf происходит переключение на libx265."""
        out = tmp_path / "test.mp4"
        event_bus = InMemoryEventBus()
        # Патчим get_ffmpeg_path ДО конструирования writer: путь
        # разрешается в __init__ (self._ffmpeg_path), и на CI без
        # установленного ffmpeg он был бы None.
        with patch(
            "recorder.ffmpeg_writer.get_ffmpeg_path", return_value="ffmpeg"
        ):
            writer = FFmpegVideoWriter(
                output_path=out,
                width=1920,
                height=1080,
                codec="hevc_amf",
                event_bus=event_bus,
            )

        call_count = 0

        def fake_popen(*_args: object, **_kwargs: object) -> MagicMock:
            nonlocal call_count
            call_count += 1
            mock_proc = MagicMock()
            if call_count == 1:
                mock_proc.poll.return_value = -1
                mock_proc.stderr = MagicMock()
                mock_proc.stderr.readline.return_value = b""
                return mock_proc
            mock_proc.poll.return_value = None
            mock_proc.stderr = MagicMock()
            mock_proc.stderr.readline.return_value = b""
            return mock_proc

        with patch("subprocess.Popen", side_effect=fake_popen):
            ok = writer._open_process(out)
            assert ok is True
            assert writer.codec == "hevc_amf"
            assert writer.actual_codec == "libx265"
            assert writer.fallback_occurred is True

    def test_software_encoder_failure_does_not_loop_fallback(
        self, tmp_path: Path
    ) -> None:
        """При падении программного кодека libx264 повторный fallback не вызывается."""
        out = tmp_path / "test.mp4"
        # Патчим get_ffmpeg_path ДО конструирования (см. тест выше).
        with patch(
            "recorder.ffmpeg_writer.get_ffmpeg_path", return_value="ffmpeg"
        ):
            writer = FFmpegVideoWriter(
                output_path=out,
                width=1920,
                height=1080,
                codec="libx264",
            )

        with patch(
            "subprocess.Popen", side_effect=OSError("Process spawn failed")
        ):
            ok = writer._open_process(out)
            assert ok is False
            assert writer.actual_codec == "libx264"
            assert writer.fallback_occurred is False


class TestVideoRecorderCodecProperties:
    """Тесты свойств actual_codec и fallback_occurred в VideoRecorder."""

    def test_video_recorder_reports_actual_codec(self) -> None:
        """VideoRecorder проксирует actual_codec и fallback_occurred из writer."""
        recorder = VideoRecorder(codec="h264_qsv")
        assert recorder.actual_codec == "h264_qsv"
        assert recorder.fallback_occurred is False

        mock_writer = MagicMock()
        mock_writer.actual_codec = "libx264"
        mock_writer.fallback_occurred = True
        recorder._ffmpeg_writer = mock_writer

        assert recorder.actual_codec == "libx264"
        assert recorder.fallback_occurred is True
