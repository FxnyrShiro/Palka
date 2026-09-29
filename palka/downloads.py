"""Менеджер загрузок + выпадающая панель прогресса.

Особенности Qt 6:
  - QWebEngineDownloadRequest больше не имеет сигнала `finished`,
    используется `stateChanged` + `isFinishedChanged`.
  - downloadRequested отдаёт item, который надо явно `accept()`.

Автосохранение идёт в ~/Downloads с дедупликацией имени.
"""
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QProgressBar,
    QScrollArea, QSizePolicy,
)
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest

from .constants import (
    COLOR_BG, COLOR_BG_PANEL, COLOR_BG_LIGHT,
    COLOR_BORDER, COLOR_BORDER_HL,
    COLOR_MINT, COLOR_LAVENDER, COLOR_TEXT, COLOR_TEXT_DIM, COLOR_DANGER,
    FONT_MONO, DEFAULT_DOWNLOAD_DIR,
)


class DownloadManager(QObject):
    """Следит за QWebEngineDownloadRequest и держит список активных/завершённых."""

    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.downloads = []
        DEFAULT_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    def register_profile(self, profile) -> None:
        profile.downloadRequested.connect(self._on_download_requested)

    # ---------- обработчики Qt ----------

    def _on_download_requested(self, item: QWebEngineDownloadRequest) -> None:
        try:
            fname = item.downloadFileName()
            path = DEFAULT_DOWNLOAD_DIR / fname
            path = self._dedupe_path(path)

            item.setDownloadDirectory(str(path.parent))
            item.setDownloadFileName(path.name)
            item.accept()

            rec = {
                "item": item,
                "path": str(path),
                "name": path.name,
                "received": 0,
                "total": item.totalBytes(),
                "finished": False,
                "success": False,
                "state": "progress",
            }
            self.downloads.append(rec)

            item.receivedBytesChanged.connect(lambda r=rec: self._on_progress(r))
            item.totalBytesChanged.connect(lambda r=rec: self._on_progress(r))
            item.stateChanged.connect(lambda s, r=rec: self._on_state(s, r))
            try:
                item.isFinishedChanged.connect(lambda r=rec: self._on_isfinished(r))
            except AttributeError:
                pass

            print(f"[DL] start: {path}", flush=True)
            self.changed.emit()
        except Exception as e:
            print(f"[DL] error: {e}", flush=True)
            try:
                item.cancel()
            except Exception:
                pass

    @staticmethod
    def _dedupe_path(path: Path) -> Path:
        """file.zip, file (1).zip, file (2).zip, ..."""
        if not path.exists():
            return path
        stem, ext = path.stem, path.suffix
        for n in range(1, 1000):
            cand = path.parent / f"{stem} ({n}){ext}"
            if not cand.exists():
                return cand
        return path

    def _on_progress(self, rec) -> None:
        try:
            rec["received"] = rec["item"].receivedBytes()
            t = rec["item"].totalBytes()
            if t > 0:
                rec["total"] = t
        except RuntimeError:
            return
        self.changed.emit()

    def _on_state(self, state, rec) -> None:
        try:
            DS = QWebEngineDownloadRequest.DownloadState
            if state == DS.DownloadCompleted:
                rec["finished"] = True
                rec["success"] = True
                rec["state"] = "done"
                print(f"[DL] completed: {rec['path']}", flush=True)
            elif state == DS.DownloadCancelled:
                rec["finished"] = True
                rec["success"] = False
                rec["state"] = "cancelled"
            elif state == DS.DownloadInterrupted:
                rec["finished"] = True
                rec["success"] = False
                rec["state"] = "interrupted"
            elif state == DS.DownloadInProgress:
                rec["state"] = "progress"
        except Exception as e:
            print(f"[DL] state handler error: {e}", flush=True)
        self.changed.emit()

    def _on_isfinished(self, rec) -> None:
        """Fallback, если stateChanged не сработал."""
        try:
            if rec["item"].isFinished() and not rec["finished"]:
                rec["finished"] = True
                p = Path(rec["path"])
                rec["success"] = p.exists() and p.stat().st_size > 0
                rec["state"] = "done" if rec["success"] else "interrupted"
                self.changed.emit()
        except Exception:
            pass

    # ---------- API для UI ----------

    def cancel(self, rec) -> None:
        try:
            rec["item"].cancel()
        except Exception as e:
            print(f"[DL] cancel error: {e}", flush=True)

    def open_file(self, rec) -> None:
        try:
            subprocess.Popen(["xdg-open", rec["path"]])
        except Exception as e:
            print(f"[DL] open error: {e}", flush=True)

    def open_folder(self, rec) -> None:
        try:
            subprocess.Popen(["xdg-open", str(Path(rec["path"]).parent)])
        except Exception as e:
            print(f"[DL] open folder error: {e}", flush=True)

    def clear_finished(self) -> None:
        self.downloads = [d for d in self.downloads if not d.get("finished")]
        self.changed.emit()

    def remove(self, rec) -> None:
        if rec in self.downloads:
            self.downloads.remove(rec)
            self.changed.emit()

    def active_count(self) -> int:
        return sum(1 for d in self.downloads if not d.get("finished"))

    def all(self):
        return list(self.downloads)


