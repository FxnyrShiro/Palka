"""
Palka — кастомный браузер на QtWebEngine.

Пакет разбит на модули:
  constants       — цвета, шрифты, константы
  theme           — тёмная палитра для Qt-виджетов
  storage         — JSON-хранилище, обфускация
  passwords       — менеджер паролей
  bookmarks       — закладки
  history         — история
  downloads       — загрузки + всплывающая панель
  managers_ui     — диалог со всеми менеджерами
  permissions     — диалог разрешений
  usb_bridge      — мост WebUSB (Tegra RCM)
  browser_page    — QWebEnginePage с инжектами
  browser_window  — главное окно
  widgets         — стилизованный QTabBar и прочие мелочи
  js              — встроенные JS-скрипты (тема, пароли, webusb-шим)
"""
import os

# Chromium flags — должны быть установлены ДО импорта PyQt6.QtWebEngineCore.
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (
    "--enable-experimental-web-platform-features "
    "--enable-features=WebAssembly,WebRtcAllowInputVolumeAdjustment "  # Убрали SmoothScrolling отсюда
    "--disable-background-timer-throttling "
    "--disable-backgrounding-occluded-windows "
    "--disable-renderer-backgrounding "
    "--disable-features=CalculateNativeWinOcclusion,OverlayScrollbar "
    "--enable-smooth-scrolling "  # Вот этот флаг отвечает за плавность
    "--enable-gpu-rasterization "
#    "--enable-oop-rasterization " # Отключите, если скроллинг идет "рывками"
    "--ignore-gpu-blocklist "
    "--num-raster-threads=4 "
    "--disable-gpu-vsync "

)

__version__ = "0.1.0"
