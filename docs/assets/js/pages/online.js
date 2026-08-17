const UPLOAD_URL = "https://api.pixel-to-path.com/upload";
const CONVERT_URL = "https://api.pixel-to-path.com/convert";

let currentFile = null;
let currentSvg = null;
let currentSession = null;
let abortCtrl = null;

// ── Language detection ────────────────────────────────────────────────────────
function detectLang() {
    const m = window.location.pathname.match(/^\/([a-z]{2})\//);
    if (!m) return "en";
    return m[1] === "pt" ? "pt-BR" : m[1];
}
// const T = (window.PTP_I18N || {})[ detectLang() ] || window.PTP_I18N["en"];
const T =  window.PTP_I18N["fr"];

// ── Presets ───────────────────────────────────────────────────────────────────
const PRESETS = {
    bw: {
        colormode: "binary", mode: "spline",
        filter_speckle: 4, corner_threshold: 60,
        length_threshold: 4.0, splice_threshold: 45, path_precision: 3,
    },
    poster: {
        colormode: "color", hierarchical: "stacked", mode: "spline",
        filter_speckle: 4, color_precision: 8, layer_difference: 16,
        corner_threshold: 60, length_threshold: 4.0, splice_threshold: 45, path_precision: 3,
    },
    photo: {
        colormode: "color", hierarchical: "stacked", mode: "spline",
        filter_speckle: 10, color_precision: 8, layer_difference: 48,
        corner_threshold: 180, length_threshold: 4.0, splice_threshold: 45, path_precision: 2,
    },
};

// ── Tooltip ───────────────────────────────────────────────────────────────────
let tooltipTarget  = null;
let tooltipTimeout = null;
let showTimeout    = null;

function initTooltip() {
    const tip = document.getElementById("param-tooltip");
    if (!tip) return;
    document.querySelectorAll(".param-help").forEach(btn => {
        btn.addEventListener("mouseenter", () => scheduleShowTooltip(btn));
        btn.addEventListener("mouseleave", () => { clearTimeout(showTimeout); scheduleHideTooltip(); });
        btn.addEventListener("focus",      () => scheduleShowTooltip(btn));
        btn.addEventListener("blur",       () => { clearTimeout(showTimeout); scheduleHideTooltip(); });
        btn.addEventListener("click", e => {
            e.stopPropagation();
            clearTimeout(showTimeout);
            if (tooltipTarget === btn && tip.classList.contains("tt-visible")) hideTooltip();
            else showTooltip(btn);
        });
    });
    tip.addEventListener("mouseenter", () => clearTimeout(tooltipTimeout));
    tip.addEventListener("mouseleave", () => scheduleHideTooltip());
    document.addEventListener("click", e => {
        if (!e.target.closest(".param-help") && !e.target.closest("#param-tooltip")) hideTooltip();
    });
}

function scheduleShowTooltip(btn) {
    clearTimeout(showTimeout);
    showTimeout = setTimeout(() => showTooltip(btn), 400);
}

function showTooltip(btn) {
    const tip   = document.getElementById("param-tooltip");
    const param = btn.dataset.param;
    const info  = T.params?.[param];
    if (!tip || !info) return;
    clearTimeout(tooltipTimeout);
    tooltipTarget = btn;
    tip.querySelector(".tt-title").textContent = info.title;
    tip.querySelector(".tt-text").textContent  = info.text;
    tip.classList.remove("tt-visible");
    tip.style.cssText = "position:fixed; width:230px; opacity:0; pointer-events:none; transition:none;";
    const tipW = 230, tipH = tip.offsetHeight, margin = 8;
    const btnRect = btn.getBoundingClientRect();
    let left = btnRect.left + btnRect.width / 2 - tipW / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - tipW - 8));
    let top, arrowDir;
    if (btnRect.top > tipH + margin + 10) {
        top = btnRect.top - tipH - margin; arrowDir = "down";
    } else {
        top = btnRect.bottom + margin;     arrowDir = "up";
    }
    const arrowLeft = btnRect.left + btnRect.width / 2 - left;
    tip.style.cssText = `position:fixed; width:${tipW}px; left:${left}px; top:${top}px;`;
    tip.dataset.arrow = arrowDir;
    tip.style.setProperty("--arrow-left", Math.max(12, Math.min(arrowLeft, tipW - 12)) + "px");
    requestAnimationFrame(() => tip.classList.add("tt-visible"));
}

