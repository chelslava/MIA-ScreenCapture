"""
Конфигурация pytest и общие fixtures
====================================

Содержит общие fixtures для использования в тестах.
"""

import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock

if TYPE_CHECKING:
    from PyQt6.QtWidgets import QApplication

import pytest
from _pytest import pathlib as pytest_pathlib
from _pytest import tmpdir as pytest_tmpdir

_original_cleanup_dead_symlinks = pytest_pathlib.cleanup_dead_symlinks
_LOCAL_TMP_ROOT = Path(__file__).parent / ".local_tmp"
_LOCAL_SYSTEM_TMP = _LOCAL_TMP_ROOT / "system"


def _safe_cleanup_dead_symlinks(root: Path) -> None:
    """
    Безопасная очистка временных ссылок для Windows окружения.

    На некоторых машинах (в т.ч. CI) удаление basetemp может завершаться
    `PermissionError` из-за временных блокировок/ACL. Такая ошибка не должна
    валить весь прогон тестов, если сами тесты завершились.
    """
    try:
        _original_cleanup_dead_symlinks(root)
    except PermissionError:
        return


pytest_pathlib.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks
pytest_tmpdir.cleanup_dead_symlinks = _safe_cleanup_dead_symlinks


def _bootstrap_local_tmp_dirs() -> None:
    """
    Подготавливает изолированные tmp/cache директории для pytest.

    Это снижает риск `WinError 5` на Windows из-за блокировок в системном
    temp-каталоге и в корневом `.pytest_cache`.
    """
    (_LOCAL_TMP_ROOT / "pytest").mkdir(parents=True, exist_ok=True)
    (_LOCAL_TMP_ROOT / ".pytest_cache").mkdir(parents=True, exist_ok=True)
    _LOCAL_SYSTEM_TMP.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("TMP", str(_LOCAL_SYSTEM_TMP))
    os.environ.setdefault("TEMP", str(_LOCAL_SYSTEM_TMP))
    os.environ.setdefault("TMPDIR", str(_LOCAL_SYSTEM_TMP))


_bootstrap_local_tmp_dirs()

# Добавление родительской директории в путь для импорта
sys.path.insert(0, str(Path(__file__).parent.parent))


# =============================================================================
# Мокирование PyQt6 для GUI тестов
# =============================================================================

# Мокируем PyQt6 до импорта любых модулей, которые его используют
# Это позволяет тестировать GUI код без установленного PyQt6


def _create_mock_class(name: str, bases=()):
    """Создание mock класса с правильным MRO."""

    class MockClass(*bases):
        def __init__(self, *args, **kwargs):
            super().__init__()

        def __iter__(self):
            return iter([])

    MockClass.__name__ = name
    MockClass.__qualname__ = name
    return MockClass


