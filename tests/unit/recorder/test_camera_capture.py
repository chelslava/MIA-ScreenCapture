"""Тесты захвата веб-камеры через FFmpeg/DirectShow (#165)."""

import subprocess
from unittest.mock import MagicMock, patch

from recorder.camera_capture import (
    CameraRecorder,
    parse_ffmpeg_device_list,
)

_DEVICE_LIST_OUTPUT = """
[dshow @ 000001] DirectShow video devices (some may be both video and audio):
[dshow @ 000001]  "Integrated Webcam"
[dshow @ 000001]     Alternative name "@device_pnp_\\usb#vid"
[dshow @ 000001]  "USB Camera"
[dshow @ 000001] DirectShow audio devices:
[dshow @ 000001]  "Microphone Array"
"""


class TestParseFfmpegDeviceList:
    """Разбор списка устройств из вывода FFmpeg (#165)."""

    def test_parses_video_devices_only(self) -> None:
        """Аудио-устройства и альтернативные имена исключаются."""
        devices = parse_ffmpeg_device_list(_DEVICE_LIST_OUTPUT)

        assert [d.name for d in devices] == [
            "Integrated Webcam",
            "USB Camera",
        ]

    def test_empty_output(self) -> None:
        """Пустой вывод даёт пустой список."""
        assert parse_ffmpeg_device_list("") == []

    def test_output_without_devices(self) -> None:
        """Вывод без секции видеоустройств даёт пустой список."""
        assert parse_ffmpeg_device_list("no devices here") == []


class TestListCameras:
    """Перечисление камер через subprocess (#165)."""

    def test_returns_parsed_devices(self) -> None:
        """Устройства извлекаются из stderr FFmpeg."""
        result = MagicMock(returncode=1, stderr=_DEVICE_LIST_OUTPUT)
        with patch("subprocess.run", return_value=result):
            from recorder.camera_capture import list_cameras

            cameras = list_cameras()

        assert len(cameras) == 2

    def test_ffmpeg_unreachable_returns_empty(self) -> None:
        """Недоступный FFmpeg даёт пустой список без исключения."""
        with patch(
            "subprocess.run",
            side_effect=OSError("ffmpeg not found"),
        ):
            from recorder.camera_capture import list_cameras

            assert list_cameras() == []

    def test_timeout_returns_empty(self) -> None:
        """Таймаут перечисления даёт пустой список."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=15),
        ):
            from recorder.camera_capture import list_cameras

            assert list_cameras() == []


class TestCameraRecorder:
    """Lifecycle записи камеры (#165)."""

    def test_start_with_explicit_device(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """start запускает Popen с указанным устройством."""
        recorder = CameraRecorder(device_name="Integrated Webcam")
        process = MagicMock()
        with patch(
            "recorder.camera_capture.subprocess.Popen",
            return_value=process,
        ) as mock_popen:
            ok = recorder.start(tmp_path / "cam.mp4")

        assert ok is True
        cmd = mock_popen.call_args.args[0]
        assert "video=Integrated Webcam" in cmd
        assert recorder.is_running is False  # process.poll() -> None? нет

    def test_start_without_devices_fails(self) -> None:
        """Без указанного устройства и без найденных камер — отказ."""
        recorder = CameraRecorder(device_name="")
        with patch(
            "recorder.camera_capture.list_cameras",
            return_value=[],
        ):
            assert recorder.start("/tmp/cam.mp4") is False

    def test_start_uses_first_camera_when_unspecified(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Пустое имя устройства — берётся первая найденная камера."""
        from recorder.camera_capture import CameraDeviceInfo

        recorder = CameraRecorder(device_name="")
        process = MagicMock()
        with (
            patch(
                "recorder.camera_capture.list_cameras",
                return_value=[CameraDeviceInfo(name="Cam A")],
            ),
            patch(
                "recorder.camera_capture.subprocess.Popen",
                return_value=process,
            ) as mock_popen,
        ):
            assert recorder.start(tmp_path / "cam.mp4") is True
            assert "video=Cam A" in mock_popen.call_args.args[0]

    def test_start_popen_failure_returns_false(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """OSError от Popen не пробрасывается."""
        recorder = CameraRecorder(device_name="Cam")
        with patch(
            "recorder.camera_capture.subprocess.Popen",
            side_effect=OSError("boom"),
        ):
            assert recorder.start(tmp_path / "cam.mp4") is False

    def test_stop_graceful_q_and_success(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Остановка пишет 'q' в stdin и ждёт завершения."""
        camera_file = tmp_path / "cam.mp4"
        camera_file.write_bytes(b"fake")
        process = MagicMock()
        process.poll.return_value = 0
        recorder = CameraRecorder(device_name="Cam")
        recorder._process = process
        recorder._output_path = camera_file

        assert recorder.stop() is True
        process.stdin.write.assert_called_once_with(b"q\n")
        process.wait.assert_called_once()

    def test_stop_without_file_returns_false(self) -> None:
        """Отсутствие файла камеры — неуспех без исключения."""
        process = MagicMock()
        recorder = CameraRecorder(device_name="Cam")
        recorder._process = process
        recorder._output_path = None

        assert recorder.stop() is False
