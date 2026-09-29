"""Точка входа. `python3 -m palka` запускает браузер.

Single-instance через flock + QLocalServer:

  1. Пытаемся взять эксклюзивный lock на $XDG_RUNTIME_DIR/palka-<uid>.lock.
     Успех — мы первый экземпляр.
     Провал — другой экземпляр уже работает, шлём ему URL и выходим.
     Второй процесс НИКОГДА не запускается с тем же профилем.

  2. Первый экземпляр слушает QLocalServer, принимает URL от последующих
     запусков и открывает их в новых вкладках.
"""
import os
import sys
import fcntl
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QSurfaceFormat
from PyQt6.QtCore import QUrl
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

from .theme import apply_dark_app_theme
from .browser_window import MiniBrowser


SOCKET_NAME = "palka-single-instance"
RUNTIME_DIR = Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp")
LOCK_FILE = RUNTIME_DIR / f"palka-{os.getuid()}.lock"


def try_acquire_lock():
    """Эксклюзивный flock на lock-файл.

    Возвращает file object (держать открытым) или None, если уже занят.
    """
    try:
        f = open(LOCK_FILE, "w")
    except OSError as e:
        print(f"[LOCK] cannot open {LOCK_FILE}: {e}", flush=True)
        return None
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        f.write(str(os.getpid()))
        f.flush()
        return f
    except OSError:
        f.close()
        return None


def send_to_existing(url: str) -> bool:
    """Одна попытка передать URL живому экземпляру.

    True — доставлено, можно выходить.
    False — не получилось (сервер не отвечает или его нет).
    """
    sock = QLocalSocket()
    sock.connectToServer(SOCKET_NAME)
    if not sock.waitForConnected(1000):
        return False

    sock.write((url + "\n").encode("utf-8"))
    sock.flush()
    if not sock.waitForBytesWritten(1000):
        sock.disconnectFromServer()
        return False

    # Ждём ACK. Сервер отвечает ДО add_new_tab, так что 3 секунды
    # — с большим запасом.
    if not sock.waitForReadyRead(3000):
        sock.disconnectFromServer()
        return False

    ack = bytes(sock.readAll().data()).decode("utf-8", errors="ignore").strip()
    sock.disconnectFromServer()
    return ack == "OK"


def main():
    fmt = QSurfaceFormat.defaultFormat()
    fmt.setSwapInterval(0)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    apply_dark_app_theme()

    # URL из аргументов командной строки
    url_arg = None
    if len(sys.argv) > 1:
        candidate = sys.argv[-1]
        if candidate.startswith(("http://", "https://", "file://")):
            url_arg = candidate

    # --- Шаг 1: пытаемся взять lock ---
    lock = try_acquire_lock()

    if lock is None:
        # Другой экземпляр уже работает. Одна попытка передать URL —
        # БЕЗ retry, иначе сервер получит URL дважды и откроет две вкладки.
        if url_arg:
            if not send_to_existing(url_arg):
                print(f"[IPC] existing instance did not respond, "
                      f"dropping URL: {url_arg}", flush=True)
        # В любом случае не запускаем второе окно.
        return

    # --- Шаг 2: мы первый экземпляр ---
    # Чистим stale-сокет от предыдущего краша (lock уже наш, значит
    # точно никакой живой сервер его не держит).
    QLocalServer.removeServer(SOCKET_NAME)

    server = QLocalServer()
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    if not server.listen(SOCKET_NAME):
        print(f"[IPC] cannot listen on {SOCKET_NAME}: "
              f"{server.errorString()}", flush=True)

    window = MiniBrowser()
    window.show()

    if url_arg:
        window.add_new_tab(QUrl(url_arg), "Открыть")

    def on_new_connection():
        conn = server.nextPendingConnection()
        if conn is None:
            return

        # Флаг: обработать соединение ровно один раз.
        # readyRead может эмититься несколько раз — данные приходят
        # частями. Без флага мы бы парсили буфер повторно и
        # дублировали вкладки.
        state = {"done": False}

        def on_ready():
            if state["done"]:
                return

            data = bytes(conn.readAll().data()).decode(
                "utf-8", errors="ignore")

            # Ждём терминатор строки — клиент шлёт "URL\n".
            # Если "\n" ещё нет, данные неполные, ждём следующего readyRead.
            if "\n" not in data:
                return

            state["done"] = True

            urls = []
            for line in data.split("\n"):
                line = line.strip()
                if line.startswith(("http://", "https://", "file://")):
                    urls.append(line)

            # ACK ОБЯЗАТЕЛЬНО до add_new_tab — add_new_tab блокирует
            # event loop на 500+ мс, а клиент за это время устанет ждать.
            conn.write(b"OK\n")
            conn.flush()
            conn.disconnectFromServer()

            for u in urls:
                window.add_new_tab(QUrl(u), "Открыть")

            if urls:
                if window.isMinimized():
                    window.showNormal()
                window.raise_()
                window.activateWindow()

        conn.readyRead.connect(on_ready)

    server.newConnection.connect(on_new_connection)

    # --- Cleanup при выходе ---
    def on_quit():
        try:
            server.close()
            QLocalServer.removeServer(SOCKET_NAME)
        except Exception:
            pass
        try:
            lock.close()
        except Exception:
            pass

    app.aboutToQuit.connect(on_quit)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
