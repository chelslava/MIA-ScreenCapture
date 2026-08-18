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
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from config import get_config
from core.event_bus import RecordingEvent, RecordingEventType
from core.readiness import (
    ReadinessSnapshot,
    RecordingReadinessService,
    build_readiness_checks,
)
from core.recording_types import AudioMode, CaptureMode
from gui.controllers.desktop_actions_controller import DesktopActionsController
from gui.controllers.profile_gui_controller import ProfileGUIController
from gui.controllers.readiness_controller import ReadinessController
from gui.controllers.recording_controller import RecordingController
from gui.controllers.recordings_controller import RecordingsController
from gui.controllers.settings_controller import SettingsController
from gui.controllers.status_bar_controller import StatusBarController
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
    RecordingStatus,
    VideoSettings,
)
from gui.styles.theme import Theme, apply_theme
from gui.views.appearance_view import AppearanceView
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.finalization_progress_dialog import (
    FinalizationProgressDialog,
)
from gui.views.output_view import OutputView
from gui.views.post_processing_view import PostProcessingView
from gui.views.readiness_center_view import ReadinessCenterView
from gui.views.recording_indicator import RecordingIndicatorOverlay
from gui.views.video_view import VideoView
from logger_config import get_module_logger, open_logs_folder
from recorder.utils import (
    FFmpegStatus,
    format_filesize,
    format_time,
    generate_thumbnail,
)

logger = get_module_logger(__name__)
_STATUS_UPDATE_INTERVAL_MS = 100
_SIDEBAR_DEFAULT_WIDTH = 110
_SIDEBAR_COLLAPSED_WIDTH = 44
_SIDEBAR_TEXT_VISIBLE_THRESHOLD = 70
_SIDEBAR_ICONS_DIR = Path(__file__).resolve().parent / "assets" / "icons"

if TYPE_CHECKING:
    from core.application_facade import ApplicationFacade


