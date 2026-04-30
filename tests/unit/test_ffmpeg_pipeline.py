"""Unit-тесты слоя сервисов FFmpeg-пайплайна."""

from __future__ import annotations

import subprocess
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

from recorder.ffmpeg_pipeline import (
    FinalizeService,
    ProcessResult,
    ProcessSupervisor,
    RecoveryPolicy,
)

# ---------------------------------------------------------------------------
# ProcessSupervisor
# ---------------------------------------------------------------------------


class TestProcessSupervisor:
    """Тесты управления жизненным циклом FFmpeg-процесса."""

    def _make_supervisor(self) -> ProcessSupervisor:
        return ProcessSupervisor(ffmpeg_path="ffmpeg")

    def test_run_simple_success(self) -> None:
        """Успешный запуск без cancel_event возвращает returncode=0."""
        supervisor = self._make_supervisor()
        fake_proc = MagicMock()
        fake_proc.returncode = 0

        with patch("subprocess.run", return_value=fake_proc):
            result = supervisor.run(["ffmpeg", "-version"], timeout=30)

        assert result.returncode == 0
        assert result.cancelled is False
        assert result.stderr_tail is None

    def test_run_simple_failure_returns_stderr_tail(
        self, tmp_path: Path
    ) -> None:
        """При returncode != 0 возвращается хвост stderr."""
        supervisor = self._make_supervisor()
        fake_proc = MagicMock()
        fake_proc.returncode = 1

        stderr_file = tmp_path / "err.log"
        stderr_file.write_text("error: codec not found", encoding="utf-8")

        with (
            patch("subprocess.run", return_value=fake_proc),
            patch.object(
                supervisor,
                "_read_stderr_tail",
                return_value="error: codec not found",
            ),
        ):
            result = supervisor.run(["ffmpeg", "-bad"], timeout=30)

        assert result.returncode == 1
        assert result.stderr_tail == "error: codec not found"

    def test_run_cancellable_cancel_event_terminates_process(self) -> None:
        """Установка cancel_event завершает процесс и выставляет cancelled=True."""
        supervisor = self._make_supervisor()
        cancel_event = threading.Event()
        cancel_event.set()

        fake_proc = MagicMock(spec=subprocess.Popen)
        fake_proc.returncode = -1
        fake_proc.poll.return_value = None

        with patch("subprocess.Popen", return_value=fake_proc):
            result = supervisor._run_cancellable(
                cmd=["ffmpeg"],
                stderr_file=MagicMock(),
                timeout=60,
                cancel_event=cancel_event,
                creationflags=0,
            )

        assert result.cancelled is True
        fake_proc.terminate.assert_called_once()

    def test_run_simple_calls_subprocess_run(self) -> None:
        """Без cancel_event используется subprocess.run."""
        supervisor = self._make_supervisor()
        fake_proc = MagicMock()
        fake_proc.returncode = 0

        with patch("subprocess.run", return_value=fake_proc) as mock_run:
            supervisor._run_simple(
                cmd=["ffmpeg"],
                stderr_file=MagicMock(),
                timeout=10,
                creationflags=0,
            )

        mock_run.assert_called_once()

    def test_run_cancellable_process_finishes_normally(self) -> None:
        """Если процесс завершается нормально, cancelled=False."""
        supervisor = self._make_supervisor()
        cancel_event = threading.Event()

        fake_proc = MagicMock(spec=subprocess.Popen)
        fake_proc.returncode = 0
        fake_proc.poll.return_value = 0

        with patch("subprocess.Popen", return_value=fake_proc):
            result = supervisor._run_cancellable(
                cmd=["ffmpeg"],
                stderr_file=MagicMock(),
                timeout=60,
                cancel_event=cancel_event,
                creationflags=0,
            )

        assert result.cancelled is False
        assert result.returncode == 0

    def test_read_stderr_tail_returns_none_on_success(
        self, tmp_path: Path
    ) -> None:
        """При returncode=0 и cancelled=False stderr_tail не читается."""
        supervisor = self._make_supervisor()
        log_file = tmp_path / "stderr.log"
        log_file.write_text("some output", encoding="utf-8")

        result = supervisor._read_stderr_tail(
            log_file, returncode=0, cancelled=False
        )

        assert result is None

    def test_read_stderr_tail_reads_on_error(self, tmp_path: Path) -> None:
        """При returncode != 0 возвращается содержимое хвоста."""
        supervisor = self._make_supervisor()
        log_file = tmp_path / "stderr.log"
        log_file.write_text("fatal error message", encoding="utf-8")

        result = supervisor._read_stderr_tail(
            log_file, returncode=1, cancelled=False
        )

        assert result == "fatal error message"

    def test_read_stderr_tail_returns_none_for_missing_file(self) -> None:
        """Если файл не существует — возвращается None."""
        supervisor = self._make_supervisor()
        result = supervisor._read_stderr_tail(
            Path("/nonexistent/file.log"), returncode=1, cancelled=False
        )
        assert result is None


