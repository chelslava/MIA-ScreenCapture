"""
Пакет GUI
=========

Этот пакет содержит все компоненты GUI:
- MainWindow: Главное окно приложения
- TrayIcon: Иконка системного трея и меню
- SchedulerTab: Интерфейс управления планировщиком

Архитектура MVC:
- models: Модели данных (RecordingState)
- views: Представления (CaptureView, AudioView, VideoView, OutputView)
- controllers: Контроллеры (RecordingController, SettingsController)
"""

from .main_window import MainWindow
from .scheduler_tab import SchedulerTab
from .tray_icon import TrayIcon

__all__ = ["MainWindow", "TrayIcon", "SchedulerTab"]
