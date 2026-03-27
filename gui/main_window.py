"""
Модуль главного окна (рефакторинг)
===================================

Главное окно GUI для приложения записи видео.
Использует MVC архитектуру с разделением на компоненты.
"""

import os
import platform
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import get_config
from core.recording_types import AudioMode, CaptureMode
from gui.controllers.recording_controller import RecordingController
from gui.controllers.settings_controller import SettingsController
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    VideoSettings,
)
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.output_view import OutputView
from gui.views.video_view import VideoView
from logger_config import get_module_logger
from recorder.utils import check_ffmpeg, format_filesize, format_time

logger = get_module_logger(__name__)


class MainWindow(QMainWindow):
    """
    Главное окно приложения.

    Использует MVC архитектуру:
    - Model: RecordingState
    - View: CaptureView, AudioView, VideoView, OutputView
    - Controller: RecordingController, SettingsController
    """

    # Сигналы
    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal(str)
    recording_paused = pyqtSignal()
    recording_resumed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    close_requested = pyqtSignal(object)

    def __init__(self, headless: bool = False):
        """
        Инициализация главного окна.

        Args:
            headless: Если True, окно будет скрыто
        """
        super().__init__()

        self._headless = headless

        # Инициализация модели и контроллеров
        self._state = RecordingState()
        self._recording_controller = RecordingController(self._state)
        self._settings_controller = SettingsController(
            self._state, get_config()
        )

        # Таймер обновления статуса
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)

        # Настройка окна
        self._setup_window()
        self._setup_ui()
        self._connect_signals()

        # Загрузка настроек
        self._settings_controller.load_settings()
        self._apply_settings_to_views()

        # Проверка зависимостей
        self._check_dependencies()

        # Запуск таймера обновления
        self._update_timer.start(100)  # 10 FPS обновление

        logger.info("Главное окно инициализировано")

    def _setup_window(self) -> None:
        """Настройка свойств окна."""
        self.setWindowTitle("MIA-ScreenCapture")
        self.setMinimumSize(800, 600)
        self.resize(900, 700)

        # Центрирование на экране
        from PyQt6.QtGui import QGuiApplication

        primary_screen = QGuiApplication.primaryScreen()
        if primary_screen:
            screen = primary_screen.geometry()
        else:
            screen = self._get_default_geometry()
        size = self.geometry()
        self.move(
            (screen.width() - size.width()) // 2,
            (screen.height() - size.height()) // 2,
        )

    def _setup_ui(self) -> None:
        """Настройка пользовательского интерфейса."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Создание вкладок
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Вкладка записи
        recording_tab = self._create_recording_tab()
        self.tabs.addTab(recording_tab, "Запись")

        # Вкладка планировщика
        from gui.scheduler_tab import SchedulerTab

        self.scheduler_tab = SchedulerTab()
        self.tabs.addTab(self.scheduler_tab, "Планировщик")

        # Вкладка диагностики
        from gui.views.diagnostics_view import DiagnosticsView

        self._diagnostics_view = DiagnosticsView()
        self._diagnostics_view.recheck_requested.connect(self._run_diagnostics)
        self._diagnostics_view.fix_requested.connect(self._on_diagnostics_fix)
        self.tabs.addTab(self._diagnostics_view, "Диагностика")

        # Строка состояния
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Индикатор состояния
        self.status_label = QLabel("Готов")
        self.status_bar.addPermanentWidget(self.status_label)

        # Индикатор времени
        self.time_label = QLabel("00:00")
        self.status_bar.addPermanentWidget(self.time_label)

    def _create_recording_tab(self) -> QWidget:
        """Создание вкладки записи."""
        widget = QWidget()
        layout = QHBoxLayout(widget)

        # Левая панель - Элементы управления
        left_panel = self._create_left_panel()
        layout.addWidget(left_panel, stretch=2)

        # Правая панель - Последние записи
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, stretch=1)

        return widget

    def _create_left_panel(self) -> QWidget:
        """Создание левой панели с элементами управления."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Представления (Views)
        self._capture_view = CaptureView()
        layout.addWidget(self._capture_view)

        self._audio_view = AudioView()
        layout.addWidget(self._audio_view)

        self._video_view = VideoView()
        layout.addWidget(self._video_view)

        self._output_view = OutputView()
        layout.addWidget(self._output_view)

        # Кнопки управления
        buttons_layout = self._create_control_buttons()
        layout.addLayout(buttons_layout)

        return widget

    def _create_control_buttons(self) -> QHBoxLayout:
        """Создание кнопок управления."""
        layout = QHBoxLayout()

        self.start_btn = QPushButton("Начать запись")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start_recording)
        layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setMinimumHeight(40)
        self.pause_btn.setEnabled(False)
        self.pause_btn.clicked.connect(self._toggle_pause)
        layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop_recording)
        layout.addWidget(self.stop_btn)

        return layout

    def _create_right_panel(self) -> QWidget:
        """Создание правой панели с последними записями."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        from PyQt6.QtWidgets import QGroupBox

        group = QGroupBox("Последние записи")
        group_layout = QVBoxLayout(group)

        self.recordings_list = QListWidget()
        self.recordings_list.itemDoubleClicked.connect(self._open_recording)
        group_layout.addWidget(self.recordings_list)

        # Кнопки
        btn_layout = QHBoxLayout()

        open_folder_btn = QPushButton("Открыть папку")
        open_folder_btn.clicked.connect(self._open_recording_folder)
        btn_layout.addWidget(open_folder_btn)

        open_file_btn = QPushButton("Открыть файл")
        open_file_btn.clicked.connect(self._open_selected_recording)
        btn_layout.addWidget(open_file_btn)

        group_layout.addLayout(btn_layout)

        layout.addWidget(group)

        return widget

    def _connect_signals(self) -> None:
        """Подключение сигналов от представлений."""
        # Сигналы CaptureView
        self._capture_view.capture_type_changed.connect(
            self._on_capture_type_changed
        )
        self._capture_view.window_selected.connect(self._on_window_selected)
        self._capture_view.rect_selected.connect(self._on_rect_selected)

        # Сигналы AudioView
        self._audio_view.audio_type_changed.connect(
            self._on_audio_type_changed
        )
        self._audio_view.mic_device_changed.connect(
            self._on_mic_device_changed
        )

        # Сигналы VideoView
        self._video_view.settings_changed.connect(
            self._on_video_settings_changed
        )

        # Сигналы OutputView
        self._output_view.output_path_changed.connect(
            self._on_output_path_changed
        )

    def _apply_settings_to_views(self) -> None:
        """Применение настроек к представлениям."""
        # Настройки видео
        self._video_view.set_settings(self._state.video)

        # Путь вывода
        if self._state.output.default_path:
            self._output_view.set_output_path(self._state.output.default_path)

        # Недавние записи
        self._refresh_recent_recordings()

    def _refresh_recent_recordings(self) -> None:
        """Обновление списка недавних записей."""
        self.recordings_list.clear()
        for rec in self._state.recent_recordings:
            if rec.path.exists():
                item_text = f"{rec.path.name} - {format_filesize(rec.size)} - {rec.date}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, str(rec.path))
                self.recordings_list.addItem(item)

    # === Обработчики сигналов от представлений ===

    def _on_capture_type_changed(self, capture_type) -> None:
        """Обработка изменения типа области захвата."""
        self._settings_controller.update_capture_settings(
            capture_type=capture_type
        )

    def _on_window_selected(self, window_title: str) -> None:
        """Обработка выбора окна."""
        self._settings_controller.update_capture_settings(
            window_title=window_title
        )

    def _on_rect_selected(self, coords: tuple[int, int, int, int]) -> None:
        """Обработка выбора прямоугольника."""
        self._settings_controller.update_capture_settings(rect_coords=coords)

    def _on_audio_type_changed(self, audio_type: AudioMode) -> None:
        """Обработка изменения типа аудио."""
        self._settings_controller.update_audio_settings(audio_type=audio_type)

    def _on_mic_device_changed(self, device_index: int) -> None:
        """Обработка выбора устройства микрофона."""
        self._settings_controller.update_audio_settings(
            mic_device_index=device_index
        )

    def _on_video_settings_changed(self, settings) -> None:
        """Обработка изменения настроек видео."""
        self._settings_controller.update_video_settings(
            fps=settings.fps,
            codec=settings.codec,
            bitrate=settings.bitrate,
            format=settings.format,
        )
        self._output_view.set_default_format(settings.format)

    def _on_output_path_changed(self, path: str) -> None:
        """Обработка изменения пути вывода."""
        self._settings_controller.update_output_settings(output_path=path)

    # === Управление записью ===

    def _start_recording(self) -> None:
        """Запуск записи."""
        if self._state.is_recording():
            return

        # Получение настроек из представлений
        capture_type = self._capture_view.get_capture_type()
        rect_coords = self._capture_view.get_rect_coords()

        # Проверка координат для прямоугольной области
        if capture_type == CaptureMode.RECT and rect_coords is None:
            self._show_error("Введите корректные координаты области захвата")
            return

        # Fallback на полное разрешение экрана
        if rect_coords is None:
            from PyQt6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                rect_coords = (0, 0, geometry.width(), geometry.height())
            else:
                rect_coords = (0, 0, 1920, 1080)

        capture = CaptureSettings(
            capture_type=capture_type,
            window_title=self._capture_view.get_window_title(),
            rect_coords=rect_coords,
        )

        audio = self._state.audio
        video = self._video_view.get_settings()
        output_path = self._settings_controller.get_output_path()

        # Запуск записи через контроллер
        success, error_msg = self._recording_controller.start_recording(
            output_path=output_path,
            capture=capture,
            audio=audio,
            video=video,
        )

        if success:
            self._on_recording_started(output_path)
        else:
            self._show_error(error_msg or "Не удалось запустить запись")

    def _stop_recording(self) -> None:
        """Остановка записи."""
        if not self._state.is_recording() and not self._state.is_paused():
            return

        output_path = self._recording_controller.stop_recording()

        if output_path:
            self._on_recording_stopped(output_path)
        else:
            self._show_error("Не удалось сохранить запись")

    def _toggle_pause(self) -> None:
        """Переключение состояния паузы."""
        if self._state.is_paused():
            self._recording_controller.resume_recording()
            self._on_recording_resumed()
        else:
            self._recording_controller.pause_recording()
            self._on_recording_paused()

    # === Обработчики событий записи ===

    def _on_recording_started(self, output_path: Path) -> None:
        """Обработка запуска записи."""
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setEnabled(True)
        self.pause_btn.setText("Пауза")

        self.status_label.setText("Запись")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

        self.recording_started.emit(str(output_path))
        logger.info(f"Запись запущена: {output_path}")

    def _on_recording_stopped(self, output_path: Path) -> None:
        """Обработка остановки записи."""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.pause_btn.setEnabled(False)

        self.status_label.setText("Готов")
        self.status_label.setStyleSheet("")
        self.time_label.setText("00:00")

        # Добавление в список последних записей
        if output_path.exists():
            size = output_path.stat().st_size
            self._settings_controller.add_recent_recording(output_path, size)
            self._refresh_recent_recordings()

        self.recording_stopped.emit(str(output_path))
        logger.info(f"Запись остановлена: {output_path}")

    def _on_recording_paused(self) -> None:
        """Обработка приостановки записи."""
        self.pause_btn.setText("Продолжить")
        self.status_label.setText("Пауза")
        self.status_label.setStyleSheet("color: orange; font-weight: bold;")

        self.recording_paused.emit()

    def _on_recording_resumed(self) -> None:
        """Обработка возобновления записи."""
        self.pause_btn.setText("Пауза")
        self.status_label.setText("Запись")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")

        self.recording_resumed.emit()

    def _update_status(self) -> None:
        """Обновление отображения статуса."""
        if self._state.is_recording():
            elapsed = self._recording_controller.elapsed_time
            self.time_label.setText(format_time(elapsed))

    # === Вспомогательные методы ===

    def _open_recording(self, item: QListWidgetItem) -> None:
        """Открытие файла записи."""
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self._open_file(path)

    def _open_selected_recording(self) -> None:
        """Открытие выбранного файла записи."""
        item = self.recordings_list.currentItem()
        if item:
            self._open_recording(item)

    def _open_recording_folder(self) -> None:
        """Открытие папки с выбранной записью."""
        item = self.recordings_list.currentItem()
        if item:
            path = Path(item.data(Qt.ItemDataRole.UserRole))
            if path.parent.exists():
                self._open_folder(str(path.parent))

    def _open_file(self, path: str) -> None:
        """Открытие файла с помощью системного приложения по умолчанию."""
        system = platform.system()
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def _open_folder(self, path: str) -> None:
        """Открытие папки в файловом менеджере."""
        system = platform.system()
        if system == "Windows":
            subprocess.run(["explorer", path])
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def _show_error(self, message: str) -> None:
        """Показ сообщения об ошибке."""
        QMessageBox.critical(self, "Ошибка", message)
        self.error_occurred.emit(message)

    def _check_dependencies(self) -> None:
        """Проверка необходимых зависимостей."""
        ffmpeg_available, version = check_ffmpeg()
        if not ffmpeg_available:
            QMessageBox.warning(
                self,
                "FFmpeg не найден",
                "FFmpeg не установлен или не найден в PATH.\n\n"
                "Пожалуйста, установите FFmpeg для кодирования видео.\n"
                "Скачать: https://ffmpeg.org/download.html",
            )

    def _get_default_geometry(self):
        """Возвращает геометрию по умолчанию при отсутствии экрана."""
        from PyQt6.QtCore import QRect

        return QRect(0, 0, 1920, 1080)

    def closeEvent(self, event) -> None:
        """Обработка события закрытия окна."""
        # Сначала эмитируем сигнал для внешней обработки
        self.close_requested.emit(event)

        # Если событие было проигнорировано внешним обработчиком, выходим
        if not event.isAccepted():
            return

        # Стандартная обработка закрытия
        if self._state.is_recording():
            reply = QMessageBox.question(
                self,
                "Запись в процессе",
                "Запись в процессе. Остановить и сохранить?",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )

            if reply == QMessageBox.StandardButton.Yes:
                self._stop_recording()
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self._settings_controller.save_settings()
        self._update_timer.stop()
        event.accept()

    # === Публичные методы для API ===

    def get_status(self) -> dict:
        """
        Получение текущего статуса записи.

        Returns:
            Словарь с информацией о статусе записи
        """
        return {
            "is_recording": self._state.is_recording(),
            "is_paused": self._state.is_paused(),
            "elapsed_time": self._recording_controller.elapsed_time,
            "current_file": str(self._state.current_output)
            if self._state.current_output
            else None,
        }

    def _run_diagnostics(self) -> None:
        """Запуск диагностики системы."""
        logger.info("_run_diagnostics вызван")
        try:
            config = get_config()
            output_path = config.settings.output.default_path
            logger.info(f"output_path: {output_path}")

            api_running = False
            if self._api_server is not None:
                try:
                    api_running = self._api_server.is_running()
                except Exception:
                    api_running = False

            logger.info(f"api_running: {api_running}")
            self._diagnostics_view.run_checks(
                api_enabled=api_running,
                output_path=output_path,
            )
            logger.info("Диагностика завершена")
        except Exception as e:
            logger.error(f"Ошибка диагностики: {e}")

    def _on_diagnostics_fix(self, check_name: str) -> None:
        """Обработка нажатия кнопки исправления."""
        if check_name == "Папка вывода":
            self._select_output_folder()

    def _select_output_folder(self) -> None:
        """Выбор папки для сохранения записей."""
        from PyQt6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self,
            "Выберите папку для сохранения записей",
            "",
        )
        if folder:
            config = get_config()
            config.settings.output.default_path = folder
            config.save()
            self._run_diagnostics()

    def start_recording_with_params(self, params: dict) -> dict:
        """
        Запуск записи с параметрами из API.

        Args:
            params: Словарь с параметрами записи
                - area: "full" | "window" | "rect"
                - window_title: str (опционально)
                - rect: [x1, y1, x2, y2] (опционально)
                - audio: "mic" | "system" | "none" | "both"
                - fps: int (опционально)
                - codec: str (опционально)
                - bitrate: str (опционально)
                - duration: int (опционально)
                - output_path: str (опционально)

        Returns:
            Словарь с результатом операции
        """
        if self._state.is_recording():
            return {"success": False, "error": "Запись уже идёт"}

        try:
            # Определение типа захвата
            area_type = params.get("area", "full")
            capture_type_map = {
                "full": CaptureMode.FULL,
                "window": CaptureMode.WINDOW,
                "rect": CaptureMode.RECT,
            }
            capture_type = capture_type_map.get(area_type, CaptureMode.FULL)

            # Координаты прямоугольника
            rect_coords = None
            if area_type == "rect" and "rect" in params:
                r = params["rect"]
                if isinstance(r, (list, tuple)) and len(r) >= 4:
                    rect_coords = (r[0], r[1], r[2], r[3])
                else:
                    return {
                        "success": False,
                        "error": "rect должен содержать 4 координаты [x1, y1, x2, y2]",
                    }

            # Настройки захвата
            capture = CaptureSettings(
                capture_type=capture_type,
                window_title=params.get("window_title") or "",
                rect_coords=rect_coords or (0, 0, 1920, 1080),
            )

            # Настройки аудио
            audio_type_map = {
                "mic": AudioMode.MIC,
                "system": AudioMode.SYSTEM,
                "none": AudioMode.NONE,
                "both": AudioMode.BOTH,
            }
            audio_type = audio_type_map.get(
                params.get("audio", "mic"), AudioMode.MIC
            )
            # Используем метод состояния для thread-safe изменения
            self._state.set_audio_type(audio_type)
            audio_settings = AudioSettings(
                audio_type=audio_type,
                mic_device_index=params.get("mic_device_index"),
            )

            # Настройки видео (создаём копию для избежания race condition)
            base_settings = self._video_view.get_settings()
            video_settings = VideoSettings(
                fps=params.get("fps", base_settings.fps),
                codec=params.get("codec", base_settings.codec),
                bitrate=params.get("bitrate", base_settings.bitrate),
                format=base_settings.format,
            )

            # Путь вывода
            output_path = params.get("output_path")
            if output_path:
                output_path = Path(output_path)
            else:
                output_path = self._settings_controller.get_output_path()

            # Запуск записи
            success, error_msg = self._recording_controller.start_recording(
                output_path=output_path,
                capture=capture,
                audio=audio_settings,
                video=video_settings,
            )

            if success:
                self._on_recording_started(output_path)
                return {
                    "success": True,
                    "output_path": str(output_path),
                }
            else:
                return {
                    "success": False,
                    "error": error_msg or "Не удалось запустить запись",
                }

        except Exception as e:
            logger.error(f"Ошибка запуска записи: {e}")
            return {"success": False, "error": str(e)}

    def stop_recording(self) -> dict:
        """
        Остановка текущей записи.

        Returns:
            Словарь с результатом операции
        """
        if not self._state.is_recording():
            return {"success": False, "error": "Запись не идёт"}

        output_path = self._recording_controller.stop_recording()

        if output_path:
            self._on_recording_stopped(output_path)
            return {
                "success": True,
                "filepath": str(output_path),
            }
        else:
            return {"success": False, "error": "Не удалось сохранить запись"}

    def toggle_pause(self) -> dict:
        """
        Переключение состояния паузы.

        Returns:
            Словарь с новым состоянием паузы
        """
        if not self._state.is_recording():
            return {"success": False, "error": "Запись не идёт"}

        if self._state.is_paused():
            self._recording_controller.resume_recording()
            self._on_recording_resumed()
            return {"success": True, "is_paused": False}
        else:
            self._recording_controller.pause_recording()
            self._on_recording_paused()
            return {"success": True, "is_paused": True}

    def get_recordings(self) -> list:
        """
        Получение списка недавних записей.

        Returns:
            Список словарей с информацией о записях
        """
        config = get_config()
        return config.settings.recent_recordings
