"""Desktop movement helpers: keep a continuous walk across wrapped screen edges."""

import math


def wrap_desktop_x(x, screen_left, screen_width, widget_width):
    """Return a wrap-around x. Re-enter only after the whole window has exited.

    The valid travel cycle is [left-widget_width, left+screen_width].
    Movement overshoot is retained and no heading reversal is required.
    """
    if not all(math.isfinite(v) for v in (x, screen_left, screen_width, widget_width)):
        raise ValueError("Non-finite desktop movement coordinate")
    if screen_width <= 0 or widget_width <= 0:
        raise ValueError("Desktop and window widths must be positive")
    start = screen_left - widget_width
    end = screen_left + screen_width
    if x < start or x > end:
        x = start + (x - start) % (screen_width + widget_width)
    return x
