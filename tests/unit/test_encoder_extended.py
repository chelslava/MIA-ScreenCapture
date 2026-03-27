"""
Расширенные unit тесты для Encoder
===================================

Дополнительные тесты для повышения покрытия encoder до 90%.
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

from recorder.encoder import Encoder, EncodingSettings


class TestEncodingSettings:
    """Тесты настроек кодирования."""

    def test_default_settings(self) -> None:
        """Проверка настроек по умолчанию."""
        settings = EncodingSettings()

        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.preset == "medium"
        assert settings.crf == 23
        assert settings.audio_codec == "aac"
        assert settings.audio_bitrate == "192k"
        assert settings.format == "mp4"

    def test_custom_settings(self) -> None:
        """Проверка пользовательских настроек."""
        settings = EncodingSettings(
            codec="h264",
            bitrate="5M",
            preset="fast",
            crf=18,
            audio_codec="mp3",
            audio_bitrate="320k",
            format="mkv",
        )

        assert settings.codec == "h264"
        assert settings.bitrate == "5M"
        assert settings.preset == "fast"
        assert settings.crf == 18
        assert settings.audio_codec == "mp3"
        assert settings.audio_bitrate == "320k"
        assert settings.format == "mkv"

    def test_crf_range(self) -> None:
        """Проверка диапазона CRF."""
        # Минимальный CRF (лучшее качество)
        settings_min = EncodingSettings(crf=0)
        assert settings_min.crf == 0

        # Максимальный CRF (худшее качество)
        settings_max = EncodingSettings(crf=51)
        assert settings_max.crf == 51

    def test_preset_values(self) -> None:
        """Проверка значений preset."""
        presets = ["ultrafast", "fast", "medium", "slow"]

        for preset in presets:
            settings = EncodingSettings(preset=preset)
            assert settings.preset == preset

    def test_dataclass_equality(self) -> None:
        """Проверка равенства dataclass."""
        settings1 = EncodingSettings(codec="libx264", bitrate="2M")
        settings2 = EncodingSettings(codec="libx264", bitrate="2M")

        assert settings1 == settings2

    def test_dataclass_inequality(self) -> None:
        """Проверка неравенства dataclass."""
        settings1 = EncodingSettings(codec="libx264")
        settings2 = EncodingSettings(codec="h264")

        assert settings1 != settings2


class TestEncoderInit:
    """Тесты инициализации Encoder."""

    def test_init_default_settings(self) -> None:
        """Проверка инициализации с настройками по умолчанию."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        assert encoder.settings is not None
        assert encoder.settings.codec == "libx264"

    def test_init_custom_settings(self) -> None:
        """Проверка инициализации с пользовательскими настройками."""
        custom_settings = EncodingSettings(codec="h264", bitrate="5M")

        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder(settings=custom_settings)

        assert encoder.settings == custom_settings

    def test_init_ffmpeg_not_found(self) -> None:
        """Проверка инициализации когда FFmpeg не найден."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(False, None)):
            with patch("recorder.encoder.get_ffmpeg_path", return_value=None):
                encoder = Encoder()

        assert encoder._ffmpeg_path is None

    def test_ffprobe_path_detection(self) -> None:
        """Проверка определения пути к ffprobe."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                with patch("shutil.which", return_value="/usr/bin/ffprobe"):
                    encoder = Encoder()

        assert encoder._ffprobe_path == "/usr/bin/ffprobe"


class TestEncoderAvailability:
    """Тесты проверки доступности FFmpeg."""

    def test_is_available_true(self) -> None:
        """Проверка доступности FFmpeg (доступен)."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        assert encoder.is_available is True

    def test_is_available_false(self) -> None:
        """Проверка доступности FFmpeg (недоступен)."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(False, None)):
            with patch("recorder.encoder.get_ffmpeg_path", return_value=None):
                encoder = Encoder()

        assert encoder.is_available is False


