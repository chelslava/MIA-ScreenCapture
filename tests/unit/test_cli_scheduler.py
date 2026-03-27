"""
Тесты модуля cli/scheduler.py.

Модуль содержит тесты для проверки CRUD операций планировщика через CLI.
"""

from unittest.mock import Mock, patch

import pytest

from cli.scheduler import (
    create_schedule,
    delete_schedule,
    get_api_headers,
    preview_upcoming_runs,
    toggle_schedule,
    update_schedule,
    validate_schedule_params,
)


class TestGetApiHeaders:
    """Тесты функции get_api_headers."""

    def test_no_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Проверка пустых заголовков без API ключа."""
        monkeypatch.delenv("MIA_SCREEN_CAPTURE_API_KEY", raising=False)
        headers = get_api_headers()
        assert headers == {}

    def test_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Проверка заголовков с API ключом."""
        monkeypatch.setenv("MIA_API_KEY", "test-key-123")
        headers = get_api_headers()
        assert "X-API-Key" in headers
        assert headers["X-API-Key"] == "test-key-123"


class TestValidateScheduleParams:
    """Тесты функции validate_schedule_params."""

    def test_valid_time(self) -> None:
        """Проверка валидного времени."""
        is_valid, error = validate_schedule_params({"time": "09:30"})
        assert is_valid is True
        assert error == ""

    def test_invalid_time_format(self) -> None:
        """Проверка невалидного формата времени."""
        is_valid, error = validate_schedule_params({"time": "9:30"})
        assert is_valid is False
        assert "HH:MM" in error

    def test_invalid_time_hour(self) -> None:
        """Проверка невалидного часа."""
        is_valid, error = validate_schedule_params({"time": "25:00"})
        assert is_valid is False
        assert "23" in error

    def test_invalid_time_minute(self) -> None:
        """Проверка невалидной минуты."""
        is_valid, error = validate_schedule_params({"time": "10:70"})
        assert is_valid is False
        assert "59" in error

    def test_valid_days_of_week(self) -> None:
        """Проверка валидных дней недели."""
        is_valid, error = validate_schedule_params({"days_of_week": "0,1,2"})
        assert is_valid is True
        assert error == ""

    def test_valid_days_of_week_list(self) -> None:
        """Проверка валидных дней недели (список)."""
        is_valid, error = validate_schedule_params({"days_of_week": [0, 1, 2]})
        assert is_valid is True
        assert error == ""

    def test_invalid_day_of_week(self) -> None:
        """Проверка невалидного дня недели."""
        is_valid, error = validate_schedule_params({"days_of_week": [0, 7]})
        assert is_valid is False
        assert "0-6" in error

    def test_valid_datetime(self) -> None:
        """Проверка валидного datetime."""
        is_valid, error = validate_schedule_params(
            {"datetime": "2026-01-20 09:30"}
        )
        assert is_valid is True
        assert error == ""

    def test_invalid_datetime_format(self) -> None:
        """Проверка невалидного формата datetime."""
        is_valid, error = validate_schedule_params(
            {"datetime": "2026/01/20 09:30"}
        )
        assert is_valid is False
        assert "YYYY-MM-DD HH:MM" in error

    def test_valid_interval(self) -> None:
        """Проверка валидного интервала."""
        is_valid, error = validate_schedule_params(
            {"interval_hours": 1, "interval_minutes": 30}
        )
        assert is_valid is True
        assert error == ""

    def test_interval_zero_for_interval_trigger(self) -> None:
        """Проверка нулевого интервала для interval триггера."""
        is_valid, error = validate_schedule_params(
            {"trigger": "interval", "interval_hours": 0, "interval_minutes": 0}
        )
        assert is_valid is False
        assert "interval-hours" in error or "interval-minutes" in error

    def test_valid_cron_expression(self) -> None:
        """Проверка валидного cron выражения."""
        is_valid, error = validate_schedule_params(
            {"cron_expression": "0 9 * * 1-5"}
        )
        assert is_valid is True
        assert error == ""

    def test_invalid_cron_expression(self) -> None:
        """Проверка невалидного cron выражения."""
        is_valid, error = validate_schedule_params(
            {"cron_expression": "invalid cron!"}
        )
        assert is_valid is False
        assert "Cron" in error

    def test_multiple_errors(self) -> None:
        """Проверка нескольких ошибок валидации."""
        is_valid, error = validate_schedule_params(
            {
                "time": "25:70",
                "days_of_week": [8],
            }
        )
        assert is_valid is False
        assert "23" in error  # Ошибка часа
        assert "0-6" in error  # Ошибка дня недели


