// Converts the transparent path-traced PNGs from render-product.py into web assets:
// trimmed, AVIF + WebP + PNG fallback, written to public/renders/ with a sizes manifest.
import sharp from 'sharp';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const work = process.env.OP_RENDER_WORK ?? join(here, '..', '.render-work');
const out = join(here, '..', 'public', 'renders');
mkdirSync(out, { recursive: true });

// name -> output widths. top* keep identical px/mm (trim only), so one width each.
const JOBS = {
  hero: [1200, 2000],
  hero_graphite: [1200, 2000],
  exploded: [1000, 1800],
  top70: [900],
  top100: [900],
  top200: [900],
};
const manifest = {};
for (const [name, widths] of Object.entries(JOBS)) {
  const src = join(work, `${name}.png`);
  if (!existsSync(src)) { console.warn(`skip ${name}: ${src} missing`); continue; }
  const isTop = name.startsWith('top');
  // Trim transparent margin, then add a small even padding so soft edges are never clipped.
  const trimmed = await sharp(src).trim({ threshold: 1 }).toBuffer({ resolveWithObject: true });
  const pad = isTop ? 0 : Math.round(trimmed.info.width * 0.04);
  const base = sharp(trimmed.data).extend({ top: pad, bottom: pad, left: pad, right: pad, background: { r: 0, g: 0, b: 0, alpha: 0 } });
  const meta = await sharp(await base.png().toBuffer()).metadata();
  const buf = await base.png().toBuffer();
  manifest[name] = { aspect: meta.width / meta.height, srcWidth: meta.width, srcHeight: meta.height, widths: [] };
  // top views: record px width of source so the page can scale mm -> px exactly
  for (const w of widths) {
    const h = Math.round((w * meta.height) / meta.width);
    const img = () => sharp(buf).resize({ width: w, withoutEnlargement: true });
    await img().avif({ quality: 60, effort: 6 }).toFile(join(out, `${name}-${w}.avif`));
    await img().webp({ quality: 84, effort: 6 }).toFile(join(out, `${name}-${w}.webp`));
    if (w === widths[0]) await img().png({ palette: true, quality: 90, compressionLevel: 9 }).toFile(join(out, `${name}-${w}.png`));
    manifest[name].widths.push({ w, h });
  }
}
writeFileSync(join(out, 'manifest.json'), JSON.stringify(manifest, null, 2));
console.log(JSON.stringify(manifest, null, 1));
