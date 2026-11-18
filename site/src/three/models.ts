import { Box3, BufferGeometry, Group, Mesh, MeshPhysicalMaterial, MeshStandardMaterial, Object3D, Vector3 } from 'three';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { SIZES, type SizeId } from '../lib/sizes';
import { buildProceduralPod } from './pod';
import type { CadLayout, PartId, PodModel } from './types';

interface ManifestEntry {
  file: string;
  size: SizeId | null;
  part: PartId | 'assembly';
}

const PART_IDS: readonly string[] = ['base', 'battery', 'pcb', 'motor', 'reservoir', 'plunger', 'lid', 'assembly'];

const baseUrl = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;

let manifestPromise: Promise<Manifest> | null = null;

interface Manifest {
  entries: ManifestEntry[];
  layouts: Partial<Record<SizeId, CadLayout>>;
}

const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

function parseLayout(raw: unknown): CadLayout | null {
  if (typeof raw !== 'object' || raw === null) return null;
  const r = raw as Record<string, unknown>;
  const need = ['length', 'width', 'x_r0', 'x_r1', 'x_end', 'bat_x', 'y_r', 'y_s', 'y_m', 'z_axis', 'z_top_inner', 'coil_cx', 'coil_cy'];
  return need.every((k) => isNum(r[k])) ? (r as unknown as CadLayout) : null;
}

function parseManifest(raw: unknown): Manifest {
  const empty: Manifest = { entries: [], layouts: {} };
  if (typeof raw !== 'object' || raw === null) return empty;
  const obj = raw as { models?: unknown; layouts?: unknown };
  const entries: ManifestEntry[] = [];
  for (const m of Array.isArray(obj.models) ? obj.models : []) {
    if (typeof m !== 'object' || m === null) continue;
    const { file, size, part } = m as Record<string, unknown>;
    if (typeof file !== 'string' || typeof part !== 'string' || !PART_IDS.includes(part)) continue;
    if (size !== null && !(typeof size === 'string' && size in SIZES)) continue;
    entries.push({ file, size: size as SizeId | null, part: part as ManifestEntry['part'] });
  }
  const layouts: Manifest['layouts'] = {};
  if (typeof obj.layouts === 'object' && obj.layouts !== null) {
    for (const id of Object.keys(SIZES) as SizeId[]) {
      const l = parseLayout((obj.layouts as Record<string, unknown>)[id]);
      if (l) layouts[id] = l;
    }
  }
  return { entries, layouts };
}

function loadManifest(): Promise<Manifest> {
  manifestPromise ??= fetch(`${baseUrl}models/manifest.json`, { cache: 'no-cache' })
    .then((r) => (r.ok ? r.json() : null))
    .then(parseManifest)
    .catch(() => ({ entries: [], layouts: {} }) as Manifest);
  return manifestPromise;
}

const stlMaterials: Record<PartId, () => MeshStandardMaterial | MeshPhysicalMaterial> = {
  base: () => new MeshStandardMaterial({ color: 0x2b2a27, roughness: 0.55 }),
  lid: () => new MeshPhysicalMaterial({ color: 0xf4f2ed, roughness: 0.36, clearcoat: 0.5 }),
  pcb: () => new MeshStandardMaterial({ color: 0x15382d, roughness: 0.45 }),
  battery: () => new MeshStandardMaterial({ color: 0xc4cad2, roughness: 0.4, metalness: 0.55 }),
  motor: () => new MeshStandardMaterial({ color: 0xbfc2c6, roughness: 0.28, metalness: 0.9 }),
  reservoir: () => new MeshPhysicalMaterial({ color: 0xdfe9f2, roughness: 0.08, transparent: true, opacity: 0.35, depthWrite: false }),
  plunger: () => new MeshStandardMaterial({ color: 0xff5a24, roughness: 0.45 }),
};

const loader = new STLLoader();

const loadStl = (file: string): Promise<BufferGeometry> =>
  new Promise((resolve, reject) => loader.load(`${baseUrl}models/${encodeURIComponent(file)}`, resolve, undefined, reject));

