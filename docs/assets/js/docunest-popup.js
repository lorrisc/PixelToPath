(function () {
    var DELAY_MS = 10000;
    var RELOADS_BEFORE_RESHOW = 5;
    var AUTOPLAY_MS = 6500;
    var LS_VISITS = "ptp_dn_visits";
    var LS_LAST = "ptp_dn_last_shown";

    var root = document.getElementById("dn-popup");
    if (!root) return;

    var dialog = root.querySelector(".dn-popup__dialog");
    var carousel = root.querySelector("[data-dn-carousel]");
    var track = root.querySelector(".dn-carousel__track");
    var slides = root.querySelectorAll(".dn-slide");
    var dots = root.querySelectorAll("[data-dn-dots] button");
    var total = slides.length;
    var index = 0;
    var autoplayTimer = null;
    var openTimer = null;
    var lastFocus = null;
    var reducedMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function storageGet(key) {
        try { return parseInt(localStorage.getItem(key) || "0", 10) || 0; } catch (_) { return 0; }
    }
    function storageSet(key, value) {
        try { localStorage.setItem(key, String(value)); } catch (_) {}
    }

    var visits = storageGet(LS_VISITS) + 1;
    storageSet(LS_VISITS, visits);
    var lastShown = storageGet(LS_LAST);
    var shouldShow = lastShown === 0 || (visits - lastShown >= RELOADS_BEFORE_RESHOW);
    if (!shouldShow) return;

    function go(next) {
        index = (next + total) % total;
        track.style.transform = "translateX(-" + (index * 100) + "%)";
        for (var i = 0; i < dots.length; i++) {
            dots[i].classList.toggle("is-active", i === index);
        }
        resetAutoplay();
    }

    function resetAutoplay() {
        clearInterval(autoplayTimer);
        if (reducedMotion || !root.classList.contains("is-open")) return;
        autoplayTimer = setInterval(function () { go(index + 1); }, AUTOPLAY_MS);
    }

    function onKeydown(e) {
        if (e.key === "Escape") {
            e.preventDefault();
            close();
            return;
        }
        if (e.key === "ArrowRight") {
            e.preventDefault();
            go(index + 1);
        }
        if (e.key === "ArrowLeft") {
            e.preventDefault();
            go(index - 1);
        }
        if (e.key === "Tab") trapFocus(e);
    }

    function focusables() {
        return dialog.querySelectorAll("a[href], button:not([disabled])");
    }

    function trapFocus(e) {
        var nodes = focusables();
        if (!nodes.length) return;
        var first = nodes[0];
        var last = nodes[nodes.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }

    function open() {
        storageSet(LS_LAST, visits);
        lastFocus = document.activeElement;
        root.hidden = false;
        document.body.classList.add("dn-popup-open");
        requestAnimationFrame(function () {
            root.classList.add("is-open");
        });
        document.addEventListener("keydown", onKeydown);
        var closeBtn = root.querySelector("[data-dn-close]");
        if (closeBtn) closeBtn.focus();
        resetAutoplay();
    }

    function close() {
        clearInterval(autoplayTimer);
        root.classList.remove("is-open");
        document.body.classList.remove("dn-popup-open");
        document.removeEventListener("keydown", onKeydown);
        setTimeout(function () {
            root.hidden = true;
            if (lastFocus && lastFocus.focus) lastFocus.focus();
        }, 220);
    }

    root.addEventListener("click", function (e) {
        if (e.target === root) close();
    });
    root.querySelectorAll("[data-dn-close]").forEach(function (btn) {
        btn.addEventListener("click", close);
    });
    root.querySelector("[data-dn-prev]").addEventListener("click", function () { go(index - 1); });
    root.querySelector("[data-dn-next]").addEventListener("click", function () { go(index + 1); });
    dots.forEach(function (dot, i) {
        dot.addEventListener("click", function () { go(i); });
    });

    carousel.addEventListener("mouseenter", function () { clearInterval(autoplayTimer); });
    carousel.addEventListener("mouseleave", resetAutoplay);

    var touchStartX = 0;
    track.addEventListener("touchstart", function (e) {
        touchStartX = e.changedTouches[0].clientX;
    }, { passive: true });
    track.addEventListener("touchend", function (e) {
        var dx = e.changedTouches[0].clientX - touchStartX;
        if (dx > 40) go(index - 1);
        if (dx < -40) go(index + 1);
    }, { passive: true });

    openTimer = setTimeout(open, DELAY_MS);
    document.addEventListener("visibilitychange", function () {
        if (document.hidden) {
            clearInterval(autoplayTimer);
        } else if (root.classList.contains("is-open")) {
            resetAutoplay();
        }
    });
})();
