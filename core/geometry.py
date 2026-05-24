"""
Геометрические утилиты для работы с координатами.
===============================================

Предоставляет функции для валидации и нормализации
прямоугольных координат области захвата экрана.
"""


def validate_rect_coords(
    x1: int, y1: int, x2: int, y2: int, *, strict: bool = False
) -> tuple[int, int, int, int]:
    """
    Валидирует и нормализует координаты прямоугольника.

    Функция обрабатывает координаты углов прямоугольника (x1, y1) и (x2, y2),
    обеспечивая корректный порядок и минимальный размер области.

    Args:
        x1, y1: Координаты первого угла (может быть как левым верхним, так и
            правым нижним).
        x2, y2: Координаты второго угла.
        strict: Если True, выбрасывает ValueError при некорректных координатах.
            Если False (по умолчанию), автоматически нормализует координаты
            через min/max.

    Returns:
        Кортеж (left, top, right, bottom) - нормализованные координаты.

    Raises:
        ValueError: Если strict=True и координаты не проходят валидацию:
            - Неверное количество координат
            - x2 <= x1 или y2 <= y1
            - Отрицательные координаты

    Examples:
        # Нормализация (автоматический порядок):
        >>> validate_rect_coords(800, 600, 100, 100)
        (100, 100, 800, 600)

        # Строгая валидация (исключение при неверном порядке):
        >>> validate_rect_coords(800, 600, 100, 100, strict=True)
        Traceback (most recent call last):
            ...
        ValueError: x2 must be greater than x1

        # Минимальный размер:
        >>> validate_rect_coords(100, 100, 105, 105)
        (100, 100, 110, 110)
    """
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)

    # Принудительный минимальный размер 10x10 пикселей
    if right - left < 10:
        right = left + 10
    if bottom - top < 10:
        bottom = top + 10

    if strict:
        # Проверки только при strict=True
        if x2 <= x1:
            raise ValueError(f"x2 must be greater than x1: x1={x1}, x2={x2}")
        if y2 <= y1:
            raise ValueError(f"y2 must be greater than y1: y1={y1}, y2={y2}")
        if left < 0 or top < 0:
            raise ValueError(
                f"Coordinates must not be negative: "
                f"[{left}, {top}, {right}, {bottom}]"
            )

    return left, top, right, bottom
