"""
Тесты парсера CLI.

Модуль содержит тесты для проверки разбора аргументов командной строки.
"""

import argparse

import pytest

from cli.parser import (
    create_parser,
    parse_args,
    print_schedule_list,
    print_status,
    process_args,
    validate_recording_params,
)


class TestCLIParserBasics:
    """Базовые тесты парсера CLI."""

    def test_cli_module_exists(self) -> None:
        """Проверка существования модуля CLI."""
        import cli.parser

        assert cli.parser is not None

    def test_parser_creation(self) -> None:
        """Проверка создания парсера."""
        parser = create_parser()
        assert isinstance(parser, argparse.ArgumentParser)
        assert parser.prog == "mia-screencapture"


class TestCLIParserModes:
    """Тесты режимов работы парсера."""

    @pytest.mark.parametrize(
        "args,expected_mode",
        [
            ([], "gui"),  # По умолчанию
            (["--headless"], "headless"),
            (["--start"], "start"),
            (["--stop"], "stop"),
            (["--status"], "status"),
            (["--schedule-list"], "schedule_list"),
        ],
    )
    def test_mode_parsing(
        self, args: list[str], expected_mode: str
    ) -> None:
        """Проверка разбора режимов работы."""
        config = parse_args(args)
        assert config["mode"] == expected_mode


class TestCLIParserRecordingOptions:
    """Тесты параметров записи."""

    @pytest.mark.parametrize(
        "args,expected_area",
        [
            (["--start"], "full"),  # По умолчанию
            (["--start", "--area", "full"], "full"),
            (["--start", "--area", "window"], "window"),
            (["--start", "--area", "rect"], "rect"),
        ],
    )
    def test_area_option(
        self, args: list[str], expected_area: str
    ) -> None:
        """Проверка опции --area."""
        config = parse_args(args)
        assert config["recording"]["area_type"] == expected_area

    @pytest.mark.parametrize(
        "args,expected_audio",
        [
            (["--start"], "none"),  # По умолчанию
            (["--start", "--audio", "mic"], "mic"),
            (["--start", "--audio", "system"], "system"),
            (["--start", "--audio", "both"], "both"),
        ],
    )
    def test_audio_option(
        self, args: list[str], expected_audio: str
    ) -> None:
        """Проверка опции --audio."""
        config = parse_args(args)
        assert config["recording"]["audio_type"] == expected_audio

    @pytest.mark.parametrize(
        "fps_value",
        [1, 15, 30, 60, 120],
    )
    def test_fps_option(self, fps_value: int) -> None:
        """Проверка опции --fps."""
        config = parse_args(["--start", "--fps", str(fps_value)])
        assert config["recording"]["fps"] == fps_value

    @pytest.mark.parametrize(
        "codec",
        ["libx264", "libx265", "libvpx-vp9"],
    )
    def test_codec_option(self, codec: str) -> None:
        """Проверка опции --codec."""
        config = parse_args(["--start", "--codec", codec])
        assert config["recording"]["codec"] == codec

    @pytest.mark.parametrize(
        "bitrate",
        ["1M", "2M", "5M", "10M"],
    )
    def test_bitrate_option(self, bitrate: str) -> None:
        """Проверка опции --bitrate."""
        config = parse_args(["--start", "--bitrate", bitrate])
        assert config["recording"]["bitrate"] == bitrate

    @pytest.mark.parametrize(
        "duration",
        [1, 60, 3600],
    )
    def test_duration_option(self, duration: int) -> None:
        """Проверка опции --duration."""
        config = parse_args(["--start", "--duration", str(duration)])
        assert config["recording"]["duration"] == duration

    def test_rect_option(self) -> None:
        """Проверка опции --rect."""
        config = parse_args(["--start", "--area", "rect", "--rect", "100", "100", "800", "600"])
        assert config["recording"]["rect_coords"] == [100, 100, 800, 600]

    def test_window_option(self) -> None:
        """Проверка опции --window."""
        config = parse_args(["--start", "--area", "window", "--window", "Chrome"])
        assert config["recording"]["window_title"] == "Chrome"

    def test_output_option(self) -> None:
        """Проверка опции --output."""
        config = parse_args(["--start", "--output", "/tmp/recording.mp4"])
        assert config["recording"]["output_path"] == "/tmp/recording.mp4"


