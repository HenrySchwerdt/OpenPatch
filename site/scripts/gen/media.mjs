// Images and the IKEA-style build steps.
// Consumes, when present:
//   docs/renders/manifest.json         entries {id, file, kind: hero|exploded|section|detail|step|component|turntable, title, caption, size, variant: light|dark}
//   docs/build-guide/steps.json        steps  {id, title, image, parts[], tools[], check, warnings}
// When they do not exist yet, interim CAD views from mechanical/ are used and flagged as interim, so the site builds on any branch state.
// Every raster image is resized and written as AVIF + WebP (responsive srcset) into public/img/; results are cached in site/.cache/.
import { copyFileSync, existsSync, mkdirSync, readFileSync, readdirSync, statSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { basename, extname, join } from 'node:path';
import sharp from 'sharp';
import { REPO_ROOT, SITE, esc, read } from './lib.mjs';

const OUT = join(SITE, 'public', 'img');
const CACHE = join(SITE, '.cache', 'img');
const WIDTHS = [480, 960, 1600];
mkdirSync(OUT, { recursive: true });
mkdirSync(CACHE, { recursive: true });

const readJson = (rel) => { try { return JSON.parse(readFileSync(join(REPO_ROOT, rel), 'utf8')); } catch { return null; } };
const slugify = (s) => String(s).toLowerCase().replace(/\.[a-z0-9]+$/, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 48) || 'img';

/** Resolve a path written in a manifest against a few plausible bases. */
function resolveFile(file, bases) {
  if (!file) return null;
  for (const b of bases) {
    const p = join(REPO_ROOT, b, file);
    if (existsSync(p) && statSync(p).isFile()) return p;
  }
  const p = join(REPO_ROOT, file);
  return existsSync(p) && statSync(p).isFile() ? p : null;
}

const processed = new Map();
/** Write responsive AVIF/WebP for one source image. Returns {key, w, h, widths}. crop = {left, top, width, height}. */
async function rasterise(src, crop) {
  const st = statSync(src);
  const id = createHash('sha1').update(`${src}|${st.size}|${st.mtimeMs}|${JSON.stringify(crop ?? null)}|v3`).digest('hex').slice(0, 10);
  if (processed.has(id)) return processed.get(id);
  const key = `${slugify(basename(src))}-${id}`;
  const meta = JSON.parse(existsSync(join(CACHE, `${key}.json`)) ? readFileSync(join(CACHE, `${key}.json`), 'utf8') : 'null');
  let info = meta;
  if (!info) {
    let base = sharp(src, { limitInputPixels: 268e6 }).rotate();
    if (crop) base = base.extract(crop);
    const buf = await base.toBuffer();
    const m = await sharp(buf).metadata();
    const widths = [...new Set(WIDTHS.filter((w) => w < m.width).concat([Math.min(m.width, 1600)]))].sort((a, b) => a - b);
    for (const w of widths) {
      const r = sharp(buf).resize({ width: w, withoutEnlargement: true });
      await r.clone().avif({ quality: 52, effort: 3 }).toFile(join(CACHE, `${key}-${w}.avif`));
      await r.clone().webp({ quality: 78 }).toFile(join(CACHE, `${key}-${w}.webp`));
    }
    info = { key, w: m.width, h: m.height, widths: widths.map((w) => w) };
    writeFileSync(join(CACHE, `${key}.json`), JSON.stringify(info));
  }
  for (const w of info.widths) for (const e of ['avif', 'webp']) copyFileSync(join(CACHE, `${key}-${w}.${e}`), join(OUT, `${key}-${w}.${e}`));
  processed.set(id, info);
  return info;
}

/** Copy a video file as is (turntables). */
function copyVideo(src) {
  const name = `${slugify(basename(src))}${extname(src).toLowerCase()}`;
  mkdirSync(join(SITE, 'public', 'media'), { recursive: true });
  copyFileSync(src, join(SITE, 'public', 'media', name));
  return `media/${name}`;
}

const isVideo = (f) => /\.(mp4|webm)$/i.test(f);
const isRaster = (f) => /\.(png|jpe?g|webp|avif|gif|tiff?)$/i.test(f);

// ------------------------------------------------------------------ interim images (until docs/renders/manifest.json exists)
const BENCH = 'mechanical/out/bench';
const COMP = 'mechanical/components/out';
function interimEntries() {
  const e = [];
  const add = (o) => { if (resolveFile(o.file, [''])) e.push({ interim: true, variant: 'any', ...o }); };
  add({ id: 'interim-hero', kind: 'hero', file: `${BENCH}/OP-100_iso.png`, title: 'OP-100 bench pod, isometric', caption: 'Interim CAD view.', crop: { left: 300, top: 170, width: 740, height: 500 } });
  add({ id: 'interim-exploded', kind: 'exploded', file: `${BENCH}/OP-100_exploded.png`, title: 'OP-100 exploded view', caption: 'Interim CAD view.', crop: { left: 440, top: 170, width: 860, height: 800 } });
  const sec = [['y_motor', 'Section through the motor', 'Drive train: motor, gear pair, leadscrew and carriage.'], ['y_reservoir', 'Section through the reservoir', 'Reservoir, plunger and lip seals.'], ['y_cannula', 'Section through the dock', 'Cannula dock, needle and fluid path.'], ['y_screw', 'Section through the leadscrew', 'Leadscrew lane and carriage.']];
  for (const [k, title, caption] of sec) add({ id: `interim-section-${k}`, kind: 'section', file: `${BENCH}/OP-100_section_${k}.png`, title, caption, crop: { left: 270, top: 190, width: 1020, height: 220 } });
  add({ id: 'interim-section-plan', kind: 'section', file: `${BENCH}/OP-100_section_plan_z4.2.png`, title: 'Plan section at 4.2 mm', caption: 'Looking down into the open pod.' });
  const cat = readJson('mechanical/components/catalog.json') ?? {};
  for (const [id, c] of Object.entries(cat)) {
    const png = c?.files?.png ? `mechanical/components/${c.files.png}` : `${COMP}/${id}.png`;
    add({ id: `comp-${id}`, kind: 'component', file: png, title: String(c?.title ?? id).split(',')[0].split(' (')[0], caption: '', compId: id, mm: c?.size_mm });
  }
  return e;
}

function loadManifest() {
  const m = readJson('docs/renders/manifest.json');
  const list = Array.isArray(m) ? m : (m?.renders ?? m?.images ?? m?.entries ?? []);
  return list.filter((x) => x && x.file);
}

/** Group entries by id (light and dark variants share an id, or carry a -light / -dark suffix) and rasterise. */
async function build(entries, bases) {
  const groups = new Map();
  for (const x of entries) {
    const variant = x.variant === 'dark' || x.variant === 'light' ? x.variant : 'any';
    const gid = variant === 'any' ? x.id : String(x.id).replace(/[-_.](light|dark)$/i, '');
    const g = groups.get(gid) ?? { id: gid, kind: x.kind, title: x.title, caption: x.caption, interim: !!x.interim, variants: {}, extra: x };
    g.title ||= x.title; g.caption ||= x.caption;
    const src = x.abs ?? resolveFile(x.file, bases);
    if (!src) { groups.set(gid, g); continue; }
    if (isVideo(src)) g.video = copyVideo(src);
    else if (isRaster(src)) g.variants[variant] = await rasterise(src, x.crop);
    groups.set(gid, g);
  }
  return [...groups.values()].filter((g) => Object.keys(g.variants).length || g.video);
}

// ------------------------------------------------------------------ picture markup
const dimsOf = (v) => `width="${v.w}" height="${v.h}"`;
function sources(v, sizes) {
  const set = (ext) => v.widths.map((w) => `img/${v.key}-${w}.${ext}`);
  return { set, sizes };
}

/** <picture> for one variant. root is the relative prefix of the page. */
export function pictureHtml(v, root, { alt = '', sizes = '100vw', eager = false, cls = '' } = {}) {
  const set = (ext) => v.widths.map((w) => `${root}img/${v.key}-${w}.${ext} ${w}w`).join(', ');
  const mid = v.widths[Math.min(1, v.widths.length - 1)];
  return `<picture${cls ? ` class="${cls}"` : ''}><source type="image/avif" srcset="${set('avif')}" sizes="${sizes}"><source type="image/webp" srcset="${set('webp')}" sizes="${sizes}"><img src="${root}img/${v.key}-${mid}.webp" ${dimsOf(v)} alt="${esc(alt)}" decoding="async"${eager ? ' fetchpriority="high"' : ' loading="lazy"'}></picture>`;
}

/** Theme-aware image: one picture per variant, CSS shows the one matching the colour scheme (hidden ones are lazy and never load). */
export function themed(g, root, opts = {}) {
  if (!g) return '';
  if (g.video && !Object.keys(g.variants).length) return `<video class="turntable" src="${root}${g.video}" muted loop playsinline autoplay preload="metadata" aria-label="${esc(opts.alt ?? g.title ?? '')}"></video>`;
  const { light, dark, any } = g.variants;
  const alt = opts.alt ?? g.title ?? '';
  if (any || !(light && dark)) return pictureHtml(any ?? light ?? dark, root, { ...opts, alt });
  return `${pictureHtml(light, root, { ...opts, alt, eager: false, cls: 'th-light' })}${pictureHtml(dark, root, { ...opts, alt, eager: false, cls: 'th-dark' })}`;
}

// ------------------------------------------------------------------ steps (docs/build-guide/steps.json) and interim steps
const asList = (x) => (Array.isArray(x) ? x : x == null || x === '' ? [] : [x]);
const nameOf = (x) => (typeof x === 'string' ? { name: x } : { name: x?.name ?? x?.title ?? x?.id ?? '', qty: x?.qty ?? x?.count ?? null, note: x?.note ?? '', image: x?.image ?? x?.file ?? null });

function stepsFromAssembly(media) {
  const src = read('mechanical/ASSEMBLY.md');
  if (!src) return [];
  const bench = src.slice(src.indexOf('# Bench pod assembly'));
  const parts = bench.split(/\n(?=## B\d+\.)/).slice(1);
  const seen = new Set();
  const keyImg = [[/duckbill|valve/i, 'duckbill_valve_generic'], [/needle/i, 'needle_30g_efd_14in'], [/gear|motor|leadscrew/i, 'nfp_608_26_45'], [/board|ffc|hall/i, 'ffc_05mm_10p_same_side'], [/dock|adapter|cannula/i, 'cannula_head_dummy'], [/magnet/i, 'magnet_d3x1p5_diametric'], [/septum/i, 'septum_d4x2'], [/screw|clos/i, 'screw_iso7045_m1p2x4']];
  const comp = (id) => media.find((g) => g.id === `comp-${id}`);
  const hero = media.find((g) => g.id === 'interim-exploded');
  const toolWords = [['tweezers', 'Tweezers'], ['screwdriver', 'Screwdriver PH000'], ['loctite|cyanoacrylate|CA drop', 'Thread-locker or CA glue'], ['punch', 'Biopsy punch'], ['drill', 'Pin vise and drills'], ['razor', 'Razor blade']];
  const out = [];
  for (const blk of parts) {
    const m = /^## (B\d+)\.\s*(.+)$/m.exec(blk);
    if (!m || seen.has(m[1])) continue;
    seen.add(m[1]);
    const body = blk.split('\n').slice(1).join('\n');
    const items = body.split('\n').filter((l) => /^\s*(\d+\.|\*)\s/.test(l)).map((l) => l.replace(/^\s*(\d+\.|\*)\s+/, '').replace(/`/g, '').replace(/\*\*/g, ''));
    const text = items.length ? items : [body.trim().replace(/`/g, '').replace(/\*\*/g, '').split('\n')[0]].filter(Boolean);
    const bold = [...body.matchAll(/\*\*([^*]{3,40})\*\*/g)].map((x) => x[1]).filter((x) => !/^(Pins|Dock|Tongue|Plunger|Dock insert)/i.test(x));
    const hit = keyImg.find(([re]) => re.test(m[2]));
    const img = (hit && comp(hit[1])) || hero;
    out.push({
      id: m[1].toLowerCase(), title: m[2].replace(/\s*\(.*$/, '').replace(/\s*\d{4}-\d\d-\d\d.*$/, ''), group: null,
      notes: text.slice(0, 6).map((t) => (t.length > 260 ? `${t.slice(0, 257).replace(/\s+\S*$/, '')}…` : t)),
      parts: [...new Set(bold)].slice(0, 6).map((n) => ({ name: n })),
      tools: toolWords.filter(([re]) => new RegExp(re, 'i').test(body)).map(([, n]) => ({ name: n })),
      check: /B8|B1|B6/.test(m[1]) ? (items[0] ?? '') : '', warnings: /water/i.test(body) ? ['Water only. Never connect to a person.'] : [],
      image: img, interim: true, source: 'mechanical/ASSEMBLY.md',
    });
  }
  return out;
}

async function loadSteps(media) {
  const raw = readJson('docs/build-guide/steps.json');
  const list = Array.isArray(raw) ? raw : (raw?.steps ?? []);
  if (!list.length) return { steps: stepsFromAssembly(media), interim: true };
  const bases = ['docs/build-guide', 'docs/build-guide/img', 'docs/renders', ''];
  const steps = [];
  for (const [i, s] of list.entries()) {
    const imgSrc = typeof s.image === 'object' && s.image ? (s.image.file ?? s.image.light) : s.image;
    const img = imgSrc ? await build([{ id: `step-${s.id ?? i}`, kind: 'step', variant: 'any', file: imgSrc, title: s.title }], bases) : [];
    const chk = s.check && typeof s.check === 'object' ? s.check : { text: s.check };
    const chkFile = chk.image ?? s.check_image;
    const checkImg = chkFile ? await build([{ id: `check-${s.id ?? i}`, kind: 'step', variant: 'any', file: chkFile, title: `Check: ${s.title}` }], bases) : [];
    const partsList = [];
    for (const p of asList(s.parts)) {
      const n = nameOf(p);
      const pimg = n.image ? (await build([{ id: `p-${slugify(n.name)}`, kind: 'component', variant: 'any', file: n.image, title: n.name }], bases))[0] : null;
      partsList.push({ ...n, img: pimg });
    }
    steps.push({
      id: String(s.id ?? `s${i + 1}`), title: s.title ?? `Step ${i + 1}`, group: s.group ?? s.phase ?? null,
      notes: asList(s.notes ?? s.instructions ?? s.text ?? s.description).map(String),
      parts: partsList, tools: asList(s.tools).map(nameOf),
      check: chk.text ?? '', checkImage: checkImg[0] ?? null, warnings: asList(s.warnings ?? s.warning).map(String),
      image: img[0] ?? null, interim: false, source: 'docs/build-guide/steps.json',
    });
  }
  return { steps, interim: false };
}

/** Everything the page generators need. */
export async function loadMedia() {
  const manifest = loadManifest();
  const real = await build(manifest, ['docs/renders', 'docs/renders/img', 'docs']);
  const interim = await build(interimEntries(), ['']);
  const kinds = new Set(real.map((g) => g.kind));
  // an interim entry is used only for a kind (or id) that the real manifest does not cover
  const fallbackKinds = interim.filter((g) => g.kind !== 'component' && !kinds.has(g.kind));
  const comps = interim.filter((g) => g.kind === 'component' && !real.some((r) => r.kind === 'component' && r.id === g.id));
  const all = [...real, ...fallbackKinds, ...comps];
  const find = (...pats) => { for (const p of pats) { const hit = all.find((g) => (typeof p === 'string' ? g.id === p || g.kind === p : p.test(`${g.id} ${g.title}`))); if (hit) return hit; } return null; };
  const ofKind = (k) => all.filter((g) => g.kind === k);
  const stepData = await loadSteps(interim);
  return {
    all, find, ofKind, steps: stepData.steps, stepsInterim: stepData.interim,
    hasManifest: manifest.length > 0, realCount: real.length, interimUsed: fallbackKinds.length > 0 || stepData.interim,
    waiting: ['hero', 'exploded', 'section', 'detail', 'step', 'component', 'turntable'].filter((k) => !kinds.has(k)),
  };
}

export { sources };
