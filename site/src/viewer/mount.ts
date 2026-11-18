import {
  ACESFilmicToneMapping, AmbientLight, BufferGeometry, CanvasTexture, DirectionalLight, Group, Mesh,
  MeshPhysicalMaterial, PCFSoftShadowMap, PerspectiveCamera, PlaneGeometry, PMREMGenerator, Scene,
  ShadowMaterial, SRGBColorSpace, WebGLRenderer, MathUtils,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { STLLoader } from 'three/addons/loaders/STLLoader.js';
import { toCreasedNormals } from 'three/addons/utils/BufferGeometryUtils.js';

const BASE = import.meta.env.BASE_URL.endsWith('/') ? import.meta.env.BASE_URL : `${import.meta.env.BASE_URL}/`;
const DIMS: Readonly<Record<string, { l: number }>> = { '70': { l: 38 }, '100': { l: 42 }, '200': { l: 55.4 } };
const W = 32;
const H = 8.5;

declare global { interface Window { __opViewer?: { renderer: WebGLRenderer } } }

const loader = new STLLoader();
const cache = new Map<string, BufferGeometry>();
async function loadStl(file: string): Promise<BufferGeometry> {
  const hit = cache.get(file);
  if (hit) return hit;
  const raw = await loader.loadAsync(`${BASE}models/${file}`);
  const geo = toCreasedNormals(raw, MathUtils.degToRad(32));
  raw.dispose();
  cache.set(file, geo);
  return geo;
}

function contactShadowTexture(): CanvasTexture {
  const c = document.createElement('canvas');
  c.width = c.height = 256;
  const g = c.getContext('2d');
  if (g) {
    const grad = g.createRadialGradient(128, 128, 8, 128, 128, 126);
    grad.addColorStop(0, 'rgba(0,0,0,0.55)');
    grad.addColorStop(0.5, 'rgba(0,0,0,0.22)');
    grad.addColorStop(1, 'rgba(0,0,0,0)');
    g.fillStyle = grad;
    g.fillRect(0, 0, 256, 256);
  }
  const t = new CanvasTexture(c);
  t.colorSpace = SRGBColorSpace;
  return t;
}

export async function mountViewer(root: HTMLElement, reducedMotion: boolean): Promise<void> {
  const canvas = root.querySelector<HTMLCanvasElement>('.viewer-canvas');
  const ui = root.querySelector<HTMLElement>('.viewer-ui');
  const status = root.querySelector<HTMLElement>('.viewer-status');
  if (!canvas || !ui) throw new Error('viewer markup missing');
  canvas.hidden = false;

  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = PCFSoftShadowMap;
  window.__opViewer = { renderer };

  const scene = new Scene();
  const pmrem = new PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environmentIntensity = 0.9;
  scene.add(new AmbientLight(0xffffff, 0.15));
  const key = new DirectionalLight(0xffffff, 1.6);
  key.position.set(-40, 90, 60);
  key.castShadow = true;
  key.shadow.mapSize.set(1024, 1024);
  key.shadow.radius = 8;
  key.shadow.bias = -0.0004;
  Object.assign(key.shadow.camera, { left: -60, right: 60, top: 60, bottom: -60, near: 10, far: 260 });
  scene.add(key);

  const camera = new PerspectiveCamera(28, 1, 10, 800);
  camera.position.set(-70, 62, 96);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 70;
  controls.maxDistance = 220;
  controls.maxPolarAngle = Math.PI * 0.49;
  controls.enablePan = false;
  controls.autoRotate = !reducedMotion;
  controls.autoRotateSpeed = 0.9;
  controls.target.set(0, 4, 0);
  canvas.tabIndex = 0;
  controls.listenToKeyEvents(canvas);
  controls.addEventListener('start', () => { controls.autoRotate = false; });

  const shell = new MeshPhysicalMaterial({ color: 0xf1f0ed, roughness: 0.58, metalness: 0, clearcoat: 0.08, clearcoatRoughness: 0.6, sheen: 0.4, sheenRoughness: 0.8, sheenColor: 0xffffff });
  const ground = new Mesh(new PlaneGeometry(260, 260), new ShadowMaterial({ opacity: 0.32 }));
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);
  const contact = new Mesh(
    new PlaneGeometry(1, 1),
    new MeshPhysicalMaterial({ map: contactShadowTexture(), transparent: true, depthWrite: false, color: 0x000000, roughness: 1 }),
  );
  contact.rotation.x = -Math.PI / 2;
  contact.position.y = 0.02;
  scene.add(contact);

  const pod = new Group();
  scene.add(pod);

  let current = '';
  async function show(size: string): Promise<void> {
    if (size === current || !DIMS[size]) return;
    current = size;
    if (status) status.textContent = 'Loading model…';
    const [bottom, top] = await Promise.all([loadStl(`OP-${size}_bottom.stl`), loadStl(`OP-${size}_top.stl`)]);
    if (size !== current) return;
    pod.clear();
    for (const g of [bottom, top]) {
      const m = new Mesh(g, shell);
      m.castShadow = true;
      m.receiveShadow = true;
      pod.add(m);
    }
    const { l } = DIMS[size];
    // CAD: x length, y width, z height. three.js: y up, so rotate -90deg about X and centre on the footprint.
    pod.rotation.x = -Math.PI / 2;
    pod.position.set(-l / 2, 0, W / 2);
    contact.scale.set(l * 1.55, W * 1.9, 1);
    contact.position.set(0, 0.02, 0);
    controls.target.set(0, H / 2, 0);
    if (status) status.textContent = '';
    renderer.domElement.dataset.size = size;
    wake();
  }

  let visible = true;
  let raf = 0;
  const resize = (): void => {
    const { clientWidth: w, clientHeight: h } = canvas;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.fov = w / h < 1 ? 42 : 28;
    camera.updateProjectionMatrix();
  };
  const tick = (): void => {
    raf = 0;
    if (!visible) return;
    controls.update();
    renderer.render(scene, camera);
    raf = requestAnimationFrame(tick);
  };
  function wake(): void { if (!raf && visible) raf = requestAnimationFrame(tick); }
  new ResizeObserver(() => { resize(); wake(); }).observe(canvas);
  new IntersectionObserver((e) => { visible = e.some((x) => x.isIntersecting); wake(); }).observe(root);
  resize();

  ui.hidden = false;
  const buttons = [...ui.querySelectorAll<HTMLButtonElement>('[data-vsize]')];
  for (const b of buttons) {
    b.addEventListener('click', () => {
      buttons.forEach((x) => x.setAttribute('aria-checked', String(x === b)));
      void show(b.dataset.vsize ?? '100');
    });
  }
  await show('100');
  tick();
  root.classList.add('is-live');
  root.dataset.ready = 'true';
}
