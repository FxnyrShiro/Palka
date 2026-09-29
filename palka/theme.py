"""Тёмная палитра приложения.

Chromium читает палитру Qt и передаёт сайтам prefers-color-scheme: dark.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPalette, QColor, QGuiApplication

from .constants import (
    COLOR_BG, COLOR_TEXT, COLOR_MINT,
)


def apply_dark_app_theme() -> None:
    # Официальный Qt 6.5+ способ (если есть в сборке)
    try:
        QGuiApplication.styleHints().setColorScheme(Qt.ColorScheme.Dark)
    except (AttributeError, TypeError):
        pass

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Base,            QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor("#0f1a17"))
    pal.setColor(QPalette.ColorRole.Text,            QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Button,          QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(COLOR_TEXT))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(COLOR_MINT))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.ToolTipBase,     QColor(COLOR_BG))
    pal.setColor(QPalette.ColorRole.ToolTipText,     QColor(COLOR_TEXT))
    QGuiApplication.setPalette(pal)
