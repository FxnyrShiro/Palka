/*
 * Автозаполнение и сохранение логинов/паролей.
 *
 * Инжектируется в InjectionPoint.DocumentReady, MainWorld, только верхний фрейм.
 *
 * Схема:
 *   - Просим у Python креды для location.origin, если есть — заполняем.
 *   - Ловим момент "пользователь отправил форму" (submit, Enter, click,
 *     beforeunload, SPA-переходы через history API) и отправляем данные в Python.
 *
 * Юзернейм запоминается в sessionStorage, потому что SPA-логины (Google,
 * Reddit) показывают email и пароль на разных экранах: когда мы видим
 * пароль, поля email в DOM уже нет.
 */
(function () {
    if (window.__pw_manager_installed) return;
    window.__pw_manager_installed = true;

    // ===== Async-мост с Python =====
    window.__pendingPwRequests = {};
    window.__deliverPwResponse = function (id, resp) {
        const cb = window.__pendingPwRequests[id];
        if (cb) {
            delete window.__pendingPwRequests[id];
            cb(resp);
        }
    };

    function callBridge(p) {
        return new Promise((resolve, reject) => {
            const id = "pw_" + Date.now() + "_" + Math.random().toString(36).slice(2);
            window.__pendingPwRequests[id] = resolve;
            (function tryCall() {
                if (window.__pwBridge) {
                    window.__pwBridge.call(id, JSON.stringify(p));
                } else {
                    setTimeout(tryCall, 30);
                }
            })();
            setTimeout(() => {
                if (window.__pendingPwRequests[id]) {
                    delete window.__pendingPwRequests[id];
                    reject(new Error("pw timeout"));
                }
            }, 15000);
        });
    }

    // ===== Кэш юзернейма между экранами SPA =====
    let rememberedUser = "";
    try {
        const s = sessionStorage.getItem("__pw_remembered_user");
        if (s) rememberedUser = s;
    } catch (e) {}

    function rememberUser(v) {
        if (!v) return;
        rememberedUser = v;
        try {
            sessionStorage.setItem("__pw_remembered_user", v);
        } catch (e) {}
    }

    // ===== Поиск полей =====
    function pwInputs() {
        return Array.from(document.querySelectorAll('input[type="password"]'));
    }

    function userField(scope) {
        const r = scope || document;
        return r.querySelector(
            'input[type="text"], input[type="email"], ' +
            'input[name*="user" i], input[name*="login" i], ' +
            'input[name*="email" i], input[autocomplete="username"]'
        );
    }

    // ===== Автозаполнение =====
    function autofill() {
        const ps = pwInputs();
        if (ps.length === 0) return;
        callBridge({ m: "getCredentials", origin: location.origin }).then(r => {
            let j;
            try {
                j = JSON.parse(r);
            } catch (e) {
                return;
            }
            if (!j.ok || !j.username) return;
            rememberUser(j.username);

            const u = userField(document);
            if (u && !u.value) {
                u.value = j.username;
                u.dispatchEvent(new Event('input', { bubbles: true }));
                u.dispatchEvent(new Event('change', { bubbles: true }));
            }
            ps.forEach(p => {
                if (!p.value) {
                    p.value = j.password;
                    p.dispatchEvent(new Event('input', { bubbles: true }));
                    p.dispatchEvent(new Event('change', { bubbles: true }));
                }
            });
        }).catch(() => {});
    }

    // ===== Сохранение =====
    let lastSave = { user: "", pass: "", t: 0 };

    function capture(reason) {
        const ps = pwInputs();
        if (ps.length === 0) return;
        const p = ps[0];
        const pass = p.value || "";
        if (pass.length < 2) return;

        let user = "";
        const u = userField(document);
        user = (u && u.value) ? u.value : rememberedUser;

        const now = Date.now();
        if (lastSave.user === user && lastSave.pass === pass
            && (now - lastSave.t) < 2000) {
            return;
        }
        lastSave = { user, pass, t: now };

        console.log("[PW] capture (" + reason + "): user=" + JSON.stringify(user));
        callBridge({
            m: "saveCredentials",
            origin: location.origin,
            username: user,
            password: pass,
        }).catch(() => {});
    }

    // ===== Отслеживание ввода =====
    function onInput(e) {
        const t = e.target;
        if (!t || t.tagName !== "INPUT") return;
        if (t.type === "password" && t.value) {
            const f = t.closest("form");
            const scope = f || t.parentElement || document;
            const u = userField(scope);
            if (u && u.value) rememberUser(u.value);
        }
        if ((t.type === "text" || t.type === "email") && t.value) {
            rememberUser(t.value);
        }
    }

    document.addEventListener("input", onInput, true);

    // Enter на поле пароля — типичный триггер submit
    document.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && e.target && e.target.type === "password") {
            setTimeout(() => capture("enter"), 50);
        }
    }, true);

    // Клик по кнопке — на случай кастомных форм без form.submit
    document.addEventListener("click", (e) => {
        const t = e.target;
        if (!t || !t.tagName) return;
        const isSubmitLike =
            t.tagName === "BUTTON" ||
            (t.tagName === "INPUT" && (t.type === "submit" || t.type === "button"));
        if (isSubmitLike) {
            setTimeout(() => capture("click"), 50);
        }
    }, true);

    // Уход со страницы — последний шанс сохранить
    window.addEventListener("beforeunload", () => capture("beforeunload"), true);
    window.addEventListener("pagehide", () => capture("pagehide"), true);

    // SPA-переходы
    const _pushState = history.pushState;
    const _replaceState = history.replaceState;
    history.pushState = function () {
        const r = _pushState.apply(this, arguments);
        setTimeout(() => capture("pushState"), 100);
        return r;
    };
    history.replaceState = function () {
        const r = _replaceState.apply(this, arguments);
        setTimeout(() => capture("replaceState"), 100);
        return r;
    };
    window.addEventListener("popstate", () => setTimeout(() => capture("popstate"), 100));

    // ===== Первые попытки =====
    autofill();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => setTimeout(autofill, 200), { once: true });
    }
    setTimeout(autofill, 500);
    setTimeout(autofill, 1500);
    setTimeout(autofill, 3000);
})();
