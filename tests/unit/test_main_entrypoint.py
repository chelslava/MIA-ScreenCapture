"""Тесты entrypoint-логики `main.py`."""

from pathlib import Path

import main


class TestMainEntrypoint:
    """Проверки bootstrap-логики перед запуском приложения."""

    def test_load_environment_reads_dotenv_when_file_exists(
        self, monkeypatch
    ) -> None:
        """`.env` должен загружаться только при наличии файла."""
        calls: list[Path] = []

        monkeypatch.setattr(main.Path, "exists", lambda _self: True)
        monkeypatch.setattr(
            main, "load_dotenv", lambda path: calls.append(Path(path))
        )

        main._load_environment()

        assert len(calls) == 1
        assert calls[0].name == ".env"

    def test_main_calls_environment_bootstrap_before_app_run(
        self, monkeypatch
    ) -> None:
        """`main()` должен явно вызывать bootstrap и запускать приложение."""
        events: list[str] = []

        class FakeApp:
            """Минимальная заглушка приложения для проверки вызовов."""

            def __init__(self, config):
                assert config["mode"] == "headless"
                events.append("app_init")

            @staticmethod
            def run() -> int:
                events.append("app_run")
                return 42

        monkeypatch.setattr(
            main,
            "_load_environment",
            lambda: events.append("load_environment"),
        )
        monkeypatch.setattr(
            main,
            "parse_args",
            lambda: {
                "mode": "headless",
                "verbose": 0,
                "quiet": False,
                "config_path": "config/config.json",
            },
        )
        monkeypatch.setattr(main, "setup_logger", lambda level: None)
        monkeypatch.setattr(
            main,
            "init_config",
            lambda config_path: events.append(str(config_path)),
        )
        monkeypatch.setattr(main, "VideoRecorderApp", FakeApp)

        result = main.main()

        assert result == 42
        assert events[0] == "load_environment"
        assert Path(events[1]).name == "config.json"
        assert events[2] == "app_init"
        assert events[3] == "app_run"
