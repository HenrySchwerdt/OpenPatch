import {
  BoxGeometry,
  BufferGeometry,
  CylinderGeometry,
  EdgesGeometry,
  ExtrudeGeometry,
  Group,
  LineBasicMaterial,
  LineSegments,
  Mesh,
  MeshPhysicalMaterial,
  MeshStandardMaterial,
  Object3D,
  Path,
  Shape,
  Vector3,
} from 'three';
import type { SizeSpec } from '../lib/sizes';
import type { CadLayout, PartId, PodModel } from './types';

/** Prozedurales Platzhalter-Modell aus den Maßen in spec/design-parameters.md. */

const WALL = 0.9;
const FLOOR = 0.9;
const LID_BOTTOM = 7.3;
const CORNER = 9;

const mat = {
  lid: () => new MeshPhysicalMaterial({ color: 0xf4f2ed, roughness: 0.36, clearcoat: 0.5, clearcoatRoughness: 0.35 }),
  base: () => new MeshStandardMaterial({ color: 0x2b2a27, roughness: 0.55, metalness: 0.05 }),
  klett: () => new MeshStandardMaterial({ color: 0x6c6a65, roughness: 0.95 }),
  pcb: () => new MeshStandardMaterial({ color: 0x15382d, roughness: 0.45, metalness: 0.15 }),
  chip: () => new MeshStandardMaterial({ color: 0x161616, roughness: 0.4, metalness: 0.3 }),
  copper: () => new MeshStandardMaterial({ color: 0xc7773d, roughness: 0.35, metalness: 0.9 }),
  battery: () => new MeshStandardMaterial({ color: 0xc4cad2, roughness: 0.4, metalness: 0.55 }),
  signal: () => new MeshStandardMaterial({ color: 0xff5a24, roughness: 0.45 }),
  metal: () => new MeshStandardMaterial({ color: 0xbfc2c6, roughness: 0.28, metalness: 0.9 }),
  brass: () => new MeshStandardMaterial({ color: 0xc9a24a, roughness: 0.35, metalness: 0.85 }),
  rubber: () => new MeshStandardMaterial({ color: 0x1d1d1d, roughness: 0.9 }),
  glass: () => new MeshPhysicalMaterial({ color: 0xdfe9f2, roughness: 0.08, transparent: true, opacity: 0.3, depthWrite: false }),
};

function roundedRect(shape: Shape | Path, w: number, h: number, r: number): void {
  const x = -w / 2;
  const y = -h / 2;
  shape.moveTo(x + r, y);
  shape.lineTo(x + w - r, y);
  shape.absarc(x + w - r, y + r, r, -Math.PI / 2, 0, false);
  shape.lineTo(x + w, y + h - r);
  shape.absarc(x + w - r, y + h - r, r, 0, Math.PI / 2, false);
  shape.lineTo(x + r, y + h);
  shape.absarc(x + r, y + h - r, r, Math.PI / 2, Math.PI, false);
  shape.lineTo(x, y + r);
  shape.absarc(x + r, y + r, r, Math.PI, Math.PI * 1.5, false);
}

const outline = (w: number, h: number, r: number): Shape => {
  const s = new Shape();
  roundedRect(s, w, h, Math.min(r, h / 2, w / 2));
  return s;
};

/** Schiebt Extrusion (Shape-XY, Tiefe Z) auf Pod-Koordinaten: Länge X, Höhe Y, Breite Z. */
function flat(geo: BufferGeometry, y: number): BufferGeometry {
  geo.rotateX(-Math.PI / 2);
  geo.translate(0, y, 0);
  return geo;
}

const extrude = (shape: Shape, depth: number, bevel = 0): ExtrudeGeometry =>
  new ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: bevel > 0,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelSegments: 6,
    curveSegments: 28,
  });

function mesh(geo: BufferGeometry, material: Mesh['material'], name: string): Mesh {
  const m = new Mesh(geo, material);
  m.name = name;
  return m;
}

function box(w: number, h: number, d: number, x: number, y: number, z: number, material: Mesh['material']): Mesh {
  const m = new Mesh(new BoxGeometry(w, h, d), material);
  m.position.set(x, y, z);
  return m;
}

/** Zylinder mit Achse entlang X (Länge) bei (x, y, z). */
function cylX(r: number, len: number, x: number, y: number, z: number, material: Mesh['material']): Mesh {
  const g = new CylinderGeometry(r, r, len, 40);
  g.rotateZ(Math.PI / 2);
  const m = new Mesh(g, material);
  m.position.set(x, y, z);
  return m;
}

function cylY(r: number, h: number, x: number, y: number, z: number, material: Mesh['material']): Mesh {
  const m = new Mesh(new CylinderGeometry(r, r, h, 48), material);
  m.position.set(x, y, z);
  return m;
}

