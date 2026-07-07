/*
 * Shared Telegram Mini App viewport setup.
 *
 * Compact header:
 *  - Bot API 8.0+  → requestFullscreen(): Telegram's bar disappears, leaving only
 *    the floating Close/More buttons (the "compact header" competitors show).
 *  - Every version → blend the native header / background / bottom bar into our
 *    black (#000000) theme with setHeaderColor/setBackgroundColor/setBottomBarColor,
 *    so even on clients below 8.0 the native bar merges with the app and reads as a
 *    minimal, seamless header instead of a chunky separate bar.
 *
 * Scroll-to-close:
 *  - Bot API 7.7+  → disableVerticalSwipes(): the drag-down-to-close gesture is off.
 *  - Older clients → overscroll-behavior:none CSS fallback (in each page).
 *
 * Safe areas: Telegram exposes --tg-safe-area-inset-top / --tg-content-safe-area-inset-top
 * as CSS vars on supported clients, so header padding is handled in CSS
 * (--app-safe-top). On desktop / older clients those vars are absent → fall back to 0.
 *
 * Safe to include on any page — it no-ops when not running inside Telegram.
 */
(function () {
    var tg = window.Telegram && window.Telegram.WebApp;
    if (!tg) return;

    var BG = '#000000'; // matches the black/gold design system

    function atLeast(v) {
        try {
            return typeof tg.isVersionAtLeast === 'function' && tg.isVersionAtLeast(v);
        } catch (e) { return false; }
    }
    function call(name) {
        var args = Array.prototype.slice.call(arguments, 1);
        try { if (typeof tg[name] === 'function') tg[name].apply(tg, args); } catch (e) {}
    }

    try { tg.ready(); } catch (e) {}

    // ── Blend the native chrome into our theme (works on all versions) ──
    if (atLeast('6.9')) call('setHeaderColor', BG);       // hex needs 6.9+
    else call('setHeaderColor', 'secondary_bg_color');    // best effort below 6.9
    if (atLeast('6.1')) call('setBackgroundColor', BG);
    if (atLeast('7.10')) call('setBottomBarColor', BG);

    // ── Compact / fullscreen header ──
    try { tg.expand(); } catch (e) {}
    if (atLeast('8.0') && typeof tg.requestFullscreen === 'function') {
        try { tg.requestFullscreen(); } catch (e) {}
        // If the client refuses fullscreen, we're still expanded — nothing else to do.
        try { tg.onEvent('fullscreenFailed', function () { try { tg.expand(); } catch (err) {} }); } catch (e) {}
    }

    // ── Stop scroll-to-close (drag-down dismiss) ──
    if (atLeast('7.7') && typeof tg.disableVerticalSwipes === 'function') {
        call('disableVerticalSwipes');
    }

    // NOTE: We deliberately do NOT use Telegram's native BackButton (tg.BackButton).
    // On several clients it renders a "Back" text label that clashes with the app's
    // own in-page back arrows. Navigation uses the pages' own back buttons; closing
    // the app is handled by Telegram's built-in Close control (always present).
    // Make sure the native back arrow is hidden if a previous build left it on.
    try { if (tg.BackButton) tg.BackButton.hide(); } catch (e) {}

    // Keep the app expanded if Telegram collapses the viewport again.
    try {
        tg.onEvent('viewportChanged', function (e) {
            if (e && e.isStateStable && !tg.isExpanded) {
                try { tg.expand(); } catch (err) {}
            }
        });
    } catch (e) {}
})();
