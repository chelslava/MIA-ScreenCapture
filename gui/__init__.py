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

Примечание: Импорты модулей выполняются явно для избежания
циклических зависимостей и不必要的 загрузки GUI в headless режиме.
"""

__all__ = ["MainWindow", "TrayIcon", "SchedulerTab"]
