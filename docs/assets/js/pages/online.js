const API_URL = "https://api.pixel-to-path.com/convert";

let currentFile = null;
let currentSvg = null;
let debounceId = null;
let abortCtrl = null;

const PRESETS = {
    bw: {
        colormode: "binary",
        mode: "spline",
        filter_speckle: 4,
        color_precision: 6,
        layer_difference: 16,
        corner_threshold: 60,
        length_threshold: 4.0,
        splice_threshold: 45,
        num_colors: 8,
    },
    poster: {
        colormode: "color",
        mode: "spline",
        filter_speckle: 4,
        color_precision: 8,
        layer_difference: 6,
        corner_threshold: 60,
        length_threshold: 4.0,
        splice_threshold: 45,
        num_colors: 8,
    },
    photo: {
        colormode: "color",
        mode: "spline",
        filter_speckle: 10,
        color_precision: 6,
        layer_difference: 16,
        corner_threshold: 60,
        length_threshold: 4.0,
        splice_threshold: 45,
        num_colors: 12,
    },
};

function applyPreset(key) {
    const p = PRESETS[key];
    document
        .querySelectorAll(".presets__btn")
        .forEach((b) => b.classList.toggle("presets__btn--active", b.dataset.preset === key));
    setSegVal("seg-colormode", p.colormode);
    setSegVal("seg-mode", p.mode);
    [
        "num_colors",
        "color_precision",
        "layer_difference",
        "corner_threshold",
        "length_threshold",
        "splice_threshold",
        "filter_speckle",
    ].forEach((k) => setSlider(k, p[k]));
    updateColormodeVis();
    schedule();
}

function getSegVal(id) {
    return document.querySelector(`#${id} button.active`)?.dataset.val ?? "";
}
function setSegVal(id, val) {
    document
        .querySelectorAll(`#${id} button`)
        .forEach((b) => b.classList.toggle("active", b.dataset.val === val));
}
function setSlider(id, v) {
    const sl = document.getElementById("sl-" + id);
    const vl = document.getElementById("v-" + id);
    if (sl) sl.value = v;
    if (vl) vl.textContent = id === "length_threshold" ? (+v).toFixed(1) : v;
}
function updateColormodeVis() {
    const m = getSegVal("seg-colormode");
    document.getElementById("color-params").style.display =
        m === "color" ? "" : "none";
    document.getElementById("binary-params").style.display =
        m === "binary" ? "" : "none";
}
function getParams() {
    return {
        colormode: getSegVal("seg-colormode"),
        hierarchical: getSegVal("seg-hierarchical"),
        mode: getSegVal("seg-mode"),
        num_colors: +document.getElementById("sl-num_colors").value,
        filter_speckle: +document.getElementById("sl-filter_speckle").value,
        color_precision: +document.getElementById("sl-color_precision").value,
        layer_difference: +document.getElementById("sl-layer_difference").value,
        corner_threshold: +document.getElementById("sl-corner_threshold").value,
        length_threshold: +document.getElementById("sl-length_threshold").value,
        splice_threshold: +document.getElementById("sl-splice_threshold").value,
        invert: document.getElementById("sw-invert").checked,
    };
}

function schedule() {
    if (!currentFile) return;
    clearTimeout(debounceId);
    debounceId = setTimeout(runConversion, 600);
}

async function runConversion() {
    if (!currentFile) return;
    if (abortCtrl) abortCtrl.abort();
    abortCtrl = new AbortController();

    setOverlay(true, "Converting…");
    setLive("converting");

    const fd = new FormData();
    fd.append("file", currentFile);
    Object.entries(getParams()).forEach(([k, v]) => fd.append(k, v));

    try {
        const res = await fetch(API_URL, {
            method: "POST",
            body: fd,
            signal: abortCtrl.signal,
        });
        if (!res.ok) {
            const e = await res
                .json()
                .catch(() => ({ detail: res.statusText }));
            throw new Error(e.detail || "Server error");
        }

        const svg = await res.text();
        currentSvg = svg;
        renderSvg(svg);
        setOverlay(false);
        setLive("ok");
        setStatus(
            `✓ Ready · ${(new Blob([svg]).size / 1024).toFixed(1)} KB`,
            "ok",
        );
        document.getElementById("btn-dl").disabled = false;
    } catch (e) {
        if (e.name === "AbortError") return;
        setOverlay(false);
        setLive("error");
        setStatus("✕ " + e.message, "error");
    }
}