class TestCreateSchedule:
    """Тесты функции create_schedule."""

    @patch("cli.scheduler._make_api_request")
    def test_create_schedule_success(
        self, mock_request: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Проверка успешного создания задачи."""
        mock_request.return_value = (
            200,
            {"success": True, "data": {"task_id": "task-123"}},
        )

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {
                "name": "Test Task",
                "trigger": "daily",
                "time": "09:30",
            },
            "recording": {"area_type": "full", "audio_type": "mic"},
        }

        result = create_schedule(config)
        assert result == 0
        mock_request.assert_called_once()

    @patch("cli.scheduler._make_api_request")
    def test_create_schedule_with_preset(
        self, mock_request: Mock, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Проверка создания задачи с preset."""
        mock_request.return_value = (
            200,
            {"success": True, "data": {"task_id": "task-123"}},
        )

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"preset": "workday-morning"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 0

    def test_create_schedule_missing_time(self) -> None:
        """Проверка ошибки при отсутствии времени для daily триггера."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"trigger": "daily"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1

    def test_create_schedule_missing_datetime_for_once(self) -> None:
        """Проверка ошибки при отсутствии datetime для once триггера."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"trigger": "once"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1

    def test_create_schedule_missing_days_for_weekly(self) -> None:
        """Проверка ошибки при отсутствии дней для weekly триггера."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"trigger": "weekly", "time": "09:30"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1

    def test_create_schedule_missing_interval(self) -> None:
        """Проверка ошибки при отсутствии интервала для interval триггера."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"trigger": "interval"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1

    @patch("cli.scheduler._make_api_request")
    def test_create_schedule_invalid_preset(self, mock_request: Mock) -> None:
        """Проверка ошибки при невалидном preset."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"preset": "invalid-preset"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1
        mock_request.assert_not_called()

    @patch("cli.scheduler._make_api_request")
    def test_create_schedule_api_error(self, mock_request: Mock) -> None:
        """Проверка обработки ошибки API."""
        mock_request.return_value = (500, {"error": "Server error"})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"trigger": "daily", "time": "09:30"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1

    @patch("cli.scheduler._make_api_request")
    def test_create_schedule_unauthorized(self, mock_request: Mock) -> None:
        """Проверка обработки ошибки авторизации."""
        mock_request.return_value = (401, {"error": "Unauthorized"})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"trigger": "daily", "time": "09:30"},
            "recording": {},
        }

        result = create_schedule(config)
        assert result == 1


class TestUpdateSchedule:
    """Тесты функции update_schedule."""

    @patch("cli.scheduler._make_api_request")
    def test_update_schedule_success(self, mock_request: Mock) -> None:
        """Проверка успешного обновления задачи."""
        mock_request.return_value = (
            200,
            {"success": True},
        )

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"task_id": "task-123", "name": "Updated Task"},
            "recording": {},
        }

        result = update_schedule(config)
        assert result == 0

    def test_update_schedule_missing_task_id(self) -> None:
        """Проверка ошибки при отсутствии ID задачи."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {},
            "recording": {},
        }

        result = update_schedule(config)
        assert result == 1

    @patch("cli.scheduler._make_api_request")
    def test_update_schedule_api_error(self, mock_request: Mock) -> None:
        """Проверка обработки ошибки API."""
        mock_request.return_value = (404, {"error": "Task not found"})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"task_id": "task-123"},
            "recording": {},
        }

        result = update_schedule(config)
        assert result == 1


