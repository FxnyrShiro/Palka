"""Диалог-менеджер: закладки, история, пароли.

Одно окно с тремя табами. Модальность выключена — можно оставить
открытым и работать во вкладках.
"""
from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QTabWidget, QListWidget, QListWidgetItem,
    QPushButton, QLineEdit,
)

from .constants import FONT_MONO


_DIALOG_QSS = None  # заполняется в ManagerDialog через styles.py


class ManagerDialog(QDialog):
    def __init__(self, parent, pw_manager, bm_manager, hist_manager, open_url_cb):
        super().__init__(parent)
        self.setWindowTitle("Менеджер")
        self.setModal(False)
        self.resize(900, 600)

        # Импорт здесь, чтобы не создавать циклов
        from .styles import DIALOG_QSS
        self.setStyleSheet(DIALOG_QSS)

        self.pw_manager = pw_manager
        self.bm_manager = bm_manager
        self.hist_manager = hist_manager
        self.open_url_cb = open_url_cb

        L = QVBoxLayout(self)
        L.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget()
        L.addWidget(self.tabs)

        self._build_bookmarks_tab()
        self._build_history_tab()
        self._build_passwords_tab()

    # ==================== ЗАКЛАДКИ ====================

    def _build_bookmarks_tab(self) -> None:
        w = QWidget()
        L = QVBoxLayout(w)
        L.setContentsMargins(8, 8, 8, 8)

        self.bm_list = QListWidget()
        self.bm_list.itemDoubleClicked.connect(self._bm_open)
        L.addWidget(self.bm_list)

        B = QHBoxLayout()
        btn_open = QPushButton("Открыть")
        btn_open.clicked.connect(self._bm_open_sel)
        B.addWidget(btn_open)

        btn_del = QPushButton("Удалить")
        btn_del.setObjectName("deny")
        btn_del.clicked.connect(self._bm_del)
        B.addWidget(btn_del)

        B.addStretch(1)
        L.addLayout(B)

        self.tabs.addTab(w, "⭐ Закладки")
        self._reload_bookmarks()

    def _reload_bookmarks(self) -> None:
        self.bm_list.clear()
        for b in self.bm_manager.all():
            it = QListWidgetItem(f"{b.get('title','')}\n  {b.get('url','')}")
            it.setData(Qt.ItemDataRole.UserRole, b.get("url", ""))
            self.bm_list.addItem(it)

    def _bm_open(self, it: QListWidgetItem) -> None:
        url = it.data(Qt.ItemDataRole.UserRole)
        if url:
            self.open_url_cb(url)

    def _bm_open_sel(self) -> None:
        it = self.bm_list.currentItem()
        if it:
            self._bm_open(it)

    def _bm_del(self) -> None:
        i = self.bm_list.currentRow()
        if i >= 0:
            self.bm_manager.remove_at(i)
            self._reload_bookmarks()

    # ==================== ИСТОРИЯ ====================

    def _build_history_tab(self) -> None:
        w = QWidget()
        L = QVBoxLayout(w)
        L.setContentsMargins(8, 8, 8, 8)

        self.hist_filter = QLineEdit()
        self.hist_filter.setPlaceholderText("Фильтр…")
        self.hist_filter.textChanged.connect(self._reload_history)
        L.addWidget(self.hist_filter)

        self.hist_list = QListWidget()
        self.hist_list.itemDoubleClicked.connect(self._hist_open)
        L.addWidget(self.hist_list)

        B = QHBoxLayout()
        btn_open = QPushButton("Открыть")
        btn_open.clicked.connect(self._hist_open_sel)
        B.addWidget(btn_open)

        btn_del = QPushButton("Удалить")
        btn_del.setObjectName("deny")
        btn_del.clicked.connect(self._hist_del)
        B.addWidget(btn_del)

        btn_clear = QPushButton("Очистить всё")
        btn_clear.setObjectName("deny")
        btn_clear.clicked.connect(self._hist_clear)
        B.addWidget(btn_clear)

        B.addStretch(1)
        L.addLayout(B)

        self.tabs.addTab(w, "🕓 История")
        self._reload_history()

    def _reload_history(self) -> None:
        self.hist_list.clear()
        q = self.hist_filter.text().lower()
        # Запоминаем индексы в полном списке истории — для удаления
        self._hist_indices = []

        for i, h in enumerate(self.hist_manager.all()):
            if q and q not in h.get("url", "").lower() \
                    and q not in h.get("title", "").lower():
                continue

            ts = h.get("ts", 0)
            try:
                when = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
            except Exception:
                when = ""

            it = QListWidgetItem(
                f"{h.get('title','')}\n  {h.get('url','')}    [{when}]")
            it.setData(Qt.ItemDataRole.UserRole, h.get("url", ""))
            self.hist_list.addItem(it)
            self._hist_indices.append(i)

    def _hist_open(self, it: QListWidgetItem) -> None:
        url = it.data(Qt.ItemDataRole.UserRole)
        if url:
            self.open_url_cb(url)

    def _hist_open_sel(self) -> None:
        it = self.hist_list.currentItem()
        if it:
            self._hist_open(it)

    def _hist_del(self) -> None:
        row = self.hist_list.currentRow()
        if 0 <= row < len(self._hist_indices):
            self.hist_manager.remove_at(self._hist_indices[row])
            self._reload_history()

    def _hist_clear(self) -> None:
        self.hist_manager.clear()
        self._reload_history()

    # ==================== ПАРОЛИ ====================

    def _build_passwords_tab(self) -> None:
        w = QWidget()
        L = QVBoxLayout(w)
        L.setContentsMargins(8, 8, 8, 8)

        self.pw_list = QListWidget()
        L.addWidget(self.pw_list)

        B = QHBoxLayout()
        btn_del = QPushButton("Удалить")
        btn_del.setObjectName("deny")
        btn_del.clicked.connect(self._pw_del)
        B.addWidget(btn_del)

        btn_toggle = QPushButton("Показать/Скрыть")
        btn_toggle.clicked.connect(self._pw_toggle)
        B.addWidget(btn_toggle)

        B.addStretch(1)
        L.addLayout(B)

        self.tabs.addTab(w, "🔑 Пароли")
        self._pw_visible = False
        self._reload_passwords()

    def _reload_passwords(self) -> None:
        self.pw_list.clear()
        for origin, user, pw in self.pw_manager.all():
            shown = pw if self._pw_visible else "•" * min(len(pw), 12)
            it = QListWidgetItem(f"{origin}\n  👤 {user}   🔒 {shown}")
            it.setData(Qt.ItemDataRole.UserRole, origin)
            self.pw_list.addItem(it)

    def _pw_del(self) -> None:
        it = self.pw_list.currentItem()
        if it:
            origin = it.data(Qt.ItemDataRole.UserRole)
            self.pw_manager.remove(origin)
            self._reload_passwords()

    def _pw_toggle(self) -> None:
        self._pw_visible = not self._pw_visible
        self._reload_passwords()

    # ==================== публичное ====================

    def refresh_all(self) -> None:
        """Перечитать всё из менеджеров — вызывается при открытии окна."""
        self._reload_bookmarks()
        self._reload_history()
        self._reload_passwords()
