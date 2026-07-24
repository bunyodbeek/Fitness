/*
 * tg_auth.js — Telegram Mini App sessiya autentifikatsiyasi (yagona manba).
 *
 * Muammo: `Telegram.WebApp.initDataUnsafe.user.id` ishonchsiz — ba'zan bo'sh
 * bo'ladi va "Telegram ID topilmadi" xatosini keltirib chiqaradi.
 *
 * Yechim: hech qachon initDataUnsafe'dan ID o'qimaymiz. Faqat imzolangan xom
 * `Telegram.WebApp.initData` satrini backendga yuboramiz; backend imzoni
 * tekshirib, foydalanuvchini aniqlaydi va sessiya (cookie) + token qaytaradi.
 * Token xotirada saqlanadi va keyingi AJAX so'rovlariga biriktiriladi.
 *
 * telegram-web-app.js <head> ichida SINxron yuklangan bo'lishi shart — shu fayl
 * undan KEYIN yuklanadi, shuning uchun bu yerda window.Telegram mavjud bo'ladi.
 */
(function (global) {
    'use strict';

    var AUTH_URL = global.__AUTH_URL || '/api/auth/telegram';
    var _token = null;          // sessiya tokeni (faqat xotirada)
    var _authPromise = null;    // takroriy auth chaqiruvlarini birlashtirish uchun

    function tgApp() {
        return (global.Telegram && global.Telegram.WebApp) ? global.Telegram.WebApp : null;
    }

    // Telegram SDK talab qiladi: ready() + expand() ilova ochilishida chaqirilsin.
    function ready() {
        var tg = tgApp();
        if (!tg) return;
        try { tg.ready(); } catch (e) {}
        try { tg.expand(); } catch (e) {}
    }

    function getInitData() {
        var tg = tgApp();
        return (tg && tg.initData) ? tg.initData : '';
    }

    function delay(ms) {
        return new Promise(function (resolve) { setTimeout(resolve, ms); });
    }

    // initData ba'zan SDK poyga holati tufayli birinchi o'qishda bo'sh keladi.
    // 300ms oraliq bilan 3 martagacha qayta urinamiz.
    async function getInitDataWithRetry(retries, waitMs) {
        retries = (typeof retries === 'number') ? retries : 3;
        waitMs = (typeof waitMs === 'number') ? waitMs : 300;
        var data = getInitData();
        var attempts = 0;
        while (!data && attempts < retries) {
            await delay(waitMs);
            data = getInitData();
            attempts++;
        }
        return data;
    }

    function getToken() {
        return _token;
    }

    function setToken(t) {
        _token = t || null;
    }

    function botDeepLink() {
        var link = global.__BOT_DEEPLINK || '';
        if (!link) return '';
        // Mini app initData bilan ochilishi uchun ?startapp bo'lishi kerak.
        if (link.indexOf('startapp') === -1) {
            link += (link.indexOf('?') === -1 ? '?' : '&') + 'startapp';
        }
        return link;
    }

    // "Ilovani bot orqali qayta oching" ekrani (foydalanuvchiga tushunarli, Uzbek).
    function showReopenScreen(message) {
        function render() {
            if (document.getElementById('tgAuthReopen')) return;
            var link = botDeepLink();
            var overlay = document.createElement('div');
            overlay.id = 'tgAuthReopen';
            overlay.setAttribute('style', [
                'position:fixed', 'inset:0', 'z-index:99999',
                'display:flex', 'flex-direction:column',
                'align-items:center', 'justify-content:center',
                'text-align:center', 'padding:24px',
                'background:#000', 'color:#EAEAEA',
                'font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',Roboto,sans-serif'
            ].join(';'));

            var title = document.createElement('div');
            title.setAttribute('style', 'font-size:20px;font-weight:700;margin-bottom:12px;color:#FFD700;');
            title.textContent = 'Ilovani bot orqali oching';

            var text = document.createElement('div');
            text.setAttribute('style', 'font-size:15px;line-height:1.5;max-width:320px;margin-bottom:24px;opacity:.9;');
            text.textContent = message ||
                'Telegram ma’lumotlari yetib kelmadi. Iltimos, ilovani bot ichidagi tugma orqali qayta oching.';

            overlay.appendChild(title);
            overlay.appendChild(text);

            if (link) {
                var btn = document.createElement('a');
                btn.href = link;
                btn.textContent = 'Botni ochish';
                btn.setAttribute('style', [
                    'display:inline-block', 'padding:14px 28px', 'border-radius:12px',
                    'background:#FFD700', 'color:#000', 'font-weight:700',
                    'font-size:16px', 'text-decoration:none'
                ].join(';'));
                overlay.appendChild(btn);
            }

            document.body.appendChild(overlay);
        }

        if (document.body) render();
        else document.addEventListener('DOMContentLoaded', render);
    }

    /*
     * authenticate() — ilova kirish nuqtasida chaqiriladi.
     * 1) ready()/expand()
     * 2) initData ni (retry bilan) oladi
     * 3) bo'sh bo'lsa → reopen ekrani va reject
     * 4) backendga POST qiladi, token'ni saqlaydi va JSON qaytaradi
     *
     * options.silent = true bo'lsa reopen ekrani ko'rsatilmaydi (jimgina qaytadi).
     */
    function authenticate(options) {
        options = options || {};
        if (_authPromise) return _authPromise;

        _authPromise = (async function () {
            ready();
            var initData = await getInitDataWithRetry(3, 300);

            if (!initData) {
                if (!options.silent) showReopenScreen();
                return { success: false, code: 'missing_init_data', empty: true };
            }

            try {
                var res = await fetch(AUTH_URL, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    credentials: 'include',
                    body: JSON.stringify({ init_data: initData })
                });
                var data = await res.json().catch(function () { return {}; });

                if (data && data.success) {
                    if (data.token) setToken(data.token);
                    return data;
                }

                // Backend aniq xato kodini qaytardi (bad_signature / expired / ...).
                if (!options.silent) {
                    showReopenScreen(data && data.error);
                }
                return data || { success: false, code: 'auth_failed' };
            } catch (e) {
                // Tarmoq xatosi — reopen ekranini ko'rsatmaymiz (qayta urinish mumkin).
                console.error('TgAuth network error:', e);
                return { success: false, code: 'network_error' };
            }
        })();

        return _authPromise;
    }

    // Sessiya tokenini biriktirgan fetch (keyingi barcha AJAX so'rovlari uchun).
    function authedFetch(url, opts) {
        opts = opts || {};
        var headers = Object.assign({}, opts.headers || {});
        if (_token) headers['Authorization'] = 'Bearer ' + _token;
        opts.headers = headers;
        if (!('credentials' in opts)) opts.credentials = 'include';
        return fetch(url, opts);
    }

    global.TgAuth = {
        ready: ready,
        getInitData: getInitData,
        getInitDataWithRetry: getInitDataWithRetry,
        authenticate: authenticate,
        authedFetch: authedFetch,
        getToken: getToken,
        setToken: setToken,
        showReopenScreen: showReopenScreen,
        botDeepLink: botDeepLink
    };
})(window);