function buildBase(L: number, W: number): Group {
  const g = new Group();
  const floor = mesh(flat(extrude(outline(L - 0.9, W - 0.9, CORNER - 0.45), 0.0001, 0.45), 0.45), mat.base(), 'floor');
  const ring = outline(L, W, CORNER);
  ring.holes.push(((): Path => {
    const p = new Path();
    roundedRect(p, L - 2 * WALL, W - 2 * WALL, CORNER - WALL);
    return p;
  })());
  const wall = mesh(flat(extrude(ring, LID_BOTTOM - FLOOR), FLOOR), mat.base(), 'wall');
  const klett = mesh(flat(extrude(outline(L - 6, W - 6, CORNER - 2), 0.3), -0.3), mat.klett(), 'klett');
  g.add(floor, wall, klett);
  return g;
}

function buildLid(L: number, W: number): Group {
  const g = new Group();
  const bevel = 0.45;
  const geo = extrude(outline(L - 2 * bevel, W - 2 * bevel, CORNER - bevel), 0.0001, bevel);
  flat(geo, LID_BOTTOM + bevel);
  // leichte Wölbung (Kissenform): bis +0,3 mm in der Mitte
  const pos = geo.attributes.position!;
  for (let i = 0; i < pos.count; i++) {
    const nx = pos.getX(i) / (L / 2);
    const nz = pos.getZ(i) / (W / 2);
    pos.setY(i, pos.getY(i) + 0.3 * Math.max(0, 1 - nx * nx) * Math.max(0, 1 - nz * nz));
  }
  pos.needsUpdate = true;
  geo.computeVertexNormals();
  g.add(mesh(geo, mat.lid(), 'lid-shell'));
  const topY = LID_BOTTOM + 2 * bevel + 0.3;
  const button = cylY(2.4, 0.5, L / 2 - 8, topY, -W / 2 + 7.5, mat.signal());
  g.add(button);
  const inlay = cylY(1.9, 0.3, -L / 2 + 6.5, topY - 0.05, W / 2 - 8, mat.base());
  g.add(inlay);
  return g;
}

interface Layout {
  readonly xl: number;
  readonly lres: number;
  readonly gx: number;
  readonly bx0: number;
  readonly bx1: number;
  readonly laneY: number;
  readonly zRes: number;
  readonly zMotor: number;
  readonly zScrew: number;
  readonly coil: { x: number; z: number; r: number };
}

/** Koordinaten aus dem CAD-Layout (x ab Kante, y Breite, z oben) auf Pod-Koordinaten (zentriert). */
function layoutFromCad(L: number, W: number, c: CadLayout): Layout {
  const xl = c.x_r0 - L / 2;
  const lres = c.x_r1 - c.x_r0;
  return {
    xl,
    lres,
    gx: c.gear_x1 !== undefined && c.x_s !== undefined ? c.x_s - L / 2 : xl + lres + 1.5,
    bx0: c.bat_x - L / 2 + 0.2,
    bx1: c.x_end - L / 2,
    laneY: c.z_axis,
    zRes: -(c.y_r - W / 2),
    zMotor: -(c.y_m - W / 2),
    zScrew: -(c.y_s - W / 2),
    coil: { x: c.coil_cx - L / 2, z: -(c.coil_cy - W / 2), r: 8.8 },
  };
}

function layoutFallback(L: number, stroke: number): Layout {
  const xl = -L / 2 + WALL + 0.8;
  const lres = stroke + 3;
  const bx1 = L / 2 - WALL - 0.7;
  return {
    xl, lres, gx: xl + lres + 1.5, bx0: bx1 - 18, bx1, laneY: 3.9, zRes: 6.8, zMotor: -9, zScrew: -3,
    coil: { x: (bx1 - 18 + bx1) / 2 - 1.2, z: -3.4, r: 7.4 },
  };
}

function buildBattery(l: Layout): Group {
  const g = new Group();
  const w = l.bx1 - l.bx0;
  const cx = (l.bx0 + l.bx1) / 2;
  g.add(box(w, 3.2, 27, cx, FLOOR + 1.6, 0, mat.battery()));
  const tab = box(1.2, 3.25, 27.2, cx + w * 0.3, FLOOR + 1.6, 0, mat.signal());
  g.add(tab);
  return g;
}

function buildPcb(l: Layout): Group {
  const g = new Group();
  const w = l.bx1 - l.bx0;
  const cx = (l.bx0 + l.bx1) / 2;
  const y = FLOOR + 3.2 + 0.4 + 0.3;
  g.add(box(w, 0.6, 28.4, cx, y, 0, mat.pcb()));
  const top = y + 0.3;
  g.add(box(6, 0.9, 6, cx + w / 2 - 4.2, top + 0.45, 9.4, mat.chip())); // nRF54L15 QFN48
  g.add(box(3, 0.7, 3, cx + w / 2 - 4.2, top + 0.35, -11, mat.chip())); // STSPIN220
  g.add(box(2.4, 0.6, 1.6, cx - w / 2 + 3, top + 0.3, -3.2, mat.chip())); // TPL5010
  for (let i = 0; i < 5; i++) g.add(box(1, 0.5, 0.5, cx - w / 2 + 2.2 + i * 1.5, top + 0.25, 11.2, mat.brass()));
  g.add(box(2, 0.6, 2, cx - w / 2 + 3, top + 0.3, -9, mat.chip())); // Hall-Sensor
  const coil = new Shape();
  coil.absarc(0, 0, l.coil.r, 0, Math.PI * 2, false);
  const hole = new Path();
  hole.absarc(0, 0, l.coil.r * 0.57, 0, Math.PI * 2, true);
  coil.holes.push(hole);
  const coilGeo = new ExtrudeGeometry(coil, { depth: 0.35, bevelEnabled: false, curveSegments: 48 });
  flat(coilGeo, top);
  const coilMesh = mesh(coilGeo, mat.copper(), 'qi-coil');
  coilMesh.position.set(l.coil.x, 0, l.coil.z);
  g.add(coilMesh);
  return g;
}

