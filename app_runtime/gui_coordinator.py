"""GUI runtime coordinator для composition root приложения."""

from __future__ import annotations

import importlib.metadata
import sys
import threading
from typing import TYPE_CHECKING

from .thread_executor import MainThreadExecutor

if TYPE_CHECKING:
    from main import VideoRecorderApp


class GuiRuntimeCoordinator:
    """Координатор запуска GUI-рантайма приложения."""

    def __init__(self, app: VideoRecorderApp) -> None:
        self._app = app

    def run(self) -> int:
        """Запускает GUI-режим и инициализирует связанные компоненты."""
        from PyQt6.QtWidgets import QApplication

        self._app._app = QApplication(sys.argv)
        assert self._app._app is not None
        self._app._gui_thread_id = threading.get_ident()
        self._app._gui_executor = MainThreadExecutor()
        self._app._app.setApplicationName("MIA-ScreenCapture")
        try:
            version = importlib.metadata.version("mia-screencapture")
        except importlib.metadata.PackageNotFoundError:
            version = "dev"
        self._app._app.setApplicationVersion(version)

        self._setup_main_window()
        self._setup_tray_icon()
        self._bind_window_and_tray_signals()
        self._bind_runtime_components()

        assert self._app._main_window is not None
        self._app._main_window.show()
        self._app._running = True
        return self._app._app.exec()

    def _setup_main_window(self) -> None:
        """Создаёт главное окно приложения."""
        from gui.main_window import MainWindow

        self._app._main_window = MainWindow()
        assert self._app._main_window is not None

    def _setup_tray_icon(self) -> None:
        """Создаёт иконку в трее и подключает её сигналы."""
        from gui.tray_icon import TrayIcon

        assert self._app._main_window is not None
        facade = self._app.get_application_facade()
        self._app._tray_icon = TrayIcon(self._app._main_window)
        assert self._app._tray_icon is not None
        self._app._tray_icon.show()

        self._app._tray_icon.start_requested.connect(
            facade.request_start_recording
        )
        self._app._tray_icon.stop_requested.connect(
            facade.request_stop_recording
        )
        self._app._tray_icon.pause_requested.connect(
            facade.request_toggle_pause_recording
        )
        self._app._tray_icon.show_window_requested.connect(
            self._app._show_window
        )
        self._app._tray_icon.exit_requested.connect(self._app._quit_app)

    def _bind_window_and_tray_signals(self) -> None:
        """Связывает сигналы главного окна и трея."""
        assert self._app._main_window is not None
        assert self._app._tray_icon is not None
        tray_icon = self._app._tray_icon

        self._app._main_window.recording_started.connect(
            lambda p: tray_icon.on_recording_started(p)
        )
        self._app._main_window.recording_stopped.connect(
            lambda p: tray_icon.on_recording_stopped(p)
        )
        self._app._main_window.recording_paused.connect(
            tray_icon.on_recording_paused
        )
        self._app._main_window.recording_resumed.connect(
            tray_icon.on_recording_resumed
        )
        self._app._main_window.error_occurred.connect(tray_icon.on_error)
        self._app._main_window.close_requested.connect(
            self._app._handle_close_requested
        )

    def _bind_runtime_components(self) -> None:
        """Подключает API/планировщик и hotkeys к GUI."""
        assert self._app._main_window is not None
        facade = self._app.get_application_facade()

        self._app._setup_hotkeys()
        facade.start_api_server()
        self._app._main_window.bind_application_facade(facade)
        self._app._main_window.refresh_api_status_view()
        self._app._start_scheduler()
