// Safety, Fault-code explorer and Status board.
import { blobUrl, esc, inline, plain, read, section, slug, tables } from './lib.mjs';
import { docUrl } from './docs.mjs';
import { SEVERITY } from './data.mjs';

const LAYER_NAMES = { 1: 'Controller board', 2: 'Pod sensor board', 3: 'Cables', 4: 'Drive mechanics', 5: 'Fluid path', 6: 'Sensing channels', 7: 'Firmware', 8: 'Protocol', 9: 'Phone app', A: 'Power', B: 'Environment' };

// ------------------------------------------------------------------------------------ SAFETY
function gateSvg() {
  // Fixed geometry; JS toggles the "on" class of elements by data-net. Without JS the diagram shows the default (all off).
  return `<svg class="gate" viewBox="0 0 600 270" role="img" aria-labelledby="gt gd">
<title id="gt">Interlock logic diagram</title>
<desc id="gd">Docked or reverse direction feed an OR gate. Its output, the motor enable from the microcontroller, and the watchdog latch feed a three-input AND gate. The AND output switches the motor supply for the stepper driver.</desc>
<g class="in"><text x="8" y="40">DOCKED</text><text x="8" y="90">DIR_REV</text><text x="8" y="160">MCU_EN</text><text x="8" y="230">WDT latch</text></g>
<path class="w" data-net="docked" d="M92 36H150"/><path class="w" data-net="rev" d="M92 86H150"/>
<path class="gatebox" d="M150 22h44q36 0 46 30 -10 30 -46 30h-44q16 -30 0 -60z"/><text class="gl" x="176" y="56">OR</text>
<path class="w" data-net="or" d="M240 52H300V120H330"/>
<path class="w" data-net="mcu" d="M92 156H330"/>
<path class="w" data-net="latch" d="M92 226H300V196H330"/>
<path class="gatebox" d="M330 100h40q48 0 48 56t-48 56h-40z"/><text class="gl" x="350" y="162">AND</text>
<path class="w" data-net="out" d="M418 156H470"/>
<rect class="box" x="470" y="130" width="124" height="52" rx="3"/><text class="gl" x="532" y="152" text-anchor="middle">VMOT switch</text><text class="sub" x="532" y="170" text-anchor="middle" data-out-text>OFF</text>
<text class="sub" x="330" y="256">MOT_ALLOW = latch AND MCU_EN AND (DOCKED OR DIR_REV)</text>
</svg>`;
}

