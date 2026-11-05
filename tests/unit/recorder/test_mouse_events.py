"""Тесты авто-zoom по активности мыши (#170)."""

from pathlib import Path

from core.post_processing.steps import build_auto_zoom_filter_complex
from recorder.mouse_events import (
    MouseEvent,
    build_zoom_segments,
    parse_mouse_events,
)


def _events_at(*times: float) -> list[MouseEvent]:
    return [MouseEvent(t=t, x=100, y=100) for t in times]


class TestParseMouseEvents:
    """Разбор sidecar-файла событий (#170)."""

    def test_parse_sorted_and_skips_broken(self) -> None:
        """Битые строки пропускаются, результат по времени."""
        lines = [
            '{"t": 2.0, "x": 10, "y": 20}',
            "not json",
            '{"t": 1.0, "x": 30, "y": 40}',
            "",
            '{"x": 5}',  # нет t
        ]
        events = parse_mouse_events(lines)

        assert [e.t for e in events] == [1.0, 2.0]

    def test_empty_input(self) -> None:
        assert parse_mouse_events([]) == []


class TestBuildZoomSegments:
    """Кластеризация активности в сегменты зума (#170)."""

    def test_empty_events(self) -> None:
        assert build_zoom_segments([], video_duration_s=60.0) == []

    def test_single_cluster(self) -> None:
        """Пачка событий превращается в один сегмент."""
        segments = build_zoom_segments(
            _events_at(10.0, 10.2, 10.4), video_duration_s=60.0
        )

        assert len(segments) == 1
        assert segments[0].start_s <= 10.0
        assert segments[0].end_s >= 10.4

    def test_distant_events_split(self) -> None:
        """События далеко друг от друга — отдельные сегменты."""
        segments = build_zoom_segments(
            _events_at(10.0, 10.2, 30.0, 30.2), video_duration_s=60.0
        )

        assert len(segments) == 2
        assert segments[0].end_s < segments[1].start_s

    def test_short_segments_filtered(self) -> None:
        """Сегменты короче min_segment_s отбрасываются."""
        segments = build_zoom_segments(
            _events_at(10.0, 10.1),
            video_duration_s=60.0,
            min_segment_s=2.0,
        )

        assert segments == []

    def test_segments_clamped_to_duration(self) -> None:
        """Хвост активности у конца видео не выходит за длительность."""
        segments = build_zoom_segments(
            _events_at(59.0, 59.5), video_duration_s=60.0
        )

        assert segments
        assert segments[-1].end_s <= 60.0


class TestBuildAutoZoomFilterComplex:
    """Генерация filter_complex для зума (#170)."""

    def test_empty_segments_returns_none(self) -> None:
        assert build_auto_zoom_filter_complex([]) is None

    def test_low_zoom_returns_none(self) -> None:
        assert (
            build_auto_zoom_filter_complex([(5.0, 10.0)], zoom_level=1.0)
            is None
        )

    def test_single_segment_structure(self) -> None:
        """Один сегмент: trim+zoompan кусок, concat, замыкание."""
        result = build_auto_zoom_filter_complex([(5.0, 10.0)])

        assert result is not None
        assert "trim=start=5.0:duration=5.0" in result
        assert "zoompan=z='min(zoom+0.0015,1.5)'" in result
        assert "concat=n=" in result

    def test_gap_and_zoom_pieces(self) -> None:
        """Сегмент в середине: кусок-зазор + зум-кусок."""
        result = build_auto_zoom_filter_complex([(5.0, 8.0)])

        assert result is not None
        assert "trim=start=0.0:duration=5.0" in result  # зазор
        assert "trim=start=5.0:duration=3.0" in result  # зум


class TestVpxSpeedArgs:
    """Аргументы скорости libvpx при транскодировании (#180)."""

    def test_vp9_gets_row_mt_and_cpu_used(self) -> None:
        """libvpx-vp9: row-mt, cpu-used, deadline, threads."""
        from core.post_processing.steps import build_vpx_speed_args

        args = build_vpx_speed_args("libvpx-vp9")
        assert args == [
            "-row-mt",
            "1",
            "-cpu-used",
            "4",
            "-deadline",
            "good",
            "-threads",
            "0",
        ]

    def test_vp8_gets_cpu_used_without_row_mt(self) -> None:
        """libvpx (VP8): cpu-used и threads, без row-mt."""
        from core.post_processing.steps import build_vpx_speed_args

        args = build_vpx_speed_args("libvpx")
        assert "-cpu-used" in args
        assert "-row-mt" not in args

    def test_non_vpx_gets_no_args(self) -> None:
        """Не-vpx кодеки не получают скоростных аргументов."""
        from core.post_processing.steps import build_vpx_speed_args

        assert build_vpx_speed_args("libx264") == []
        assert build_vpx_speed_args("hevc_nvenc") == []

    def test_transcode_cmd_contains_vpx_args(self, tmp_path: Path) -> None:
        """cmd транскодирования включает vpx-аргументы после -c:v."""
        from unittest.mock import MagicMock, patch

        from core.post_processing.steps import TranscodeStep

        video = tmp_path / "v.mp4"
        video.write_bytes(b"v")
        captured: dict[str, list[str]] = {}

        def fake_run(cmd: list[str], **kwargs: object) -> MagicMock:
            captured["cmd"] = cmd
            Path(cmd[-1]).write_bytes(b"out")
            return MagicMock(returncode=0, stderr="")

        step = TranscodeStep(target_format="webm", target_codec="libvpx-vp9")
        with (
            patch(
                "core.post_processing.steps.get_ffmpeg_path",
                return_value="ffmpeg",
            ),
            patch("subprocess.run", side_effect=fake_run),
        ):
            step.execute(video)

        cmd = captured["cmd"]
        codec_index = cmd.index("-c:v")
        assert cmd[codec_index + 1] == "libvpx-vp9"
        assert "-row-mt" in cmd[codec_index + 2 : codec_index + 12]
        assert "-cpu-used" in cmd[codec_index + 2 : codec_index + 12]
