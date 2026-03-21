// Highlight active TOC link on scroll
(function () {
    const toc     = document.getElementById('legalToc');
    if (!toc) return;
    const links   = Array.from(toc.querySelectorAll('a'));
    const targets = links.map(a => document.querySelector(a.getAttribute('href')));

    function update() {
        let current = targets[0];
        targets.forEach(el => {
            if (el && el.getBoundingClientRect().top < 160) current = el;
        });
        links.forEach(a => {
            a.classList.toggle('active', a.getAttribute('href') === '#' + current?.id);
        });
    }

    window.addEventListener('scroll', update, { passive: true });
    update();
})();