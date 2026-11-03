"""
Тесты страницы настроек SettingsPage
====================================

Проверяют двухпанельную компоновку «категории + содержимое»: список
категорий, переключение страниц и оборачивание каждого раздела в
QScrollArea (виджеты больше не сжимаются и не перекрываются).

`QStackedWidget` патчится на время создания страницы: без этого общий
auto-mock из conftest копит вызовы между тестами сессии.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from gui.views.settings_page import (
    CATEGORY_TITLES,
    SettingsCategory,
    SettingsPage,
)


@contextmanager
def _make_page() -> Iterator[tuple[SettingsPage, list[MagicMock]]]:
    """Создать страницу с mock-представлениями в изолированном стеке."""
    views = [MagicMock() for _ in range(len(SettingsCategory))]
    with patch("gui.views.settings_page.QStackedWidget", MagicMock()):
        page = SettingsPage(*views)
    yield page, views


class TestSettingsPageStructure:
    """Структура страницы: категории, страницы, прокрутка."""

    def test_category_list_contains_all_categories(self) -> None:
        """Список категорий содержит все категории по порядку."""
        with _make_page() as (page, _views):
            assert page._category_list.count() == len(SettingsCategory)
            items = [
                page._category_list.item(i).text()
                for i in range(page._category_list.count())
            ]
            assert items == [
                CATEGORY_TITLES[category] for category in SettingsCategory
            ]

    def test_category_titles_are_unique(self) -> None:
        """Заголовки категорий не повторяются."""
        titles = list(CATEGORY_TITLES.values())
        assert len(titles) == len(set(titles))

    def test_every_view_wrapped_in_scroll_area(self) -> None:
        """Каждое представление обёрнуто в QScrollArea своей категории."""
        with _make_page() as (page, views):
            assert len(page._pages.addWidget.call_args_list) == len(views)
            for index, view in enumerate(views):
                page_widget = page._pages.addWidget.call_args_list[index].args[
                    0
                ]
                # View лежит внутри body-контейнера scroll area
                # (обёртка с прижимом к верху против растяжения строк)
                scroll_containers = [
                    child
                    for child in page_widget.layout()._widgets
                    if getattr(child, "widget", None) is not None
                    and child.widget() is not None
                    and getattr(child.widget(), "layout", lambda: None)()
                    is not None
                    and view in child.widget().layout()._widgets
                ]
                assert scroll_containers, (
                    f"Категория {index}: view не обёрнут в QScrollArea"
                )

    def test_accessibility_metadata_on_category_list(self) -> None:
        """Список категорий имеет accessibility-метаданные."""
        with _make_page() as (page, _views):
            assert page._category_list._accessible_name == "Категории настроек"


class TestSettingsPageNavigation:
    """Переключение категорий."""

    def test_show_category_switches_page(self) -> None:
        """show_category переключает страницу стека."""
        with _make_page() as (page, _views):
            page.show_category(int(SettingsCategory.POST_PROCESSING))

            page._pages.setCurrentIndex.assert_called_with(
                int(SettingsCategory.POST_PROCESSING)
            )
            assert page.current_category() == int(
                SettingsCategory.POST_PROCESSING
            )

    def test_show_category_clamps_out_of_range(self) -> None:
        """Индексы вне диапазона зажимаются допустимыми значениями."""
        with _make_page() as (page, _views):
            page.show_category(99)
            assert page.current_category() == len(SettingsCategory) - 1

            page.show_category(-5)
            assert page.current_category() == 0

    def test_current_category_defaults_to_first(self) -> None:
        """После show_category(0) текущая категория — первая."""
        with _make_page() as (page, _views):
            page.show_category(0)

            assert page.current_category() == int(SettingsCategory.VIDEO)
