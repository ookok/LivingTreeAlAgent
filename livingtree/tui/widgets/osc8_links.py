"""OSC 8 Hyperlinks — Clickable URLs in terminal output.

Enables OSC 8 escape sequences so URLs in the transcript are
Cmd+Click/Ctrl+Click openable on supported terminals (iTerm2, Terminal.app,
Ghostty, Kitty, WezTerm, Alacritty, Windows Terminal, modern gnome-terminal).

Usage:
    link = osc8_link("https://example.com", "Click here")
    # Wraps text in OSC 8 hyperlink escape sequence
"""

from __future__ import annotations

import re

OSC = "\033]"
ST = "\033" + "\\"
BEL = "\007"


def osc8_link(url: str, text: str | None = None) -> str:
    """Create an OSC 8 hyperlink in terminal output.

    Args:
        url: The target URL (must be a fully-formed URL)
        text: Display text (defaults to the URL itself)

    Returns:
        String with OSC 8 escape sequences wrapping the text
    """
    if not _is_supported_terminal():
        return text or url

    display = text if text is not None else url
    return f"{OSC}8;;{url}{BEL}{display}{OSC}8;;{BEL}"


def convert_links(text: str) -> str:
    """Auto-convert URLs in text to OSC 8 hyperlinks.

    Recognizes http://, https:// patterns and wraps them.
    """
    if not _is_supported_terminal():
        return text

    url_pattern = re.compile(r'(https?://[^\s<>"\'\]\)]+)')
    return url_pattern.sub(lambda m: osc8_link(m.group(1)), text)


def markdown_links(text: str) -> str:
    """Convert Markdown [text](url) links to OSC 8 hyperlinks."""
    if not _is_supported_terminal():
        return text

    pattern = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')
    return pattern.sub(lambda m: osc8_link(m.group(2), m.group(1)), text)


def _is_supported_terminal() -> bool:
    """Check if the current terminal supports OSC 8 hyperlinks."""
    import os
    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()

    supported_terms = {
        "xterm-kitty", "wezterm", "alacritty",
        "ghostty", "screen", "tmux",
    }
    supported_programs = {
        "iterm.app", "apple_terminal", "windows terminal",
        "vscode", "warp",
    }

    if term in supported_terms:
        return True
    if term_program in supported_programs:
        return True
    if os.environ.get("WT_SESSION"):
        return True
    if os.environ.get("KITTY_PID"):
        return True
    if os.environ.get("ALACRITTY_LOG"):
        return True
    if os.environ.get("WEZTERM_EXECUTABLE"):
        return True

    return False
