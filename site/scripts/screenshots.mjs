// Usage: npm run build && npm run preview &  then  node scripts/screenshots.mjs [baseUrl]
// Writes light/dark screenshots at 375/768/1440 of the main pages to screenshots/, checks horizontal overflow,
// console errors, and that the 3D viewer draws pixels. CHROME_PATH overrides the browser (default: Playwright's Chromium).
import { chromium } from 'playwright-core';
import { existsSync, mkdirSync, readdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const base = (process.argv[2] ?? 'http://127.0.0.1:4174/').replace(/\/?$/, '/');
const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'screenshots');
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

function findChrome() {
  if (process.env.CHROME_PATH) return process.env.CHROME_PATH;
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, '/root/.cache/ms-playwright', `${process.env.HOME}/.cache/ms-playwright`].filter(Boolean);
  for (const r of roots) {
    if (!existsSync(r)) continue;
    for (const d of readdirSync(r).filter((n) => n.startsWith('chromium')).sort().reverse()) {
      for (const p of ['chrome-linux/chrome', 'chrome-linux64/chrome']) if (existsSync(join(r, d, p))) return join(r, d, p);
    }
  }
  return undefined;
}

const PAGES = [['home', ''], ['design', 'design/'], ['safety', 'safety/'], ['faults', 'faults/'], ['status', 'status/'], ['build', 'build/'], ['parts', 'parts/'], ['licence', 'licence/'], ['legal', 'legal/'], ['doc', 'docs/mechanical-assembly/']];
const browser = await chromium.launch({ executablePath: findChrome(), args: ['--no-sandbox', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const problems = [];

for (const theme of ['light', 'dark']) {
  for (const [w, h] of [[375, 812], [768, 1024], [1440, 900]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: theme });
    const page = await ctx.newPage();
    page.on('console', (m) => { if (m.type() === 'error') problems.push(`[${w}/${theme}] ${m.text()}`); });
    page.on('pageerror', (e) => problems.push(`[${w}/${theme}] pageerror ${e.message}`));
    for (const [name, path] of PAGES) {
      await page.goto(base + path, { waitUntil: 'networkidle' });
      if (name === 'design') {
        await page.click('.viewer-start');
        await page.waitForSelector('.viewer[data-ready="true"]', { timeout: 60000 });
        await page.waitForTimeout(1500);
        const lit = await page.evaluate(() => {
          const c = document.querySelector('.viewer-canvas');
          const t = document.createElement('canvas'); t.width = c.width; t.height = c.height;
          const g = t.getContext('2d'); g.drawImage(c, 0, 0);
          const d = g.getImageData(0, 0, t.width, t.height).data; let n = 0;
          for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++;
          return n;
        }).catch(() => 0);
        if (!lit) problems.push(`[${w}/${theme}] viewer canvas empty (software GL may not support preserveDrawingBuffer)`);
      }
      await page.evaluate(() => window.scrollTo(0, 0));
      const top = await page.evaluate(() => { const b = document.querySelector('.banner'); const r = b?.getBoundingClientRect(); return b && r.top <= 0.5 && document.elementFromPoint(5, 5)?.closest('.banner') && r.height > 20 ? Math.round(r.height) : 0; });
      if (!top) problems.push(`[${w}/${theme}] ${name}: safety banner is not the first visible element`);
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (overflow > 0) problems.push(`[${w}/${theme}] ${name}: horizontal overflow ${overflow}px`);
      try { await page.screenshot({ path: join(out, `${theme}-${w}-${name}.png`), fullPage: name !== 'faults' && name !== 'doc', timeout: 120000 }); } catch (e) { problems.push(`[${w}/${theme}] ${name}: screenshot failed ${e.message.split('\n')[0]}`); }
    }
    await ctx.close();
  }
}
await browser.close();
if (problems.length) { console.log('Problems:\n' + problems.join('\n')); process.exitCode = 1; } else console.log('screenshots ok');
