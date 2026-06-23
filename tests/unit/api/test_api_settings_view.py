"""Тесты для вкладки настроек API."""

from __future__ import annotations

import types
from collections.abc import Callable
from pathlib import Path

import pytest

from gui.views import api_settings_view


class _SignalStub:
    """Простейший сигнал для тестового QTimer."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[..., None]] = []

    def connect(self, callback) -> None:
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs) -> None:
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class _FakeTimer:
    """Тестовая замена QTimer."""

    def __init__(self, parent=None) -> None:
        self.parent = parent
        self.timeout = _SignalStub()
        self.started_interval: int | None = None
        self.stopped = False

    def start(self, interval: int) -> None:
        self.started_interval = interval
        self.stopped = False

    def stop(self) -> None:
        self.stopped = True


class _NoopThread:
    """Поток-заглушка без автоматического выполнения target."""

    def __init__(self, target, args=(), daemon: bool = False) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        """Не выполнять target автоматически в unit-тесте."""


class _FakeCursor:
    """Тестовый курсор для окна логов."""

    def movePosition(self, operation) -> None:
        self.operation = operation


class _FakePlainTextEdit:
    """Тестовая замена QPlainTextEdit."""

    class LineWrapMode:
        NoWrap = object()

    def __init__(self, *args, **kwargs) -> None:
        self._plain_text = ""
        self._cursor = _FakeCursor()
        self._enabled = True

    def setReadOnly(self, read_only: bool) -> None:
        self._read_only = read_only

    def setLineWrapMode(self, mode) -> None:
        self._line_wrap_mode = mode

    def setMaximumBlockCount(self, count: int) -> None:
        self._maximum_block_count = count

    def setFont(self, font) -> None:
        self._font = font

    def setPlainText(self, text: str) -> None:
        self._plain_text = text

    def toPlainText(self) -> str:
        return self._plain_text

    def appendPlainText(self, text: str) -> None:
        if self._plain_text:
            self._plain_text = f"{self._plain_text}\n{text}"
        else:
            self._plain_text = text

    def textCursor(self) -> _FakeCursor:
        return self._cursor

    def setTextCursor(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor

    def ensureCursorVisible(self) -> None:
        self._cursor_visible = True


class _FakeClipboard:
    """Тестовый буфер обмена."""

    def __init__(self) -> None:
        self.text_value = ""

    def setText(self, text: str) -> None:
        self.text_value = text


class _FakeGuiApplication:
    """Тестовая замена QGuiApplication."""

    clipboard_instance = _FakeClipboard()

    @staticmethod
    def clipboard() -> _FakeClipboard:
        return _FakeGuiApplication.clipboard_instance


@pytest.fixture
def api_view_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> types.SimpleNamespace:
    """Подготовка среды для тестов ApiSettingsView."""

    def set_style_sheet(self, style: str) -> None:
        self._style_sheet = style

    def style_sheet(self) -> str:
        return getattr(self, "_style_sheet", "")

    monkeypatch.setattr(
        api_settings_view.QLabel,
        "setStyleSheet",
        set_style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        api_settings_view.QLabel,
        "styleSheet",
        style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        api_settings_view.QGroupBox,
        "setStyleSheet",
        set_style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        api_settings_view.QGroupBox,
        "styleSheet",
        style_sheet,
        raising=False,
    )
    monkeypatch.setattr(
        api_settings_view.QFormLayout,
        "addRow",
        lambda self, *args: None,
        raising=False,
    )
    monkeypatch.setattr(
        api_settings_view.QLineEdit,
        "setEchoMode",
        lambda self, mode: setattr(self, "_echo_mode", mode),
        raising=False,
    )
    monkeypatch.setattr(
        api_settings_view.QLineEdit,
        "EchoMode",
        types.SimpleNamespace(Password=object(), Normal=object()),
        raising=False,
    )
    monkeypatch.setattr(api_settings_view, "QTimer", _FakeTimer)
    monkeypatch.setattr(
        api_settings_view.threading,
        "Thread",
        _NoopThread,
    )
    monkeypatch.setattr(
        api_settings_view,
        "QPlainTextEdit",
        _FakePlainTextEdit,
    )
    monkeypatch.setattr(
        api_settings_view,
        "QGuiApplication",
        _FakeGuiApplication,
    )
    monkeypatch.setattr(
        api_settings_view,
        "open_api_logs_folder",
        lambda: None,
    )

    log_dir = tmp_path / "api"
    monkeypatch.setattr(
        api_settings_view,
        "get_api_log_dir",
        lambda: log_dir,
    )
    _FakeGuiApplication.clipboard_instance = _FakeClipboard()

    return types.SimpleNamespace(log_dir=log_dir)


def _complete_log_refresh(view: api_settings_view.ApiSettingsView) -> None:
    """Доставить в UI результат фонового чтения лога."""
    result = view._read_log_update()
    view._on_logs_load_completed(view._log_request_id, result, None)


def test_copy_token_to_clipboard(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Токен копируется в буфер обмена."""

    view = api_settings_view.ApiSettingsView()
    view.set_settings(5000, "secret-token")

    view._on_copy_token_clicked()

    clipboard = _FakeGuiApplication.clipboard()
    assert clipboard.text_value == "secret-token"
    assert (
        view._status_label.text() == "Статус: токен скопирован в буфер обмена."
    )


