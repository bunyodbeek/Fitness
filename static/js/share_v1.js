/* share_v1.js — Program share-link modal logic */
(function () {
    "use strict";

    /* T is populated by the inline <script> block in the template */
    var T = window.SHARE_TRANSLATIONS || {};

    function showShareModal() {
        var modal = document.getElementById("share-modal");
        if (modal) modal.style.display = "flex";
    }

    function hideShareModal() {
        var modal = document.getElementById("share-modal");
        if (modal) modal.style.display = "none";
    }

    function copyToClipboard(text, feedbackEl) {
        var done = function () {
            if (!feedbackEl) return;
            var orig = feedbackEl.textContent;
            feedbackEl.textContent = T.copied || "Copied!";
            setTimeout(function () { feedbackEl.textContent = orig; }, 2000);
        };

        /* Modern clipboard API */
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(done).catch(function () {
                fallbackCopy(text, feedbackEl, done);
            });
        } else {
            fallbackCopy(text, feedbackEl, done);
        }
    }

    /* execCommand fallback for Telegram WebView */
    function fallbackCopy(text, feedbackEl, done) {
        var ta = document.createElement("textarea");
        ta.value = text;
        ta.style.cssText = "position:fixed;top:-9999px;left:-9999px;opacity:0;";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        try {
            document.execCommand("copy");
            done();
        } catch (e) {
            if (feedbackEl) feedbackEl.textContent = T.copy_failed || "Copy failed";
        }
        document.body.removeChild(ta);
    }

    function generateShareLink(generateUrl, tokenEl, linkEl) {
        var btn = document.getElementById("share-generate-btn");
        if (btn) btn.disabled = true;

        fetch(generateUrl, {
            method: "POST",
            headers: { "X-CSRFToken": getCsrf() },
        })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                if (data.token) {
                    if (tokenEl) tokenEl.textContent = data.token;
                    if (linkEl) linkEl.value = data.url;
                    showShareModal();
                } else {
                    alert(T.error || "Error generating link");
                }
            })
            .catch(function () {
                alert(T.error || "Error generating link");
            })
            .finally(function () {
                if (btn) btn.disabled = false;
            });
    }

    function getCsrf() {
        var el = document.querySelector("[name=csrfmiddlewaretoken]");
        if (el) return el.value;
        var match = document.cookie.match(/csrftoken=([^;]+)/);
        return match ? match[1] : "";
    }

    /* Expose to global scope so inline onclick handlers can call them */
    window.shareModal = {
        show: showShareModal,
        hide: hideShareModal,
        copy: copyToClipboard,
        generate: generateShareLink,
    };

    /* Close modal when clicking the backdrop */
    document.addEventListener("DOMContentLoaded", function () {
        var backdrop = document.getElementById("share-modal-backdrop");
        if (backdrop) {
            backdrop.addEventListener("click", hideShareModal);
        }
    });
})();