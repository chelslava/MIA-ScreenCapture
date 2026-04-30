"""Unit-тесты унифицированного формата ошибок."""

from __future__ import annotations

from core.error_format import (
    ErrorCode,
    ErrorHandler,
    error_response,
    success_response,
)
from exceptions import (
    APIAuthenticationError,
    APIAuthorizationError,
    APINotFoundError,
    APIRateLimitError,
    APIValidationError,
    MIAError,
    RecordingError,
    RecordingNotActiveError,
    RecordingStateError,
    SchedulerError,
    TaskNotFoundError,
    TaskValidationError,
)

# ---------------------------------------------------------------------------
# error_response / success_response
# ---------------------------------------------------------------------------


class TestErrorResponseHelper:
    """Тесты функции формирования ответа об ошибке."""

    def test_returns_success_false(self) -> None:
        result = error_response(ErrorCode.INTERNAL_ERROR, "ошибка")
        assert result["success"] is False

    def test_error_field_contains_code_and_message(self) -> None:
        result = error_response("my_code", "my message")
        assert result["error"]["code"] == "my_code"
        assert result["error"]["message"] == "my message"

    def test_details_none_by_default(self) -> None:
        result = error_response("code", "message")
        assert result["error"]["details"] is None

    def test_details_included_when_provided(self) -> None:
        result = error_response("code", "message", details="extra info")
        assert result["error"]["details"] == "extra info"

    def test_structure_has_expected_keys(self) -> None:
        result = error_response("code", "message")
        assert set(result["error"].keys()) == {"code", "message", "details"}


class TestSuccessResponseHelper:
    """Тесты функции формирования успешного ответа."""

    def test_returns_success_true(self) -> None:
        result = success_response()
        assert result["success"] is True

    def test_merges_extra_data(self) -> None:
        result = success_response({"output_path": "/tmp/video.mp4"})
        assert result["output_path"] == "/tmp/video.mp4"
        assert result["success"] is True

    def test_no_data_returns_only_success(self) -> None:
        result = success_response()
        assert result == {"success": True}

    def test_data_none_returns_only_success(self) -> None:
        result = success_response(None)
        assert result == {"success": True}


# ---------------------------------------------------------------------------
# ErrorCode constants
# ---------------------------------------------------------------------------


class TestErrorCode:
    """Проверяет наличие ключевых констант кодов ошибок."""

    def test_recording_codes_defined(self) -> None:
        assert ErrorCode.RECORDING_ALREADY_ACTIVE
        assert ErrorCode.RECORDING_NOT_ACTIVE
        assert ErrorCode.RECORDING_FAILED

    def test_scheduler_codes_defined(self) -> None:
        assert ErrorCode.TASK_NOT_FOUND
        assert ErrorCode.TASK_VALIDATION_FAILED
        assert ErrorCode.SCHEDULER_ERROR

    def test_api_codes_defined(self) -> None:
        assert ErrorCode.AUTHENTICATION_REQUIRED
        assert ErrorCode.AUTHORIZATION_DENIED
        assert ErrorCode.VALIDATION_ERROR
        assert ErrorCode.RESOURCE_NOT_FOUND
        assert ErrorCode.RATE_LIMIT_EXCEEDED

    def test_general_codes_defined(self) -> None:
        assert ErrorCode.INTERNAL_ERROR
        assert ErrorCode.INVALID_REQUEST
        assert ErrorCode.OPERATION_CANCELLED


# ---------------------------------------------------------------------------
# ErrorHandler.handle — маппинг исключений
# ---------------------------------------------------------------------------


class TestErrorHandlerClassification:
    """Тесты маппинга исключений в унифицированные ответы."""

    def _handle(self, exc: Exception) -> dict:
        return ErrorHandler().handle(exc)

    def test_recording_state_error_maps_to_already_active(self) -> None:
        result = self._handle(RecordingStateError("Запись уже идёт"))
        assert result["success"] is False
        assert result["error"]["code"] == ErrorCode.RECORDING_ALREADY_ACTIVE

    def test_recording_not_active_maps_to_not_active(self) -> None:
        result = self._handle(RecordingNotActiveError("Запись не активна"))
        assert result["error"]["code"] == ErrorCode.RECORDING_NOT_ACTIVE

    def test_generic_recording_error_maps_to_recording_failed(self) -> None:
        result = self._handle(RecordingError("Сбой записи"))
        assert result["error"]["code"] == ErrorCode.RECORDING_FAILED

    def test_task_not_found_error_maps_correctly(self) -> None:
        result = self._handle(TaskNotFoundError("task-99"))
        assert result["error"]["code"] == ErrorCode.TASK_NOT_FOUND

    def test_task_validation_error_maps_correctly(self) -> None:
        result = self._handle(TaskValidationError("Некорректное расписание"))
        assert result["error"]["code"] == ErrorCode.TASK_VALIDATION_FAILED

    def test_scheduler_error_maps_to_scheduler_error(self) -> None:
        result = self._handle(SchedulerError("Планировщик сломан"))
        assert result["error"]["code"] == ErrorCode.SCHEDULER_ERROR

    def test_api_authentication_error(self) -> None:
        result = self._handle(APIAuthenticationError())
        assert result["error"]["code"] == ErrorCode.AUTHENTICATION_REQUIRED

    def test_api_authorization_error(self) -> None:
        result = self._handle(APIAuthorizationError())
        assert result["error"]["code"] == ErrorCode.AUTHORIZATION_DENIED

    def test_api_validation_error(self) -> None:
        result = self._handle(APIValidationError("Некорректный параметр"))
        assert result["error"]["code"] == ErrorCode.VALIDATION_ERROR

    def test_api_not_found_error(self) -> None:
        result = self._handle(APINotFoundError())
        assert result["error"]["code"] == ErrorCode.RESOURCE_NOT_FOUND

    def test_api_rate_limit_error(self) -> None:
        result = self._handle(APIRateLimitError())
        assert result["error"]["code"] == ErrorCode.RATE_LIMIT_EXCEEDED

    def test_base_mia_error_maps_to_internal(self) -> None:
        result = self._handle(MIAError("что-то пошло не так"))
        assert result["error"]["code"] == ErrorCode.INTERNAL_ERROR

    def test_value_error_maps_to_invalid_request(self) -> None:
        result = self._handle(ValueError("Некорректный параметр"))
        assert result["error"]["code"] == ErrorCode.INVALID_REQUEST

    def test_os_error_maps_to_internal_error(self) -> None:
        result = self._handle(OSError("disk error"))
        assert result["error"]["code"] == ErrorCode.INTERNAL_ERROR

    def test_unknown_exception_maps_to_internal_error(self) -> None:
        result = self._handle(RuntimeError("unexpected"))
        assert result["error"]["code"] == ErrorCode.INTERNAL_ERROR

    def test_message_from_exception_preserved(self) -> None:
        result = self._handle(RecordingError("конкретное сообщение об ошибке"))
        assert "конкретное сообщение об ошибке" in result["error"]["message"]

    def test_details_from_mia_error_included(self) -> None:
        exc = RecordingError("ошибка", details="подробности диагностики")
        result = self._handle(exc)
        assert result["error"]["details"] == "подробности диагностики"

    def test_result_is_always_success_false(self) -> None:
        for exc in [
            RecordingStateError("x"),
            ValueError("y"),
            RuntimeError("z"),
        ]:
            assert self._handle(exc)["success"] is False
