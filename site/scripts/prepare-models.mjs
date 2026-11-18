// Copies only the shell meshes (OP-{70,100,200}_{top,bottom}.stl) from mechanical/out into public/models/
// for the lazy-loaded 3D viewer. Missing files are skipped; the viewer reports a friendly error then.
import { copyFileSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const src = join(root, '..', 'mechanical', 'out');
const dst = join(root, 'public', 'models');
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
let n = 0;
for (const size of ['70', '100', '200']) {
  for (const part of ['top', 'bottom']) {
    const f = `OP-${size}_${part}.stl`;
    if (existsSync(join(src, f))) { copyFileSync(join(src, f), join(dst, f)); n++; }
  }
}
console.log(`prepare-models: ${n}/6 shell meshes copied`);