/** Baut ein Modell aus STL-Dateien (CAD ist Z-oben, Three.js Y-oben). */
async function buildStlPod(entries: ManifestEntry[]): Promise<PodModel> {
  const geos = await Promise.all(entries.map((e) => loadStl(e.file)));
  const group = new Group();
  const parts = new Map<PartId, Object3D>();
  const isAssembly = entries.every((e) => e.part === 'assembly');

  entries.forEach((entry, i) => {
    const geo = geos[i]!;
    geo.rotateX(-Math.PI / 2);
    geo.computeVertexNormals();
    const partId: PartId = entry.part === 'assembly' ? 'base' : entry.part;
    const material = isAssembly
      ? new MeshPhysicalMaterial({ color: 0xf4f2ed, roughness: 0.4, clearcoat: 0.4 })
      : stlMaterials[partId]();
    const holder = parts.get(partId) ?? new Group();
    holder.add(new Mesh(geo, material));
    parts.set(partId, holder);
  });
  parts.forEach((p, pid) => {
    p.name = pid;
    group.add(p);
  });

  const box = new Box3().setFromObject(group);
  const size = box.getSize(new Vector3());
  const center = box.getCenter(new Vector3());
  group.position.set(-center.x, -box.min.y, -center.z);
  const wrap = new Group();
  wrap.add(group);

  const anchors = new Map<PartId, Vector3>();
  parts.forEach((p, pid) => {
    const b = new Box3().setFromObject(p);
    const c = b.getCenter(new Vector3()).add(group.position);
    anchors.set(pid, new Vector3(c.x, b.max.y + group.position.y, c.z));
  });

  return { group: wrap, parts, anchors, source: 'stl', explodable: !isAssembly, length: size.x, width: size.z, height: size.y };
}

/**
 * Hybrid: echte Gehäuse-STL (Boden/Deckel) aus dem CAD + Innenleben prozedural
 * an den Positionen aus layout.json. So bleibt die Explosionsansicht vollständig.
 */
async function buildHybridPod(id: SizeId, shells: ManifestEntry[], cad: CadLayout | undefined): Promise<PodModel> {
  const model = buildProceduralPod(SIZES[id], cad);
  const geos = await Promise.all(shells.map((e) => loadStl(e.file)));
  const union = new Box3();
  geos.forEach((g) => {
    g.rotateX(-Math.PI / 2);
    g.computeBoundingBox();
    union.union(g.boundingBox!);
  });
  const c = union.getCenter(new Vector3());
  const byPart = new Map<PartId, Group>();
  shells.forEach((e, i) => {
    const g = geos[i]!;
    g.translate(-c.x, -union.min.y, -c.z);
    g.computeVertexNormals();
    const pid = e.part as PartId;
    const holder = byPart.get(pid) ?? new Group();
    holder.add(new Mesh(g, stlMaterials[pid]()));
    byPart.set(pid, holder);
  });
  byPart.forEach((holder, pid) => {
    const old = model.parts.get(pid);
    if (old) {
      model.group.remove(old);
      old.traverse((o) => {
        if (o instanceof Mesh) o.geometry.dispose();
      });
    }
    holder.name = pid;
    model.group.add(holder);
    (model.parts as Map<PartId, Object3D>).set(pid, holder);
  });
  return model;
}

const cache = new Map<SizeId, PodModel>();

export async function getPod(id: SizeId): Promise<PodModel> {
  const hit = cache.get(id);
  if (hit) return hit;
  let model: PodModel;
  try {
    const { entries, layouts } = await loadManifest();
    const mine = entries.filter((m) => m.size === id || m.size === null);
    const shells = mine.filter((m) => m.part === 'base' || m.part === 'lid');
    const assembly = mine.filter((m) => m.part === 'assembly' && m.size === id);
    if (shells.length) model = await buildHybridPod(id, shells, layouts[id]);
    else if (assembly.length) model = await buildStlPod(assembly);
    else model = buildProceduralPod(SIZES[id], layouts[id]);
  } catch (err) {
    console.warn('[OpenPatch] STL-Laden fehlgeschlagen, nutze Platzhalter', err);
    model = buildProceduralPod(SIZES[id]);
  }
  cache.set(id, model);
  return model;
}
