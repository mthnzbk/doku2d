"""Clipboard operations that preserve text when access is denied."""
from sfml.window import Clipboard


def get_text():
    try:
        return Clipboard.get_string()
    except RuntimeError:
        return None


def set_text(text):
    """Verify the write before a cut is allowed to remove its selection."""
    try:
        Clipboard.set_string(str(text))
        return Clipboard.get_string() == str(text)
    except RuntimeError:
        return False