# ---------------------------------------------------------------------------
# RecoveryPolicy
# ---------------------------------------------------------------------------


class TestRecoveryPolicy:
    """Тесты политик восстановления при ошибках."""

    def test_move_with_fallback_success(self, tmp_path: Path) -> None:
        """Успешное перемещение через Path.replace."""
        src = tmp_path / "src.mp4"
        src.write_bytes(b"data")
        dst = tmp_path / "dst.mp4"

        policy = RecoveryPolicy(fallback_dir=tmp_path / "fallback")
        final_path, error = policy.move_with_fallback(src, dst)

        assert error is None
        assert final_path == dst
        assert dst.exists()
        assert not src.exists()

    def test_move_with_fallback_uses_fallback_on_permission_error(
        self, tmp_path: Path
    ) -> None:
        """При PermissionError файл копируется в fallback_dir."""
        src = tmp_path / "src.mp4"
        src.write_bytes(b"data")
        dst = tmp_path / "readonly" / "dst.mp4"
        fallback_dir = tmp_path / "fallback"

        policy = RecoveryPolicy(fallback_dir=fallback_dir)

        with patch.object(
            Path, "replace", side_effect=PermissionError("access denied")
        ):
            final_path, error = policy.move_with_fallback(src, dst)

        assert error is None
        assert final_path.exists()

    def test_cleanup_corrupted_removes_file(self, tmp_path: Path) -> None:
        """Повреждённый файл удаляется из файловой системы."""
        corrupt = tmp_path / "corrupt.mp4"
        corrupt.write_bytes(b"\x00" * 10)

        policy = RecoveryPolicy()
        policy.cleanup_corrupted(corrupt)

        assert not corrupt.exists()

    def test_cleanup_corrupted_noop_if_missing(self) -> None:
        """Не падает, если файла уже нет."""
        policy = RecoveryPolicy()
        policy.cleanup_corrupted(Path("/nonexistent/file.mp4"))

    def test_move_with_fallback_reports_error_on_full_failure(
        self, tmp_path: Path
    ) -> None:
        """Если все попытки неудачны, возвращается описание ошибки."""
        src = tmp_path / "src.mp4"
        src.write_bytes(b"data")
        dst = tmp_path / "dst.mp4"
        policy = RecoveryPolicy(fallback_dir=tmp_path / "fallback")

        with (
            patch.object(
                Path, "replace", side_effect=PermissionError("no access")
            ),
            patch("shutil.copy2", side_effect=OSError("disk full")),
        ):
            _final_path, error = policy.move_with_fallback(src, dst)

        assert error is not None
        assert "fallback" in error.lower() or "переместить" in error.lower()


# ---------------------------------------------------------------------------
# FinalizeService
# ---------------------------------------------------------------------------


def _make_finalize_service(
    supervisor: ProcessSupervisor | None = None,
    recovery: RecoveryPolicy | None = None,
) -> FinalizeService:
    if supervisor is None:
        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=0, stderr_tail=None, cancelled=False
        )
    if recovery is None:
        recovery = MagicMock(spec=RecoveryPolicy)
        recovery.move_with_fallback.side_effect = lambda src, dst: (dst, None)
    return FinalizeService(
        supervisor=supervisor,
        recovery=recovery,
        ffmpeg_path="ffmpeg",
    )


