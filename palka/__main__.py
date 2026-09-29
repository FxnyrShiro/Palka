"""Точка входа. `python3 -m palka` запускает браузер."""
import sys

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat
from .theme import apply_dark_app_theme
from .browser_window import MiniBrowser


def main():
    fmt = QSurfaceFormat.defaultFormat()
    fmt.setSwapInterval(0)
    QSurfaceFormat.setDefaultFormat(fmt)
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_app_theme()

    window = MiniBrowser()
    if len(sys.argv) > 1:
        arg = sys.argv[-1]
        if arg.startswith(("http://", "https://", "file://")):
            window.add_new_tab(QUrl(arg), "Открыть")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