# Создаем базовый QWidget mock с необходимыми методами
class MockQWidgetBase:
    """Базовый mock для QWidget с необходимыми методами."""

    def __init__(self, *args, **kwargs):
        self._enabled = True
        self._visible = True
        self._layout = None

    def setChecked(self, checked: bool):
        """Для QRadioButton, QCheckBox."""
        self._checked = checked

    def isChecked(self) -> bool:
        """Для QRadioButton, QCheckBox."""
        return getattr(self, "_checked", False)

    def setEnabled(self, enabled: bool):
        self._enabled = enabled

    def isEnabled(self) -> bool:
        return self._enabled

    def setVisible(self, visible: bool):
        self._visible = visible

    def isVisible(self) -> bool:
        return self._visible

    def setLayout(self, layout):
        self._layout = layout

    def layout(self):
        return self._layout

    def setText(self, text: str):
        """Для QLabel, QPushButton, QLineEdit."""
        self._text = text

    def text(self) -> str:
        """Для QLabel, QPushButton, QLineEdit."""
        return getattr(self, "_text", "")

    def setRange(self, min_val: int, max_val: int):
        """Для QSpinBox."""
        self._min = min_val
        self._max = max_val

    def setValue(self, value: int):
        """Для QSpinBox."""
        self._value = value

    def value(self) -> int:
        """Для QSpinBox."""
        return getattr(self, "_value", 0)

    def addItem(self, item: str):
        """Для QComboBox."""
        if not hasattr(self, "_items"):
            self._items = []
        self._items.append(item)

    def addItems(self, items: list):
        """Для QComboBox."""
        if not hasattr(self, "_items"):
            self._items = []
        self._items.extend(items)

    def currentText(self) -> str:
        """Для QComboBox."""
        return getattr(self, "_current_text", "")

    def setCurrentText(self, text: str):
        """Для QComboBox."""
        self._current_text = text

    def currentIndex(self) -> int:
        """Для QComboBox."""
        return getattr(self, "_current_index", -1)

    def setCurrentIndex(self, index: int):
        """Для QComboBox."""
        self._current_index = index

    def count(self) -> int:
        """Для QComboBox."""
        return len(getattr(self, "_items", []))

    def itemText(self, index: int) -> str:
        """Для QComboBox."""
        items = getattr(self, "_items", [])
        if 0 <= index < len(items):
            return items[index]
        return ""

    def clear(self):
        """Для QComboBox."""
        self._items = []
        self._current_index = -1
        self._current_text = ""

    def setEditable(self, editable: bool):
        """Для QComboBox."""
        self._editable = editable

    def isEditable(self) -> bool:
        """Для QComboBox."""
        return getattr(self, "_editable", False)

    def setMinimumWidth(self, width: int):
        """Для QWidget."""
        self._minimum_width = width

    def minimumWidth(self) -> int:
        """Для QWidget."""
        return getattr(self, "_minimum_width", 0)

    def setMaximumWidth(self, width: int):
        """Для QWidget."""
        self._maximum_width = width

    def maximumWidth(self) -> int:
        """Для QWidget."""
        return getattr(self, "_maximum_width", 16777215)

    def setMinimumHeight(self, height: int):
        """Для QWidget."""
        self._minimum_height = height

    def minimumHeight(self) -> int:
        """Для QWidget."""
        return getattr(self, "_minimum_height", 0)

    def setMaximumHeight(self, height: int):
        """Для QWidget."""
        self._maximum_height = height

    def maximumHeight(self) -> int:
        """Для QWidget."""
        return getattr(self, "_maximum_height", 16777215)

    def setFixedSize(self, width: int, height: int):
        """Для QWidget."""
        self._fixed_width = width
        self._fixed_height = height

    def resize(self, width: int, height: int):
        """Для QWidget."""
        self._width = width
        self._height = height

    def setToolTip(self, text: str):
        """Для QWidget."""
        self._tooltip = text

    def toolTip(self) -> str:
        """Для QWidget."""
        return getattr(self, "_tooltip", "")

    def setPlaceholderText(self, text: str):
        """Для QLineEdit."""
        self._placeholder = text

    def setReadOnly(self, read_only: bool):
        """Для QLineEdit, QTextEdit."""
        self._read_only = read_only

    def toPlainText(self) -> str:
        """Для QTextEdit."""
        return getattr(self, "_plain_text", "")

    def setPlainText(self, text: str):
        """Для QTextEdit."""
        self._plain_text = text

    def __iter__(self):
        return iter([])


# Signal mock
class MockSignal:
    """Mock для pyqtSignal."""

    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def disconnect(self, callback=None):
        if callback:
            if callback in self._callbacks:
                self._callbacks.remove(callback)
        else:
            self._callbacks.clear()

    def emit(self, *args, **kwargs):
        for callback in self._callbacks:
            callback(*args, **kwargs)


# Создаем mock классы с нужными методами
def _create_widget_mock_class(name: str):
    """Создание mock класса для виджета с методами."""

    class MockWidget(MockQWidgetBase):
        pass

    MockWidget.__name__ = name
    MockWidget.__qualname__ = name
    # Добавляем signals как атрибуты класса
    if name == "QRadioButton":
        MockWidget.toggled = MockSignal()
        MockWidget.clicked = MockSignal()
    elif name == "QCheckBox":
        MockWidget.stateChanged = MockSignal()
        MockWidget.toggled = MockSignal()
        MockWidget.clicked = MockSignal()
    elif name == "QSpinBox":
        MockWidget.valueChanged = MockSignal()
    elif name == "QComboBox":
        MockWidget.currentTextChanged = MockSignal()
        MockWidget.currentIndexChanged = MockSignal()
    elif name == "QLineEdit":
        MockWidget.textChanged = MockSignal()
        MockWidget.textEdited = MockSignal()
        MockWidget.returnPressed = MockSignal()
    elif name == "QTextEdit":
        MockWidget.textChanged = MockSignal()
    elif name == "QPushButton":
        MockWidget.clicked = MockSignal()
    return MockWidget


