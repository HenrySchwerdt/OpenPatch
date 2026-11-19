// Shared helpers for the build-time generators: repo access, markdown tables, markdown rendering.
import { existsSync, readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { dirname, join, posix, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Marked } from 'marked';

export const SITE = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
export const REPO_ROOT = resolve(SITE, '..');
function originUrl() {
  try {
    const u = execFileSync('git', ['config', '--get', 'remote.origin.url'], { cwd: REPO_ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim();
    const m = /github\.com[:/]([^/]+\/[^/.]+?)(?:\.git)?$/.exec(u);
    return m ? `https://github.com/${m[1]}` : '';
  } catch { return ''; }
}
// Set by the Pages workflow (github.repository); locally derived from the git remote.
export const REPO_URL = (process.env.VITE_REPO_URL || originUrl() || 'https://github.com').replace(/\/$/, '');
const REPO_SLUG = REPO_URL.replace(/^https:\/\/github\.com\//, '');
const OWNER = REPO_SLUG.split('/')[0] || 'x';

export const exists = (rel) => existsSync(join(REPO_ROOT, rel));
export const read = (rel) => (exists(rel) ? readFileSync(join(REPO_ROOT, rel), 'utf8') : null);
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
export const slug = (s) => String(s).toLowerCase().replace(/<[^>]+>/g, '').replace(/[^\p{L}\p{N}\s-]/gu, '').trim().replace(/\s+/g, '-').replace(/-+/g, '-');
export const blobUrl = (rel) => `${REPO_URL}/blob/main/${rel.replace(/^\.?\//, '')}`;

export function gitInfo() {
  const run = (...a) => { try { return execFileSync('git', a, { cwd: REPO_ROOT, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim(); } catch { return ''; } };
  const sha = run('rev-parse', '--short', 'HEAD') || (process.env.GITHUB_SHA || '').slice(0, 7) || 'unknown';
  const date = run('log', '-1', '--format=%cs') || new Date().toISOString().slice(0, 10);
  return { sha, date };
}

/** Strip inline markdown to plain text (for data attributes and search). */
export function plain(md) {
  return String(md ?? '').replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]+)\]\([^)]*\)/g, '$1').replace(/[`*]/g, '').replace(/(^|\s)_([^_]+)_(?=\s|$)/g, '$1$2').replace(/<br\s*\/?>/g, ' ').replace(/\s+/g, ' ').trim();
}

function splitRow(l) {
  const s = l.trim().replace(/^\|/, '').replace(/\|$/, '');
  const cells = [];
  let cur = '';
  let code = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === '`') code = !code;
    if (c === '\\' && s[i + 1] === '|') { cur += '|'; i++; continue; }
    if (c === '|' && !code) { cells.push(cur.trim()); cur = ''; } else cur += c;
  }
  cells.push(cur.trim());
  return cells;
}

/** All pipe tables in a markdown text: { heading, headers[], rows[][] } (cells keep inline markdown). */
export function tables(md) {
  const out = [];
  const lines = md.split('\n');
  let heading = '';
  let inFence = false;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (/^```/.test(l)) inFence = !inFence;
    if (inFence) continue;
    const h = /^#{1,6}\s+(.*)$/.exec(l);
    if (h) heading = h[1].trim();
    if (/^\s*\|.*\|\s*$/.test(l) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|\s*$/.test(lines[i + 1])) {
      const headers = splitRow(l);
      const rows = [];
      i += 2;
      while (i < lines.length && /^\s*\|.*\|\s*$/.test(lines[i])) { rows.push(splitRow(lines[i])); i++; }
      i--;
      out.push({ heading, headers, rows });
    }
  }
  return out;
}

/** Markdown of the section starting at a heading matching `re`, up to the next heading of same or higher level. */
export function section(md, re) {
  const lines = md.split('\n');
  let start = -1;
  let level = 0;
  let fence = false;
  for (let i = 0; i < lines.length; i++) {
    if (/^```/.test(lines[i])) fence = !fence;
    if (fence) continue;
    const h = /^(#{1,6})\s+(.*)$/.exec(lines[i]);
    if (!h) continue;
    if (start < 0) { if (re.test(h[2])) { start = i; level = h[1].length; } }
    else if (h[1].length <= level) return lines.slice(start + 1, i).join('\n');
  }
  return start < 0 ? '' : lines.slice(start + 1).join('\n');
}

/** Render repo markdown to HTML. opts: { docPath, resolveDoc(relPath) -> url|null, resolveAsset(relPath) -> url|null } */
export function renderMarkdown(md, opts = {}) {
  const toc = [];
  const used = new Map();
  const docDir = posix.dirname(opts.docPath || 'README.md');
  const fixUrl = (href) => {
    if (!href || /^(https?:|mailto:|#)/.test(href)) return href;
    const [p, frag] = href.split('#');
    const repoRel = posix.normalize(posix.join(docDir, p));
    if (repoRel.startsWith('..')) return href;
    const doc = opts.resolveDoc?.(repoRel);
    if (doc) return doc + (frag ? `#${frag}` : '');
    return `${REPO_URL}/blob/main/${repoRel}${frag ? `#${frag}` : ''}`;
  };
  const m = new Marked({ gfm: true });
  m.use({
    renderer: {
      heading({ tokens, depth }) {
        const text = this.parser.parseInline(tokens);
        let id = slug(tokens.map((t) => t.raw ?? t.text ?? '').join('')) || 'section';
        const n = used.get(id) ?? 0;
        used.set(id, n + 1);
        if (n) id += `-${n}`;
        if (depth >= 2 && depth <= 3) toc.push({ depth, id, text: plain(text.replace(/<[^>]+>/g, '')) });
        return `<h${depth} id="${id}"><a class="anchor" href="#${id}" aria-label="Link to this section">#</a>${text}</h${depth}>\n`;
      },
      link({ href, title, tokens }) {
        const t = this.parser.parseInline(tokens);
        const u = fixUrl(href);
        const ext = /^https?:/.test(u) ? ' rel="noopener"' : '';
        return `<a href="${esc(u)}"${title ? ` title="${esc(title)}"` : ''}${ext}>${t}</a>`;
      },
      image({ href, title, text }) {
        const local = /^(https?:|data:)/.test(href) ? href : opts.resolveAsset?.(posix.normalize(posix.join(docDir, href)));
        if (!local) return `<span class="missing-img">[image: ${esc(text || href)}]</span>`;
        return `<img src="${esc(local)}" alt="${esc(text)}"${title ? ` title="${esc(title)}"` : ''} loading="lazy" />`;
      },
      code({ text, lang }) {
        const note = lang === 'mermaid' ? '<p class="code-note">Diagram source (Mermaid). Rendered view: open this file on GitHub.</p>' : '';
        return `${note}<pre><code${lang ? ` class="language-${esc(lang)}"` : ''}>${esc(text)}</code></pre>\n`;
      },
      html({ text }) { return text.replace(/<script[\s\S]*?<\/script>/gi, '').replace(/\son\w+="[^"]*"/gi, ''); },
    },
  });
  let html = m.parse(md);
  html = html.replaceAll('<table>', '<div class="tablewrap" role="region" aria-label="Table" tabindex="0"><table>').replaceAll('</table>', '</table></div>');
  // keep personal names out of visible text (hrefs to the repository stay)
  const own = OWNER.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  html = html.replace(new RegExp(`>([^<]*)${own}/[\\w.-]+`, 'gi'), '>$1the OpenPatch repository').replace(new RegExp(`>https://${own}\\.github\\.io/[^<]*<`, 'gi'), '>the project site<');
  return { html, toc };
}

export function inline(md, opts = {}) {
  return renderMarkdown(String(md ?? ''), opts).html.replace(/^<p>|<\/p>\s*$/g, '').trim();
}
