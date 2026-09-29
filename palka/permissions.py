"""Диалог запроса разрешений (микрофон, камера, геолокация и т.п.)."""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
)
from PyQt6.QtWebEngineCore import QWebEnginePermission

from .constants import (
    COLOR_MINT, COLOR_LAVENDER, FONT_MONO,
)


PERMISSION_NAMES = {
    QWebEnginePermission.PermissionType.MediaAudioCapture:
        ("Микрофон", "🎤"),
    QWebEnginePermission.PermissionType.MediaVideoCapture:
        ("Камера", "📷"),
    QWebEnginePermission.PermissionType.MediaAudioVideoCapture:
        ("Микрофон и камера", "🎥"),
    QWebEnginePermission.PermissionType.DesktopVideoCapture:
        ("Захват экрана", "🖥"),
    QWebEnginePermission.PermissionType.DesktopAudioVideoCapture:
        ("Захват экрана и звука", "🖥"),
    QWebEnginePermission.PermissionType.Geolocation:
        ("Геолокация", "📍"),
    QWebEnginePermission.PermissionType.Notifications:
        ("Уведомления", "🔔"),
    QWebEnginePermission.PermissionType.ClipboardReadWrite:
        ("Буфер обмена", "📋"),
    QWebEnginePermission.PermissionType.LocalFontsAccess:
        ("Локальные шрифты", "🔤"),
}


class PermissionDialog(QDialog):
    def __init__(self, origin: str, name: str, icon: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Запрос доступа")
        self.setModal(True)
        self.setMinimumWidth(380)

        # Импорт здесь — чтобы не создавать циклическую зависимость
        from .styles import DIALOG_QSS
        self.setStyleSheet(DIALOG_QSS)

        L = QVBoxLayout(self)
        L.setContentsMargins(20, 18, 20, 18)
        L.setSpacing(14)

        title = QLabel(f"{icon}  Запрос: {name}")
        title.setStyleSheet(
            f"color: {COLOR_MINT}; font-size: 14px; font-weight: bold;")
        L.addWidget(title)

        L.addWidget(QLabel("Сайт запрашивает доступ. Разрешить?"))

        origin_label = QLabel(origin)
        origin_label.setWordWrap(True)
        origin_label.setStyleSheet(
            f"color: {COLOR_LAVENDER}; padding: 6px 10px;"
            f"background: rgba(179,136,255,0.08);"
            f"border: 1px solid rgba(179,136,255,0.2);"
            f"border-radius: 6px;"
        )
        L.addWidget(origin_label)

        B = QHBoxLayout()
        B.addStretch(1)

        deny = QPushButton("Запретить")
        deny.setObjectName("deny")
        deny.clicked.connect(self.reject)
        B.addWidget(deny)

        allow = QPushButton("Разрешить")
        allow.setDefault(True)
        allow.clicked.connect(self.accept)
        B.addWidget(allow)

        L.addLayout(B)
