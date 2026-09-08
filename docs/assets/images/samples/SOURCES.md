# Sample imagery — sources & licenses

Files in this directory are **generated** by `scripts/generate-samples.py`
(run with the main app venv:
`/home/lcrappier/Projets/PixelToPath/env/bin/python scripts/generate-samples.py`).
All traced SVGs are genuine tool output produced with the presets shipped in
`moteur/image_utils.py` (`bw`, `poster`, `photo`).

## Drawn inputs (no external rights)

- `logo-input.png`, `logo-tiny.png` — drawn programmatically (PIL): navy disc
  with white chevron knockout.
- `sticker-input.png` — drawn programmatically (PIL): flat-color retro badge
  (sky bands, sun, mountains).

## Photo input (CC0)

- `photo-input.jpg` — crop/resize of
  [“Hot air balloon in blue sky (Unsplash)”](https://commons.wikimedia.org/wiki/File:Hot_air_balloon_in_blue_sky_(Unsplash).jpg)
  (archived copy, Wikimedia Commons), license
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/).
  Original source: Unsplash. Fetched from
  `https://commons.wikimedia.org/wiki/Special:FilePath/Hot%20air%20balloon%20in%20blue%20sky%20(Unsplash).jpg`
  and cached in `scripts/.cache/` (not committed).

## Derived files

`*-zoom.webp` composites (PNG · 400% vs SVG · 400%) and
`assets/images/og/og-{logo,sticker,photo}.jpg` are assembled from the inputs
and traced SVGs above; the CC0 photo's terms impose no attribution
requirement, and this file records the source for transparency.
