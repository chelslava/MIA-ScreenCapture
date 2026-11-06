"""Unit-тесты machine-readable вывода CLI и exit-кодов (#206)."""

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from cli.exit_codes import (
    EXIT_OK,
    EXIT_RUNTIME_ERROR,
    EXIT_STATE_CONFLICT,
    EXIT_USAGE,
)
from cli.parser import parse_args, print_json


class TestExitCodeContract:
    """Стабильный контракт exit-кодов (#206)."""

    def test_contract_values(self) -> None:
        """Значения кодов не меняются между релизами."""
        assert EXIT_OK == 0
        assert EXIT_USAGE == 1
        assert EXIT_STATE_CONFLICT == 2
        assert EXIT_RUNTIME_ERROR == 3

    def test_http_mapping_conflict(self) -> None:
        """409 маппится в код 2 (конфликт состояния)."""
        from cli.scheduler import exit_code_for_status

        assert exit_code_for_status(409) == EXIT_STATE_CONFLICT

    @pytest.mark.parametrize("status", [400, 401, 404, 422])
    def test_http_mapping_usage(self, status: int) -> None:
        """400/401/404/422 маппятся в код 1 (использование)."""
        from cli.scheduler import exit_code_for_status

        assert exit_code_for_status(status) == EXIT_USAGE

    @pytest.mark.parametrize("status", [0, 403, 500, 503, 504])
    def test_http_mapping_runtime(self, status: int) -> None:
        """Сетевые/серверные ошибки маппятся в код 3 (исполнение)."""
        from cli.scheduler import exit_code_for_status

        assert exit_code_for_status(status) == EXIT_RUNTIME_ERROR


