"""
Общие GUI-константы
===================

Единая точка значений, разделяемых несколькими виджетами.
"""

from enum import IntEnum
from typing import Final

# Такт мигания рамки активной записи (#161): используется оверлеем
# recording_indicator и будет переиспользован плавающим виджетом (#158)
RECORDING_INDICATOR_TICK_MS: Final[int] = 450


class SidebarPage(IntEnum):
    """Страницы главного окна (индексы сайдбара = индексы content stack).

    Единственный источник порядка страниц: `MainWindowUIBuilderMixin`
    строит страницы в этом порядке, а переключение выполняется через
    `MainWindow._show_page` — прямое `setCurrentRow(<int>)` запрещено.
    """

    RECORD = 0
    RECORDINGS = 1
    SETTINGS = 2
    SCHEDULER = 3
    DIAGNOSTICS = 4
    API = 5
