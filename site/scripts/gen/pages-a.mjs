// Overview (datasheet front page), Design and Licence pages.
import { blobUrl, esc, REPO_URL } from './lib.mjs';
import { docUrl } from './docs.mjs';

const f1 = (n) => (Math.round(n * 10) / 10).toString();

/** Dimension line helpers (SVG, drawn in mm * scale). */
function hDim(x1, x2, y, label) {
  return `<g class="dim"><line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}"/><line x1="${x1}" y1="${y - 5}" x2="${x1}" y2="${y + 5}"/><line x1="${x2}" y1="${y - 5}" x2="${x2}" y2="${y + 5}"/><text x="${(x1 + x2) / 2}" y="${y + 15}" text-anchor="middle">${label}</text></g>`;
}
function vDim(x, y1, y2, label) {
  return `<g class="dim"><line x1="${x}" y1="${y1}" x2="${x}" y2="${y2}"/><line x1="${x - 5}" y1="${y1}" x2="${x + 5}" y2="${y1}"/><line x1="${x - 5}" y1="${y2}" x2="${x + 5}" y2="${y2}"/><text x="${x + 9}" y="${(y1 + y2) / 2 + 4}">${label}</text></g>`;
}

export function envelopeFigure(spec) {
  const dash = /(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)/.exec(spec.envelope.find((e) => e.dash)?.dash ?? '');
  const shapes = [...(dash ? [{ name: 'Omnipod DASH', l: +dash[1], w: +dash[2], h: +dash[3], ref: true }] : []), ...spec.envelope.filter((e) => e.l).map((e) => ({ name: e.size, l: e.l, w: e.w, h: e.h }))].sort((a, b) => b.w - a.w || b.l - a.l);
  const S = 5.2;
  let y = 14;
  let plan = '';
  const maxL = Math.max(...shapes.map((s) => s.l));
  for (const s of shapes) {
    const w = s.l * S, h = s.w * S;
    plan += `<g><rect class="${s.ref ? 'shape ref' : 'shape'}" x="30" y="${y}" width="${w}" height="${h}" rx="${(s.ref ? 7 : 4) * S}" ${s.ref ? 'stroke-dasharray="6 4"' : ''}/><text class="lbl" x="${30 + w / 2}" y="${y + h / 2 + 4}" text-anchor="middle">${esc(s.name)}</text>${hDim(30, 30 + w, y + h + 12, `${f1(s.l)} mm`)}${vDim(30 + w + 12, y, y + h, `${f1(s.w)}`)}</g>`;
    y += h + 44;
  }
  // side profile
  let side = '';
  let sy = y + 6;
  for (const s of shapes) {
    const w = s.l * S, h = s.h * S;
    side += `<g><rect class="${s.ref ? 'shape ref' : 'shape'}" x="30" y="${sy}" width="${w}" height="${h}" rx="3" ${s.ref ? 'stroke-dasharray="6 4"' : ''}/><text class="lbl" x="${30 + w + 24}" y="${sy + h / 2 + 4}">${esc(s.name)}</text>${vDim(30 + w + 10, sy, sy + h, '')}<text class="dimv" x="${30 + w + 24}" y="${sy + h / 2 + 18}">${f1(s.h)} mm</text></g>`;
    sy += h + 22;
  }
  const W = 30 + maxL * S + 120;
  return `<figure class="fig"><svg viewBox="0 0 ${Math.ceil(W)} ${Math.ceil(sy)}" role="img" aria-labelledby="envt envd" class="drawing">
<title id="envt">Pod envelopes to scale: plan view and side profile</title>
<desc id="envd">${shapes.map((s) => `${s.name} ${f1(s.l)} by ${f1(s.w)} by ${f1(s.h)} millimetres`).join('; ')}.</desc>
<text class="cap" x="30" y="10">PLAN VIEW (top), 5.2 px per mm</text>${plan}
<text class="cap" x="30" y="${y - 2}">SIDE PROFILE (same scale)</text>${side}</svg>
<figcaption>Envelopes from <a href="${blobUrl('spec/design-parameters.md')}">spec section 2</a>, drawn to scale. Dashed outline: Omnipod DASH, for comparison only.</figcaption></figure>`;
}

function row(a, b, c) { return `<tr><th scope="row">${a}</th><td class="num">${b}</td><td>${c}</td></tr>`; }

