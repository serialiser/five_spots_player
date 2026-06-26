import sys
import os


def resource_path(relative_path):
    """Resolve asset paths for both development and PyInstaller frozen mode."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return relative_path
