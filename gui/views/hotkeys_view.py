"""
Экран со списком горячих клавиш
=================================

Немодальный read-only диалог, показывающий все горячие клавиши приложения:
глобальные (работают без фокуса окна) и в-приложении (Qt-shortcuts из
`gui.desktop_actions.DesktopActionRegistry`).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from gui.desktop_actions import DesktopActionRegistry
from gui.styles.theme import Theme

# Реально зарегистрированы в main.py:_setup_hotkeys (только 2 из 4
# DEFAULT_HOTKEYS из gui/hotkeys.py — START/STOP не подключены к callback).
GLOBAL_HOTKEYS: tuple[tuple[str, str], ...] = (
    ("Переключить запись (старт/стоп)", "Ctrl+Alt+T"),
    ("Пауза/продолжить запись", "Ctrl+Alt+P"),
)


class HotkeysView(QDialog):
    """Немодальный диалог-справка по горячим клавишам приложения."""

    def __init__(
        self,
        desktop_actions: DesktopActionRegistry,
        parent: QWidget | None = None,
    ) -> None:
        """
        Инициализация диалога.

        Args:
            desktop_actions: Реестр in-app действий с их shortcut'ами.
            parent: Родительский виджет.
        """
        super().__init__(parent)
        self._desktop_actions = desktop_actions
        self.setWindowTitle("Горячие клавиши")
        self.setModal(False)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Настройка интерфейса диалога."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            Theme.MARGIN, Theme.MARGIN, Theme.MARGIN, Theme.MARGIN
        )
        layout.setSpacing(Theme.SPACING)

        layout.addWidget(self._create_global_group())
        layout.addWidget(self._create_app_group())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        self._apply_accessibility_metadata()

    def _create_global_group(self) -> QGroupBox:
        """Группа глобальных горячих клавиш (работают без фокуса окна)."""
        group = QGroupBox("Глобальные (работают, даже если окно не активно)")
        group_layout = QVBoxLayout(group)
        self._global_table = self._build_table(GLOBAL_HOTKEYS)
        group_layout.addWidget(self._global_table)
        return group

    def _create_app_group(self) -> QGroupBox:
        """Группа in-app горячих клавиш (требуют фокуса окна)."""
        group = QGroupBox("В приложении (требуют фокуса окна)")
        group_layout = QVBoxLayout(group)
        self._app_table = self._build_table(self._app_hotkey_rows())
        group_layout.addWidget(self._app_table)
        return group

    def _app_hotkey_rows(self) -> tuple[tuple[str, str], ...]:
        """Строки таблицы in-app клавиш из реестра desktop-действий."""
        return tuple(
            (action.title, action.shortcut)
            for action in self._desktop_actions.all()
            if action.shortcut
        )

    @staticmethod
    def _build_table(rows: tuple[tuple[str, str], ...]) -> QTableWidget:
        """Построить read-only таблицу «действие / комбинация»."""
        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels(["Действие", "Комбинация"])
        vertical_header = table.verticalHeader()
        if vertical_header is not None:
            vertical_header.setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for row, (title, shortcut) in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(title))
            table.setItem(row, 1, QTableWidgetItem(shortcut))
        return table

    def _apply_accessibility_metadata(self) -> None:
        """Назначение accessibility metadata для таблиц горячих клавиш."""
        apply_accessible_metadata(
            self._global_table,
            "Глобальные горячие клавиши",
            "Список горячих клавиш, работающих даже когда окно приложения "
            "не в фокусе.",
        )
        apply_accessible_metadata(
            self._app_table,
            "Горячие клавиши приложения",
            "Список горячих клавиш, работающих только при открытом и "
            "активном окне приложения.",
        )
