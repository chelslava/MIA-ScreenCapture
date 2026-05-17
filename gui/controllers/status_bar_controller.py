"""
Контроллер строки состояния
============================

Управляет обновлением кнопок управления записью и строки состояния
в зависимости от текущего статуса записи.
"""

from typing import Any

from gui.models.recording_state import RecordingStatus
from gui.styles.theme import Theme
from logger_config import get_module_logger

logger = get_module_logger(__name__)

_STATE_CONFIG: dict[RecordingStatus, dict[str, Any]] = {
    RecordingStatus.IDLE: {
        "start_enabled": True,
        "stop_enabled": False,
        "pause_enabled": False,
        "pause_text": "Пауза",
        "stop_text": "Стоп",
        "status_text": "Готов",
        "status_style": "",
        "time_text": "00:00",
    },
    RecordingStatus.RECORDING: {
        "start_enabled": False,
        "stop_enabled": True,
        "pause_enabled": True,
        "pause_text": "Пауза",
        "stop_text": "Стоп",
        "status_text": "Запись",
        "status_style": Theme.status_style("danger"),
        "time_text": None,
    },
    RecordingStatus.PAUSED: {
        "start_enabled": False,
        "stop_enabled": True,
        "pause_enabled": True,
        "pause_text": "Продолжить",
        "stop_text": "Стоп",
        "status_text": "Пауза",
        "status_style": Theme.status_style("warning"),
        "time_text": None,
    },
    RecordingStatus.STOPPING: {
        "start_enabled": False,
        "stop_enabled": True,
        "pause_enabled": False,
        "pause_text": "Пауза",
        "stop_text": "Отменить остановку",
        "status_text": "Остановка...",
        "status_style": Theme.status_style("warning"),
        "time_text": None,
    },
}


class StatusBarController:
    """
    Контроллер строки состояния и кнопок управления.

    Управляет состоянием кнопок start/stop/pause и метками
    статуса/времени в строке состояния.
    """

    def __init__(
        self,
        start_btn: Any,
        stop_btn: Any,
        pause_btn: Any,
        status_label: Any,
        time_label: Any,
    ) -> None:
        """
        Инициализация контроллера.

        Args:
            start_btn: Кнопка начала записи.
            stop_btn: Кнопка остановки записи.
            pause_btn: Кнопка паузы/возобновления записи.
            status_label: Метка текущего статуса.
            time_label: Метка времени записи.
        """
        self._start_btn = start_btn
        self._stop_btn = stop_btn
        self._pause_btn = pause_btn
        self._status_label = status_label
        self._time_label = time_label

    def apply_recording_status(self, status: RecordingStatus) -> None:
        """
        Обновить кнопки и метки согласно статусу записи.

        Args:
            status: Новый статус записи.
        """
        config = _STATE_CONFIG.get(status, _STATE_CONFIG[RecordingStatus.IDLE])

        self._start_btn.setEnabled(bool(config["start_enabled"]))
        self._stop_btn.setEnabled(bool(config["stop_enabled"]))
        self._pause_btn.setEnabled(bool(config["pause_enabled"]))
        self._pause_btn.setText(str(config["pause_text"]))
        self._stop_btn.setText(str(config["stop_text"]))
        self._status_label.setText(str(config["status_text"]))
        self._status_label.setStyleSheet(str(config["status_style"]))

        time_text = config["time_text"]
        if time_text is not None:
            self._time_label.setText(str(time_text))

    def update_time_display(self, time_text: str) -> None:
        """
        Обновить метку времени записи.

        Args:
            time_text: Отформатированная строка времени.
        """
        self._time_label.setText(time_text)
