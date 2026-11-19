// Viewport screenshot: node scripts/vshot.mjs out.png width theme path scrollY [selector]
import { chromium } from 'playwright-core';
const [out, w, theme, path, y, sel] = process.argv.slice(2);
const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
const p = await (await b.newContext({ viewport: { width: +w, height: 900 }, colorScheme: theme })).newPage();
await p.goto(`http://127.0.0.1:${process.env.PORT || 4174}/${path}`, { waitUntil: 'networkidle' });
if (sel) await p.locator(sel).first().scrollIntoViewIfNeeded(); else await p.evaluate((v) => window.scrollTo(0, +v), y);
await p.waitForTimeout(900);
await p.screenshot({ path: out });
await b.close();
