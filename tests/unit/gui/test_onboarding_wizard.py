"""Тесты мастера первого запуска и поиска настроек (#172)."""

from types import SimpleNamespace
from unittest.mock import MagicMock


class TestOnboardingWizard:
    """Мастер первого запуска (#172)."""

    def test_three_pages_added(self) -> None:
        """Мастер добавляет приветствие, сводку и проверку готовности."""
        from unittest.mock import patch

        from gui.views.onboarding_wizard import OnboardingWizard

        with patch("gui.views.onboarding_wizard.QWizardPage") as page_cls:
            OnboardingWizard(
                {"Область захвата": "Весь экран"},
                SimpleNamespace(issues=()),
            )
            # QWizardPage замокан: каждая из 3 страниц создавалась
            assert page_cls.call_count == 3

    def test_settings_summary_used(self) -> None:
        """Сводка настроек передаётся в конструктор без исключений."""
        from gui.views.onboarding_wizard import OnboardingWizard

        wizard = OnboardingWizard(
            {"Область захвата": "Весь экран", "Аудио": "Микрофон"},
            SimpleNamespace(issues=()),
        )
        assert wizard is not None

    def test_non_snapshot_readiness_handled(self) -> None:
        """Строка вместо readiness — страница-заглушка без исключений."""
        from gui.views.onboarding_wizard import OnboardingWizard

        wizard = OnboardingWizard(
            {"Область захвата": "Весь экран"}, "unavailable"
        )
        assert wizard is not None


class TestOnboardingFlag:
    """Флаг onboarding_completed в конфиге (#172)."""

    def test_default_false(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Мастер показывается при первом запуске."""
        from config import AppSettings

        assert AppSettings().onboarding_completed is False

    def test_roundtrip(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Флаг переживает сохранение и перезагрузку."""
        from config import ConfigManager

        path = tmp_path / "config.json"
        manager = ConfigManager(path)
        manager.settings.onboarding_completed = True
        assert manager.save() is True

        reloaded = ConfigManager(path)
        assert reloaded.settings.onboarding_completed is True


class TestSettingsSearch:
    """Поиск по настройкам (#172)."""

    @staticmethod
    def _make_page(views: list) -> object:
        from gui.views.settings_page import SettingsPage

        page = SettingsPage.__new__(SettingsPage)
        page._views = tuple(views)
        page.show_category = MagicMock()
        return page

    def test_search_switches_to_matching_category(self) -> None:
        """Запрос по подписи виджета переключает раздел (#172)."""

        # Порядок категорий: VIDEO, AUDIO, OUTPUT, APPEARANCE, POST, ADVANCED
        video_view = MagicMock()
        video_view.findChildren.return_value = [MagicMock(text=lambda: "FPS")]
        audio_view = MagicMock()
        audio_view.findChildren.return_value = [
            MagicMock(text=lambda: "Шумоподавление микрофона")
        ]
        others = [MagicMock() for _ in range(4)]
        for view in others:
            view.findChildren.return_value = [MagicMock(text=lambda: "x")]

        page = self._make_page([video_view, audio_view, *others])
        page._on_search_changed("шумоподавление")

        # AUDIO — индекс 1 в SettingsCategory
        page.show_category.assert_called_once_with(1)

    def test_empty_query_is_noop(self) -> None:
        """Пустой запрос не переключает категорию."""

        views = [MagicMock() for _ in range(6)]
        page = self._make_page(views)

        page._on_search_changed("  ")

        page.show_category.assert_not_called()

    def test_no_match_keeps_current_category(self) -> None:
        """Без совпадений категория не меняется."""

        views = [MagicMock() for _ in range(6)]
        for view in views:
            view.findChildren.return_value = [
                MagicMock(text=lambda: "нет совпадений")
            ]
        page = self._make_page(views)

        page._on_search_changed("qqqqq")

        page.show_category.assert_not_called()
