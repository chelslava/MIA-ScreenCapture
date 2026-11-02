"""
Сборка UI главного окна (#164)
==============================

Миксин ``MainWindowUIBuilderMixin`` вынесен из ``gui/main_window.py``:
создание окна, сайдбара, вкладок, панелей и статус-бара. ``MainWindow``
наследует миксин, поэтому все методы остаются доступны как раньше —
поведение и тестовый контракт не меняются.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gui.desktop_actions import DesktopActionId, DesktopActionRegistry
from gui.styles.theme import Theme
from gui.views.appearance_view import AppearanceView
from gui.views.audio_view import AudioView
from gui.views.capture_view import CaptureView
from gui.views.output_view import OutputView
from gui.views.post_processing_view import PostProcessingView
from gui.views.readiness_center_view import ReadinessCenterView
from gui.views.recording_tunables_view import RecordingTunablesView
from gui.views.recordings_list import RecordingsListWidget
from gui.views.video_view import VideoView

if TYPE_CHECKING:
    from PyQt6.QtCore import QTimer

    from gui.controllers.settings_controller import SettingsController

_SIDEBAR_DEFAULT_WIDTH = 110
_SIDEBAR_COLLAPSED_WIDTH = 44
_SIDEBAR_TEXT_VISIBLE_THRESHOLD = 70
_SIDEBAR_ICONS_DIR = Path(__file__).resolve().parents[1] / "assets" / "icons"


if TYPE_CHECKING:
    _QWindowBase = QMainWindow
else:
    # В рантайме миксин — обычный класс (без metaclass-конфликтов
    # с PyQt); QMainWindow приходит от MainWindow напрямую.
    _QWindowBase = object


class MainWindowUIBuilderMixin(_QWindowBase):
    """Построение каркаса главного окна: сайдбар, вкладки, статус-бар."""

    if TYPE_CHECKING:
        # Общие атрибуты окна, создаваемые в MainWindow.__init__/_setup_ui
        _settings_controller: SettingsController
        _toast_timer: QTimer
        _desktop_actions: DesktopActionRegistry
        _sidebar_expanded_width: int

        # Методы, оставшиеся в MainWindow (связующий слой)
        _animate_current_page_in: Callable[[], None]
        _hide_toast: Callable[[], None]
        _run_diagnostics: Callable[[], None]
        _on_diagnostics_fix: Callable[[str], None]
        _refresh_recent_recordings: Callable[[], None]
        _clear_recordings_filter: Callable[[], None]
        _on_profile_combo_changed: Callable[[int], None]
        _open_profile_dialog: Callable[[], None]
        _on_post_processing_changed: Callable[[], None]
        _on_recording_tunables_changed: Callable[[], None]
        _open_recording: Callable[[QListWidgetItem], None]
        _open_selected_recording: Callable[[], None]
        _clear_recent_recordings: Callable[[], None]
        _show_recordings_context_menu: Callable[[Any], None]
        _on_sidebar_selection_changed: Callable[[], None]

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

        # Тонкие параметры записи (#155)
        self._recording_tunables_view = RecordingTunablesView()
        self._recording_tunables_view.settings_changed.connect(
            self._on_recording_tunables_changed
        )
        layout.addWidget(self._recording_tunables_view)

        layout.addStretch()
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

        self.recordings_list = RecordingsListWidget()
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

    def _get_default_geometry(self) -> Any:
        """Возвращает геометрию по умолчанию при отсутствии экрана."""
        from PyQt6.QtCore import QRect

        return QRect(0, 0, 1920, 1080)
