"""
Модуль главного окна (рефакторинг)
===================================

Главное окно GUI для приложения записи видео.
Использует MVC архитектуру с разделением на компоненты.

Начиная с #164 окно — связующий слой: инициализация, маршрутизация
сигналов и lifecycle. Крупные блоки вынесены в миксины:

- ``gui.views.main_ui_builder`` — сборка окна/сайдбара/вкладок;
- ``gui.views.menu_builder`` — desktop actions, шорткаты, доступность;
- ``gui.controllers.api_section_controller`` — вкладка API и WebSocket;
- ``gui.controllers.recordings_actions_controller`` — операции с записями;
- ``gui.controllers.api_params_recording`` — запись по параметрам API;
- ``gui.controllers.recording_flow_controller`` — остановка записи,
  финализация, плавающий виджет и таймер статуса.
"""

import threading
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QLabel, QListWidgetItem, QMainWindow, QMessageBox

from config import get_config
from core.event_bus import RecordingEvent, RecordingEventType
from core.i18n import set_locale
from core.readiness import (
    ReadinessSnapshot,
    RecordingReadinessService,
    build_readiness_checks,
)
from core.recording_types import AudioMode, CaptureMode
from gui import transitions
from gui.controllers.api_params_recording import ApiParamsRecordingMixin
from gui.controllers.api_section_controller import ApiSectionControllerMixin
from gui.controllers.desktop_actions_controller import DesktopActionsController
from gui.controllers.profile_gui_controller import ProfileGUIController
from gui.controllers.readiness_controller import ReadinessController
from gui.controllers.recording_controller import RecordingController
from gui.controllers.recording_flow_controller import (
    RecordingFlowControllerMixin,
)
from gui.controllers.recordings_actions_controller import (
    RecordingsActionsControllerMixin,
)
from gui.controllers.recordings_controller import RecordingsController
from gui.controllers.settings_controller import SettingsController
from gui.controllers.status_bar_controller import StatusBarController
from gui.controllers.websocket_controller import WebSocketClientController
from gui.desktop_actions import DesktopActionId, DesktopActionRegistry
from gui.models.recording_state import (
    AudioSettings,
    CaptureSettings,
    RecordingState,
)
from gui.styles.backdrop import (
    apply_mica_backdrop,
    resolve_backdrop_active,
)
from gui.styles.theme import Theme, apply_theme, set_backdrop_active
from gui.views.draw_overlay import DrawOverlayWidget
from gui.views.finalization_progress_dialog import (
    FinalizationProgressDialog,
)
from gui.views.floating_widget import FloatingRecordingWidget
from gui.views.main_ui_builder import MainWindowUIBuilderMixin
from gui.views.menu_builder import MainWindowMenuActionsMixin
from gui.views.recording_indicator import RecordingIndicatorOverlay
from logger_config import get_module_logger, open_logs_folder
from recorder.utils import (
    FFmpegStatus,
    format_filesize,
    generate_thumbnail,
)

if TYPE_CHECKING:
    from core.application_facade import ApplicationFacade

logger = get_module_logger(__name__)


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


