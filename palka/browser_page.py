"""QWebEnginePage с инжектами темы, WebUSB-шима и менеджера паролей."""
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWebEngineCore import (
    QWebEnginePage, QWebEngineScript,
)
from PyQt6.QtWebChannel import QWebChannel

from .js import (
    passwords_js,
    webusb_shim_js,
    qwebchannel_js,
)
from .usb_bridge import UsbBridge
from .passwords import PasswordBridge


class MicroPage(QWebEnginePage):
    """Одна вкладка = одна QWebEnginePage со своими скриптами и мостами.

    Инжекты:
      - theme_and_scrollbar.js   (DocumentCreation, все фреймы)
      - qwebchannel.js + webusb_shim.js  (DocumentCreation, все фреймы)
      - passwords.js             (DocumentReady, только верхний фрейм)

    Мосты:
      - usbBridge  — WebUSB через pyusb
      - pwBridge   — запрос/сохранение паролей

    Сигнал pageFullScreenRequested(bool) эмитится, когда сайт просит
    fullscreen (YouTube, Twitch). Внешний код решает, что делать с окном.
    """

    pageFullScreenRequested = pyqtSignal(bool)

    def __init__(self, profile, pw_manager, parent=None):
        super().__init__(profile, parent)

        # ===== Мосты через QWebChannel =====
        self.bridge = UsbBridge(self, self)
        self.channel = QWebChannel(self)
        self.channel.registerObject("usbBridge", self.bridge)

        self.pw_bridge = PasswordBridge(self, pw_manager, self)
        self.channel.registerObject("pwBridge", self.pw_bridge)

        self.setWebChannel(self.channel)

        # ===== Инжекты =====
        self._insert_script(
            name="webusb_shim",
            source=qwebchannel_js() + "\n;\n" + webusb_shim_js(),
            point=QWebEngineScript.InjectionPoint.DocumentCreation,
            subframes=True,
        )
        self._insert_script(
            name="pw_manager",
            source=passwords_js(),
            point=QWebEngineScript.InjectionPoint.DocumentReady,
            subframes=False,
        )

        # ===== Fullscreen =====
        self.fullScreenRequested.connect(self._on_fs_req)

    def _insert_script(self, name, source, point, subframes):
        s = QWebEngineScript()
        s.setName(name)
        s.setInjectionPoint(point)
        s.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
        s.setRunsOnSubFrames(subframes)
        s.setSourceCode(source)
        self.scripts().insert(s)

    def _on_fs_req(self, request):
        # Принимаем запрос от сайта и эмитим наружу
        request.accept()
        self.pageFullScreenRequested.emit(request.toggleOn())

    # ===== Фильтр шума в консоли =====
    def javaScriptConsoleMessage(self, level, msg, line, src):
        # Игнорируем внутренние схемы Chromium
        if src.startswith(("devtools://", "chrome://", "chrome-extension://")):
            return
        # Игнорируем известный спам, не имеющий отношения к делу
        if "Unsupported URL scheme" in msg:
            return
        if "ResizeObserver loop" in msg:
            return
        if "Unable to preventDefault inside passive event listener" in msg:
            return
        # Остальное — только ошибки
        if "error" in str(level).lower() or "Error" in msg:
            print(f"[JS] {msg}  [{src}:{line}]", flush=True)

    def certificateError(self, error):
        # Не блокируем самоподписанные сертификаты (для отладки)
        print(f"[TLS] {error.description()}", flush=True)
        return True
