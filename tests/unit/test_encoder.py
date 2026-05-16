"""
Тесты модуля кодировщика
========================

Тестирует классы EncodingSettings и Encoder.
"""

import tempfile
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

from recorder.encoder import Encoder, EncodingSettings, RecordingEncoder
from recorder.utils import FFmpegStatus


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
                with patch("recorder.encoder.get_ffprobe_path") as mock_probe:
                    mock_check.return_value = FFmpegStatus(
                        available=True, version="6.0"
                    )
                    mock_path.return_value = "/usr/bin/ffmpeg"
                    mock_probe.return_value = "/usr/bin/ffprobe"
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
                mock_check.return_value = FFmpegStatus(available=False)
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
                with patch("recorder.encoder.get_ffprobe_path") as mock_probe:
                    mock_check.return_value = FFmpegStatus(
                        available=True, version="6.0"
                    )
                    mock_path.return_value = "/usr/bin/ffmpeg"
                    mock_probe.return_value = "/usr/bin/ffprobe"
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
        assert Path(cmd[0]).name == "ffmpeg"
        assert "-y" in cmd
        assert "-i" in cmd
        assert str(video_path) in cmd
        assert str(audio_path) in cmd
        assert "-c:v" in cmd
        assert "-c:a" in cmd
        assert "-map" in cmd
        assert "-shortest" in cmd
        assert str(output_path) in cmd