export function overview(ctx) {
  const { spec, status, faults, root, reg } = ctx;
  const doc = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); };
  const area = spec.area;
  const uBase = (0.35 / (20 * 26.45)) * (area / 10);
  const opts = [{ name: '18 : 18 (1 : 1)', r: 1, note: 'CAD snapshot, architecture study recommendation' }, { name: '15 : 12', r: 12 / 15, note: 'spec section 4, firmware default feature' }];
  const gearRows = opts.map((o) => { const u = uBase / o.r; return `<tr><th scope="row">${o.name}</th><td class="num">${u.toFixed(5)}</td><td class="num">${(0.05 / u).toFixed(1)}</td><td>${o.note}</td></tr>`; }).join('');
  const limits = spec.limits.map((l) => `<tr><th scope="row">${esc(l.name)}</th><td class="val">${l.value ? esc(l.value) : '(stated in the name)'}</td></tr>`).join('');
  const mismatch = status?.warnings?.[0] ? `<div class="callout warn" role="note"><p><strong>Open decision.</strong> ${esc(status.warnings[0].replace(/`/g, '').replace(/\*\*/g, '').replace(/^Gear-ratio mismatch to resolve first:\s*/, 'Gear ratio: '))}</p></div>` : '';
  const counts = faults ? `${faults.total} fault codes (${faults.counts.I} info, ${faults.counts.W} warning, ${faults.counts.F} fault, ${faults.counts.L} latched)` : 'fault catalogue not found at build time';
  const envRows = spec.envelope.map((e) => `<tr><th scope="row">${esc(e.size)}</th><td class="num">${esc(e.volume)}</td><td class="num">${f1(e.l)} × ${f1(e.w)} × ${f1(e.h)}</td><td class="num">${(e.l * e.w * e.h / 1000).toFixed(1)}</td></tr>`).join('');
  const dashM = /(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)/.exec(spec.envelope.find((e) => e.dash)?.dash ?? '');
  const dashVol = dashM ? (dashM[1] * dashM[2] * dashM[3]) / 1000 : null;
  const dashRow = dashM ? `<tr><th scope="row">Omnipod DASH (reference)</th><td class="num">2.00 ml</td><td class="num">${dashM[1]} × ${dashM[2]} × ${dashM[3]}</td><td class="num">${dashVol.toFixed(1)}</td></tr>` : '';
  return `
<header class="pagehead">
  <p class="kicker">Datasheet · Rev A (bench) · generated from the repository</p>
  <h1>OpenPatch: a patch insulin pump, documented in full</h1>
  <p class="lede">An open engineering notebook for a very flat, detachable insulin pump. The goal is not a product. It is a complete, checkable blueprint: every dimension, safety limit, fault code and open question is published, and this site is generated from those documents.</p>
</header>

<section class="danger" aria-labelledby="warn-h">
  <h2 id="warn-h">Test project. Never wear it.</h2>
  <ul>
    <li>OpenPatch is <strong>not a medical device</strong>. No regulator has reviewed it. It has none of the validation a real insulin pump needs.</li>
    <li>Every test is a <strong>bench test</strong>: water only, into a vial, beaker or onto a balance. Never insulin or any drug, never a person or animal.</li>
    <li>Real insulin pumps deliver a drug where errors can kill. If you need a pump, talk to your diabetes care team and use an approved device.</li>
  </ul>
  <p><a href="${doc('DISCLAIMER.md')}">Read the full disclaimer</a></p>
</section>

<section aria-labelledby="goal-h">
  <h2 id="goal-h">What this repository is trying to show</h2>
  <p>A pump is only as trustworthy as its documentation. Big manufacturers keep the safety case, the fault behaviour and the build details private. This project publishes all three, so that others can check the work, copy the parts that are good and point at the parts that are wrong.</p>
  <ul class="plain">
    <li><strong>Safety you can inspect.</strong> A hardware interlock that works with broken firmware, and firmware that proves the interlock still works. <a href="${root}safety/">Safety architecture</a></li>
    <li><strong>Faults that name the part.</strong> ${esc(counts)}, each with severity, field-replaceable part and the text a user would see. <a href="${root}faults/">Fault explorer</a></li>
    <li><strong>Honest status.</strong> What is verified, what is not, and which decisions are still open. <a href="${root}status/">Status board</a></li>
    <li><strong>Buildable on a bench.</strong> Guides, parts lock list and cost model. <a href="${root}build/">Build guides</a></li>
  </ul>
</section>

${mismatch}