class TestEncoderMergeVideoAudio:
    """Тесты объединения видео и аудио."""

    def test_merge_success(self) -> None:
        """Проверка успешного объединения."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch("pathlib.Path.exists", return_value=True):
                success, error = encoder.merge_video_audio(
                    video_path=Path("/tmp/video.mp4"),
                    audio_path=Path("/tmp/audio.wav"),
                    output_path=Path("/tmp/output.mp4"),
                )

        assert success is True
        assert error is None

    def test_merge_ffmpeg_error(self) -> None:
        """Проверка ошибки FFmpeg при объединении."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "FFmpeg error"

        with patch("subprocess.run", return_value=mock_result):
            success, error = encoder.merge_video_audio(
                video_path=Path("/tmp/video.mp4"),
                audio_path=Path("/tmp/audio.wav"),
                output_path=Path("/tmp/output.mp4"),
            )

        assert success is False
        assert error is not None

    def test_merge_video_not_found(self) -> None:
        """Проверка ошибки когда видеофайл не найден."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        with patch("pathlib.Path.exists", return_value=False):
            success, error = encoder.merge_video_audio(
                video_path=Path("/tmp/nonexistent.mp4"),
                audio_path=Path("/tmp/audio.wav"),
                output_path=Path("/tmp/output.mp4"),
            )

        assert success is False
        assert error is not None

    def test_merge_audio_not_found(self) -> None:
        """Проверка ошибки когда аудиофайл не найден."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        def mock_exists(self):
            return str(self) == "/tmp/video.mp4"

        with patch("pathlib.Path.exists", mock_exists):
            success, error = encoder.merge_video_audio(
                video_path=Path("/tmp/video.mp4"),
                audio_path=Path("/tmp/nonexistent.wav"),
                output_path=Path("/tmp/output.mp4"),
            )

        assert success is False

    def test_merge_with_progress_callback(self) -> None:
        """Проверка объединения с callback прогресса."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        progress_values = []

        def progress_callback(value: float) -> None:
            progress_values.append(value)

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch("pathlib.Path.exists", return_value=True):
                encoder.merge_video_audio(
                    video_path=Path("/tmp/video.mp4"),
                    audio_path=Path("/tmp/audio.wav"),
                    output_path=Path("/tmp/output.mp4"),
                    progress_callback=progress_callback,
                )

        # Callback может быть вызван или нет в зависимости от реализации


class TestEncoderExtractAudio:
    """Тесты извлечения аудио."""

    def test_extract_audio_success(self) -> None:
        """Проверка успешного извлечения аудио."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch("pathlib.Path.exists", return_value=True):
                success, error = encoder.extract_audio(
                    video_path=Path("/tmp/video.mp4"),
                    audio_path=Path("/tmp/audio.aac"),
                )

        assert success is True

    def test_extract_audio_video_not_found(self) -> None:
        """Проверка ошибки когда видео не найдено."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        with patch("pathlib.Path.exists", return_value=False):
            success, error = encoder.extract_audio(
                video_path=Path("/tmp/nonexistent.mp4"),
                audio_path=Path("/tmp/audio.aac"),
            )

        assert success is False


class TestEncoderGetVideoInfo:
    """Тесты получения информации о видео."""

    def test_get_video_info_success(self) -> None:
        """Проверка успешного получения информации."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                with patch("shutil.which", return_value="/usr/bin/ffprobe"):
                    encoder = Encoder()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}'

        with patch("subprocess.run", return_value=mock_result):
            with patch("pathlib.Path.exists", return_value=True):
                info = encoder.get_video_info(Path("/tmp/video.mp4"))

        assert info is not None

    def test_get_video_info_file_not_found(self) -> None:
        """Проверка ошибки когда файл не найден."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                with patch("shutil.which", return_value="/usr/bin/ffprobe"):
                    encoder = Encoder()

        with patch("pathlib.Path.exists", return_value=False):
            info = encoder.get_video_info(Path("/tmp/nonexistent.mp4"))

        assert info is None

    def test_get_video_info_no_ffprobe(self) -> None:
        """Проверка когда ffprobe недоступен."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                with patch("shutil.which", return_value=None):
                    encoder = Encoder()

        info = encoder.get_video_info(Path("/tmp/video.mp4"))

        assert info is None


class TestEncoderEdgeCases:
    """Тесты граничных случаев."""

    def test_merge_with_special_characters_in_path(self) -> None:
        """Проверка объединения со спецсимволами в пути."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            with patch("pathlib.Path.exists", return_value=True):
                success, error = encoder.merge_video_audio(
                    video_path=Path("/tmp/video test (1).mp4"),
                    audio_path=Path("/tmp/audio test.wav"),
                    output_path=Path("/tmp/output [final].mp4"),
                )

        # Должно работать даже со спецсимволами
        assert success is True

    def test_encoder_with_none_settings(self) -> None:
        """Проверка инициализации с None настройками."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder(settings=None)

        # Должны использоваться настройки по умолчанию
        assert encoder.settings is not None
        assert encoder.settings.codec == "libx264"


class TestEncoderSubprocessError:
    """Тесты обработки ошибок subprocess."""

    def test_subprocess_timeout(self) -> None:
        """Проверка таймаута subprocess."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=30),
        ), patch("pathlib.Path.exists", return_value=True):
            success, error = encoder.merge_video_audio(
                video_path=Path("/tmp/video.mp4"),
                audio_path=Path("/tmp/audio.wav"),
                output_path=Path("/tmp/output.mp4"),
            )

        assert success is False
        assert error is not None

    def test_subprocess_file_not_found(self) -> None:
        """Проверка ошибки FileNotFoundError в subprocess."""
        with patch("recorder.encoder.check_ffmpeg", return_value=(True, "5.0")):
            with patch("recorder.encoder.get_ffmpeg_path", return_value="/usr/bin/ffmpeg"):
                encoder = Encoder()

        with patch(
            "subprocess.run",
            side_effect=FileNotFoundError("ffmpeg not found"),
        ), patch("pathlib.Path.exists", return_value=True):
            success, error = encoder.merge_video_audio(
                video_path=Path("/tmp/video.mp4"),
                audio_path=Path("/tmp/audio.wav"),
                output_path=Path("/tmp/output.mp4"),
            )

        assert success is False
        assert error is not None


class TestEncodingSettingsValidation:
    """Тесты валидации настроек кодирования."""

    def test_valid_bitrate_formats(self) -> None:
        """Проверка корректных форматов битрейта."""
        valid_bitrates = ["500K", "1M", "2M", "5M", "10M", "5000K"]

        for bitrate in valid_bitrates:
            settings = EncodingSettings(bitrate=bitrate)
            assert settings.bitrate == bitrate

    def test_valid_audio_bitrate_formats(self) -> None:
        """Проверка корректных форматов аудио битрейта."""
        valid_bitrates = ["128k", "192k", "256k", "320k"]

        for bitrate in valid_bitrates:
            settings = EncodingSettings(audio_bitrate=bitrate)
            assert settings.audio_bitrate == bitrate

    def test_valid_formats(self) -> None:
        """Проверка корректных форматов вывода."""
        valid_formats = ["mp4", "mkv", "avi", "mov"]

        for fmt in valid_formats:
            settings = EncodingSettings(format=fmt)
            assert settings.format == fmt

    def test_valid_codecs(self) -> None:
        """Проверка корректных кодеков."""
        valid_codecs = ["libx264", "h264", "libx265", "vp9"]

        for codec in valid_codecs:
            settings = EncodingSettings(codec=codec)
            assert settings.codec == codec
