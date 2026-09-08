/* AdSense différé (lazy-fill) : adsbygoogle.js (206 Ko compressé / 653 Ko
   décodé) n'est téléchargé et exécuté qu'au moment où un premier emplacement
   approche du viewport — plus aucune requête publicitaire au chargement de la
   page si le lecteur ne scrolle pas.
   - Unités visibles ou quasi visibles au chargement : remplissage immédiat
     (visibilité et revenus préservés sur la première page d'écran).
   - Unités sous la ligne de flottaison : IntersectionObserver avec une marge
     de pré-remplissage de 400px, pour que l'annonce soit servie avant l'entrée
     à l'écran (pas de slot vide, pas de perte de visibilité).
   Les pushes inline ont été retirés de partials/ads.ejs : sans ce fichier,
   aucune demande d'annonce n'est émise. Le script AdSense reste injecté en
   async (jamais bloquant). */
(function () {
    'use strict';

    var CLIENT = 'ca-pub-1281752767600519';
    // Marge de pré-remplissage : identique au rootMargin de l'observer et au
    // seuil de détection initiale, pour éviter un flash de slot vide juste
    // sous la ligne de flottaison.
    var MARGIN = 400;

    var slots = Array.prototype.slice.call(document.querySelectorAll('ins.adsbygoogle'));
    if (!slots.length) return;

    var libRequested = false;

    function loadLibrary() {
        if (libRequested) return;
        libRequested = true;
        var s = document.createElement('script');
        s.async = true;
        s.crossOrigin = 'anonymous';
        s.src = 'https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=' + CLIENT;
        document.head.appendChild(s);
    }

    function fill(ins) {
        if (ins.getAttribute('data-ad-lazy')) return; // déjà poussé
        ins.setAttribute('data-ad-lazy', '1');
        loadLibrary();
        // La file adsbygoogle fonctionne avant ET après le chargement de la
        // librairie (c'était le mécanisme des pushes inline de ads.ejs).
        (window.adsbygoogle = window.adsbygoogle || []).push({});
    }

    function fillAll(list) {
        list.forEach(fill);
        if (list.length) loadLibrary();
    }

    // 1. Unités déjà visibles (ou dans la marge) au chargement : remplissage
    //    immédiat, sans attendre l'observer.
    var pending = [];
    var vh = window.innerHeight || document.documentElement.clientHeight;
    slots.forEach(function (ins) {
        var rect = ins.getBoundingClientRect();
        if (rect.top < vh + MARGIN && rect.bottom > -MARGIN) fill(ins);
        else pending.push(ins);
    });

    if (!pending.length) return;

    // 2. Très vieux navigateurs sans IntersectionObserver : comportement
    //    historique (tout remplir) plutôt que perdre l'inventaire.
    if (!('IntersectionObserver' in window)) {
        fillAll(pending);
        return;
    }

    // 3. Le reste : remplissage à l'approche du viewport.
    var io = new IntersectionObserver(function (entries) {
        var hit = [];
        entries.forEach(function (entry) {
            if (entry.isIntersecting) {
                io.unobserve(entry.target);
                hit.push(entry.target);
            }
        });
        fillAll(hit);
    }, { rootMargin: MARGIN + 'px 0px' });

    pending.forEach(function (ins) { io.observe(ins); });
})();
