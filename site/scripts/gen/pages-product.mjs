// Product / Design page: exploded hero, size overlay, scroll story, lazy 3D viewer, component library, collapsible data.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { SITE, blobUrl, esc } from './lib.mjs';
import { stage } from './pages-home.mjs';
import { themed } from './media.mjs';

const f1 = (n) => (Math.round(n * 10) / 10).toFixed(1);

function modelBytes() {
  try {
    const m = JSON.parse(readFileSync(join(SITE, 'public', 'models', 'manifest.json'), 'utf8'));
    const sum = (m.sizes?.['100']?.parts ?? []).reduce((a, p) => a + (p.bytes ?? 0), 0) + (m.assembly?.bytes ?? 0);
    return sum ? `${(sum / 1e6).toFixed(1)} MB` : null;
  } catch { return null; }
}

/** All pods and the DASH outline drawn over each other at one scale (plan view), plus thickness bars. */
export function sizeFigure(F) {
  if (!F.sizes.length) return '';
  const shapes = [...(F.dash ? [{ ...F.dash, ref: true }] : []), ...[...F.sizes].sort((a, b) => b.l - a.l).map((s) => ({ ...s, name: s.id }))];
  const S = 8;
  const W = Math.max(...shapes.map((s) => s.l)) * S;
  const H = Math.max(...shapes.map((s) => s.w)) * S;
  const pad = 18;
  const labelX = W + 28;
  const plan = shapes.map((s, i) => {
    const w = s.l * S, h = s.w * S;
    const y = (H - h) / 2 + pad;
    return `<rect class="sz ${s.ref ? 'sz-ref' : `sz-${i}`}" x="${pad}" y="${y}" width="${w}" height="${h}" rx="${(s.ref ? 8 : 5) * S / 2}"/>`;
  }).join('');
  const legend = `<ul class="szlegend">${shapes.map((s, i) => `<li><i class="sw ${s.ref ? 'sz-ref' : `sz-${i}`}"></i><b>${esc(s.name)}</b> <span class="num">${f1(s.l)} \u00d7 ${f1(s.w)} \u00d7 ${f1(s.h)} mm</span></li>`).join('')}</ul>`;
  const maxH = Math.max(...shapes.map((s) => s.h));
  const bars = shapes.map((s, i) => `<g><text class="szl" x="${pad}" y="${H + pad * 2 + 30 + i * 34 + 12}">${esc(s.name)}</text><rect class="sz ${s.ref ? 'sz-ref' : `sz-${i}`}" x="${pad + 120}" y="${H + pad * 2 + 30 + i * 34}" width="${(s.h / maxH) * (W - 190)}" height="18" rx="3"/><text class="szd" x="${pad + 128 + (s.h / maxH) * (W - 190)}" y="${H + pad * 2 + 30 + i * 34 + 13}">${f1(s.h)} mm</text></g>`).join('');
  const total = H + pad * 2 + 30 + shapes.length * 34 + 6;
  return `<figure class="sizefig"><svg viewBox="0 0 ${Math.ceil(W + pad * 2)} ${Math.ceil(total)}" role="img" aria-labelledby="sz-t sz-d" class="drawing">
<title id="sz-t">Pod outlines to scale, plan view, and thickness</title>
<desc id="sz-d">${shapes.map((s) => `${s.name} ${f1(s.l)} by ${f1(s.w)} by ${f1(s.h)} millimetres`).join('; ')}.</desc>
${plan}
<text class="szc" x="${pad}" y="${H + pad * 2 + 14}">THICKNESS</text>${bars}</svg>
${legend}<figcaption>All outlines at one scale. Dashed: Omnipod DASH for comparison. Pod sizes from the generated CAD data, comparison from spec section 2.</figcaption></figure>`;
}

