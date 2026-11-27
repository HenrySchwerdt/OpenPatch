// The pump family: pieces shared by the home page and both product pages (model switch, model cards, test-only strip).
// Every number comes from facts.mjs (OpenPatch) or facts-opentube.mjs (OpenTube).
import { esc } from './lib.mjs';
import { stage } from './media.mjs';

const f1 = (n) => (n == null ? 'n/a' : (Math.round(n * 10) / 10).toFixed(1));
const num = (n) => (n == null ? 'n/a' : String(n));

export const MODELS = [
  { key: 'openpatch', href: 'design/', name: 'OpenPatch', kind: 'Patch pump' },
  { key: 'opentube', href: 'opentube/', name: 'OpenTube', kind: 'Tubed pump' },
];

/** Segmented link control at the top of each product page. */
export function familySwitch(root, current) {
  return `<nav class="family" aria-label="Pump models">${MODELS.map((m) => `<a href="${root}${m.href}"${m.key === current ? ' aria-current="page"' : ''}><span class="fam-name">${esc(m.name)}</span><span class="fam-kind">${esc(m.kind)}</span></a>`).join('')}</nav>`;
}

/** The same test-only statement on both product pages, right under the lede. */
export function testOnly(root) {
  return `<p class="testonly" role="note"><strong>Test hardware, not a medical device.</strong> Never on a person or animal. Never filled with insulin or any other drug: bench tests with water only, into a container. <a href="${root}legal/">Disclaimers</a></p>`;
}

/** Card data for both models. F = OpenPatch facts, T = OpenTube facts. */
export function models(media, F, T) {
  const h = F.hero;
  const ot = media.product('opentube');
  return [
    {
      ...MODELS[0], status: 'Rev A bench pod',
      line: 'A flat, detachable patch pod with a swappable cannula dock, built around a 16 × 5 mm stadium reservoir.',
      img: media.find('hero'), alt: 'Render of the OpenPatch OP-100 bench pod with a clear lid: reservoir, drive and sensor board visible inside a flat white housing.',
      specs: [
        ['Height', h ? f1(h.h) : 'n/a', 'mm'],
        [`Size ${h?.id ?? ''}`.trim(), h ? `${f1(h.l)} × ${f1(h.w)}` : 'n/a', 'mm'],
        ['Reservoir', F.sizes.map((s) => s.ml).join(' / ') || 'n/a', 'ml'],
        ['Dose step', F.uPerStep ?? 'n/a', 'U'],
      ],
    },
    {
      ...MODELS[1], status: 'In development',
      line: 'A tubed pump around a 1.6 ml glass cartridge, with the original Accu-Chek Insight Adapter & Tubing as its front cap.',
      img: ot.byId('opentube_hero_rear'), alt: null,
      specs: [
        ['Size with adapter', T.size ? `${f1(T.size.l)} × ${num(T.size.w)} × ${num(T.size.h)}` : 'n/a', 'mm'],
        ['Envelope', T.envelope != null ? `${f1(T.envelope)}` : 'n/a', `ml${T.vsInsight ? ` (${T.vsInsight} vs Insight)` : ''}`],
        ['Cartridge', T.cart?.ml != null ? f1(T.cart.ml) : 'n/a', 'ml'],
        ['Stroke', T.stroke != null ? f1(T.stroke) : 'n/a', 'mm'],
      ],
    },
  ];
}

/** One model card. The heading link is stretched over the card (one tab stop, whole card clickable). */
export function modelCard(m, root, { eager = false, level = 2, sizes = '(min-width: 1240px) 580px, (min-width: 52rem) 48vw, 100vw' } = {}) {
  const H = `h${level}`;
  return `<article class="model" aria-labelledby="m-${m.key}">
  ${stage(m.img, root, { alt: m.alt ?? undefined, sizes, eager, cls: 'model-img', label: 'Render pending' })}
  <div class="model-body">
    <p class="model-kicker"><span>${esc(m.kind)}</span><span class="model-status">${esc(m.status)}</span></p>
    <${H} class="model-name" id="m-${m.key}"><a href="${root}${m.href}">${esc(m.name)}</a></${H}>
    <p class="model-line">${esc(m.line)}</p>
    <dl class="specs">${m.specs.map(([k, v, u]) => `<div><dt>${esc(k)}</dt><dd><span class="num">${esc(v)}</span> <span class="u">${esc(u)}</span></dd></div>`).join('')}</dl>
    <p class="model-go" aria-hidden="true">Explore ${esc(m.name)}</p>
  </div>
</article>`;
}

/** Closing block of a product page: the sibling model. */
export function sibling(all, current, root) {
  const other = all.find((m) => m.key !== current);
  if (!other) return '';
  return `<section class="wrap block sibling" aria-labelledby="sib-h">
  <p class="eyebrow">The other pump</p>
  <h2 id="sib-h" class="h-sm">Same electronics, a different way to hold the water.</h2>
  <div class="models one">${modelCard(other, root, { level: 3, sizes: '(min-width: 52rem) 560px, 100vw' })}</div>
</section>`;
}
