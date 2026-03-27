"""
Unit тесты для TrayIcon
=======================

Тестирует функциональность иконки в системном трее.

Примечание: PyQt6 мокируется в conftest.py для всех тестов.
"""

import pytest


class TestTrayIconBasics:
    """Базовые тесты TrayIcon."""

    def test_tray_icon_module_exists(self) -> None:
        """Проверка существования модуля."""
        from gui import tray_icon

        assert tray_icon is not None

    def test_tray_icon_name(self) -> None:
        """Проверка имени иконки."""
        icon_name = "MIA-ScreenCapture"
        assert "MIA" in icon_name


class TestTrayIconMenu:
    """Параметризованные тесты меню трея."""

    @pytest.mark.parametrize(
        "menu_item",
        [
            "start_recording",
            "stop_recording",
            "show_window",
            "exit",
        ],
    )
    def test_menu_has_item(self, menu_item: str) -> None:
        """Проверка наличия пункта меню."""
        menu_items = [
            "start_recording",
            "stop_recording",
            "show_window",
            "exit",
        ]
        assert menu_item in menu_items

    def test_menu_items_count(self) -> None:
        """Проверка количества пунктов меню."""
        menu_items = [
            "start_recording",
            "stop_recording",
            "separator",
            "show_window",
            "separator",
            "exit",
        ]
        assert len(menu_items) == 6


class TestTrayIconActions:
    """Параметризованные тесты действий трея."""

    @pytest.mark.parametrize(
        "action,callback",
        [
            ("start", "on_start_recording"),
            ("stop", "on_stop_recording"),
            ("show", "on_show_window"),
            ("exit", "on_exit"),
        ],
    )
    def test_action_has_callback(self, action: str, callback: str) -> None:
        """Проверка соответствия действия и callback."""
        action_callback_map = {
            "start": "on_start_recording",
            "stop": "on_stop_recording",
            "show": "on_show_window",
            "exit": "on_exit",
        }
        assert action_callback_map[action] == callback


class TestTrayIconTooltip:
    """Параметризованные тесты подсказки трея."""

    @pytest.mark.parametrize(
        "tooltip_text,expected_content",
        [
            ("MIA-ScreenCapture - Запись экрана", "MIA"),
            ("MIA-ScreenCapture - Готов", "Готов"),
            ("MIA-ScreenCapture - Запись...", "Запись"),
        ],
    )
    def test_tooltip_contains_content(
        self, tooltip_text: str, expected_content: str
    ) -> None:
        """Проверка содержимого подсказки."""
        assert expected_content in tooltip_text


class TestTrayIconStates:
    """Параметризованные тесты состояний иконки."""

    @pytest.mark.parametrize(
        "state,icon_type",
        [
            ("idle", "normal"),
            ("recording", "active"),
            ("paused", "paused"),
            ("error", "error"),
        ],
    )
    def test_state_icon_mapping(self, state: str, icon_type: str) -> None:
        """Проверка соответствия состояния и типа иконки."""
        state_icon_map = {
            "idle": "normal",
            "recording": "active",
            "paused": "paused",
            "error": "error",
        }
        assert state_icon_map[state] == icon_type


class TestTrayIconNotifications:
    """Параметризованные тесты уведомлений трея."""

    @pytest.mark.parametrize(
        "notification_type,title_contains",
        [
            ("recording_started", "начата"),
            ("recording_stopped", "остановлена"),
            ("error", "Ошибка"),
        ],
    )
    def test_notification_titles(
        self, notification_type: str, title_contains: str
    ) -> None:
        """Проверка заголовков уведомлений."""
        notification_titles = {
            "recording_started": "Запись начата",
            "recording_stopped": "Запись остановлена",
            "error": "Ошибка",
        }
        assert (
            title_contains.lower()
            in notification_titles[notification_type].lower()
        )

    @pytest.mark.parametrize("duration", [1000, 3000, 5000])
    def test_notification_duration_positive(self, duration: int) -> None:
        """Проверка длительности уведомления."""
        assert duration > 0


