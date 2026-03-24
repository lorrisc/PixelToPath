(function() {
    const LOG_URL = "https://api.pixel-to-path.com/log";
    
    // 1. Gestion de la visite unique (valide pour tout l'onglet)
    let visitId = sessionStorage.getItem('ptp_visit_id');
    let isNewVisit = false;
    
    if (!visitId) {
        // Génère un ID unique de visite
        visitId = crypto.randomUUID ? crypto.randomUUID() : 'v-' + Math.random().toString(36).substring(2) + Date.now().toString(36);
        sessionStorage.setItem('ptp_visit_id', visitId);
        isNewVisit = true;
    }

    let eventsQueue = [];
    let pageLoadMs = null;

    // 2. Mesure du temps de chargement de la page
    window.addEventListener('load', () => {
        setTimeout(() => {
            const navEntry = performance.getEntriesByType('navigation')[0];
            if (navEntry) {
                pageLoadMs = Math.round(navEntry.loadEventEnd - navEntry.startTime);
            } else {
                pageLoadMs = Date.now() - performance.timing.navigationStart;
            }
            
            // Si c'est sa première page, on envoie le log initial tout de suite
            if (isNewVisit) sendLogs();
        }, 0);
    });

    // 3. Écoute des clics globaux (Heatmap)
    document.addEventListener('click', (e) => {
        // Ignorer les faux clics générés par le code
        if (e.clientX === 0 && e.clientY === 0) return;
        
        // Trouver un identifiant pertinent pour l'élément cliqué pour aider l'analyse
        let target = e.target;
        let targetIdentifier = target.id ? `#${target.id}` : 
                               (target.className && typeof target.className === 'string' ? `.${target.className.split(' ')[0]}` : target.tagName.toLowerCase());

        eventsQueue.push({
            type: 'click',
            timestamp: new Date().toISOString(),
            data: {
                x: Math.round(e.pageX),
                y: Math.round(e.pageY),
                target: targetIdentifier,
                url: window.location.pathname // C'est ici qu'on gère tes 20 URLs dynamiquement !
            }
        });
    }, { passive: true });

    // 4. Fonction exposée pour que online.js puisse envoyer des événements spécifiques
    window.trackEvent = function(type, data = {}) {
        data.url = window.location.pathname;
        eventsQueue.push({
            type: type,
            timestamp: new Date().toISOString(),
            data: data
        });
        
        // On force l'envoi immédiat pour les événements critiques (upload, erreur)
        if (['upload_start', 'conversion_success', 'error'].includes(type)) {
            sendLogs();
        }
    };

    // 5. Logique d'envoi furtif
    function sendLogs() {
        if (!isNewVisit && eventsQueue.length === 0) return; // Rien à envoyer

        const payload = {
            visit_id: visitId,
            is_new_visit: isNewVisit,
            language: navigator.language,
            resolution: `${window.screen.width}x${window.screen.height}`,
            page_load_ms: pageLoadMs,
            events: [...eventsQueue] // On copie le tableau
        };

        // On vide la file d'attente
        eventsQueue = [];
        isNewVisit = false;

        // Envoi via sendBeacon (garantit l'envoi même si l'utilisateur ferme l'onglet)
        try {
            const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' });
            navigator.sendBeacon(LOG_URL, blob);
        } catch (e) {
            // Fallback classique
            fetch(LOG_URL, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
                keepalive: true
            }).catch(() => {});
        }
    }

    // Envoi automatique en arrière-plan toutes les 10 secondes
    setInterval(sendLogs, 10000);

    // Envoi de sécurité si l'utilisateur change d'onglet ou quitte la page
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'hidden') sendLogs();
    });
})();