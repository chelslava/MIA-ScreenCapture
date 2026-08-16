"""
Кольцевой буфер для live-логов GUI.
=====================================

Потокобезопасный буфер с ограниченным размером (ring-buffer) для
отображения live-логов в GUI API-вкладке.  Предотвращает неограниченный
рост памяти при высокой интенсивности логирования (burst mode).

Ключевые свойства:
- Новые строки вытесняют старые при достижении лимита (FIFO eviction).
- Потокобезопасен: все публичные методы защищены ``threading.Lock``.
- Поддерживает дебаунс: сброс «грязного» флага позволяет UI опрашивать
  буфер только при наличии новых данных.
"""

from __future__ import annotations

import threading
from collections import deque

_DEFAULT_MAX_LINES = 2000
_DEFAULT_MAX_LINE_LENGTH = 2048


class GuiLogBuffer:
    """Потокобезопасный кольцевой буфер строк лога для GUI.

    Args:
        max_lines: Максимальное число строк в буфере.
            При превышении самые старые строки вытесняются.
        max_line_length: Максимальная длина одной строки в символах.
            Более длинные строки обрезаются с суффиксом ``…``.
    """

    def __init__(
        self,
        max_lines: int = _DEFAULT_MAX_LINES,
        max_line_length: int = _DEFAULT_MAX_LINE_LENGTH,
    ) -> None:
        if max_lines < 1:
            raise ValueError(
                f"max_lines должен быть >= 1, получено {max_lines}"
            )
        if max_line_length < 1:
            raise ValueError(
                f"max_line_length должен быть >= 1, получено {max_line_length}"
            )
        self._max_lines = max_lines
        self._max_line_length = max_line_length
        self._lines: deque[str] = deque(maxlen=max_lines)
        self._lock = threading.Lock()
        self._dirty = False
        self._evicted_count = 0

    @property
    def max_lines(self) -> int:
        """Максимальное количество строк в буфере."""
        return self._max_lines

    def append(self, text: str) -> None:
        """Добавляет строки из ``text`` в буфер.

        Текст разбивается по символу новой строки.  Пустые строки
        игнорируются.  Строки длиннее ``max_line_length`` обрезаются.

        Args:
            text: Одна или несколько строк лога, разделённых ``\\n``.
        """
        if not text:
            return
        lines = text.splitlines()
        with self._lock:
            before = len(self._lines)
            for line in lines:
                if not line:
                    continue
                if len(line) > self._max_line_length:
                    line = line[: self._max_line_length - 1] + "…"
                self._lines.append(line)
            # Подсчёт вытесненных строк (deque с maxlen делает это само)
            added = len(lines)
            capacity = self._max_lines - before
            if added > capacity:
                self._evicted_count += added - capacity
            self._dirty = True

    def get_text(self) -> str:
        """Возвращает всё содержимое буфера как единую строку.

        Returns:
            Строки буфера, соединённые символом перевода строки.
        """
        with self._lock:
            return "\n".join(self._lines)

    def is_dirty(self) -> bool:
        """Возвращает ``True``, если буфер изменился с последнего сброса.

        Returns:
            Признак наличия несброшенных изменений.
        """
        with self._lock:
            return self._dirty

    def clear_dirty(self) -> None:
        """Сбрасывает флаг изменений (dirty-флаг).

        Вызывается GUI-потоком после отрисовки содержимого буфера.
        """
        with self._lock:
            self._dirty = False

    def clear(self) -> None:
        """Полностью очищает буфер и сбрасывает счётчики."""
        with self._lock:
            self._lines.clear()
            self._dirty = False
            self._evicted_count = 0

    def __len__(self) -> int:
        """Возвращает текущее количество строк в буфере."""
        with self._lock:
            return len(self._lines)

    @property
    def evicted_count(self) -> int:
        """Суммарное число строк, вытесненных из буфера с момента создания.

        Полезно для диагностики и тестирования burst-сценариев.
        """
        with self._lock:
            return self._evicted_count