<section aria-labelledby="env-h">
  <h2 id="env-h">1. Envelope compared with Omnipod DASH</h2>
  <div class="split">
    <div>
      <div class="tablewrap" role="region" aria-label="Envelope table" tabindex="0"><table>
        <caption>Target envelope per size (spec section 2). Volume column is the bounding box, not the reservoir.</caption>
        <thead><tr><th scope="col">Size</th><th scope="col">Reservoir (U100)</th><th scope="col">L × W × H, mm</th><th scope="col">Box, cm³</th></tr></thead>
        <tbody>${envRows}${dashRow}</tbody></table></div>
      <p class="note">The CAD snapshot of the bench pod is currently 44.9 × 32.0 × 8.5 mm for OP-100 (spec target 42.0). Spec numbers are targets until the mechanics are finished; see <a href="${root}status/">status</a>.</p>
    </div>
    ${envelopeFigure(spec)}
  </div>
</section>

<section aria-labelledby="dose-h">
  <h2 id="dose-h">2. Dose resolution</h2>
  <p>Drive: NFP-608-26.45 geared stepper (20 steps per revolution, ratio 26.45), M1.6 × 0.35 leadscrew, stadium reservoir of ${area.toFixed(1)} mm². One step moves the plunger by 0.35 mm / (20 × 26.45) / gear ratio, and 1 U is 10 mm³ of U100.</p>
  <div class="tablewrap" role="region" aria-label="Dose resolution" tabindex="0"><table>
    <caption>Resolution per gear pair (motor teeth : screw teeth). Computed at build time from spec section 3 and 4.</caption>
    <thead><tr><th scope="col">Gear pair</th><th scope="col">U per step</th><th scope="col">Steps for 0.05 U</th><th scope="col">Where it is used</th></tr></thead>
    <tbody>${gearRows}</tbody></table></div>
  <p class="note"><strong>Not decided yet.</strong> The two documents disagree and the choice changes every dose by 25 %. The decision and its evidence will be recorded in <a href="${doc('docs/STATUS.md')}">STATUS</a> before any hardware is ordered.</p>
</section>

<section aria-labelledby="lim-h">
  <h2 id="lim-h">3. Safety limits (hard-coded upper bounds)</h2>
  <div class="tablewrap" role="region" aria-label="Safety limits" tabindex="0"><table>
    <caption>Firmware defaults from <a href="${doc('spec/design-parameters.md')}">spec section 7</a>. Relaxing any of them requires a decision entry in STATUS.</caption>
    <thead><tr><th scope="col">Limit</th><th scope="col">Value</th></tr></thead><tbody>${limits}</tbody></table></div>
  <p>Beyond these, the hardware bounds a runaway inside one watchdog window; see the <a href="${root}safety/">interlock</a>.</p>
</section>

<section aria-labelledby="cost-h">
  <h2 id="cost-h">4. Cost per pump</h2>
  <p>Planning estimates, not quotes. The full tables (first pump, marginal pump, line items) are on <a href="${root}parts/#cost">Parts and cost</a>.</p>
  <ul class="plain">
    <li>One Rev A bench iteration (controller board, pod board, prints, motor, gears): about <span class="num">130 to 150 USD</span> (cost model).</li>
    <li>The sourcing study finds that a complete first pump does <strong>not</strong> reliably come in under 200 EUR (about 223 to 366 EUR for the recommended build), but an additional pump from the same orders is about <span class="num">65 to 95 EUR</span>.</li>
  </ul>
</section>

<section class="explainer" aria-labelledby="lic-h">
  <h2 id="lic-h">Licence in one minute</h2>
  <p>Free for study, research and bench self-builds (CC BY-NC-SA 4.0 for hardware and docs, PolyForm Noncommercial for software). Anyone who wants to <em>sell</em> it needs a commercial "Fair-Price" licence: price at most unit cost plus 30 %, 5 % of revenue into an open clinical-trial fund, unweakened safety design. The first company that pays for approval and trials is repaid by followers out of their own margin, capped at investment plus 20 %, then the data goes open. Draft, under legal review, source-available rather than open source. <a href="${root}licence/">Read the licence and fair-price model, with a payback calculator</a>.</p>
</section>

<section aria-labelledby="where-h">
  <h2 id="where-h">Where to go next</h2>
  <ul class="linklist">
    <li><a href="${root}design/"><strong>Design</strong></a><span>3D explorer with part numbers, top view, parts that are not modelled yet.</span></li>
    <li><a href="${root}safety/"><strong>Safety</strong></a><span>Interlock simulator, truth table, layers, hazards H1 to H10, bench verification plan.</span></li>
    <li><a href="${root}faults/"><strong>Fault codes</strong></a><span>Search by code, component, severity or replaceable part.</span></li>
    <li><a href="${root}status/"><strong>Status</strong></a><span>Per area: state, evidence, next step. Updated from STATUS.md on every build.</span></li>
    <li><a href="${root}build/"><strong>Build</strong></a><span>From parts order to bench tests.</span></li>
    <li><a href="${root}docs/"><strong>Docs</strong></a><span>Every specification and design note, rendered.</span></li>
  </ul>
