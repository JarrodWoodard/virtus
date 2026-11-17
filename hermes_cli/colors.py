"""Shared ANSI color utilities for Hermes CLI modules."""

import os
import sys


def should_use_color() -> bool:
    """Return True when colored output is appropriate."""
    if os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb":
        return False
    return bool(sys.stdout.isatty())


class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    # Dextral blue family (virtus). The names stay semantic so call sites keep reading naturally;
    # the values are truecolor so a terminal's own 16-colour palette cannot turn "yellow" into the
    # dark orange this fork removed.
    RED = "\033[38;2;91;110;245m"      # bad      #5B6EF5
    GREEN = "\033[38;2;35;181;211m"    # good     #23B5D3
    YELLOW = "\033[38;2;127;179;224m"  # warn     #7FB3E0
    BLUE = "\033[38;2;29;155;240m"     # accent   #1D9BF0
    MAGENTA = "\033[38;2;127;141;247m" # critical #7F8DF7
    CYAN = "\033[38;2;93;184;245m"     # light    #5DB8F5


def color(text: str, *codes) -> str:
    """Apply color codes to text (only when color output is appropriate)."""
    if not should_use_color():
        return text
    return "".join(codes) + text + Colors.RESET
