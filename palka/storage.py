"""JSON-хранилище и обфускация для паролей.

Обфускация — XOR с ключом, производным от $USER и hostname.
Это НЕ криптография: защищает от случайного просмотра файла,
но не от целенаправленного взлома.
"""
import os
import json
import base64
import hashlib
from pathlib import Path
from typing import Any

from .constants import CONFIG_DIR


# ==================== ОБФУСКАЦИЯ ====================

def _machine_key() -> bytes:
    seed = (os.environ.get("USER", "user") + "|" + os.uname().nodename).encode()
    return hashlib.sha256(seed).digest()


def _xor_bytes(data: bytes) -> bytes:
    key = _machine_key()
    out = bytearray(len(data))
    for i, b in enumerate(data):
        out[i] = b ^ key[i % len(key)]
    return bytes(out)


def obfuscate(s: str) -> str:
    return base64.b64encode(_xor_bytes(s.encode("utf-8"))).decode("ascii")


def deobfuscate(s: str) -> str:
    try:
        return _xor_bytes(base64.b64decode(s)).decode("utf-8")
    except Exception:
        return ""


# ==================== ХРАНИЛИЩЕ ====================

class JsonStore:
    """Простой JSON-стор с правами 600 на файл.

    data — dict или list, в зависимости от default.
    """

    def __init__(self, name: str, default: Any):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.path = CONFIG_DIR / name
        self.default = default
        self.data = default.copy() if isinstance(default, dict) else list(default)
        self.load()

    def load(self) -> None:
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[STORE] {self.path.name} load error: {e}", flush=True)

    def save(self) -> None:
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            try:
                os.chmod(self.path, 0o600)
            except Exception:
                pass
        except Exception as e:
            print(f"[STORE] {self.path.name} save error: {e}", flush=True)
