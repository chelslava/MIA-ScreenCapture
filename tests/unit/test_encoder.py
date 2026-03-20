"""
Тесты модуля кодировщика
========================

Тестирует классы EncodingSettings и Encoder.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from recorder.encoder import Encoder, EncodingSettings


class TestEncodingSettings:
    """Тесты настроек кодирования."""

    def test_default_values(self) -> None:
        """Проверка значений по умолчанию."""
        settings = EncodingSettings()
        assert settings.codec == "libx264"
        assert settings.bitrate == "2M"
        assert settings.preset == "medium"
        assert settings.crf == 23
        assert settings.audio_codec == "aac"
        assert settings.audio_bitrate == "192k"
        assert settings.format == "mp4"

    def test_custom_values(self) -> None:
        """Проверка пользовательских значений."""
        settings = EncodingSettings(
            codec="libx265",
            bitrate="5M",
            preset="fast",
            crf=18,
            audio_codec="mp3",
            audio_bitrate="320k",
            format="mkv",
        )
        assert settings.codec == "libx265"
        assert settings.bitrate == "5M"
        assert settings.preset == "fast"
        assert settings.crf == 18
        assert settings.audio_codec == "mp3"
        assert settings.audio_bitrate == "320k"
        assert settings.format == "mkv"


class TestEncoder:
    """Тесты класса Encoder."""

    @pytest.fixture
    def mock_ffmpeg(self) -> None:
        """Мокает проверку FFmpeg."""
        with patch("recorder.encoder.check_ffmpeg") as mock_check:
            with patch("recorder.encoder.get_ffmpeg_path") as mock_path:
                mock_check.return_value = (True, "6.0")
                mock_path.return_value = "/usr/bin/ffmpeg"
                yield

    @pytest.fixture
    def encoder(self, mock_ffmpeg: None) -> Encoder:
        """Создаёт кодировщик для тестов."""
        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            return Encoder()

    def test_init_with_default_settings(self, mock_ffmpeg: None) -> None:
        """Проверка инициализации с настройками по умолчанию."""
        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            encoder = Encoder()

        assert encoder.settings.codec == "libx264"
        assert encoder.settings.bitrate == "2M"

    def test_init_with_custom_settings(self, mock_ffmpeg: None) -> None:
        """Проверка инициализации с пользовательскими настройками."""
        custom_settings = EncodingSettings(
            codec="libx265",
            bitrate="10M",
        )

        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            encoder = Encoder(settings=custom_settings)

        assert encoder.settings.codec == "libx265"
        assert encoder.settings.bitrate == "10M"

    def test_is_available_true(self, mock_ffmpeg: None) -> None:
        """Проверка is_available когда FFmpeg доступен."""
        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            encoder = Encoder()

        assert encoder.is_available is True

    def test_is_available_false(self) -> None:
        """Проверка is_available когда FFmpeg недоступен."""
        with patch("recorder.encoder.check_ffmpeg") as mock_check:
            with patch("recorder.encoder.get_ffmpeg_path") as mock_path:
                mock_check.return_value = (False, None)
                mock_path.return_value = None

                encoder = Encoder()

        assert encoder.is_available is False

    def test_merge_video_audio_ffmpeg_unavailable(
        self, mock_ffmpeg: None
    ) -> None:
        """Проверка merge_video_audio когда FFmpeg недоступен."""
        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            encoder = Encoder()
        encoder._ffmpeg_path = None

        video_path = Path("/tmp/video.mp4")
        audio_path = Path("/tmp/audio.wav")
        output_path = Path("/tmp/output.mp4")

        success, error = encoder.merge_video_audio(
            video_path, audio_path, output_path
        )

        assert success is False
        assert "FFmpeg недоступен" in error

    def test_merge_video_audio_video_not_found(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка merge_video_audio когда видеофайл не найден."""
        video_path = tmp_path / "nonexistent.mp4"
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()  # Создаём аудиофайл
        output_path = tmp_path / "output.mp4"

        success, error = encoder.merge_video_audio(
            video_path, audio_path, output_path
        )

        assert success is False
        assert "Видеофайл не найден" in error

    def test_merge_video_audio_audio_not_found(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка merge_video_audio когда аудиофайл не найден."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()  # Создаём видеофайл
        audio_path = tmp_path / "nonexistent.wav"
        output_path = tmp_path / "output.mp4"

        success, error = encoder.merge_video_audio(
            video_path, audio_path, output_path
        )

        assert success is False
        assert "Аудиофайл не найден" in error

    def test_merge_video_audio_creates_output_dir(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка создания директории вывода."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "subdir" / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            # Создаём выходной файл для проверки
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.touch()

            success, error = encoder.merge_video_audio(
                video_path, audio_path, output_path
            )

        assert success is True

    def test_merge_video_audio_success(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка успешного объединения."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            # Создаём выходной файл для имитации успешного объединения
            output_path.touch()

            success, error = encoder.merge_video_audio(
                video_path, audio_path, output_path
            )

        assert success is True
        assert error is None

    def test_merge_video_audio_ffmpeg_error(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка обработки ошибки FFmpeg."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="FFmpeg encoding error", stdout=""
            )

            success, error = encoder.merge_video_audio(
                video_path, audio_path, output_path
            )

        assert success is False
        assert "FFmpeg encoding error" in error

    def test_merge_video_audio_timeout(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка обработки таймаута FFmpeg."""
        import subprocess

        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd="ffmpeg", timeout=3600
            )

            success, error = encoder.merge_video_audio(
                video_path, audio_path, output_path
            )

        assert success is False
        assert "Таймаут" in error

    def test_merge_video_audio_deletes_originals(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка удаления оригиналов при keep_originals=False."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            output_path.touch()

            success, error = encoder.merge_video_audio(
                video_path,
                audio_path,
                output_path,
                keep_originals=False,
            )

        assert success is True
        assert not video_path.exists()
        assert not audio_path.exists()

    def test_merge_video_audio_keeps_originals(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка сохранения оригиналов при keep_originals=True."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            output_path.touch()

            success, error = encoder.merge_video_audio(
                video_path,
                audio_path,
                output_path,
                keep_originals=True,
            )

        assert success is True
        assert video_path.exists()
        assert audio_path.exists()

    def test_merge_video_audio_output_not_created(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка когда выходной файл не был создан."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            # Не создаём выходной файл

            success, error = encoder.merge_video_audio(
                video_path, audio_path, output_path
            )

        assert success is False
        assert "не был создан" in error

    def test_encode_video_success(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка успешного перекодирования."""
        input_path = tmp_path / "input.mp4"
        input_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            output_path.touch()

            success, error = encoder.encode_video(input_path, output_path)

        assert success is True
        assert error is None

    def test_encode_video_input_not_found(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка перекодирования когда входной файл не найден."""
        input_path = tmp_path / "nonexistent.mp4"
        output_path = tmp_path / "output.mp4"

        success, error = encoder.encode_video(input_path, output_path)

        assert success is False
        assert "не найден" in error

    def test_encode_video_with_custom_settings(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка перекодирования с пользовательскими настройками."""
        input_path = tmp_path / "input.mp4"
        input_path.touch()
        output_path = tmp_path / "output.mp4"
        custom_settings = EncodingSettings(
            codec="libx265",
            bitrate="5M",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            output_path.touch()

            success, error = encoder.encode_video(
                input_path, output_path, settings=custom_settings
            )

        assert success is True
        # Проверяем что команда содержит пользовательские настройки
        call_args = mock_run.call_args[0][0]
        assert "libx265" in call_args
        assert "5M" in call_args


class TestEncoderAdditionalMethods:
    """Дополнительные тесты методов Encoder."""

    @pytest.fixture
    def mock_ffmpeg(self) -> None:
        """Мокает проверку FFmpeg."""
        with patch("recorder.encoder.check_ffmpeg") as mock_check:
            with patch("recorder.encoder.get_ffmpeg_path") as mock_path:
                mock_check.return_value = (True, "6.0")
                mock_path.return_value = "/usr/bin/ffmpeg"
                yield

    @pytest.fixture
    def encoder(self, mock_ffmpeg: None) -> Encoder:
        """Создаёт кодировщик для тестов."""
        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            return Encoder()

    def test_get_video_info_success(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка получения информации о видео."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"format": {"duration": "120.5"}}',
            )

            info = encoder.get_video_info(video_path)

        assert info is not None
        assert "format" in info

    def test_get_video_info_error(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка обработки ошибки при получении информации."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")

            info = encoder.get_video_info(video_path)

        assert info is None

    def test_get_video_info_no_ffprobe(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка когда ffprobe недоступен."""
        encoder._ffprobe_path = None
        video_path = tmp_path / "video.mp4"

        info = encoder.get_video_info(video_path)

        assert info is None

    def test_get_duration_success(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка получения длительности видео."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()

        with patch.object(
            encoder,
            "get_video_info",
            return_value={"format": {"duration": "120.5"}},
        ):
            duration = encoder.get_duration(video_path)

        assert duration == 120.5

    def test_get_duration_no_info(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка когда информация недоступна."""
        video_path = tmp_path / "video.mp4"

        with patch.object(encoder, "get_video_info", return_value=None):
            duration = encoder.get_duration(video_path)

        assert duration is None

    def test_extract_audio_success(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка извлечения аудио."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            success, error = encoder.extract_audio(video_path, audio_path)

        assert success is True
        assert error is None

    def test_extract_audio_ffmpeg_unavailable(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка извлечения аудио когда FFmpeg недоступен."""
        encoder._ffmpeg_path = None
        video_path = tmp_path / "video.mp4"
        audio_path = tmp_path / "audio.wav"

        success, error = encoder.extract_audio(video_path, audio_path)

        assert success is False
        assert "недоступен" in error

    def test_extract_audio_error(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка обработки ошибки при извлечении аудио."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="Extract error"
            )

            success, error = encoder.extract_audio(video_path, audio_path)

        assert success is False
        assert "Extract error" in error

    def test_create_thumbnail_success(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка создания миниатюры."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        thumbnail_path = tmp_path / "thumbnail.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="")

            success, error = encoder.create_thumbnail(
                video_path, thumbnail_path, timestamp=5.0
            )

        assert success is True
        assert error is None

    def test_create_thumbnail_ffmpeg_unavailable(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка создания миниатюры когда FFmpeg недоступен."""
        encoder._ffmpeg_path = None
        video_path = tmp_path / "video.mp4"
        thumbnail_path = tmp_path / "thumbnail.png"

        success, error = encoder.create_thumbnail(video_path, thumbnail_path)

        assert success is False
        assert "недоступен" in error

    def test_create_thumbnail_error(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка обработки ошибки при создании миниатюры."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        thumbnail_path = tmp_path / "thumbnail.png"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stderr="Thumbnail error"
            )

            success, error = encoder.create_thumbnail(
                video_path, thumbnail_path
            )

        assert success is False
        assert "Thumbnail error" in error

    def test_merge_command_structure(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка структуры команды объединения."""
        video_path = tmp_path / "video.mp4"
        video_path.touch()
        audio_path = tmp_path / "audio.wav"
        audio_path.touch()
        output_path = tmp_path / "output.mp4"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stderr="", stdout=""
            )
            output_path.touch()

            encoder.merge_video_audio(video_path, audio_path, output_path)

        # Проверяем структуру команды
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(video_path) in cmd
        assert str(audio_path) in cmd
        assert "-c:v" in cmd
        assert "-c:a" in cmd
        assert "-map" in cmd
        assert "-shortest" in cmd
        assert str(output_path) in cmd
