"""Общие QSS-строки для диалогов и попапов."""
from .constants import (
    COLOR_BG, COLOR_BG_LIGHT, COLOR_BG_PANEL,
    COLOR_BORDER, COLOR_BORDER_HL,
    COLOR_MINT, COLOR_LAVENDER, COLOR_TEXT,
    FONT_MONO,
)


DIALOG_QSS = f"""
QDialog, QMessageBox {{ background-color: {COLOR_BG}; }}
QLabel {{ color: {COLOR_TEXT}; font-family: {FONT_MONO}; font-size: 12px; }}
QTabWidget::pane {{
    border: 1px solid rgba(0, 255, 170, 0.15);
    background: {COLOR_BG};
    border-radius: 6px;
}}
QTabBar::tab {{
    background: rgba(179, 136, 255, 0.10);
    color: {COLOR_LAVENDER};
    padding: 6px 16px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    border: 1px solid rgba(179, 136, 255, 0.25);
    border-bottom: none;
    font-family: {FONT_MONO};
    font-size: 11px;
}}
QTabBar::tab:selected {{
    background: rgba(0, 255, 170, 0.14);
    color: {COLOR_MINT};
    border: 1px solid rgba(0, 255, 170, 0.45);
    border-bottom: none;
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    background: rgba(179, 136, 255, 0.22);
    color: #d4c4ff;
}}
QListWidget {{
    background: rgba(255, 255, 255, 0.02);
    color: {COLOR_TEXT};
    border: 1px solid rgba(0, 255, 170, 0.10);
    border-radius: 6px;
    font-family: {FONT_MONO};
    font-size: 11px;
    outline: none;
}}
QListWidget::item {{
    padding: 5px 8px;
    border-bottom: 1px solid rgba(0, 255, 170, 0.06);
}}
QListWidget::item:selected {{
    background: rgba(0, 255, 170, 0.18);
    color: #ffffff;
}}
QListWidget::item:hover:!selected {{
    background: rgba(179, 136, 255, 0.10);
}}
QPushButton {{
    background-color: rgba(0, 255, 170, 0.08);
    color: {COLOR_MINT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-family: {FONT_MONO};
    font-size: 12px;
    min-width: 80px;
}}
QPushButton:hover {{
    background-color: rgba(0, 255, 170, 0.18);
    color: #ffffff;
    border-color: {COLOR_BORDER_HL};
}}
QPushButton:pressed {{
    background-color: {COLOR_MINT};
    color: {COLOR_BG};
}}
QPushButton#deny {{
    background-color: rgba(179, 136, 255, 0.08);
    color: {COLOR_LAVENDER};
    border: 1px solid rgba(179, 136, 255, 0.2);
}}
QPushButton#deny:hover {{
    background-color: rgba(179, 136, 255, 0.2);
    color: #ffffff;
}}
QPushButton#deny:pressed {{
    background-color: {COLOR_LAVENDER};
    color: {COLOR_BG};
}}
QLineEdit {{
    background-color: {COLOR_BG_LIGHT};
    color: {COLOR_TEXT};
    border: 1px solid {COLOR_BORDER};
    border-radius: 6px;
    padding: 4px 10px;
    font-family: {FONT_MONO};
    font-size: 12px;
}}
QLineEdit:focus {{
    border: 1px solid {COLOR_BORDER_HL};
    background-color: rgba(0, 255, 170, 0.04);
}}
"""