class TestJsonFlag:
    """Глобальный флаг --json (#206)."""

    def test_json_flag_parsed(self) -> None:
        """--json попадает в конфиг как json_output."""
        config = parse_args(["--status", "--json"])
        assert config["json_output"] is True

    def test_json_flag_default_off(self) -> None:
        """Без --json json_output выключен."""
        config = parse_args(["--status"])
        assert config["json_output"] is False

    def test_print_json_is_valid_json(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """print_json печатает валидный JSON с юникодом."""
        data: dict[str, Any] = {"имя": "запись", "fps": 60, "вкл": True}

        print_json(data)

        out = capsys.readouterr().out
        assert json.loads(out) == data


class TestCliJsonOutputs:
    """JSON-вывод команд CLI через прокси (#206)."""

    @staticmethod
    def _make_proxy(json_output: bool) -> Any:
        from app_runtime.app_cli_proxy_mixin import CliProxyMixin

        proxy = CliProxyMixin.__new__(CliProxyMixin)
        proxy._config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "recording": {
                "area_type": "full",
                "rect_coords": None,
                "window_title": None,
                "audio_type": "none",
                "output_path": None,
                "fps": 30,
                "codec": "libx264",
                "bitrate": "2M",
                "duration": None,
            },
        }
        if json_output:
            proxy._config["json_output"] = True
        coordinator = MagicMock()
        coordinator.get_effective_api_key.return_value = None
        proxy._api_runtime_coordinator = coordinator
        return proxy

    def test_status_json_output(self, capsys: pytest.CaptureFixture) -> None:
        """--status --json печатает JSON статуса."""
        proxy = self._make_proxy(json_output=True)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "data": {"is_recording": False},
        }

        with patch("requests.get", return_value=response):
            code = proxy._run_status()

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert json.loads(out) == {"is_recording": False}

    def test_status_human_output_without_json(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Без --json статус остаётся человекочитаемым."""
        proxy = self._make_proxy(json_output=False)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "data": {"is_recording": False},
        }

        with patch("requests.get", return_value=response):
            code = proxy._run_status()

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert "Статус" in out

    def test_schedule_list_json_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """--schedule-list --json печатает JSON массив задач."""
        proxy = self._make_proxy(json_output=True)
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "data": [{"id": "t1", "enabled": True}],
        }

        with patch("requests.get", return_value=response):
            code = proxy._run_schedule_list()

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert json.loads(out) == [{"id": "t1", "enabled": True}]

    def test_start_conflict_exit_code(self) -> None:
        """ "Запись уже идёт" (409) даёт exit-код 2 (#206)."""
        proxy = self._make_proxy(json_output=False)
        health_resp = MagicMock()
        health_resp.status_code = 200
        health_resp.json.return_value = {"status": "ok"}
        response = MagicMock()
        response.status_code = 409
        response.json.return_value = {
            "success": False,
            "error": "Запись уже идёт",
        }

        with (
            patch("requests.get", return_value=health_resp),
            patch("requests.post", return_value=response),
        ):
            code = proxy._run_start()

        assert code == EXIT_STATE_CONFLICT

    def test_stop_conflict_exit_code(self) -> None:
        """ "Запись не активна" (409) даёт exit-код 2 (#206)."""
        proxy = self._make_proxy(json_output=False)
        response = MagicMock()
        response.status_code = 409
        response.json.return_value = {
            "success": False,
            "error": "Запись не активна",
        }

        with patch("requests.post", return_value=response):
            code = proxy._run_stop()

        assert code == EXIT_STATE_CONFLICT

    def test_stop_runtime_error_exit_code(self) -> None:
        """Недоступный API при --stop даёт exit-код 3 (#206)."""
        proxy = self._make_proxy(json_output=False)

        with patch(
            "requests.post", side_effect=__import__("requests").ConnectionError
        ):
            code = proxy._run_stop()

        assert code == EXIT_RUNTIME_ERROR

    def test_list_presets_json_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """--list-presets --json печатает JSON массив пресетов."""
        proxy = self._make_proxy(json_output=True)

        code = proxy._run_list_presets()

        out = capsys.readouterr().out
        assert code == EXIT_OK
        presets = json.loads(out)
        assert isinstance(presets, list)
        assert all("name" in p for p in presets)

    def test_plugins_list_json_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """--plugins-list --json печатает JSON массив плагинов."""
        proxy = self._make_proxy(json_output=True)
        plugin = MagicMock()
        plugin.to_dict.return_value = {"name": "example", "status": "loaded"}
        proxy._plugin_manager = MagicMock()
        proxy._plugin_manager.get_all_plugins.return_value = [plugin]

        code = proxy._run_plugins_list()

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert json.loads(out) == [{"name": "example", "status": "loaded"}]

    def test_plugins_info_json_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """--plugins-info NAME --json печатает JSON метаданных."""
        proxy = self._make_proxy(json_output=True)
        proxy._config["plugin_name"] = "example"
        meta = MagicMock()
        meta.to_dict.return_value = {"name": "example", "version": "1.0"}
        proxy._plugin_manager = MagicMock()
        proxy._plugin_manager.get_plugin_metadata.return_value = meta

        code = proxy._run_plugins_info()

        out = capsys.readouterr().out
        assert code == EXIT_OK
        assert json.loads(out) == {"name": "example", "version": "1.0"}

    def test_schedule_preview_json_output(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """--schedule-preview --json печатает JSON предстоящих запусков."""
        from cli.scheduler import preview_upcoming_runs

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {
            "success": True,
            "data": [
                {
                    "id": "t1",
                    "name": "Задача",
                    "enabled": True,
                    "next_run": "2026-11-07T09:30:00",
                    "schedule_type": "daily",
                }
            ],
        }

        with patch("requests.get", return_value=response):
            code = preview_upcoming_runs(
                {
                    "api": {"host": "127.0.0.1", "port": 5000},
                    "json_output": True,
                }
            )

        out = capsys.readouterr().out
        assert code == EXIT_OK
        upcoming = json.loads(out)
        assert upcoming[0]["id"] == "t1"
