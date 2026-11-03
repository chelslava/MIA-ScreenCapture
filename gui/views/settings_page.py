"""
Страница «Настройки»: категории + панель содержимого
=====================================================

Раньше все шесть групп настроек укладывались в одну колонку без
прокрутки — в окне ограниченной высоты виджеты сжимались и перекрывали
друг друга. Теперь каждая категория открывается на всю высоту страницы
внутри ``QScrollArea`` — по образцу приложения «Параметры» Windows 11.
"""

from __future__ import annotations

from enum import IntEnum

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from gui.accessibility import apply_accessible_metadata
from gui.styles.theme import Theme

# Ширина колонки категорий: вмещает самый длинный заголовок без обрезки
_CATEGORY_LIST_WIDTH = 176


class SettingsCategory(IntEnum):
    """Категории страницы настроек.

    Значение = индекс в списке категорий и в QStackedWidget; порядок
    следования членов задаёт порядок страниц.
    """

    VIDEO = 0
    AUDIO = 1
    OUTPUT = 2
    APPEARANCE = 3
    POST_PROCESSING = 4
    ADVANCED = 5


# Заголовки категорий; содержимое передаётся конструктору в порядке
# SettingsCategory (video, audio, output, appearance, post, advanced).
CATEGORY_TITLES: dict[SettingsCategory, str] = {
    SettingsCategory.VIDEO: "Видео",
    SettingsCategory.AUDIO: "Аудио",
    SettingsCategory.OUTPUT: "Файлы и вывод",
    SettingsCategory.APPEARANCE: "Внешний вид",
    SettingsCategory.POST_PROCESSING: "Постобработка",
    SettingsCategory.ADVANCED: "Расширенные",
}


class SettingsPage(QWidget):
    """Двухпанельная страница настроек главного окна.

    Args:
        video_view: Виджет настроек видео.
        audio_view: Виджет настроек аудио.
        output_view: Виджет пути вывода.
        appearance_view: Виджет внешнего вида (тема, язык, обновления).
        post_processing_view: Виджет конвейера постобработки.
        tunables_view: Виджет расширенных параметров записи.
        parent: Родительский виджет.
    """

    def __init__(
        self,
        video_view: QWidget,
        audio_view: QWidget,
        output_view: QWidget,
        appearance_view: QWidget,
        post_processing_view: QWidget,
        tunables_view: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._views: tuple[QWidget, ...] = (
            video_view,
            audio_view,
            output_view,
            appearance_view,
            post_processing_view,
            tunables_view,
        )

        self._setup_ui()
        self._apply_accessibility_metadata()

    # ------------------------------------------------------------------
    # Построение интерфейса
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        """Построить двухпанельную компоновку: категории + содержимое."""
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

        self._category_list = QListWidget()
        self._category_list.setFixedWidth(_CATEGORY_LIST_WIDTH)
        self._category_list.setObjectName("settingsCategories")
        self._category_list.currentRowChanged.connect(
            self._on_category_changed
        )
        for category in SettingsCategory:
            title = CATEGORY_TITLES[category]
            item = QListWidgetItem(title)
            item.setToolTip(title)
            self._category_list.addItem(item)
        layout.addWidget(self._category_list)

        self._pages = QStackedWidget()
        for index, view in enumerate(self._views):
            self._pages.addWidget(
                self._build_category_page(
                    CATEGORY_TITLES[SettingsCategory(index)], view
                )
            )
        layout.addWidget(self._pages, stretch=1)

    def _build_category_page(self, title: str, view: QWidget) -> QWidget:
        """Построить страницу категории: заголовок + прокручиваемое тело.

        Args:
            title: Заголовок категории (подпись страницы и header).
            view: Виджет с настройками категории.

        Returns:
            Готовая страница для QStackedWidget.
        """
        page = QWidget()
        page_layout = QVBoxLayout()
        page_layout.setContentsMargins(
            Theme.MARGIN * 3, Theme.MARGIN * 2, Theme.MARGIN * 3, Theme.MARGIN
        )
        page_layout.setSpacing(Theme.SPACING)
        page.setLayout(page_layout)

        header = QLabel(title)
        header.setStyleSheet(Theme.title_style())
        page_layout.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        # Контент тянется по ширине, прокрутка — только по вертикали
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # Обёртка с прижимом к верху: без неё widgetResizable растянет
        # view на всю высоту viewport и строки разъедутся по вертикали
        body = QWidget()
        body_layout = QVBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(view)
        body_layout.addStretch()
        body.setLayout(body_layout)
        scroll.setWidget(body)
        page_layout.addWidget(scroll, stretch=1)
        return page

    def _apply_accessibility_metadata(self) -> None:
        """Назначить accessibility-метаданные списку категорий."""
        apply_accessible_metadata(
            self._category_list,
            "Категории настроек",
            "Переключение между разделами настроек: видео, аудио, файлы, "
            "внешний вид, постобработка и расширенные параметры.",
        )

    # ------------------------------------------------------------------
    # Публичный API
    # ------------------------------------------------------------------

    def show_category(self, index: int) -> None:
        """Выбрать категорию по индексу.

        Args:
            index: Индекс категории (0..``len(CATEGORY_TITLES) - 1``);
                вне диапазона — зажимается допустимыми значениями.
        """
        index = max(0, min(index, self._category_list.count() - 1))
        self._category_list.setCurrentRow(index)

    def current_category(self) -> int:
        """Получить индекс текущей категории.

        Returns:
            Индекс выбранной категории или -1, если ничего не выбрано.
        """
        return self._category_list.currentRow()

    # ------------------------------------------------------------------
    # Обработчики
    # ------------------------------------------------------------------

    def _on_category_changed(self, row: int) -> None:
        """Синхронизировать содержимое с выбором в списке категорий.

        Args:
            row: Индекс выбранной строки списка категорий.
        """
        if row >= 0:
            self._pages.setCurrentIndex(row)