class MainWindow(
    MainWindowUIBuilderMixin,
    MainWindowMenuActionsMixin,
    ApiSectionControllerMixin,
    RecordingsActionsControllerMixin,
    ApiParamsRecordingMixin,
    RecordingFlowControllerMixin,
    QMainWindow,
):
    """
    Главное окно приложения.

    Использует MVC архитектуру:
    - Model: RecordingState
    - View: CaptureView, AudioView, VideoView, OutputView
    - Controller: RecordingController, SettingsController

    Сам класс — связующий слой: инициализация, маршрутизация сигналов
    между контроллерами и lifecycle окна (#164). Крупные блоки логики
    вынесены в миксины (см. docstring модуля).
    """

    # Сигналы
    recording_started = pyqtSignal(str)
    recording_stopped = pyqtSignal(str)
    recording_paused = pyqtSignal()
    recording_resumed = pyqtSignal()
    error_occurred = pyqtSignal(str)
    # Потеря аудио-чанков: суммарное количество за текущую запись (#154).
    # Сигнал нужен для маршалинга из потока sounddevice в GUI-поток.
    audio_chunks_dropped = pyqtSignal(int)
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
        # Потеря аудио-чанков (#154): callback приходит из потока
        # sounddevice — в GUI уходим через queued-сигнал.
        self._audio_drop_warning_shown = False
        self._recording_controller.set_audio_chunks_dropped_callback(
            self.audio_chunks_dropped.emit
        )
        self.audio_chunks_dropped.connect(
            self._on_audio_chunks_dropped_warning
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
        # Плавающий виджет записи (#158) — также лениво
        self._floating_widget: FloatingRecordingWidget | None = None
        # Оверлей рисования (#159) — создаётся по первому хоткею
        self._draw_overlay: DrawOverlayWidget | None = None
        self._readiness_request_id = 0
        self._latest_readiness_snapshot: ReadinessSnapshot | None = None
        self._latest_readiness_inputs: dict[str, object] | None = None

        # Таймер обновления статуса
        self._update_timer = QTimer()
        self._update_timer.timeout.connect(self._update_status)

        # Настройка окна
        self._setup_window()
        self._setup_ui()
        # Mica требует созданный hwnd; QSS-прослойку выставляет
        # gui_coordinator до apply_theme (#157)
        self._apply_mica_backdrop()
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

    def _on_sidebar_selection_changed(self) -> None:
        """Обработчик переключения страниц при клике на боковую панель."""
        current_row = self._sidebar.currentRow()
        if current_row >= 0:
            self._content_stack.setCurrentIndex(current_row)
            self._animate_current_page_in()

    def _animate_current_page_in(self) -> None:
        """Fade-переход вкладки с учётом настроек и reduced-motion (#161)."""
        if not get_config().settings.ui_animations:
            return
        if transitions.reduced_motion_preferred():
            return
        transitions.animate_page_in(self._content_stack.currentWidget())

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

        # Язык интерфейса
        self._appearance_view.set_current_language(
            self._settings_controller.get_language()
        )

        # Поведение закрытия окна (сворачивание в трей)
        self._appearance_view.set_minimize_to_tray(
            self._settings_controller.get_minimize_to_tray()
        )

        # Анимации переходов (#161)
        self._appearance_view.set_ui_animations(
            get_config().settings.ui_animations
        )

        # Материал Windows 11 (#157)
        self._appearance_view.set_win11_backdrop(
            get_config().settings.win11_backdrop
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

        # Тонкие параметры записи (#155)
        if hasattr(self, "_recording_tunables_view"):
            self._recording_tunables_view.set_settings(
                get_config().settings.recording_tunables
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

    def _on_recording_tunables_changed(self) -> None:
        """Сохранение тонких параметров записи при изменении в UI (#155)."""
        if not hasattr(self, "_recording_tunables_view"):
            return
        new_tunables = self._recording_tunables_view.get_settings()
        config = get_config()
        config.settings.recording_tunables = new_tunables
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
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsDragEnabled)

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
        self._apply_mica_backdrop()

    def _apply_mica_backdrop(self) -> None:
        """Включить материал Windows 11 для окна при включённой опции (#157).

        DWM-материал требует hwnd, поэтому применяется после создания окна;
        на Windows 10 / при отказе DWM окно остаётся с обычной темой.
        """
        active = resolve_backdrop_active(get_config().settings.win11_backdrop)
        set_backdrop_active(active)
        if not active:
            return
        if not hasattr(self, "winId"):
            return
        try:
            apply_mica_backdrop(int(self.winId()))
        except Exception as e:
            logger.warning("Не удалось применить Mica: %s", e)

    def _on_win11_backdrop_changed(self, enabled: bool) -> None:
        """Сохранение и применение настройки материала Windows 11 (#157)."""
        config = get_config()
        config.settings.win11_backdrop = bool(enabled)
        config.save()
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app is not None:
            apply_theme(app, self._settings_controller.get_theme_mode())
        self._apply_mica_backdrop()

    def _on_language_changed(self, language: str) -> None:
        """Обработка выбора языка интерфейса."""
        self._settings_controller.set_language(language)
        set_locale(language)
        logger.info(f"Язык интерфейса изменен на: {language}")

    def _on_ui_animations_changed(self, enabled: bool) -> None:
        """Сохранение настройки плавных переходов (#161)."""
        config = get_config()
        config.settings.ui_animations = bool(enabled)
        config.save()

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

            elif event_type == "disk_space_critical":
                message = payload.get(
                    "message", "Критическая нехватка места на диске"
                )
                self._show_toast(message, duration_ms=5000)
                self._show_non_modal_error(message)

            elif event.event_type is RecordingEventType.ERROR:
                message = (
                    payload.get("message")
                    or payload.get("error")
                    or "Произошла ошибка записи"
                )
                self._show_toast(str(message), duration_ms=5000)
                self._show_non_modal_error(str(message))

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
        self._appearance_view.language_changed.connect(
            self._on_language_changed
        )
        self._appearance_view.hotkeys_requested.connect(
            self._show_hotkeys_view
        )
        self._appearance_view.minimize_to_tray_changed.connect(
            self._on_minimize_to_tray_changed
        )
        self._appearance_view.ui_animations_changed.connect(
            self._on_ui_animations_changed
        )
        self._appearance_view.win11_backdrop_changed.connect(
            self._on_win11_backdrop_changed
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
        draw_overlay = getattr(self, "_draw_overlay", None)
        if (
            draw_overlay is not None
            and getattr(draw_overlay, "isVisible", lambda: False)()
        ):
            draw_overlay.close_overlay()
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

    # === Ошибки и уведомления ===

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

    # === Режим рисования поверх экрана (#159) ===

    def _get_draw_overlay(self) -> DrawOverlayWidget | None:
        """Лениво создать оверлей рисования (#159)."""
        if self._draw_overlay is None:
            try:
                self._draw_overlay = DrawOverlayWidget()
            except Exception as e:
                logger.warning("Не удалось создать оверлей рисования: %s", e)
                return None
            self._draw_overlay.screenshot_taken.connect(
                self._on_draw_screenshot_taken
            )
            self._draw_overlay.stop_requested.connect(self._stop_recording)
        return self._draw_overlay

    def toggle_draw_overlay_mode(self) -> None:
        """Показать или скрыть оверлей быстрых аннотаций (#159).

        Режим доступен только во время активной записи: аннотации —
        вспомогательный инструмент кадра, а не самостоятельный режим.
        """
        overlay = getattr(self, "_draw_overlay", None)
        if (
            overlay is not None
            and getattr(overlay, "isVisible", lambda: False)()
        ):
            overlay.close_overlay()
            return
        if not self._state.is_recording():
            self._show_toast(
                "Режим рисования доступен только во время записи",
                duration_ms=4000,
            )
            return
        overlay = self._get_draw_overlay()
        if overlay is None:
            return
        overlay.open_overlay()
        self.status_bar.showMessage(
            "Режим рисования: Esc — выход, Ctrl+Z — отмена", 5000
        )

    def _toggle_draw_overlay(self) -> None:
        """Callback desktop-действия и глобального хоткея."""
        self.toggle_draw_overlay_mode()

    def _on_draw_screenshot_taken(self, path_text: str) -> None:
        """Тост о сохранённом аннотированном скриншоте (#159)."""
        self._show_toast(f"Скриншот сохранён: {path_text}", 5000)

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
            Словарь с метриками кадров (FPS, jitter, latency и др.) и
            счётчиком потерянных аудио-чанков (#154).
        """
        metrics = self._recording_controller.frame_metrics
        metrics["dropped_audio_chunks"] = (
            self._recording_controller.dropped_audio_chunks
        )
        return metrics

    def get_finalization_status(self) -> dict[str, Any]:
        """
        Получение статуса финализации записи (#151).

        Returns:
            Словарь {active, percent, stage, elapsed_s, eta_s}.
        """
        return self._recording_controller.progress_tracker.snapshot()

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
                dropped_audio_chunks=(
                    self._recording_controller.dropped_audio_chunks
                ),
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
