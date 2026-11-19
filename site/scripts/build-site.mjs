// Generates every HTML page of the site from the repository documents (run by prebuild/predev).
// Output (gitignored): index.html, design/, safety/, faults/, status/, build/, parts/, docs/, licence/ in site/.
import { copyFileSync, existsSync, mkdirSync, rmSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { REPO_ROOT, SITE, blobUrl, gitInfo, renderMarkdown } from './gen/lib.mjs';
import { parseFaults, parseParts, parseSpec, parseStatus } from './gen/data.mjs';
import { docUrl, makeAssetResolver, registry, renderDoc } from './gen/docs.mjs';
import { renderPage } from './gen/shell.mjs';
import { home } from './gen/pages-home.mjs';
import { product } from './gen/pages-product.mjs';
import { build } from './gen/pages-build.mjs';
import { collectFacts } from './gen/facts.mjs';
import { loadMedia } from './gen/media.mjs';
import { licence } from './gen/pages-licence.mjs';
import { legal } from './gen/pages-legal.mjs';
import { faults, safety, status } from './gen/pages-b.mjs';
import { docPage, docsIndex, parts } from './gen/pages-c.mjs';

const git = gitInfo();
const reg = registry();
const spec = parseSpec() ?? { envelope: [], limits: [], area: 74.6 };
const faultData = parseFaults();
const statusData = parseStatus();
const partsData = parseParts();
const facts = collectFacts({ spec, faults: faultData, status: statusData });
const media = await loadMedia();

for (const d of ['design', 'safety', 'faults', 'status', 'build', 'parts', 'docs', 'licence', 'legal', 'index.html']) rmSync(join(SITE, d), { recursive: true, force: true });
mkdirSync(join(SITE, 'public', 'doc-assets'), { recursive: true });

const written = [];
function write(rel, html) {
  const f = join(SITE, rel);
  mkdirSync(dirname(f), { recursive: true });
  writeFileSync(f, html);
  written.push(rel);
}

const rootFor = (rel) => (rel === 'index.html' ? './' : '../'.repeat(rel.split('/').length - 1));

function page(rel, nav, title, description, body, extra = {}) {
  write(rel, renderPage({ title, description, root: rootFor(rel), nav, body: extra.legacy ? `<div class="wrap legacy">${body}</div>` : body, meta: { ...git, ...extra.meta }, entry: extra.entry ?? 'main' }));
}
function ctxFor(rel) {
  const root = rootFor(rel);
  const resolveDoc = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : null; };
  return {
    root, reg, spec, git, parts: partsData, data: null, facts, media,
    d: (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); },
    md: (s) => renderMarkdown(s, { docPath: 'docs/x.md', resolveDoc, resolveAsset: makeAssetResolver(root) }).html,
  };
}

// figure (annotated CAD top view), only if the CAD pipeline produced it
const fig = join(REPO_ROOT, 'mechanical', 'out', 'bench', 'OP-100_layout_annotated.svg');
mkdirSync(join(SITE, 'public', 'figures'), { recursive: true });
if (existsSync(fig)) copyFileSync(fig, join(SITE, 'public', 'figures', 'OP-100_layout_annotated.svg'));

page('index.html', '', 'OpenPatch', 'An open, fully documented test platform for a very flat patch pump: dimensions, safety limits and fault codes are all public.', home({ ...ctxFor('index.html'), faults: faultData, status: statusData }), { meta: { source: 'spec, mechanical/out, docs/' } });
page('design/index.html', 'design/', 'Product', 'The OpenPatch bench pod: exploded view, size against an Omnipod DASH, how it works inside and a 3D viewer.', product(ctxFor('design/index.html')), { entry: 'design', meta: { source: 'mechanical/, docs/PARTS-LOCK.md' } });
page('safety/index.html', 'safety/', 'Safety', 'Hardware interlock simulator, defence in depth and hazard explorer for the OpenPatch pump (test project).', safety({ ...ctxFor('safety/index.html') }), { entry: 'safety', meta: { source: 'docs/02-safety.md, docs/06-diagnostics.md' } });
page('faults/index.html', 'faults/', 'Fault codes', 'Searchable catalogue of all OpenPatch diagnostic codes with severity, replaceable part, action and Trio text.', faults({ ...ctxFor('faults/index.html'), data: faultData }), { entry: 'faults', meta: { source: 'docs/06-diagnostics.md' } });
page('status/index.html', 'status/', 'Status', 'What is verified and what is not in the OpenPatch project, generated from STATUS.md.', status({ ...ctxFor('status/index.html'), data: statusData }), { meta: { source: 'docs/STATUS.md' } });
page('build/index.html', 'build/', 'Build', 'Step-by-step assembly of the OpenPatch Rev A bench pod, with parts, tools and a check for every step.', build(ctxFor('build/index.html')), { entry: 'build', meta: { source: 'docs/build-guide/, mechanical/ASSEMBLY.md' } });
page('parts/index.html', 'parts/', 'Parts and cost', 'Parts lock list, sources, prices and cost per pump.', parts(ctxFor('parts/index.html')), { entry: 'parts', legacy: true, meta: { source: 'docs/PARTS-LOCK.md, docs/SHOPPING.md, docs/05-cost-model.md' } });
page('licence/index.html', 'licence/', 'Licence', 'Community licence and commercial Fair-Price licence for OpenPatch, in plain language.', licence(ctxFor('licence/index.html')), { entry: 'licence', legacy: true, meta: { source: 'LICENSE.md, COMMERCIAL-LICENSE.md' } });
page('legal/index.html', 'legal/', 'Disclaimers and legal', 'Disclaimers, privacy statement and legal notice for the OpenPatch test project.', legal(ctxFor('legal/index.html')), { legacy: true, meta: { source: 'DISCLAIMER.md' } });
page('docs/index.html', 'docs/', 'Docs', 'Every OpenPatch specification and design document, rendered.', docsIndex(ctxFor('docs/index.html')), { legacy: true, meta: { source: 'repository markdown' } });
for (const e of reg) {
  const rel = `docs/${e.slug}/index.html`;
  const c = ctxFor(rel);
  page(rel, 'docs/', e.title, `${e.title} (${e.path}), rendered from the OpenPatch repository.`, docPage(c, e, renderDoc(e, reg, c.root)), { legacy: true, meta: { source: e.path } });
}

// vite inputs
writeFileSync(join(SITE, 'pages.json'), JSON.stringify(written));
console.log(`build-site: ${written.length} pages (${reg.length} docs, ${faultData?.total ?? 0} fault codes) at ${git.sha}`);
console.log(`build-site: images ${media.realCount} from docs/renders manifest${media.interimUsed ? ', interim CAD views in use' : ''}; ${media.steps.length} build steps (${media.stepsInterim ? 'interim, from mechanical/ASSEMBLY.md' : 'docs/build-guide/steps.json'}); waiting on render kinds: ${media.waiting.join(', ') || 'none'}`);
for (const x of facts.stale) console.log(`build-site: STALE DOC ${x.doc} ${x.what}`);
