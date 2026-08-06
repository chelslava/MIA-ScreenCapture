"""
Тесты LoadingOverlay — полупрозрачного оверлея загрузки (#105).
"""

from gui.views.loading_overlay import LoadingOverlay


class TestLoadingOverlayInit:
    """Проверки инициализации оверлея."""

    def test_default_message(self) -> None:
        """По умолчанию отображается сообщение «Загрузка...»."""
        overlay = LoadingOverlay()

        assert overlay._message == "Загрузка..."
        assert overlay._label is not None

    def test_custom_message(self) -> None:
        """Кастомное сообщение передаётся в оверлей."""
        overlay = LoadingOverlay(message="Проверка FFmpeg...")

        assert overlay._message == "Проверка FFmpeg..."
        assert overlay._label is not None

    def test_hidden_by_default(self) -> None:
        """Оверлей скрыт сразу после создания."""
        overlay = LoadingOverlay()

        assert overlay.isVisible() is False

    def test_label_styled_for_visibility(self) -> None:
        """Label получает белый жирный текст для читаемости на оверлее."""
        overlay = LoadingOverlay()

        style = overlay._label.styleSheet()
        assert "color: #FFFFFF" in style
        assert "font-weight: bold" in style


class TestLoadingOverlayVisibility:
    """Проверки show/hide."""

    def test_show_makes_overlay_visible(self) -> None:
        """show() делает оверлей видимым."""
        overlay = LoadingOverlay()

        overlay.show()

        assert overlay.isVisible() is True

    def test_hide_makes_overlay_invisible(self) -> None:
        """hide() скрывает оверлей."""
        overlay = LoadingOverlay()
        overlay.show()

        overlay.hide()

        assert overlay.isVisible() is False

    def test_show_copies_parent_geometry(self) -> None:
        """show() с родителем растягивает оверлей на его геометрию."""
        from PyQt6.QtWidgets import QWidget

        parent = QWidget()
        parent.geometry = lambda: (0, 0, 800, 600)
        overlay = LoadingOverlay()
        overlay.parentWidget = lambda: parent
        captured: list[tuple] = []
        overlay.setGeometry = lambda rect: captured.append(rect)

        overlay.show()

        assert captured == [(0, 0, 800, 600)]


class TestLoadingOverlayMessage:
    """Проверки обновления сообщения."""

    def test_set_message_updates_label(self) -> None:
        """setMessage() обновляет текст label."""
        overlay = LoadingOverlay()

        overlay.setMessage("Загрузка окон...")

        assert overlay._message == "Загрузка окон..."
        assert overlay._label.text() == "Загрузка окон..."
