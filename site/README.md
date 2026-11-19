# OpenPatch site

An engineering notebook / datasheet for OpenPatch, generated from the repository documents. **Test project, not a medical device, never to be used on a person or animal, water bench tests only.** Every page carries the safety banner (`scripts/gen/shell.mjs`); do not remove or weaken it.

## Build

```bash
cd site
npm ci
npm run build      # prebuild = npm run generate, then tsc --noEmit, then vite build -> dist/
npm run dev        # generate + vite dev server
npm run preview    # serve dist/ on 127.0.0.1:4173
node scripts/screenshots.mjs   # Playwright, 375/768/1440 x light/dark -> screenshots/ (needs preview running)
```

GitHub Pages: `.github/workflows/pages.yml` runs `npm ci && npm run build` in `site/` and uploads `site/dist`. Base path defaults to `./` (relative), so it works under any project-pages URL. No change to the workflow is needed.

## Pipeline: everything is generated from the repo

`npm run generate` runs two scripts. Their output is git-ignored (see `site/.gitignore`).

| Script | Reads | Produces |
|---|---|---|
| `scripts/build-site.mjs` (+ `scripts/gen/`) | `docs/06-diagnostics.md`, `docs/STATUS.md`, `docs/PARTS-LOCK.md`, `docs/SHOPPING.md`, `docs/05-cost-model.md`, `docs/02-safety.md`, `spec/design-parameters.md`, every registered markdown doc, `mechanical/out/bench/OP-100_layout_annotated.svg` | all HTML pages: `index.html`, `design/`, `safety/`, `faults/`, `status/`, `build/`, `parts/`, `licence/`, `legal/`, `docs/<slug>/` |
| `scripts/prepare-models.mjs` | `mechanical/out[/bench]/OP-<size>_<part>.stl`, optional `mechanical/components/` | `public/models/**.glb` and `public/models/manifest.json` |

* **Fault explorer**: the catalogue tables of `docs/06-diagnostics.md` (header `Code | Name | Detection | By | Sev | FRU: action | Haz | Test | Trio text`) are parsed into 150 static cards; layer, component, FRU and action names come from the doc's own tables (sections 2.3 to 2.5, 4.8). A tiny script (`src/pages/faults.ts`, under 1 kB gzip) filters them. Deep links: `faults/#c-1-06-001`, `faults/#q=watchdog`.
* **Status board**: tables, warnings, decision log and next steps of `docs/STATUS.md`. The badge is a keyword reading of the "Verified" text.
* **Safety page**: layers, hazard table and traceability come from `docs/06-diagnostics.md` and `docs/02-safety.md`; the interlock formula is `latch AND MCU_EN AND (DOCKED OR DIR_REV)` (spec 7a). If the formula changes, edit `gateSvg()` and the truth-table loop in `scripts/gen/pages-b.mjs` and `src/pages/safety.ts`.
* **Docs**: the list in `scripts/gen/docs.mjs` plus any new `docs/*.md`. A file is skipped when missing (or, for licence files, when it does not yet contain the current licence text), so the build works on any branch state.
* Parsers are tolerant: a missing source or changed table shape degrades to a visible note on the page instead of failing the build. Check the build log line `build-site: N pages (...)`.

## Images and build steps (renders pipeline)

`scripts/gen/media.mjs` consumes what the render and build-guide agents write:

* `docs/renders/manifest.json`: entries `{id, file, kind: hero|exploded|section|detail|step|component|turntable, title, caption, size, variant: light|dark}`. `file` is resolved against `docs/renders/`, then the repo root. A light and a dark entry with the same id (or a `-light` / `-dark` suffix) become one theme-aware image. Video files (mp4/webm) of kind `turntable` are copied as is.
* `docs/build-guide/steps.json`: steps `{id, title, image, parts[], tools[], check, warnings}`. `parts` and `tools` may be strings or `{name, qty, image}`; optional `notes`, `group`, `check_image`.