</section>`;
}

export function design(ctx) {
  const { root, parts } = ctx;
  const rows = (parts ?? []).map((p) => `<tr data-lock="${esc(p.no)}"><th scope="row" class="num">${esc(p.no)}</th><td>${esc(p.fn)}</td><td>${esc(p.partPlain.split('(')[0].trim())}</td><td><span class="badge st-${p.statusKey}">${p.statusKey === 'locked' ? 'Locked' : p.statusKey === 'sample' ? 'Lock after sample' : 'Candidate'}</span></td><td data-model-for="${esc(p.no)}"><span class="muted">no 3D model yet</span></td></tr>`).join('');
  return `
<header class="pagehead">
  <p class="kicker">Design</p>
  <h1>Mechanical design and 3D explorer</h1>
  <p class="lede">Explode the pod, click a part, read its datasheet entry. The models are generated envelopes for fit and interference checks. They are <strong>not</strong> vendor-accurate yet: motor, gears, sensor board and valves are still to be modelled from the vendor drawings.</p>
</header>

<section aria-labelledby="v-h" class="viewer-section">
  <h2 id="v-h">3D explorer</h2>
  <div class="viewer" data-viewer data-manifest="${root}models/manifest.json" data-root="${root}">
    <div class="viewer-stage">
      <canvas class="viewer-canvas" hidden tabindex="0" aria-label="3D view of the pod. Use arrow keys to orbit, plus and minus to zoom. Parts can also be chosen from the list."></canvas>
      <div class="viewer-labels" aria-hidden="false"></div>
      <p class="viewer-note">NOT A MEDICAL DEVICE · NEVER ON A PERSON OR ANIMAL · NO INSULIN OR DRUGS · WATER BENCH TESTS ONLY</p>
      <div class="viewer-placeholder">
        <p><strong>OP-100 exploded view</strong></p>
        <p class="muted">Loads three.js and about 12 MB of meshes on request. Nothing is loaded until you press the button.</p>
        <button type="button" class="btn viewer-start">Load 3D model</button>
        <p class="viewer-status" role="status" aria-live="polite"></p>
      </div>
    </div>
    <div class="viewer-panel" hidden>
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
  <p class="note viewer-source" data-viewer-source>Model source: generated CAD (mechanical/out). When <code>mechanical/components/catalog.json</code> and an assembly glTF exist at build time, the explorer uses them instead.</p>
</section>

<section aria-labelledby="top-h">
  <h2 id="top-h">Rev A top view (CAD snapshot)</h2>
  <figure class="fig wide">
    <img class="paper" src="${root}figures/OP-100_layout_annotated.svg" width="838" height="810" alt="Annotated top view of the OP-100 bench pod showing motor, gearbox, gear pair, leadscrew, carriage, reservoir, end cap, cannula dock, sensor board and cable exit, numbered 1 to 15." loading="lazy" />
    <figcaption>Produced by <code>mechanical/annotate.py</code> from the CAD. <strong>Unverified</strong>: it uses the 18 : 18 gear pair that the spec does not yet agree with, and <code>check.py --variant bench</code> has to be re-run (see <a href="${root}status/">status</a>).</figcaption>
  </figure>
</section>

<section aria-labelledby="bom-h">
  <h2 id="bom-h">Bought-in parts and model coverage</h2>
  <p>Rows come from the <a href="${root}docs/parts-lock/">parts lock list</a>. The last column fills in when a 3D model for the part exists in the build.</p>
  <div class="tablewrap" role="region" aria-label="Parts and model coverage" tabindex="0"><table>
    <thead><tr><th scope="col">#</th><th scope="col">Function</th><th scope="col">Chosen part</th><th scope="col">Status</th><th scope="col">3D model</th></tr></thead>
    <tbody>${rows}</tbody></table></div>
</section>

<section aria-labelledby="gen-h">
  <h2 id="gen-h">How the models get here</h2>
  <p>Shell and printed parts come from <code>mechanical/generate.py</code> (SolidCraft). Vendor-accurate component models are catalogued in <code>mechanical/components/catalog.json</code> with glTF files, and an assembled pod as glTF. The site build converts and bundles whatever exists; see <a href="${REPO_URL}/blob/main/site/README.md">site/README.md</a> for the regeneration steps.</p>
</section>`;
}
