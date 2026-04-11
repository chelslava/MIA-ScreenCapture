"""Вспомогательные функции доступности для GUI."""

from __future__ import annotations

from typing import Any


def apply_accessible_metadata(
    widget: Any,
    accessible_name: str,
    accessible_description: str,
    tooltip: str | None = None,
) -> None:
    """
    Назначить accessible metadata и tooltip для виджета.

    Args:
        widget: Целевой виджет Qt или тестовый mock.
        accessible_name: Читаемое имя элемента.
        accessible_description: Описание назначения элемента.
        tooltip: Дополнительная tooltip-подсказка.
    """
    widget._accessible_name = accessible_name
    widget._accessible_description = accessible_description

    set_name = getattr(widget, "setAccessibleName", None)
    if callable(set_name):
        set_name(accessible_name)

    set_description = getattr(widget, "setAccessibleDescription", None)
    if callable(set_description):
        set_description(accessible_description)

    if tooltip is None:
        return

    widget._tooltip = tooltip
    set_tooltip = getattr(widget, "setToolTip", None)
    if callable(set_tooltip):
        set_tooltip(tooltip)
