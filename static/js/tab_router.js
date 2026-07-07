/*
 * Instant tab navigation for the 5 bottom-nav tabs (no SPA framework).
 *
 * Strategy: stale-while-revalidate HTML fragments.
 *  - Tab links are intercepted; the fragment (?partial=1) is injected into #content.
 *  - A fresh cache hit paints instantly; in parallel we refetch and swap if changed.
 *  - A cold tab shows a black/gold skeleton until the fetch resolves.
 *  - pushState/popstate keep the URL + back button correct.
 *  - Any fetch failure falls back to a normal full navigation.
 *
 * The shell (base.html: tg_viewport init, bottom nav, toasts) stays put and runs
 * exactly once — only #content is swapped, so Telegram init is never re-run.
 */
(function () {
    'use strict';

    var CONTENT_ID = 'content';
    var CACHE_PREFIX = 'tabfrag:';
    var TTL = 5 * 60 * 1000;           // 5 min → stale
    var PREFETCH_DELAY = 2000;

    var contentEl = function () { return document.getElementById(CONTENT_ID); };
    var origin = location.origin;
    var currentPath = location.pathname;   // guards against out-of-order fetches

    // ---- tab set (derived from the bottom nav, so it stays in sync) ----
    function tabPaths() {
        var out = {};
        document.querySelectorAll('.bottom-nav a[href]').forEach(function (a) {
            try { out[new URL(a.href, origin).pathname] = a.href; } catch (e) {}
        });
        return out;
    }
    function isTabPath(p) { return Object.prototype.hasOwnProperty.call(tabPaths(), p); }

    // ---- cache (sessionStorage, keyed by pathname so language prefix is baked in) ----
    function key(path) { return CACHE_PREFIX + path; }
    function readCache(path) {
        try {
            var o = JSON.parse(sessionStorage.getItem(key(path)) || 'null');
            return (o && typeof o.html === 'string') ? o : null;
        } catch (e) { return null; }
    }
    function writeCache(path, html) {
        try { sessionStorage.setItem(key(path), JSON.stringify({ html: html, ts: Date.now() })); }
        catch (e) { /* quota / private mode — just skip caching */ }
    }
    function isFresh(o) { return !!o && (Date.now() - o.ts) < TTL; }

    window.tabCache = {
        invalidate: function (path) {
            try { sessionStorage.removeItem(key(path || location.pathname)); } catch (e) {}
        },
        clearAll: function () {
            try {
                Object.keys(sessionStorage).forEach(function (k) {
                    if (k.indexOf(CACHE_PREFIX) === 0) sessionStorage.removeItem(k);
                });
            } catch (e) {}
        },
        // Invalidate every cached tab whose path contains `substr` (language-agnostic,
        // e.g. invalidateMatch('/favorites/') hits /en|/ru|/uz variants).
        invalidateMatch: function (substr) {
            try {
                Object.keys(sessionStorage).forEach(function (k) {
                    if (k.indexOf(CACHE_PREFIX) === 0 && k.indexOf(substr) >= 0) {
                        sessionStorage.removeItem(k);
                    }
                });
            } catch (e) {}
        }
    };

    // ---- DOM ----
    function setActiveTab(path) {
        document.querySelectorAll('.bottom-nav a[href]').forEach(function (a) {
            var p;
            try { p = new URL(a.href, origin).pathname; } catch (e) { return; }
            a.classList.toggle('active', p === path);
        });
    }

    // innerHTML does not execute <script> — recreate the nodes so they run.
    function runScripts(root) {
        root.querySelectorAll('script').forEach(function (old) {
            var s = document.createElement('script');
            for (var i = 0; i < old.attributes.length; i++) {
                s.setAttribute(old.attributes[i].name, old.attributes[i].value);
            }
            s.textContent = old.textContent;
            old.parentNode.replaceChild(s, old);
        });
    }

    function inject(html, path) {
        var el = contentEl();
        if (!el) return;
        el.innerHTML = html;
        runScripts(el);
        setActiveTab(path);
        window.scrollTo(0, 0);
        try { window.dispatchEvent(new CustomEvent('tab:loaded', { detail: { path: path } })); } catch (e) {}
    }

    function skeleton() {
        return '<div class="tab-skeleton">' +
            '<div class="sk tall"></div><div class="sk"></div>' +
            '<div class="sk"></div><div class="sk"></div></div>';
    }

    function partialUrl(path) {
        return path + (path.indexOf('?') >= 0 ? '&' : '?') + 'partial=1';
    }

    function fetchPartial(path) {
        return fetch(partialUrl(path), {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        }).then(function (r) {
            if (!r.ok) throw new Error('HTTP ' + r.status);
            return r.text();
        });
    }

    // ---- navigate to a tab path (already pushed to history by caller) ----
    function render(path, search) {
        var full = path + (search || '');
        var cacheable = !search;                 // only bare tab URLs are cached
        var cached = cacheable ? readCache(path) : null;
        var painted = false;

        if (isFresh(cached)) {
            inject(cached.html, path);
            painted = true;
        } else {
            inject(skeleton(), path);
        }

        fetchPartial(full).then(function (html) {
            if (currentPath !== path) return;    // user moved on — drop this result
            if (!cached || cached.html !== html) inject(html, path);
            if (cacheable) writeCache(path, html);
        }).catch(function () {
            if (!painted) window.location.assign(full);   // hard fallback
        });
    }

    function go(path, search) {
        var full = path + (search || '');
        if (full !== location.pathname + location.search) {
            history.pushState({ tabRouter: true }, '', full);
        }
        currentPath = path;
        render(path, search);
    }

    // ---- click interception ----
    document.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var a = e.target.closest ? e.target.closest('a[href]') : null;
        if (!a || a.target === '_blank' || a.hasAttribute('download') || a.getAttribute('href').charAt(0) === '#') return;
        var url;
        try { url = new URL(a.href, origin); } catch (e2) { return; }
        if (url.origin !== origin || !isTabPath(url.pathname)) return;
        e.preventDefault();
        if (url.pathname === location.pathname && url.search === location.search) {
            window.scrollTo(0, 0);
            return;
        }
        go(url.pathname, url.search);
    }, false);

    // ---- back / forward ----
    window.addEventListener('popstate', function () {
        var path = location.pathname;
        currentPath = path;
        if (isTabPath(path)) render(path, location.search);
        else window.location.reload();           // left the tab world → full page
    });

    // ---- prefetch the other tabs once the app is idle ----
    function prefetchOthers() {
        try { if (navigator.connection && navigator.connection.saveData) return; } catch (e) {}
        var paths = Object.keys(tabPaths()).filter(function (p) { return p !== location.pathname; });
        (function next(i) {
            if (i >= paths.length) return;
            var p = paths[i];
            if (isFresh(readCache(p))) return next(i + 1);
            fetchPartial(p).then(function (html) { writeCache(p, html); }).catch(function () {})
                .then(function () { next(i + 1); });
        })(0);
    }
    function schedulePrefetch() {
        if (window.requestIdleCallback) requestIdleCallback(prefetchOthers, { timeout: 4000 });
        else setTimeout(prefetchOthers, PREFETCH_DELAY);
    }

    // Full-form-POST pages (profile edit, program import) don't load the router, so
    // they leave a simple "dirty" flag in sessionStorage; consume it here on the next
    // shell load and invalidate the affected tab. Keeps the cache-key convention here.
    try {
        var dirtyFlags = {
            'tabdirty:profile': '/users/profile/',
            'tabdirty:programs': '/gym/programs/'
        };
        Object.keys(dirtyFlags).forEach(function (flag) {
            if (sessionStorage.getItem(flag)) {
                window.tabCache.invalidateMatch(dirtyFlags[flag]);
                sessionStorage.removeItem(flag);
            }
        });
    } catch (e) {}

    // Language switch = full reload to a new /uz|/ru|/en prefix. Detect the change
    // and drop the whole tab cache so no stale-language fragment survives.
    try {
        var curLang = (location.pathname.match(/^\/(en|ru|uz)\//) || [])[1] || '';
        if (sessionStorage.getItem('tabfrag_lang') !== curLang) {
            window.tabCache.clearAll();
            sessionStorage.setItem('tabfrag_lang', curLang);
        }
    } catch (e) {}

    // Tag the initial entry so the first Back behaves predictably, then warm the cache.
    try { history.replaceState({ tabRouter: true }, '', location.href); } catch (e) {}
    if (document.readyState === 'complete') setTimeout(schedulePrefetch, PREFETCH_DELAY);
    else window.addEventListener('load', function () { setTimeout(schedulePrefetch, PREFETCH_DELAY); });
})();
