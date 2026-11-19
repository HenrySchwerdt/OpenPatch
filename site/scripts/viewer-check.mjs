// Smoke test for the 3D viewer incl. the component library view. Usage: node scripts/viewer-check.mjs [outDir]
import { chromium } from 'playwright-core';
import { existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const out = process.argv[2] ?? 'screenshots';
const root = process.env.PLAYWRIGHT_BROWSERS_PATH ?? '/opt/pw-browsers';
const dir = readdirSync(root).filter((n) => n.startsWith('chromium-')).sort().pop();
const exe = ['chrome-linux/chrome', 'chrome-linux64/chrome'].map((p) => join(root, dir, p)).find(existsSync);
const b = await chromium.launch({ executablePath: exe, args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errs = [];
p.on('console', (m) => m.type() === 'error' && errs.push(m.text()));
p.on('pageerror', (e) => errs.push(e.message));
await p.goto('http://127.0.0.1:4173/design/', { waitUntil: 'networkidle' });
await p.click('.viewer-start');
await p.waitForSelector('.viewer[data-ready="true"]', { timeout: 90000 });
await p.waitForTimeout(1500);
await p.locator('.viewer').screenshot({ path: join(out, 'viewer-pod.png'), timeout: 120000 });
await p.check('input[value="library"]');
await p.click('.partlist button:has(.pn:text-is("nfp_608_26_45"))');
await p.waitForTimeout(2500);
await p.locator('.viewer').screenshot({ path: join(out, 'viewer-component-motor.png'), timeout: 120000 });
console.log(errs.length ? errs : 'viewer ok');
await b.close();
