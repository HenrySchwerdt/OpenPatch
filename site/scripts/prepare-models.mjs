// Kopiert mechanical/out/**/*.stl nach public/models/ und schreibt manifest.json.
// Existieren keine Dateien, schreibt das Skript ein leeres Manifest -> die Seite
// fällt zur Laufzeit auf das prozedurale Platzhalter-Modell zurück.
import { existsSync, mkdirSync, readdirSync, copyFileSync, writeFileSync, rmSync, statSync, readFileSync } from 'node:fs';
import { dirname, join, relative, basename } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const srcDir = join(root, '..', 'mechanical', 'out');
const outDir = join(root, 'public', 'models');

const PART_RULES = [
  ['lid', /(lid|deckel|top|cover|oben)/i],
  ['base', /(base|bottom|unten|tray|boden|floor|shell|housing|gehaeuse|gehäuse)/i],
  ['pcb', /(pcb|board|platine|electronics)/i],
  ['battery', /(batt|akku|lipo|cell)/i],
  ['reservoir', /(reservoir|cartridge|tank|ampulle)/i],
  ['plunger', /(plunger|piston|kolben)/i],
  ['motor', /(motor|stepper|drive|gear|spindle|spindel)/i],
];

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(join(dir, e.name)) : [join(dir, e.name)],
  );
}

function classify(relPath) {
  const name = relPath.replace(/\\/g, '/');
  const sizeMatch = name.match(/OP[-_ ]?(70|100|200)/i);
  const size = sizeMatch ? `OP-${sizeMatch[1]}` : null;
  const file = basename(name).replace(/OP[-_ ]?(70|100|200)/i, '');
  const hit = PART_RULES.find(([, re]) => re.test(file));
  return { size, part: hit ? hit[0] : 'assembly' };
}

rmSync(outDir, { recursive: true, force: true });
mkdirSync(outDir, { recursive: true });

const models = [];
const others = [];
const layouts = {};
if (existsSync(srcDir)) {
  for (const abs of walk(srcDir)) {
    const rel = relative(srcDir, abs);
    const lower = abs.toLowerCase();
    if (lower.endsWith('.stl')) {
      const flat = rel.replace(/[\\/]/g, '__');
      copyFileSync(abs, join(outDir, flat));
      models.push({ file: flat, bytes: statSync(abs).size, ...classify(rel) });
    } else if (lower.endsWith('.layout.json')) {
      const m = basename(abs).match(/OP[-_ ]?(70|100|200)/i);
      if (m) {
        try { layouts[`OP-${m[1]}`] = JSON.parse(readFileSync(abs, 'utf8')); } catch { /* ignorieren */ }
      }
    } else if (/\.(step|stp|dxf|3mf|dwg)$/.test(lower)) {
      others.push({ file: rel.replace(/\\/g, '/'), bytes: statSync(abs).size });
    }
  }
}

writeFileSync(
  join(outDir, 'manifest.json'),
  JSON.stringify({ generated: new Date().toISOString(), models, others, layouts }, null, 2),
);
console.log(
  models.length
    ? `[models] ${models.length} STL aus mechanical/out kopiert`
    : '[models] keine STL in mechanical/out gefunden -> prozedurales Platzhalter-Modell',
);