function scheduleHideTooltip() { tooltipTimeout = setTimeout(hideTooltip, 120); }
function hideTooltip() {
    const tip = document.getElementById("param-tooltip");
    if (tip) tip.classList.remove("tt-visible");
    tooltipTarget = null;
}

// ── Helpers UI ────────────────────────────────────────────────────────────────
function getSegVal(id) { return document.querySelector(`#${id} button.active`)?.dataset.val ?? ""; }
function setSegVal(id, val) {
    document.querySelectorAll(`#${id} button`).forEach(b => b.classList.toggle("active", b.dataset.val === val));
}
function setSlider(id, v) {
    const sl = document.getElementById("sl-" + id), vl = document.getElementById("v-" + id);
    if (sl) sl.value = v;
    if (vl) vl.textContent = id === "length_threshold" ? (+v).toFixed(1) : v;
}
function updateColormodeVis() {
    const m = getSegVal("seg-colormode");
    document.getElementById("color-params").style.display  = m === "color"  ? "" : "none";
    document.getElementById("binary-params").style.display = m === "binary" ? "" : "none";
}
function getParams() {
    const colormode = getSegVal("seg-colormode");
    return {
        colormode,
        hierarchical:     getSegVal("seg-hierarchical"),
        mode:             getSegVal("seg-mode"),
        filter_speckle:   +document.getElementById("sl-filter_speckle").value,
        color_precision:  +document.getElementById("sl-color_precision").value,
        layer_difference: +document.getElementById("sl-layer_difference").value,
        corner_threshold: +document.getElementById("sl-corner_threshold").value,
        length_threshold: +document.getElementById("sl-length_threshold").value,
        splice_threshold: +document.getElementById("sl-splice_threshold").value,
        path_precision:   +document.getElementById("sl-path_precision").value,
        invert: colormode === "binary" && document.getElementById("sw-invert").checked,
    };
}
function clearActivePreset() {
    document.querySelectorAll(".presets__btn").forEach(b => b.classList.remove("presets__btn--active"));
}
function setOverlay(show, text) {
    document.getElementById("overlay").classList.toggle("active", show);
    document.getElementById("overlay-text").textContent = text ?? T.converting;
}
function setStatus(msg, type) {
    const el = document.getElementById("status");
    el.textContent = msg; el.className = type || "";
}
function setLive(state) {
    const dot = document.getElementById("live-dot"), text = document.getElementById("live-text");
    const c = { ok: "#4caf7d", converting: "#e09a00", error: "#c62828" };
    dot.style.background = c[state];
    dot.style.animation  = state === "ok" ? "" : "none";
    text.textContent = state === "converting" ? T.live_converting
                     : state === "error"      ? T.live_error
                     :                          T.live_ready;
}
function clearPreview() {
    document.getElementById("preview__body__svg-container").querySelectorAll("svg").forEach(n => n.remove());
    document.getElementById("placeholder").style.display = "";
    document.getElementById("btn-dl").disabled = true;
    currentSvg = null;
}
function renderSvg(svgStr) {
    const container = document.getElementById("preview__body__svg-container");
    document.getElementById("placeholder").style.display = "none";
    container.querySelectorAll("svg").forEach(n => n.remove());
    const doc = new DOMParser().parseFromString(svgStr, "image/svg+xml");
    const svgEl = doc.documentElement;
    const vb = svgEl.getAttribute("viewBox");
    if (!vb) {
        const w = svgEl.getAttribute("width"), h = svgEl.getAttribute("height");
        if (w && h) svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
    }
    svgEl.removeAttribute("width"); svgEl.removeAttribute("height");
    svgEl.style.cssText = "max-width:100%;max-height:100%;width:auto;height:auto;display:block;";
    container.appendChild(svgEl);
}