class TestCLIParserAPIOptions:
    """Тесты параметров API."""

    def test_default_api_config(self) -> None:
        """Проверка конфигурации API по умолчанию."""
        config = parse_args(["--headless"])
        assert config["api"]["enabled"] is True
        assert config["api"]["host"] == "127.0.0.1"
        assert config["api"]["port"] == 5000

    @pytest.mark.parametrize(
        "host",
        ["127.0.0.1", "localhost", "0.0.0.0"],
    )
    def test_api_host_option(self, host: str) -> None:
        """Проверка опции --api-host."""
        config = parse_args(["--headless", "--api-host", host])
        assert config["api"]["host"] == host

    @pytest.mark.parametrize(
        "port",
        [5000, 8080, 3000],
    )
    def test_api_port_option(self, port: int) -> None:
        """Проверка опции --api-port."""
        config = parse_args(["--headless", "--api-port", str(port)])
        assert config["api"]["port"] == port

    def test_no_api_option(self) -> None:
        """Проверка опции --no-api."""
        config = parse_args(["--headless", "--no-api"])
        assert config["api"]["enabled"] is False


class TestCLIParserSchedulerOptions:
    """Тесты параметров планировщика."""

    def test_schedule_option(self) -> None:
        """Проверка опции --schedule."""
        config = parse_args(["--start", "--schedule", "0 9 * * *"])
        assert config["scheduler"]["enabled"] is True
        assert config["scheduler"]["cron"] == "0 9 * * *"

    def test_schedule_name_option(self) -> None:
        """Проверка опции --schedule-name."""
        config = parse_args([
            "--start",
            "--schedule", "0 9 * * *",
            "--schedule-name", "Morning Recording"
        ])
        assert config["scheduler"]["name"] == "Morning Recording"

    def test_default_schedule_name(self) -> None:
        """Проверка имени задачи по умолчанию."""
        config = parse_args(["--start", "--schedule", "0 9 * * *"])
        assert config["scheduler"]["name"] == "Запланированная запись"


class TestCLIParserOtherOptions:
    """Тесты других опций."""

    def test_config_option(self) -> None:
        """Проверка опции --config."""
        config = parse_args(["--gui", "--config", "/tmp/config.json"])
        assert config["config_path"] == "/tmp/config.json"

    @pytest.mark.parametrize(
        "verbose_count,args",
        [
            (1, ["--verbose"]),
            (2, ["-vv"]),
            (3, ["-vvv"]),
        ],
    )
    def test_verbose_option(self, verbose_count: int, args: list[str]) -> None:
        """Проверка опции --verbose."""
        config = parse_args(args)
        assert config["verbose"] == verbose_count

    def test_quiet_option(self) -> None:
        """Проверка опции --quiet."""
        config = parse_args(["--quiet"])
        assert config["quiet"] is True


class TestCLIParserValidation:
    """Тесты валидации параметров."""

    def test_invalid_command_raises_error(self) -> None:
        """Проверка ошибки при неизвестной команде."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--unknown-command"])

    @pytest.mark.parametrize(
        "fps",
        [1, 30, 60, 120],
    )
    def test_valid_fps_range(self, fps: int) -> None:
        """Проверка валидного диапазона FPS."""
        params = {"fps": fps}
        is_valid, error = validate_recording_params(params)
        assert is_valid is True
        assert error is None

    @pytest.mark.parametrize(
        "fps",
        [0, -1, 121, 150],
    )
    def test_invalid_fps_range(self, fps: int) -> None:
        """Проверка невалидного диапазона FPS."""
        params = {"fps": fps}
        is_valid, error = validate_recording_params(params)
        assert is_valid is False
        assert "FPS" in error

    @pytest.mark.parametrize(
        "duration",
        [1, 60, 3600],
    )
    def test_valid_duration(self, duration: int) -> None:
        """Проверка валидной длительности."""
        params = {"duration": duration}
        is_valid, error = validate_recording_params(params)
        assert is_valid is True
        assert error is None

    def test_invalid_duration(self) -> None:
        """Проверка невалидной длительности."""
        params = {"duration": 0}
        is_valid, error = validate_recording_params(params)
        assert is_valid is False
        assert "длительность" in error.lower()

    def test_valid_area_type_full(self) -> None:
        """Проверка валидного типа области full."""
        params = {"area_type": "full"}
        is_valid, error = validate_recording_params(params)
        assert is_valid is True
        assert error is None

    def test_valid_area_type_window(self) -> None:
        """Проверка валидного типа области window с заголовком."""
        params = {"area_type": "window", "window_title": "Chrome"}
        is_valid, error = validate_recording_params(params)
        assert is_valid is True
        assert error is None

    def test_valid_area_type_rect(self) -> None:
        """Проверка валидного типа области rect с координатами."""
        params = {"area_type": "rect", "rect_coords": [100, 100, 800, 600]}
        is_valid, error = validate_recording_params(params)
        assert is_valid is True
        assert error is None

    def test_invalid_area_type(self) -> None:
        """Проверка невалидного типа области."""
        params = {"area_type": "invalid"}
        is_valid, error = validate_recording_params(params)
        assert is_valid is False
        assert "области" in error.lower()

    def test_rect_validation_missing_coords(self) -> None:
        """Проверка валидации rect без координат."""
        params = {"area_type": "rect"}
        is_valid, error = validate_recording_params(params)
        assert is_valid is False
        assert "координаты" in error.lower()

    def test_rect_validation_invalid_coords(self) -> None:
        """Проверка валидации rect с неверными координатами."""
        params = {
            "area_type": "rect",
            "rect_coords": [800, 600, 100, 100],  # x2 < x1, y2 < y1
        }
        is_valid, error = validate_recording_params(params)
        assert is_valid is False
        assert "координаты" in error.lower()

    def test_window_validation_missing_title(self) -> None:
        """Проверка валидации window без заголовка."""
        params = {"area_type": "window"}
        is_valid, error = validate_recording_params(params)
        assert is_valid is False
        assert "заголовок" in error.lower()


class TestCLIParserHelp:
    """Тесты справки."""

    @pytest.mark.parametrize(
        "args",
        [
            ["--help"],
            ["-h"],
            ["--start", "--help"],
        ],
    )
    def test_help_flag(self, args: list[str]) -> None:
        """Проверка флага --help."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(args)
        assert exc_info.value.code == 0


