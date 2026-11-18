// Usage: npm run build && npm run preview &  then  node scripts/screenshots.mjs [url]
// Writes light/dark screenshots at 375/768/1440 to screenshots/ and checks the 3D viewer draws pixels.
import { chromium } from 'playwright-core';
import { mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const url = process.argv[2] ?? 'http://127.0.0.1:4173/';
const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'screenshots');
rmSync(out, { recursive: true, force: true });
mkdirSync(out, { recursive: true });

const CHROME = process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({ executablePath: CHROME, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const problems = [];
const SECTIONS = ['size', 'how', 'safety', 'build', 'cost', 'open', 'faq'];

for (const theme of ['light', 'dark']) {
  for (const [w, h] of [[375, 812], [768, 1024], [1440, 900]]) {
    const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: theme });
    const page = await ctx.newPage();
    page.on('console', (m) => { if (m.type() === 'error') problems.push(`[${w}/${theme}] ${m.text()}`); });
    page.on('pageerror', (e) => problems.push(`[${w}/${theme}] pageerror ${e.message}`));
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1800);
    await page.screenshot({ path: join(out, `${theme}-${w}-hero.png`) });
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    if (overflow > 0) problems.push(`[${w}/${theme}] horizontal overflow ${overflow}px`);

    // story at three scroll positions
    const top = await page.evaluate(() => document.querySelector('.story-track').getBoundingClientRect().top + scrollY);
    const span = await page.evaluate(() => document.querySelector('.story-track').offsetHeight - innerHeight);
    for (const [i, f] of [[1, 0.02], [2, 0.5], [3, 0.95]]) {
      await page.evaluate((y) => scrollTo(0, y), top + span * f - 0);
      await page.waitForTimeout(900);
      await page.screenshot({ path: join(out, `${theme}-${w}-story-${i}.png`) });
    }
    for (const id of SECTIONS) {
      await page.evaluate((i) => document.getElementById(i).scrollIntoView({ behavior: 'instant' }), id);
      await page.waitForTimeout(1300);
      await page.screenshot({ path: join(out, `${theme}-${w}-${id}.png`) });
    }
    if (theme === 'light' || w === 1440) {
      await page.evaluate(() => document.getElementById('viewer').scrollIntoView({ behavior: 'instant' }));
      await page.click('.viewer-start');
      await page.waitForSelector('[data-viewer][data-ready="true"]', { timeout: 30000 });
      await page.waitForTimeout(1500);
      await page.screenshot({ path: join(out, `${theme}-${w}-viewer.png`) });
      const stats = await page.evaluate(() => {
        const c = document.querySelector('.viewer-canvas');
        const g = document.createElement('canvas'); g.width = 128; g.height = 80;
        const x = g.getContext('2d'); x.drawImage(c, 0, 0, 128, 80);
        const d = x.getImageData(0, 0, 128, 80).data;
        let lit = 0; for (let i = 0; i < d.length; i += 4) if (d[i + 3] > 200 && d[i] > 120) lit++;
        return { lit, total: 128 * 80 };
      });
      console.log(`viewer ${theme}/${w}: ${stats.lit}/${stats.total} bright opaque px`);
      if (stats.lit < 100) problems.push(`[${w}/${theme}] viewer canvas looks empty`);
    }
    await ctx.close();
  }
}
await browser.close();
console.log(problems.length ? `PROBLEMS:\n${problems.join('\n')}` : 'no console errors, no overflow');
