"""Тесты entrypoint-логики `main.py`."""

from pathlib import Path

import main


class _FakeGuard:
    """Заглушка `SingleInstanceGuard` для детерминированных тестов."""

    instances: list["_FakeGuard"] = []

    def __init__(self, *, acquire_result: bool = True) -> None:
        self.acquire_result = acquire_result
        self.acquire_called = False
        self.release_called = False
        _FakeGuard.instances.append(self)

    def acquire(self) -> bool:
        self.acquire_called = True
        return self.acquire_result

    def release(self) -> None:
        self.release_called = True


class TestMainEntrypoint:
    """Проверки bootstrap-логики перед запуском приложения."""

    def setup_method(self) -> None:
        _FakeGuard.instances = []

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
        monkeypatch.setattr(main, "SingleInstanceGuard", _FakeGuard)

        result = main.main()

        assert result == 42
        assert events[0] == "load_environment"
        assert Path(events[1]).name == "config.json"
        assert events[2] == "app_init"
        assert events[3] == "app_run"
        assert _FakeGuard.instances[0].acquire_called is True
        assert _FakeGuard.instances[0].release_called is True

    def test_main_skips_guard_for_cli_client_modes(self, monkeypatch) -> None:
        """CLI-команды (status/start/stop/...) не должны создавать guard."""
        events: list[str] = []

        class FakeApp:
            def __init__(self, config):
                events.append("app_init")

            @staticmethod
            def run() -> int:
                events.append("app_run")
                return 0

        monkeypatch.setattr(main, "_load_environment", lambda: None)
        monkeypatch.setattr(
            main,
            "parse_args",
            lambda: {
                "mode": "status",
                "verbose": 0,
                "quiet": False,
                "config_path": None,
            },
        )
        monkeypatch.setattr(main, "setup_logger", lambda level: None)
        monkeypatch.setattr(main, "init_config", lambda config_path: None)
        monkeypatch.setattr(main, "VideoRecorderApp", FakeApp)
        monkeypatch.setattr(main, "SingleInstanceGuard", _FakeGuard)

        result = main.main()

        assert result == 0
        assert events == ["app_init", "app_run"]
        assert _FakeGuard.instances == []

    def test_main_returns_early_when_gui_instance_already_running(
        self, monkeypatch
    ) -> None:
        """Второй GUI-экземпляр должен завершиться без создания приложения."""
        app_created = False

        class FakeApp:
            def __init__(self, config):
                nonlocal app_created
                app_created = True

            @staticmethod
            def run() -> int:
                return 0

        focus_calls: list[str] = []

        monkeypatch.setattr(main, "_load_environment", lambda: None)
        monkeypatch.setattr(
            main,
            "parse_args",
            lambda: {
                "mode": "gui",
                "verbose": 0,
                "quiet": False,
                "config_path": None,
            },
        )
        monkeypatch.setattr(main, "setup_logger", lambda level: None)
        monkeypatch.setattr(main, "init_config", lambda config_path: None)
        monkeypatch.setattr(main, "VideoRecorderApp", FakeApp)
        monkeypatch.setattr(
            main,
            "SingleInstanceGuard",
            lambda: _FakeGuard(acquire_result=False),
        )
        monkeypatch.setattr(
            main,
            "bring_existing_window_to_front",
            lambda: focus_calls.append("focus"),
        )

        result = main.main()

        assert result == 0
        assert app_created is False
        assert focus_calls == ["focus"]
        assert _FakeGuard.instances[0].release_called is False

    def test_main_does_not_steal_focus_when_headless_instance_running(
        self, monkeypatch
    ) -> None:
        """В headless-режиме не нужно переключать фокус — окна нет."""
        focus_calls: list[str] = []

        monkeypatch.setattr(main, "_load_environment", lambda: None)
        monkeypatch.setattr(
            main,
            "parse_args",
            lambda: {
                "mode": "headless",
                "verbose": 0,
                "quiet": False,
                "config_path": None,
            },
        )
        monkeypatch.setattr(main, "setup_logger", lambda level: None)
        monkeypatch.setattr(main, "init_config", lambda config_path: None)
        monkeypatch.setattr(
            main,
            "SingleInstanceGuard",
            lambda: _FakeGuard(acquire_result=False),
        )
        monkeypatch.setattr(
            main,
            "bring_existing_window_to_front",
            lambda: focus_calls.append("focus"),
        )

        result = main.main()

        assert result == 0
        assert focus_calls == []
