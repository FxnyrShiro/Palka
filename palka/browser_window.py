"""Главное окно браузера.

Содержит:
  - верхнюю панель вкладок с кнопкой "+"
  - адресную строку с кнопками навигации, звёздочкой, загрузками, меню
  - QStackedWidget с QWebEngineView для каждой вкладки
  - панель поиска по странице (Ctrl+F)
  - горячие клавиши (см. _setup_shortcuts)
  - мосты к менеджерам (пароли, закладки, история, загрузки)
  - логику fullscreen от страницы и F11
"""
import os
import subprocess
import tempfile

from PyQt6.QtCore import Qt, QEvent, QPoint, QUrl, QTimer, QPropertyAnimation, QEasingCurve, \
    QAbstractAnimation
from PyQt6.QtGui import QKeySequence, QShortcut, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QPushButton, QLineEdit, QLabel, QMenu, QDialog,
    QGraphicsOpacityEffect,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import (
    QWebEngineProfile, QWebEnginePage, QWebEngineSettings,
)

from .constants import (
    COLOR_BG, COLOR_BG_LIGHT, COLOR_BG_PANEL,
    COLOR_BORDER, COLOR_BORDER_HL,
    COLOR_MINT, COLOR_LAVENDER, COLOR_TEXT, COLOR_TEXT_DIM,
    FONT_MONO, PROFILE_NAME,
)
from .styles import DIALOG_QSS
from .widgets import StyledTabBar
from .browser_page import MicroPage
from .passwords import PasswordManager
from .bookmarks import BookmarkManager
from .history import HistoryManager
from .downloads import DownloadManager, DownloadsPopup
from .managers_ui import ManagerDialog
from .permissions import PermissionDialog, PERMISSION_NAMES


# ==================== QSS НАВИГАЦИОННЫХ КНОПОК ====================

_NAV_BTN_QSS = f"""
    QPushButton {{
        background-color: rgba(0, 255, 170, 0.08);
        color: {COLOR_MINT};
        border: 1px solid rgba(0, 255, 170, 0.20);
        border-radius: 5px;
        padding: 0;
        font-family: {FONT_MONO};
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: rgba(0, 255, 170, 0.30);
        color: #ffffff;
        border-color: {COLOR_MINT};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_MINT};
        color: {COLOR_BG};
    }}
    QPushButton:disabled {{
        color: #2a3a34;
        background: transparent;
        border-color: #1a2a24;
    }}
"""

_DL_BTN_QSS_IDLE = f"""
    QPushButton {{
        background-color: rgba(0, 255, 170, 0.08);
        color: {COLOR_MINT};
        border: 1px solid rgba(0, 255, 170, 0.20);
        border-radius: 5px;
        padding: 0;
        font-family: {FONT_MONO};
        font-size: 13px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: rgba(0, 255, 170, 0.30);
        color: #ffffff;
        border-color: {COLOR_MINT};
    }}
    QPushButton:pressed {{
        background-color: {COLOR_MINT};
        color: {COLOR_BG};
    }}
"""

_DL_BTN_QSS_ACTIVE = f"""
    QPushButton {{
        background-color: rgba(0, 255, 170, 0.25);
        color: {COLOR_MINT};
        border: 1px solid {COLOR_MINT};
        border-radius: 5px;
        padding: 0;
        font-family: {FONT_MONO};
        font-size: 11px;
        font-weight: bold;
    }}
    QPushButton:hover {{
        background-color: {COLOR_MINT};
        color: {COLOR_BG};
    }}
"""