class TestCLIParserVersion:
    """Тесты версии."""

    def test_version_flag(self) -> None:
        """Проверка флага --version."""
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0


class TestCLIParserProcessArgs:
    """Тесты обработки аргументов."""

    def test_process_args_returns_dict(self) -> None:
        """Проверка, что process_args возвращает словарь."""
        parser = create_parser()
        args = parser.parse_args(["--start"])
        config = process_args(args)
        assert isinstance(config, dict)
        assert "mode" in config
        assert "recording" in config
        assert "api" in config

    def test_process_args_recording_params(self) -> None:
        """Проверка обработки параметров записи."""
        parser = create_parser()
        args = parser.parse_args([
            "--start",
            "--fps", "60",
            "--codec", "libx265",
            "--bitrate", "5M",
        ])
        config = process_args(args)
        assert config["recording"]["fps"] == 60
        assert config["recording"]["codec"] == "libx265"
        assert config["recording"]["bitrate"] == "5M"


class TestCLIParserPrintFunctions:
    """Тесты функций вывода."""

    def test_print_status_recording(self, capsys: pytest.CaptureFixture) -> None:
        """Проверка вывода статуса при записи."""
        status = {
            "is_recording": True,
            "is_paused": False,
            "elapsed_time": 125,
            "current_file": "/tmp/test.mp4",
        }
        print_status(status)
        captured = capsys.readouterr()
        assert "ЗАПИСЬ" in captured.out
        assert "02:05" in captured.out
        assert "/tmp/test.mp4" in captured.out

    def test_print_status_paused(self, capsys: pytest.CaptureFixture) -> None:
        """Проверка вывода статуса при паузе."""
        status = {
            "is_recording": True,
            "is_paused": True,
            "elapsed_time": 60,
            "current_file": "/tmp/test.mp4",
        }
        print_status(status)
        captured = capsys.readouterr()
        assert "ПАУЗА" in captured.out

    def test_print_status_idle(self, capsys: pytest.CaptureFixture) -> None:
        """Проверка вывода статуса при ожидании."""
        status = {"is_recording": False}
        print_status(status)
        captured = capsys.readouterr()
        assert "ОЖИДАНИЕ" in captured.out

    def test_print_schedule_list_empty(self, capsys: pytest.CaptureFixture) -> None:
        """Проверка вывода пустого списка задач."""
        print_schedule_list([])
        captured = capsys.readouterr()
        assert "Нет запланированных задач" in captured.out

    def test_print_schedule_list_with_tasks(self, capsys: pytest.CaptureFixture) -> None:
        """Проверка вывода списка задач."""
        tasks = [
            {
                "id": "task-1",
                "name": "Morning Recording",
                "schedule_type": "cron",
                "enabled": True,
                "next_run": "2024-01-15 09:00:00",
            }
        ]
        print_schedule_list(tasks)
        captured = capsys.readouterr()
        assert "task-1" in captured.out
        assert "Morning Recording" in captured.out
        assert "ВКЛЮЧЕНО" in captured.out


class TestCLIParserMutuallyExclusive:
    """Тесты взаимно исключающих опций."""

    def test_start_and_stop_mutually_exclusive(self) -> None:
        """Проверка, что --start и --stop взаимно исключают друг друга."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--start", "--stop"])

    def test_gui_and_headless_mutually_exclusive(self) -> None:
        """Проверка, что --gui и --headless взаимно исключают друг друга."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--gui", "--headless"])

    def test_start_and_status_mutually_exclusive(self) -> None:
        """Проверка, что --start и --status взаимно исключают друг друга."""
        parser = create_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--start", "--status"])