MockQWidget = _create_mock_class("QWidget", (MockQWidgetBase,))
MockQMainWindow = _create_mock_class("QMainWindow", (MockQWidgetBase,))
MockQDialog = _create_mock_class("QDialog", (MockQWidgetBase,))
MockQGroupBox = _create_mock_class("QGroupBox", (MockQWidgetBase,))
MockQLabel = _create_mock_class("QLabel", (MockQWidgetBase,))
MockQPushButton = _create_widget_mock_class("QPushButton")
MockQRadioButton = _create_widget_mock_class("QRadioButton")
MockQCheckBox = _create_widget_mock_class("QCheckBox")
MockQComboBox = _create_widget_mock_class("QComboBox")
MockQSpinBox = _create_widget_mock_class("QSpinBox")
MockQLineEdit = _create_widget_mock_class("QLineEdit")
MockQTextEdit = _create_widget_mock_class("QTextEdit")
MockQListWidget = _create_mock_class("QListWidget", (MockQWidgetBase,))
MockQTreeWidget = _create_mock_class("QTreeWidget", (MockQWidgetBase,))
MockQTabWidget = _create_mock_class("QTabWidget", (MockQWidgetBase,))
MockQScrollArea = _create_mock_class("QScrollArea", (MockQWidgetBase,))
MockQSplitter = _create_mock_class("QSplitter", (MockQWidgetBase,))
MockQFrame = _create_mock_class("QFrame", (MockQWidgetBase,))


# Layout mocks - с методами setContentsMargins, addWidget и т.д.
class MockQVBoxLayoutBase:
    """Базовый mock для QVBoxLayout с необходимыми методами."""

    def __init__(self, *args, **kwargs):
        self._margins = (0, 0, 0, 0)
        self._spacing = 0
        self._widgets = []

    def setContentsMargins(self, left, top, right, bottom):
        self._margins = (left, top, right, bottom)

    def contentsMargins(self):
        return self._margins

    def setSpacing(self, spacing):
        self._spacing = spacing

    def spacing(self):
        return self._spacing

    def addWidget(self, widget, stretch=0, alignment=0):
        self._widgets.append(widget)

    def addLayout(self, layout, stretch=0):
        pass

    def addStretch(self, stretch=0):
        pass

    def addSpacing(self, size):
        pass

    def insertWidget(self, index, widget, stretch=0, alignment=0):
        self._widgets.insert(index, widget)

    def count(self):
        return len(self._widgets)

    def itemAt(self, index):
        if 0 <= index < len(self._widgets):
            return self._widgets[index]
        return None

    def __iter__(self):
        return iter([])


class MockQHBoxLayoutBase(MockQVBoxLayoutBase):
    """Mock для QHBoxLayout."""

    pass


class MockQGridLayoutBase:
    """Mock для QGridLayout."""

    def __init__(self, *args, **kwargs):
        self._widgets = {}

    def setContentsMargins(self, left, top, right, bottom):
        pass

    def addWidget(self, widget, row, col, rowSpan=1, colSpan=1, alignment=0):
        self._widgets[(row, col)] = widget

    def addLayout(self, layout, row, col, alignment=0):
        pass

    def setSpacing(self, spacing):
        pass

    def __iter__(self):
        return iter([])


class MockQFormLayoutBase:
    """Mock для QFormLayout."""

    def __init__(self, *args, **kwargs):
        self._rows = []

    def setContentsMargins(self, left, top, right, bottom):
        pass

    def addRow(self, label, field):
        self._rows.append((label, field))

    def setSpacing(self, spacing):
        pass

    def __iter__(self):
        return iter([])


