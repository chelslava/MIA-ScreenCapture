"""
Пакет GUI
=========

Этот пакет содержит все компоненты GUI:
- MainWindow: Главное окно приложения
- TrayIcon: Иконка системного трея и меню
- SchedulerTab: Интерфейс управления планировщиком
"""

from .main_window import MainWindow
from .tray_icon import TrayIcon
from .scheduler_tab import SchedulerTab

__all__ = ['MainWindow', 'TrayIcon', 'SchedulerTab']
