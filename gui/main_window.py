"""
Модуль главного окна
====================

Главное окно GUI для приложения записи видео.
Содержит все элементы управления для записи, настроек и планировщика.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import get_config
from logger_config import get_module_logger
from recorder.audio_recorder import AudioRecorder, SystemAudioRecorder
from recorder.encoder import EncodingSettings, RecordingEncoder
from recorder.utils import (
    check_ffmpeg,
    format_filesize,
    format_time,
    get_audio_devices,
    get_available_windows,
    get_screen_size,
)
from recorder.video_recorder import CaptureArea, VideoRecorder

logger = get_module_logger(__name__)


class RecordingManager:
    """
    Управляет процессом записи, включая видео, аудио и кодирование.
    """

    def __init__(self):
        """Инициализация менеджера записи."""
        self.video_recorder: Optional[VideoRecorder] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        self.encoder: Optional[RecordingEncoder] = None

        self._is_recording = False
        self._is_paused = False
        self._current_output: Optional[Path] = None
        self._temp_video: Optional[Path] = None
        self._temp_audio: Optional[Path] = None

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    @property
    def is_paused(self) -> bool:
        return self._is_paused

    @property
    def elapsed_time(self) -> float:
        if self.video_recorder:
            return self.video_recorder.elapsed_time
        return 0

    @property
    def current_output(self) -> Optional[Path]:
        return self._current_output

    def start(
        self,
        output_path: Path,
        capture_area: CaptureArea,
        audio_type: str = "none",
        fps: int = 30,
        codec: str = "libx264",
        bitrate: str = "2M",
        duration: Optional[int] = None,
        mic_device: Optional[int] = None,
    ) -> bool:
        """
        Запуск записи.

        Args:
            output_path: Путь к выходному файлу
            capture_area: Область захвата экрана
            audio_type: Тип источника аудио
            fps: Кадров в секунду
            codec: Видеокодек
            bitrate: Битрейт видео
            duration: Длительность записи в секундах
            mic_device: Индекс устройства микрофона

        Returns:
            True если запись успешно запущена
        """
        try:
            self._current_output = Path(output_path)

            # Настройка кодировщика
            settings = EncodingSettings(codec=codec, bitrate=bitrate)
            self.encoder = RecordingEncoder(self._current_output, settings)
            self._temp_video, self._temp_audio = self.encoder.setup()

            # Инициализация видеозаписи
            self.video_recorder = VideoRecorder(
                fps=fps, codec=codec, bitrate=bitrate
            )

            # Запуск видеозаписи
            if not self.video_recorder.start(
                self._temp_video, capture_area, duration
            ):
                self.encoder.cancel()
                return False

            # Запуск аудиозаписи при необходимости
            if audio_type in ("mic", "both"):
                self.audio_recorder = AudioRecorder()
                self.audio_recorder.start(
                    self._temp_audio,
                    device_index=mic_device,
                    duration=duration,
                )
            elif audio_type == "system":
                try:
                    self.audio_recorder = SystemAudioRecorder()
                    self.audio_recorder.start(
                        self._temp_audio, duration=duration
                    )
                except Exception as e:
                    logger.warning(f"Системное аудио недоступно: {e}")
                    self.audio_recorder = None

            self._is_recording = True
            self._is_paused = False
            return True

        except Exception as e:
            logger.error(f"Не удалось запустить запись: {e}")
            self._cleanup()
            return False

    def pause(self) -> bool:
        """Приостановка записи."""
        if not self._is_recording or self._is_paused:
            return False

        if self.video_recorder:
            self.video_recorder.pause()
        if self.audio_recorder:
            self.audio_recorder.pause()

        self._is_paused = True
        return True

    def resume(self) -> bool:
        """Возобновление записи."""
        if not self._is_recording or not self._is_paused:
            return False

        if self.video_recorder:
            self.video_recorder.resume()
        if self.audio_recorder:
            self.audio_recorder.resume()

        self._is_paused = False
        return True

    def stop(self) -> Optional[Path]:
        """
        Остановка записи и финализация.

        Returns:
            Путь к выходному файлу или None при ошибке
        """
        if not self._is_recording:
            return None

        # Остановка видео
        if self.video_recorder:
            self.video_recorder.stop()

        # Остановка аудио
        has_audio = self.audio_recorder is not None
        if self.audio_recorder:
            self.audio_recorder.stop()

        # Финализация (объединение видео и аудио)
        if self.encoder:
            success, error = self.encoder.finalize(has_audio=has_audio)
            if not success:
                logger.error(f"Не удалось финализировать запись: {error}")
                return None

        self._is_recording = False
        self._is_paused = False

        return self._current_output

    def cancel(self) -> None:
        """Отмена записи без сохранения."""
        if self.video_recorder:
            self.video_recorder.stop()
        if self.audio_recorder:
            self.audio_recorder.stop()
        if self.encoder:
            self.encoder.cancel()

        self._is_recording = False
        self._is_paused = False

    def _cleanup(self) -> None:
        """Очистка ресурсов."""
        if self.video_recorder:
            self.video_recorder.stop()
            self.video_recorder = None
        if self.audio_recorder:
            self.audio_recorder.stop()
            self.audio_recorder = None
        if self.encoder:
            self.encoder.cancel()
            self.encoder = None


class MainWindow(QMainWindow):
    """
    Главное окно приложения.

    Содержит:
    - Элементы управления записью
    - Выбор области захвата
    - Настройки аудио
    - Настройки видео
    - Настройки вывода
    - Список последних записей
    - Вкладку планировщика
    """

    # Сигналы
    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal(str)
    recording_paused = pyqtSignal()
    recording_resumed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    close_requested = pyqtSignal(object)  # Сигнал для обработки закрытия окна

    def __init__(self, headless: bool = False):
        """
        Инициализация главного окна.

        Args:
            headless: Если True, окно будет скрыто
        """
        super().__init__()

        self._headless = headless
        self._recording_manager = RecordingManager()
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)

        # Загрузка конфигурации
        self._config = get_config()

        # Настройка окна
        self._setup_window()
        self._setup_ui()
        self._load_settings()

        # Проверка FFmpeg
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

        # Группа области захвата
        capture_group = self._create_capture_group()
        layout.addWidget(capture_group)

        # Группа настроек аудио
        audio_group = self._create_audio_group()
        layout.addWidget(audio_group)

        # Группа настроек видео
        video_group = self._create_video_group()
        layout.addWidget(video_group)

        # Группа настроек вывода
        output_group = self._create_output_group()
        layout.addWidget(output_group)

        # Кнопки управления
        buttons_layout = self._create_control_buttons()
        layout.addLayout(buttons_layout)

        return widget

    def _create_capture_group(self) -> QGroupBox:
        """Создание группы выбора области захвата."""
        group = QGroupBox("Область захвата")
        layout = QVBoxLayout(group)

        # Радиокнопки
        self.area_button_group = QButtonGroup()

        self.full_screen_radio = QRadioButton("Весь экран")
        self.full_screen_radio.setChecked(True)
        self.area_button_group.addButton(self.full_screen_radio, 0)
        layout.addWidget(self.full_screen_radio)

        self.window_radio = QRadioButton("Окно")
        self.area_button_group.addButton(self.window_radio, 1)
        layout.addWidget(self.window_radio)

        # Селектор окон
        window_layout = QHBoxLayout()
        self.window_combo = QComboBox()
        self.window_combo.setMinimumWidth(200)
        self._refresh_windows()

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self._refresh_windows)
        refresh_btn.setMaximumWidth(80)

        window_layout.addWidget(QLabel("Окно:"))
        window_layout.addWidget(self.window_combo)
        window_layout.addWidget(refresh_btn)
        layout.addLayout(window_layout)

        self.rect_radio = QRadioButton("Прямоугольник")
        self.area_button_group.addButton(self.rect_radio, 2)
        layout.addWidget(self.rect_radio)

        # Координаты прямоугольника
        rect_layout = QHBoxLayout()
        self.rect_edit = QLineEdit()
        self.rect_edit.setPlaceholderText("X1, Y1, X2, Y2")
        self.rect_edit.setEnabled(False)

        select_rect_btn = QPushButton("Выбрать")
        select_rect_btn.setMaximumWidth(80)
        select_rect_btn.clicked.connect(self._select_rectangle)

        rect_layout.addWidget(QLabel("Координаты:"))
        rect_layout.addWidget(self.rect_edit)
        rect_layout.addWidget(select_rect_btn)
        layout.addLayout(rect_layout)

        # Подключение радиокнопок
        self.area_button_group.buttonClicked.connect(self._on_area_changed)
        self._on_area_changed(self.full_screen_radio)

        return group

    def _create_audio_group(self) -> QGroupBox:
        """Создание группы настроек аудио."""
        group = QGroupBox("Настройки аудио")
        layout = QVBoxLayout(group)

        # Тип аудио
        self.audio_button_group = QButtonGroup()

        self.no_audio_radio = QRadioButton("Без аудио")
        self.no_audio_radio.setChecked(True)
        self.audio_button_group.addButton(self.no_audio_radio, 0)
        layout.addWidget(self.no_audio_radio)

        self.mic_radio = QRadioButton("Микрофон")
        self.audio_button_group.addButton(self.mic_radio, 1)
        layout.addWidget(self.mic_radio)

        self.system_audio_radio = QRadioButton("Системное аудио")
        self.audio_button_group.addButton(self.system_audio_radio, 2)
        layout.addWidget(self.system_audio_radio)

        # Селектор микрофона
        mic_layout = QHBoxLayout()
        self.mic_combo = QComboBox()
        self._refresh_audio_devices()

        refresh_mic_btn = QPushButton("Обновить")
        refresh_mic_btn.setMaximumWidth(80)
        refresh_mic_btn.clicked.connect(self._refresh_audio_devices)

        mic_layout.addWidget(QLabel("Устройство:"))
        mic_layout.addWidget(self.mic_combo)
        mic_layout.addWidget(refresh_mic_btn)
        layout.addLayout(mic_layout)

        return group

    def _create_video_group(self) -> QGroupBox:
        """Создание группы настроек видео."""
        group = QGroupBox("Настройки видео")
        layout = QGridLayout(group)

        # FPS
        layout.addWidget(QLabel("FPS:"), 0, 0)
        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(1, 120)
        self.fps_spin.setValue(30)
        layout.addWidget(self.fps_spin, 0, 1)

        # Кодек
        layout.addWidget(QLabel("Кодек:"), 0, 2)
        self.codec_combo = QComboBox()
        self.codec_combo.addItems(["libx264", "mp4v", "h264", "xvid"])
        layout.addWidget(self.codec_combo, 0, 3)

        # Битрейт
        layout.addWidget(QLabel("Битрейт:"), 1, 0)
        self.bitrate_combo = QComboBox()
        self.bitrate_combo.setEditable(True)
        self.bitrate_combo.addItems(["1M", "2M", "4M", "8M", "10M"])
        self.bitrate_combo.setCurrentText("2M")
        layout.addWidget(self.bitrate_combo, 1, 1)

        # Формат
        layout.addWidget(QLabel("Формат:"), 1, 2)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["mp4", "avi", "mkv"])
        layout.addWidget(self.format_combo, 1, 3)

        return group

    def _create_output_group(self) -> QGroupBox:
        """Создание группы настроек вывода."""
        group = QGroupBox("Вывод")
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel("Сохранить в:"))
        self.output_edit = QLineEdit()
        layout.addWidget(self.output_edit)

        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self._browse_output)
        layout.addWidget(browse_btn)

        return group

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

    def _refresh_windows(self) -> None:
        """Обновление списка доступных окон."""
        self.window_combo.clear()
        windows = get_available_windows()

        for win in windows:
            self.window_combo.addItem(win["title"])

    def _refresh_audio_devices(self) -> None:
        """Обновление списка аудиоустройств."""
        self.mic_combo.clear()
        devices = get_audio_devices()

        for dev in devices.get("input", []):
            self.mic_combo.addItem(dev["name"], dev["id"])

    def _on_area_changed(self, button: QRadioButton) -> None:
        """Обработка изменения типа области захвата."""
        is_window = button == self.window_radio
        is_rect = button == self.rect_radio

        self.window_combo.setEnabled(is_window)
        self.rect_edit.setEnabled(is_rect)

    def _select_rectangle(self) -> None:
        """Открытие overlay для выбора прямоугольника."""
        # Здесь открывается полноэкранное прозрачное окно для выбора
        # Для простоты используем диалог
        from PyQt6.QtWidgets import QInputDialog

        screen_width, screen_height = get_screen_size()

        text, ok = QInputDialog.getText(
            self,
            "Выбор области",
            "Введите координаты (x1, y1, x2, y2):",
            QLineEdit.EchoMode.Normal,
            f"0, 0, {screen_width}, {screen_height}",
        )

        if ok:
            self.rect_edit.setText(text)
            self.rect_radio.setChecked(True)

    def _browse_output(self) -> None:
        """Выбор места сохранения выходного файла."""
        default_name = (
            f"recording_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
        )

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить запись",
            str(
                Path(self.output_edit.text()) / default_name
                if self.output_edit.text()
                else default_name
            ),
            "MP4 файлы (*.mp4);;AVI файлы (*.avi);;Все файлы (*)",
        )

        if file_path:
            self.output_edit.setText(file_path)

    def _get_capture_area(self) -> CaptureArea:
        """Получение текущей конфигурации области захвата."""
        if self.full_screen_radio.isChecked():
            return CaptureArea.full_screen()
        elif self.window_radio.isChecked():
            window_title = self.window_combo.currentText()
            return CaptureArea.from_window(window_title)
        elif self.rect_radio.isChecked():
            coords_text = self.rect_edit.text()
            try:
                coords = [int(x.strip()) for x in coords_text.split(",")]
                if len(coords) == 4:
                    return CaptureArea.from_rect(*coords)
            except ValueError:
                pass
            return CaptureArea.full_screen()

        return CaptureArea.full_screen()

    def _get_audio_type(self) -> str:
        """Получение текущего типа аудио."""
        if self.mic_radio.isChecked():
            return "mic"
        elif self.system_audio_radio.isChecked():
            return "system"
        return "none"

    def _get_output_path(self) -> Path:
        """Получение пути к выходному файлу."""
        output_text = self.output_edit.text()
        if output_text:
            return Path(output_text)

        # Генерация пути по умолчанию
        config = self._config.settings
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        format_ext = self.format_combo.currentText()
        filename = f"recording_{timestamp}.{format_ext}"

        default_path = config.output.default_path
        if default_path:
            return Path(default_path) / filename
        return Path(filename)

    def _start_recording(self) -> None:
        """Запуск записи."""
        if self._recording_manager.is_recording:
            return

        output_path = self._get_output_path()
        capture_area = self._get_capture_area()
        audio_type = self._get_audio_type()

        # Получение индекса устройства микрофона
        mic_device = None
        if audio_type in ("mic", "both"):
            mic_device = self.mic_combo.currentData()

        # Запуск записи
        success = self._recording_manager.start(
            output_path=output_path,
            capture_area=capture_area,
            audio_type=audio_type,
            fps=self.fps_spin.value(),
            codec=self.codec_combo.currentText(),
            bitrate=self.bitrate_combo.currentText(),
            mic_device=mic_device,
        )

        if success:
            self._on_recording_started(output_path)
        else:
            self._show_error("Не удалось запустить запись")

    def _stop_recording(self) -> None:
        """Остановка записи."""
        if not self._recording_manager.is_recording:
            return

        output_path = self._recording_manager.stop()

        if output_path:
            self._on_recording_stopped(output_path)
        else:
            self._show_error("Не удалось сохранить запись")

    def _toggle_pause(self) -> None:
        """Переключение состояния паузы."""
        if self._recording_manager.is_paused:
            self._recording_manager.resume()
            self._on_recording_resumed()
        else:
            self._recording_manager.pause()
            self._on_recording_paused()

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
        self._add_recent_recording(output_path)

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
        if self._recording_manager.is_recording:
            elapsed = self._recording_manager.elapsed_time
            self.time_label.setText(format_time(elapsed))

    def _add_recent_recording(self, path: Path) -> None:
        """Добавление записи в список последних."""
        if not path.exists():
            return

        size = path.stat().st_size
        item_text = f"{path.name} - {format_filesize(size)} - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        item = QListWidgetItem(item_text)
        item.setData(Qt.ItemDataRole.UserRole, str(path))
        self.recordings_list.insertItem(0, item)

        # Ограничение размера списка
        while self.recordings_list.count() > 20:
            self.recordings_list.takeItem(self.recordings_list.count() - 1)

        # Сохранение в конфигурацию
        self._config.add_recent_recording(str(path), size)

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
        import platform
        import subprocess

        system = platform.system()
        if system == "Windows":
            os.startfile(path)
        elif system == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])

    def _open_folder(self, path: str) -> None:
        """Открытие папки в файловом менеджере."""
        import platform
        import subprocess

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

    def _load_settings(self) -> None:
        """Загрузка настроек из конфигурации."""
        settings = self._config.settings

        # Настройки видео
        self.fps_spin.setValue(settings.video.fps)
        self.codec_combo.setCurrentText(settings.video.codec)
        self.bitrate_combo.setCurrentText(settings.video.bitrate)
        self.format_combo.setCurrentText(settings.video.format)

        # Путь вывода
        if settings.output.default_path:
            self.output_edit.setText(settings.output.default_path)

        # Загрузка последних записей
        for rec in settings.recent_recordings:
            path = Path(rec["path"])
            if path.exists():
                size = rec.get("size", path.stat().st_size)
                date = rec.get("date", "")
                item_text = f"{path.name} - {format_filesize(size)} - {date}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, str(path))
                self.recordings_list.addItem(item)

    def _save_settings(self) -> None:
        """Сохранение текущих настроек в конфигурацию."""
        settings = self._config.settings

        # Настройки видео
        settings.video.fps = self.fps_spin.value()
        settings.video.codec = self.codec_combo.currentText()
        settings.video.bitrate = self.bitrate_combo.currentText()
        settings.video.format = self.format_combo.currentText()

        # Путь вывода
        output_text = self.output_edit.text()
        if output_text:
            settings.output.default_path = output_text

        self._config.save()

    def closeEvent(self, event) -> None:
        """Обработка события закрытия окна."""
        # Сначала эмитируем сигнал для внешней обработки
        self.close_requested.emit(event)

        # Если событие было проигнорировано внешним обработчиком, выходим
        if not event.isAccepted():
            return

        # Стандартная обработка закрытия
        if self._recording_manager.is_recording:
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

        self._save_settings()
        self._update_timer.stop()
        event.accept()

    def _get_default_geometry(self):
        """Возвращает геометрию по умолчанию при отсутствии экрана."""
        from PyQt6.QtCore import QRect
        return QRect(0, 0, 1920, 1080)
