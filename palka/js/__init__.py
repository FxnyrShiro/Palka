"""Встроенные JS-скрипты, инжектируемые в каждую страницу.

Сами тексты лежат в .js-файлах рядом. Здесь — только загрузчики,
чтобы browser_page.py не возился с путями.
"""
from pathlib import Path


_JS_DIR = Path(__file__).parent


def _read(name: str) -> str:
    return (_JS_DIR / name).read_text(encoding="utf-8")


def passwords_js() -> str:
    """Автозаполнение и сохранение логинов/паролей."""
    return _read("passwords.js")


def webusb_shim_js() -> str:
    """Подмена navigator.usb для работы WebRCM с Tegra RCM."""
    return _read("webusb_shim.js")


def qwebchannel_js() -> str:
    """Исходник qwebchannel.js из встроенных ресурсов Qt.

    Загружаем через QFile, потому что :/qtwebchannel/qwebchannel.js
    доступен только Qt-приложению, а нам нужно вставить его текст
    в тот же мир, что и наш шим.
    """
    from PyQt6.QtCore import QFile, QIODevice

    for path in (":/qtwebchannel/qwebchannel.js",
                 "qrc:///qtwebchannel/qwebchannel.js"):
        f = QFile(path)
        if f.open(QIODevice.OpenModeFlag.ReadOnly):
            try:
                return bytes(f.readAll().data()).decode("utf-8")
            finally:
                f.close()
    raise RuntimeError("Не удалось загрузить qwebchannel.js из ресурсов Qt")