function stadium(w: number, h: number): Shape {
  return outline(w, h, h / 2);
}

function buildReservoir(l: Layout): Group {
  const g = new Group();
  const tube = stadium(16 + 1.2, 5 + 1.2);
  const hole = new Path();
  roundedRect(hole, 16, 5, 2.5);
  tube.holes.push(hole);
  const geo = extrude(tube, l.lres);
  geo.rotateY(Math.PI / 2);
  geo.translate(l.xl, l.laneY, l.zRes);
  const shell = mesh(geo, mat.glass(), 'reservoir-shell');
  const edges = new LineSegments(new EdgesGeometry(geo, 35), new LineBasicMaterial({ color: 0x7d868f, transparent: true, opacity: 0.55 }));
  const septum = cylX(2, 2, l.xl - 1.3, l.laneY, l.zRes, mat.rubber());
  g.add(shell, edges, septum);
  return g;
}

function buildPlunger(l: Layout): Group {
  const g = new Group();
  const geo = extrude(stadium(15.8, 4.8), 3, 0);
  geo.rotateY(Math.PI / 2);
  geo.translate(l.xl + l.lres - 4.5, l.laneY, l.zRes);
  g.add(mesh(geo, mat.signal(), 'plunger'));
  g.add(cylX(0.8, l.lres + 0.5, l.xl + (l.lres + 0.5) / 2 - 0.5, l.laneY, l.zScrew, mat.metal()));
  g.add(cylY(2.6, 0.9, l.gx, l.laneY, l.zScrew, mat.brass()));
  const zMid = (l.zRes + l.zScrew) / 2;
  g.add(box(2, 1.2, Math.abs(l.zRes - l.zScrew) + 2, l.xl + l.lres - 3, l.laneY, zMid, mat.signal()));
  return g;
}

function buildMotor(l: Layout): Group {
  const g = new Group();
  const z = l.zMotor;
  g.add(cylX(3, 9, l.gx - 7.2, l.laneY, z, mat.metal()));
  g.add(cylX(3.05, 2, l.gx - 11.6, l.laneY, z, mat.chip()));
  g.add(cylX(2.6, 2.4, l.gx - 1.4, l.laneY, z, mat.brass()));
  g.add(cylY(2.7, 0.9, l.gx, l.laneY, z, mat.brass()));
  return g;
}

/**
 * Pod aus Parametern. Mit `cad` (mechanical/out/*.layout.json) stimmen Längen und Positionen
 * der Innenteile mit dem CAD überein; ohne bleibt es ein Platzhalter aus der Spezifikation.
 */
export function buildProceduralPod(spec: SizeSpec, cad?: CadLayout): PodModel {
  const L = cad?.length ?? spec.length;
  const W = cad?.width ?? spec.width;
  const l = cad ? layoutFromCad(L, W, cad) : layoutFallback(L, spec.stroke);
  const lidBottom = cad ? cad.z_top_inner : LID_BOTTOM;

  const parts = new Map<PartId, Object3D>([
    ['base', buildBase(L, W)],
    ['battery', buildBattery(l)],
    ['pcb', buildPcb(l)],
    ['motor', buildMotor(l)],
    ['reservoir', buildReservoir(l)],
    ['plunger', buildPlunger(l)],
    ['lid', buildLid(L, W)],
  ]);

  const group = new Group();
  group.name = spec.id;
  parts.forEach((p, id) => {
    p.name = id;
    group.add(p);
  });

  const anchors = new Map<PartId, Vector3>([
    ['base', new Vector3(-L / 2 + 3, 1, W / 2 - 1)],
    ['battery', new Vector3(l.bx1 - 2, FLOOR + 3.2, 6)],
    ['pcb', new Vector3(l.bx1 - 3, 6, 9.4)],
    ['motor', new Vector3(l.gx - 7, l.laneY + 3, l.zMotor)],
    ['reservoir', new Vector3(l.xl + 2, l.laneY + 3.3, l.zRes + 8)],
    ['plunger', new Vector3(l.xl + l.lres - 3, l.laneY + 3.3, l.zRes + 8)],
    ['lid', new Vector3(L / 2 - 2, lidBottom + 1.3, -W / 2 + 4)],
  ]);

  return { group, parts, anchors, source: cad ? 'hybrid' : 'procedural', explodable: true, length: L, width: W, height: spec.height };
}
