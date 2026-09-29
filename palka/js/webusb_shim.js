/*
 * WebUSB-шим для Tegra RCM (WebRCM).
 *
 * Инжектируется в InjectionPoint.DocumentCreation, MainWorld, все фреймы.
 * Загружается вместе с qwebchannel.js — тот код идёт перед этим.
 *
 * Задача: подменить navigator.usb и проксировать все вызовы в Python
 * через QWebChannel. Python общается с реальным USB через pyusb.
 *
 * Используется request/response протокол с ID, потому что pyqtSlot с
 * result=str в PyQt6 через QWebChannel иногда возвращает null в JS.
 */
(function () {
    if (window.__webusb_shim_installed) return;
    window.__webusb_shim_installed = true;

    // ===== Очередь отложенных ответов =====
    window.__pendingRequests = {};
    window.__deliverResponse = function (id, resp) {
        const cb = window.__pendingRequests[id];
        if (cb) {
            delete window.__pendingRequests[id];
            cb(resp);
        }
    };

    // ===== Утилиты =====
    function toHex(data) {
        try {
            let v;
            if (data instanceof ArrayBuffer) v = new Uint8Array(data);
            else if (data && data.buffer) v = new Uint8Array(data.buffer);
            else v = new Uint8Array(data);
            let s = "";
            for (let i = 0; i < v.length; i++) {
                s += v[i].toString(16).padStart(2, "0");
            }
            return s;
        } catch (e) {
            return "";
        }
    }

    function hexToDV(hex) {
        if (!hex) hex = "";
        const n = hex.length / 2;
        const b = new ArrayBuffer(n);
        const v = new Uint8Array(b);
        for (let i = 0; i < n; i++) {
            v[i] = parseInt(hex.substr(i * 2, 2), 16);
        }
        return new DataView(b);
    }

    function callBridge(p) {
        return new Promise((res, rej) => {
            const id = "req_" + Date.now() + "_" + Math.random().toString(36).slice(2);
            window.__pendingRequests[id] = res;
            (function t() {
                if (window.__usbBridge) {
                    window.__usbBridge.call(id, JSON.stringify(p));
                } else {
                    setTimeout(t, 20);
                }
            })();
            setTimeout(() => {
                if (window.__pendingRequests[id]) {
                    delete window.__pendingRequests[id];
                    rej(new Error("timeout"));
                }
            }, 30000);
        });
    }

    // ===== Фейковое устройство =====
    function fakeDevice() {
        return {
            vendorId: 0x0955,
            productId: 0x7321,
            productName: "APX",
            manufacturerName: "NVIDIA Corp.",
            serialNumber: "",
            opened: false,
            configuration: null,

            open: function () {
                const s = this;
                return callBridge({ m: "open" }).then(r => {
                    const j = JSON.parse(r);
                    if (!j.ok) throw new Error(j.error);
                    s.opened = true;
                });
            },
            close: function () {
                const s = this;
                return callBridge({ m: "close" }).then(() => { s.opened = false; });
            },
            selectConfiguration: function (n) {
                return callBridge({ m: "selectConfiguration", n: n }).then(() => {});
            },
            claimInterface: function (n) {
                return callBridge({ m: "claimInterface", n: n }).then(r => {
                    const j = JSON.parse(r);
                    if (!j.ok) throw new Error(j.error);
                });
            },
            releaseInterface: function (n) {
                return callBridge({ m: "releaseInterface", n: n }).then(() => {});
            },
            reset: function () {
                return callBridge({ m: "reset" }).then(() => {});
            },
            controlTransferOut: function (setup, data) {
                const hex = toHex(data);
                return callBridge({
                    m: "controlTransferOut",
                    setup: setup,
                    len: hex.length / 2,
                    hex: hex,
                }).then(() => ({ status: "ok", bytesWritten: hex.length / 2 }));
            },
            controlTransferIn: function (setup, length) {
                return callBridge({
                    m: "controlTransferIn",
                    setup: setup,
                    length: length,
                }).then(r => {
                    const j = JSON.parse(r);
                    return { status: "ok", data: hexToDV(j.hex || "") };
                });
            },
            transferOut: function (ep, data) {
                const hex = toHex(data);
                return callBridge({
                    m: "transferOut",
                    ep: ep,
                    len: hex.length / 2,
                    hex: hex,
                }).then(r => {
                    const j = JSON.parse(r);
                    return { status: "ok", bytesWritten: j.written || hex.length / 2 };
                });
            },
            transferIn: function (ep, length) {
                return callBridge({
                    m: "transferIn",
                    ep: ep,
                    length: length,
                }).then(r => {
                    const j = JSON.parse(r);
                    return { status: "ok", data: hexToDV(j.hex || "") };
                });
            },
            clearHalt: function (d, ep) {
                return callBridge({ m: "clearHalt", d: d, ep: ep }).then(() => {});
            },
        };
    }

    const fakeUsb = {
        onconnect: null,
        ondisconnect: null,
        getDevices: () => Promise.resolve([]),
        requestDevice: function (filters) {
            return callBridge({ m: "requestDevice", filters: filters }).then(r => {
                const j = JSON.parse(r);
                if (!j.ok) throw new Error(j.error);
                return fakeDevice();
            });
        },
    };

    try {
        Object.defineProperty(navigator, "usb", {
            configurable: true,
            enumerable: true,
            get: () => fakeUsb,
        });
        console.log("[shim] navigator.usb installed");
    } catch (e) {
        console.error("[shim] failed to install navigator.usb:", e);
    }

    // ===== Подключение к QWebChannel =====
    function connect() {
        if (!window.qt || !window.qt.webChannelTransport) {
            return setTimeout(connect, 30);
        }
        new QWebChannel(qt.webChannelTransport, function (ch) {
            window.__usbBridge = ch.objects.usbBridge;
            window.__pwBridge = ch.objects.pwBridge;
            console.log("[shim] bridges connected");
        });
    }
    connect();
})();
