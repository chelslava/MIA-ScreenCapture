"""
Geometry utilities for working with coordinates.
================================================

Provides functions for validating and normalizing
rectangular coordinates for screen capture area.
"""


def validate_rect_coords(
    x1: int, y1: int, x2: int, y2: int, *, strict: bool = False
) -> tuple[int, int, int, int]:
    """
    Validate and normalize rectangle coordinates.

    Processes coordinates of rectangle corners (x1, y1) and (x2, y2),
    ensuring correct order and minimum area size.

    Args:
        x1, y1: Coordinates of the first corner (can be top-left or bottom-right).
        x2, y2: Coordinates of the second corner.
        strict: If True, raises ValueError for invalid coordinates.
            If False (default), automatically normalizes coordinates via min/max.

    Returns:
        Tuple (left, top, right, bottom) - normalized coordinates.

    Raises:
        ValueError: If strict=True and coordinates are invalid:
            - Wrong number of coordinates
            - x2 <= x1 or y2 <= y1
            - Negative coordinates

    Examples:
        # Normalization (automatic ordering):
        >>> validate_rect_coords(800, 600, 100, 100)
        (100, 100, 800, 600)

        # Strict validation (exception on wrong order):
        >>> validate_rect_coords(800, 600, 100, 100, strict=True)
        Traceback (most recent call last):
            ...
        ValueError: x2 must be greater than x1

        # Minimum size:
        >>> validate_rect_coords(100, 100, 105, 105)
        (100, 100, 110, 110)
    """
    left = min(x1, x2)
    top = min(y1, y2)
    right = max(x1, x2)
    bottom = max(y1, y2)

    # Enforce minimum size of 10x10 pixels
    if right - left < 10:
        right = left + 10
    if bottom - top < 10:
        bottom = top + 10

    if strict:
        # Checks only when strict=True
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