Every raster image is resized to 480/960/1600 px and written as AVIF + WebP into `public/img/` (cache in `.cache/`, both git-ignored). Kinds that the manifest does not cover fall back to interim CAD views from `mechanical/out/bench/` and `mechanical/components/out/`, flagged "Interim CAD view" on the page; without `steps.json` the build page follows `mechanical/ASSEMBLY.md`. The build log prints which kinds are still waiting.

Facts (`scripts/gen/facts.mjs`): sizes from `mechanical/out/bench/OP-*.mech.json` (spec section 2 as fallback), gear pair and U/step from spec section 4, safety limits from spec section 7, cost from `docs/SHOPPING.md` section 0.1, simulation counts from `mechanical/sim/REPORT.md`, licence terms from `COMMERCIAL-LICENSE.md`. A prose document that disagrees with the generated data is listed as stale (build log and status page).

## 3D viewer and realistic models

The viewer (`src/viewer/mount.ts`, three.js, about 160 kB gzip) loads only when the visitor presses "Load 3D model". The page itself ships no 3D code.

Sources, in order of preference (`scripts/prepare-models.mjs`):

1. **Assembly glTF**: the first file matching `assembly*.glb|gltf` in `mechanical/components/`, then `mechanical/out/bench/`, then `mechanical/out/`. Each top-level node is one selectable part. A node is matched to a catalog entry when its name equals or contains the entry `id`.
2. **`mechanical/components/catalog.json`** (vendor-accurate component models). Accepted shapes: an array, or `{components: [...]}` / `{parts: [...]}`. Per entry, the first present key of each group is used:
   * id: `id`, `key`, `ref`, `name`
   * part number: `mpn`, `part_number`, `partNumber`, `pn`; vendor: `manufacturer`, `vendor`, `brand`, `supplier`
   * model file (relative to `catalog.json`): `gltf`, `glb`, `model`, `file`, `path`; `.gltf` buffers and textures are copied along
   * `lock_no` (row in `docs/PARTS-LOCK.md`, fills the "3D model" column of the parts table), `datasheet`, `dims_mm`, `position_mm` (placed in the CAD frame when there is no assembly glTF), `verified`, `source`, `note`
3. **Fallback**: generated CAD STLs, welded and written as compact `.glb`. Part names and notes come from `scripts/part-meta.json`.

The manifest records which source is used; the page note under the viewer states it. Models are shown as "generated envelope, not vendor-accurate" unless they come from the catalog.

Regenerate after the CAD or components change:

```bash
cd mechanical && python3 generate.py --variant bench     # STL/STEP/annotated SVG into out/bench
cd ../site && npm run build
```

When the components agent lands `catalog.json` and the pod assembly glTF, no site change is needed. If their field names differ from the list above, extend the `pick(...)` calls in `scripts/prepare-models.mjs`.

Path-traced marketing renders (`npm run renders`, SolidCraft) are no longer used by the site and are kept only as an optional tool; they write to `public/renders/`.

## Design and accessibility notes

* Paper and ink palette with a drawing-blue accent, monospace for numbers and codes, system font stacks only. Colour tokens are in `src/site.css` (light, dark, and a manual Auto/Light/Dark toggle).
* WCAG AA contrast in both themes; severity and status are never colour-only (letter marks and text labels). Keyboard: skip link, all controls are native elements, tables scroll in focusable regions, the 3D canvas has arrow/plus/minus/Escape keys and every part is also a list button.
* Initial JS per page: 0.9 to 2.5 kB gzip. CSS about 5 kB gzip.

## Privacy and exposure rules

No cookies, no analytics, no third-party requests (a CSP enforces `self`), fonts are system fonts. No personal names, addresses, e-mails or photos anywhere; refer to "the OpenPatch maintainer" and link only to the repository. There is deliberately no Impressum. Keep the disclaimers (`scripts/gen/pages-legal.mjs`) and the top banner.
