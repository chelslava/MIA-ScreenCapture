#!/usr/bin/env python3
"""
Скрипт для создания скриншотов интерфейса приложения.
Используется для документации.
"""

import sys
import time
from pathlib import Path

from PyQt6.QtWidgets import QApplication

# Добавить корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.recording_state import RecordingState
from gui.main_window import MainWindow


def take_screenshots() -> None:
    """Создать скриншоты интерфейса."""
    app = QApplication(sys.argv)

    # Создать главное окно
    window = MainWindow(headless=False)
    window.show()

    # Подождать загрузки окна
    app.processEvents()
    time.sleep(1)

    # Скриншот главного окна (запись вкладка)
    output_dir = (
        Path(__file__).parent.parent / "docs" / "assets" / "screenshots"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path = output_dir / "main-window-recording-tab.png"
    pixmap = window.grab()
    pixmap.save(str(screenshot_path))
    print(f"Скриншот сохранён: {screenshot_path}")

    # Переключиться на вкладку настроек
    if hasattr(window, "_sidebar") and hasattr(window, "_sidebar_items"):
        # Найти индекс вкладки "Настройки"
        for idx, item in enumerate(window._sidebar_items):
            if "Настройки" in item or "Settings" in item:
                window._sidebar.setCurrentRow(idx)
                app.processEvents()
                time.sleep(0.5)

                screenshot_path = output_dir / "main-window-settings-tab.png"
                pixmap = window.grab()
                pixmap.save(str(screenshot_path))
                print(f"Скриншот сохранён: {screenshot_path}")
                break

    # Закрыть окно
    window.close()
    sys.exit(0)


if __name__ == "__main__":
    take_screenshots()
