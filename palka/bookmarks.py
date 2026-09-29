"""Закладки."""
import time

from .storage import JsonStore


class BookmarkManager:
    def __init__(self):
        self.store = JsonStore("bookmarks.json", [])

    def add(self, url: str, title: str) -> None:
        """Добавить или обновить заголовок, если URL уже есть."""
        for b in self.store.data:
            if b.get("url") == url:
                b["title"] = title or b.get("title", "")
                self.store.save()
                return
        self.store.data.append({
            "url": url,
            "title": title or url,
            "added": int(time.time()),
        })
        self.store.save()

    def remove_at(self, idx: int) -> None:
        if 0 <= idx < len(self.store.data):
            del self.store.data[idx]
            self.store.save()

    def is_bookmarked(self, url: str) -> bool:
        return any(b.get("url") == url for b in self.store.data)

    def all(self):
        return list(self.store.data)