class TestFinalizeService:
    """Тесты финализации записи."""

    def test_finalize_success_with_audio(self, tmp_path: Path) -> None:
        """Успешная финализация с аудио возвращает success=True."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"video_data")
        audio = tmp_path / "audio.wav"
        audio.write_bytes(b"audio_data")
        output = tmp_path / "output.mp4"

        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=0, stderr_tail=None, cancelled=False
        )
        recovery = MagicMock(spec=RecoveryPolicy)
        recovery.move_with_fallback.side_effect = lambda src, dst: (dst, None)

        service = FinalizeService(
            supervisor=supervisor,
            recovery=recovery,
            ffmpeg_path="ffmpeg",
        )

        with patch.object(
            service, "validate_output", return_value=(True, None)
        ):
            result = service.finalize(video, audio, output)

        assert result.success is True
        assert result.error is None

    def test_finalize_success_without_audio(self, tmp_path: Path) -> None:
        """Финализация без аудиофайла использует encode_only."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"video_data")
        output = tmp_path / "output.mp4"

        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=0, stderr_tail=None, cancelled=False
        )
        recovery = MagicMock(spec=RecoveryPolicy)
        recovery.move_with_fallback.side_effect = lambda src, dst: (dst, None)

        service = FinalizeService(
            supervisor=supervisor,
            recovery=recovery,
            ffmpeg_path="ffmpeg",
        )

        with patch.object(
            service, "validate_output", return_value=(True, None)
        ):
            result = service.finalize(video, None, output)

        assert result.success is True
        supervisor.run.assert_called_once()
        cmd_used = supervisor.run.call_args[0][0]
        assert "-i" in cmd_used
        assert "-map" not in cmd_used

    def test_finalize_returns_error_when_video_missing(
        self, tmp_path: Path
    ) -> None:
        """Если видеофайл не существует, финализация не запускается."""
        service = _make_finalize_service()
        result = service.finalize(
            tmp_path / "missing.mp4", None, tmp_path / "out.mp4"
        )
        assert result.success is False
        assert "не найден" in (result.error or "")

    def test_finalize_cancelled_process(self, tmp_path: Path) -> None:
        """Отмена процесса возвращает success=False."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"data")
        output = tmp_path / "output.mp4"

        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=-1, stderr_tail=None, cancelled=True
        )
        service = _make_finalize_service(supervisor=supervisor)

        result = service.finalize(video, None, output)

        assert result.success is False
        assert result.error == "Отменено"

    def test_finalize_ffmpeg_error(self, tmp_path: Path) -> None:
        """Ненулевой returncode FFmpeg возвращает ошибку."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"data")
        output = tmp_path / "output.mp4"

        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=1, stderr_tail="encoder not found", cancelled=False
        )
        service = _make_finalize_service(supervisor=supervisor)

        result = service.finalize(video, None, output)

        assert result.success is False
        assert "encoder not found" in (result.error or "")

    def test_finalize_removes_temp_file_on_error(self, tmp_path: Path) -> None:
        """Временный output-файл очищается даже при ошибке валидации."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"data")
        output = tmp_path / "output.mp4"

        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=0, stderr_tail=None, cancelled=False
        )
        recovery = MagicMock(spec=RecoveryPolicy)
        recovery.move_with_fallback.side_effect = lambda src, dst: (dst, None)

        service = FinalizeService(
            supervisor=supervisor, recovery=recovery, ffmpeg_path="ffmpeg"
        )

        with patch.object(
            service, "validate_output", return_value=(False, "пуст")
        ):
            result = service.finalize(video, None, output)

        assert result.success is False
        recovery.cleanup_corrupted.assert_called_once()

    def test_validate_output_fails_for_missing_file(
        self, tmp_path: Path
    ) -> None:
        """Валидация failing если файла нет."""
        service = _make_finalize_service()
        ok, err = service.validate_output(tmp_path / "missing.mp4")
        assert ok is False
        assert err is not None

    def test_validate_output_fails_for_empty_file(
        self, tmp_path: Path
    ) -> None:
        """Валидация failing если файл пустой."""
        service = _make_finalize_service()
        empty = tmp_path / "empty.mp4"
        empty.write_bytes(b"")
        ok, err = service.validate_output(empty)
        assert ok is False
        assert "пуст" in (err or "")

    def test_validate_output_success_for_nonempty_file(
        self, tmp_path: Path
    ) -> None:
        """Валидация успешна если файл непустой."""
        service = _make_finalize_service()
        real_file = tmp_path / "video.mp4"
        real_file.write_bytes(b"\x00" * 1024)
        ok, err = service.validate_output(real_file)
        assert ok is True
        assert err is None

    def test_finalize_move_error_propagated(self, tmp_path: Path) -> None:
        """Ошибка перемещения файла пробрасывается в результат."""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"data")
        output = tmp_path / "output.mp4"

        supervisor = MagicMock(spec=ProcessSupervisor)
        supervisor.run.return_value = ProcessResult(
            returncode=0, stderr_tail=None, cancelled=False
        )
        recovery = MagicMock(spec=RecoveryPolicy)
        recovery.move_with_fallback.return_value = (output, "диск недоступен")

        service = FinalizeService(
            supervisor=supervisor, recovery=recovery, ffmpeg_path="ffmpeg"
        )

        with patch.object(
            service, "validate_output", return_value=(True, None)
        ):
            result = service.finalize(video, None, output)

        assert result.success is False
        assert "диск недоступен" in (result.error or "")