MockQVBoxLayout = _create_mock_class("QVBoxLayout", (MockQVBoxLayoutBase,))
MockQHBoxLayout = _create_mock_class("QHBoxLayout", (MockQHBoxLayoutBase,))
MockQGridLayout = _create_mock_class("QGridLayout", (MockQGridLayoutBase,))
MockQFormLayout = _create_mock_class("QFormLayout", (MockQFormLayoutBase,))


class MockQApplication:
    """Mock для QApplication."""

    _instance = None

    def __init__(self, *args, **kwargs):
        MockQApplication._instance = self

    @classmethod
    def instance(cls):
        return cls._instance

    def exec(self):
        return 0


# Создаем mock модули
qt_widgets_mock = MagicMock()
qt_widgets_mock.QWidget = MockQWidget
qt_widgets_mock.QMainWindow = MockQMainWindow
qt_widgets_mock.QDialog = MockQDialog
qt_widgets_mock.QGroupBox = MockQGroupBox
qt_widgets_mock.QVBoxLayout = MockQVBoxLayout
qt_widgets_mock.QHBoxLayout = MockQHBoxLayout
qt_widgets_mock.QGridLayout = MockQGridLayout
qt_widgets_mock.QFormLayout = MockQFormLayout
qt_widgets_mock.QLabel = MockQLabel
qt_widgets_mock.QPushButton = MockQPushButton
qt_widgets_mock.QRadioButton = MockQRadioButton
qt_widgets_mock.QCheckBox = MockQCheckBox
qt_widgets_mock.QComboBox = MockQComboBox
qt_widgets_mock.QSpinBox = MockQSpinBox
qt_widgets_mock.QLineEdit = MockQLineEdit
qt_widgets_mock.QTextEdit = MockQTextEdit
qt_widgets_mock.QListWidget = MockQListWidget
qt_widgets_mock.QTreeWidget = MockQTreeWidget
qt_widgets_mock.QTabWidget = MockQTabWidget
qt_widgets_mock.QScrollArea = MockQScrollArea
qt_widgets_mock.QSplitter = MockQSplitter
qt_widgets_mock.QFrame = MockQFrame
qt_widgets_mock.QApplication = MockQApplication

qt_core_mock = MagicMock()
qt_core_mock.Qt = MagicMock()
qt_core_mock.Qt.Checked = 2
qt_core_mock.Qt.Unchecked = 0
qt_core_mock.Qt.PartiallyChecked = 1


def mock_pyqtSignal(*args, **kwargs):
    """Mock для pyqtSignal."""

    class MockSignal:
        def __init__(self):
            self._callbacks = []

        def connect(self, callback):
            self._callbacks.append(callback)

        def disconnect(self, callback=None):
            if callback:
                self._callbacks.remove(callback)
            else:
                self._callbacks.clear()

        def emit(self, *args, **kwargs):
            for callback in self._callbacks:
                callback(*args, **kwargs)

    return MockSignal()


qt_core_mock.pyqtSignal = mock_pyqtSignal
qt_core_mock.pyqtSlot = lambda *args, **kwargs: lambda func: func
qt_core_mock.QObject = _create_mock_class("QObject")
qt_core_mock.QThread = _create_mock_class("QThread")
qt_core_mock.QTimer = _create_mock_class("QTimer")
qt_core_mock.QSettings = _create_mock_class("QSettings")

qt_gui_mock = MagicMock()
qt_gui_mock.QIcon = _create_mock_class("QIcon")
qt_gui_mock.QPixmap = _create_mock_class("QPixmap")
qt_gui_mock.QColor = _create_mock_class("QColor")
qt_gui_mock.QFont = _create_mock_class("QFont")
qt_gui_mock.QCursor = _create_mock_class("QCursor")

