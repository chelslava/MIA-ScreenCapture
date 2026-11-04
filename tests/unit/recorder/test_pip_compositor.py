"""Тесты композитинга PiP-оверлея (#165)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from core.recording_types import PiPPosition, PiPSettings
from recorder.pip_compositor import (
    build_pip_filter_complex,
    compose_pip_overlay,
    pip_overlay_position_expr,
)


class TestPipOverlayPositionExpr:
    """Выражения позиции overlay для четырёх углов (#165)."""

    def test_bottom_right(self) -> None:
        x, y = pip_overlay_position_expr(
            PiPPosition.BOTTOM_RIGHT, margin_px=24
        )
        assert x == "main_w-overlay_w-24"
        assert y == "main_h-overlay_h-24"

    def test_bottom_left(self) -> None:
        x, y = pip_overlay_position_expr(PiPPosition.BOTTOM_LEFT, margin_px=16)
        assert x == "16"
        assert y == "main_h-overlay_h-16"

    def test_top_left(self) -> None:
        x, y = pip_overlay_position_expr(PiPPosition.TOP_LEFT, margin_px=0)
        assert x == "0"
        assert y == "0"

    def test_top_right(self) -> None:
        x, y = pip_overlay_position_expr(PiPPosition.TOP_RIGHT, margin_px=8)
        assert x == "main_w-overlay_w-8"
        assert y == "8"


class TestBuildPipFilterComplex:
    """Построение filter_complex (#165)."""

    def test_contains_scale_and_overlay(self) -> None:
        settings = PiPSettings(
            enabled=True,
            position=PiPPosition.BOTTOM_RIGHT,
            size_percent=20,
        )
        filter_str = build_pip_filter_complex(settings)

        assert "[1:v]scale=main_w*20/100:-2[cam];" in filter_str
        assert "[0:v][cam]overlay=x=main_w-overlay_w-24" in filter_str
        assert "y=main_h-overlay_h-24" in filter_str


class TestComposePipOverlay:
    """Запуск композитинга через FFmpeg (#165)."""

    def test_missing_base_file(self, tmp_path: Path) -> None:
        """Отсутствующий основной файл — ошибка без запуска FFmpeg."""
        ok, error = compose_pip_overlay(
            base_video=tmp_path / "no.mp4",
            camera_video=tmp_path / "cam.mp4",
            output_path=tmp_path / "out.mp4",
            settings=PiPSettings(enabled=True),
        )
        assert ok is False
        assert error is not None and "не найден" in error

    def test_missing_camera_file(self, tmp_path: Path) -> None:
        """Отсутствующий файл камеры — ошибка без запуска FFmpeg."""
        base = tmp_path / "base.mp4"
        base.write_bytes(b"v")
        ok, error = compose_pip_overlay(
            base_video=base,
            camera_video=tmp_path / "no.mp4",
            output_path=tmp_path / "out.mp4",
            settings=PiPSettings(enabled=True),
        )
        assert ok is False
        assert error is not None and "не найден" in error

    def test_success_replaces_base_in_place(self, tmp_path: Path) -> None:
        """Успех при output == base: замена через временный файл."""
        base = tmp_path / "base.mp4"
        base.write_bytes(b"base")
        camera = tmp_path / "base_pipcam.mp4"
        camera.write_bytes(b"cam")

        result = MagicMock(returncode=0, stderr="")

        def fake_run(cmd, **_kwargs):  # type: ignore[no-untyped-def]
            # FFmpeg «создаёт» временный файл с наложением
            target = Path(cmd[-1])
            target.write_bytes(b"composed")
            return result

        with patch(
            "recorder.pip_compositor.subprocess.run",
            side_effect=fake_run,
        ) as mock_run:
            ok, error = compose_pip_overlay(
                base_video=base,
                camera_video=camera,
                output_path=base,
                settings=PiPSettings(enabled=True),
                ffmpeg_binary="ffmpeg",
            )

        assert ok is True
        assert error is None
        assert base.read_bytes() == b"composed"
        cmd = mock_run.call_args.args[0]
        assert "-filter_complex" in cmd

    def test_ffmpeg_failure_returns_error(self, tmp_path: Path) -> None:
        """Ненулевой код возврата FFmpeg — ошибка с хвостом stderr."""
        base = tmp_path / "base.mp4"
        base.write_bytes(b"base")
        camera = tmp_path / "cam.mp4"
        camera.write_bytes(b"cam")
        result = MagicMock(returncode=1, stderr="error tail")

        with patch(
            "recorder.pip_compositor.subprocess.run", return_value=result
        ):
            ok, error = compose_pip_overlay(
                base_video=base,
                camera_video=camera,
                output_path=tmp_path / "out.mp4",
                settings=PiPSettings(enabled=True),
            )

        assert ok is False
        assert error is not None and "error tail" in error
