/* DocuNest promo : bannière footer + popup carrousel.
 * Markup injecté en JS après le chargement complet de la page — aucune trace
 * DocuNest dans le HTML statique (SEO : pages ciblant des requêtes SVG, cf.
 * audit). Les textes localisés vivent dans js/docunest-strings.js, généré par
 * build.js depuis locales/ (un seul fichier partagé, pas de requête par page).
 */
(function () {
    "use strict";

    var DELAY_MS = 10000;
    var RELOADS_BEFORE_RESHOW = 5;
    var AUTOPLAY_MS = 6500;
    var CONVERSION_POLL_MS = 2000;
    var LS_VISITS = "ptp_dn_visits";
    var LS_LAST = "ptp_dn_last_shown";
    // Langues ayant une version localisée de docunest.app, les autres → EN
    var DN_LOCALIZED = { fr: 1, de: 1, es: 1, pt: 1 };

    var script = document.currentScript;
    var assetBase = (script && script.dataset.asset) || "";
    var lang = (document.documentElement.lang || "en").split("-")[0].toLowerCase();
    var allStrings = window.DN_STRINGS || {};
    var t = allStrings[lang] || allStrings.en;

    var dnBase = "https://docunest.app/" + (DN_LOCALIZED[lang] ? lang + "/" : "");
    var POPUP_URL = dnBase + "?utm_source=pixeltopath&utm_medium=popup&utm_campaign=site_popup";
    var BAR_URL = dnBase + "?utm_source=pixeltopath&utm_medium=popup&utm_campaign=site_popup&utm_content=tools";
    var SPONSOR_URL = dnBase + "?utm_source=pixeltopath&utm_medium=banner&utm_campaign=site_footer";

    function el(html) {
        var host = document.createElement("div");
        host.innerHTML = html.trim();
        return host.firstElementChild;
    }

    // ── Bannière footer ──────────────────────────────────────────────────────────
    function buildSponsor() {
        var footer = document.querySelector("footer");
        if (!footer || !t || !t.sponsor_title) return;
        var banner = el(`
        <a class="sponsor" href="${SPONSOR_URL}" target="_blank" rel="sponsored noopener noreferrer">
            <div class="container sponsor__inner">
                <div class="sponsor__mark" aria-hidden="true">
                    <svg viewBox="0 0 32 32" width="26" height="26" fill="none">
                        <path d="M8 4.5h11.2L24 9.3V26a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 8 26V4.5z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
                        <path d="M19 4.5V9h4.8" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
                        <path d="M12 14.5h8M12 18.5h8M12 22.5h5.5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>
                    </svg>
                </div>
                <div class="sponsor__copy">
                    <strong class="sponsor__title">${t.sponsor_title}</strong>
                    <span class="sponsor__text">${t.sponsor_text}</span>
                </div>
                <span class="sponsor__cta">${t.sponsor_cta}</span>
            </div>
        </a>`);
        footer.insertAdjacentElement("beforebegin", banner);
    }

    // ── Popup carrousel ──────────────────────────────────────────────────────────
    // Titres en <p> (classe .dn-slide__title) : aucun poids de heading, même rendu.
    function slide(title, text, alt, img) {
        return `
            <article class="dn-slide">
                <p class="dn-slide__title">${title}</p>
                <p class="dn-slide__text">${text}</p>
                <div class="dn-slide__frame">
                    <img src="${assetBase}images/docunest/${img}" alt="${alt}" width="1280" height="720" loading="lazy" decoding="async">
                </div>
            </article>`;
    }

    function buildPopup() {
        return el(`
        <div id="dn-popup" class="dn-popup" hidden>
            <div class="dn-popup__dialog" role="dialog" aria-modal="true" aria-labelledby="dn-popup-title">
                <div class="dn-popup__top">
                    <p class="dn-popup__brand" id="dn-popup-title">DocuNest</p>
                    <button type="button" class="dn-popup__close" data-dn-close aria-label="${t.dn_close}">&times;</button>
                </div>

                <div class="dn-carousel" data-dn-carousel>
                    <div class="dn-carousel__viewport">
                        <div class="dn-carousel__track">
                            ${slide(t.dn_s1_title, t.dn_s1_text, t.dn_s1_alt, "redact.webp")}
                            ${slide(t.dn_s2_title, t.dn_s2_text, t.dn_s2_alt, "sign.webp")}
                            ${slide(t.dn_s3_title, t.dn_s3_text, t.dn_s3_alt, "watermark.webp")}
                            <article class="dn-slide dn-slide--offer">
                                <p class="dn-slide__title dn-slide__title--xl">${t.dn_s4_title}</p>
                                <p class="dn-slide__text">${t.dn_s4_text}</p>
                                <ul class="dn-offer">
                                    <li class="dn-offer__item">
                                        <strong>${t.dn_s4_p1_title}</strong>
                                        <span>${t.dn_s4_p1_text}</span>
                                    </li>
                                    <li class="dn-offer__item">
                                        <strong>${t.dn_s4_p2_title}</strong>
                                        <span>${t.dn_s4_p2_text}</span>
                                    </li>
                                    <li class="dn-offer__item">
                                        <strong>${t.dn_s4_p3_title}</strong>
                                        <span>${t.dn_s4_p3_text}</span>
                                    </li>
                                    <li class="dn-offer__item">
                                        <strong>${t.dn_s4_p4_title}</strong>
                                        <span>${t.dn_s4_p4_text}</span>
                                    </li>
                                </ul>
                                <a class="dn-offer__cta" href="${POPUP_URL}" target="_blank" rel="noopener noreferrer">${t.dn_s4_cta}</a>
                            </article>
                        </div>
                    </div>
                    <button type="button" class="dn-carousel__nav dn-carousel__nav--prev" data-dn-prev aria-label="${t.dn_prev}">
                        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M15.5 4.5 8 12l7.5 7.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    </button>
                    <button type="button" class="dn-carousel__nav dn-carousel__nav--next" data-dn-next aria-label="${t.dn_next}">
                        <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true"><path d="M8.5 4.5 16 12l-7.5 7.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    </button>
                    <div class="dn-carousel__dots" data-dn-dots>
                        <button type="button" class="is-active" aria-label="1"></button>
                        <button type="button" aria-label="2"></button>
                        <button type="button" aria-label="3"></button>
                        <button type="button" aria-label="4"></button>
                    </div>
                </div>

                <div class="dn-bar">
                    <nav class="dn-bar__tools" aria-label="DocuNest">
                        <a href="${BAR_URL}" target="_blank" rel="noopener noreferrer">${t.dn_bar_redact}</a>
                        <a href="${BAR_URL}" target="_blank" rel="noopener noreferrer">${t.dn_bar_sign}</a>
                        <a href="${BAR_URL}" target="_blank" rel="noopener noreferrer">${t.dn_bar_watermark}</a>
                        <a href="${BAR_URL}" target="_blank" rel="noopener noreferrer">${t.dn_bar_merge}</a>
                        <a href="${BAR_URL}" target="_blank" rel="noopener noreferrer">${t.dn_bar_edit}</a>
                    </nav>
                    <div class="dn-bar__cta-wrap">
                        <span class="dn-bar__note">${t.dn_bar_note}</span>
                        <a class="dn-bar__cta" href="${POPUP_URL}" target="_blank" rel="noopener noreferrer">${t.dn_bar_cta}</a>
                    </div>
                </div>
            </div>
        </div>`);
    }

    function initPopup() {
        if (!t || !t.dn_s1_title) return;
        // Pages de conversion : la modale est désactivée (le bandeau footer reste actif)
        if (document.body.getAttribute("data-dn-popup") === "off") return;
        var root = buildPopup();
        document.body.appendChild(root);
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
            clearTimeout(openTimer);
            root.classList.remove("is-open");
            document.body.classList.remove("dn-popup-open");
            document.removeEventListener("keydown", onKeydown);
            setTimeout(function () {
                root.hidden = true;
                if (lastFocus && lastFocus.focus) lastFocus.focus();
            }, 220);
        }

        // /online/ uniquement : ne pas ouvrir pendant une conversion en cours
        // (#overlay.porte par online.ejs, absent des autres pages) — on attend la fin.
        function conversionActive() {
            var overlay = document.getElementById("overlay");
            return !!(overlay && overlay.classList.contains("active"));
        }

        function armOpen(delay) {
            openTimer = setTimeout(function () {
                if (conversionActive()) {
                    armOpen(CONVERSION_POLL_MS);
                    return;
                }
                open();
            }, delay);
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

        // Une conversion lancée popup ouverte (cf. setOverlay dans online.js) la referme.
        window.closeDocuNestPopup = close;

        if (shouldShow) armOpen(DELAY_MS);
    }

    // Montage après le chargement complet : les scripts promo ne retardent rien
    // et le HTML servit au crawler reste vierge de contenu DocuNest.
    function mount() {
        buildSponsor();
        initPopup();
    }

    if (document.readyState === "complete") mount();
    else window.addEventListener("load", mount);
})();
