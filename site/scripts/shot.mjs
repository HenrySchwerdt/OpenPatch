// Quick screenshots of selected pages: node scripts/shot.mjs <outDir> <width> <theme> <page...>   (needs `npm run preview`)
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import { join } from 'node:path';

const [out, w, theme, ...pages] = process.argv.slice(2);
mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const ctx = await browser.newContext({ viewport: { width: +w, height: 900 }, colorScheme: theme });
const page = await ctx.newPage();
const errs = [];
page.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
page.on('pageerror', (e) => errs.push(e.message));
for (const p of pages) {
  await page.goto(`http://127.0.0.1:${process.env.PORT || 4174}/${p === 'home' ? '' : p}`, { waitUntil: 'networkidle' });
  await page.evaluate(async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) { window.scrollTo(0, y); await new Promise((r) => setTimeout(r, 200)); } window.scrollTo(0, 0); });
  await page.waitForTimeout(800);
  const ov = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  const name = (p === 'home' ? 'home' : p.replace(/\//g, '')) || 'home';
  await page.screenshot({ path: join(out, `${theme}-${w}-${name}.png`), fullPage: true, timeout: 120000 });
  console.log(name, 'overflow', ov);
}
if (errs.length) console.log('errors', errs);
await browser.close();
