"""
Модуль главного окна (рефакторинг)
===================================

Главное окно GUI для приложения записи видео.
Использует MVC архитектуру с разделением на компоненты.
"""

import os
import platform
import subprocess
import threading
import webbrowser
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
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
from core.readiness import (
    ReadinessSnapshot,
    RecordingReadinessService,
    build_readiness_checks,
)
from core.recording_types import AudioMode, CaptureMode
from gui.controllers.recording_controller import RecordingController
from gui.controllers.settings_controller import SettingsController
from gui.controllers.websocket_controller import WebSocketClientController
from gui.desktop_actions import (
    DesktopAction,
    DesktopActionId,
    DesktopActionRegistry,
    get_desktop_action_spec,
)
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
    VideoSettings,
)
from gui.styles.theme import Theme
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.output_view import OutputView
from gui.views.readiness_center_view import ReadinessCenterView
from gui.views.recording_indicator import RecordingIndicatorOverlay
from gui.views.video_view import VideoView
from logger_config import get_module_logger
from recorder.utils import check_ffmpeg, format_filesize, format_time

logger = get_module_logger(__name__)
_STATUS_UPDATE_INTERVAL_MS = 100

if TYPE_CHECKING:
    from core.application_facade import ApplicationFacade


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
    stop_operation_finished = pyqtSignal(object, object)
    dependency_check_completed = pyqtSignal(object, object)
    readiness_refresh_completed = pyqtSignal(
        int,
        object,
        object,
        object,
        object,
    )

    def __init__(self, headless: bool = False):
        """
        Инициализация главного окна.

        Args:
            headless: Если True, окно будет скрыто
        """
        super().__init__()

        self._headless = headless
        self._application_facade: ApplicationFacade | None = None
        self._stop_operation_thread: threading.Thread | None = None
        self._stop_operation_in_progress = False

        # Инициализация модели и контроллеров
        self._state = RecordingState()
        self._recording_controller = RecordingController(self._state)
        self._settings_controller = SettingsController(
            self._state, get_config()
        )
        self._readiness_service = RecordingReadinessService()
        self._desktop_actions = DesktopActionRegistry()
        self._registered_shortcuts: dict[str, str] = {}
        self._tab_navigation_order: list[QWidget] = []
        self._ws_controller: WebSocketClientController | None = None
        self._recording_indicator = RecordingIndicatorOverlay()
        self._readiness_request_id = 0
        self._latest_readiness_snapshot: ReadinessSnapshot | None = None
        self._latest_readiness_inputs: dict[str, object] | None = None

        # Таймер обновления статуса
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)

        # Настройка окна
        self._setup_window()
        self._setup_ui()
        self._setup_desktop_actions()
        self._connect_signals()

        # Загрузка настроек
        self._settings_controller.load_settings()
        self._apply_settings_to_views()
        self._refresh_api_status()

        # Проверка зависимостей
        self._check_dependencies()
        self._refresh_readiness_summary()

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

        # Вкладка API
        from gui.views.api_settings_view import ApiSettingsView

        self._api_settings_view = ApiSettingsView()
        self.tabs.addTab(self._api_settings_view, "API")

        # Строка состояния
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Индикатор состояния
        self.status_label = QLabel("Готов")
        self.status_bar.addPermanentWidget(self.status_label)

        # Индикатор WebSocket соединения
        self._ws_status_label = QLabel("WS: —")
        self._ws_status_label.setToolTip(
            "Статус WebSocket-соединения с API сервером"
        )
        self.status_bar.addPermanentWidget(self._ws_status_label)

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

        self._readiness_center_view = ReadinessCenterView()
        layout.addWidget(self._readiness_center_view)

        # Кнопки управления
        buttons_layout = self._create_control_buttons()
        layout.addLayout(buttons_layout)

        return widget

    def _create_control_buttons(self) -> QHBoxLayout:
        """Создание кнопок управления."""
        layout = QHBoxLayout()

        self.start_btn = QPushButton("Начать запись")
        self.start_btn.setMinimumHeight(40)
        layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setMinimumHeight(40)
        self.pause_btn.setEnabled(False)
        layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setMinimumHeight(40)
        self.stop_btn.setEnabled(False)
        layout.addWidget(self.stop_btn)

        return layout

    def _create_right_panel(self) -> QWidget:
        """Создание правой панели с последними записями."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        from PyQt6.QtWidgets import QGroupBox

        group = QGroupBox("Последние записи")
        group_layout = QVBoxLayout(group)

        filter_layout = QHBoxLayout()
        self._recordings_filter_input = QLineEdit()
        self._recordings_filter_input.setPlaceholderText(
            "Фильтр по имени файла"
        )
        self._recordings_filter_input.textChanged.connect(
            lambda _text: self._refresh_recent_recordings()
        )
        filter_layout.addWidget(self._recordings_filter_input)

        self._clear_filter_btn = QPushButton("Сбросить")
        self._clear_filter_btn.clicked.connect(self._clear_recordings_filter)
        filter_layout.addWidget(self._clear_filter_btn)
        group_layout.addLayout(filter_layout)

        self.recordings_list = QListWidget()
        self.recordings_list.itemDoubleClicked.connect(self._open_recording)
        group_layout.addWidget(self.recordings_list)

        # Кнопки
        btn_layout = QHBoxLayout()

        self._open_latest_btn = QPushButton("Открыть последний")
        btn_layout.addWidget(self._open_latest_btn)

        self._open_folder_btn = QPushButton("Открыть папку")
        btn_layout.addWidget(self._open_folder_btn)

        self._open_file_btn = QPushButton("Открыть файл")
        self._open_file_btn.clicked.connect(self._open_selected_recording)
        btn_layout.addWidget(self._open_file_btn)

        self._clear_list_btn = QPushButton("Очистить список")
        self._clear_list_btn.clicked.connect(self._clear_recent_recordings)
        btn_layout.addWidget(self._clear_list_btn)

        group_layout.addLayout(btn_layout)

        layout.addWidget(group)

        return widget

    def _connect_signals(self) -> None:
        """Подключение сигналов от представлений."""
        # Ключевые desktop actions
        self.start_btn.clicked.connect(
            lambda: self._desktop_actions.execute(
                DesktopActionId.START_RECORDING
            )
        )
        self.pause_btn.clicked.connect(
            lambda: self._desktop_actions.execute(DesktopActionId.TOGGLE_PAUSE)
        )
        self.stop_btn.clicked.connect(
            lambda: self._desktop_actions.execute(
                DesktopActionId.STOP_RECORDING
            )
        )
        self._open_latest_btn.clicked.connect(
            lambda: self._desktop_actions.execute(
                DesktopActionId.OPEN_LATEST_RECORDING
            )
        )
        self._open_folder_btn.clicked.connect(
            lambda: self._desktop_actions.execute(
                DesktopActionId.OPEN_RECORDING_FOLDER
            )
        )

        # Сигналы CaptureView
        self._capture_view.capture_type_changed.connect(
            self._on_capture_type_changed
        )
        self._capture_view.window_selected.connect(self._on_window_selected)
        self._capture_view.rect_selected.connect(self._on_rect_selected)
        self._capture_view.windows_load_completed.connect(
            lambda *_: self._refresh_readiness_summary()
        )

        # Сигналы AudioView
        self._audio_view.audio_type_changed.connect(
            self._on_audio_type_changed
        )
        self._audio_view.mic_device_changed.connect(
            self._on_mic_device_changed
        )
        self._audio_view.devices_load_completed.connect(
            lambda *_: self._refresh_readiness_summary()
        )

        # Сигналы VideoView
        self._video_view.settings_changed.connect(
            self._on_video_settings_changed
        )

        # Сигналы OutputView
        self._output_view.output_path_changed.connect(
            self._on_output_path_changed
        )
        self.stop_operation_finished.connect(self._on_stop_operation_finished)
        self.dependency_check_completed.connect(
            self._on_dependency_check_completed
        )
        self.readiness_refresh_completed.connect(
            self._on_readiness_refresh_completed
        )

        # Сигналы ApiSettingsView
        self._api_settings_view.apply_requested.connect(
            self._on_api_settings_apply
        )
        self._api_settings_view.start_requested.connect(self._on_api_start)
        self._api_settings_view.stop_requested.connect(self._on_api_stop)
        self._api_settings_view.restart_requested.connect(self._on_api_restart)
        self._api_settings_view.refresh_requested.connect(
            self._refresh_api_status
        )
        self._readiness_center_view.refresh_requested.connect(
            self._refresh_readiness_summary
        )
        self._readiness_center_view.details_requested.connect(
            self._show_readiness_details
        )
        self._readiness_center_view.action_requested.connect(
            self._handle_readiness_action
        )

    def _setup_desktop_actions(self) -> None:
        """Создать action registry, shortcuts и accessibility metadata."""
        start_spec = get_desktop_action_spec(DesktopActionId.START_RECORDING)
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.START_RECORDING,
                title=start_spec.title,
                description=start_spec.description,
                callback=self._start_recording,
                shortcut=start_spec.shortcut,
                enabled_when=lambda: not self._state.is_recording(),
            )
        )
        pause_spec = get_desktop_action_spec(DesktopActionId.TOGGLE_PAUSE)
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.TOGGLE_PAUSE,
                title=pause_spec.title,
                description=pause_spec.description,
                callback=self._toggle_pause,
                shortcut=pause_spec.shortcut,
                enabled_when=lambda: (
                    self._state.is_recording() or self._state.is_paused()
                ),
            )
        )
        stop_spec = get_desktop_action_spec(DesktopActionId.STOP_RECORDING)
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.STOP_RECORDING,
                title=stop_spec.title,
                description=stop_spec.description,
                callback=self._stop_recording,
                shortcut=stop_spec.shortcut,
                enabled_when=lambda: (
                    self._state.is_recording() or self._state.is_paused()
                ),
            )
        )
        latest_spec = get_desktop_action_spec(
            DesktopActionId.OPEN_LATEST_RECORDING
        )
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.OPEN_LATEST_RECORDING,
                title=latest_spec.title,
                description=latest_spec.description,
                callback=self._open_latest_recording,
                shortcut=latest_spec.shortcut,
            )
        )
        folder_spec = get_desktop_action_spec(
            DesktopActionId.OPEN_RECORDING_FOLDER
        )
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.OPEN_RECORDING_FOLDER,
                title=folder_spec.title,
                description=folder_spec.description,
                callback=self._open_recording_folder,
                shortcut=folder_spec.shortcut,
            )
        )
        recording_tab_spec = get_desktop_action_spec(
            DesktopActionId.SHOW_RECORDING_TAB
        )
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.SHOW_RECORDING_TAB,
                title=recording_tab_spec.title,
                description=recording_tab_spec.description,
                callback=lambda: self.tabs.setCurrentIndex(0),
                shortcut=recording_tab_spec.shortcut,
            )
        )
        diagnostics_tab_spec = get_desktop_action_spec(
            DesktopActionId.SHOW_DIAGNOSTICS_TAB
        )
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.SHOW_DIAGNOSTICS_TAB,
                title=diagnostics_tab_spec.title,
                description=diagnostics_tab_spec.description,
                callback=lambda: self.tabs.setCurrentWidget(
                    self._diagnostics_view
                ),
                shortcut=diagnostics_tab_spec.shortcut,
            )
        )
        api_tab_spec = get_desktop_action_spec(DesktopActionId.SHOW_API_TAB)
        self._desktop_actions.register(
            DesktopAction(
                action_id=DesktopActionId.SHOW_API_TAB,
                title=api_tab_spec.title,
                description=api_tab_spec.description,
                callback=lambda: self.tabs.setCurrentWidget(
                    self._api_settings_view
                ),
                shortcut=api_tab_spec.shortcut,
            )
        )

        self._apply_action_metadata(
            self.start_btn,
            DesktopActionId.START_RECORDING,
        )
        self._apply_action_metadata(
            self.pause_btn,
            DesktopActionId.TOGGLE_PAUSE,
        )
        self._apply_action_metadata(
            self.stop_btn,
            DesktopActionId.STOP_RECORDING,
        )
        self._apply_action_metadata(
            self._open_latest_btn,
            DesktopActionId.OPEN_LATEST_RECORDING,
        )
        self._apply_action_metadata(
            self._open_folder_btn,
            DesktopActionId.OPEN_RECORDING_FOLDER,
        )

        self._apply_accessible_metadata(
            self.tabs,
            "Основные вкладки приложения",
            "Позволяет переключаться между записью, планировщиком, "
            "диагностикой и API.",
        )
        self._apply_accessible_metadata(
            self.status_label,
            "Статус записи",
            "Показывает текущее состояние записи и readiness-подсказки.",
        )
        self._apply_accessible_metadata(
            self._ws_status_label,
            "Статус WebSocket",
            "Показывает состояние соединения с API сервером.",
        )
        self._apply_accessible_metadata(
            self.time_label,
            "Таймер записи",
            "Показывает длительность текущей записи.",
        )
        self._apply_accessible_metadata(
            self.recordings_list,
            "Список последних записей",
            "Содержит последние записанные файлы и позволяет открыть их.",
        )
        self._apply_accessible_metadata(
            self._recordings_filter_input,
            "Фильтр записей",
            "Фильтрует список последних записей по имени и дате.",
        )

        self._configure_tab_order()
        self._register_qt_shortcuts()

    def _apply_action_metadata(
        self,
        widget: QWidget,
        action_id: DesktopActionId,
    ) -> None:
        """Применить tooltip/accessibility metadata для desktop-действия."""
        action = self._desktop_actions.get(action_id)
        tooltip = action.description
        if action.shortcut:
            tooltip = f"{tooltip} Горячая клавиша: {action.shortcut}."
            self._registered_shortcuts[action_id.value] = action.shortcut
        self._apply_accessible_metadata(
            widget,
            action.title,
            action.description,
        )
        widget_any = cast(Any, widget)
        widget_any._tooltip = tooltip
        set_tooltip = getattr(widget, "setToolTip", None)
        if callable(set_tooltip):
            set_tooltip(tooltip)

        set_shortcut = getattr(widget, "setShortcut", None)
        if callable(set_shortcut) and action.shortcut:
            set_shortcut(action.shortcut)
        if action.shortcut:
            widget_any._shortcut = action.shortcut

    def _apply_accessible_metadata(
        self,
        widget: QWidget,
        accessible_name: str,
        accessible_description: str,
    ) -> None:
        """Назначить accessible metadata с fallback для unit-test моков."""
        widget_any = cast(Any, widget)
        widget_any._accessible_name = accessible_name
        widget_any._accessible_description = accessible_description
        set_name = getattr(widget, "setAccessibleName", None)
        if callable(set_name):
            set_name(accessible_name)

        set_description = getattr(widget, "setAccessibleDescription", None)
        if callable(set_description):
            set_description(accessible_description)

    def _configure_tab_order(self) -> None:
        """Настроить логичный tab order для сценариев без мыши."""
        tab_order = [
            self.start_btn,
            self.pause_btn,
            self.stop_btn,
            self._recordings_filter_input,
            self.recordings_list,
            self._open_latest_btn,
            self._open_folder_btn,
        ]
        self._tab_navigation_order = tab_order
        set_tab_order = getattr(self, "setTabOrder", None)
        if callable(set_tab_order):
            for current_widget, next_widget in zip(
                tab_order,
                tab_order[1:],
                strict=False,
            ):
                set_tab_order(current_widget, next_widget)

    def _register_qt_shortcuts(self) -> None:
        """Зарегистрировать оконные shortcuts для key actions."""
        self._qt_shortcuts: list[Any] = []
        try:
            from PyQt6.QtGui import QKeySequence, QShortcut
        except Exception:
            return

        for action in self._desktop_actions.all():
            if not action.shortcut:
                continue
            try:
                shortcut = QShortcut(QKeySequence(action.shortcut), self)
                shortcut.activated.connect(
                    lambda action_id=action.action_id: (
                        self._desktop_actions.execute(action_id)
                    )
                )
                self._qt_shortcuts.append(shortcut)
            except Exception:
                continue

    def _apply_settings_to_views(self) -> None:
        """Применение настроек к представлениям."""
        self._capture_view.set_capture_type(self._state.capture.capture_type)
        self._capture_view.set_window_title(self._state.capture.window_title)
        if self._state.capture.capture_type == CaptureMode.RECT:
            self._capture_view.set_rect_coords(self._state.capture.rect_coords)

        # Настройки аудио
        self._audio_view.set_audio_type(self._state.audio.audio_type)
        if self._state.audio.mic_device_index is not None:
            self._audio_view.set_mic_device_index(
                self._state.audio.mic_device_index
            )
        if self._state.audio.mic_device_name:
            self._audio_view.set_mic_device_name(
                self._state.audio.mic_device_name
            )

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
        filter_text = self._normalized_recordings_filter()
        for rec in self._state.recent_recordings:
            if not rec.path.exists():
                continue
            if not self._recording_matches_filter(
                rec.path.name, rec.date, filter_text
            ):
                continue
            item_text = (
                f"{rec.path.name} - {format_filesize(rec.size)} - {rec.date}"
            )
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, str(rec.path))
            self.recordings_list.addItem(item)

    def _clear_recordings_filter(self) -> None:
        """Сброс фильтра списка недавних записей."""
        self._recordings_filter_input.setText("")
        self._refresh_recent_recordings()

    def _normalized_recordings_filter(self) -> str:
        """Нормализация текста фильтра для сравнения."""
        return self._recordings_filter_input.text().strip().lower()

    @staticmethod
    def _recording_matches_filter(
        filename: str, date_text: str, filter_text: str
    ) -> bool:
        """Проверка попадания записи под фильтр."""
        normalized_filter = filter_text.strip().lower()
        if not normalized_filter:
            return True
        haystack = f"{filename.lower()} {date_text.lower()}"
        return normalized_filter in haystack

    # === Обработчики сигналов от представлений ===

    def _on_capture_type_changed(self, capture_type) -> None:
        """Обработка изменения типа области захвата."""
        self._settings_controller.update_capture_settings(
            capture_type=capture_type
        )
        self._refresh_readiness_summary()

    def _on_window_selected(self, window_title: str) -> None:
        """Обработка выбора окна."""
        self._settings_controller.update_capture_settings(
            window_title=window_title
        )
        self._refresh_readiness_summary()

    def _on_rect_selected(self, coords: tuple[int, int, int, int]) -> None:
        """Обработка выбора прямоугольника."""
        self._settings_controller.update_capture_settings(rect_coords=coords)
        self._refresh_readiness_summary()

    def _on_audio_type_changed(self, audio_type: AudioMode) -> None:
        """Обработка изменения типа аудио."""
        self._settings_controller.update_audio_settings(audio_type=audio_type)
        self._refresh_readiness_summary()

    def _on_mic_device_changed(self, device_index: int) -> None:
        """Обработка выбора устройства микрофона."""
        self._settings_controller.update_audio_settings(
            mic_device_index=device_index
        )
        self._refresh_readiness_summary()

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
        self._refresh_readiness_summary()

    def _refresh_readiness_summary(self) -> None:
        """Асинхронно обновить compact readiness center."""
        if not hasattr(self, "_readiness_center_view"):
            return

        capture = self._build_capture_settings_from_views()
        if capture is None:
            self._readiness_center_view.set_error_state(
                "Сначала выберите корректную область прямоугольного захвата."
            )
            return

        audio = self._build_audio_settings_from_state()
        output_path = self._settings_controller.get_output_path()
        self._readiness_request_id += 1
        request_id = self._readiness_request_id
        self._readiness_center_view.set_loading_state()

        threading.Thread(
            target=self._refresh_readiness_worker,
            args=(request_id, capture, audio, output_path),
            daemon=True,
        ).start()

    def _refresh_readiness_worker(
        self,
        request_id: int,
        capture: CaptureSettings,
        audio: AudioSettings,
        output_path: Path,
    ) -> None:
        """Собрать readiness snapshot в фоне для inline summary."""
        try:
            snapshot = self._readiness_service.evaluate(
                capture=capture,
                audio=audio,
                output_path=output_path,
            )
            self.readiness_refresh_completed.emit(
                request_id,
                snapshot,
                None,
                capture,
                audio,
            )
        except Exception as error:
            self.readiness_refresh_completed.emit(
                request_id,
                None,
                str(error),
                capture,
                audio,
            )

    def _on_readiness_refresh_completed(
        self,
        request_id: int,
        snapshot: object,
        error: object,
        capture: object,
        audio: object,
    ) -> None:
        """Применить readiness snapshot к compact center."""
        if request_id != self._readiness_request_id:
            return

        if error is not None:
            self._readiness_center_view.set_error_state(str(error))
            return

        if not isinstance(snapshot, ReadinessSnapshot):
            return

        if not isinstance(capture, CaptureSettings) or not isinstance(
            audio,
            AudioSettings,
        ):
            return

        checks = build_readiness_checks(snapshot, capture, audio)
        self._latest_readiness_snapshot = snapshot
        self._latest_readiness_inputs = {
            "capture": capture,
            "audio": audio,
            "output_path": self._settings_controller.get_output_path(),
        }
        self._readiness_center_view.apply_checks(checks)

    def _show_readiness_details(self) -> None:
        """Открыть вкладку диагностики и запустить подробную проверку."""
        if hasattr(self, "tabs") and hasattr(self, "_diagnostics_view"):
            self.tabs.setCurrentWidget(self._diagnostics_view)
        self._run_diagnostics()

    def _handle_readiness_action(self, action_key: str) -> None:
        """Выполнить one-click action из readiness center или диагностики."""
        if action_key == "open_ffmpeg_docs":
            webbrowser.open("https://ffmpeg.org/download.html")
            return

        if action_key == "choose_output_path":
            self._select_output_folder()
            return

        if action_key == "refresh_windows":
            self.tabs.setCurrentIndex(0)
            self._capture_view._refresh_windows()
            return

        if action_key == "focus_capture_window":
            self.tabs.setCurrentIndex(0)
            self._capture_view.set_capture_type(CaptureMode.WINDOW)
            focus = getattr(self._capture_view._window_combo, "setFocus", None)
            if callable(focus):
                focus()
            return

        if action_key == "refresh_audio_devices":
            self.tabs.setCurrentIndex(0)
            self._audio_view._refresh_audio_devices()
            return

        if action_key == "focus_microphone_selection":
            self.tabs.setCurrentIndex(0)
            focus = getattr(self._audio_view._mic_combo, "setFocus", None)
            if callable(focus):
                focus()
            return

        if action_key == "API сервер":
            self.tabs.setCurrentWidget(self._api_settings_view)
            return

        fallback_action_map = {
            "Папка вывода": "choose_output_path",
            "Аудиоустройства": "refresh_audio_devices",
            "Окно захвата": "refresh_windows",
            "FFmpeg": "open_ffmpeg_docs",
        }
        resolved_action = fallback_action_map.get(action_key)
        if resolved_action is not None:
            self._handle_readiness_action(resolved_action)

    # === Управление записью ===

    def bind_application_facade(
        self,
        application_facade: "ApplicationFacade",
    ) -> None:
        """
        Подключает фасад приложения к окну.

        Args:
            application_facade: Публичный runtime/API фасад.
        """
        self._application_facade = application_facade

    def _start_recording(self) -> None:
        """Запуск записи."""
        if self._state.is_recording():
            return

        capture = self._build_capture_settings_from_views()
        if capture is None:
            self._show_non_modal_error(
                "Введите корректные координаты области захвата"
            )
            return

        audio = self._build_audio_settings_from_state()
        video = self._video_view.get_settings()
        output_path = self._settings_controller.get_output_path()
        readiness = self._readiness_service.evaluate(
            capture=capture,
            audio=audio,
            output_path=output_path,
        )
        if not self._apply_readiness_snapshot(readiness):
            return

        # Запуск записи через контроллер
        success, error_msg = self._recording_controller.start_recording(
            output_path=output_path,
            capture=capture,
            audio=audio,
            video=video,
        )

        if success:
            self._on_recording_started(output_path, capture)
        else:
            self._show_non_modal_error(
                error_msg or "Не удалось запустить запись"
            )

    def _apply_readiness_snapshot(self, snapshot) -> bool:
        """
        Применить readiness snapshot к стартовому сценарию записи.

        Args:
            snapshot: Результат preflight-проверки.

        Returns:
            `True`, если старт можно продолжать.
        """
        if hasattr(self, "_readiness_center_view"):
            capture = (
                self._build_capture_settings_from_views() or CaptureSettings()
            )
            audio = self._build_audio_settings_from_state()
            checks = build_readiness_checks(snapshot, capture, audio)
            self._readiness_center_view.apply_checks(checks)

        if snapshot.is_ready:
            if snapshot.warning_issues:
                self.status_bar.showMessage(
                    f"Проверка готовности: {snapshot.summary_text()}",
                    7000,
                )
            return True

        self.status_label.setText("Не готово к записи")
        self.status_label.setStyleSheet(Theme.status_style("warning"))
        self.status_bar.showMessage(
            f"Старт заблокирован: {snapshot.summary_text()}",
            10000,
        )
        if hasattr(self, "tabs") and hasattr(self, "_diagnostics_view"):
            self.tabs.setCurrentWidget(self._diagnostics_view)
            self._run_diagnostics()
        return False

    def _build_capture_settings_from_views(self) -> CaptureSettings | None:
        """Собрать текущие настройки захвата из GUI."""
        capture_type = self._capture_view.get_capture_type()
        rect_coords = self._capture_view.get_rect_coords()

        if capture_type == CaptureMode.RECT and rect_coords is None:
            return None

        if rect_coords is None:
            from PyQt6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                rect_coords = (0, 0, geometry.width(), geometry.height())
            else:
                rect_coords = (0, 0, 1920, 1080)

        return CaptureSettings(
            capture_type=capture_type,
            window_title=self._capture_view.get_window_title(),
            rect_coords=rect_coords,
        )

    def _build_audio_settings_from_state(self) -> AudioSettings:
        """Собрать текущие настройки аудио из состояния приложения."""
        return AudioSettings(
            audio_type=self._state.audio.audio_type,
            mic_device_index=self._state.audio.mic_device_index,
            mic_device_name=self._state.audio.mic_device_name,
        )

    def start_recording(self) -> dict[str, Any]:
        """
        Публичный запуск записи с текущими UI-настройками.

        Returns:
            Результат запуска записи.
        """
        if self._state.is_recording():
            return {"success": False, "error": "Запись уже идёт"}

        self._start_recording()
        if self._state.is_recording():
            return {
                "success": True,
                "output_path": str(self._state.current_output)
                if self._state.current_output is not None
                else None,
            }
        return {"success": False, "error": "Не удалось запустить запись"}

    def _stop_recording(self) -> None:
        """Остановка записи."""
        if self._stop_operation_in_progress:
            self._cancel_stop_operation()
            return

        if not self._state.is_recording() and not self._state.is_paused():
            return
        self._begin_stop_operation()

    def request_stop_recording(self) -> dict[str, Any]:
        """
        Публичный запрос остановки записи из интерактивного UI.

        Returns:
            Снимок текущего статуса.
        """
        self._stop_recording()
        return self.get_status()

    def _toggle_pause(self) -> None:
        """Переключение состояния паузы."""
        if self._stop_operation_in_progress:
            return
        if self._state.is_paused():
            self._recording_controller.resume_recording()
            self._on_recording_resumed()
        else:
            self._recording_controller.pause_recording()
            self._on_recording_paused()

    def request_toggle_pause(self) -> dict[str, Any]:
        """
        Публичное переключение паузы из интерактивного UI.

        Returns:
            Снимок текущего статуса.
        """
        self._toggle_pause()
        return self.get_status()

    def _begin_stop_operation(self) -> None:
        """Запустить остановку записи в фоне."""
        self._stop_operation_in_progress = True
        self._update_ui_state("stopping")
        self.status_bar.showMessage("Финализация записи...", 0)

        self._stop_operation_thread = threading.Thread(
            target=self._stop_recording_worker,
            daemon=True,
        )
        self._stop_operation_thread.start()

    def _stop_recording_worker(self) -> None:
        """Фоновый worker остановки записи."""
        output_path = self._recording_controller.stop_recording()
        error_message = (
            None if output_path is not None else "Не удалось сохранить запись"
        )
        self.stop_operation_finished.emit(output_path, error_message)

    def _cancel_stop_operation(self) -> None:
        """Запросить отмену долгой остановки записи."""
        if not self._stop_operation_in_progress:
            return

        if self._recording_controller.request_stop_cancellation():
            self.status_label.setText("Отмена остановки...")
            self.status_bar.showMessage(
                "Запрошена отмена остановки записи",
                5000,
            )
            self.stop_btn.setEnabled(False)
            return

        self.status_bar.showMessage(
            "Остановка ещё не дошла до стадии, которую можно отменить",
            5000,
        )

    def _on_stop_operation_finished(
        self,
        output_path: Path | None,
        error_message: str | None,
    ) -> None:
        """Завершить UI-часть операции остановки записи."""
        self._stop_operation_in_progress = False
        self._stop_operation_thread = None
        self.stop_btn.setText("Стоп")

        if output_path is not None:
            self._on_recording_stopped(output_path)
            return

        self._update_ui_state("idle")
        self._recording_indicator.hide_indicator()
        self.status_bar.showMessage(
            error_message or "Остановка записи не завершена",
            5000,
        )

    # === Обработчики событий записи ===

    def _on_recording_started(
        self,
        output_path: Path,
        capture: CaptureSettings | None = None,
    ) -> None:
        """Обработка запуска записи."""
        self._set_status_updates_enabled(True)
        self._update_ui_state("recording")
        if capture is not None:
            self._recording_indicator.show_for_capture(capture)

        self.recording_started.emit(str(output_path))
        logger.info(f"Запись запущена: {output_path}")

    def _on_recording_stopped(self, output_path: Path) -> None:
        """Обработка остановки записи."""
        self._set_status_updates_enabled(False)
        self._update_ui_state("idle")
        self._recording_indicator.hide_indicator()

        # Добавление в список последних записей
        if output_path.exists():
            size = output_path.stat().st_size
            self._settings_controller.add_recent_recording(output_path, size)
            self._refresh_recent_recordings()

        self.recording_stopped.emit(str(output_path))
        logger.info(f"Запись остановлена: {output_path}")

    def _on_recording_paused(self) -> None:
        """Обработка приостановки записи."""
        self._set_status_updates_enabled(False)
        self._update_ui_state("paused")
        self._recording_indicator.set_paused(True)

        self.recording_paused.emit()

    def _on_recording_resumed(self) -> None:
        """Обработка возобновления записи."""
        self._set_status_updates_enabled(True)
        self._update_ui_state("recording")
        self._recording_indicator.set_paused(False)

        self.recording_resumed.emit()

    def _update_status(self) -> None:
        """Обновление отображения статуса."""
        if self._state.is_recording():
            elapsed = self._recording_controller.elapsed_time
            self.time_label.setText(format_time(elapsed))

    def _set_status_updates_enabled(self, enabled: bool) -> None:
        """
        Включить или выключить обновление времени записи.

        Args:
            enabled: Нужно ли держать timer активным.
        """
        if enabled:
            self._update_timer.start(_STATUS_UPDATE_INTERVAL_MS)
            return

        self._update_timer.stop()

    def _update_ui_state(self, state: str) -> None:
        """
        Централизованно обновить состояние recording UI controls.

        Args:
            state: Один из `idle`, `recording`, `paused`, `stopping`.
        """
        state_config = {
            "idle": {
                "start_enabled": True,
                "stop_enabled": False,
                "pause_enabled": False,
                "pause_text": "Пауза",
                "stop_text": "Стоп",
                "status_text": "Готов",
                "status_style": "",
                "time_text": "00:00",
            },
            "recording": {
                "start_enabled": False,
                "stop_enabled": True,
                "pause_enabled": True,
                "pause_text": "Пауза",
                "stop_text": "Стоп",
                "status_text": "Запись",
                "status_style": Theme.status_style("danger"),
                "time_text": None,
            },
            "paused": {
                "start_enabled": False,
                "stop_enabled": True,
                "pause_enabled": True,
                "pause_text": "Продолжить",
                "stop_text": "Стоп",
                "status_text": "Пауза",
                "status_style": Theme.status_style("warning"),
                "time_text": None,
            },
            "stopping": {
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
        config = state_config.get(state, state_config["idle"])

        start_enabled = bool(config["start_enabled"])
        stop_enabled = bool(config["stop_enabled"])
        pause_enabled = bool(config["pause_enabled"])
        pause_text = str(config["pause_text"])
        stop_text = str(config["stop_text"])
        status_text = str(config["status_text"])
        status_style = str(config["status_style"])
        time_text = config["time_text"]

        self.start_btn.setEnabled(start_enabled)
        self.stop_btn.setEnabled(stop_enabled)
        self.pause_btn.setEnabled(pause_enabled)
        self.pause_btn.setText(pause_text)
        self.stop_btn.setText(stop_text)
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(status_style)

        if time_text is not None:
            self.time_label.setText(str(time_text))

    def _get_api_control_handler(
        self,
        control_name: str,
    ) -> Callable[..., Any] | None:
        """Возвращает API-обработчик из публичного фасада приложения."""
        application_facade = self._application_facade
        if application_facade is None:
            return None

        handler_map: dict[str, Callable[..., Any]] = {
            "get_status": application_facade.get_api_status,
            "apply_settings": application_facade.apply_api_settings,
            "start": lambda: application_facade.start_api_server(force=True),
            "stop": application_facade.stop_api_server,
            "restart": application_facade.restart_api_server,
            "open_logs": application_facade.open_api_logs_folder,
        }
        return handler_map.get(control_name)

    def _invoke_api_control(
        self,
        control_name: str,
        *args: Any,
    ) -> dict[str, Any] | None:
        """Вызов обработчика API из главного приложения."""
        handler = self._get_api_control_handler(control_name)
        if handler is None:
            return None

        try:
            result = handler(*args)
        except Exception as e:
            logger.error(f"Ошибка вызова API control '{control_name}': {e}")
            self._show_non_modal_error(str(e))
            return None

        if isinstance(result, dict):
            return result
        return {"success": True, "data": result}

    def _refresh_api_status(self) -> None:
        """Обновление статуса API на вкладке."""
        if not hasattr(self, "_api_settings_view"):
            return

        status = self._invoke_api_control("get_status")
        if status is None:
            api_running = False
            if self._application_facade is not None:
                try:
                    api_running = bool(
                        self._application_facade.get_api_status().get(
                            "running", False
                        )
                    )
                except Exception:
                    api_running = False
            message = "Сервер запущен" if api_running else "Сервер остановлен"
            self._api_settings_view.set_status(api_running, message)
            return

        configured = status.get("configured", {})
        port = configured.get("port", status.get("port", 5000))
        token = configured.get("api_key", "")
        if not self._api_settings_view.is_editing_settings():
            self._api_settings_view.set_settings(
                port=int(port),
                token=token or "",
            )

        running = bool(status.get("running", False))
        if running:
            message = f"Запущен: {status.get('url', 'http://127.0.0.1')}"
        else:
            message = "Сервер остановлен"
        self._api_settings_view.set_status(running, message)

    def refresh_api_status_view(self) -> None:
        """Публичное обновление API статуса для runtime-слоя."""
        self._refresh_api_status()

    def _on_api_settings_apply(self, port: int, token: str) -> None:
        """Сохранение настроек API из вкладки."""
        result = self._invoke_api_control(
            "apply_settings", {"port": port, "token": token}
        )
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            message = "Настройки API сохранены"
            if result.get("restart_required"):
                message += ". Нужен перезапуск API сервера"
            self.status_bar.showMessage(message, 5000)
            self._refresh_api_status()
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось сохранить настройки API")
        )

    def _on_api_start(self) -> None:
        """Запуск API сервера из вкладки."""
        result = self._invoke_api_control("start")
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            self.status_bar.showMessage("API сервер запущен", 5000)
            self._refresh_api_status()
            self._start_websocket_after_api(result)
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось запустить API сервер")
        )

    def _start_websocket_after_api(self, api_result: dict) -> None:
        """Запуск WebSocket клиента после старта API."""
        configured = api_result.get("configured", {})
        url = api_result.get("url", "")
        token = configured.get("api_key", "")

        if url and token:
            if not self._ws_controller:
                self.init_websocket_client(url, token)
            self.connect_websocket()

    def _on_api_stop(self) -> None:
        """Остановка API сервера из вкладки."""
        result = self._invoke_api_control("stop")
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            self.disconnect_websocket()
            self.status_bar.showMessage("API сервер остановлен", 5000)
            self._refresh_api_status()
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось остановить API сервер")
        )

    def _on_api_restart(self) -> None:
        """Перезапуск API сервера из вкладки."""
        result = self._invoke_api_control("restart")
        if result is None:
            self._show_non_modal_error("Управление API недоступно")
            return
        if result.get("success"):
            self.disconnect_websocket()
            self.status_bar.showMessage("API сервер перезапущен", 5000)
            self._refresh_api_status()
            self._start_websocket_after_api(result)
            return
        self._show_non_modal_error(
            result.get("error", "Не удалось перезапустить API сервер")
        )

    # === WebSocket клиент ===

    def init_websocket_client(self, base_url: str, api_token: str) -> None:
        """
        Инициализация WebSocket-клиента.

        Args:
            base_url: Базовый URL API (http://host:port)
            api_token: API токен для аутентификации
        """
        ws_url = base_url.replace("http://", "ws://").replace(
            "https://", "wss://"
        )
        ws_url = f"{ws_url}/ws"

        self._ws_controller = WebSocketClientController(
            base_url=ws_url, api_token=api_token, parent=self
        )
        self._ws_controller.status_changed.connect(self._on_ws_status_changed)
        self._ws_controller.event_received.connect(self._on_ws_event_received)
        self._ws_controller.error_occurred.connect(self._on_ws_error)
        logger.info("WebSocket клиент инициализирован: %s", ws_url)

    def connect_websocket(self) -> None:
        """Подключение WebSocket-клиента к серверу."""
        if self._ws_controller:
            self._ws_controller.connect()

    def disconnect_websocket(self) -> None:
        """Отключение WebSocket-клиента."""
        if self._ws_controller:
            self._ws_controller.disconnect()

    def _on_ws_status_changed(self, status: str) -> None:
        """Обработка изменения статуса WebSocket."""
        status_map = {
            "connected": ("WS: ●", "#22c55e", "Подключено"),
            "connecting": ("WS: ◐", "#f59e0b", "Подключение..."),
            "disconnected": ("WS: ○", "#6b7280", "Отключено"),
            "reconnecting": (
                "WS: ◐",
                "#f59e0b",
                "Переподключение...",
            ),
            "error": ("WS: ✗", "#ef4444", "Ошибка"),
        }
        text, color, tooltip = status_map.get(
            status, ("WS: ?", "#6b7280", "Неизвестно")
        )
        self._ws_status_label.setText(text)
        tone = "muted"
        if color == "green":
            tone = "success"
        elif color == "orange":
            tone = "warning"
        elif color == "red":
            tone = "danger"
        self._ws_status_label.setStyleSheet(Theme.status_style(tone))
        self._ws_status_label.setToolTip(tooltip)

    def _on_ws_event_received(self, event_type: str, payload: dict) -> None:
        """Обработка полученного через WebSocket события."""
        logger.debug("WebSocket событие: %s, payload: %s", event_type, payload)

        if event_type == "recording.started":
            self.recording_started.emit(payload.get("output_path", ""))
        elif event_type == "recording.stopped":
            self.recording_stopped.emit(payload.get("output_path", ""))
        elif event_type == "recording.paused":
            self.recording_paused.emit()
        elif event_type == "recording.resumed":
            self.recording_resumed.emit()
        elif event_type == "recording.error":
            error_msg = payload.get("error", "Неизвестная ошибка")
            self.error_occurred.emit(error_msg)

    def _on_ws_error(self, message: str) -> None:
        """Обработка ошибки WebSocket."""
        logger.warning("WebSocket ошибка: %s", message)

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

    def _open_latest_recording(self) -> None:
        """Открытие самой свежей записи из списка."""
        item = self.recordings_list.item(0)
        if item:
            self._open_recording(item)

    def _clear_recent_recordings(self) -> None:
        """Очистка списка последних записей."""
        self._settings_controller.clear_recent_recordings()
        self._refresh_recent_recordings()
        self.status_bar.showMessage("Список последних записей очищен", 5000)

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

    def _show_non_modal_error(
        self,
        message: str,
        duration_ms: int = 10000,
    ) -> None:
        """
        Показ ошибки без обязательного modal dialog.

        Args:
            message: Текст ошибки.
            duration_ms: Длительность сообщения в status bar.
        """
        self.status_label.setText("Ошибка")
        self.status_label.setStyleSheet(Theme.status_style("danger"))
        self.status_bar.showMessage(message, duration_ms)
        self.error_occurred.emit(message)

    def _check_dependencies(self) -> None:
        """Проверка необходимых зависимостей."""
        threading.Thread(
            target=self._check_dependencies_worker,
            daemon=True,
        ).start()

    def _check_dependencies_worker(self) -> None:
        """Выполнить проверку зависимостей в фоне."""
        try:
            result = check_ffmpeg()
            self.dependency_check_completed.emit(result, None)
        except Exception as error:
            self.dependency_check_completed.emit(None, str(error))

    def _on_dependency_check_completed(
        self,
        result: object,
        error: object,
    ) -> None:
        """Применить результат фоновой проверки зависимостей."""
        if error is not None:
            logger.error("Ошибка проверки зависимостей: %s", error)
            return

        if not isinstance(result, tuple) or not result:
            return

        ffmpeg_available = bool(result[0])
        if not ffmpeg_available:
            self.status_label.setText("Требует внимания")
            self.status_label.setStyleSheet(Theme.status_style("warning"))
            self.status_bar.showMessage(
                "FFmpeg не найден. Проверьте readiness center "
                "или откройте диагностику.",
                12000,
            )
            self._refresh_readiness_summary()

    def _get_default_geometry(self):
        """Возвращает геометрию по умолчанию при отсутствии экрана."""
        from PyQt6.QtCore import QRect

        return QRect(0, 0, 1920, 1080)

    def showEvent(self, event: Any) -> None:
        """Возобновить timer времени записи при показе окна."""
        if self._state.is_recording():
            self._set_status_updates_enabled(True)
        try:
            super().showEvent(event)
        except AttributeError:
            return

    def hideEvent(self, event: Any) -> None:
        """Остановить timer времени записи, когда окно скрыто."""
        self._set_status_updates_enabled(False)
        try:
            super().hideEvent(event)
        except AttributeError:
            return

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
            api_running = False
            if self._application_facade is not None:
                try:
                    api_running = bool(
                        self._application_facade.get_api_status().get(
                            "running", False
                        )
                    )
                except Exception:
                    api_running = False

            capture = self._build_capture_settings_from_views()
            audio = self._build_audio_settings_from_state()
            output_path = self._settings_controller.get_output_path()
            readiness_snapshot = self._resolve_cached_readiness_snapshot(
                capture,
                audio,
                output_path,
            )

            logger.info(f"api_running: {api_running}")
            self._diagnostics_view.run_checks(
                api_enabled=api_running,
                output_path=output_path,
                capture=capture,
                audio=audio,
                snapshot=readiness_snapshot,
            )
            logger.info("Диагностика завершена")
        except Exception as e:
            logger.error(f"Ошибка диагностики: {e}")

    def _resolve_cached_readiness_snapshot(
        self,
        capture: CaptureSettings | None,
        audio: AudioSettings,
        output_path: Path,
    ) -> ReadinessSnapshot | None:
        """Вернуть последний readiness snapshot, если он ещё актуален."""
        latest_inputs = self._latest_readiness_inputs
        if latest_inputs is None or self._latest_readiness_snapshot is None:
            return None

        if (
            latest_inputs.get("capture") == capture
            and latest_inputs.get("audio") == audio
            and latest_inputs.get("output_path") == output_path
        ):
            return self._latest_readiness_snapshot
        return None

    def _on_diagnostics_fix(self, check_name: str) -> None:
        """Обработка нажатия кнопки исправления."""
        self._handle_readiness_action(check_name)

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
            output_path = self._resolve_requested_output_path(
                params.get("output_path"),
                video_settings.format,
            )
            readiness = self._readiness_service.evaluate(
                capture=capture,
                audio=audio_settings,
                output_path=output_path,
            )
            if not readiness.is_ready:
                return {
                    "success": False,
                    "error": readiness.summary_text(),
                    "details": [issue.message for issue in readiness.issues],
                }

            # Запуск записи
            success, error_msg = self._recording_controller.start_recording(
                output_path=output_path,
                capture=capture,
                audio=audio_settings,
                video=video_settings,
            )

            if success:
                self._on_recording_started(output_path, capture)
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

    def _resolve_requested_output_path(
        self,
        requested_output_path: Any,
        output_format: str,
    ) -> Path:
        """Преобразование output_path из API в конечный путь файла."""
        if requested_output_path is None:
            return Path(str(self._settings_controller.get_output_path()))

        raw_path = str(requested_output_path).strip()
        if not raw_path:
            return Path(str(self._settings_controller.get_output_path()))

        candidate = Path(raw_path)
        is_dir_hint = raw_path.endswith(("/", "\\"))
        if is_dir_hint or (candidate.exists() and candidate.is_dir()):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            extension = output_format.lstrip(".")
            return Path(candidate, f"recording_{timestamp}.{extension}")

        if candidate.suffix:
            return Path(str(candidate))

        extension = output_format.lstrip(".")
        return Path(str(candidate.with_suffix(f".{extension}")))

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
        return cast(list[Any], config.settings.recent_recordings)