class _ThreadTracker:
    def __init__(self) -> None:
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()

    def track(self, thread: threading.Thread) -> threading.Thread:
        with self._lock:
            self._threads = [t for t in self._threads if t.is_alive()]
            self._threads.append(thread)
        return thread

    def join_all(self, timeout: float = 5.0) -> None:
        with self._lock:
            threads = list(self._threads)
        for t in threads:
            if t.is_alive():
                t.join(timeout=timeout)
                if t.is_alive():
                    logger.warning(
                        "Поток не завершился за timeout: %s", t.name
                    )
        with self._lock:
            self._threads = [t for t in self._threads if t.is_alive()]


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

    def __init__(self, headless: bool = False, event_bus: Any | None = None):
        """Инициализация главного окна."""
        super().__init__()

        self._headless = headless
        self._application_facade: ApplicationFacade | None = None
        self._stop_operation_thread: threading.Thread | None = None
        self._stop_operation_in_progress = False
        self._thread_tracker = _ThreadTracker()

        # Таймер для toast уведомлений
        self._toast_timer = QTimer()
        self._toast_timer.timeout.connect(self._hide_toast)
        self._event_bus = event_bus

        # Инициализация модели и контроллеров
        self._state = RecordingState()
        self._recording_controller = RecordingController(
            self._state, event_bus=event_bus
        )
        self._recording_controller.set_error_callback(
            self._show_non_modal_error
        )
        self._settings_controller = SettingsController(
            self._state, get_config()
        )
        self._readiness_service = RecordingReadinessService()
        self._readiness_controller = ReadinessController(
            self._readiness_service,
            track_thread=self._thread_tracker.track,
        )
        self._desktop_actions = DesktopActionRegistry()
        self._desktop_actions_controller = DesktopActionsController(
            self._desktop_actions
        )
        self._registered_shortcuts = (
            self._desktop_actions_controller.registered_shortcuts
        )
        self._tab_navigation_order = (
            self._desktop_actions_controller.tab_navigation_order
        )
        self._profile_gui_controller = ProfileGUIController()
        self._ws_controller: WebSocketClientController | None = None
        self._recording_indicator = RecordingIndicatorOverlay()
        # Диалог прогресса финализации создаётся лениво,
        # чтобы не требовать QApplication слишком рано
        self._finalization_dialog: FinalizationProgressDialog | None = None
        self._readiness_request_id = 0
        self._latest_readiness_snapshot: ReadinessSnapshot | None = None
        self._latest_readiness_inputs: dict[str, object] | None = None

        # Таймер обновления статуса
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)

        # Настройка окна
        self._setup_window()
        self._setup_ui()
        self._recordings_controller = RecordingsController(
            state=self._state,
            settings_controller=self._settings_controller,
            recordings_list=self.recordings_list,
            filter_input=self._recordings_filter_input,
            status_bar=self.status_bar,
            track_thread=self._thread_tracker.track,
        )
        self._status_bar_controller = StatusBarController(
            start_btn=self.start_btn,
            stop_btn=self.stop_btn,
            pause_btn=self.pause_btn,
            status_label=self.status_label,
            time_label=self.time_label,
        )
        self._setup_desktop_actions()
        self._connect_signals()

        # Загрузка настроек
        self._settings_controller.load_settings()
        self._apply_settings_to_views()
        self._refresh_api_status()

        # Проверка зависимостей
        self._check_dependencies()
        self._refresh_readiness_summary()

        # Инициализация профилей
        self._init_profiles()

        logger.info("Главное окно инициализировано")

    def _setup_window(self) -> None:
        """Настройка свойств окна."""
        self.setWindowTitle("MIA-ScreenCapture")
        self.setMinimumSize(900, 650)
        self.resize(1000, 750)

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
        self._sidebar_expanded_width = _SIDEBAR_DEFAULT_WIDTH

        # Боковая панель навигации + содержимое — в QSplitter, чтобы дать
        # пользователю drag-resize handle (раньше был обычный QHBoxLayout
        # без какой-либо возможности менять ширину сайдбара).
        self._sidebar_splitter = QSplitter(Qt.Orientation.Horizontal)
        self._sidebar_splitter.setChildrenCollapsible(False)
        self.setCentralWidget(self._sidebar_splitter)

        sidebar_container = QWidget()
        sidebar_layout = QVBoxLayout(sidebar_container)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        self._sidebar_toggle_btn = QPushButton("◂")
        self._sidebar_toggle_btn.setFixedHeight(20)
        self._sidebar_toggle_btn.setToolTip(
            "Свернуть/развернуть боковую панель"
        )
        self._sidebar_toggle_btn.clicked.connect(
            self._on_sidebar_toggle_clicked
        )
        sidebar_layout.addWidget(self._sidebar_toggle_btn)

        self._sidebar = QListWidget()
        self._sidebar.setIconSize(QSize(20, 20))
        self._sidebar.itemSelectionChanged.connect(
            self._on_sidebar_selection_changed
        )
        sidebar_layout.addWidget(self._sidebar)

        self._sidebar_splitter.addWidget(sidebar_container)

        # Содержимое (stacked widget)
        self._content_stack = QStackedWidget()
        self._sidebar_splitter.addWidget(self._content_stack)
        self._sidebar_splitter.setStretchFactor(0, 0)
        self._sidebar_splitter.setStretchFactor(1, 1)
        self._sidebar_splitter.splitterMoved.connect(
            self._on_sidebar_splitter_moved
        )

        # Добавление страниц в stacked widget
        # 0 - Запись
        recording_tab = self._create_recording_tab()
        self._content_stack.addWidget(recording_tab)
        self._sidebar.addItem(self._make_sidebar_item("record", "Запись"))

        # 1 - Настройки
        settings_tab = self._create_settings_tab()
        self._content_stack.addWidget(settings_tab)
        self._sidebar.addItem(self._make_sidebar_item("settings", "Настройки"))

        # 2 - Планировщик
        from gui.scheduler.scheduler_tab import SchedulerTab

        self.scheduler_tab = SchedulerTab()
        self._content_stack.addWidget(self.scheduler_tab)
        self._sidebar.addItem(
            self._make_sidebar_item("scheduler", "Планировщик")
        )

        # 3 - Диагностика
        from gui.views.diagnostics_view import DiagnosticsView

        self._diagnostics_view = DiagnosticsView()
        self._diagnostics_view.recheck_requested.connect(self._run_diagnostics)
        self._diagnostics_view.fix_requested.connect(self._on_diagnostics_fix)
        self._diagnostics_view.logs_requested.connect(
            lambda: self._desktop_actions.execute(
                DesktopActionId.OPEN_APP_LOGS
            )
        )
        self._content_stack.addWidget(self._diagnostics_view)
        self._sidebar.addItem(
            self._make_sidebar_item("diagnostics", "Диагностика")
        )

        # 4 - API
        from gui.views.api_settings_view import ApiSettingsView

        self._api_settings_view = ApiSettingsView()
        self._content_stack.addWidget(self._api_settings_view)
        self._sidebar.addItem(self._make_sidebar_item("api", "API"))

        # Выбрать первую страницу по умолчанию
        self._sidebar.setCurrentRow(0)
        self._content_stack.setCurrentIndex(0)

        # Для совместимости с тестами - связать tabs с content_stack
        self.tabs = self._content_stack

        # Строка состояния
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Индикатор состояния
        self.status_label = QLabel("Готов")
        self.status_bar.addPermanentWidget(self.status_label)

        # Индикатор WebSocket соединения
        self._ws_status_label = QLabel("● Disconnected")
        self._ws_status_label.setToolTip(
            "Статус WebSocket-соединения с API сервером"
        )
        self._ws_status_label.setStyleSheet(Theme.status_style("danger"))
        self.status_bar.addPermanentWidget(self._ws_status_label)

        self._toast_timer = QTimer()
        self._toast_timer.timeout.connect(self._hide_toast)

        self.time_label = QLabel("00:00")
        self.status_bar.addPermanentWidget(self.time_label)

    def _on_sidebar_selection_changed(self) -> None:
        """Обработчик переключения страниц при клике на боковую панель."""
        current_row = self._sidebar.currentRow()
        if current_row >= 0:
            self._content_stack.setCurrentIndex(current_row)

    def _make_sidebar_item(
        self, icon_name: str, label: str
    ) -> QListWidgetItem:
        """
        Создать пункт сайдбара с PNG-иконкой вместо emoji.

        Args:
            icon_name: Имя файла иконки без расширения (`gui/assets/icons/`).
            label: Текстовая подпись пункта.
        """
        icon_path = _SIDEBAR_ICONS_DIR / f"{icon_name}.png"
        item = QListWidgetItem(QIcon(str(icon_path)), label)
        item.setToolTip(label)
        return item

    def _update_sidebar_text_visibility(self, width: int) -> None:
        """
        Скрыть/показать текстовые подписи пунктов сайдбара по ширине.

        При узкой ширине (свёрнутое состояние или перетаскивание handle
        ниже порога, когда текст всё равно не виден целиком) остаются
        только иконки — полный текст хранится в `toolTip()` и не теряется.

        Args:
            width: Текущая ширина сайдбара в пикселях.
        """
        show_text = width >= _SIDEBAR_TEXT_VISIBLE_THRESHOLD
        for row in range(self._sidebar.count()):
            item = self._sidebar.item(row)
            if item is None:
                continue
            label = item.toolTip()
            if not label:
                continue
            item.setText(label if show_text else "")

    def _apply_sidebar_width(self, width: int) -> None:
        """
        Применить ширину боковой панели к splitter (без сохранения).

        Args:
            width: Желаемая ширина сайдбара в пикселях.
        """
        width = max(width, _SIDEBAR_COLLAPSED_WIDTH)
        sizes = self._sidebar_splitter.sizes()
        total = sum(sizes) if sizes else width + 400
        self._sidebar_splitter.setSizes([width, max(total - width, 1)])
        if width > _SIDEBAR_COLLAPSED_WIDTH:
            self._sidebar_expanded_width = width
        self._sidebar_toggle_btn.setText(
            "▸" if width <= _SIDEBAR_COLLAPSED_WIDTH else "◂"
        )
        self._update_sidebar_text_visibility(width)

    def _on_sidebar_toggle_clicked(self) -> None:
        """Свернуть боковую панель до минимума или развернуть обратно."""
        sizes = self._sidebar_splitter.sizes()
        current_width = sizes[0] if sizes else _SIDEBAR_DEFAULT_WIDTH
        if current_width <= _SIDEBAR_COLLAPSED_WIDTH:
            target_width = self._sidebar_expanded_width
        else:
            self._sidebar_expanded_width = current_width
            target_width = _SIDEBAR_COLLAPSED_WIDTH
        self._apply_sidebar_width(target_width)
        self._settings_controller.set_sidebar_width(target_width)

    def _on_sidebar_splitter_moved(self, _pos: int, _index: int) -> None:
        """
        Реакция на ручное перетаскивание handle сайдбара.

        Скрывает текстовые подписи, когда пользователь утягивает handle
        ниже порога читаемости (а не только при клике на кнопку
        сворачивания), и сохраняет итоговую ширину в конфигурации.
        """
        sizes = self._sidebar_splitter.sizes()
        if not sizes:
            return
        width = sizes[0]
        if width > _SIDEBAR_COLLAPSED_WIDTH:
            self._sidebar_expanded_width = width
        self._update_sidebar_text_visibility(width)
        self._settings_controller.set_sidebar_width(width)

    @property
    def tabs(self) -> QStackedWidget | None:
        """Совместимость с тестами - возвращает content_stack."""
        if not hasattr(self, "_content_stack"):
            return None
        return self._content_stack

    @tabs.setter
    def tabs(self, value: QStackedWidget) -> None:
        """Совместимость с тестами - устанавливает content_stack."""
        self._content_stack = value

    def _create_recording_tab(self) -> QWidget:
        """Создание вкладки записи (минимум - только для быстрого старта)."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Левая панель - Только область захвата и кнопки
        left_panel = self._create_quick_start_panel()
        layout.addWidget(left_panel, stretch=2)

        # Правая панель - Последние записи
        right_panel = self._create_right_panel()
        layout.addWidget(right_panel, stretch=1)

        return widget

    def _create_quick_start_panel(self) -> QWidget:
        """Создание панели быстрого старта (только захват + кнопки)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Только область захвата
        self._capture_view = CaptureView()
        layout.addWidget(self._capture_view)

        # Селектор профилей записи
        profile_layout = QHBoxLayout()
        profile_layout.setSpacing(4)
        profile_label = QLabel("Профиль:")
        profile_label.setStyleSheet("font-weight: bold;")
        self._profile_combo = QComboBox()
        self._profile_combo.currentIndexChanged.connect(
            self._on_profile_combo_changed
        )
        self._profile_manage_btn = QPushButton("⚙️ Профили...")
        self._profile_manage_btn.clicked.connect(self._open_profile_dialog)
        profile_layout.addWidget(profile_label)
        profile_layout.addWidget(self._profile_combo, stretch=1)
        profile_layout.addWidget(self._profile_manage_btn)
        layout.addLayout(profile_layout)

        # Статус готовности (компактно)
        self._readiness_center_view = ReadinessCenterView()
        layout.addWidget(self._readiness_center_view, stretch=0)

        # Кнопки управления
        buttons_layout = self._create_control_buttons()
        layout.addLayout(buttons_layout)

        layout.addStretch()
        return widget

    def _create_settings_tab(self) -> QWidget:
        """Создание вкладки настроек (аудио, видео, вывод)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

        # Аудио настройки
        self._audio_view = AudioView()
        layout.addWidget(self._audio_view)

        # Видео настройки
        self._video_view = VideoView()
        layout.addWidget(self._video_view)

        # Путь вывода
        self._output_view = OutputView()
        layout.addWidget(self._output_view)

        # Внешний вид (тема)
        self._appearance_view = AppearanceView()
        layout.addWidget(self._appearance_view)

        # Постобработка (#118)
        self._post_processing_view = PostProcessingView()
        self._post_processing_view.settings_changed.connect(
            self._on_post_processing_changed
        )
        layout.addWidget(self._post_processing_view)

        layout.addStretch()
        return widget

    def _create_left_panel(self) -> QWidget:
        """Создание левой панели (устаревший метод - не используется)."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(6)

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
        layout.addWidget(self._readiness_center_view, stretch=0)

        # Кнопки управления
        buttons_layout = self._create_control_buttons()
        layout.addLayout(buttons_layout)

        return widget

    def _create_control_buttons(self) -> QHBoxLayout:
        """Создание кнопок управления."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.start_btn = QPushButton("Начать запись")
        self.start_btn.setMinimumHeight(32)
        self.start_btn.setAccessibleName("Начать запись")
        layout.addWidget(self.start_btn)

        self.pause_btn = QPushButton("Пауза")
        self.pause_btn.setMinimumHeight(32)
        self.pause_btn.setEnabled(False)
        self.pause_btn.setAccessibleName("Пауза / Продолжить запись")
        layout.addWidget(self.pause_btn)

        self.stop_btn = QPushButton("Стоп")
        self.stop_btn.setMinimumHeight(32)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setAccessibleName("Остановить запись")
        layout.addWidget(self.stop_btn)

        return layout

    def _create_right_panel(self) -> QWidget:
        """Создание правой панели с последними записями."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        from PyQt6.QtWidgets import QGroupBox

        group = QGroupBox("Последние записи")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(4, 4, 4, 4)
        group_layout.setSpacing(4)

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
        self.recordings_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.recordings_list.customContextMenuRequested.connect(
            self._show_recordings_context_menu
        )
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

        # Сигналы AppearanceView
        self._appearance_view.theme_changed.connect(self._on_theme_changed)
        self._appearance_view.hotkeys_requested.connect(
            self._show_hotkeys_view
        )
        self._appearance_view.minimize_to_tray_changed.connect(
            self._on_minimize_to_tray_changed
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

        self._ws_controller = WebSocketClientController(
            base_url="ws://localhost:5000/ws"
        )
        self._ws_controller.status_changed.connect(self._update_ws_status)
        self._ws_controller.connected.connect(
            lambda: self._show_toast("WebSocket подключён")
        )
        self._ws_controller.disconnected.connect(
            lambda: self._show_toast("WebSocket отключён")
        )
        self._ws_controller.error_occurred.connect(
            lambda msg: self._show_toast(f"WebSocket ошибка: {msg}", 5000)
        )

    def _setup_desktop_actions(self) -> None:
        """Создать action registry, shortcuts и accessibility metadata."""
        callbacks = {
            DesktopActionId.START_RECORDING: self._start_recording,
            DesktopActionId.TOGGLE_PAUSE: self._toggle_pause,
            DesktopActionId.STOP_RECORDING: self._stop_recording,
            DesktopActionId.OPEN_LATEST_RECORDING: self._open_latest_recording,
            DesktopActionId.OPEN_RECORDING_FOLDER: self._open_recording_folder,
            DesktopActionId.SHOW_RECORDING_TAB: lambda: (
                self._sidebar.setCurrentRow(0)
                if hasattr(self, "_sidebar")
                else None
            ),
            DesktopActionId.SHOW_SCHEDULER_TAB: lambda: (
                self._sidebar.setCurrentRow(2)
                if hasattr(self, "_sidebar")
                else None
            ),
            DesktopActionId.SHOW_DIAGNOSTICS_TAB: lambda: (
                self._sidebar.setCurrentRow(3)
                if hasattr(self, "_sidebar")
                else None
            ),
            DesktopActionId.SHOW_API_TAB: lambda: (
                self._sidebar.setCurrentRow(4)
                if hasattr(self, "_sidebar")
                else None
            ),
            DesktopActionId.OPEN_APP_LOGS: self._open_application_logs,
        }
        enabled_conditions = {
            DesktopActionId.START_RECORDING: lambda: (
                not self._state.is_recording()
            ),
            DesktopActionId.TOGGLE_PAUSE: lambda: (
                self._state.is_recording() or self._state.is_paused()
            ),
            DesktopActionId.STOP_RECORDING: lambda: (
                self._state.is_recording() or self._state.is_paused()
            ),
        }
        if hasattr(self, "_desktop_actions_controller"):
            self._desktop_actions_controller.registry = self._desktop_actions
            self._desktop_actions_controller.register_default_actions(
                callbacks=callbacks,
                enabled_conditions=enabled_conditions,
            )
        else:
            for action_id, spec in [
                (
                    DesktopActionId.START_RECORDING,
                    get_desktop_action_spec(DesktopActionId.START_RECORDING),
                ),
                (
                    DesktopActionId.TOGGLE_PAUSE,
                    get_desktop_action_spec(DesktopActionId.TOGGLE_PAUSE),
                ),
                (
                    DesktopActionId.STOP_RECORDING,
                    get_desktop_action_spec(DesktopActionId.STOP_RECORDING),
                ),
                (
                    DesktopActionId.OPEN_LATEST_RECORDING,
                    get_desktop_action_spec(
                        DesktopActionId.OPEN_LATEST_RECORDING
                    ),
                ),
                (
                    DesktopActionId.OPEN_RECORDING_FOLDER,
                    get_desktop_action_spec(
                        DesktopActionId.OPEN_RECORDING_FOLDER
                    ),
                ),
                (
                    DesktopActionId.SHOW_RECORDING_TAB,
                    get_desktop_action_spec(
                        DesktopActionId.SHOW_RECORDING_TAB
                    ),
                ),
                (
                    DesktopActionId.SHOW_SCHEDULER_TAB,
                    get_desktop_action_spec(
                        DesktopActionId.SHOW_SCHEDULER_TAB
                    ),
                ),
                (
                    DesktopActionId.SHOW_DIAGNOSTICS_TAB,
                    get_desktop_action_spec(
                        DesktopActionId.SHOW_DIAGNOSTICS_TAB
                    ),
                ),
                (
                    DesktopActionId.SHOW_API_TAB,
                    get_desktop_action_spec(DesktopActionId.SHOW_API_TAB),
                ),
                (
                    DesktopActionId.OPEN_APP_LOGS,
                    get_desktop_action_spec(DesktopActionId.OPEN_APP_LOGS),
                ),
            ]:
                self._desktop_actions.register(
                    DesktopAction(
                        action_id=action_id,
                        title=spec.title,
                        description=spec.description,
                        callback=callbacks[action_id],
                        shortcut=spec.shortcut,
                        enabled_when=enabled_conditions.get(action_id),
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

        if hasattr(self, "_sidebar"):
            self._apply_accessible_metadata(
                self._sidebar,
                "Боковая панель навигации",
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
        DesktopActionsController.apply_accessible_metadata(
            widget, accessible_name, accessible_description
        )

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
        if hasattr(self, "_desktop_actions_controller"):
            self._desktop_actions_controller.configure_tab_order(
                self, tab_order
            )
        else:
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
        alt_shortcuts: list[tuple[str, Any]] = [
            ("Alt+R", self.start_btn),
            ("Alt+S", self.stop_btn),
            ("Alt+P", self.pause_btn),
        ]
        if hasattr(self, "_desktop_actions_controller"):
            self._desktop_actions_controller.register_qt_shortcuts(
                self, alt_shortcuts
            )

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

        # Тема оформления
        self._appearance_view.set_current_mode(
            self._settings_controller.get_theme_mode()
        )

        # Поведение закрытия окна (сворачивание в трей)
        self._appearance_view.set_minimize_to_tray(
            self._settings_controller.get_minimize_to_tray()
        )

        # Ширина боковой панели
        self._apply_sidebar_width(
            self._settings_controller.get_sidebar_width()
        )

        # Настройки постобработки (#118)
        if hasattr(self, "_post_processing_view"):
            self._post_processing_view.set_settings(
                get_config().settings.post_processing
            )

        # Недавние записи
        self._refresh_recent_recordings()

    def _on_post_processing_changed(self) -> None:
        """Сохранение настроек постобработки при изменении в UI (#118)."""
        if not hasattr(self, "_post_processing_view"):
            return
        new_settings = self._post_processing_view.get_settings()
        config = get_config()
        config.settings.post_processing = new_settings
        config.save()

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

            thumbnail_path = generate_thumbnail(rec.path)
            if thumbnail_path:
                item.setIcon(QIcon(str(thumbnail_path)))
            else:
                item.setIcon(self._get_recorded_video_icon())

            self.recordings_list.addItem(item)

    def _clear_recordings_filter(self) -> None:
        """Сброс фильтра списка недавних записей."""
        self._recordings_filter_input.setText("")
        self._refresh_recent_recordings()

    def _normalized_recordings_filter(self) -> str:
        """Нормализация текста фильтра для сравнения."""
        return self._recordings_controller.normalized_recordings_filter()

    @staticmethod
    def _recording_matches_filter(
        filename: str, date_text: str, filter_text: str
    ) -> bool:
        """Проверка попадания записи под фильтр."""
        return RecordingsController.recording_matches_filter(
            filename, date_text, filter_text
        )

    # === Обработчики сигналов от представлений ===

    def _on_capture_type_changed(self, capture_type: Any) -> None:
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

    def _on_video_settings_changed(self, settings: Any) -> None:
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

    def _on_theme_changed(self, mode: str) -> None:
        """Обработка выбора темы оформления."""
        self._settings_controller.set_theme_mode(mode)
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            apply_theme(app, mode)

    def _on_minimize_to_tray_changed(self, enabled: bool) -> None:
        """Обработка переключения «сворачивать в трей при закрытии»."""
        self._settings_controller.set_minimize_to_tray(enabled)

    def _show_hotkeys_view(self) -> None:
        """Показать немодальный экран со списком горячих клавиш."""
        if getattr(self, "_hotkeys_view", None) is None:
            from gui.views.hotkeys_view import HotkeysView

            self._hotkeys_view = HotkeysView(
                self._desktop_actions, parent=self
            )
        self._hotkeys_view.show()
        self._hotkeys_view.raise_()
        self._hotkeys_view.activateWindow()

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
        self._readiness_center_view.set_loading_state()

        self._readiness_request_id = (
            self._readiness_controller.request_readiness_refresh(
                capture=capture,
                audio=audio,
                output_path=output_path,
                on_completed=lambda req_id, snap, err, cap, aud: (
                    self.readiness_refresh_completed.emit(
                        req_id, snap, err, cap, aud
                    )
                ),
            )
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
        if not self._readiness_controller.is_request_current(request_id):
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
        self._readiness_controller.store_readiness_result(
            snapshot,
            capture,
            audio,
            self._settings_controller.get_output_path(),
        )
        self._latest_readiness_snapshot = (
            self._readiness_controller.latest_snapshot
        )
        self._latest_readiness_inputs = (
            self._readiness_controller.latest_inputs
        )
        self._readiness_center_view.apply_checks(checks)

    def _show_readiness_details(self) -> None:
        """Открыть вкладку диагностики и запустить подробную проверку."""
        if hasattr(self, "_sidebar") and hasattr(self, "_diagnostics_view"):
            self._sidebar.setCurrentRow(3)
        self._run_diagnostics()

    def _update_ws_status(self, status: str) -> None:
        label_labels = {
            "disconnected": ("● Disconnected", "danger"),
            "connecting": ("● Connecting...", "warning"),
            "connected": ("● Connected", "success"),
            "reconnecting": ("◌ Reconnecting...", "warning"),
            "error": ("● Error", "danger"),
        }

        label, color = label_labels.get(status, ("● Disconnected", "danger"))
        self._ws_status_label.setText(label)
        self._ws_status_label.setStyleSheet(Theme.status_style(color))

    def _show_toast(self, message: str, duration_ms: int = 3000) -> None:
        if self._toast_timer.isActive():
            self._toast_timer.stop()

        toast_label = QLabel(message)
        toast_label.setStyleSheet(
            f"background-color: {Theme.color('muted')};"
            f"color: white;"
            f"padding: 8px 16px;"
            f"border-radius: 4px;"
        )
        toast_label.setFixedWidth(300)
        toast_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.status_bar.insertWidget(0, toast_label, 1)

        self._toast_timer.setSingleShot(True)
        self._toast_timer.start(duration_ms)

    def _hide_toast(self) -> None:
        self.status_bar.clearMessage()

    def _subscribe_to_ffmpeg_events(self, event_bus: Any) -> None:
        """Подписаться на события FFmpeg через EventBus."""

        def handler(event: RecordingEvent) -> None:
            if event.event_type not in (
                RecordingEventType.WARNING,
                RecordingEventType.ERROR,
            ):
                return

            payload = event.payload
            event_type = payload.get("type", "")

            if event_type == "ffmpeg_recovery":
                message = payload.get("message", "FFmpeg восстановлен")
                self._show_toast(message, duration_ms=3000)

            elif event_type == "ffmpeg_crash":
                message = payload.get("message", "FFmpeg завершился с ошибкой")
                self._show_toast(message, duration_ms=5000)
                self._show_non_modal_error(message)

        event_bus.subscribe(RecordingEventType.WARNING, handler)
        event_bus.subscribe(RecordingEventType.ERROR, handler)

    def _handle_readiness_action(self, action_key: str) -> None:
        """Выполнить one-click action из readiness center или диагностики."""

        def _refresh_windows_action() -> None:
            if hasattr(self, "_sidebar"):
                self._sidebar.setCurrentRow(0)
            self._capture_view.refresh_windows()

        def _focus_capture_window_action() -> None:
            if hasattr(self, "_sidebar"):
                self._sidebar.setCurrentRow(0)
            self._capture_view.set_capture_type(CaptureMode.WINDOW)
            self._capture_view.focus_window_combo()

        def _refresh_audio_devices_action() -> None:
            if hasattr(self, "_sidebar"):
                self._sidebar.setCurrentRow(1)
            self._audio_view._refresh_audio_devices()

        def _focus_microphone_selection_action() -> None:
            if hasattr(self, "_sidebar"):
                self._sidebar.setCurrentRow(1)
            focus = getattr(self._audio_view._mic_combo, "setFocus", None)
            if callable(focus):
                focus()

        def _switch_to_api_tab() -> None:
            if hasattr(self, "_sidebar"):
                self._sidebar.setCurrentRow(4)

        handlers: dict[str, Callable[[], None]] = {
            "choose_output_path": self._select_output_folder,
            "refresh_windows": _refresh_windows_action,
            "focus_capture_window": _focus_capture_window_action,
            "refresh_audio_devices": _refresh_audio_devices_action,
            "focus_microphone_selection": _focus_microphone_selection_action,
            "API сервер": _switch_to_api_tab,
        }
        self._readiness_controller.handle_readiness_action(
            action_key, handlers
        )

    # === Управление профилями записи ===

    def _init_profiles(self) -> None:
        """Инициализация списка профилей в выпадающем списке."""
        if not hasattr(self, "_profile_combo"):
            return
        self._profile_gui_controller.init_profiles(self._profile_combo)

    def _on_profile_combo_changed(self, index: int) -> None:
        """Обработка выбора профиля в выпадающем списке."""
        if index < 0 or not hasattr(self, "_profile_combo"):
            return
        self._profile_gui_controller.on_profile_combo_changed(
            index, self._profile_combo, self.apply_profile_settings
        )

    def _open_profile_dialog(self) -> None:
        """Открытие диалога управления профилями."""
        if hasattr(self, "_profile_combo"):
            self._profile_gui_controller.open_profile_dialog(
                self, self._profile_combo, self.apply_profile_settings
            )

    def apply_profile_settings(self, profile: Any) -> None:
        """Применяет параметры профиля к активным представлениям и состоянию."""
        self._profile_gui_controller.apply_profile_settings(
            profile,
            video_view=getattr(self, "_video_view", None),
            audio_view=getattr(self, "_audio_view", None),
            capture_view=getattr(self, "_capture_view", None),
            state=getattr(self, "_state", None),
            combo=getattr(self, "_profile_combo", None),
            status_bar=getattr(self, "status_bar", None),
        )

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

    def _apply_readiness_snapshot(self, snapshot: Any) -> bool:
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
        if hasattr(self, "_sidebar") and hasattr(self, "_diagnostics_view"):
            self._sidebar.setCurrentRow(3)
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

    def _get_finalization_dialog(self) -> FinalizationProgressDialog:
        """Получить диалог прогресса финализации (создать при необходимости)."""
        if self._finalization_dialog is None:
            dialog = FinalizationProgressDialog(
                tracker=self._recording_controller.progress_tracker,
                parent=self,
            )
            dialog.cancel_requested.connect(self._cancel_stop_operation)
            self._finalization_dialog = dialog
        return self._finalization_dialog

    def _show_finalization_progress_dialog(self) -> None:
        """Показать диалог прогресса финализации записи."""
        try:
            dialog = self._get_finalization_dialog()
        except Exception as e:
            # Без GUI (например, в тестах) пропускаем диалог
            logger.debug(f"Не удалось создать диалог финализации: {e}")
            return
        dialog.start()

    def _hide_finalization_progress_dialog(self) -> None:
        """Скрыть диалог прогресса финализации записи."""
        dialog = self._finalization_dialog
        if dialog is None:
            return
        try:
            dialog.stop()
        except Exception as e:
            logger.debug(f"Не удалось остановить диалог финализации: {e}")

    def _begin_stop_operation(self) -> None:
        """Запустить остановку записи в фоне."""
        self._stop_operation_in_progress = True
        self._update_ui_state(RecordingStatus.STOPPING)
        self.status_bar.showMessage("Финализация записи...", 0)
        self._show_finalization_progress_dialog()
        self._stop_operation_thread = threading.Thread(
            target=self._stop_recording_worker,
            daemon=True,
        )
        self._thread_tracker.track(self._stop_operation_thread)
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
        self._hide_finalization_progress_dialog()

        if output_path is not None:
            self._on_recording_stopped(output_path)
            return

        self._update_ui_state(RecordingStatus.IDLE)
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
        self._update_ui_state(RecordingStatus.RECORDING)
        if capture is not None:
            self._recording_indicator.show_for_capture(capture)

        self.recording_started.emit(str(output_path))
        logger.info(f"Запись запущена: {output_path}")

    def _on_recording_stopped(self, output_path: Path) -> None:
        """Обработка остановки записи."""
        self._set_status_updates_enabled(False)
        self._update_ui_state(RecordingStatus.IDLE)
        self._recording_indicator.hide_indicator()

        # Добавление в список последних записей
        if output_path.exists():
            size = output_path.stat().st_size
            self._settings_controller.add_recent_recording(output_path, size)
            # Запустить генерацию миниатюры в фоновом потоке
            self._generate_thumbnail_for_recording(output_path)
        self._refresh_recent_recordings()

        self.recording_stopped.emit(str(output_path))
        logger.info(f"Запись остановлена: {output_path}")

    def _generate_thumbnail_for_recording(self, output_path: Path) -> None:
        """Генерировать миниатюру для новой записи в фоновом потоке."""
        self._recordings_controller.generate_thumbnail_for_recording(
            output_path
        )

    def _get_recorded_video_icon(self) -> QIcon:
        """Получить placeholder иконку для записи без миниатюры."""
        return self._recordings_controller.get_recorded_video_icon()

    def _on_recording_paused(self) -> None:
        """Обработка приостановки записи."""
        self._set_status_updates_enabled(False)
        self._update_ui_state(RecordingStatus.PAUSED)
        self._recording_indicator.set_paused(True)

        self.recording_paused.emit()

    def _on_recording_resumed(self) -> None:
        """Обработка возобновления записи."""
        self._set_status_updates_enabled(True)
        self._update_ui_state(RecordingStatus.RECORDING)
        self._recording_indicator.set_paused(False)

        self.recording_resumed.emit()

    def _update_status(self) -> None:
        """Обновление отображения статуса."""
        if self._state.is_recording():
            elapsed = self._recording_controller.elapsed_time
            formatted_time = format_time(elapsed)
            metrics = self._recording_controller.frame_metrics
            actual_fps = float(metrics.get("actual_fps", 0.0))
            jitter_ms = float(metrics.get("jitter_ms", 0.0))
            if actual_fps > 0:
                display_text = f"{formatted_time} (FPS: {actual_fps:.1f} | Jitter: {jitter_ms:.1f}ms)"
            else:
                display_text = formatted_time
            self._status_bar_controller.update_time_display(display_text)

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

    def _update_ui_state(self, status: RecordingStatus) -> None:
        """
        Централизованно обновить состояние recording UI controls.

        Args:
            status: Статус записи из `RecordingStatus`.
        """
        self._status_bar_controller.apply_recording_status(status)

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
            "connected": (
                "● Connected",
                Theme.color("success"),
                "Подключено",
            ),
            "connecting": (
                "● Connecting...",
                Theme.color("warning"),
                "Подключение...",
            ),
            "disconnected": (
                "● Disconnected",
                Theme.color("danger"),
                "Отключено",
            ),
            "reconnecting": (
                "◌ Reconnecting...",
                Theme.color("warning"),
                "Переподключение...",
            ),
            "error": ("● Error", Theme.color("danger"), "Ошибка"),
        }
        text, color, tooltip = status_map.get(
            status, ("● Unknown", Theme.color("muted"), "Неизвестно")
        )
        self._ws_status_label.setText(text)
        self._ws_status_label.setStyleSheet(
            f"color: {color}; font-weight: bold;"
        )
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
            self._open_file(str(path))

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

    def _copy_selected_recording_path(self) -> None:
        """Копирование пути выбранной записи в буфер обмена."""
        item = self.recordings_list.currentItem()
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return

        from PyQt6.QtGui import QGuiApplication

        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(str(path))
        self.status_bar.showMessage(
            "Путь записи скопирован в буфер обмена", 5000
        )

    def _show_recordings_context_menu(self, pos: Any) -> None:
        """Контекстное меню по правому клику на записи в списке."""
        item = self.recordings_list.itemAt(pos)
        if item is None:
            return
        self.recordings_list.setCurrentItem(item)

        menu = QMenu(self)

        open_action = QAction("Открыть файл", menu)
        open_action.triggered.connect(self._open_selected_recording)
        menu.addAction(open_action)

        folder_action = QAction("Открыть папку", menu)
        folder_action.triggered.connect(self._open_recording_folder)
        menu.addAction(folder_action)

        menu.addSeparator()

        copy_action = QAction("Копировать путь", menu)
        copy_action.triggered.connect(self._copy_selected_recording_path)
        menu.addAction(copy_action)

        menu.exec(self.recordings_list.mapToGlobal(pos))

    def _open_file(self, path: str) -> None:
        """Открытие файла с помощью системного приложения по умолчанию."""
        system = platform.system()
        if system == "Windows":
            # os.startfile is Windows-specific and not in type stubs
            os.startfile(path)  # type: ignore[attr-defined, unused-ignore]
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

    def _open_application_logs(self) -> None:
        """Открыть папку логов приложения без modal-диалога."""
        try:
            open_logs_folder()
        except Exception as error:
            logger.error("Не удалось открыть папку логов: %s", error)
            self._show_non_modal_error(
                f"Не удалось открыть папку логов: {error}"
            )
            return
        self.status_bar.showMessage("Открыта папка логов приложения", 5000)

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
        Theme.apply_error_status(
            self.status_label, self.status_bar, message, duration_ms
        )
        self.error_occurred.emit(message)

    def _check_dependencies(self) -> None:
        """Проверка необходимых зависимостей."""
        self._readiness_controller.check_dependencies(
            lambda result, error: self.dependency_check_completed.emit(
                result, error
            )
        )

    def _on_dependency_check_completed(
        self,
        result: object,
        error: object,
    ) -> None:
        """Применить результат фоновой проверки зависимостей."""
        if error is not None:
            logger.error("Ошибка проверки зависимостей: %s", error)
            return

        if not isinstance(result, FFmpegStatus):
            return

        if result.available:
            if result.recommendation:
                logger.warning("FFmpeg: %s", result.recommendation)
                self.status_bar.showMessage(
                    f"FFmpeg: {result.recommendation}",
                    10000,
                )
            else:
                logger.info(
                    "FFmpeg доступен: версия %s, путь %s",
                    result.version,
                    result.path,
                )
            return

        logger.warning(
            "FFmpeg недоступен: %s. Рекомендация: %s",
            result.error,
            result.recommendation,
        )
        self.start_btn.setEnabled(False)
        self.start_btn.setToolTip(
            result.recommendation or result.error or "FFmpeg недоступен"
        )
        self.status_label.setText("Требует внимания")
        self.status_label.setStyleSheet(Theme.status_style("warning"))
        hint = result.recommendation or result.error or "FFmpeg не найден."
        self.status_bar.showMessage(
            f"{hint} Проверьте readiness center или откройте диагностику.",
            12000,
        )
        self._refresh_readiness_summary()

    def _get_default_geometry(self) -> Any:
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

    def closeEvent(self, event: Any) -> None:
        """Обработка события закрытия окна.

        Логика свёртывания в трей и выхода делегирована
        ``VideoRecorderApp._handle_close_requested`` (main.py):
        поведение определяется настройкой ``minimize_to_tray``.
        Во время активной записи здесь показывается расширенный
        диалог выбора действия (#94/#90).
        """
        # Если запись активна, предлагаем явный выбор действия,
        # чтобы пользователь мог предпочесть сворачивание выходу.
        if self._state.is_recording():
            choice = self._ask_close_action_while_recording()
            if choice == "cancel":
                event.ignore()
                return
            if choice == "tray":
                # force_minimize_to_tray=True заставляет main.py
                # скрыть окно независимо от minimize_to_tray.
                self.close_requested.emit(
                    {"event": event, "force_minimize_to_tray": True}
                )
                return
            if choice == "stop_and_exit":
                self._stop_recording()
                # Дальнейшая обработка через штатный путь,
                # чтобы graceful shutdown корректно завершил работу.

        # Сначала эмитируем сигнал для внешней обработки
        self.close_requested.emit(event)

        # Если событие было проигнорировано внешним обработчиком, выходим
        if not event.isAccepted():
            return

        self._settings_controller.save_settings()
        self._update_timer.stop()
        self._thread_tracker.join_all()
        event.accept()

    def _ask_close_action_while_recording(self) -> str:
        """Диалог выбора действия при закрытии во время записи.

        Returns:
            Одно из: ``"tray"``, ``"stop_and_exit"``, ``"cancel"``.
        """
        box = QMessageBox(self)
        box.setWindowTitle("Запись в процессе")
        box.setText("Запись активна. Что сделать?")
        box.setInformativeText(
            "Сворачивание в трей продолжит запись в фоне. "
            "Для выхода будет остановлена и сохранена текущая запись."
        )
        box.setIcon(QMessageBox.Icon.Question)

        tray_button = box.addButton(
            "Свернуть в трей", QMessageBox.ButtonRole.AcceptRole
        )
        exit_button = box.addButton(
            "Остановить запись и выйти",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = box.addButton(
            "Отмена", QMessageBox.ButtonRole.RejectRole
        )

        box.setDefaultButton(tray_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is tray_button:
            return "tray"
        if clicked is exit_button:
            return "stop_and_exit"
        if clicked is cancel_button:
            return "cancel"
        return "cancel"

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

    def get_metrics(self) -> dict:
        """
        Получение текущих метрик производительности видеозаписи (#114).

        Returns:
            Словарь с метриками кадров (FPS, jitter, latency и др.)
        """
        return self._recording_controller.frame_metrics

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

            # Получить количество восстановлений FFmpeg
            recovery_count = self._recording_controller.get_recoveries_count()

            self._diagnostics_view.run_checks(
                api_enabled=api_running,
                output_path=output_path,
                capture=capture,
                audio=audio,
                snapshot=readiness_snapshot,
                recovery_count=recovery_count,
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
        if hasattr(self, "_readiness_controller"):
            cached = self._readiness_controller.resolve_cached_snapshot(
                capture, audio, output_path
            )
            if cached is not None:
                return cached
        latest_inputs = getattr(self, "_latest_readiness_inputs", None)
        latest_snapshot = getattr(self, "_latest_readiness_snapshot", None)
        if latest_inputs is None or latest_snapshot is None:
            return None
        if (
            isinstance(latest_inputs, dict)
            and latest_inputs.get("capture") == capture
            and latest_inputs.get("audio") == audio
            and latest_inputs.get("output_path") == output_path
            and isinstance(latest_snapshot, ReadinessSnapshot)
        ):
            return latest_snapshot
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
                if isinstance(r, list | tuple) and len(r) >= 4:
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

    def switch_capture_source(self, params: dict) -> dict:
        """
        Переключает источник захвата активной записи без остановки (#48).

        Args:
            params: Словарь с параметрами нового источника захвата
                - area: "full" | "window" | "rect"
                - window_title: str (опционально)
                - rect: [x1, y1, x2, y2] (опционально)

        Returns:
            Словарь с результатом операции.
        """
        if not self._state.is_recording():
            return {"success": False, "error": "Запись не активна"}

        area_type = params.get("area", "full")
        capture_type_map = {
            "full": CaptureMode.FULL,
            "window": CaptureMode.WINDOW,
            "rect": CaptureMode.RECT,
        }
        capture_type = capture_type_map.get(area_type, CaptureMode.FULL)

        rect_coords = None
        if area_type == "rect" and "rect" in params:
            r = params["rect"]
            if isinstance(r, list | tuple) and len(r) >= 4:
                rect_coords = (r[0], r[1], r[2], r[3])
            else:
                return {
                    "success": False,
                    "error": "rect должен содержать 4 координаты [x1, y1, x2, y2]",
                }

        capture = CaptureSettings(
            capture_type=capture_type,
            window_title=params.get("window_title") or "",
            rect_coords=rect_coords or (0, 0, 1920, 1080),
            strict_window_match=True,
        )

        success, error_msg = self._recording_controller.switch_capture_source(
            capture
        )
        if success:
            return {"success": True}
        return {
            "success": False,
            "error": error_msg or "Не удалось переключить источник захвата",
        }

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
