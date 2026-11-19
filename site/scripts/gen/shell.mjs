// Page shell: the safety banner (always the first element, never dismissable), header, footer.
import { esc, REPO_URL } from './lib.mjs';

export const NAV = [
  ['design/', 'Product'],
  ['safety/', 'Safety'],
  ['build/', 'Build'],
  ['faults/', 'Fault codes'],
  ['status/', 'Status'],
  ['docs/', 'Docs'],
  ['licence/', 'Licence'],
];

const MARK = `<svg class="mark" width="26" height="26" viewBox="0 0 26 26" aria-hidden="true"><rect x="1.5" y="6" width="23" height="14" rx="7" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="8.5" cy="13" r="2.2" fill="currentColor"/></svg>`;

export function renderPage({ title, description, root, nav, body, entry = 'main', meta, wide = false }) {
  const links = NAV.map(([href, label]) => `<li><a href="${root}${href}"${nav === href ? ' aria-current="page"' : ''}>${esc(label)}</a></li>`).join('');
  const tb = meta ?? {};
  const full = title === 'OpenPatch' ? 'OpenPatch (not a medical device)' : `${title} · OpenPatch (not a medical device)`;
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>${esc(full)}</title>
<meta name="description" content="${esc(description)} Not a medical device; never to be used on a person or animal; bench tests with water only." />
<meta name="color-scheme" content="light dark" />
<meta name="theme-color" content="#f6f6f4" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#0b0b0c" media="(prefers-color-scheme: dark)" />
<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; media-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'none'" />
<meta name="referrer" content="strict-origin-when-cross-origin" />
<link rel="icon" href="${root}favicon.svg" type="image/svg+xml" />
<script src="${root}theme.js"></script>
<script type="module" src="/src/entries/${entry}.ts"></script>
</head>
<body${wide ? ' class="wide"' : ''}>
<a class="skip-link" href="#main">Skip to content</a>
<div class="banner" role="note" aria-label="Safety notice"><p><strong>NOT A MEDICAL DEVICE.</strong> No CE marking, no FDA clearance. Experimental test project: <strong>never</strong> on a person or animal, <strong>never</strong> filled with insulin or any drug. Water bench tests only. <a href="${root}legal/">Disclaimers and legal</a></p></div>
<header class="topbar">
  <div class="bar">
    <a class="brand" href="${root}" aria-label="OpenPatch, home">${MARK}<span>OpenPatch</span></a>
    <nav class="mainnav" id="mainnav" aria-label="Main"><ul>${links}</ul></nav>
    <button class="theme-toggle" type="button" data-theme-toggle aria-label="Colour theme: automatic" title="Switch colour theme"><span aria-hidden="true">Auto</span></button>
    <button class="menu-btn" type="button" aria-expanded="false" aria-controls="mainnav" data-menu><span class="bars" aria-hidden="true"></span><span class="sr">Menu</span></button>
  </div>
</header>
<main id="main" tabindex="-1">
${body}
</main>
<footer class="sitefoot">
  <div class="foot-safety" role="note"><p><strong>Not a medical device.</strong> Never use on a person or animal. Never fill with insulin or any drug. Water bench tests only. <a href="${root}legal/">Disclaimers and legal notice</a></p></div>
  <div class="foot-grid">
    <div class="foot-brand">
      <a class="brand" href="${root}">${MARK}<span>OpenPatch</span></a>
      <p>An open test platform for a flat, detachable patch pump. Bench use only.</p>
    </div>
    <nav aria-label="Explore"><h2>Explore</h2><ul>${NAV.slice(0, 5).map(([h, l]) => `<li><a href="${root}${h}">${esc(l)}</a></li>`).join('')}</ul></nav>
    <nav aria-label="Project"><h2>Project</h2><ul>
      <li><a href="${root}docs/">Docs</a></li><li><a href="${root}parts/">Parts and cost</a></li><li><a href="${root}licence/">Licence and fair price</a></li><li><a href="${root}legal/">Disclaimers and legal</a></li><li><a href="${REPO_URL}">Source on GitHub</a></li>
    </ul></nav>
  </div>
  <p class="foot-small">Hardware and documentation CC BY-NC-SA 4.0. Software PolyForm Noncommercial 1.0.0. Commercial use needs a separate licence. No cookies, no tracking, no third-party requests.
  <span class="num">Built ${esc(tb.date ?? '')} · ${esc(tb.sha ?? '')}${tb.source ? ` · source: ${esc(tb.source)}` : ''}</span></p>
</footer>
</body>
</html>
`;
}