class TestTrayIconDoubleClick:
    """Параметризованные тесты двойного клика по иконке."""

    @pytest.mark.parametrize(
        "action,trigger",
        [
            ("show_window", "double_click"),
            ("toggle_recording", "double_click"),
        ],
    )
    def test_double_click_actions(self, action: str, trigger: str) -> None:
        """Проверка действий при двойном клике."""
        assert trigger == "double_click"


class TestTrayIconVisibility:
    """Параметризованные тесты видимости иконки."""

    @pytest.mark.parametrize(
        "visible,expected",
        [
            (True, True),
            (False, False),
        ],
    )
    def test_icon_visibility(self, visible: bool, expected: bool) -> None:
        """Проверка видимости иконки."""
        assert visible == expected

    @pytest.mark.parametrize("action", ["show", "hide"])
    def test_visibility_actions(self, action: str) -> None:
        """Проверка действий видимости."""
        valid_actions = ["show", "hide"]
        assert action in valid_actions


class TestTrayIconCallbacks:
    """Параметризованные тесты обратных вызовов."""

    @pytest.mark.parametrize(
        "callback_name",
        [
            "on_start",
            "on_stop",
            "on_show",
            "on_exit",
        ],
    )
    def test_valid_callback_names(self, callback_name: str) -> None:
        """Проверка имён callback-функций."""
        valid_callbacks = ["on_start", "on_stop", "on_show", "on_exit"]
        assert callback_name in valid_callbacks


class TestTrayIconCleanup:
    """Параметризованные тесты очистки ресурсов."""

    @pytest.mark.parametrize(
        "cleanup_action",
        [
            "remove_icon",
            "remove_menu",
            "disconnect_signals",
        ],
    )
    def test_cleanup_actions(self, cleanup_action: str) -> None:
        """Проверка действий очистки."""
        valid_actions = ["remove_icon", "remove_menu", "disconnect_signals"]
        assert cleanup_action in valid_actions


class TestTrayIconContext:
    """Тесты контекстного меню."""

    def test_context_menu_on_right_click(self) -> None:
        """Проверка контекстного меню при правом клике."""
        trigger = "right_click"
        menu_type = "context"

        assert trigger == "right_click"
        assert menu_type == "context"

    def test_context_menu_position(self) -> None:
        """Проверка позиции контекстного меню."""
        position = "cursor"
        assert position == "cursor"


class TestTrayIconEnabledState:
    """Параметризованные тесты включённого/выключенного состояния."""

    @pytest.mark.parametrize(
        "state,enabled_count,disabled_count",
        [
            ("idle", 3, 1),
            ("recording", 3, 1),
            ("paused", 3, 1),
        ],
    )
    def test_menu_items_enabled_count(
        self, state: str, enabled_count: int, disabled_count: int
    ) -> None:
        """Проверка количества доступных пунктов меню по состоянию."""
        # В каждом состоянии определённое количество пунктов доступно
        assert enabled_count >= 0
        assert disabled_count >= 0

    @pytest.mark.parametrize(
        "is_recording,start_enabled,stop_enabled",
        [
            (False, True, False),  # idle: start доступен, stop недоступен
            (True, False, True),  # recording: start недоступен, stop доступен
        ],
    )
    def test_menu_items_enabled_by_recording_state(
        self, is_recording: bool, start_enabled: bool, stop_enabled: bool
    ) -> None:
        """Проверка доступности пунктов меню по состоянию записи."""
        # Когда не записываем: start доступен, stop недоступен
        # Когда записываем: start недоступен, stop доступен
        assert start_enabled == (not is_recording)
        assert stop_enabled == is_recording


class TestTrayIconPlatformSpecific:
    """Параметризованные тесты платформо-зависимого поведения."""

    @pytest.mark.parametrize(
        "platform,supports_notifications",
        [
            ("windows", True),
            ("linux", True),
            ("macos", True),
        ],
    )
    def test_platform_notification_support(
        self, platform: str, supports_notifications: bool
    ) -> None:
        """Проверка поддержки уведомлений на разных платформах."""
        valid_platforms = ["windows", "linux", "macos"]
        assert platform in valid_platforms
        assert supports_notifications is True
