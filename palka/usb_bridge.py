"""Мост между JS-шимом и реальным USB через pyusb.

Используется request/response паттерн через QWebChannel:
  JS:    window.__usbBridge.call(id, json)
  Python: on call() -> runJavaScript("window.__deliverResponse(id, resp)")

Почему не возвращаем значение напрямую из pyqtSlot?
  В PyQt6 QWebChannel иногда возвращает null в JS вместо строки.
  runJavaScript надёжнее.
"""
import json

import usb.core
import usb.util

from PyQt6.QtCore import QObject, pyqtSlot

from .constants import (
    SWITCH_VID, SWITCH_PID, PACKET_SIZE, USB_MODE,
)


# ==================== ХЕЛПЕРЫ ====================

def _request_type_to_byte(setup) -> int:
    """WebUSB setup -> bmRequestType байт для pyusb."""
    if not isinstance(setup, dict):
        setup = {}

    direction = setup.get("direction", "out")
    rt = 0x80 if direction == "in" else 0x00

    t = setup.get("requestType", "standard")
    if t == "class":
        rt |= 0x20
    elif t == "vendor":
        rt |= 0x40
    elif t == "reserved":
        rt |= 0x60

    r = setup.get("recipient", "device")
    if r == "interface":
        rt |= 0x01
    elif r == "endpoint":
        rt |= 0x02
    elif r == "other":
        rt |= 0x03

    return rt


# ==================== МОСТ ====================