export function product(ctx) {
  const { root, facts: F, media, parts: P } = ctx;
  const exploded = media.find('exploded');
  const secs = media.ofKind('section');
  const byRe = (re) => secs.find((g) => re.test(`${g.id} ${g.title}`)) ?? null;
  const sReservoir = byRe(/reservoir/i) ?? secs[0] ?? null;
  const sMotor = byRe(/motor|drive|screw/i) ?? secs[1] ?? secs[0] ?? null;
  const sDock = media.find(/dock|cannula/i) ?? byRe(/cannula|dock/i) ?? secs[2] ?? secs[0] ?? null;
  const sPlan = byRe(/plan/i) ?? media.find('detail') ?? secs[secs.length - 1] ?? null;
  const turntable = media.ofKind('turntable')[0] ?? null;
  const comps = media.ofKind('component');
  const mb = modelBytes();
  const h = F.hero;
  const res = F.sizes.find((s) => s.strokeMm);

  const chapters = [
    { id: 'reservoir', img: sReservoir, n: '01', t: 'A flat reservoir', p: `A stadium-shaped bore, 16.0 × 5.0 mm, holds up to ${F.sizes.map((s) => s.ml).join(', ')} ml. ${res ? `The stroke is ${F.sizes.map((s) => f1(s.strokeMm)).join(', ')} mm for ${F.sizes.map((s) => s.units).join(', ')} U.` : ''} A cast silicone lip seal rides on a polypropylene plunger.`, k: 'Reservoir' },
    { id: 'drive', img: sMotor, n: '02', t: 'A tiny geared motor, a precise screw', p: `${F.motor ? `The ${esc(F.motor)} stepper` : 'A 6 mm geared stepper'} drives an M1.6 × 0.35 leadscrew through a purchased ${F.gear ? `${F.gear.motor} T : ${F.gear.screw} T` : ''} brass gear pair. One step is ${esc(F.uPerStep ?? 'n/a')} U.`, k: 'Drive' },
    { id: 'dock', img: sDock, n: '03', t: 'A dock that adapts', p: 'The needle, the snap arms and the magnet seat live in one swappable insert on a frozen pod interface. A hall sensor reads the magnet, so a pod that is not docked cannot deliver forward.', k: 'Dock' },
    { id: 'sensing', img: sPlan, n: '04', t: 'It checks its own work', p: 'An angle sensor on the leadscrew magnet verifies every revolution and detects stalls. The same board carries the dock sensor and one flat cable to the controller.', k: 'Sensing' },
  ];

  const partsRows = (P ?? []).map((p) => `<tr data-lock="${esc(p.no)}"><th scope="row" class="num">${esc(p.no)}</th><td>${esc(p.fn)}</td><td>${esc(p.partPlain.split('(')[0].trim())}</td><td><span class="badge st-${p.statusKey}">${p.statusKey === 'locked' ? 'Locked' : p.statusKey === 'sample' ? 'Lock after sample' : 'Candidate'}</span></td><td data-model-for="${esc(p.no)}"><span class="muted">no 3D model yet</span></td></tr>`).join('');
  const envRows = F.sizes.map((s) => `<tr><th scope="row">${esc(s.id)}</th><td class="num">${esc(s.ml)} ml</td><td class="num">${f1(s.l)} × ${f1(s.w)} × ${f1(s.h)}</td><td class="num">${s.volume.toFixed(1)}</td><td>${esc(s.source)}</td></tr>`).join('') + (F.dash ? `<tr><th scope="row">Omnipod DASH</th><td class="num">2.0 ml</td><td class="num">${f1(F.dash.l)} × ${f1(F.dash.w)} × ${f1(F.dash.h)}</td><td class="num">${F.dash.volume.toFixed(1)}</td><td>reference</td></tr>` : '');

  return `
<section class="pagehero" aria-labelledby="h1">
  <div class="wrap pagehero-copy">
    <p class="eyebrow">Product</p>
    <h1 id="h1">${h ? `${f1(h.h)} millimetres<br>of pump.` : 'The pod.'}</h1>
    <p class="lede">${h && F.dash ? `The ${esc(h.id)} is ${f1(h.l)} × ${f1(h.w)} mm, ${F.volPct}% of the volume of an Omnipod DASH.` : ''} One housing, three lengths: ${F.sizes.map((s) => `${s.units} U`).join(', ')}.</p>
  </div>
  <div class="wrap hero-stage">${stage(turntable ?? exploded, root, { alt: 'OP-100 exploded view', sizes: '(min-width: 1240px) 1160px, 100vw', eager: true, cls: 'hero-img' })}</div>
</section>

<section class="wrap block" aria-labelledby="sz">
  <div class="split2">
    <div><p class="eyebrow">Size</p><h2 id="sz">Built around a 16&nbsp;×&nbsp;5&nbsp;mm reservoir.</h2>
    <p>Three lengths share one width and one height. Everything else (motor, gears, board, dock) is identical, so only the reservoir and the housing grow.</p>
    <details class="tech"><summary>Envelope table</summary><div class="tablewrap" role="region" aria-label="Envelope table" tabindex="0"><table><thead><tr><th scope="col">Size</th><th scope="col">Reservoir</th><th scope="col">L × W × H, mm</th><th scope="col">Box, cm³</th><th scope="col">Source</th></tr></thead><tbody>${envRows}</tbody></table></div></details></div>
    <div>${sizeFigure(F)}</div>
  </div>
</section>

<section class="story" data-story aria-label="How the pod works">
  <div class="wrap story-head"><p class="eyebrow">Inside</p><h2>Four things that matter.</h2></div>
  <div class="wrap story-grid">
    <div class="story-stage" aria-hidden="false"><div class="stage-sticky">
      ${chapters.map((c, i) => `<div class="story-img${i === 0 ? ' on' : ''}" data-i="${i}">${stage(c.img, root, { alt: c.img?.title ?? c.t, sizes: '(min-width: 900px) 700px, 100vw', label: 'Render pending' })}</div>`).join('')}
    </div></div>
    <ol class="story-chapters">
      ${chapters.map((c, i) => `<li class="chapter${i === 0 ? ' on' : ''}" id="${c.id}" data-i="${i}"><p class="chnum num">${c.n} · ${esc(c.k)}</p><h3>${esc(c.t)}</h3><p>${c.p}</p></li>`).join('')}
    </ol>
  </div>
</section>

<section class="wrap block" aria-labelledby="v-h">
  <p class="eyebrow">3D</p>
  <h2 id="v-h">Take it apart yourself.</h2>
  <p class="lede sm">Explode the pod, pick a part, read its data. Switch to the component library for the bought-in parts modelled from vendor drawings.</p>
  <div class="viewer" data-viewer data-manifest="${root}models/manifest.json" data-root="${root}">
    <div class="viewer-stage">
      <canvas class="viewer-canvas" hidden tabindex="0" aria-label="3D view of the pod. Use arrow keys to orbit, plus and minus to zoom. Parts can also be chosen from the list."></canvas>
      <div class="viewer-labels" aria-hidden="false"></div>
      <p class="viewer-note">NOT A MEDICAL DEVICE · NEVER ON A PERSON OR ANIMAL · NO INSULIN OR DRUGS · WATER BENCH TESTS ONLY</p>
      <div class="viewer-placeholder">
        <p class="vp-title">OP-100 exploded view</p>
        <p class="muted">Loads three.js${mb ? ` and ${mb} of meshes` : ' and the meshes'} on request. Nothing is loaded until you press the button.</p>
        <button type="button" class="btn primary viewer-start">Load 3D model</button>
        <p class="viewer-status" role="status" aria-live="polite"></p>
      </div>
    </div>
    <div class="viewer-panel" hidden>
      <fieldset class="mode-pick" hidden><legend>View</legend>
        <label><input type="radio" name="vmode" value="pod" checked /> Pod (generated CAD)</label>
        <label><input type="radio" name="vmode" value="library" /> Component library</label>
      </fieldset>
      <fieldset class="size-pick"><legend>Size</legend>
        <label><input type="radio" name="vsize" value="70" /> OP-70</label>
        <label><input type="radio" name="vsize" value="100" checked /> OP-100</label>
        <label><input type="radio" name="vsize" value="200" /> OP-200</label>
      </fieldset>
      <label class="range">Explode <input type="range" min="0" max="100" value="55" class="explode" aria-label="Explode distance" /></label>
      <label class="check"><input type="checkbox" class="show-labels" checked /> Part labels</label>
      <h3>Parts</h3>
      <ul class="partlist"></ul>
      <div class="partinfo" aria-live="polite"><p class="muted">Select a part to see its data.</p></div>
    </div>
  </div>
  <p class="note viewer-source" data-viewer-source>Model source: generated CAD (mechanical/out). When a vendor-accurate component catalogue or an assembly glTF exists at build time, the viewer uses them.</p>
</section>

${comps.length ? `<section class="wrap block" aria-labelledby="lib-h">
  <p class="eyebrow">Component library</p>
  <h2 id="lib-h">${comps.length} bought-in parts, modelled.</h2>
  <p class="lede sm">Motor, gears, magnets, ICs, connectors and boards, drawn from vendor datasheets with a confidence level each. Open them in the 3D viewer above.</p>
  <ul class="compgrid">${comps.slice(0, 24).map((g) => `<li><div class="compimg">${themed(g, root, { alt: g.title, sizes: '(min-width: 900px) 200px, 45vw' })}</div><p class="ct">${esc(g.title)}</p>${g.extra?.mm ? `<p class="cs num">${g.extra.mm.map((x) => f1(x)).join(' × ')} mm</p>` : ''}</li>`).join('')}</ul>
  ${comps.length > 24 ? `<p class="note">${comps.length - 24} more in the 3D library view.</p>` : ''}
</section>` : ''}

<section class="wrap block" aria-labelledby="bom-h">
  <h2 id="bom-h" class="h-sm">Details</h2>
  <details class="tech"><summary>Bought-in parts and 3D model coverage</summary>
    <p class="muted">Rows come from the <a href="${root}docs/parts-lock/">parts lock list</a>. The last column fills in when a 3D model for the part exists in the build. Prices and sources are on <a href="${root}parts/">Parts and cost</a>.</p>
    <div class="tablewrap" role="region" aria-label="Parts and model coverage" tabindex="0"><table><thead><tr><th scope="col">#</th><th scope="col">Function</th><th scope="col">Chosen part</th><th scope="col">Status</th><th scope="col">3D model</th></tr></thead><tbody>${partsRows}</tbody></table></div>
  </details>
  <details class="tech"><summary>Annotated top view (CAD snapshot)</summary>
    <figure class="fig wide"><img class="paper" src="${root}figures/OP-100_layout_annotated.svg" width="838" height="810" alt="Annotated top view of the OP-100 bench pod showing motor, gearbox, gear pair, leadscrew, carriage, reservoir, end cap, cannula dock, sensor board and cable exit, numbered 1 to 15." loading="lazy" />
    <figcaption>Produced by <code>mechanical/annotate.py</code> from the CAD. Check <code>mechanical/check.py --variant bench</code> output on the <a href="${root}status/">status page</a> before relying on it.</figcaption></figure>
  </details>
  <details class="tech"><summary>How the models get here</summary>
    <p>Shell and printed parts come from <code>mechanical/generate.py</code>. Vendor-accurate component models are catalogued in <code>mechanical/components/catalog.json</code>. The site build converts whatever exists; see <a href="${blobUrl('site/README.md')}">site/README.md</a> for the regeneration steps.</p>
  </details>
</section>`;
}
