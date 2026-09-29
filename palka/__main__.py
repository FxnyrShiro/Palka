"""Точка входа. `python3 -m palka` запускает браузер."""
import sys

from PyQt6.QtWidgets import QApplication

from .theme import apply_dark_app_theme
from .browser_window import MiniBrowser


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_app_theme()

    window = MiniBrowser()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