# ==================== UI ====================

class DownloadRow(QWidget):
    """Одна строка загрузки в попапе."""

    open_clicked = pyqtSignal(object)
    folder_clicked = pyqtSignal(object)
    cancel_clicked = pyqtSignal(object)

    def __init__(self, rec, parent=None):
        super().__init__(parent)
        self.rec = rec

        L = QVBoxLayout(self)
        L.setContentsMargins(8, 6, 8, 6)
        L.setSpacing(4)

        # Верхняя строка: имя + кнопки
        top = QHBoxLayout()
        top.setSpacing(4)

        self.name_label = QLabel(rec.get("name", "file"))
        self.name_label.setStyleSheet(
            f"color: {COLOR_TEXT}; font-family: {FONT_MONO}; "
            f"font-size: 11px; font-weight: bold;"
        )
        self.name_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top.addWidget(self.name_label, 1)

        self.btn_open = QPushButton("📂")
        self.btn_open.setFixedSize(22, 20)
        self.btn_open.setToolTip("Открыть файл")
        self.btn_open.clicked.connect(lambda: self.open_clicked.emit(rec))
        self.btn_open.setStyleSheet(self._mini_btn_qss())
        top.addWidget(self.btn_open)

        self.btn_folder = QPushButton("🗀")
        self.btn_folder.setFixedSize(22, 20)
        self.btn_folder.setToolTip("Открыть папку")
        self.btn_folder.clicked.connect(lambda: self.folder_clicked.emit(rec))
        self.btn_folder.setStyleSheet(self._mini_btn_qss())
        top.addWidget(self.btn_folder)

        self.btn_cancel = QPushButton("✕")
        self.btn_cancel.setFixedSize(22, 20)
        self.btn_cancel.clicked.connect(lambda: self.cancel_clicked.emit(rec))
        self.btn_cancel.setStyleSheet(self._mini_btn_qss(danger=True))
        top.addWidget(self.btn_cancel)

        L.addLayout(top)

        # Прогресс
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{
                background: rgba(255,255,255,0.05);
                border: none; border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background: {COLOR_MINT}; border-radius: 3px;
            }}
        """)
        L.addWidget(self.progress)

        # Статус
        self.status_label = QLabel("")
        self.status_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-family: {FONT_MONO}; font-size: 10px;"
        )
        L.addWidget(self.status_label)

        self._refresh()

    def _mini_btn_qss(self, danger=False):
        c = COLOR_DANGER if danger else COLOR_LAVENDER
        return f"""
            QPushButton {{
                background: transparent; color: {c};
                border: none; border-radius: 3px;
                font-family: {FONT_MONO}; font-size: 11px; padding: 0;
            }}
            QPushButton:hover {{ background: rgba(179, 136, 255, 0.3); color: white; }}
            QPushButton:pressed {{ background: {COLOR_LAVENDER}; color: {COLOR_BG}; }}
        """

    def _refresh(self) -> None:
        rec = self.rec
        total = rec.get("total", 0)
        recv = rec.get("received", 0)
        state = rec.get("state", "progress")

        if state == "progress":
            if total > 0:
                pct = int(recv * 100 / total)
                self.progress.setRange(0, 100)
                self.progress.setValue(pct)
                self.status_label.setText(
                    f"{recv // 1024} / {total // 1024} KB · {pct}%")
            else:
                self.progress.setRange(0, 0)  # бесконечный
                self.status_label.setText(f"{recv // 1024} KB")
            self.btn_open.setEnabled(False)
            self.btn_cancel.setText("✕")
            self.btn_cancel.setToolTip("Отменить")
        elif state == "done":
            self.progress.setRange(0, 100)
            self.progress.setValue(100)
            size = total // 1024 if total else recv // 1024
            self.status_label.setText(f"Готово · {size} KB")
            self.btn_open.setEnabled(True)
            self.btn_cancel.setText("🗑")
            self.btn_cancel.setToolTip("Убрать")
        elif state in ("cancelled", "interrupted"):
            self.progress.setRange(0, 100)
            self.progress.setValue(0)
            self.status_label.setText(
                "Отменено" if state == "cancelled" else "Прервано")
            self.btn_open.setEnabled(False)
            self.btn_cancel.setText("🗑")


class DownloadsPopup(QFrame):
    """Выпадающая панель загрузок. Открывается под кнопкой ⬇."""

    def __init__(self, parent, dl_manager: DownloadManager):
        super().__init__(parent, Qt.WindowType.Popup)
        self.dl_manager = dl_manager

        self.setObjectName("dlpopup")
        self.setStyleSheet(f"""
            QFrame#dlpopup {{
                background: {COLOR_BG_PANEL};
                border: 1px solid {COLOR_BORDER_HL};
                border-radius: 10px;
            }}
        """)
        self.setFixedWidth(360)

        L = QVBoxLayout(self)
        L.setContentsMargins(10, 10, 10, 10)
        L.setSpacing(6)

        # Заголовок
        header = QHBoxLayout()
        title = QLabel("⬇  Загрузки")
        title.setStyleSheet(
            f"color: {COLOR_MINT}; font-family: {FONT_MONO}; "
            f"font-size: 13px; font-weight: bold;"
        )
        header.addWidget(title)
        header.addStretch(1)

        self.btn_clear = QPushButton("Очистить")
        self.btn_clear.setFixedHeight(22)
        self.btn_clear.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {COLOR_LAVENDER};
                border: 1px solid rgba(179, 136, 255, 0.3);
                border-radius: 4px;
                font-family: {FONT_MONO}; font-size: 10px;
                padding: 0 8px;
            }}
            QPushButton:hover {{ background: rgba(179, 136, 255, 0.2); color: white; }}
        """)
        self.btn_clear.clicked.connect(self._clear)
        header.addWidget(self.btn_clear)
        L.addLayout(header)

        # Скролл со списком
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }")
        self.inner = QWidget()
        self.inner.setStyleSheet("background: transparent;")
        self.inner_l = QVBoxLayout(self.inner)
        self.inner_l.setContentsMargins(0, 0, 0, 0)
        self.inner_l.setSpacing(4)
        self.inner_l.addStretch(1)
        self.scroll.setWidget(self.inner)
        L.addWidget(self.scroll, 1)

        # Placeholder
        self.empty_label = QLabel("Нет загрузок")
        self.empty_label.setStyleSheet(
            f"color: {COLOR_TEXT_DIM}; font-family: {FONT_MONO}; "
            f"font-size: 11px; padding: 20px;"
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        L.addWidget(self.empty_label)

        self.dl_manager.changed.connect(self._rebuild)

    def _clear(self) -> None:
        self.dl_manager.clear_finished()
        self._rebuild()

    def _rebuild(self) -> None:
        # Сносим старые строки
        while self.inner_l.count() > 1:
            it = self.inner_l.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        downloads = self.dl_manager.all()
        if not downloads:
            self.empty_label.show()
            self.scroll.hide()
            self._adjust_height()
            return

        self.empty_label.hide()
        self.scroll.show()

        # Новые сверху
        for rec in reversed(downloads):
            row = DownloadRow(rec)
            row.open_clicked.connect(self.dl_manager.open_file)
            row.folder_clicked.connect(self.dl_manager.open_folder)
            row.cancel_clicked.connect(self._on_cancel_click)
            self.inner_l.insertWidget(0, row)

        self._adjust_height()

    def _on_cancel_click(self, rec) -> None:
        if rec.get("finished"):
            self.dl_manager.remove(rec)
        else:
            self.dl_manager.cancel(rec)

    def _adjust_height(self) -> None:
        self.inner.adjustSize()
        h = self.inner.sizeHint().height() + 80
        self.setFixedHeight(min(max(h, 120), 500))

    def popup_at(self, global_pos) -> None:
        """Показать попап под указанной точкой, не вылезая за экран."""
        self._rebuild()
        self.show()

        x = global_pos.x() - self.width()
        y = global_pos.y() + 6

        screen = QGuiApplication.primaryScreen()
        if screen:
            g = screen.availableGeometry()
            if x < g.left():
                x = g.left() + 4
            if x + self.width() > g.right():
                x = g.right() - self.width() - 4
            if y + self.height() > g.bottom():
                y = global_pos.y() - self.height() - 6

        self.move(x, y)
        self.raise_()
