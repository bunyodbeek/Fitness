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
 *
 * `data-swap` links opt any OTHER in-app link into the same pipeline — used by the
 * Gym/Home mode pills, which used to do a full page navigation (session write →
 * re-download the whole shell) and felt like a freeze on every toggle. Three things
 * make them instant:
 *
 *  - cacheSearch: their URLs differ only by ?type=gym|home, so the cache is keyed on
 *    pathname+search — otherwise every query-string URL would bypass the cache.
 *  - soft: on a cold cache the current page stays on screen dimmed
 *    (#content.tab-swapping) rather than being replaced by a skeleton — both modes
 *    render the same layout, so a skeleton would only add a flash.
 *  - prefetchSwaps(): runs on idle after load AND after every inject(), so entering
 *    the programs tab immediately warms the opposite mode. By the time the pill is
 *    tapped the fragment is normally already cached and paints on the same frame,
 *    leaving only a background revalidation request.
 */
(function () {
    'use strict';

    var CONTENT_ID = 'content';
    var CACHE_PREFIX = 'tabfrag:';
    var TTL = 5 * 60 * 1000;           // 5 min → stale
    var PREFETCH_DELAY = 2000;

    var contentEl = function () { return document.getElementById(CONTENT_ID); };
    var origin = location.origin;
    var currentUrl = location.pathname + location.search;  // guards out-of-order fetches

    // Paths reached through a `data-swap` link. They are not tabs, so popstate has
    // to be told they can be re-rendered in place instead of hard-reloading.
    var swapPaths = Object.create(null);

    // ---- tab set (derived from the bottom nav, so it stays in sync) ----
    function tabPaths() {
        var out = {};
        document.querySelectorAll('.bottom-nav a[href]').forEach(function (a) {
            try { out[new URL(a.href, origin).pathname] = a.href; } catch (e) {}
        });
        return out;
    }
    function isTabPath(p) { return Object.prototype.hasOwnProperty.call(tabPaths(), p); }
    // `full` is pathname+search — swap URLs are only distinguishable by their query.
    function isSwapUrl(full) { return !!swapPaths[full]; }
    function isRoutable(path, full) { return isTabPath(path) || isSwapUrl(full); }

    // `data-swap` targets on the page right now (e.g. the Gym/Home mode pills).
    function swapUrls() {
        var out = [];
        document.querySelectorAll('a[data-swap][href]').forEach(function (a) {
            try {
                var u = new URL(a.href, origin);
                if (u.origin === origin) out.push(u.pathname + u.search);
            } catch (e) {}
        });
        return out;
    }

    // Remember every swap destination we have seen, keyed by pathname+search.
    // Re-run after each inject(): a fragment swap replaces the pills, and popstate
    // needs to recognise these URLs long after that DOM is gone.
    function registerSwapPaths() {
        swapUrls().forEach(function (u) { swapPaths[u] = true; });
    }

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
        // A `data-swap` destination (e.g. /home/programs/) is not itself a nav href.
        // Leave the highlight where it is rather than un-highlighting every tab.
        if (!isTabPath(path)) return;
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
        el.classList.remove('tab-swapping');
        runScripts(el);
        setActiveTab(path);
        window.scrollTo(0, 0);
        // The fragment carries its own mode pills — re-index them and start warming
        // the opposite mode straight away, so the first toggle is already a cache hit.
        registerSwapPaths();
        scheduleSwapPrefetch();
        try { window.dispatchEvent(new CustomEvent('tab:loaded', { detail: { path: path } })); } catch (e) {}
    }

    // Soft loading state: keep the current DOM, just mark it busy. Used for
    // `data-swap` navigations so a cold cache dims the page instead of blanking it.
    function setBusy(on) {
        var el = contentEl();
        if (el) el.classList.toggle('tab-swapping', !!on);
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

    // ---- navigate to a routable path (already pushed to history by caller) ----
    // opts.soft   — cold cache keeps the current DOM (dimmed) instead of a skeleton.
    // opts.cacheSearch — cache this URL even though it carries a query string.
    function render(path, search, opts) {
        opts = opts || {};
        var full = path + (search || '');
        // Cache key is the FULL url, so ?type=… style variants never collide.
        var cacheable = !search || !!opts.cacheSearch;
        var cached = cacheable ? readCache(full) : null;
        var painted = false;

        if (isFresh(cached)) {
            inject(cached.html, path);
            painted = true;
        } else if (opts.soft) {
            setBusy(true);
        } else {
            inject(skeleton(), path);
        }

        fetchPartial(full).then(function (html) {
            if (currentUrl !== full) return;     // user moved on — drop this result
            if (!cached || cached.html !== html) inject(html, path);
            else setBusy(false);
            if (cacheable) writeCache(full, html);
        }).catch(function () {
            setBusy(false);
            if (!painted) window.location.assign(full);   // hard fallback
        });
    }

    function go(path, search, opts) {
        var full = path + (search || '');
        var isSwap = !!(opts && opts.soft);
        // Remember the destination before the pills are swapped out of the DOM, and
        // stamp the history entry so popstate can tell a swap from a plain tab.
        if (isSwap) swapPaths[full] = true;
        if (full !== location.pathname + location.search) {
            history.pushState({ tabRouter: true, swap: isSwap }, '', full);
        }
        currentUrl = full;
        render(path, search, opts);
    }

    // ---- click interception ----
    document.addEventListener('click', function (e) {
        if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var a = e.target.closest ? e.target.closest('a[href]') : null;
        if (!a || a.target === '_blank' || a.hasAttribute('download') || a.getAttribute('href').charAt(0) === '#') return;
        var url;
        try { url = new URL(a.href, origin); } catch (e2) { return; }
        var isSwap = a.hasAttribute('data-swap');
        if (url.origin !== origin || !(isTabPath(url.pathname) || isSwap)) return;
        e.preventDefault();
        if (url.pathname === location.pathname && url.search === location.search) {
            window.scrollTo(0, 0);
            return;
        }
        // Swap links (mode pills) carry a query string — without cacheSearch their
        // fragments would never be cached, and without soft they'd flash a skeleton.
        go(url.pathname, url.search, isSwap ? { soft: true, cacheSearch: true } : undefined);
    }, false);

    // ---- back / forward ----
    window.addEventListener('popstate', function (event) {
        var path = location.pathname;
        var full = path + location.search;
        currentUrl = full;
        var backToSwap = !!(event && event.state && event.state.swap) || isSwapUrl(full);
        if (backToSwap) {
            render(path, location.search, { soft: true, cacheSearch: true });
        } else if (isRoutable(path, full)) {
            render(path, location.search);
        } else {
            window.location.reload();            // left the tab world → full page
        }
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
    // ---- prefetch the counterpart swap URLs (Gym <-> Home) ----
    // Same walk as prefetchOthers, but keyed on pathname+search so ?type=gym and
    // ?type=home get their own cache entries.
    function prefetchSwaps() {
        try { if (navigator.connection && navigator.connection.saveData) return; } catch (e) {}
        var urls = swapUrls().filter(function (u) {
            return u !== location.pathname + location.search && !isFresh(readCache(u));
        });
        (function next(i) {
            if (i >= urls.length) return;
            var u = urls[i];
            fetchPartial(u).then(function (html) { writeCache(u, html); }).catch(function () {})
                .then(function () { next(i + 1); });
        })(0);
    }

    // Debounced: inject() fires this on every fragment swap, and the pills are
    // re-scanned each time — no need to run the walk more than once per burst.
    var swapPrefetchTimer = null;
    function scheduleSwapPrefetch() {
        if (swapPrefetchTimer) clearTimeout(swapPrefetchTimer);
        swapPrefetchTimer = setTimeout(function () {
            swapPrefetchTimer = null;
            if (window.requestIdleCallback) requestIdleCallback(prefetchSwaps, { timeout: 3000 });
            else prefetchSwaps();
        }, 500);
    }

    function schedulePrefetch() {
        if (window.requestIdleCallback) requestIdleCallback(prefetchOthers, { timeout: 4000 });
        else setTimeout(prefetchOthers, PREFETCH_DELAY);
        scheduleSwapPrefetch();
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

    // Index the mode pills present in the server-rendered page. The script tag sits
    // after #content so they are already parsed; DOMContentLoaded is a safety net for
    // any page that loads the router earlier.
    registerSwapPaths();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', registerSwapPaths);
    }

    // Tag the initial entry so the first Back behaves predictably, then warm the cache.
    try {
        history.replaceState(
            { tabRouter: true, swap: isSwapUrl(location.pathname + location.search) },
            '', location.href
        );
    } catch (e) {}
    if (document.readyState === 'complete') setTimeout(schedulePrefetch, PREFETCH_DELAY);
    else window.addEventListener('load', function () { setTimeout(schedulePrefetch, PREFETCH_DELAY); });
})();
