"""
Пакет CLI
=========

Этот пакет содержит функциональность интерфейса командной строки:
- Разбор аргументов с argparse
- Выполнение команд для режима без интерфейса
"""

from .parser import create_parser, process_args

__all__ = ["create_parser", "process_args"]
