import {
  CanvasTexture,
  DirectionalLight,
  Group,
  MathUtils,
  Mesh,
  MeshBasicMaterial,
  NeutralToneMapping,
  PerspectiveCamera,
  PlaneGeometry,
  PMREMGenerator,
  Scene,
  Vector3,
  WebGLRenderer,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { fmt, type SizeId } from '../lib/sizes';
import { onSize } from '../lib/state';
import { prefersReducedMotion } from '../lib/ui';
import { getPod } from './models';
import { EXPLODE_OFFSET, PART_LABEL, type PartId, type PodModel } from './types';

interface Label {
  readonly el: HTMLLIElement;
  readonly anchor: () => Vector3 | undefined;
  readonly mode: 'explode' | 'assembled';
  readonly text?: (m: PodModel) => string;
  readonly nudge: number;
}

const FOV = 28;
/** Vertikaler Pixel-Versatz einzelner Beschriftungen, damit sie sich nicht überlappen. */
const NUDGE: Partial<Record<PartId, number>> = { reservoir: 26, plunger: -16, motor: 8 };
const HOME_AZIMUTH = MathUtils.degToRad(38);
const HOME_POLAR = MathUtils.degToRad(58);

function shadowTexture(): CanvasTexture {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const ctx = c.getContext('2d')!;
  const g = ctx.createRadialGradient(128, 128, 8, 128, 128, 128);
  g.addColorStop(0, 'rgba(0,0,0,0.55)');
  g.addColorStop(0.45, 'rgba(0,0,0,0.22)');
  g.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 256, 256);
  const t = new CanvasTexture(c);
  t.colorSpace = 'srgb';
  return t;
}

