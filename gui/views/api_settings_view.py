"""
Вкладка настроек API
====================

Представление для управления API сервером, его настройками и логами.
"""

from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QFontDatabase, QGuiApplication
from PyQt6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import Theme
from logger_config import (
    get_api_log_dir,
    get_module_logger,
    open_api_logs_folder,
)

logger = get_module_logger(__name__)

_LOG_REFRESH_INTERVAL_MS = 1000
_MAX_LOG_BLOCKS = 5000
_AUTO_REFRESH_PAUSED_TEXT = "Автообновление включится при открытии вкладки"
_LOG_LOADING_TEXT = "Загрузка журнала API..."
_LOG_EMPTY_TEXT = (
    "Журнал API пока не создан. Запустите сервер, чтобы начать запись."
)


class ApiSettingsView(QWidget):
    """Виджет настройки API сервера."""

    apply_requested = pyqtSignal(int, str)
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    restart_requested = pyqtSignal()
    refresh_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """
        Инициализация вкладки API.

        Args:
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._current_log_path: Path | None = None
        self._log_offset = 0
        self._server_running = False
        self._auto_refresh_enabled = False
        self._log_loaded_once = False

        self._setup_ui()
        self._setup_timer()
        self._set_log_status(_AUTO_REFRESH_PAUSED_TEXT)

    def _setup_ui(self) -> None:
        """Настройка интерфейса вкладки."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("API сервер")
        title.setStyleSheet(Theme.title_style())
        layout.addWidget(title)

        layout.addWidget(self._create_settings_group())
        layout.addWidget(self._create_controls_group())
        layout.addWidget(self._create_logs_group())

        layout.addStretch()

    def _create_settings_group(self) -> QGroupBox:
        """Создание группы настроек сервера."""
        group = QGroupBox("Настройки сервера")
        layout = QFormLayout(group)

        self._port_spinbox = QSpinBox()
        self._port_spinbox.setRange(1, 65535)
        self._port_spinbox.setValue(5000)
        layout.addRow("Порт:", self._port_spinbox)

        self._token_edit = QLineEdit()
        self._token_edit.setPlaceholderText("Введите API токен")
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addRow("Токен:", self._token_edit)

        buttons_layout = QHBoxLayout()

        self._apply_btn = QPushButton("Сохранить настройки")
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        buttons_layout.addWidget(self._apply_btn)

        self._copy_token_btn = QPushButton("Копировать токен")
        self._copy_token_btn.clicked.connect(self._on_copy_token_clicked)
        buttons_layout.addWidget(self._copy_token_btn)

        self._open_logs_btn = QPushButton("Открыть папку логов API")
        self._open_logs_btn.clicked.connect(self._on_open_logs_clicked)
        buttons_layout.addWidget(self._open_logs_btn)

        layout.addRow(buttons_layout)
        return group

    def _create_controls_group(self) -> QGroupBox:
        """Создание группы управления сервером."""
        group = QGroupBox("Управление сервером")
        layout = QVBoxLayout(group)

        buttons_layout = QHBoxLayout()

        self._start_btn = QPushButton("Запустить")
        self._start_btn.clicked.connect(self._on_start_clicked)
        buttons_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("Остановить")
        self._stop_btn.clicked.connect(self._on_stop_clicked)
        buttons_layout.addWidget(self._stop_btn)

        self._restart_btn = QPushButton("Перезапустить")
        self._restart_btn.clicked.connect(self._on_restart_clicked)
        buttons_layout.addWidget(self._restart_btn)

        layout.addLayout(buttons_layout)

        self._status_label = QLabel("Статус: неизвестно")
        self._status_label.setStyleSheet(Theme.status_style("muted"))
        layout.addWidget(self._status_label)

        self._server_state_label = QLabel("Сервер готов к запуску")
        self._server_state_label.setStyleSheet(Theme.secondary_text_style())
        layout.addWidget(self._server_state_label)

        self._update_server_controls(False)
        return group

    def _create_logs_group(self) -> QGroupBox:
        """Создание группы с логами API."""
        group = QGroupBox("Логи API")
        layout = QVBoxLayout(group)

        header_layout = QHBoxLayout()

        self._log_source_label = QLabel("Файл логов: не найден")
        self._log_source_label.setStyleSheet(Theme.secondary_text_style())
        header_layout.addWidget(self._log_source_label)
        header_layout.addStretch()

        self._refresh_btn = QPushButton("Обновить")
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self._refresh_btn)

        layout.addLayout(header_layout)

        self._log_view = QPlainTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._log_view.setMaximumBlockCount(_MAX_LOG_BLOCKS)
        self._log_view.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        layout.addWidget(self._log_view)

        self._log_status_label = QLabel(_AUTO_REFRESH_PAUSED_TEXT)
        self._log_status_label.setStyleSheet(Theme.secondary_text_style())
        layout.addWidget(self._log_status_label)

        self._apply_accessibility_metadata()
        return group

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для controls вкладки API."""
        apply_accessible_metadata(
            self._port_spinbox,
            "Порт API",
            "Позволяет выбрать порт API сервера.",
            "Поддерживаются значения от 1 до 65535.",
        )
        apply_accessible_metadata(
            self._token_edit,
            "API токен",
            "Поле для ввода токена доступа к API серверу.",
            "Введите токен API.",
        )
        apply_accessible_metadata(
            self._apply_btn,
            "Сохранить настройки API",
            "Сохраняет порт и токен API сервера.",
            "Сохраняет настройки API.",
        )
        apply_accessible_metadata(
            self._copy_token_btn,
            "Копировать API токен",
            "Копирует текущий токен API в буфер обмена.",
            "Копирует токен в буфер обмена.",
        )
        apply_accessible_metadata(
            self._open_logs_btn,
            "Открыть папку логов API",
            "Открывает директорию с логами API сервера.",
            "Открывает папку логов API.",
        )
        apply_accessible_metadata(
            self._start_btn,
            "Запустить API сервер",
            "Запускает встроенный API сервер.",
            "Запускает API сервер.",
        )
        apply_accessible_metadata(
            self._stop_btn,
            "Остановить API сервер",
            "Останавливает встроенный API сервер.",
            "Останавливает API сервер.",
        )
        apply_accessible_metadata(
            self._restart_btn,
            "Перезапустить API сервер",
            "Перезапускает встроенный API сервер.",
            "Перезапускает API сервер.",
        )
        apply_accessible_metadata(
            self._refresh_btn,
            "Обновить логи API",
            "Перечитывает текущий журнал API сервера.",
            "Обновляет логи API.",
        )
        apply_accessible_metadata(
            self._status_label,
            "Статус API сервера",
            "Показывает результат последнего действия и текущий статус API.",
        )
        apply_accessible_metadata(
            self._log_view,
            "Журнал API",
            "Показывает текущий лог API сервера в режиме только чтения.",
        )
        apply_accessible_metadata(
            self._log_status_label,
            "Статус обновления журнала API",
            "Показывает состояние загрузки, ошибки и автообновления журнала.",
        )

    def _setup_timer(self) -> None:
        """Настройка таймера обновления логов."""
        self._log_timer = QTimer(self)
        self._log_timer.timeout.connect(self._on_timer_tick)

    def _on_timer_tick(self) -> None:
        """Периодическое обновление логов и статуса API."""
        self.refresh_requested.emit()
        self.refresh_logs()

    def _on_apply_clicked(self) -> None:
        """Обработка сохранения настроек."""
        self.apply_requested.emit(
            self._port_spinbox.value(),
            self._token_edit.text().strip(),
        )

    def _on_start_clicked(self) -> None:
        """Обработка запуска сервера."""
        self.start_requested.emit()

    def _on_stop_clicked(self) -> None:
        """Обработка остановки сервера."""
        self.stop_requested.emit()

    def _on_restart_clicked(self) -> None:
        """Обработка перезапуска сервера."""
        self.restart_requested.emit()

    def _on_refresh_clicked(self) -> None:
        """Обработка ручного обновления логов."""
        self.refresh_requested.emit()
        self.refresh_logs(show_loading_state=True)

    def _on_open_logs_clicked(self) -> None:
        """Открытие папки с логами API."""
        open_api_logs_folder()

    def _on_copy_token_clicked(self) -> None:
        """Копирование токена в буфер обмена."""
        token = self._token_edit.text().strip()
        if not token:
            self._status_label.setText(
                "Статус: токен не задан. Сначала введите и сохраните его."
            )
            self._status_label.setStyleSheet(Theme.status_style("warning"))
            return

        clipboard = QGuiApplication.clipboard()
        assert clipboard is not None
        clipboard.setText(token)
        self._status_label.setText("Статус: токен скопирован в буфер обмена.")
        self._status_label.setStyleSheet(Theme.status_style("success"))

    def get_settings(self) -> tuple[int, str]:
        """
        Получение текущих значений формы.

        Returns:
            Кортеж (порт, токен).
        """
        return self._port_spinbox.value(), self._token_edit.text().strip()

    def is_editing_settings(self) -> bool:
        """
        Проверка активного редактирования настроек.

        Returns:
            True, если фокус находится на полях порта или токена.
        """
        return self._port_spinbox.hasFocus() or self._token_edit.hasFocus()

    def set_settings(self, port: int, token: str) -> None:
        """
        Установка значений формы.

        Args:
            port: Порт API сервера.
            token: API токен.
        """
        self._port_spinbox.setValue(port)
        self._token_edit.setText(token)

    def set_status(self, running: bool, message: str | None = None) -> None:
        """
        Обновление отображения статуса сервера.

        Args:
            running: Признак запущенного сервера.
            message: Дополнительное сообщение о статусе.
        """
        self._server_running = running
        self._update_server_controls(running)

        if message is None:
            message = "Сервер запущен" if running else "Сервер остановлен"

        self._status_label.setText(f"Статус: {message}")
        tone = "success" if running else "muted"
        self._status_label.setStyleSheet(Theme.status_style(tone))
        self._server_state_label.setText(message)
        self._server_state_label.setStyleSheet(
            Theme.secondary_text_style()
            if not running
            else f"color: {Theme.COLORS['success']};"
        )

    def set_log_text(self, text: str) -> None:
        """
        Полная замена содержимого окна логов.

        Args:
            text: Текст логов.
        """
        self._log_view.setPlainText(text)
        self._scroll_logs_to_end()

    def append_log_text(self, text: str) -> None:
        """
        Добавление текста в окно логов.

        Args:
            text: Текст для добавления.
        """
        if not text:
            return
        cleaned_text = text.rstrip("\n")
        if self._log_view.toPlainText():
            self._log_view.appendPlainText(cleaned_text)
        else:
            self._log_view.setPlainText(cleaned_text)
        self._scroll_logs_to_end()

    def refresh_logs(self, show_loading_state: bool = False) -> None:
        """Обновление логов API из файла."""
        if show_loading_state:
            self._show_loading_state()
        try:
            log_path = self._resolve_current_log_path()
            if log_path is None:
                self._log_source_label.setText("Журнал API: файл не найден")
                self._set_empty_state(_LOG_EMPTY_TEXT)
                return

            self._log_source_label.setText(f"Файл логов: {log_path.name}")
            if log_path != self._current_log_path:
                self._current_log_path = log_path
                self._log_offset = 0
                self._load_full_log(log_path)
                self._set_log_status("Журнал API обновлён")
                return

            self._append_new_log_data(log_path)
            self._set_log_status("Журнал API обновлён")
        except Exception as e:
            logger.error(f"Не удалось обновить журнал API: {e}")
            self._set_error_state(f"Не удалось обновить журнал API: {e}")

    def set_auto_refresh_enabled(self, enabled: bool) -> None:
        """
        Включить или выключить автообновление логов.

        Args:
            enabled: Требуемое состояние автообновления.
        """
        if self._auto_refresh_enabled == enabled:
            return

        self._auto_refresh_enabled = enabled
        if enabled:
            self._log_timer.start(_LOG_REFRESH_INTERVAL_MS)
            self._set_log_status("Автообновление включено")
            self.refresh_logs(show_loading_state=not self._log_loaded_once)
            return

        self._stop_auto_refresh()
        self._set_log_status(_AUTO_REFRESH_PAUSED_TEXT)

    def showEvent(self, event: Any) -> None:
        """Активирует lifecycle-aware auto-refresh при показе вкладки."""
        self.set_auto_refresh_enabled(True)
        try:
            super().showEvent(event)
        except AttributeError:
            return

    def hideEvent(self, event: Any) -> None:
        """Отключает автообновление, когда вкладка скрыта."""
        self._stop_auto_refresh()
        self._auto_refresh_enabled = False
        self._set_log_status(_AUTO_REFRESH_PAUSED_TEXT)
        try:
            super().hideEvent(event)
        except AttributeError:
            return

    def _resolve_current_log_path(self) -> Path | None:
        """Определение актуального файла логов API."""
        api_log_dir = Path(get_api_log_dir())
        if not api_log_dir.exists():
            return None

        log_files = sorted(
            api_log_dir.glob("api_*.log"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if log_files:
            return log_files[0]

        return None

    def _load_full_log(self, log_path: Path) -> None:
        """Загрузка файла логов целиком после смены источника."""
        if not log_path.exists():
            self._set_empty_state("Файл журнала API пока не создан. Запустите сервер.")
            self._log_offset = 0
            return

        with open(log_path, "rb") as file:
            data = file.read()

        text = data.decode("utf-8", errors="replace")
        self._log_view.setPlainText(text or "Журнал API пуст.")
        self._log_offset = len(data)
        self._log_loaded_once = True
        self._scroll_logs_to_end()

    def _append_new_log_data(self, log_path: Path) -> None:
        """Подгрузка новых строк из файла логов."""
        if not log_path.exists():
            return

        size = log_path.stat().st_size
        if size < self._log_offset:
            self._load_full_log(log_path)
            return

        if size == self._log_offset:
            return

        with open(log_path, "rb") as file:
            file.seek(self._log_offset)
            data = file.read()

        if not data:
            return

        self._log_offset = self._log_offset + len(data)
        self._log_loaded_once = True
        self.append_log_text(data.decode("utf-8", errors="replace"))

    def _update_server_controls(self, running: bool) -> None:
        """Обновление состояния кнопок управления сервером."""
        self._start_btn.setEnabled(not running)
        self._stop_btn.setEnabled(running)
        self._restart_btn.setEnabled(running)

    def _stop_auto_refresh(self) -> None:
        """Остановить таймер автообновления, если он доступен."""
        stop = getattr(self._log_timer, "stop", None)
        if callable(stop):
            stop()

    def _show_loading_state(self) -> None:
        """Показать пользователю состояние загрузки журнала."""
        self._set_log_status(_LOG_LOADING_TEXT)
        if not self._log_view.toPlainText():
            self._log_view.setPlainText(_LOG_LOADING_TEXT)

    def _set_empty_state(self, message: str) -> None:
        """Показать состояние отсутствия данных."""
        self._log_loaded_once = True
        self._log_view.setPlainText(message)
        self._set_log_status("Журнал API пуст или ещё не создан")

    def _set_error_state(self, message: str) -> None:
        """Показать состояние ошибки загрузки журнала."""
        if not self._log_view.toPlainText():
            self._log_view.setPlainText(message)
        self._set_log_status(message, color="red")

    def _set_log_status(self, message: str, color: str = "gray") -> None:
        """Обновить подпись состояния журнала."""
        self._log_status_label.setText(message)
        tone = "muted"
        if color == "red":
            tone = "danger"
        elif color == "orange":
            tone = "warning"
        elif color == "green":
            tone = "success"
        self._log_status_label.setStyleSheet(
            Theme.secondary_text_style()
            if tone == "muted"
            else f"color: {Theme.COLORS[tone]};"
        )

    def _scroll_logs_to_end(self) -> None:
        """Прокрутка окна логов к последней строке."""
        from PyQt6.QtGui import QTextCursor

        cursor = self._log_view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self._log_view.setTextCursor(cursor)
        self._log_view.ensureCursorVisible()
