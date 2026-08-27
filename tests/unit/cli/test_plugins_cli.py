"""
Unit-тесты для CLI команд плагинов (Issue #124).
================================================
"""

from __future__ import annotations

import pytest

from cli.parser import (
    create_parser,
    print_plugin_info,
    print_plugins_list,
    process_args,
)


def test_cli_parser_plugins_modes() -> None:
    """Проверка распознавания аргументов плагинов парсером."""
    parser = create_parser()

    # --plugins-list
    args = parser.parse_args(["--plugins-list"])
    conf = process_args(args)
    assert conf["mode"] == "plugins_list"

    # --plugins-info
    args = parser.parse_args(["--plugins-info", "my_plugin"])
    conf = process_args(args)
    assert conf["mode"] == "plugins_info"
    assert conf["plugin_name"] == "my_plugin"

    # --plugins-enable
    args = parser.parse_args(["--plugins-enable", "my_plugin"])
    conf = process_args(args)
    assert conf["mode"] == "plugins_enable"
    assert conf["plugin_name"] == "my_plugin"

    # --plugins-disable
    args = parser.parse_args(["--plugins-disable", "my_plugin"])
    conf = process_args(args)
    assert conf["mode"] == "plugins_disable"
    assert conf["plugin_name"] == "my_plugin"


def test_print_plugins_list_empty(capsys: pytest.CaptureFixture) -> None:
    """Вывод пустого списка плагинов."""
    print_plugins_list([])
    captured = capsys.readouterr()
    assert "не обнаружены" in captured.out


def test_print_plugins_list_items(capsys: pytest.CaptureFixture) -> None:
    """Вывод списка с плагинами."""
    plugins = [
        {
            "name": "watermark",
            "version": "1.0.0",
            "status": "enabled",
            "description": "Водяной знак",
        }
    ]
    print_plugins_list(plugins)
    captured = capsys.readouterr()
    assert "watermark" in captured.out
    assert "ENABLED" in captured.out
    assert "Водяной знак" in captured.out


def test_print_plugin_info(capsys: pytest.CaptureFixture) -> None:
    """Вывод детальной информации о плагине."""
    info = {
        "name": "watermark",
        "version": "1.0.0",
        "status": "enabled",
        "author": "MIA Team",
        "homepage": "https://example.com",
        "description": "Добавление водяного знака",
        "config": {"text": "demo"},
        "settings_schema": {"type": "object"},
    }
    print_plugin_info(info)
    captured = capsys.readouterr()
    assert "watermark" in captured.out
    assert "MIA Team" in captured.out
    assert "ENABLED" in captured.out
