"""Цвета, шрифты, пути, аппаратные константы."""
import os
from pathlib import Path


# ==================== ПАЛИТРА ====================

COLOR_BG         = "#0a1210"
COLOR_BG_LIGHT   = "rgba(255, 255, 255, 0.04)"
COLOR_BG_PANEL   = "#0f1a17"
COLOR_BORDER     = "rgba(0, 255, 170, 0.15)"
COLOR_BORDER_HL  = "rgba(0, 255, 170, 0.5)"
COLOR_MINT       = "#00ffaa"
COLOR_LAVENDER   = "#b388ff"
COLOR_LAVENDER_D = "#a99bc9"
COLOR_TEXT       = "#e0f2fe"
COLOR_TEXT_DIM   = "#64748b"
COLOR_DANGER     = "#ff5c7a"

FONT_MONO = '"JetBrains Mono", "Segoe UI", monospace'


# ==================== ПУТИ ====================

CONFIG_DIR = Path.home() / ".config" / "micro-browser"
DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads"

# Имя профиля QtWebEngine (создаётся в ~/.local/share/browser.sh/)
PROFILE_NAME = "micro-browser-profile"


# ==================== USB ====================

SWITCH_VID = 0x0955
SWITCH_PID = 0x7321
PACKET_SIZE = 4096

# "auto"   — реально работать с USB
# "logger" — только логировать (отладка без устройства)
USB_MODE = os.environ.get("USB_MODE", "auto")
