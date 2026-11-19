// Page shell: banner, navigation, title-block footer. Every page gets the disclaimer banner.
import { esc, REPO_URL } from './lib.mjs';

export const NAV = [
  ['', 'Overview', 'The datasheet'],
  ['design/', 'Design', '3D explorer, parts, envelope'],
  ['safety/', 'Safety', 'Interlock and defence in depth'],
  ['faults/', 'Fault codes', 'Searchable catalogue'],
  ['status/', 'Status', 'Verified and not verified'],
  ['build/', 'Build', 'Guides, tests, order list'],
  ['parts/', 'Parts and cost', 'BOM lock, cost model'],
  ['docs/', 'Docs', 'Every document, rendered'],
  ['licence/', 'Licence', 'Community and commercial'],
  ['legal/', 'Disclaimers and legal', 'Disclaimers, privacy, notices'],
];

export function renderPage({ title, description, root, nav, body, entry = 'main', meta }) {
  const links = NAV.map(([href, label]) => {
    const cur = nav === href ? ' aria-current="page"' : '';
    return `<li><a href="${root}${href}"${cur}>${esc(label)}</a></li>`;
  }).join('');
  const tb = meta ?? {};
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(title)} · OpenPatch (not a medical device)</title>
<meta name="description" content="${esc(description)} Not a medical device; never to be used on a person or animal; bench tests with water only." />
<meta name="color-scheme" content="light dark" />
<meta name="theme-color" content="#f2efe6" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#0e1620" media="(prefers-color-scheme: dark)" />
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'none'" />
<meta name="referrer" content="strict-origin-when-cross-origin" />
<link rel="icon" href="${root}favicon.svg" type="image/svg+xml" />
<script src="${root}theme.js"></script>
<script type="module" src="/src/entries/${entry}.ts"></script>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<div class="banner" role="note" aria-label="Safety notice"><p><strong>⚠ NOT A MEDICAL DEVICE.</strong> Not approved or certified by any authority (no CE marking, no FDA clearance). Experimental test project: must <strong>NEVER</strong> be used on a person or animal and <strong>NEVER</strong> be filled with insulin or any other drug. Bench tests with water only. <a href="${root}legal/">Read all disclaimers</a></p></div>
<div class="frame">
<header class="topbar">
  <a class="brand" href="${root}"><svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><rect x="1.5" y="5.5" width="19" height="11" rx="4" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M6 11h10M6 8.5v5M16 8.5v5" stroke="currentColor" stroke-width="1"/></svg><span>OpenPatch</span></a>
  <button class="theme-toggle" type="button" data-theme-toggle aria-label="Colour theme: automatic" title="Switch colour theme"><span aria-hidden="true">Auto</span></button>
  <button class="menu-btn" type="button" aria-expanded="false" aria-controls="sidenav" data-menu>Menu</button>
</header>
<nav class="sidenav" id="sidenav" aria-label="Main"><ul>${links}</ul>
  <p class="side-note"><a href="${REPO_URL}">Source on GitHub</a></p>
</nav>
<main id="main" tabindex="-1">
${body}
</main>
<footer class="titleblock" aria-label="Document title block">
  <table>
    <tr><th scope="row">Document</th><td>${esc(title)}</td><th scope="row">Source</th><td>${tb.source ? esc(tb.source) : 'site generator'}</td></tr>
    <tr><th scope="row">Built</th><td class="num">${esc(tb.date ?? '')} · commit ${esc(tb.sha ?? '')}</td><th scope="row">Status</th><td>Test project, bench use only. <a href="${root}status/">What is verified</a></td></tr>
  </table>
  <p class="foot-warn"><strong>Not a medical device.</strong> Never use on a person or animal. Never fill with insulin or any drug. Water bench tests only. <a href="${root}legal/">Disclaimers and legal notice</a></p>
  <p>Hardware and documentation: CC BY-NC-SA 4.0. Software: PolyForm Noncommercial 1.0.0. Commercial use needs a separate licence. <a href="${root}licence/">Licence page</a>.</p>
</footer>
</div>
</body>
</html>
`;
}
