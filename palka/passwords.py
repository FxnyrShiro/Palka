"""Менеджер паролей + мост в JS.

Обфускация значений — в storage.obfuscate/deobfuscate.
Мост работает по request/response протоколу через QWebChannel.
"""
import json

from PyQt6.QtCore import QObject, pyqtSlot

from .storage import JsonStore, obfuscate, deobfuscate


class PasswordManager:
    def __init__(self):
        self.store = JsonStore("passwords.json", {})

    # ---------- API ----------

    def set(self, origin: str, username: str, password: str) -> None:
        self.store.data[origin] = {
            "u": obfuscate(username),
            "p": obfuscate(password),
        }
        self.store.save()

    def get(self, origin: str):
        rec = self.store.data.get(origin)
        if not rec:
            return None
        return {
            "username": deobfuscate(rec.get("u", "")),
            "password": deobfuscate(rec.get("p", "")),
        }

    def remove(self, origin: str) -> None:
        if origin in self.store.data:
            del self.store.data[origin]
            self.store.save()

    def all(self):
        """Список (origin, username, password) для UI."""
        out = []
        for origin in sorted(self.store.data.keys()):
            c = self.get(origin)
            if c:
                out.append((origin, c["username"], c["password"]))
        return out


class PasswordBridge(QObject):
    """Мост JS <-> PasswordManager.

    JS вызывает bridge.call(id, json), Python асинхронно доставляет
    ответ через runJavaScript("window.__deliverPwResponse(id, resp)").
    """

    def __init__(self, page, manager: PasswordManager, parent=None):
        super().__init__(parent)
        self.page = page
        self.manager = manager

    @pyqtSlot(str, str)
    def call(self, request_id: str, payload_json: str) -> None:
        try:
            response = self._dispatch(payload_json)
        except Exception as e:
            print(f"[PW] dispatch error: {e}", flush=True)
            response = json.dumps({"ok": False, "error": str(e)})

        js = "window.__deliverPwResponse(%s, %s);" % (
            json.dumps(request_id),
            json.dumps(response),
        )
        self.page.runJavaScript(js)

    def _dispatch(self, payload_json: str) -> str:
        try:
            p = json.loads(payload_json)
        except Exception:
            return '{"ok": false}'

        m = p.get("m", "?")
        if m == "getCredentials":
            return self._get(p.get("origin", ""))
        if m == "saveCredentials":
            return self._save(
                p.get("origin", ""),
                p.get("username", ""),
                p.get("password", ""),
            )
        return '{"ok": true}'

    def _get(self, origin: str) -> str:
        c = self.manager.get(origin)
        if c and c.get("username"):
            return json.dumps({"ok": True, **c})
        return '{"ok": false}'

    def _save(self, origin: str, username: str, password: str) -> str:
        if not origin or not password:
            return '{"ok": false}'
        existing = self.manager.get(origin)
        if (existing
                and existing.get("username") == username
                and existing.get("password") == password):
            return '{"ok": true, "cached": true}'
        print(f"[PW] saved for {origin} (user={username!r})", flush=True)
        self.manager.set(origin, username, password)
        return '{"ok": true}'
