// Document registry: which repo markdown files are rendered as pages under /docs/<slug>/.
// Optional files are skipped when missing, so the site builds on any branch state; files that later appear are picked up.
import { copyFileSync, existsSync, mkdirSync, readdirSync, statSync } from 'node:fs';
import { basename, extname, join } from 'node:path';
import { exists, read, REPO_ROOT, renderMarkdown, SITE, slug as mkslug } from './lib.mjs';

// [path, group, mustMatch?]  mustMatch guards against stale files (e.g. an old licence text).
const LIST = [
  ['DISCLAIMER.md', 'Start here'],
  ['README.md', 'Start here'],
  ['docs/STATUS.md', 'Start here'],
  ['spec/design-parameters.md', 'Specification'],
  ['docs/02-safety.md', 'Safety and diagnostics'],
  ['docs/06-diagnostics.md', 'Safety and diagnostics'],
  ['docs/01-architecture.md', 'Architecture and protocol'],
  ['docs/v010/ARCHITECTURE.md', 'Architecture and protocol'],
  ['docs/04-protocol.md', 'Architecture and protocol'],
  ['firmware/docs/openpatch-protocol.md', 'Architecture and protocol'],
  ['firmware-rs/docs/architecture.md', 'Architecture and protocol'],
  ['firmware-rs/docs/protocol-extensions.md', 'Architecture and protocol'],
  ['firmware-rs/docs/boards.md', 'Architecture and protocol'],
  ['firmware-rs/docs/bootloader.md', 'Architecture and protocol'],
  ['firmware-rs/docs/ble-stack-choice.md', 'Architecture and protocol'],
  ['firmware-rs/docs/differential-testing.md', 'Architecture and protocol'],
  ['firmware-rs/docs/stubs.md', 'Architecture and protocol'],
  ['docs/03-patents.md', 'Architecture and protocol'],
  ['docs/SHOPPING.md', 'Build and order'],
  ['docs/PARTS-LOCK.md', 'Build and order'],
  ['docs/05-cost-model.md', 'Build and order'],
  ['docs/SETUP.md', 'Build and order'],
  ['mechanical/ASSEMBLY.md', 'Build and order'],
  ['mechanical/REFILL.md', 'Build and order'],
  ['mechanical/cannula-measurement.md', 'Build and order'],
  ['mechanical/parts.md', 'Build and order'],
  ['mechanical/gear-selection.md', 'Build and order'],
  ['mechanical/motor-selection.md', 'Build and order'],
  ['mechanical/linear-actuator-selection.md', 'Build and order'],
  ['mechanical/README.md', 'Build and order'],
  ['mechanical/sim/REPORT.md', 'Build and order'],
  ['firmware-rs/docs/bench-testing.md', 'Build and order'],
  ['electronics/bench/pin-assignment.md', 'Build and order'],
  ['electronics/bench/FOOTPRINT-VERIFICATION.md', 'Build and order'],
  ['electronics/bench/fab/ORDER.md', 'Build and order'],
  ['electronics/bench/fab/COST.md', 'Build and order'],
  ['mechanical/CART-A-V2-BRIEF.md', 'OpenTube (cart pump A)'],
  ['docs/CART-ORDER.md', 'OpenTube (cart pump A)'],
  ['LICENSE.md', 'Licence', /PolyForm/],
  ['COMMERCIAL-LICENSE.md', 'Licence', /Fair-Price/],
  ['CONTRIBUTING.md', 'Licence'],
  ['CLA.md', 'Licence'],
];

const NAMES = { 'DISCLAIMER.md': 'Disclaimer', 'README.md': 'Repository overview', 'docs/STATUS.md': 'Project status and handover', 'spec/design-parameters.md': 'Design parameters (single source of truth)', 'mechanical/CART-A-V2-BRIEF.md': 'OpenTube design brief (cart pump A, v2)', 'docs/CART-ORDER.md': 'Cart pump cost and order package' };

export function slugFor(path) {
  if (path === 'DISCLAIMER.md') return 'disclaimer';
  return path.replace(/\.md$/i, '').replace(/^docs\//, '').replace(/[\\/]/g, '-').toLowerCase();
}

export function registry() {
  const seen = new Set();
  const out = [];
  const add = (path, group, must) => {
    if (seen.has(path) || !exists(path)) return;
    const src = read(path);
    if (must && !must.test(src)) return;
    seen.add(path);
    const h1 = /^#\s+(.+)$/m.exec(src)?.[1]?.replace(/[`*]/g, '').trim();
    out.push({ path, group, slug: slugFor(path), title: NAMES[path] ?? h1 ?? basename(path), src });
  };
  for (const [p, g, m] of LIST) add(p, g, m);
  // anything new under docs/ shows up automatically
  if (existsSync(join(REPO_ROOT, 'docs'))) for (const f of readdirSync(join(REPO_ROOT, 'docs')).sort()) if (f.endsWith('.md')) add(`docs/${f}`, 'Other documents');
  return out;
}

export function docUrl(entry, root) { return `${root}docs/${entry.slug}/`; }

/** Copies a referenced repo image into public/doc-assets and returns its site path (null if unusable). */
export function makeAssetResolver(root) {
  mkdirSync(join(SITE, 'public', 'doc-assets'), { recursive: true });
  return (rel) => {
    const f = join(REPO_ROOT, rel);
    if (!existsSync(f) || !/\.(png|jpe?g|svg|webp|gif)$/i.test(extname(f)) || statSync(f).size > 900_000) return null;
    const name = rel.replace(/[\\/]/g, '_');
    copyFileSync(f, join(SITE, 'public', 'doc-assets', name));
    return `${root}doc-assets/${name}`;
  };
}

export function renderDoc(entry, reg, root) {
  const byPath = new Map(reg.map((e) => [e.path, e]));
  return renderMarkdown(entry.src, {
    docPath: entry.path,
    resolveDoc: (p) => { const e = byPath.get(p); return e ? docUrl(e, root) : null; },
    resolveAsset: makeAssetResolver(root),
  });
}