sys.modules["PyQt6"] = MagicMock()
sys.modules["PyQt6.QtWidgets"] = qt_widgets_mock
sys.modules["PyQt6.QtCore"] = qt_core_mock
sys.modules["PyQt6.QtGui"] = qt_gui_mock


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Создание временной директории для тестов.

    Yields:
        Путь к временной директории
    """
    tmpdir = Path(tempfile.mkdtemp())
    try:
        yield tmpdir
    finally:
        # На Windows возможны кратковременные блокировки файлов после теста.
        for attempt in range(10):
            try:
                shutil.rmtree(tmpdir)
                break
            except OSError:
                if attempt == 9:
                    raise
                time.sleep(0.05 * (attempt + 1))


@pytest.fixture
def temp_config_file(temp_dir: Path) -> Path:
    """
    Создание временного файла конфигурации.

    Args:
        temp_dir: Временная директория

    Returns:
        Путь к файлу конфигурации
    """
    config_data = {
        "video": {
            "fps": 30,
            "codec": "libx264",
            "bitrate": "2M",
            "format": "mp4",
            "compression": True,
        },
        "audio": {
            "record_mic": True,
            "record_system": False,
            "mic_device": None,
            "system_device": None,
            "sample_rate": 44100,
            "channels": 2,
        },
        "capture": {
            "area_type": "full",
            "window_title": None,
            "rect_coords": None,
        },
        "output": {
            "default_path": str(temp_dir / "recordings"),
            "filename_template": "recording_{datetime}",
        },
        "api": {"enabled": True, "host": "127.0.0.1", "port": 5000},
        "scheduler": {
            "enabled": True,
            "persist_tasks": True,
            "max_concurrent_tasks": 1,
        },
        "minimize_to_tray": True,
        "show_notifications": True,
        "language": "en",
        "recent_recordings": [],
        "max_recent_recordings": 20,
    }

    config_path = temp_dir / "config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)

    return config_path


@pytest.fixture
def sample_recording_params() -> dict[str, Any]:
    """
    Пример параметров записи для тестов.

    Returns:
        Словарь с параметрами записи
    """
    return {
        "area_type": "full",
        "window_title": None,
        "rect_coords": None,
        "audio_type": "none",
        "output_path": None,
        "fps": 30,
        "codec": "libx264",
        "bitrate": "2M",
        "duration": None,
    }


@pytest.fixture
def sample_schedule_task() -> dict[str, Any]:
    """
    Пример задачи планировщика для тестов.

    Returns:
        Словарь с данными задачи
    """
    return {
        "id": "test-task-001",
        "name": "Тестовая запись",
        "schedule_type": "once",
        "params": {
            "area_type": "full",
            "audio_type": "none",
            "fps": 30,
            "codec": "libx264",
            "bitrate": "2M",
        },
        "enabled": True,
        "start_time": "2026-03-18T12:00:00",
        "time_of_day": None,
        "days_of_week": None,
        "interval_minutes": None,
        "interval_hours": None,
    }


@pytest.fixture
def temp_video_file(temp_dir: Path) -> Path:
    """
    Создание временного видеофайла (пустой файл с расширением .mp4).

    Args:
        temp_dir: Временная директория

    Returns:
        Путь к видеофайлу
    """
    video_path = temp_dir / "test_video.mp4"
    video_path.write_bytes(b"fake video content")
    return video_path


@pytest.fixture
def temp_audio_file(temp_dir: Path) -> Path:
    """
    Создание временного аудиофайла (пустой файл с расширением .wav).

    Args:
        temp_dir: Временная директория

    Returns:
        Путь к аудиофайлу
    """
    audio_path = temp_dir / "test_audio.wav"
    audio_path.write_bytes(b"fake audio content")
    return audio_path


@pytest.fixture
def mock_config_manager(temp_config_file: Path):
    """
    Создание mock ConfigManager для тестов.

    Args:
        temp_config_file: Путь к временному файлу конфигурации

    Returns:
        Экземпляр ConfigManager
    """
    from config import ConfigManager

    return ConfigManager(temp_config_file)


@pytest.fixture
def mock_logger():
    """
    Создание mock логгера для тестов.

    Returns:
        Mock логгер
    """
    import logging

    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)

    # Добавление handler для вывода в консоль
    handler = logging.StreamHandler()
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


@pytest.fixture
def tasks_file(temp_dir: Path) -> Path:
    """
    Создание временного файла задач планировщика.

    Args:
        temp_dir: Временная директория

    Returns:
        Путь к файлу задач
    """
    tasks_path = temp_dir / "tasks.json"
    tasks_path.write_text("[]")
    return tasks_path


@pytest.fixture(scope="module")
def qapp() -> "QApplication":
    """
    Создание QApplication для GUI тестов.

    Returns:
        Экземпляр QApplication
    """
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
