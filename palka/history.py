"""История посещений.

Хранится до MAX записей. Дубликаты по URL схлопываются: при повторном
визите запись перемещается наверх с новым timestamp.

Запись на диск — с дебаунсом (не чаще раза в 2 секунды), чтобы не
тормозить навигацию.
"""
import time

from .storage import JsonStore


class HistoryManager:
    MAX = 5000
    SAVE_INTERVAL = 2  # сек

    def __init__(self):
        self.store = JsonStore("history.json", [])
        self._last_url = None
        self._last_save = 0.0

    def add(self, url: str, title: str) -> None:
        if not url or url.startswith(("about:", "view-source:")):
            return
        if url == self._last_url:
            return
        self._last_url = url

        # Удаляем старую запись с этим URL, если есть
        self.store.data = [h for h in self.store.data if h.get("url") != url]
        self.store.data.insert(0, {
            "url": url,
            "title": title or url,
            "ts": int(time.time()),
        })
        if len(self.store.data) > self.MAX:
            self.store.data = self.store.data[:self.MAX]

        now = time.time()
        if now - self._last_save > self.SAVE_INTERVAL:
            self.store.save()
            self._last_save = now

    def flush(self) -> None:
        """Сохранить немедленно — вызывается при закрытии окна."""
        self.store.save()

    def remove_at(self, idx: int) -> None:
        if 0 <= idx < len(self.store.data):
            del self.store.data[idx]
            self.store.save()

    def clear(self) -> None:
        self.store.data = []
        self.store.save()

    def all(self):
        return list(self.store.data)