export async function initStage(): Promise<void> {
  const host = document.getElementById('stage') as HTMLElement;
  const canvas = document.getElementById('stage-canvas') as HTMLCanvasElement;
  const labelHost = document.getElementById('part-labels') as HTMLUListElement;
  const explodeBtn = document.getElementById('explode-toggle') as HTMLButtonElement;
  const resetBtn = document.getElementById('reset-view') as HTMLButtonElement;
  const sourceEl = document.getElementById('stage-source') as HTMLElement;
  const fallback = document.getElementById('stage-fallback') as HTMLElement;

  let renderer: WebGLRenderer;
  try {
    renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (err) {
    console.warn('[OpenPatch] WebGL nicht verfügbar', err);
    canvas.hidden = true;
    fallback.hidden = false;
    explodeBtn.disabled = true;
    resetBtn.disabled = true;
    return;
  }

  const reduced = prefersReducedMotion();
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = NeutralToneMapping;
  renderer.toneMappingExposure = 1.0;

  const scene = new Scene();
  const pmrem = new PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.85;
  const key = new DirectionalLight(0xffffff, 1.4);
  key.position.set(40, 90, 30);
  scene.add(key);

  const camera = new PerspectiveCamera(FOV, 1, 1, 600);
  const controls = new OrbitControls(camera, canvas);
  controls.enablePan = false;
  controls.enableDamping = !reduced;
  controls.dampingFactor = 0.07;
  controls.minDistance = 40;
  controls.maxDistance = 260;
  controls.minPolarAngle = MathUtils.degToRad(8);
  controls.maxPolarAngle = MathUtils.degToRad(88);
  controls.autoRotate = !reduced;
  controls.autoRotateSpeed = 0.9;

  const shadow = new Mesh(
    new PlaneGeometry(1, 1),
    new MeshBasicMaterial({ map: shadowTexture(), transparent: true, depthWrite: false, opacity: 0.8 }),
  );
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = -0.35;
  shadow.renderOrder = -1;
  scene.add(shadow);

  const holder = new Group();
  scene.add(holder);

  let model: PodModel | null = null;
  let explode = 0;
  let explodeTarget = 0;
  let lastBase = 110;
  let visible = true;
  let raf = 0;
  let dirty = true;
  const labels: Label[] = [];

  /* ------- Kamera ------- */
  const baseDistance = (): number => {
    const m = model;
    const radius = (m ? Math.max(m.length / 2 + 6, m.width / 2 + 8) : 30) * (1 + 0.35 * explode);
    const aspect = camera.aspect;
    const hfov = 2 * Math.atan(Math.tan(MathUtils.degToRad(FOV) / 2) * aspect);
    const byWidth = radius / Math.tan(hfov / 2);
    const byHeight = (radius * (0.62 + 0.55 * explode)) / Math.tan(MathUtils.degToRad(FOV) / 2);
    return Math.max(byWidth, byHeight) * 1.08;
  };

  const placeCamera = (): void => {
    const target = new Vector3(0, MathUtils.lerp(4, 24, explode), 0);
    const off = camera.position.clone().sub(controls.target);
    const base = baseDistance();
    off.multiplyScalar(base / lastBase);
    lastBase = base;
    controls.target.copy(target);
    camera.position.copy(target).add(off);
  };

  const homeCamera = (): void => {
    const base = baseDistance();
    lastBase = base;
    const target = new Vector3(0, MathUtils.lerp(4, 24, explode), 0);
    controls.target.copy(target);
    camera.position.set(
      target.x + base * Math.sin(HOME_POLAR) * Math.sin(HOME_AZIMUTH),
      target.y + base * Math.cos(HOME_POLAR),
      target.z + base * Math.sin(HOME_POLAR) * Math.cos(HOME_AZIMUTH),
    );
    controls.update();
    dirty = true;
  };

  /* ------- Beschriftungen ------- */
  const makeLabel = (text: string, anchor: () => Vector3 | undefined, mode: Label['mode'], extra = '', textFn?: Label['text'], nudge = 0): void => {
    const li = document.createElement('li');
    const span = document.createElement('span');
    span.textContent = text;
    li.append(span);
    if (extra) li.className = extra;
    labelHost.append(li);
    labels.push({ el: li, anchor, mode, text: textFn, nudge });
  };

  const SIDE: Record<PartId, string> = { base: 'left', battery: 'right', pcb: 'right', motor: 'right', reservoir: 'left', plunger: 'left', lid: 'right' };
  (Object.keys(PART_LABEL) as PartId[]).forEach((id) => {
    makeLabel(PART_LABEL[id], () => model?.anchors.get(id)?.clone().setY((model.anchors.get(id)?.y ?? 0) + EXPLODE_OFFSET[id] * explode), 'explode', SIDE[id], undefined, NUDGE[id] ?? 0);
  });
  const dimAnchor = (fn: (m: PodModel) => Vector3) => (): Vector3 | undefined => (model ? fn(model) : undefined);
  makeLabel('H 8,5 mm', dimAnchor((m) => new Vector3(m.length / 2, m.height / 2, m.width / 2)), 'assembled', 'right dim-label');
  makeLabel('L', dimAnchor((m) => new Vector3(0, 0, m.width / 2)), 'assembled', 'right dim-label', (m) => `L ${fmt(Math.round(m.length * 10) / 10)} mm`);
  makeLabel('B 32 mm', dimAnchor((m) => new Vector3(m.length / 2, 0, 0)), 'assembled', 'right dim-label', (m) => `B ${fmt(Math.round(m.width * 10) / 10)} mm`);

  const tmp = new Vector3();
  const updateLabels = (): void => {
    const w = host.clientWidth;
    const h = host.clientHeight;
    const showExplode = explode > 0.85;
    const showAssembled = explode < 0.05;
    for (const l of labels) {
      const a = l.anchor();
      const show = a && (l.mode === 'explode' ? showExplode : showAssembled);
      l.el.classList.toggle('on', Boolean(show));
      if (!a) continue;
      tmp.copy(a).project(camera);
      const x = (tmp.x * 0.5 + 0.5) * w;
      const y = (-tmp.y * 0.5 + 0.5) * h;
      const left = l.el.classList.contains('left');
      const ownW = l.el.offsetWidth;
      l.el.style.transform = `translate3d(${(left ? x - ownW : x - 3.5).toFixed(1)}px, ${(y - 7 + l.nudge).toFixed(1)}px, 0)`;
    }
  };

  /* ------- Modell ------- */
  const applyExplode = (): void => {
    if (!model) return;
    model.parts.forEach((obj, id) => {
      obj.position.y = EXPLODE_OFFSET[id] * explode;
    });
  };

  let loadToken = 0;
  const showSize = async (id: SizeId): Promise<void> => {
    const token = ++loadToken;
    const next = await getPod(id);
    if (token !== loadToken) return;
    holder.clear();
    model = next;
    holder.add(next.group);
    for (const l of labels) if (l.text) l.el.firstElementChild!.textContent = l.text(next);
    shadow.scale.set(next.length + 34, next.width + 34, 1);
    explodeBtn.disabled = !next.explodable;
    explodeBtn.title = next.explodable ? '' : 'Explosionsansicht braucht Einzelteile in mechanical/out/';
    if (!next.explodable && explodeTarget > 0) setExplode(false);
    sourceEl.textContent =
      next.source === 'stl'
        ? `CAD-Modell: mechanical/out · ${id}`
        : next.source === 'hybrid'
          ? `Gehäuse: CAD-STL · Innenleben: Layout-Modell · ${id}`
          : `Platzhalter-Modell aus Spezifikation · ${id}`;
    applyExplode();
    placeCamera();
    dirty = true;
  };

  const setExplode = (on: boolean): void => {
    explodeTarget = on ? 1 : 0;
    explodeBtn.setAttribute('aria-pressed', String(on));
    if (reduced) {
      explode = explodeTarget;
      applyExplode();
      placeCamera();
    }
    controls.autoRotate = false;
    dirty = true;
  };

  /* ------- Eingaben ------- */
  explodeBtn.addEventListener('click', () => setExplode(explodeTarget === 0));
  resetBtn.addEventListener('click', () => {
    homeCamera();
    controls.autoRotate = !reduced && explodeTarget === 0;
  });
  controls.addEventListener('start', () => {
    controls.autoRotate = false;
  });
  controls.addEventListener('change', () => {
    dirty = true;
  });

  canvas.addEventListener('keydown', (e) => {
    const step = MathUtils.degToRad(9);
    const off = camera.position.clone().sub(controls.target);
    let handled = true;
    switch (e.key) {
      case 'ArrowLeft':
      case 'ArrowRight': {
        const a = e.key === 'ArrowLeft' ? step : -step;
        const x = off.x * Math.cos(a) - off.z * Math.sin(a);
        const z = off.x * Math.sin(a) + off.z * Math.cos(a);
        off.x = x;
        off.z = z;
        break;
      }
      case 'ArrowUp':
      case 'ArrowDown': {
        const r = off.length();
        const polar = MathUtils.clamp(Math.acos(off.y / r) + (e.key === 'ArrowUp' ? -step : step), controls.minPolarAngle, controls.maxPolarAngle);
        const az = Math.atan2(off.x, off.z);
        off.set(r * Math.sin(polar) * Math.sin(az), r * Math.cos(polar), r * Math.sin(polar) * Math.cos(az));
        break;
      }
      case '+':
      case '=':
        off.multiplyScalar(0.88);
        break;
      case '-':
      case '_':
        off.multiplyScalar(1.14);
        break;
      default:
        handled = false;
    }
    if (!handled) return;
    e.preventDefault();
    controls.autoRotate = false;
    off.setLength(MathUtils.clamp(off.length(), controls.minDistance, controls.maxDistance));
    camera.position.copy(controls.target).add(off);
    dirty = true;
  });

  const resize = (): void => {
    const w = Math.max(1, host.clientWidth);
    const h = Math.max(1, host.clientHeight);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    placeCamera();
    dirty = true;
  };
  new ResizeObserver(resize).observe(host);

  new IntersectionObserver(
    (entries) => {
      visible = entries[0]?.isIntersecting ?? true;
      if (visible) schedule();
    },
    { threshold: 0 },
  ).observe(host);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) schedule();
  });

  /* ------- Schleife ------- */
  const tick = (): void => {
    raf = 0;
    if (!visible || document.hidden) return;
    if (Math.abs(explode - explodeTarget) > 0.0005) {
      explode += (explodeTarget - explode) * (reduced ? 1 : 0.085);
      if (Math.abs(explode - explodeTarget) <= 0.0005) explode = explodeTarget;
      applyExplode();
      placeCamera();
      dirty = true;
    }
    const moved = controls.update();
    if (dirty || moved || controls.autoRotate) {
      renderer.render(scene, camera);
      updateLabels();
      dirty = false;
    }
    schedule();
  };
  const schedule = (): void => {
    if (!raf) raf = requestAnimationFrame(tick);
  };

  onSize((id) => {
    void showSize(id);
  });
  resize();
  homeCamera();
  schedule();

  window.addEventListener('op-theme', () => {
    dirty = true;
  });
}