export function safety(ctx) {
  const { root, reg } = ctx;
  const d = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); };
  const diag = read('docs/06-diagnostics.md') ?? '';
  const safe = read('docs/02-safety.md') ?? '';
  const tb = tables(diag);
  const layerT = tb.find((t) => /^layer$/i.test(plain(t.headers[0])) && /^what$/i.test(plain(t.headers[1] ?? '')));
  const hwT = tb.find((t) => /hardware alone/i.test(t.headers[1] ?? ''));
  const traceT = tb.find((t) => /^hazard$/i.test(plain(t.headers[0])) && /^codes$/i.test(plain(t.headers[1] ?? '')));
  const hazT = tables(safe).find((t) => /hazard/i.test(t.headers[1] ?? '') && /countermeasure/i.test(t.headers[3] ?? ''));
  const hid = (s) => /^(H\d+)/.exec(plain(s))?.[1];
  const H = new Map();
  for (const r of hazT?.rows ?? []) H.set(hid(r[0]) ?? plain(r[0]).replace(/\W/g, ''), { id: plain(r[0]).replace(/\W/g, ''), title: plain(r[1]), cause: r[2], counter: r[3] });
  for (const r of hwT?.rows ?? []) { const id = hid(r[0]); if (!id) continue; const h = H.get(id) ?? { id, title: plain(r[0]).replace(/^H\d+\s*/, '') }; Object.assign(h, { hw: r[1], hwDoes: r[2], fwAdds: r[3], cover: r[4] }); H.set(id, h); }
  for (const r of traceT?.rows ?? []) { const id = hid(r[0]); if (!id) continue; const h = H.get(id) ?? { id, title: plain(r[0]).replace(/^H\d+\s*/, '') }; Object.assign(h, { codes: r[1], tests: r[2], accept: r[3] }); H.set(id, h); }
  const hazards = [...H.values()].sort((a, b) => +a.id.slice(1) - +b.id.slice(1));

  const layers = (layerT?.rows ?? []).map((r) => `<li class="layer"><div class="lh"><span class="lid num">${esc(plain(r[0]).split(' ')[0])}</span><strong>${esc(plain(r[0]).replace(/^L\d\s*/, '').replace(/ \(this document\)/, ''))}</strong></div><dl><div><dt>What</dt><dd>${inline(r[1])}</dd></div><div><dt>Independent of</dt><dd>${inline(r[2])}</dd></div><div><dt>If it trips</dt><dd>${inline(r[3])}</dd></div></dl></li>`).reverse().join('');

  const rows = [];
  for (let i = 0; i < 16; i++) {
    const docked = !!(i & 1), rev = !!(i & 2), mcu = !!(i & 4), latch = !!(i & 8);
    const out = latch && mcu && (docked || rev);
    let why = '';
    if (!latch) why = 'Latch cleared: watchdog not serviced, over-current, or power-up';
    else if (!mcu) why = 'Firmware has not enabled the motor';
    else if (!docked && !rev) why = 'Undocked, direction forward: no forward motion off the cannula';
    else if (docked && !rev) why = 'Normal delivery';
    else if (!docked && rev) why = 'Draw mode: refill, pod undocked';
    else why = 'Docked, reverse';
    rows.push(`<tr data-row="${i}" class="${out ? 'on' : ''}"><td class="num">${mcu ? 1 : 0}</td><td class="num">${latch ? 1 : 0}</td><td class="num">${docked ? 1 : 0}</td><td class="num">${rev ? 1 : 0}</td><th scope="row" class="num out ${out ? 'yes' : 'no'}">${out ? 'MOTOR ON' : 'off'}</th><td>${why}</td></tr>`);
  }

  const limitsMd = section(read('spec/design-parameters.md') ?? '', /^7\.\s*Safety limits/);
  const bench = section(safe, /^3\.\s*Bench verification/);
  const gaps = section(diag, /^1\.5/);

  return `
<header class="pagehead">
  <p class="kicker">Safety architecture</p>
  <h1>Safety: what stops the motor, and who checks that it can</h1>
  <p class="lede">The design rule: if the software is wrong, the hardware is still right, and the software continuously proves that the hardware can still do its job. Nothing here makes on-body use acceptable. It exists so that bench tests are meaningful and the engineering is done properly.</p>
</header>

<div class="callout warn" role="note"><p><strong>Design intent, not verified hardware.</strong> The interlock is designed and modelled; the current board changes are not yet verified (no DRC report, no oscilloscope measurement of the watchdog bound). See <a href="${root}status/">status</a>. Source documents: <a href="${d('docs/02-safety.md')}">02-safety</a>, <a href="${d('docs/06-diagnostics.md')}">06-diagnostics</a>, <a href="${d('spec/design-parameters.md')}">spec section 7 and 7a</a>.</p></div>

<section aria-labelledby="il-h">
  <h2 id="il-h">1. Hardware interlock: try it</h2>
  <p>The motor supply is switched by a P-FET that only closes when all of these hold. Toggle the inputs to see the result. All gates default to <em>off</em> (pull-downs, a missing cable reads "not docked").</p>
  <div class="sim" data-sim>
    <fieldset class="sim-inputs"><legend>Inputs</legend>
      <label><input type="checkbox" data-in="mcu" /> <span><code>MCU_EN</code> firmware enables the motor</span></label>
      <label><input type="checkbox" data-in="latch" /> <span><code>WDT latch</code> TPL5010 watchdog serviced, latch armed</span></label>
      <label><input type="checkbox" data-in="docked" /> <span><code>DOCKED</code> hall sensor sees the cannula magnet</span></label>
      <label><input type="checkbox" data-in="rev" /> <span><code>DIR_REV</code> direction is reverse (draw)</span></label>
    </fieldset>
    ${gateSvg()}
    <p class="sim-result" role="status" aria-live="polite" data-sim-result><strong>Motor supply: OFF.</strong> <span data-sim-why></span></p>
  </div>
  <div class="tablewrap" role="region" aria-label="Interlock truth table" tabindex="0"><table class="truth">
    <caption>Complete truth table (16 rows). The highlighted row follows the toggles above. Motor runs in ${rows.filter((r) => r.includes('MOTOR ON')).length} of 16 rows; <strong>no row with the latch cleared, firmware disabled, or undocked-forward runs it</strong>.</caption>
    <thead><tr><th scope="col">MCU_EN</th><th scope="col">WDT latch</th><th scope="col">DOCKED</th><th scope="col">DIR_REV</th><th scope="col">VMOT</th><th scope="col">Meaning</th></tr></thead><tbody>${rows.join('')}</tbody></table></div>
  <h3>How the watchdog fits in</h3>
  <ul class="plain">
    <li>The external TPL5010 (about 2 s) is serviced only by the safety task, as the last step of a verified tick. If the firmware hangs, the TPL5010 resets the MCU <em>and</em> clears the latch, so the motor supply is cut without any software.</li>
    <li>Hardware step budget (decided 2026-11-19, not built yet): an arm window and pulse budget in discrete logic bound a runaway inside the watchdog window to about 1.6 U. Without it, hardware alone does not bound the dose inside one window, so the dose limit is a software limit (see section 4).</li>
    <li>Firmware proves at runtime that each gate can still cut the supply (rotating single-gate disarm). A proven-stuck gate latches the pod: <strong>no delivery with a degraded protection layer</strong>.</li>
  </ul>
  <p class="note">Older text in <a href="${d('docs/02-safety.md')}">02-safety section 2</a> shows only two enables; the definition above (spec 7a, diagnostics 1.1) is current. The reverse-direction exception exists so that draw-mode refill works undocked. The polarity of <code>DIR_REV</code> is an unverified assumption with its own fault code (<a href="${root}faults/#q=4-40-003">4-40-003</a>).</p>
</section>

<section aria-labelledby="layers-h">
  <h2 id="layers-h">2. Defence in depth</h2>
  <p>Six layers, outermost first. Each is independent of the one above it, and none relies on the layer above for its own function.</p>
  <ol class="layers">${layers || '<li>Layer table not found in docs/06-diagnostics.md</li>'}</ol>
</section>

<section aria-labelledby="haz-h">
  <h2 id="haz-h">3. Hazard explorer</h2>
  <p>Pick a hazard to see what hardware does alone, what firmware must add, and which fault codes and tests close it.</p>
  <div class="hazard" data-hazards>
    <div class="haz-pick" role="group" aria-label="Hazards">${hazards.map((h, i) => `<button type="button" class="chip" data-haz="${h.id}" aria-pressed="${i === 0}">${h.id}</button>`).join('')}</div>
    ${hazards.map((h, i) => `<article class="haz-card" data-haz-card="${h.id}" ${i ? 'hidden' : ''}>
      <h3>${h.id} ${esc(h.title)}</h3>
      <dl>
        ${h.cause ? `<div><dt>Cause</dt><dd>${inline(h.cause)}</dd></div>` : ''}
        ${h.counter ? `<div><dt>Countermeasures</dt><dd>${inline(h.counter)}</dd></div>` : ''}
        ${h.hw ? `<div><dt>Covered by hardware alone?</dt><dd><strong>${inline(h.hw)}</strong>. ${inline(h.hwDoes ?? '')}</dd></div>` : ''}
        ${h.fwAdds ? `<div><dt>Firmware must add</dt><dd>${inline(h.fwAdds)}</dd></div>` : ''}
        ${h.codes ? `<div><dt>Fault codes</dt><dd>${(h.codes.match(/`[^`]+`/g) ?? []).map((c) => { const q = c.replace(/`/g, '').replace(/[*/].*$/, '').replace(/\.\..*$/, ''); return `<a class="codechip" href="${root}faults/#q=${encodeURIComponent(q)}">${esc(c.replace(/`/g, ''))}</a>`; }).join(' ')}</dd></div>` : ''}
        ${h.tests ? `<div><dt>Tests</dt><dd>${inline(h.tests)}</dd></div>` : ''}
        ${h.accept ? `<div><dt>Acceptance</dt><dd>${inline(h.accept)}</dd></div>` : ''}
      </dl></article>`).join('')}
  </div>
</section>

<section aria-labelledby="lim-h">
  <h2 id="lim-h">4. Dose limits (software, separate task)</h2>
  <p>These are enforced by the safety supervisor, which approves every motor step and is separate from the delivery engine. The delivery engine cannot step the motor itself.</p>
  <div class="md">${ctx.md(limitsMd)}</div>
  ${gaps ? `<p class="note"><strong>Known gap.</strong> ${esc(plain(gaps).split('. ').slice(0, 3).join('. '))}. Full text: <a href="${d('docs/06-diagnostics.md')}#${slug('1.5 Residual gap and recommended hardware additions (decision needed)')}">diagnostics 1.5</a>.</p>` : ''}
</section>

<section aria-labelledby="bench-h">
  <h2 id="bench-h">5. Bench verification plan</h2>
  <p>Water only, into containers. Never insulin or any drug, never a person. There is no step beyond the bench.</p>
  <div class="md">${bench ? (ctx.md(bench)) : ''}</div>
</section>`;
}

// ------------------------------------------------------------------------------------ FAULTS
export function faults(ctx) {
  const { root, data, reg } = ctx;
  const d = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); };
  if (!data) {
    return `<header class="pagehead"><p class="kicker">Fault codes</p><h1>Fault code explorer</h1></header><div class="callout warn"><p>docs/06-diagnostics.md was not found at build time, so the catalogue could not be generated.</p></div>`;
  }
  const layers = [...new Set(data.codes.map((c) => c.layer))];
  const frus = [...new Set(data.codes.map((c) => c.fru))].filter(Boolean).sort();
  const sevChips = Object.entries(SEVERITY).map(([k, v]) => `<button type="button" class="chip sev-${k}" data-sev="${k}" aria-pressed="false"><span class="sevmark" aria-hidden="true">${k}</span> ${v.label} <span class="num">${data.counts[k]}</span></button>`).join('');
  const cards = data.codes.map((c) => {
    const text = `${c.code} ${c.name} ${c.component} ${c.layerShort} ${c.layerName} ${c.fru} ${c.fruName} ${c.action} ${c.trio} ${c.detection} ${c.hazards}`.toLowerCase();
    return `<details class="fault sev-${c.sev}" id="c-${c.code}" data-sev="${c.sev}" data-layer="${c.layer}" data-fru="${esc(c.fru)}" data-text="${esc(text)}">
<summary><span class="code num">${c.code}</span><span class="fname">${esc(c.name)}</span><span class="sev"><span class="sevmark" aria-hidden="true">${c.sev}</span>${SEVERITY[c.sev]?.label ?? c.sev}</span><span class="fruline"><span class="muted">Part:</span> ${esc(c.fruName || c.fruText)}</span></summary>
<div class="fbody">
  ${c.trio ? `<p class="trio"><span class="muted">Trio shows:</span> “${esc(c.trio)}”</p>` : ''}
  <dl>
    <div><dt>Component</dt><dd>${esc(LAYER_NAMES[c.layer] ?? c.layerName)} / ${esc(c.component || c.comp)}${c.refs ? ` <span class="muted">(${esc(c.refs)})</span>` : ''}</dd></div>
    <div><dt>Replaceable part (FRU)</dt><dd>${esc(c.fruText)}${c.fruName ? `: ${esc(c.fruName)}` : ''}</dd></div>
    <div><dt>Recommended action</dt><dd><code>${esc(c.action || 'NONE')}</code>${c.actionText ? ` ${esc(c.actionText)}` : ''}</dd></div>
    <div><dt>Detected when</dt><dd>${esc(c.detection)}</dd></div>
    <div><dt>Detected by</dt><dd>${esc(c.by)}</dd></div>
    <div><dt>Hazards</dt><dd>${esc(c.hazards)}</dd></div>
    <div><dt>Tests</dt><dd>${esc(c.tests)}</dd></div>
    <div><dt>Severity</dt><dd>${SEVERITY[c.sev]?.text ?? ''}</dd></div>
  </dl>
  <p><a href="#c-${c.code}">Link to this code</a></p>
</div></details>`;
  }).join('\n');
  return `
<header class="pagehead">
  <p class="kicker">Fault codes</p>
  <h1>Fault code explorer</h1>
  <p class="lede">Every anomaly in every layer gets a 32-bit code: layer, component, fault, instance. Each code says how serious it is, <strong>which part to replace</strong>, what to do, and what Trio would show. ${data.total} codes, generated from <a href="${d('docs/06-diagnostics.md')}">docs/06-diagnostics.md</a>.</p>
</header>
<div class="callout" role="note"><p>This is a <strong>design catalogue</strong>. Most codes are not implemented in firmware yet, and none has been exercised on hardware. Notation: <code>L-CC-FFF</code> in hex, for example <code>1-06-001</code> is layer 1 (controller board), component 06 (motor supply switch), fault 001.</p></div>

<section class="explorer" data-explorer aria-label="Fault code search">
  <div class="controls">
    <div class="field"><label for="q">Search code, name, component, part or Trio text</label><input id="q" type="search" autocomplete="off" spellcheck="false" placeholder="for example 1-06, watchdog, motor, replace" /></div>
    <div class="field"><label for="layer">Layer</label><select id="layer"><option value="">All layers</option>${layers.map((l) => `<option value="${l}">${l}: ${esc(LAYER_NAMES[l] ?? l)}</option>`).join('')}</select></div>
    <div class="field"><label for="fru">Replaceable part</label><select id="fru"><option value="">All parts</option>${frus.map((f) => `<option value="${esc(f)}">${esc(f)}${data.frus[f] ? `: ${esc(data.frus[f].name)}` : ''}</option>`).join('')}</select></div>
  </div>
  <div class="chips" role="group" aria-label="Severity filter">${sevChips}<button type="button" class="linkbtn" data-reset>Reset filters</button><button type="button" class="linkbtn" data-expand>Expand all</button></div>
  <p class="count" role="status" aria-live="polite" data-count>${data.total} of ${data.total} codes shown</p>
  <div class="faultlist">${cards}</div>
  <p class="empty" data-empty hidden>No code matches. Try fewer words or reset the filters.</p>
</section>

<section aria-labelledby="leg-h">
  <h2 id="leg-h">Legend</h2>
  <div class="tablewrap" role="region" aria-label="Severity levels" tabindex="0"><table>
    <caption>Severity levels</caption><thead><tr><th scope="col">Sev</th><th scope="col">Name</th><th scope="col">Behaviour</th></tr></thead>
    <tbody>${Object.entries(SEVERITY).map(([k, v]) => `<tr><th scope="row" class="num">${k}</th><td>${v.label}</td><td>${esc(v.text)}</td></tr>`).join('')}</tbody></table></div>
  <div class="tablewrap" role="region" aria-label="Replaceable parts" tabindex="0"><table>
    <caption>Replaceable parts (FRU)</caption><thead><tr><th scope="col">Id</th><th scope="col">Part</th><th scope="col">Rev A bench content</th></tr></thead>
    <tbody>${Object.values(data.frus).map((f) => `<tr><th scope="row" class="num">${esc(f.short)}</th><td>${esc(f.name)}</td><td>${esc(f.content)}</td></tr>`).join('')}</tbody></table></div>
</section>`;
}

// ------------------------------------------------------------------------------------ STATUS
const CLS = { verified: ['Evidence given', 'ok'], partial: ['Partly verified', 'mid'], unverified: ['Not verified', 'bad'] };
export function status(ctx) {
  const { root, data, reg, git } = ctx;
  const d = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); };
  if (!data) return `<header class="pagehead"><h1>Status</h1></header><div class="callout warn"><p>docs/STATUS.md not found at build time.</p></div>`;
  const card = (r) => { const [lab, k] = CLS[r.cls]; return `<article class="card"><header><h3>${esc(r.area)}</h3><span class="badge v-${k}">${lab}</span></header><dl><div><dt>State</dt><dd>${inline(r.state)}</dd></div><div><dt>Verified</dt><dd>${inline(r.verified)}</dd></div>${r.next ? `<div><dt>Next</dt><dd>${inline(r.next)}</dd></div>` : ''}</dl></article>`; };
  const tally = ['verified', 'partial', 'unverified'].map((k) => `${data.handoff.filter((r) => r.cls === k).length} ${CLS[k][0].toLowerCase()}`).join(', ');
  return `
<header class="pagehead">
  <p class="kicker">Status board</p>
  <h1>What is verified, and what is not</h1>
  <p class="lede">Generated from <a href="${d('docs/STATUS.md')}">docs/STATUS.md</a> (last updated ${esc(data.updated)}) at commit <span class="num">${esc(git.sha)}</span>. The badge is a keyword reading of the "Verified" text, not a judgement: always read the evidence.</p>
</header>
${data.warnings.map((w) => `<div class="callout warn" role="note"><p><strong>Open decision.</strong> ${inline(w.replace(/^Gear-ratio mismatch to resolve first:\s*/, 'Gear ratio: '))}</p></div>`).join('')}
<section aria-labelledby="arch-h"><h2 id="arch-h">Current architecture (decided)</h2><p>${inline(data.architecture)}</p></section>
<section aria-labelledby="ho-h"><h2 id="ho-h">State at handoff</h2><p class="muted">${esc(tally)} of ${data.handoff.length} areas.</p><div class="cards">${data.handoff.map(card).join('')}</div></section>
<section aria-labelledby="pa-h"><h2 id="pa-h">Status per subproject</h2><div class="cards">${data.perArea.map(card).join('')}</div></section>
<section aria-labelledby="ns-h"><h2 id="ns-h">Next steps, in order</h2><ol class="steps">${data.nextSteps.map((s) => `<li>${inline(s)}</li>`).join('')}</ol></section>
<section aria-labelledby="dl-h"><h2 id="dl-h">Decision log</h2><ul class="decisions">${data.decisions.map((s) => `<li>${inline(s)}</li>`).join('')}</ul></section>`;
}