class UsbBridge(QObject):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self.dev = None
        self.claimed_interfaces = set()
        self.out_buffer = bytearray()

    # ---------- входная точка ----------

    @pyqtSlot(str, str)
    def call(self, request_id: str, payload_json: str) -> None:
        try:
            response = self._dispatch(payload_json)
        except Exception as e:
            print(f"[WEBUSB] dispatch error: {e}", flush=True)
            response = json.dumps({"ok": False, "error": str(e)})

        js = "window.__deliverResponse(%s, %s);" % (
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
        handler = {
            "requestDevice":       lambda: self._on_request_device(p.get("filters")),
            "open":                self._on_open,
            "close":               self._on_close,
            "selectConfiguration": lambda: self._on_select_configuration(p.get("n")),
            "claimInterface":      lambda: self._on_claim_interface(p.get("n")),
            "releaseInterface":    lambda: self._on_release_interface(p.get("n")),
            "controlTransferOut":  lambda: self._on_control_transfer_out(p),
            "controlTransferIn":   lambda: self._on_control_transfer_in(p),
            "transferOut":         lambda: self._on_transfer_out(p),
            "transferIn":          lambda: self._on_transfer_in(p),
        }.get(m)

        if handler is None:
            print(f"[WEBUSB] unhandled: {m}", flush=True)
            return '{"ok": true}'
        return handler()

    # ---------- device ----------

    def _on_request_device(self, filters) -> str:
        if USB_MODE == "logger":
            print("[WEBUSB] (logger) requestDevice", flush=True)
            return '{"ok": true}'
        try:
            dev = usb.core.find(idVendor=SWITCH_VID, idProduct=SWITCH_PID)
        except Exception as e:
            print(f"[WEBUSB] find error: {e}", flush=True)
            dev = None

        if dev is None:
            print("[WEBUSB] !! Switch RCM не найден (0955:7321)", flush=True)
            return '{"ok": false, "error": "Switch RCM not found"}'

        self.dev = dev
        self.out_buffer.clear()
        print(f"[WEBUSB] found: bus={dev.bus} addr={dev.address}", flush=True)
        return '{"ok": true}'

    def _on_open(self) -> str:
        print("[WEBUSB] open", flush=True)
        return '{"ok": true}'

    def _on_close(self) -> str:
        print("[WEBUSB] close", flush=True)
        self._flush_out_buffer()
        if self.dev is not None:
            for n in list(self.claimed_interfaces):
                try:
                    usb.util.release_interface(self.dev, n)
                except Exception:
                    pass
            try:
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
            self.dev = None
        self.claimed_interfaces.clear()
        self.out_buffer.clear()
        return '{"ok": true}'

    def _on_select_configuration(self, n) -> str:
        print(f"[WEBUSB] selectConfiguration({n})", flush=True)
        if self.dev is None or USB_MODE == "logger":
            return '{"ok": true}'
        try:
            self.dev.set_configuration(n)
        except usb.core.USBError as e:
            print(f"[WEBUSB]   (set_configuration skipped: {e})", flush=True)
        return '{"ok": true}'

    def _on_claim_interface(self, n) -> str:
        print(f"[WEBUSB] claimInterface({n})", flush=True)
        if self.dev is None or USB_MODE == "logger":
            return '{"ok": true}'
        try:
            usb.util.claim_interface(self.dev, n)
            self.claimed_interfaces.add(n)
        except usb.core.USBError as e:
            print(f"[WEBUSB]   claim error: {e}", flush=True)
            return json.dumps({"ok": False, "error": str(e)})
        return '{"ok": true}'

    def _on_release_interface(self, n) -> str:
        print(f"[WEBUSB] releaseInterface({n})", flush=True)
        if self.dev is None or USB_MODE == "logger":
            return '{"ok": true}'
        try:
            usb.util.release_interface(self.dev, n)
            self.claimed_interfaces.discard(n)
        except usb.core.USBError:
            pass
        return '{"ok": true}'

    # ---------- control transfers ----------

    def _on_control_transfer_out(self, p) -> str:
        self._flush_out_buffer()
        setup = p.get("setup") or {}
        hex_data = p.get("hex", "")
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            return '{"ok": true}'

        rt = _request_type_to_byte(setup)
        req = setup.get("request", 0) if isinstance(setup, dict) else 0
        val = setup.get("value", 0) if isinstance(setup, dict) else 0
        idx = setup.get("index", 0) if isinstance(setup, dict) else 0

        print(
            f"[WEBUSB] controlTransferOut rt=0x{rt:02x} req=0x{req:02x} "
            f"val=0x{val:04x} idx=0x{idx:04x} len={len(data)}",
            flush=True,
        )

        if self.dev is None or USB_MODE == "logger":
            return '{"ok": true}'

        try:
            self.dev.ctrl_transfer(
                bmRequestType=rt, bRequest=req,
                wValue=val, wIndex=idx,
                data_or_wLength=data, timeout=10000,
            )
        except usb.core.USBError as e:
            print(f"[WEBUSB]   ctrl_transfer failed: {e}", flush=True)
            return json.dumps({"ok": False, "error": str(e)})
        return '{"ok": true}'

    def _on_control_transfer_in(self, p) -> str:
        """Control-IN через USBDEVFS_SUBMITURB + DISCARDURB.

        Как делает Chrome:
          SUBMITURB -> (короткая задержка) -> DISCARDURB

        Setup-пакет должен уйти на контроллер, но URB — не завершиться.
        Chrome делаёт это между двумя процессами (submit в одном, discard
        в другом), между ними IPC-задержка. Мы эмулируем её через sleep.
        """
        import os
        import time
        import fcntl
        import struct
        import ctypes

        self._flush_out_buffer()

        length = int(p.get("length", 0))
        if length <= 0:
            return '{"ok": true, "hex": ""}'

        setup = p.get("setup") or {}
        rt = _request_type_to_byte(setup) | 0x80
        req = setup.get("request", 0) if isinstance(setup, dict) else 0
        val = setup.get("value", 0) if isinstance(setup, dict) else 0
        idx = setup.get("index", 0) if isinstance(setup, dict) else 0

        total_len = 8 + length
        buf_c = ctypes.create_string_buffer(total_len)
        struct.pack_into("<BBHHH", buf_c, 0, rt, req, val, idx, length)
        buf_ptr = ctypes.addressof(buf_c)

        print(
            f"[WEBUSB] controlTransferIn setup={bytes(buf_c[:8]).hex()} "
            f"len={length}",
            flush=True,
        )

        if self.dev is None or USB_MODE == "logger":
            return json.dumps({"ok": True, "hex": "00" * length})

        try:
            bus = int(self.dev.bus)
            addr = int(self.dev.address)
        except Exception as e:
            print(f"[WEBUSB]   cannot resolve bus/addr: {e}", flush=True)
            return json.dumps({"ok": True, "hex": "00" * length})

        path = f"/dev/bus/usb/{bus:03d}/{addr:03d}"
        iface_num = next(iter(self.claimed_interfaces), 0)

        # Отпускаем pyusb перед usbfs-работой
        print("[WEBUSB]   releasing pyusb resources...", flush=True)
        try:
            for n in list(self.claimed_interfaces):
                try:
                    usb.util.release_interface(self.dev, n)
                except Exception:
                    pass
            try:
                usb.util.dispose_resources(self.dev)
            except Exception:
                pass
        except Exception as e:
            print(f"[WEBUSB]   dispose warning: {e}", flush=True)
        self.dev = None
        self.claimed_interfaces.clear()

        USBDEVFS_URB_TYPE_CONTROL = 2
        packed_buf = ctypes.create_string_buffer(56)
        struct.pack_into(
            "<BB2xI I 4xQ i i i i i I Q",
            packed_buf, 0,
            USBDEVFS_URB_TYPE_CONTROL,
            0, 0, 0,
            buf_ptr,
            total_len,
            0, 0, 0, 0, 0,
            0,
        )

        USBDEVFS_SUBMITURB        = 0x8038550A
        USBDEVFS_DISCARDURB       = 0x0000550B
        USBDEVFS_CLAIMINTERFACE   = 0x8004550F
        USBDEVFS_RELEASEINTERFACE = 0x80045510

        fd = -1
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError as e:
            print(f"[WEBUSB]   cannot open {path}: {e}", flush=True)
            return json.dumps({"ok": True, "hex": "00" * length})

        print(f"[WEBUSB]   opened fd={fd}", flush=True)

        try:
            # CLAIM
            try:
                fcntl.ioctl(fd, USBDEVFS_CLAIMINTERFACE,
                            struct.pack("I", iface_num))
                print(f"[WEBUSB]   claimed iface {iface_num}", flush=True)
            except OSError as e:
                print(f"[WEBUSB]   claim errno={e.errno}: {e}", flush=True)

            # --- SUBMITURB ---
            fcntl.ioctl(fd, USBDEVFS_SUBMITURB, packed_buf)
            print("[WEBUSB]   submiturb ok", flush=True)

            # --- Пауза 5 мс: setup уходит на контроллер, но URB не завершается ---
            time.sleep(0.001)

            # --- DISCARDURB ---
            try:
                fcntl.ioctl(fd, USBDEVFS_DISCARDURB, packed_buf)
                print("[WEBUSB]   discardurb ok — trigger fired", flush=True)
            except OSError as e:
                print(
                    f"[WEBUSB]   discardurb errno={e.errno}: {e}",
                    flush=True,
                )

            return json.dumps({"ok": True, "hex": "00" * length})

        except OSError as e:
            print(f"[WEBUSB]   ioctl errno={e.errno}: {e}", flush=True)
            return json.dumps({"ok": True, "hex": "00" * length})

        except Exception as e:
            print(f"[WEBUSB]   unexpected: {e}", flush=True)
            return json.dumps({"ok": True, "hex": "00" * length})

        finally:
            if fd >= 0:
                try:
                    fcntl.ioctl(fd, USBDEVFS_RELEASEINTERFACE,
                                struct.pack("I", iface_num))
                except Exception:
                    pass
                try:
                    os.close(fd)
                except Exception:
                    pass
                            
    # ---------- bulk transfers ----------

    def _on_transfer_out(self, p) -> str:
        ep = int(p.get("ep", 1))
        hex_data = p.get("hex", "")
        try:
            data = bytes.fromhex(hex_data)
        except ValueError:
            return '{"ok": true}'

        print(
            f"[WEBUSB] transferOut ep={ep} buffered len={len(data)} "
            f"total={len(self.out_buffer) + len(data)} head={hex_data[:16]}",
            flush=True,
        )

        if self.dev is None or USB_MODE == "logger":
            return json.dumps({"ok": True, "written": len(data)})

        # Собираем в буфер, отправим одним bulk-трансфером при flush
        self.out_buffer.extend(data)
        return json.dumps({"ok": True, "written": len(data)})

    def _flush_out_buffer(self) -> None:
        """Отправка накопленного буфера на USB.

        Пишем чанками по 4 КБ. ZLP не шлём — Chrome через libusb его
        тоже не шлёт. Bulk-запрос идёт на endpoint 0x01.

        Формат payload и структура чанков полностью приходят от сайта
        (WebRCM), мы их не трогаем — только проксируем в USB.
        """
        if not self.out_buffer:
            return
        if self.dev is None:
            self.out_buffer.clear()
            return

        total = len(self.out_buffer)
        num_packets = (total + PACKET_SIZE - 1) // PACKET_SIZE
        print(
            f"[WEBUSB] flushing {total} bytes "
            f"({num_packets} packets of {PACKET_SIZE})...",
            flush=True,
        )

        data = bytes(self.out_buffer)
        offset = 0
        write_count = 0

        while offset < total:
            chunk = data[offset:offset + PACKET_SIZE]
            try:
                self.dev.write(0x01, chunk, timeout=5000)
                write_count += 1
            except usb.core.USBError as e:
                print(
                    f"[WEBUSB]   write failed at packet {write_count}: {e}",
                    flush=True,
                )
                break
            offset += len(chunk)

        print(
            f"[WEBUSB]   -> wrote {write_count} packets, "
            f"total {offset}/{total} bytes",
            flush=True,
        )
        self.out_buffer.clear()

    def _on_transfer_in(self, p) -> str:
        ep = int(p.get("ep", 1))
        length = int(p.get("length", 0))
        print(f"[WEBUSB] transferIn ep={ep} len={length}", flush=True)

        if self.dev is None or USB_MODE == "logger":
            return json.dumps({"ok": True, "hex": "00" * length})

        addr = (ep & 0x0F) | 0x80
        try:
            data = self.dev.read(addr, length, timeout=1000)
            hex_data = bytes(data).hex()
            print(f"[WEBUSB]   -> {len(data)} bytes, head={hex_data[:32]}", flush=True)
            return json.dumps({"ok": True, "hex": hex_data})
        except usb.core.USBError as e:
            print(f"[WEBUSB]   read failed: {e}", flush=True)
            return json.dumps({"ok": True, "hex": "00" * length})