class MiniBrowser(QMainWindow):
    # ==================== INIT ====================

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Micro Web Browser")
        self.resize(1280, 850)

        # --- Состояние окна ---
        self._anims = []
        self.closed_tabs = []
        self._was_maximized = False
        self._find_bar_was_visible = False

        # --- Менеджеры данных ---
        self.pw_manager = PasswordManager()
        self.bm_manager = BookmarkManager()
        self.hist_manager = HistoryManager()
        self.dl_manager = DownloadManager(self)
        self.dl_manager.changed.connect(self._update_dl_badge)

        # --- Внешние окна (создаются лениво) ---
        self._devtools_window = None
        self._devtools_view = None
        self._devtools_page = None
        self._manager_dialog = None
        self._dl_popup = None

        # --- Layout ---
        L = QVBoxLayout()
        L.setContentsMargins(0, 0, 0, 0)
        L.setSpacing(0)

        L.addWidget(self._build_tab_row())
        L.addWidget(self._build_top_bar())

        # Контент
        self.stack = QStackedWidget()
        self.stack.setStyleSheet(f"background-color: {COLOR_BG};")
        L.addWidget(self.stack, 1)

        L.addWidget(self._build_find_bar())

        container = QWidget()
        container.setLayout(L)
        self.setCentralWidget(container)

        # --- Профиль и первая вкладка ---
        self.profile = self._make_profile()
        self.dl_manager.register_profile(self.profile)

        self.add_new_tab(QUrl("https://google.com"), "Стартовая")

        # --- Горячие клавиши ---
        self._setup_shortcuts()

    # ==================== ПОСТРОЕНИЕ UI ====================

    def _make_profile(self) -> QWebEngineProfile:
        profile = QWebEngineProfile(PROFILE_NAME, self)

        settings = profile.settings()
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.LocalStorageEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.JavascriptEnabled, True)
        settings.setAttribute(
            QWebEngineSettings.WebAttribute.AllowRunningInsecureContent, False)

        try:
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True)
            print("[SCROLL] OK", flush=True)
        except Exception as e:
            print(f"[SCROLL] n/a: {e}", flush=True)

        try:
            settings.setAttribute(
                QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True)
            print("[FS] OK", flush=True)
        except Exception as e:
            print(f"[FS] n/a: {e}", flush=True)

        return profile

    def _build_tab_row(self) -> QWidget:
        self.tab_bar = StyledTabBar()
        self.tab_bar.setMouseTracking(True)
        self.tab_bar.installEventFilter(self)
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        self.tab_bar.tabMoved.connect(self._on_tab_moved)
        self.tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tab_bar.customContextMenuRequested.connect(self._tab_context_menu)

        self.plus_btn = QPushButton("+")
        self.plus_btn.setFixedSize(28, 24)
        self.plus_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.plus_btn.setToolTip("Новая вкладка (Ctrl+T)")
        self.plus_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba(0, 255, 170, 0.10);
                color: {COLOR_MINT};
                border: 1px solid rgba(0, 255, 170, 0.25);
                border-radius: 5px;
                font-family: {FONT_MONO};
                font-size: 15px;
                font-weight: bold;
                padding: 0;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 255, 170, 0.35);
                color: #fff;
                border-color: {COLOR_MINT};
            }}
            QPushButton:pressed {{
                background-color: {COLOR_MINT};
                color: {COLOR_BG};
            }}
        """)
        self.plus_btn.clicked.connect(
            lambda: self.add_new_tab(QUrl("https://google.com"), "Новая вкладка"))
        self.plus_btn.pressed.connect(
            lambda *_: self._pulse_widget(self.plus_btn))

        row = QWidget()
        row.setStyleSheet(f"background-color: {COLOR_BG};")
        RL = QHBoxLayout(row)
        RL.setContentsMargins(4, 3, 6, 0)
        RL.setSpacing(0)
        RL.addWidget(self.tab_bar, 1)
        RL.addWidget(self.plus_btn)

        # Сохраняем ссылку — пригодится для скрытия/восстановления в fullscreen
        self.tab_row = row
        return row

    def _build_top_bar(self) -> QWidget:
        top = QWidget()
        top.setFixedHeight(34)
        top.setStyleSheet(
            f"QWidget {{ background-color: {COLOR_BG};"
            f" border-bottom: 1px solid #1a2a24; }}"
        )
        T = QHBoxLayout(top)
        T.setContentsMargins(6, 3, 6, 3)
        T.setSpacing(5)

        self.btn_back = self._nav_btn("◀", self.go_back, "Назад (Alt+←)")
        T.addWidget(self.btn_back)

        self.btn_forward = self._nav_btn("▶", self.go_forward, "Вперёд (Alt+→)")
        T.addWidget(self.btn_forward)

        self.btn_reload = self._nav_btn("⟳", self.reload_current_tab, "Обновить (Ctrl+R)")
        T.addWidget(self.btn_reload)

        # Адресная строка
        self.url_bar = QLineEdit()
        self.url_bar.setFixedHeight(24)
        self.url_bar.setStyleSheet(f"""
            QLineEdit {{
                background-color: {COLOR_BG_LIGHT};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 1px 10px;
                font-family: {FONT_MONO};
                font-size: 12px;
                selection-background-color: {COLOR_MINT};
                selection-color: {COLOR_BG};
            }}
            QLineEdit:focus {{
                border: 1px solid {COLOR_BORDER_HL};
                background: rgba(0, 255, 170, 0.04);
            }}
        """)
        self.url_bar.returnPressed.connect(self.navigate_to_url)
        T.addWidget(self.url_bar, 1)

        self.btn_star = self._nav_btn("☆", self.toggle_bookmark, "В закладки (Ctrl+D)")
        T.addWidget(self.btn_star)

        self.btn_dl = self._nav_btn("⬇", self._open_downloads_popup, "Загрузки (Ctrl+J)")
        self.btn_dl.setStyleSheet(_DL_BTN_QSS_IDLE)
        T.addWidget(self.btn_dl)

        self.btn_manager = self._nav_btn("☰", self.open_manager, "Менеджер (Ctrl+H)")
        T.addWidget(self.btn_manager)

        self.top_bar = top
        return top

    def _nav_btn(self, text: str, on_click, tooltip: str) -> QPushButton:
        btn = QPushButton(text)
        btn.setFixedSize(28, 24)
        btn.setStyleSheet(_NAV_BTN_QSS)
        btn.setToolTip(tooltip)
        btn.clicked.connect(on_click)
        btn.pressed.connect(lambda *_: self._pulse_widget(btn))
        return btn

    def _build_find_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            f"QWidget {{ background: {COLOR_BG_PANEL};"
            f" border-top: 1px solid #1a2a24; }}"
        )
        L = QHBoxLayout(bar)
        L.setContentsMargins(8, 4, 8, 4)
        L.setSpacing(6)

        icon = QLabel("🔍")
        icon.setStyleSheet(f"color: {COLOR_MINT}; font-size: 14px;")
        L.addWidget(icon)

        self.find_input = QLineEdit()
        self.find_input.setFixedHeight(24)
        self.find_input.setPlaceholderText(
            "Найти на странице…  (Enter — далее, Esc — закрыть)")
        self.find_input.setStyleSheet(f"""
            QLineEdit {{
                background: {COLOR_BG_LIGHT};
                color: {COLOR_TEXT};
                border: 1px solid {COLOR_BORDER};
                border-radius: 6px;
                padding: 1px 10px;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QLineEdit:focus {{ border: 1px solid {COLOR_BORDER_HL}; }}
        """)
        self.find_input.textChanged.connect(self._do_find)
        self.find_input.returnPressed.connect(self._find_next)
        L.addWidget(self.find_input, 1)

        close = QPushButton("✕")
        close.setFixedSize(20, 20)
        close.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR_LAVENDER};
                border: none;
                border-radius: 3px;
                font-family: {FONT_MONO};
                font-size: 12px;
            }}
            QPushButton:hover {{
                background: rgba(179, 136, 255, 0.4);
                color: white;
            }}
        """)
        close.clicked.connect(self.hide_find)
        L.addWidget(close)

        bar.hide()
        self.find_bar = bar

        QShortcut(QKeySequence("Escape"), self.find_input, self.hide_find)
        return bar

    # ==================== ГОРЯЧИЕ КЛАВИШИ ====================

    def _setup_shortcuts(self) -> None:
        bindings = [
            ("Ctrl+L", self.url_bar.setFocus),
            ("Ctrl+R", self.reload_current_tab),
            ("F5", self.reload_current_tab),
            ("Ctrl+T", lambda: self.add_new_tab(
                QUrl("https://google.com"), "Новая вкладка")),
            ("Ctrl+W", lambda: self.close_tab(self.tab_bar.currentIndex())),
            ("Ctrl+Shift+T", self.reopen_closed_tab),
            ("Ctrl+Tab", self.next_tab),
            ("Ctrl+Shift+Tab", self.prev_tab),
            ("Ctrl+Q", self.close),
            ("Alt+Left", self.go_back),
            ("Alt+Right", self.go_forward),
            ("Ctrl+F", self.show_find),
            ("Ctrl+=", self.zoom_in),
            ("Ctrl++", self.zoom_in),
            ("Ctrl+-", self.zoom_out),
            ("Ctrl+0", self.zoom_reset),
            ("F12", self.open_devtools),
            ("Ctrl+Shift+I", self.open_devtools),
            ("F11", self.toggle_fullscreen),
            ("Ctrl+U", self.view_source),
            ("Ctrl+P", self.print_page),
            ("Ctrl+D", self.toggle_bookmark),
            ("Ctrl+H", self.open_manager),
            ("Ctrl+Shift+O", self.open_manager),
            ("Ctrl+J", self._open_downloads_popup),
        ]
        for seq, cb in bindings:
            QShortcut(QKeySequence(seq), self, cb)

    # ==================== АНИМАЦИИ КНОПОК ====================

    def _pulse_widget(self, btn: QPushButton) -> None:
        old = btn.graphicsEffect()
        if old is not None:
            btn.setGraphicsEffect(None)

        eff = QGraphicsOpacityEffect(btn)
        eff.setOpacity(1.0)
        btn.setGraphicsEffect(eff)

        a = QPropertyAnimation(eff, b"opacity", btn)
        a.setDuration(150)
        a.setKeyValueAt(0.0, 1.0)
        a.setKeyValueAt(0.45, 0.40)
        a.setKeyValueAt(1.0, 1.0)
        a.setEasingCurve(QEasingCurve.Type.InOutQuad)

        def done(b=btn):
            try:
                b.setGraphicsEffect(None)
            except RuntimeError:
                pass

        a.finished.connect(done)
        self._anims.append(a)
        a.start(QAbstractAnimation.DeletionPolicy.KeepWhenStopped)

    # ==================== ВКЛАДКИ ====================

    def add_new_tab(self, qurl: QUrl, title: str) -> None:
        browser = QWebEngineView()
        page = MicroPage(self.profile, self.pw_manager, browser)
        browser.setPage(page)

        page.permissionRequested.connect(self.handle_permission)
        page.pageFullScreenRequested.connect(self.on_page_fullscreen)

        browser.setUrl(qurl)
        self.stack.addWidget(browser)

        i = self.tab_bar.addTab(title)
        self.tab_bar.setCurrentIndex(i)

        browser.urlChanged.connect(
            lambda u, b=browser: self.update_urlbar(u, b))
        browser.titleChanged.connect(
            lambda t, b=browser: self.update_tab_title(t, b))
        browser.urlChanged.connect(
            lambda u, b=browser: self._update_nav_buttons(b))
        browser.urlChanged.connect(
            lambda u, b=browser: self._record_history(u, b))
        browser.loadFinished.connect(
            lambda ok, b=browser: self._update_nav_buttons(b))

    def close_tab(self, i: int) -> None:
        if self.tab_bar.count() < 2:
            self.close()
            return

        w = self.stack.widget(i)
        if w:
            url = w.url().toString()
            title = self.tab_bar.tabText(i)
            if url:
                self.closed_tabs.append((url, title))
                if len(self.closed_tabs) > 30:
                    self.closed_tabs.pop(0)
            self.stack.removeWidget(w)
            w.deleteLater()

        self.tab_bar.removeTab(i)

    def reopen_closed_tab(self) -> None:
        if not self.closed_tabs:
            return
        url, title = self.closed_tabs.pop()
        self.add_new_tab(QUrl(url), title or "Восстановлено")

    def _on_tab_changed(self, i: int) -> None:
        if not (0 <= i < self.stack.count()):
            return
        self.stack.setCurrentIndex(i)

        b = self.stack.widget(i)
        if not b:
            return

        self.url_bar.setText(b.url().toString())
        self._refresh_star(b.url().toString())
        self._update_nav_buttons(b)

        if self.find_bar.isVisible() and self.find_input.text():
            b.page().findText(self.find_input.text())

    def _on_tab_moved(self, from_idx: int, to_idx: int) -> None:
        w = self.stack.widget(from_idx)
        if w is None:
            return
        self.stack.removeWidget(w)
        self.stack.insertWidget(to_idx, w)
        self.stack.setCurrentIndex(self.tab_bar.currentIndex())

    def _tab_context_menu(self, pos: QPoint) -> None:
        idx = self.tab_bar.tabAt(pos)
        if idx < 0:
            return

        m = QMenu(self)
        m.setStyleSheet(DIALOG_QSS)

        act_reload = QAction("Обновить", self)
        act_reload.triggered.connect(self.reload_current_tab)
        m.addAction(act_reload)

        act_dup = QAction("Дублировать", self)
        act_dup.triggered.connect(self._dup_tab)
        m.addAction(act_dup)

        m.addSeparator()

        act_close = QAction("Закрыть", self)
        act_close.triggered.connect(lambda: self.close_tab(idx))
        m.addAction(act_close)

        act_others = QAction("Закрыть остальные", self)
        act_others.triggered.connect(lambda: self._close_others(idx))
        m.addAction(act_others)

        m.exec(self.tab_bar.mapToGlobal(pos))

    def _dup_tab(self) -> None:
        b = self.stack.currentWidget()
        if b:
            self.add_new_tab(
                b.url(),
                self.tab_bar.tabText(self.tab_bar.currentIndex()))

    def _close_others(self, keep_idx: int) -> None:
        while self.tab_bar.count() > 1:
            if self.tab_bar.currentIndex() == keep_idx:
                for i in range(self.tab_bar.count()):
                    if i != keep_idx:
                        self.close_tab(i)
                        break
            else:
                self.close_tab(self.tab_bar.currentIndex())

    def add_new_tab_for_link(self):
        """
        Создаёт новую вкладку для ссылки, запрошенной сайтом.
        Возвращает QWebEnginePage новой вкладки.
        """
        browser = QWebEngineView()
        page = MicroPage(self.profile, self.pw_manager, browser)
        browser.setPage(page)
        
        # Подключаем те же сигналы, что и в обычном add_new_tab
        page.permissionRequested.connect(self.handle_permission)
        page.pageFullScreenRequested.connect(self.on_page_fullscreen)
        
        # Добавляем вкладку в интерфейс
        i = self.tab_bar.addTab("Загрузка…")
        self.stack.addWidget(browser)
        self.tab_bar.setCurrentIndex(i)
        
        # Подключаем обновление заголовка и URL
        browser.titleChanged.connect(
            lambda t, b=browser: self.update_tab_title(t, b))
        browser.urlChanged.connect(
            lambda u, b=browser: self.update_urlbar(u, b))
        browser.urlChanged.connect(
            lambda u, b=browser: self._update_nav_buttons(b))
        browser.urlChanged.connect(
            lambda u, b=browser: self._record_history(u, b))
        browser.loadFinished.connect(
            lambda ok, b=browser: self._update_nav_buttons(b))
        
        return page

    # ==================== НАВИГАЦИЯ ====================

    def go_back(self) -> None:
        b = self.stack.currentWidget()
        if b and b.history().canGoBack():
            b.history().back()

    def go_forward(self) -> None:
        b = self.stack.currentWidget()
        if b and b.history().canGoForward():
            b.history().forward()

    def reload_current_tab(self) -> None:
        b = self.stack.currentWidget()
        if b:
            b.reload()

    def next_tab(self) -> None:
        n = self.tab_bar.count()
        self.tab_bar.setCurrentIndex((self.tab_bar.currentIndex() + 1) % n)

    def prev_tab(self) -> None:
        n = self.tab_bar.count()
        self.tab_bar.setCurrentIndex((self.tab_bar.currentIndex() - 1) % n)

    def navigate_to_url(self):
        url = self.url_bar.text().strip()
        # Не трогаем URL со своими схемами
        special_schemes = ("http://", "https://", "chrome://",
                           "about:", "file://", "view-source:",
                           "data:", "blob:")
        if not url.startswith(special_schemes):
            url = "https://" + url
        b = self.stack.currentWidget()
        if b:
            b.setUrl(QUrl(url))

    def update_urlbar(self, qurl: QUrl, browser: QWebEngineView) -> None:
        if browser == self.stack.currentWidget():
            self.url_bar.setText(qurl.toString())
            self._refresh_star(qurl.toString())

    def update_tab_title(self, title: str, browser: QWebEngineView) -> None:
        i = self.stack.indexOf(browser)
        if i != -1:
            short = title[:18] + "…" if len(title) > 18 else title
            self.tab_bar.setTabText(i, short or "Без имени")

    def _update_nav_buttons(self, browser: QWebEngineView) -> None:
        if browser != self.stack.currentWidget():
            return
        self.btn_back.setEnabled(browser.history().canGoBack())
        self.btn_forward.setEnabled(browser.history().canGoForward())

    def _record_history(self, qurl: QUrl, browser: QWebEngineView) -> None:
        if browser != self.stack.currentWidget():
            return
        self.hist_manager.add(qurl.toString(), browser.title())
        self._refresh_star(qurl.toString())

    def _refresh_star(self, url: str) -> None:
        self.btn_star.setText("★" if self.bm_manager.is_bookmarked(url) else "☆")

    # ==================== ПОИСК ====================

    def show_find(self) -> None:
        self.find_bar.show()
        self.find_input.setFocus()
        self.find_input.selectAll()

    def hide_find(self) -> None:
        self.find_bar.hide()
        b = self.stack.currentWidget()
        if b:
            b.page().findText("")

    def _do_find(self, text: str) -> None:
        b = self.stack.currentWidget()
        if b:
            b.page().findText(text if text else "")

    def _find_next(self) -> None:
        b = self.stack.currentWidget()
        if b and self.find_input.text():
            b.page().findText(self.find_input.text())

    # ==================== ЗУМ ====================

    def zoom_in(self) -> None:
        b = self.stack.currentWidget()
        if b:
            b.page().setZoomFactor(min(b.page().zoomFactor() * 1.15, 5.0))

    def zoom_out(self) -> None:
        b = self.stack.currentWidget()
        if b:
            b.page().setZoomFactor(max(b.page().zoomFactor() / 1.15, 0.25))

    def zoom_reset(self) -> None:
        b = self.stack.currentWidget()
        if b:
            b.page().setZoomFactor(1.0)

    # ==================== FULLSCREEN ====================

    def toggle_fullscreen(self) -> None:
        """F11 — разворачивает окно, панели остаются."""
        if self.isFullScreen():
            self._restore_window_state()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()

    def on_page_fullscreen(self, on: bool) -> None:
        """Страница запросила fullscreen — прячем панели."""
        if on:
            self._was_maximized = self.isMaximized()
            self._find_bar_was_visible = self.find_bar.isVisible()
            self.tab_row.hide()
            self.top_bar.hide()
            self.find_bar.hide()
            self.showFullScreen()
        else:
            self.tab_row.show()
            self.top_bar.show()
            if getattr(self, "_find_bar_was_visible", False):
                self.find_bar.show()
            self._restore_window_state()

    def _restore_window_state(self) -> None:
        if self._was_maximized:
            self.showMaximized()
        else:
            self.showNormal()

    # ==================== МЕНЕДЖЕРЫ ====================

    def toggle_bookmark(self) -> None:
        b = self.stack.currentWidget()
        if not b:
            return
        url = b.url().toString()
        title = b.title()

        if self.bm_manager.is_bookmarked(url):
            for i, bm in enumerate(self.bm_manager.all()):
                if bm.get("url") == url:
                    self.bm_manager.remove_at(i)
                    break
            self.btn_star.setText("☆")
        else:
            self.bm_manager.add(url, title)
            self.btn_star.setText("★")

        if self._manager_dialog and self._manager_dialog.isVisible():
            self._manager_dialog._reload_bookmarks()

    def open_manager(self) -> None:
        if self._manager_dialog is None:
            self._manager_dialog = ManagerDialog(
                self,
                self.pw_manager,
                self.bm_manager,
                self.hist_manager,
                self._open_url_in_new_tab,
            )
        else:
            self._manager_dialog.refresh_all()

        self._manager_dialog.show()
        self._manager_dialog.raise_()
        self._manager_dialog.activateWindow()

    def _open_url_in_new_tab(self, url: str) -> None:
        self.add_new_tab(QUrl(url), url)

    # ==================== ЗАГРУЗКИ ====================

    def _open_downloads_popup(self) -> None:
        if self._dl_popup is None:
            self._dl_popup = DownloadsPopup(self, self.dl_manager)
        gp = self.btn_dl.mapToGlobal(
            QPoint(self.btn_dl.width(), self.btn_dl.height()))
        self._dl_popup.popup_at(gp)

    def _update_dl_badge(self) -> None:
        n = self.dl_manager.active_count()
        if n > 0:
            self.btn_dl.setText(f"⬇{n}")
            self.btn_dl.setStyleSheet(_DL_BTN_QSS_ACTIVE)
        else:
            self.btn_dl.setText("⬇")
            self.btn_dl.setStyleSheet(_DL_BTN_QSS_IDLE)

    # ==================== DEVTOOLS ====================

    def open_devtools(self) -> None:
        b = self.stack.currentWidget()
        if not b:
            return
        page = b.page()

        if self._devtools_window is None:
            self._devtools_window = QMainWindow()
            self._devtools_window.setWindowTitle("DevTools")
            self._devtools_window.resize(1100, 700)
            self._devtools_window.setStyleSheet(
                f"background: {COLOR_BG}; color: {COLOR_TEXT};")
            self._devtools_view = QWebEngineView(self._devtools_window)
            self._devtools_page = QWebEnginePage(
                self.profile, self._devtools_view)
            self._devtools_view.setPage(self._devtools_page)
            self._devtools_window.setCentralWidget(self._devtools_view)

        page.setDevToolsPage(self._devtools_page)
        page.triggerAction(QWebEnginePage.WebAction.InspectElement)
        self._devtools_window.show()
        self._devtools_window.raise_()
        self._devtools_window.activateWindow()

    # ==================== ПРОЧЕЕ ====================

    def view_source(self) -> None:
        b = self.stack.currentWidget()
        if b and b.url().toString():
            self.add_new_tab(
                QUrl("view-source:" + b.url().toString()), "Source")

    def print_page(self) -> None:
        b = self.stack.currentWidget()
        if not b:
            return
        path = os.path.join(
            tempfile.gettempdir(), f"print-{int(os.getpid())}.pdf")
        page = b.page()

        def done(p, ok):
            print(f"[PRINT] {p} ok={ok}", flush=True)
            if ok:
                try:
                    subprocess.Popen(["xdg-open", p])
                except Exception:
                    pass

        try:
            page.pdfPrintingFinished.connect(done)
            page.printToPdf(path)
        except Exception as e:
            print(f"[PRINT] n/a: {e}", flush=True)

    # ==================== СОБЫТИЯ ====================

    def eventFilter(self, obj, event):
        if obj is self.tab_bar and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.MiddleButton:
                idx = self.tab_bar.tabAt(event.pos())
                if idx != -1:
                    self.close_tab(idx)
                    return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        try:
            self.hist_manager.flush()
        except Exception:
            pass

        for win in (self._devtools_window, self._manager_dialog, self._dl_popup):
            if win is not None:
                try:
                    win.close()
                except Exception:
                    pass

        super().closeEvent(event)

    # ==================== РАЗРЕШЕНИЯ ====================

    def handle_permission(self, permission) -> None:
        ptype = permission.permissionType()
        origin = permission.origin().toString()
        name, icon = PERMISSION_NAMES.get(
            ptype, ("Неизвестный доступ", "❓"))
        print(f"[PERM] {name} <- {origin}", flush=True)

        dlg = PermissionDialog(origin, name, icon, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            permission.grant()
            print("[PERM] granted", flush=True)
        else:
            permission.deny()
            print("[PERM] denied", flush=True)
