"""Recording runtime coordinator для GUI/headless режимов."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from logger_config import get_module_logger

from .constants import (
    GUI_START_TIMEOUT_SECONDS,
    GUI_STOP_TIMEOUT_SECONDS,
)

if TYPE_CHECKING:
    from main import VideoRecorderApp

logger = get_module_logger(__name__)


class RecordingRuntimeCoordinator:
    """Координатор runtime-операций записи для GUI/headless режимов."""

    def __init__(self, app: VideoRecorderApp) -> None:
        self._app = app

    def get_status(self) -> dict[str, Any]:
        """Возвращает текущий статус записи."""
        if self._app._main_window:
            return cast(
                dict[str, Any],
                self._app._run_on_gui_thread(
                    lambda: self._app._main_window.get_status()
                ),
            )
        return self._app._recording_service.get_status()

    def start_recording(
        self,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Запускает запись через GUI или headless сервис."""
        if self._app._main_window:
            if params is None:
                return cast(
                    dict[str, Any],
                    self._app._run_on_gui_thread(
                        self._app._main_window.start_recording,
                        timeout=GUI_START_TIMEOUT_SECONDS,
                    ),
                )
            return cast(
                dict[str, Any],
                self._app._run_on_gui_thread(
                    lambda: self._app._main_window.start_recording_with_params(
                        params
                    ),
                    timeout=GUI_START_TIMEOUT_SECONDS,
                ),
            )
        if params is None:
            params = cast(
                dict[str, Any],
                self._app._config.get("recording", {}),
            )
        return self._app._recording_service.start_recording(params)

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись с fallback при таймауте GUI-потока."""
        if self._app._main_window:
            try:
                return cast(
                    dict[str, Any],
                    self._app._run_on_gui_thread(
                        lambda: self._app._main_window.stop_recording(),
                        timeout=GUI_STOP_TIMEOUT_SECONDS,
                    ),
                )
            except TimeoutError:
                logger.warning(
                    "Таймаут остановки записи в GUI-потоке (%.1f c). "
                    "Пробуем резервную остановку через сервис.",
                    GUI_STOP_TIMEOUT_SECONDS,
                )
                try:
                    fallback_result = (
                        self._app._recording_service.stop_recording()
                    )
                except Exception as e:
                    logger.exception(
                        "Резервная остановка после таймаута GUI завершилась "
                        "ошибкой: %s",
                        e,
                    )
                    return {
                        "success": False,
                        "error": (
                            "Остановка записи превысила таймаут GUI-потока, "
                            "резервная остановка не удалась"
                        ),
                    }

                if fallback_result.get("success"):
                    fallback_result.setdefault(
                        "warning",
                        (
                            "Остановка завершена через резервный путь после "
                            "таймаута GUI-потока"
                        ),
                    )
                return fallback_result

        return self._app._recording_service.stop_recording()

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу записи."""
        if self._app._main_window:
            return cast(
                dict[str, Any],
                self._app._run_on_gui_thread(
                    lambda: self._app._main_window.toggle_pause()
                ),
            )
        return self._app._recording_service.toggle_pause()

    def switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """Переключает источник захвата активной записи без остановки (#48)."""
        if self._app._main_window:
            return cast(
                dict[str, Any],
                self._app._run_on_gui_thread(
                    lambda: self._app._main_window.switch_capture_source(
                        params
                    ),
                    timeout=GUI_START_TIMEOUT_SECONDS,
                ),
            )
        return self._app._recording_service.switch_capture_source(params)

    def get_recordings(self) -> list[Any]:
        """Возвращает список последних записей."""
        if self._app._main_window:
            return cast(
                list[Any],
                self._app._run_on_gui_thread(
                    lambda: self._app._main_window.get_recordings()
                ),
            )
        return cast(
            list[Any],
            self._app._recording_service.get_recordings(),
        )
