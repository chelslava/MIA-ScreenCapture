"""Тесты MultiSourceRecorder (#51)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from recorder.multi_source_recorder import (
    MultiCaptureSourceSpec,
    MultiSourceRecorder,
)
from recorder.video_recorder import RecordingState


def _full_screen_sources() -> list[MultiCaptureSourceSpec]:
    return [
        MultiCaptureSourceSpec(label="primary", monitor_index=0),
        MultiCaptureSourceSpec(label="secondary", monitor_index=1),
    ]


def _patched_monitors():
    return patch(
        "recorder.video_recorder.get_available_monitors",
        return_value=[
            {"index": 0, "width": 1920, "height": 1080, "is_primary": True},
            {"index": 1, "width": 2560, "height": 1440, "is_primary": False},
        ],
    )


class TestMultiSourceRecorderStart:
    """Тесты запуска мультиисточниковой записи."""

    def test_start_success_with_two_sources(self) -> None:
        """Успешный старт создаёт VideoRecorder на каждый источник."""
        recorders = [MagicMock(), MagicMock()]
        for r in recorders:
            r.start.return_value = True

        with (
            _patched_monitors(),
            patch(
                "recorder.multi_source_recorder.VideoRecorder",
                side_effect=recorders,
            ),
        ):
            recorder = MultiSourceRecorder()
            success, outputs, error = recorder.start(
                _full_screen_sources(), Path("D:/out/video.mp4")
            )

        assert success is True
        assert error is None
        assert outputs == {
            "primary": Path("D:/out/video_primary.mp4"),
            "secondary": Path("D:/out/video_secondary.mp4"),
        }
        recorders[0].start.assert_called_once()
        recorders[1].start.assert_called_once()
        assert recorder.is_active is True

    def test_start_builds_correct_output_paths(self) -> None:
        """Путь каждого источника содержит {stem}_{label}{suffix}."""
        captured_paths: list[Path] = []

        def fake_start(output_path, capture_area, duration):
            captured_paths.append(output_path)
            return True

        recorders = [MagicMock(), MagicMock()]
        for r in recorders:
            r.start.side_effect = fake_start

        with (
            _patched_monitors(),
            patch(
                "recorder.multi_source_recorder.VideoRecorder",
                side_effect=recorders,
            ),
        ):
            recorder = MultiSourceRecorder()
            recorder.start(_full_screen_sources(), Path("D:/out/video.mp4"))

        assert captured_paths == [
            Path("D:/out/video_primary.mp4"),
            Path("D:/out/video_secondary.mp4"),
        ]

    def test_start_rejects_fewer_than_two_sources(self) -> None:
        """Меньше 2 источников -> отказ без создания VideoRecorder."""
        with patch("recorder.multi_source_recorder.VideoRecorder") as mock_cls:
            recorder = MultiSourceRecorder()
            success, outputs, error = recorder.start(
                [MultiCaptureSourceSpec(label="only")],
                Path("D:/out/video.mp4"),
            )

        assert success is False
        assert outputs is None
        assert "минимум 2" in error
        mock_cls.assert_not_called()

    def test_start_rejects_duplicate_labels(self) -> None:
        """Повторяющиеся labels -> отказ без создания VideoRecorder."""
        with patch("recorder.multi_source_recorder.VideoRecorder") as mock_cls:
            recorder = MultiSourceRecorder()
            success, outputs, error = recorder.start(
                [
                    MultiCaptureSourceSpec(label="dup", monitor_index=0),
                    MultiCaptureSourceSpec(label="dup", monitor_index=1),
                ],
                Path("D:/out/video.mp4"),
            )

        assert success is False
        assert outputs is None
        assert "уник" in error.lower()
        mock_cls.assert_not_called()

    def test_start_rolls_back_on_partial_failure(self) -> None:
        """Неудача второго источника останавливает уже запущенный первый."""
        first = MagicMock()
        first.start.return_value = True
        second = MagicMock()
        second.start.return_value = False

        with (
            _patched_monitors(),
            patch(
                "recorder.multi_source_recorder.VideoRecorder",
                side_effect=[first, second],
            ),
        ):
            recorder = MultiSourceRecorder()
            success, outputs, error = recorder.start(
                _full_screen_sources(), Path("D:/out/video.mp4")
            )

        assert success is False
        assert outputs is None
        assert error is not None
        first.stop.assert_called_once()
        second.stop.assert_not_called()
        assert recorder.is_active is False

    def test_start_rolls_back_on_window_not_found(self) -> None:
        """ValueError из build_capture_area (окно не найдено) откатывает старт."""
        first = MagicMock()
        first.start.return_value = True

        sources = [
            MultiCaptureSourceSpec(label="primary", monitor_index=0),
            MultiCaptureSourceSpec(
                label="missing_window",
                area_type="window",
                window_title="Несуществующее окно",
            ),
        ]

        with (
            _patched_monitors(),
            patch(
                "recorder.video_recorder.get_available_windows",
                return_value=[],
            ),
            patch(
                "recorder.multi_source_recorder.VideoRecorder",
                side_effect=[first],
            ),
        ):
            recorder = MultiSourceRecorder()
            success, outputs, error = recorder.start(
                sources, Path("D:/out/video.mp4")
            )

        assert success is False
        assert outputs is None
        first.stop.assert_called_once()
        assert recorder.is_active is False

    def test_start_rejects_when_already_active(self) -> None:
        """Повторный старт при активной записи -> отказ."""
        recorders = [MagicMock(), MagicMock()]
        for r in recorders:
            r.start.return_value = True

        with (
            _patched_monitors(),
            patch(
                "recorder.multi_source_recorder.VideoRecorder",
                side_effect=[*recorders, MagicMock()],
            ),
        ):
            recorder = MultiSourceRecorder()
            recorder.start(_full_screen_sources(), Path("D:/out/video.mp4"))

            success, outputs, error = recorder.start(
                _full_screen_sources(), Path("D:/out/video2.mp4")
            )

        assert success is False
        assert outputs is None
        assert "уже активна" in error


class TestMultiSourceRecorderStopAndStatus:
    """Тесты остановки и статуса мультиисточниковой записи."""

    def _start_active_recorder(
        self, recorders: list[MagicMock]
    ) -> MultiSourceRecorder:
        for r in recorders:
            r.start.return_value = True
        with (
            _patched_monitors(),
            patch(
                "recorder.multi_source_recorder.VideoRecorder",
                side_effect=recorders,
            ),
        ):
            recorder = MultiSourceRecorder()
            recorder.start(_full_screen_sources(), Path("D:/out/video.mp4"))
        return recorder

    def test_stop_collects_results_for_all_sources(self) -> None:
        """stop() агрегирует success/output_path по каждому источнику."""
        primary = MagicMock()
        secondary = MagicMock()
        primary.stop.return_value = True
        secondary.stop.return_value = False
        recorder = self._start_active_recorder([primary, secondary])

        results = recorder.stop()

        assert results["primary"]["success"] is True
        assert results["primary"]["output_path"] == str(
            Path("D:/out/video_primary.mp4")
        )
        assert results["secondary"]["success"] is False
        assert results["secondary"]["output_path"] is None
        assert recorder.is_active is False

    def test_get_status_aggregates_sources(self) -> None:
        """get_status() отдаёт state/elapsed_time/output_path по источникам."""
        primary = MagicMock()
        secondary = MagicMock()
        primary.state = RecordingState.RECORDING
        primary.elapsed_time = 12.5
        secondary.state = RecordingState.RECORDING
        secondary.elapsed_time = 12.5
        recorder = self._start_active_recorder([primary, secondary])

        status = recorder.get_status()

        assert status["active"] is True
        assert status["sources"]["primary"]["state"] == "recording"
        assert status["sources"]["primary"]["elapsed_time"] == 12.5
        assert status["sources"]["secondary"]["state"] == "recording"

    def test_get_status_when_idle(self) -> None:
        """Без активных источников get_status() отдаёт active=False."""
        recorder = MultiSourceRecorder()

        status = recorder.get_status()

        assert status == {"active": False, "sources": {}}
