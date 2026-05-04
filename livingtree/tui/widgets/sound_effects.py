"""Utility: play system notification sounds."""
from __future__ import annotations


def play_success() -> None:
    """Play a success notification sound."""
    _beep(800, 0.1)


def play_error() -> None:
    """Play an error notification sound."""
    _beep(400, 0.2)


def play_click() -> None:
    """Play a soft click sound."""
    _beep(1200, 0.05)


def _beep(freq: int, duration: float) -> None:
    """Cross-platform beep."""
    try:
        import winsound
        winsound.Beep(freq, int(duration * 1000))
    except Exception:
        try:
            import os
            if os.name == "nt":
                import ctypes
                ctypes.windll.kernel32.Beep(freq, int(duration * 1000))
        except Exception:
            pass


def notify_with_sound(title: str, message: str, severity: str = "info") -> None:
    """Combined notification: system tray + sound."""
    if severity == "error":
        play_error()
    elif severity == "warning":
        play_error()
    else:
        play_click()

    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x40)
    except Exception:
        pass
