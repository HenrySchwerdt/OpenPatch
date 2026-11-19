// Debug helper: lists elements that stick out of the viewport at 375 px. Usage: node scripts/overflow.mjs <path>
import { chromium } from 'playwright-core';
const base = 'http://127.0.0.1:4173/';
const b = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/opt/pw-browsers/chromium-1243/chrome-linux/chrome' });
const p = await (await b.newContext({ viewport: { width: 375, height: 812 } })).newPage();
await p.goto(base + (process.argv[2] ?? ''), { waitUntil: 'networkidle' });
console.log(await p.evaluate(() => [...document.querySelectorAll('body *')].filter((e) => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.tablewrap')).slice(0, 8).map((e) => `${e.tagName}.${e.className} ${Math.round(e.getBoundingClientRect().right)}`)));
await b.close();
