"""Small utility module -- negative control fixture for the config-effectiveness
experiment. Same style/domain as positive_control.py, but genuinely correct --
no planted bug. See controls.md for the pre-registered false-catch criterion.
"""


def average(numbers):
    """Return the arithmetic mean of a non-empty list of numbers."""
    total = sum(numbers)
    return total / len(numbers)


def clamp(value, low, high):
    """Clamp value into the inclusive range [low, high]."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def is_palindrome(text):
    """Return True if text reads the same forwards and backwards (case-insensitive)."""
    cleaned = text.lower()
    return cleaned == cleaned[::-1]