// ── Preset ────────────────────────────────────────────────────────────────────
function applyPreset(key, triggerConversion = true) {
    const p = PRESETS[key]; if (!p) return;
    document.querySelectorAll(".presets__btn")
            .forEach(b => b.classList.toggle("presets__btn--active", b.dataset.preset === key));
    setSegVal("seg-colormode", p.colormode);
    setSegVal("seg-mode", p.mode);
    if (p.colormode === "color" && p.hierarchical) setSegVal("seg-hierarchical", p.hierarchical);
    updateColormodeVis();
    ["filter_speckle","corner_threshold","length_threshold","splice_threshold","path_precision"]
        .forEach(k => { if (p[k] !== undefined) setSlider(k, p[k]); });
    if (p.colormode === "color")
        ["color_precision","layer_difference"].forEach(k => { if (p[k] !== undefined) setSlider(k, p[k]); });
    if (triggerConversion && currentSession) runConversion();
}

// ── Apply server-recommended params ──────────────────────────────────────────
function applyRecommendedParams(params, detectedType) {
    if (!params) return;
    clearActivePreset();
    setSegVal("seg-colormode", params.colormode);
    setSegVal("seg-mode", params.mode);
    if (params.colormode === "color" && params.hierarchical) setSegVal("seg-hierarchical", params.hierarchical);
    updateColormodeVis();
    ["filter_speckle","corner_threshold","length_threshold","splice_threshold","path_precision"]
        .forEach(k => { if (params[k] !== undefined) setSlider(k, params[k]); });
    if (params.colormode === "color")
        ["color_precision","layer_difference"].forEach(k => { if (params[k] !== undefined) setSlider(k, params[k]); });
    const labels = { photo: T.type_photo, illustration: T.type_illustration, logo: T.type_logo, line_art: T.type_line_art };
    if (detectedType && labels[detectedType]) setStatus(labels[detectedType] + " " + T.type_adjusted, "info");
}

// ── Upload + Convert pipeline ─────────────────────────────────────────────────
async function uploadAndConvert(file, method) {
    fullConversionStart = performance.now();
    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();
    setOverlay(true, T.uploading); setLive("converting");
    window.trackEvent("upload_start", { method: method, filename: file.name, size: file.size });
    const fd = new FormData(); fd.append("file", file);
    try {
        const res = await fetch(UPLOAD_URL, { method:"POST", body:fd, signal:abortCtrl.signal });
        if (!res.ok) { const e = await res.json().catch(()=>({detail:res.statusText})); throw new Error(e.detail||"Upload error"); }
        const data = await res.json();
        currentSession = data.session_id;
        applyRecommendedParams(data.params, data.detected_type);
        await runConversion();
    } catch(e) {
        if (e.name === "AbortError") return;
        setOverlay(false); setLive("error"); setStatus(T.upload_error(e.message), "error"); currentSession = null;
        window.trackEvent("error", { step: "upload", msg: e.message }); // TRACKING ERREUR RÉSEAU
    }
}

// ── Conversion ────────────────────────────────────────────────────────────────
async function runConversion() {
    if (!currentSession) return;
    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();
    setOverlay(true, T.converting); setLive("converting");
    const fd = new FormData();
    fd.append("session_id", currentSession);
    Object.entries(getParams()).forEach(([k,v]) => fd.append(k,v));
    try {
        const res = await fetch(CONVERT_URL, { method:"POST", body:fd, signal:abortCtrl.signal });
        if (!res.ok) {
            if (res.status === 404 && currentFile) { await uploadAndConvert(currentFile); return; }
            const e = await res.json().catch(()=>({detail:res.statusText})); throw new Error(e.detail||"Server error");
        }
        const svg = await res.text(); currentSvg = svg;
        renderSvg(svg); setOverlay(false); setLive("ok");
        setStatus(T.ready((new Blob([svg]).size/1024).toFixed(1)), "ok");
        document.getElementById("btn-dl").disabled = false;

        const totalDurationMs = Math.round(performance.now() - fullConversionStart);
        window.trackEvent("conversion_success", { 
            session_id: currentSession, 
            total_duration_ms: totalDurationMs 
        });
    } catch(e) {
        if (e.name === "AbortError") return;
        setOverlay(false); setLive("error"); setStatus(T.conv_error(e.message), "error");
        window.trackEvent("error", { step: "conversion", msg: e.message }); // TRACKING ERREUR
    }
}

