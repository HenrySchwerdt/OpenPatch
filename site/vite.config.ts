import { defineConfig, type Plugin } from 'vite';
import { bomHtml, costHtml, downloadsFromManifest, esc, hasFile } from './scripts/data.mjs';

const REPO = (process.env.VITE_REPO_URL || 'https://github.com/HenrySchwerdt/ai-insulin-pump').replace(/\/$/, '');

const kb = (n: number) => (n > 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} kB`);

function localDownloads(): string {
  const { models, others } = downloadsFromManifest() as {
    models: { file: string; bytes: number }[];
    others: { file: string; bytes: number }[];
  };
  const items = [
    ...models.map((m) => ({ href: `./models/${encodeURIComponent(m.file)}`, label: m.file.replace(/__/g, ' / '), bytes: m.bytes, local: true })),
    ...others.map((o) => ({ href: `${REPO}/blob/main/mechanical/out/${o.file}`, label: o.file, bytes: o.bytes, local: false })),
  ];
  if (!items.length) {
    return '<p class="table-note mono">Noch keine exportierten CAD-Dateien in <code>mechanical/out/</code>. Sobald vorhanden, werden sie hier beim Build gelistet.</p>';
  }
  return `<ul class="file-list">${items
    .map(
      (i) =>
        `<li><a href="${esc(i.href)}"${i.local ? ' download' : ''}><span class="mono">${esc(i.label)}</span><span class="mono dim">${kb(i.bytes)}</span></a></li>`,
    )
    .join('')}</ul>`;
}

function injectPlugin(): Plugin {
  return {
    name: 'openpatch-inject',
    transformIndexHtml(html) {
      const has = (p: string) => (hasFile(p) ? 'is-ready' : 'is-planned');
      return html
        .replaceAll('%REPO%', REPO)
        .replace('<!--BOM_TABLE-->', bomHtml())
        .replace('<!--COST_BLOCK-->', costHtml())
        .replace('<!--LOCAL_DOWNLOADS-->', localDownloads())
        .replaceAll('%STATE_MECH%', has('mechanical/out'))
        .replaceAll('%STATE_ELEC%', has('electronics/bom.csv'))
        .replaceAll('%STATE_FW%', has('firmware/core/include'))
        .replaceAll('%STATE_IOS%', has('ios/OpenPatchKit'));
    },
  };
}

export default defineConfig({
  base: process.env.VITE_BASE || './',
  plugins: [injectPlugin()],
  build: { target: 'es2022', chunkSizeWarningLimit: 700 },
  server: { host: '127.0.0.1' },
});
