"""
Модуль иконки трея
==================

Иконка системного трея для приложения видеозаписи.
Обеспечивает быстрый доступ к общим действиям и отображение статуса.
"""

from pathlib import Path

from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PyQt6.QtWidgets import QMenu, QMessageBox, QSystemTrayIcon

from logger_config import get_module_logger

logger = get_module_logger(__name__)


class TrayIcon(QSystemTrayIcon):
    """
    Иконка системного трея для видеозаписи.

    Возможности:
    - Визуальный индикатор статуса (запись, пауза, ожидание)
    - Контекстное меню с быстрыми действиями
    - Уведомления о событиях записи
    """

    # Сигналы
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    pause_requested = pyqtSignal()
    show_window_requested = pyqtSignal()
    exit_requested = pyqtSignal()

    def __init__(self, parent=None, icon_path: Path | None = None):
        """
        Инициализация иконки трея.

        Args:
            parent: Родительский QObject
            icon_path: Путь к пользовательской иконке (опционально)
        """
        super().__init__(parent)

        self._icon_path = icon_path
        self._is_recording = False
        self._is_paused = False

        # Создание иконок для разных состояний
        self._icons = {
            "idle": self._create_icon(QColor(100, 100, 100)),
            "recording": self._create_icon(QColor(255, 0, 0)),
            "paused": self._create_icon(QColor(255, 165, 0)),
        }

        # Установка начальной иконки
        self.setIcon(self._icons["idle"])
        self.setToolTip("MIA-ScreenCapture - Ожидание")

        # Создание контекстного меню
        self._create_menu()

        # Таймер анимации для состояния записи
        self._animation_timer = QTimer()
        self._animation_timer.timeout.connect(self._animate_recording)
        self._animation_frame = 0

        logger.info("Иконка трея инициализирована")

    def _create_icon(self, color: QColor) -> QIcon:
        """
        Создание цветной иконки для трея.

        Args:
            color: Цвет иконки

        Returns:
            Экземпляр QIcon
        """
        if self._icon_path and self._icon_path.exists():
            # Загрузка пользовательской иконки
            return QIcon(str(self._icon_path))

        # Создание иконки по умолчанию (круг с цветом)
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))  # Прозрачный фон

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Отрисовка круга
        painter.setBrush(color)
        painter.setPen(QColor(255, 255, 255))
        painter.drawEllipse(8, 8, 48, 48)

        # Отрисовка внутреннего круга для индикатора записи
        if color == QColor(255, 0, 0):
            painter.setBrush(QColor(200, 0, 0))
            painter.drawEllipse(16, 16, 32, 32)

        painter.end()

        return QIcon(pixmap)

    def _create_menu(self) -> None:
        """Создание контекстного меню."""
        menu = QMenu()

        # Действие показа окна
        self._show_action = QAction("Показать окно", self)
        self._show_action.triggered.connect(self.show_window_requested)
        menu.addAction(self._show_action)

        menu.addSeparator()

        # Действие запуска
        self._start_action = QAction("Начать запись", self)
        self._start_action.triggered.connect(self.start_requested)
        menu.addAction(self._start_action)

        # Действие остановки
        self._stop_action = QAction("Остановить запись", self)
        self._stop_action.triggered.connect(self.stop_requested)
        self._stop_action.setEnabled(False)
        menu.addAction(self._stop_action)

        # Действие паузы
        self._pause_action = QAction("Пауза", self)
        self._pause_action.triggered.connect(self.pause_requested)
        self._pause_action.setEnabled(False)
        menu.addAction(self._pause_action)

        menu.addSeparator()

        # Действие выхода
        self._exit_action = QAction("Выход", self)
        self._exit_action.triggered.connect(self._on_exit)
        menu.addAction(self._exit_action)

        self.setContextMenu(menu)

    def _on_exit(self) -> None:
        """Обработка действия выхода."""
        reply = QMessageBox.question(
            None,
            "Выход из MIA-ScreenCapture",
            "Вы уверены, что хотите выйти?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.exit_requested.emit()

    def _animate_recording(self) -> None:
        """Анимация иконки во время записи."""
        self._animation_frame = (self._animation_frame + 1) % 2

        if self._is_paused:
            self.setIcon(self._icons["paused"])
        elif self._animation_frame == 0:
            self.setIcon(self._icons["recording"])
        else:
            # Немного более тёмный красный для анимации
            self.setIcon(self._create_icon(QColor(200, 0, 0)))

    def set_recording_state(
        self, is_recording: bool, is_paused: bool = False
    ) -> None:
        """
        Обновление индикатора состояния записи.

        Args:
            is_recording: Активна ли запись
            is_paused: На паузе ли запись
        """
        self._is_recording = is_recording
        self._is_paused = is_paused

        # Обновление действий
        self._start_action.setEnabled(not is_recording)
        self._stop_action.setEnabled(is_recording)
        self._pause_action.setEnabled(is_recording)

        if is_paused:
            self._pause_action.setText("Возобновить")
        else:
            self._pause_action.setText("Пауза")

        # Обновление иконки и подсказки
        if is_recording:
            if is_paused:
                self.setIcon(self._icons["paused"])
                self.setToolTip("MIA-ScreenCapture - Пауза")
                self._animation_timer.stop()
            else:
                self.setToolTip("MIA-ScreenCapture - Запись")
                self._animation_timer.start(500)  # Мигание каждые 500мс
        else:
            self.setIcon(self._icons["idle"])
            self.setToolTip("MIA-ScreenCapture - Ожидание")
            self._animation_timer.stop()

    def show_notification(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
    ) -> None:
        """
        Показ уведомления из иконки трея.

        Args:
            title: Заголовок уведомления
            message: Сообщение уведомления
            icon: Тип иконки (Information, Warning, Critical)
        """
        if self.supportsMessages():
            self.showMessage(title, message, icon, 3000)
        else:
            logger.warning(f"Уведомление трея: {title} - {message}")

    def on_recording_started(self, output_path: str) -> None:
        """Обработка события начала записи."""
        self.set_recording_state(True, False)
        self.show_notification("Запись начата", f"Запись в: {output_path}")

    def on_recording_stopped(self, output_path: str) -> None:
        """Обработка события остановки записи."""
        self.set_recording_state(False, False)
        self.show_notification(
            "Запись остановлена", f"Сохранено в: {output_path}"
        )

    def on_recording_paused(self) -> None:
        """Обработка события паузы записи."""
        self.set_recording_state(True, True)
        self.show_notification("Запись приостановлена", "")

    def on_recording_resumed(self) -> None:
        """Обработка события возобновления записи."""
        self.set_recording_state(True, False)
        self.show_notification("Запись возобновлена", "")

    def on_error(self, error_message: str) -> None:
        """Обработка события ошибки."""
        self.show_notification(
            "Ошибка", error_message, QSystemTrayIcon.MessageIcon.Critical
        )

    def cleanup(self) -> None:
        """Очистка ресурсов."""
        self._animation_timer.stop()
        self.hide()
        logger.info("Иконка трея очищена")
