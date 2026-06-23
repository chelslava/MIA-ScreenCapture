"""Тесты AppearanceView на моках PyQt6."""

from PyQt6.QtWidgets import QApplication

from gui.views.appearance_view import AppearanceView


class TestAppearanceView:
    """Проверки AppearanceView с мокированным PyQt6."""

    def test_init_populates_theme_combo(self, qapp: QApplication) -> None:
        """Комбобокс темы должен содержать ровно 3 пункта."""
        view = AppearanceView()

        assert view._theme_combo.count() == 3

    def test_default_mode_is_system(self, qapp: QApplication) -> None:
        """До явного выбора текущим режимом должен быть 'system'."""
        view = AppearanceView()

        assert view.get_current_mode() == "system"

    def test_set_current_mode_dark(self, qapp: QApplication) -> None:
        """Программная установка темы должна обновлять индекс комбобокса."""
        view = AppearanceView()
        view.set_current_mode("dark")

        assert view.get_current_mode() == "dark"

    def test_set_current_mode_unknown_is_noop(
        self, qapp: QApplication
    ) -> None:
        """Неизвестный режим не должен менять текущий выбор."""
        view = AppearanceView()
        view.set_current_mode("light")
        view.set_current_mode("not-a-real-mode")

        assert view.get_current_mode() == "light"

    def test_theme_changed_emitted_on_index_change(
        self, qapp: QApplication
    ) -> None:
        """Изменение индекса комбобокса должно эмитить theme_changed."""
        view = AppearanceView()
        received: list[str] = []
        view.theme_changed.connect(received.append)

        view._on_theme_index_changed(2)

        assert received == ["dark"]

    def test_theme_changed_ignores_out_of_range_index(
        self, qapp: QApplication
    ) -> None:
        """Некорректный индекс не должен приводить к эмиту сигнала."""
        view = AppearanceView()
        received: list[str] = []
        view.theme_changed.connect(received.append)

        view._on_theme_index_changed(-1)
        view._on_theme_index_changed(99)

        assert received == []

    def test_accessibility_metadata_applied(self, qapp: QApplication) -> None:
        """Комбобокс темы должен получить accessible name/description."""
        view = AppearanceView()

        assert view._theme_combo._accessible_name == "Тема оформления"
        assert view._theme_combo._accessible_description
