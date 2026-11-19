// Prepares the 3D data for the lazy-loaded viewer -> public/models/ (gitignored, regenerated on every build).
//
// 1. Generated CAD parts (mechanical/out[/bench]/OP-<size>_<part>.stl) are welded and written as compact .glb files.
// 2. If mechanical/components/catalog.json exists (vendor-accurate component models), its entries and glTF files are
//    copied and merged into the manifest. If an assembly glTF exists it is used by the viewer as the primary model.
// 3. public/models/manifest.json describes everything the viewer and the parts table need. Missing inputs are skipped.
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { basename, dirname, extname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const repo = join(root, '..');
const dst = join(root, 'public', 'models');
const meta = JSON.parse(readFileSync(join(root, 'scripts', 'part-meta.json'), 'utf8'));
const SIZES = ['70', '100', '200'];

function parseStl(buf) {
  const n = buf.readUInt32LE(80);
  const binary = 84 + n * 50 === buf.length;
  const tri = [];
  if (binary) {
    for (let i = 0; i < n; i++) {
      const o = 84 + i * 50 + 12;
      for (let k = 0; k < 9; k++) tri.push(buf.readFloatLE(o + k * 4));
    }
  } else {
    const re = /vertex\s+(\S+)\s+(\S+)\s+(\S+)/g;
    const t = buf.toString('utf8');
    let m;
    while ((m = re.exec(t))) tri.push(+m[1], +m[2], +m[3]);
  }
  return tri;
}

function weld(tri) {
  const map = new Map();
  const pos = [];
  const idx = new Uint32Array(tri.length / 3);
  const q = 1e4;
  for (let i = 0; i < tri.length / 3; i++) {
    const x = tri[i * 3], y = tri[i * 3 + 1], z = tri[i * 3 + 2];
    const key = `${Math.round(x * q)},${Math.round(y * q)},${Math.round(z * q)}`;
    let j = map.get(key);
    if (j === undefined) { j = pos.length / 3; map.set(key, j); pos.push(x, y, z); }
    idx[i] = j;
  }
  // drop degenerate triangles
  const keep = [];
  for (let i = 0; i < idx.length; i += 3) if (idx[i] !== idx[i + 1] && idx[i + 1] !== idx[i + 2] && idx[i] !== idx[i + 2]) keep.push(idx[i], idx[i + 1], idx[i + 2]);
  return { pos: new Float32Array(pos), idx: Uint32Array.from(keep) };
}

function glb({ pos, idx }, name) {
  const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
  for (let i = 0; i < pos.length; i += 3) for (let k = 0; k < 3; k++) { min[k] = Math.min(min[k], pos[i + k]); max[k] = Math.max(max[k], pos[i + k]); }
  const idxBytes = Buffer.from(idx.buffer, idx.byteOffset, idx.byteLength);
  const posBytes = Buffer.from(pos.buffer, pos.byteOffset, pos.byteLength);
  const bin = Buffer.concat([idxBytes, posBytes]);
  const json = {
    asset: { version: '2.0', generator: 'openpatch-site/prepare-models' },
    scene: 0, scenes: [{ nodes: [0] }], nodes: [{ mesh: 0, name }],
    meshes: [{ name, primitives: [{ attributes: { POSITION: 1 }, indices: 0 }] }],
    accessors: [
      { bufferView: 0, componentType: 5125, count: idx.length, type: 'SCALAR' },
      { bufferView: 1, componentType: 5126, count: pos.length / 3, type: 'VEC3', min, max },
    ],
    bufferViews: [{ buffer: 0, byteOffset: 0, byteLength: idxBytes.length, target: 34963 }, { buffer: 0, byteOffset: idxBytes.length, byteLength: posBytes.length, target: 34962 }],
    buffers: [{ byteLength: bin.length }],
  };
  let js = Buffer.from(JSON.stringify(json));
  js = Buffer.concat([js, Buffer.alloc((4 - (js.length % 4)) % 4, 0x20)]);
  const binPad = Buffer.concat([bin, Buffer.alloc((4 - (bin.length % 4)) % 4)]);
  const head = Buffer.alloc(12);
  head.writeUInt32LE(0x46546c67, 0); head.writeUInt32LE(2, 4); head.writeUInt32LE(12 + 8 + js.length + 8 + binPad.length, 8);
  const c1 = Buffer.alloc(8); c1.writeUInt32LE(js.length, 0); c1.writeUInt32LE(0x4e4f534a, 4);
  const c2 = Buffer.alloc(8); c2.writeUInt32LE(binPad.length, 0); c2.writeUInt32LE(0x004e4942, 4);
  return { buf: Buffer.concat([head, c1, js, c2, binPad]), min, max };
}

rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
const manifest = { source: 'stl-fallback', generated: new Date().toISOString().slice(0, 10), sizes: {}, catalog: null, assembly: null, catalogNote: '' };

// ---- 1. generated CAD parts
let nStl = 0;
for (const size of SIZES) {
  const parts = [];
  for (const key of meta.order) {
    const cands = [join(repo, 'mechanical', 'out', 'bench', `OP-${size}_${key}.stl`), join(repo, 'mechanical', 'out', `OP-${size}_${key}.stl`)];
    const src = cands.find(existsSync);
    if (!src) continue;
    const mesh = weld(parseStl(readFileSync(src)));
    if (!mesh.idx.length) continue;
    const { buf, min, max } = glb(mesh, `OP-${size}_${key}`);
    mkdirSync(join(dst, `OP-${size}`), { recursive: true });
    writeFileSync(join(dst, `OP-${size}`, `${key}.glb`), buf);
    const m = meta.parts[key] ?? {};
    parts.push({
      id: `OP-${size}_${key}`, key, name: m.name ?? key, category: m.category ?? 'part', process: m.process ?? '', lockNo: m.lock ?? null, note: m.note ?? '',
      partNumber: `OP-${size}_${key}`, vendor: 'in-house CAD (mechanical/generate.py)', model: 'generated envelope, not vendor-accurate',
      url: `models/OP-${size}/${key}.glb`, bytes: buf.length, bbox: max.map((v, i) => +(v - min[i]).toFixed(2)), tris: mesh.idx.length / 3,
    });
    nStl++;
  }
  if (parts.length) manifest.sizes[size] = { parts };
}

// ---- 2. vendor-accurate component catalogue (optional, produced by the components agent)
const catPath = join(repo, 'mechanical', 'components', 'catalog.json');
if (existsSync(catPath)) {
  try {
    const raw = JSON.parse(readFileSync(catPath, 'utf8'));
    // Real shape (mechanical/components/README.md): { <id>: { title, files:{glb,step,stl,png}, size_mm, bbox_mm, material, source, confidence, notes, used_for, ... } }
    const isIdMap = !Array.isArray(raw) && Object.values(raw).every((v) => v && typeof v === 'object' && !Array.isArray(v)) && Object.values(raw).some((v) => v.files || v.title);
    const list = Array.isArray(raw) ? raw : isIdMap ? Object.entries(raw).map(([id, v]) => ({ id, ...v })) : raw.components ?? raw.parts ?? Object.entries(raw.items ?? {}).map(([id, v]) => ({ id, ...v }));
    const cdir = dirname(catPath);
    mkdirSync(join(dst, 'components'), { recursive: true });
    const copyModel = (rel) => {
      if (!rel || /^https?:/.test(rel)) return rel ?? null;
      const f = join(cdir, rel);
      if (!existsSync(f)) return null;
      const out = join(dst, 'components', basename(f));
      copyFileSync(f, out);
      if (extname(f) === '.gltf') { // copy external buffers/textures next to it
        try {
          const g = JSON.parse(readFileSync(f, 'utf8'));
          for (const r of [...(g.buffers ?? []), ...(g.images ?? [])]) if (r.uri && !r.uri.startsWith('data:')) { const s = join(dirname(f), r.uri); if (existsSync(s)) copyFileSync(s, join(dst, 'components', basename(s))); }
        } catch { /* ignore */ }
      }
      return `models/components/${basename(f)}`;
    };
    const pick = (o, ...k) => k.map((x) => o[x]).find((v) => v !== undefined && v !== null && v !== '');
    manifest.catalog = list.map((c, i) => ({
      id: String(pick(c, 'id', 'key', 'ref', 'name') ?? `component-${i}`),
      name: pick(c, 'title', 'name', 'description') ?? '',
      partNumber: pick(c, 'mpn', 'part_number', 'partNumber', 'pn', 'manufacturer_pn') ?? '',
      vendor: pick(c, 'manufacturer', 'vendor', 'brand', 'supplier') ?? '',
      category: pick(c, 'category', 'type', 'group') ?? 'component',
      lockNo: pick(c, 'lock_no', 'lockNo', 'lock', 'parts_lock') ?? (/PARTS-LOCK #(\d+)/.exec(c.used_for ?? '')?.[1] ? Number(/PARTS-LOCK #(\d+)/.exec(c.used_for)[1]) : null),
      datasheet: pick(c, 'datasheet', 'datasheet_url', 'datasheetUrl', 'url') ?? '',
      dims: pick(c, 'dims_mm', 'dimensions_mm', 'dims', 'size_mm') ?? null,
      confidence: c.confidence ?? '', material: c.material ?? '', usedFor: c.used_for ?? '', frame: c.frame ?? '', mass: c.mass_g_estimate ?? null,
      position: pick(c, 'position_mm', 'position', 'origin_mm') ?? null,
      verified: pick(c, 'verified', 'vendor_accurate', 'status') ?? null,
      source: pick(c, 'source', 'drawing', 'reference') ?? '',
      note: pick(c, 'note', 'notes', 'remark') ?? '',
      url: copyModel(c.files?.glb ?? pick(c, 'gltf', 'glb', 'model', 'file', 'path')),
    }));
    manifest.source = 'catalog';
    manifest.catalogNote = `${manifest.catalog.length} components from mechanical/components/catalog.json`;
  } catch (e) { console.warn('prepare-models: catalog.json unreadable:', e.message); }
}

// assembly glTF: components dir first, then bench output
const asmDirs = [...(process.env.OP_ASSEMBLY_DIR ? [process.env.OP_ASSEMBLY_DIR] : []), join(repo, 'mechanical', 'components'), join(repo, 'mechanical', 'out', 'bench'), join(repo, 'mechanical', 'out')];
for (const d of asmDirs) {
  if (!existsSync(d) || manifest.assembly) continue;
  const f = readdirSync(d).filter((n) => /assembly.*\.(glb|gltf)$/i.test(n) && !/^bench_pod_board/.test(n)).sort()[0];
  if (f) {
    mkdirSync(join(dst, 'components'), { recursive: true });
    copyFileSync(join(d, f), join(dst, 'components', f));
    if (/\.gltf$/i.test(f)) { try { const g = JSON.parse(readFileSync(join(d, f), 'utf8')); for (const r of g.buffers ?? []) if (r.uri && !r.uri.startsWith('data:') && existsSync(join(d, r.uri))) copyFileSync(join(d, r.uri), join(dst, 'components', basename(r.uri))); } catch { /* ignore */ } }
    manifest.assembly = { url: `models/components/${f}`, bytes: statSync(join(dst, 'components', f)).size, from: join('mechanical', d.split('mechanical')[1] ?? '', f).replace(/\\/g, '/') };
    manifest.source = manifest.source === 'catalog' ? 'catalog+assembly' : 'assembly';
  }
}

writeFileSync(join(dst, 'manifest.json'), JSON.stringify(manifest));
console.log(`prepare-models: ${nStl} CAD parts -> glb, catalog: ${manifest.catalog ? manifest.catalog.length : 'none'}, assembly: ${manifest.assembly ? manifest.assembly.url : 'none'}`);