function renderSvg(svgStr) {
    const container = document.getElementById("preview__body__svg-container");
    document.getElementById("placeholder").style.display = "none";
    container.querySelectorAll("svg").forEach((n) => n.remove());

    const doc = new DOMParser().parseFromString(svgStr, "image/svg+xml");
    const svgEl = doc.documentElement;

    // Keep viewBox but remove fixed width/height so it scales to container
    const vb = svgEl.getAttribute("viewBox");
    if (!vb) {
        const w = svgEl.getAttribute("width");
        const h = svgEl.getAttribute("height");
        if (w && h) svgEl.setAttribute("viewBox", `0 0 ${w} ${h}`);
    }
    svgEl.removeAttribute("width");
    svgEl.removeAttribute("height");
    svgEl.style.width = "100%";
    svgEl.style.height = "100%";
    svgEl.style.display = "block";

    container.appendChild(svgEl);
}

const dz = document.getElementById("dropzone");
dz.addEventListener("dragover", (e) => {
    e.preventDefault();
    dz.classList.add("drag-over");
});
dz.addEventListener("dragleave", () => dz.classList.remove("drag-over"));
dz.addEventListener("drop", (e) => {
    e.preventDefault();
    dz.classList.remove("drag-over");
    loadFile(e.dataTransfer.files[0]);
});
dz.addEventListener("click", () =>
    document.getElementById("file-input").click(),
);
document.getElementById("file-input").addEventListener("change", (e) => {
    if (e.target.files[0]) loadFile(e.target.files[0]);
});
document.addEventListener("paste", (e) => {
    const f = e.clipboardData.files[0];
    if (f?.type.startsWith("image/")) loadFile(f);
});

const ACCEPTED = ["image/png", "image/jpeg", "image/bmp", "image/webp"];
function loadFile(file) {
    if (!file || !ACCEPTED.includes(file.type)) {
        setStatus("Format not accepted — PNG, JPG, BMP or WebP only", "error");
        return;
    }
    currentFile = file;
    currentSvg = null;
    document.getElementById("btn-dl").disabled = true;
    document.getElementById("dropzone").classList.add("active")
    const reader = new FileReader();
    reader.onload = (ev) => {
        dz.querySelector(".dz-hint").style.display = "none";
        dz.querySelectorAll("img").forEach((n) => n.remove());
        const img = document.createElement("img");
        img.src = ev.target.result;
        dz.appendChild(img);
        let fn = dz.querySelector(".dz-fname");
        if (!fn) {
            fn = document.createElement("div");
            fn.className = "dz-fname";
            dz.appendChild(fn);
        }
        fn.textContent = `${file.name} · ${(file.size / 1024).toFixed(0)} KB`;
    };
    reader.readAsDataURL(file);
    schedule();
}

document.getElementById("btn-dl").addEventListener("click", () => {
    if (!currentSvg) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(
        new Blob([currentSvg], { type: "image/svg+xml" }),
    );
    a.download =
        (currentFile?.name.replace(/\.[^.]+$/, "") || "output") + ".svg";
    a.click();
    URL.revokeObjectURL(a.href);
    setStatus(`✓ Saved as ${a.download}`, "ok");
});

function setOverlay(show, text = "Converting…") {
    document.getElementById("overlay").classList.toggle("active", show);
    document.getElementById("overlay-text").textContent = text;
}
function setStatus(msg, type) {
    const el = document.getElementById("status");
    el.textContent = msg;
    el.className = type || "";
}
function setLive(state) {
    const dot = document.getElementById("live-dot"),
        text = document.getElementById("live-text");
    const c = { ok: "#4caf7d", converting: "#e09a00", error: "#c62828" };
    dot.style.background = c[state];
    dot.style.animation = state === "ok" ? "" : "none";
    text.textContent =
        state === "converting"
            ? "converting…"
            : state === "error"
              ? "error"
              : "live";
}

document.querySelectorAll(".seg").forEach((seg) => {
    seg.addEventListener("click", (e) => {
        const btn = e.target.closest("button");
        if (!btn) return;
        seg.querySelectorAll("button").forEach((b) =>
            b.classList.remove("active"),
        );
        btn.classList.add("active");
        if (seg.id === "seg-colormode") updateColormodeVis();
        schedule();
    });
});
document.querySelectorAll("input[type=range]").forEach((sl) => {
    const key = sl.id.replace("sl-", ""),
        vl = document.getElementById("v-" + key);
    sl.addEventListener("input", () => {
        if (vl)
            vl.textContent =
                key === "length_threshold" ? (+sl.value).toFixed(1) : sl.value;
    });
    sl.addEventListener("change", schedule);
});
document.getElementById("sw-invert").addEventListener("change", schedule);
document.getElementById("adv-toggle").addEventListener("click", () => {
    const open = document
        .getElementById("adv-content")
        .classList.toggle("open");
    document.getElementById("adv-arrow").textContent = open ? "▴" : "▾";
});
document
    .querySelectorAll(".presets__btn")
    .forEach((btn) =>
        btn.addEventListener("click", () => applyPreset(btn.dataset.preset)),
    );
document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "s" && currentSvg) {
        e.preventDefault();
        document.getElementById("btn-dl").click();
    }
});

applyPreset("poster");
