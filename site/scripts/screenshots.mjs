// Usage: node scripts/screenshots.mjs [url]   (Vorschau-Server muss laufen: npm run preview)
import { chromium } from 'playwright-core';
import { mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const url = process.argv[2] ?? 'http://127.0.0.1:4173/';
const out = join(dirname(fileURLToPath(import.meta.url)), '..', 'screenshots');
mkdirSync(out, { recursive: true });

const CHROME = process.env.CHROME_PATH ?? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'],
});

const problems = [];
const settle = (page, ms = 1200) => page.waitForTimeout(ms);

async function openPage(width, height, theme) {
  const ctx = await browser.newContext({ viewport: { width, height }, colorScheme: theme, deviceScaleFactor: 1 });
  const page = await ctx.newPage();
  page.on('console', (m) => {
    if (m.type() === 'error' || m.type() === 'warning') problems.push(`[${width}/${theme}] console.${m.type()}: ${m.text()}`);
  });
  page.on('pageerror', (e) => problems.push(`[${width}/${theme}] pageerror: ${e.message}`));
  page.on('requestfailed', (r) => problems.push(`[${width}/${theme}] requestfailed: ${r.url()}`));
  await page.goto(url, { waitUntil: 'networkidle' });
  await settle(page, 1800);
  return { ctx, page };
}

async function revealAll(page) {
  const h = await page.evaluate(() => document.documentElement.scrollHeight);
  for (let y = 0; y < h; y += 500) {
    await page.evaluate((v) => window.scrollTo(0, v), y);
    await page.waitForTimeout(90);
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(900);
}

for (const theme of ['light', 'dark']) {
  for (const [w, h] of [[375, 812], [1440, 900]]) {
    const { ctx, page } = await openPage(w, h, theme);
    await page.screenshot({ path: join(out, `${theme}-${w}-hero.png`) });
    if (w === 1440) {
      await page.click('#explode-toggle');
      await settle(page, 2200);
      await page.screenshot({ path: join(out, `${theme}-${w}-hero-exploded.png`) });
    }
    await revealAll(page);
    for (const id of ['groessen', 'funktion', 'sicherheit', 'bauanleitung', 'kosten', 'downloads']) {
      const el = page.locator(`#${id}`);
      await el.scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
      await el.screenshot({ path: join(out, `${theme}-${w}-sec-${id}.png`) });
    }
    await ctx.close();
  }
}

// Overflow-Check
for (const w of [320, 375, 768, 1024, 1440]) {
  const { ctx, page } = await openPage(w, 900, 'light');
  await revealAll(page);
  const r = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }));
  const bad = await page.evaluate(() => {
    const iw = window.innerWidth;
    return [...document.querySelectorAll('body *')]
      .filter((el) => { const b = el.getBoundingClientRect(); return b.right > iw + 1 && b.width > 0 && !el.closest('.table-wrap, .diagram'); })
      .slice(0, 6).map((el) => `${el.tagName}.${el.className}`);
  });
  console.log(`width ${w}: scrollWidth ${r.sw} / innerWidth ${r.iw} ${r.sw > r.iw ? 'OVERFLOW' : 'ok'} ${bad.length ? JSON.stringify(bad) : ''}`);
  await ctx.close();
}

await browser.close();
console.log(problems.length ? `PROBLEMS:\n${problems.join('\n')}` : 'no console errors / warnings / failed requests');