class TestEncoderProcessCleanup:
    """Тесты обработки stderr и очистки временных файлов."""

    @pytest.fixture
    def encoder(self) -> Encoder:
        """Создаёт кодировщик с замоканным FFmpeg."""
        with patch.object(Encoder, "_check_ffmpeg", return_value=True):
            return Encoder()

    def test_run_ffmpeg_long_process_reads_stderr_tail(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка чтения хвоста stderr и удаления временного файла."""
        stderr_path = tmp_path / "ffmpeg_stderr.log"
        real_named_temporary_file = tempfile.NamedTemporaryFile

        def fake_temp_file(*args, **kwargs):
            if kwargs.get("prefix") == "ffmpeg_stderr_":
                return open(stderr_path, "w+b")
            return real_named_temporary_file(*args, **kwargs)

        def fake_run(cmd, stdout, stderr, timeout, **kwargs):
            _ = cmd, stdout, timeout, kwargs
            stderr.write(b"line 1\nline 2\n")
            stderr.flush()
            return MagicMock(returncode=1, stderr="")

        with (
            patch(
                "recorder.encoder.tempfile.NamedTemporaryFile",
                side_effect=fake_temp_file,
            ),
            patch("recorder.encoder.subprocess.run", side_effect=fake_run),
        ):
            result = encoder._run_ffmpeg_long_process(["ffmpeg"], timeout=1)

        assert result.returncode == 1
        assert result.stderr_tail is not None
        assert "line 2" in result.stderr_tail
        assert not stderr_path.exists()

    def test_run_ffmpeg_long_process_uses_process_stderr_when_log_empty(
        self, encoder: Encoder, tmp_path: Path
    ) -> None:
        """Проверка fallback на stderr процесса при пустом файле лога."""
        stderr_path = tmp_path / "ffmpeg_stderr.log"
        real_named_temporary_file = tempfile.NamedTemporaryFile

        def fake_temp_file(*args, **kwargs):
            if kwargs.get("prefix") == "ffmpeg_stderr_":
                return open(stderr_path, "w+b")
            return real_named_temporary_file(*args, **kwargs)

        def fake_run(cmd, stdout, stderr, timeout, **kwargs):
            _ = cmd, stdout, stderr, timeout, kwargs
            return MagicMock(returncode=1, stderr="  process error  ")

        with (
            patch(
                "recorder.encoder.tempfile.NamedTemporaryFile",
                side_effect=fake_temp_file,
            ),
            patch("recorder.encoder.subprocess.run", side_effect=fake_run),
        ):
            result = encoder._run_ffmpeg_long_process(["ffmpeg"], timeout=1)

        assert result.returncode == 1
        assert result.stderr_tail == "process error"
        assert not stderr_path.exists()


class TestRecordingEncoder:
    """Тесты высокоуровневого кодировщика записи."""

    def test_setup_creates_temp_paths(self, tmp_path: Path) -> None:
        """Проверка создания временных путей записи."""
        temp_dir = tmp_path / "recorder_123"
        temp_dir.mkdir()
        output_path = tmp_path / "output.mp4"

        with (
            patch("recorder.encoder.Encoder", return_value=MagicMock()),
            patch(
                "recorder.encoder.tempfile.mkdtemp",
                return_value=str(temp_dir),
            ),
        ):
            encoder = RecordingEncoder(output_path)
            temp_video, temp_audio = encoder.setup()

        assert encoder._temp_dir == temp_dir
        assert temp_video == temp_dir / "video_temp.mp4"
        assert temp_audio == temp_dir / "audio_temp.wav"

    def test_finalize_merges_video_and_audio_and_cleans_up(
        self, tmp_path: Path
    ) -> None:
        """Проверка объединения видео и аудио с очисткой временной папки."""
        temp_dir = tmp_path / "recorder_456"
        temp_dir.mkdir()
        output_path = tmp_path / "output.mp4"
        merge_result = (True, None)
        mock_encoder = MagicMock()
        mock_encoder.merge_video_audio.return_value = merge_result

        with (
            patch("recorder.encoder.Encoder", return_value=mock_encoder),
            patch(
                "recorder.encoder.tempfile.mkdtemp",
                return_value=str(temp_dir),
            ),
            patch.object(
                RecordingEncoder,
                "_move_final_output",
                return_value=(True, None),
            ) as mock_move,
        ):
            recording_encoder = RecordingEncoder(output_path)
            temp_video, temp_audio = recording_encoder.setup()
            temp_video.write_bytes(b"video")
            temp_audio.write_bytes(b"audio")

            result = recording_encoder.finalize(has_audio=True)

        assert result == merge_result
        mock_encoder.merge_video_audio.assert_called_once_with(
            temp_video,
            temp_audio,
            temp_dir / "final_temp.mp4",
            keep_originals=False,
            progress_callback=None,
            cancel_event=ANY,
        )
        mock_move.assert_called_once_with(temp_dir / "final_temp.mp4")
        assert not temp_dir.exists()
        assert recording_encoder._temp_dir is None
        assert recording_encoder._temp_video is None
        assert recording_encoder._temp_audio is None

    def test_finalize_uses_encode_video_without_audio(
        self, tmp_path: Path
    ) -> None:
        """Проверка перекодирования без аудиодорожки."""
        temp_dir = tmp_path / "recorder_789"
        temp_dir.mkdir()
        output_path = tmp_path / "output.mp4"
        mock_encoder = MagicMock()
        mock_encoder.encode_video.return_value = (True, None)

        with (
            patch("recorder.encoder.Encoder", return_value=mock_encoder),
            patch(
                "recorder.encoder.tempfile.mkdtemp",
                return_value=str(temp_dir),
            ),
            patch.object(
                RecordingEncoder,
                "_move_final_output",
                return_value=(True, None),
            ) as mock_move,
        ):
            recording_encoder = RecordingEncoder(output_path)
            temp_video, _ = recording_encoder.setup()
            temp_video.write_bytes(b"video")

            result = recording_encoder.finalize(has_audio=False)

        assert result == (True, None)
        mock_encoder.encode_video.assert_called_once_with(
            temp_video,
            temp_dir / "final_temp.mp4",
            progress_callback=None,
            cancel_event=ANY,
        )
        mock_move.assert_called_once_with(temp_dir / "final_temp.mp4")
        assert not temp_dir.exists()

    def test_cleanup_handles_rmtree_error(self, tmp_path: Path) -> None:
        """Проверка безопасной очистки при ошибке удаления каталога."""
        temp_dir = tmp_path / "recorder_999"
        temp_dir.mkdir()
        with patch("recorder.encoder.Encoder", return_value=MagicMock()):
            recording_encoder = RecordingEncoder(tmp_path / "output.mp4")
            recording_encoder._temp_dir = temp_dir
            recording_encoder._temp_video = temp_dir / "video_temp.mp4"
            recording_encoder._temp_audio = temp_dir / "audio_temp.wav"

        with patch(
            "recorder.encoder.shutil.rmtree",
            side_effect=OSError("cleanup failed"),
        ):
            recording_encoder._cleanup()

        assert recording_encoder._temp_dir is None
        assert recording_encoder._temp_video is None
        assert recording_encoder._temp_audio is None

    def test_cancel_calls_cleanup(self, tmp_path: Path) -> None:
        """Проверка отмены записи через очистку временных файлов."""
        with patch("recorder.encoder.Encoder", return_value=MagicMock()):
            recording_encoder = RecordingEncoder(tmp_path / "output.mp4")

        with patch.object(recording_encoder, "_cleanup") as mock_cleanup:
            recording_encoder.cancel()

        mock_cleanup.assert_called_once()

    def test_cancel_during_finalization_only_sets_cancel_flag(
        self, tmp_path: Path
    ) -> None:
        """Во время финализации cancel не должен преждевременно чистить файлы."""
        with patch("recorder.encoder.Encoder", return_value=MagicMock()):
            recording_encoder = RecordingEncoder(tmp_path / "output.mp4")

        recording_encoder._is_finalizing = True

        with patch.object(recording_encoder, "_cleanup") as mock_cleanup:
            recording_encoder.cancel()

        assert recording_encoder._cancel_requested.is_set() is True
        mock_cleanup.assert_not_called()
