"""Стилизованные Q-виджеты, используемые в нескольких местах."""
from PyQt6.QtWidgets import QTabBar
from PyQt6.QtCore import Qt

from .constants import (
    COLOR_BG, COLOR_MINT, COLOR_LAVENDER, FONT_MONO,
)


class StyledTabBar(QTabBar):
    """Мятно-лавандовый tab bar без стрелок прокрутки.

    Невыбранные вкладки — лавандовые, выбранная — мятная.
    Минимальная ширина 0, максимальная 200px, эллипс по правому краю.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setMovable(True)
        self.setUsesScrollButtons(False)
        self.setElideMode(Qt.TextElideMode.ElideRight)

        self.setStyleSheet(f"""
            QTabBar {{
                background-color: {COLOR_BG};
                border: none;
            }}
            QTabBar::tab {{
                background-color: rgba(179, 136, 255, 0.10);
                color: {COLOR_LAVENDER};
                padding: 5px 14px;
                margin-right: 2px;
                border: 1px solid rgba(179, 136, 255, 0.25);
                border-bottom: 2px solid transparent;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                font-family: {FONT_MONO};
                font-size: 11px;
                min-width: 0px;
                max-width: 200px;
            }}
            QTabBar::tab:selected {{
                background-color: rgba(0, 255, 170, 0.14);
                color: {COLOR_MINT};
                border: 1px solid rgba(0, 255, 170, 0.45);
                border-bottom: 2px solid {COLOR_MINT};
                font-weight: bold;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: rgba(179, 136, 255, 0.22);
                color: #d4c4ff;
            }}
        """)
