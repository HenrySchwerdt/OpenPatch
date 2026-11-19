// Build guide index, Parts and cost, Docs index and rendered document pages.
import { blobUrl, esc, inline, read, section } from './lib.mjs';
import { docUrl } from './docs.mjs';

const BADGE = { locked: ['Locked', 'locked'], sample: ['Lock after sample', 'sample'], candidate: ['Candidate', 'candidate'] };

export function parts(ctx) {
  const { root, parts: P, md, reg } = ctx;
  const d = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); };
  const shop = read('docs/SHOPPING.md') ?? '';
  const cost = read('docs/05-cost-model.md') ?? '';
  const rows = (P ?? []).map((p) => { const [lab, k] = BADGE[p.statusKey]; return `<tr data-status="${p.statusKey}"><th scope="row" class="num">${esc(p.no)}</th><td>${esc(p.fn)}</td><td>${inline(p.part)}</td><td>${esc(p.source)}</td><td class="num">${esc(p.price)}</td><td><span class="badge st-${k}">${lab}</span></td><td class="why">${inline(p.why).slice(0, 600)}</td></tr>`; }).join('');
  const n = { locked: 0, sample: 0, candidate: 0 };
  for (const p of P ?? []) n[p.statusKey]++;
  return `
<header class="pagehead">
  <p class="kicker">Parts and cost</p>
  <h1>Bought-in parts and what a pump costs</h1>
  <p class="lede">Every external part, with chosen part, source, price and lock status. Prices are planning estimates until real invoices are logged in the <a href="${d('docs/05-cost-model.md')}">cost model</a>.</p>
</header>
<section aria-labelledby="pl-h">
  <h2 id="pl-h">Parts lock list</h2>
  ${P ? `<p class="muted">${P.length} parts: ${n.locked} locked, ${n.sample} lock after sample, ${n.candidate} candidate. Source: <a href="${d('docs/PARTS-LOCK.md')}">docs/PARTS-LOCK.md</a>.</p>
  <div class="chips" role="group" aria-label="Filter by status" data-filter-group="status">
    <button type="button" class="chip" data-filter="" aria-pressed="true">All</button>
    <button type="button" class="chip" data-filter="locked" aria-pressed="false">Locked</button>
    <button type="button" class="chip" data-filter="sample" aria-pressed="false">Lock after sample</button>
    <button type="button" class="chip" data-filter="candidate" aria-pressed="false">Candidate</button>
  </div>
  <div class="tablewrap" role="region" aria-label="Parts lock list" tabindex="0"><table class="parts" data-filter-table="status">
    <thead><tr><th scope="col">#</th><th scope="col">Function</th><th scope="col">Chosen part</th><th scope="col">Source</th><th scope="col">Price</th><th scope="col">Status</th><th scope="col">Notes</th></tr></thead><tbody>${rows}</tbody></table></div>
  <p class="note"><strong>Locked</strong>: dimensions from a datasheet. <strong>Lock after sample</strong>: chosen, but measured on a bought sample before CAD is frozen. <strong>Candidate</strong>: no verified listing yet.</p>` : '<p class="callout warn">docs/PARTS-LOCK.md not found at build time.</p>'}
</section>
<section aria-labelledby="cost-h" id="cost">
  <h2 id="cost-h">Cost per pump</h2>
  <p>Estimates, in EUR (shopping study, all-in for one builder in Germany including shipping, VAT and duty) and USD (cost model). Ranges, not quotes.</p>
  ${shop ? `<div class="md">${md(section(shop, /^0\.1/))}</div><h3>Marginal additional pump</h3><div class="md">${md(section(shop, /^0\.4/))}</div>` : ''}
  ${cost ? `<h3>One bench iteration (Rev A)</h3><div class="md">${md(section(cost, /^One bench iteration/))}</div><h3>Final design (Rev B), small quantity</h3><div class="md">${md(section(cost, /^Final design/))}</div>` : ''}
  <p class="note">Line items and sources: <a href="${d('docs/SHOPPING.md')}">shopping list</a>. Price log: <a href="${d('docs/05-cost-model.md')}#price-log-fill-in-after-each-order">cost model</a>, empty until the first order.</p>
</section>`;
}

export function docsIndex(ctx) {
  const { root, reg } = ctx;
  const groups = [...new Set(reg.map((e) => e.group))];
  return `
<header class="pagehead">
  <p class="kicker">Docs</p>
  <h1>Documentation library</h1>
  <p class="lede">${reg.length} documents from the repository, rendered at build time. Each page links back to its source file on GitHub; the repository is the single source of truth.</p>
</header>
${groups.map((g) => `<section><h2>${esc(g)}</h2><ul class="linklist">${reg.filter((e) => e.group === g).map((e) => `<li><a href="${docUrl(e, root)}"><strong>${esc(e.title)}</strong></a><span class="num">${esc(e.path)}</span></li>`).join('')}</ul></section>`).join('')}`;
}

export function docPage(ctx, entry, rendered) {
  const { root } = ctx;
  const toc = rendered.toc.filter((t) => t.depth === 2);
  return `
<header class="pagehead">
  <p class="kicker"><a href="${root}docs/">Docs</a> · ${esc(entry.group)}</p>
  <h1>${esc(entry.title)}</h1>
  <p class="srcline"><span class="num">${esc(entry.path)}</span> · <a href="${blobUrl(entry.path)}">View or edit on GitHub</a></p>
</header>
<div class="docwrap">
  ${toc.length > 2 ? `<nav class="toc" aria-label="On this page"><details open><summary>On this page</summary><ol>${rendered.toc.map((t) => `<li class="d${t.depth}"><a href="#${t.id}">${esc(t.text)}</a></li>`).join('')}</ol></details></nav>` : ''}
  <article class="md doc">${rendered.html}</article>
</div>`;
}