def test_copy_token_empty_value(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Пустой токен не копируется и показывает подсказку."""

    view = api_settings_view.ApiSettingsView()
    view.set_settings(5000, "")

    view._on_copy_token_clicked()

    clipboard = _FakeGuiApplication.clipboard()
    assert clipboard.text_value == ""
    assert (
        view._status_label.text()
        == "Статус: токен не задан. Сначала введите и сохраните его."
    )


def test_toggle_token_visibility_shows_and_hides(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Кнопка переключает echo mode токена и свой текст."""

    view = api_settings_view.ApiSettingsView()
    echo_mode = api_settings_view.QLineEdit.EchoMode

    assert view._token_edit._echo_mode is echo_mode.Password
    assert view._toggle_token_visibility_btn.text() == "Показать"

    view._on_toggle_token_visibility(True)
    assert view._token_edit._echo_mode is echo_mode.Normal
    assert view._toggle_token_visibility_btn.text() == "Скрыть"

    view._on_toggle_token_visibility(False)
    assert view._token_edit._echo_mode is echo_mode.Password
    assert view._toggle_token_visibility_btn.text() == "Показать"


def test_refresh_logs_without_file(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """При отсутствии файла показывается понятное сообщение."""

    view = api_settings_view.ApiSettingsView()

    view.refresh_logs(show_loading_state=True)
    _complete_log_refresh(view)

    assert view._log_source_label.text() == "Журнал API: файл не найден"
    assert (
        view._log_view.toPlainText()
        == "Журнал API пока не создан. Запустите сервер, чтобы начать запись."
    )
    assert view._log_status_label.text() == "Журнал API пуст или ещё не создан"


def test_set_status_updates_controls(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Статус сервера обновляет подписи и доступность кнопок."""

    view = api_settings_view.ApiSettingsView()

    view.set_status(True, "API сервер запущен")

    assert view._status_label.text() == "Статус: API сервер запущен"
    assert view._server_state_label.text() == "API сервер запущен"
    assert view._start_btn.isEnabled() is False
    assert view._stop_btn.isEnabled() is True
    assert view._restart_btn.isEnabled() is True

    view.set_status(False)

    assert view._status_label.text() == "Статус: Сервер остановлен"
    assert view._server_state_label.text() == "Сервер остановлен"
    assert view._start_btn.isEnabled() is True
    assert view._stop_btn.isEnabled() is False
    assert view._restart_btn.isEnabled() is False


def test_refresh_logs_reload_after_file_truncate(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """После ротации/обнуления файла журнал перечитывается заново."""

    view = api_settings_view.ApiSettingsView()
    log_dir = api_view_environment.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "api_2026-03-28.log"
    log_file.write_text("line-1\nline-2\n", encoding="utf-8")

    view.refresh_logs()
    _complete_log_refresh(view)
    assert "line-2" in view._log_view.toPlainText()

    # Имитируем ротацию: новый файл меньше предыдущего оффсета.
    log_file.write_text("new-line\n", encoding="utf-8")

    view.refresh_logs()
    _complete_log_refresh(view)
    assert view._log_view.toPlainText().strip() == "new-line"


def test_auto_refresh_disabled_until_view_is_shown(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Автообновление не стартует до показа вкладки."""

    view = api_settings_view.ApiSettingsView()

    assert view._log_timer.started_interval is None
    assert (
        view._log_status_label.text()
        == "Автообновление включится при открытии вкладки"
    )


def test_show_and_hide_event_toggle_auto_refresh(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Показ вкладки включает автообновление, скрытие выключает."""

    view = api_settings_view.ApiSettingsView()

    view.showEvent(None)
    assert view._log_timer.started_interval == 1000

    view.hideEvent(None)
    assert view._log_timer.stopped is True
    assert (
        view._log_status_label.text()
        == "Автообновление включится при открытии вкладки"
    )


def test_refresh_logs_error_updates_error_state(
    qapp,
    api_view_environment: types.SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ошибка чтения журнала переводит виджет в error state."""

    view = api_settings_view.ApiSettingsView()
    monkeypatch.setattr(
        view,
        "_resolve_current_log_path",
        lambda: (_ for _ in ()).throw(OSError("boom")),
    )

    view.refresh_logs(show_loading_state=True)
    view._load_logs_worker(view._log_request_id)

    assert "boom" in view._log_status_label.text()


def test_refresh_logs_starts_background_request(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Обновление логов запускает фоновый запрос и loading state."""

    view = api_settings_view.ApiSettingsView()

    view.refresh_logs(show_loading_state=True)

    assert view._log_refresh_in_progress is True
    assert view._log_status_label.text() == "Загрузка журнала API..."


def test_accessibility_metadata_is_assigned(
    qapp,
    api_view_environment: types.SimpleNamespace,
) -> None:
    """Ключевые controls вкладки API получают accessibility metadata."""

    view = api_settings_view.ApiSettingsView()

    assert view._port_spinbox._accessible_name == "Порт API"
    assert view._token_edit._accessible_name == "API токен"
    assert (
        view._toggle_token_visibility_btn._accessible_name
        == "Показать или скрыть API токен"
    )
    assert view._start_btn._accessible_name == "Запустить API сервер"
    assert view._log_view._accessible_name == "Журнал API"