class TestDeleteSchedule:
    """Тесты функции delete_schedule."""

    @patch("cli.scheduler._make_api_request")
    def test_delete_schedule_success(self, mock_request: Mock) -> None:
        """Проверка успешного удаления задачи."""
        mock_request.return_value = (200, {"success": True})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"task_id": "task-123"},
        }

        result = delete_schedule(config)
        assert result == 0

    def test_delete_schedule_missing_task_id(self) -> None:
        """Проверка ошибки при отсутствии ID задачи."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {},
        }

        result = delete_schedule(config)
        assert result == 1

    @patch("cli.scheduler._make_api_request")
    def test_delete_schedule_api_error(self, mock_request: Mock) -> None:
        """Проверка обработки ошибки API."""
        mock_request.return_value = (404, {"error": "Task not found"})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"task_id": "task-123"},
        }

        result = delete_schedule(config)
        assert result == 1


class TestToggleSchedule:
    """Тесты функции toggle_schedule."""

    @patch("cli.scheduler._make_api_request")
    def test_toggle_schedule_enable(self, mock_request: Mock) -> None:
        """Проверка включения задачи."""
        mock_request.return_value = (200, {"success": True})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"task_id": "task-123", "enabled": True},
        }

        result = toggle_schedule(config)
        assert result == 0

    @patch("cli.scheduler._make_api_request")
    def test_toggle_schedule_disable(self, mock_request: Mock) -> None:
        """Проверка выключения задачи."""
        mock_request.return_value = (200, {"success": True})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {"task_id": "task-123", "enabled": False},
        }

        result = toggle_schedule(config)
        assert result == 0

    def test_toggle_schedule_missing_task_id(self) -> None:
        """Проверка ошибки при отсутствии ID задачи."""
        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
            "scheduler": {},
        }

        result = toggle_schedule(config)
        assert result == 1


class TestPreviewUpcomingRuns:
    """Тесты функции preview_upcoming_runs."""

    @patch("cli.scheduler._make_api_request")
    def test_preview_upcoming_runs_success(
        self, mock_request: Mock, capsys: pytest.CaptureFixture
    ) -> None:
        """Проверка успешного отображения предстоящих запусков."""
        mock_request.return_value = (
            200,
            {
                "success": True,
                "data": [
                    {
                        "id": "task-123",
                        "name": "Morning Task",
                        "enabled": True,
                        "next_run": "2026-01-20 09:30:00",
                        "schedule_type": "daily",
                    }
                ],
            },
        )

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
        }

        result = preview_upcoming_runs(config, count=5)
        assert result == 0

        captured = capsys.readouterr()
        assert "Предстоящие запуски" in captured.out
        assert "task-123" in captured.out

    @patch("cli.scheduler._make_api_request")
    def test_preview_upcoming_runs_empty(
        self, mock_request: Mock, capsys: pytest.CaptureFixture
    ) -> None:
        """Проверка пустого списка предстоящих запусков."""
        mock_request.return_value = (200, {"success": True, "data": []})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
        }

        result = preview_upcoming_runs(config, count=5)
        assert result == 0

        captured = capsys.readouterr()
        assert "Нет предстоящих запусков" in captured.out

    @patch("cli.scheduler._make_api_request")
    def test_preview_upcoming_runs_api_error(self, mock_request: Mock) -> None:
        """Проверка обработки ошибки API."""
        mock_request.return_value = (500, {"error": "Server error"})

        config = {
            "api": {"host": "127.0.0.1", "port": 5000},
        }

        result = preview_upcoming_runs(config, count=5)
        assert result == 1


class TestMakeApiRequest:
    """Тесты внутренней функции _make_api_request."""

    @patch("requests.get")
    def test_make_api_request_connection_error(self, mock_get: Mock) -> None:
        """Проверка обработки ошибки соединения."""
        import requests

        from cli.scheduler import _make_api_request

        mock_get.side_effect = requests.exceptions.ConnectionError()

        config = {"api": {"host": "127.0.0.1", "port": 5000}}
        status, response = _make_api_request("GET", "/api/schedule", config)

        assert status == 503
        assert "не доступен" in response["error"]

    @patch("requests.get")
    def test_make_api_request_timeout(self, mock_get: Mock) -> None:
        """Проверка обработки таймаута."""
        import requests

        from cli.scheduler import _make_api_request

        mock_get.side_effect = requests.exceptions.Timeout()

        config = {"api": {"host": "127.0.0.1", "port": 5000}}
        status, response = _make_api_request("GET", "/api/schedule", config)

        assert status == 504
        assert "Таймаут" in response["error"]