// ── File loading ──────────────────────────────────────────────────────────────
const ACCEPTED = ["image/png","image/jpeg","image/bmp","image/webp"];
function loadFile(file, method = "unknown") {
    if (!file || !ACCEPTED.includes(file.type)) { 
        setStatus(T.format_error, "error"); 
        window.trackEvent("error", { detail: "format_error", type: file?.type }); // TRACKING ERREUR
        return; 
    }
    currentFile = file; currentSession = null; clearPreview();
    document.getElementById("dropzone").classList.add("active");
    const reader = new FileReader();
    reader.onload = ev => {
        const dz = document.getElementById("dropzone");
        dz.querySelector(".dz-hint").style.display = "none";
        dz.querySelectorAll("img").forEach(n => n.remove());
        const img = document.createElement("img"); img.src = ev.target.result; dz.appendChild(img);
        let fn = dz.querySelector(".dz-fname");
        if (!fn) { fn = document.createElement("div"); fn.className = "dz-fname"; dz.appendChild(fn); }
        fn.textContent = `${file.name} \xB7 ${(file.size/1024).toFixed(0)} KB`;
    };
    reader.readAsDataURL(file);
    uploadAndConvert(file, method);
}

// ── Listeners ─────────────────────────────────────────────────────────────────
const dz = document.getElementById("dropzone");
dz.addEventListener("dragover",  e => { e.preventDefault(); dz.classList.add("drag-over"); });
dz.addEventListener("dragleave", ()  => dz.classList.remove("drag-over"));
dz.addEventListener("drop", e => { e.preventDefault(); dz.classList.remove("drag-over"); loadFile(e.dataTransfer.files[0], "drop"); });
dz.addEventListener("click", () => document.getElementById("file-input").click());
document.getElementById("file-input").addEventListener("change", e => { if (e.target.files[0]) loadFile(e.target.files[0], "click"); });
document.addEventListener("paste", e => { const f = e.clipboardData.files[0]; if (f?.type.startsWith("image/")) loadFile(f, "paste"); });


document.querySelectorAll("input[type=range]").forEach(sl => {
    const key = sl.id.replace("sl-",""), vl = document.getElementById("v-"+key);
    sl.addEventListener("input",  () => { if (vl) vl.textContent = key==="length_threshold" ? (+sl.value).toFixed(1) : sl.value; });
    sl.addEventListener("change", () => { clearActivePreset(); if (currentSession) runConversion(); });
});
document.querySelectorAll(".seg").forEach(seg => {
    seg.addEventListener("click", e => {
        const btn = e.target.closest("button"); if (!btn) return;
        seg.querySelectorAll("button").forEach(b => b.classList.remove("active")); btn.classList.add("active");
        if (seg.id === "seg-colormode") updateColormodeVis();
        clearActivePreset(); if (currentSession) runConversion();
    });
});
document.getElementById("sw-invert").addEventListener("change", () => { if (currentSession) runConversion(); });
document.getElementById("btn-dl").addEventListener("click", () => {
    if (!currentSvg) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([currentSvg],{type:"image/svg+xml"}));
    a.download = (currentFile?.name.replace(/\.[^.]+$/,"") || "output") + ".svg";
    a.click(); URL.revokeObjectURL(a.href); setStatus(T.saved(a.download), "ok");
});
document.getElementById("adv-toggle").addEventListener("click", () => {
    const open = document.getElementById("adv-content").classList.toggle("open");
    document.getElementById("adv-arrow").textContent = open ? "\u25B4" : "\u25BE";
});
document.querySelectorAll(".presets__btn").forEach(btn => btn.addEventListener("click", () => applyPreset(btn.dataset.preset)));
document.addEventListener("keydown", e => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s" && currentSvg) { e.preventDefault(); document.getElementById("btn-dl").click(); }
});

applyPreset("poster", false);
initTooltip();