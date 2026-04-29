/* CayenaBot — scene-builder.js
 * THE PRODUCT. Builds a real Three.js apartment from room JSON.
 * PBR materials, procedural HDRI, cinematic lighting, two camera modes.
 *
 * This file is split internally into sections:
 *   1) bootstrap renderer + scene + lights + HDRI
 *   2) materials library
 *   3) per-room geometry (walls with door/window cuts, floor, ceiling)
 *   4) furniture builders
 *   5) exterior context (dollhouse only)
 *   6) public API: build(rooms, styleDNA), camera modes, capture
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { buildFurnitureForRoom } from './scene-furniture.js';
import { MAT } from './scene-materials.js';

const ROOM_HEIGHT = 2.8;
const WALL_THICKNESS = 0.12;
// 1 unit = 1 meter. We map bbox percentages onto a base apartment size.
const APT_W = 18; // meters
const APT_D = 14; // meters

/* ================================================================ HDRI */
function buildSkyEnvironment(renderer, mode = 'walk') {
  const stops = mode === 'walk'
    ? ['#4a90d9', '#87CEEB', '#b8dbe8', '#f5e6d0', '#d4a574']
    : ['#0a0e1a', '#1a1a2e', '#2a2a3e', '#3a3a4e', '#1a1a2e'];

  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  const grd = ctx.createLinearGradient(0, 0, 0, 512);
  stops.forEach((c, i) => grd.addColorStop(i / (stops.length - 1), c));
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, 512, 512);

  const tex = new THREE.CanvasTexture(cv);
  tex.mapping = THREE.EquirectangularReflectionMapping;
  tex.colorSpace = THREE.SRGBColorSpace;

  const pmrem = new THREE.PMREMGenerator(renderer);
  const envMap = pmrem.fromEquirectangular(tex).texture;
  pmrem.dispose();
  tex.dispose();
  return envMap;
}

/* ================================================================ lighting */
function addLights(scene) {
  const ambient = new THREE.AmbientLight(0xfff8f0, 0.4);
  scene.add(ambient);

  const sun = new THREE.DirectionalLight(0xffecd0, 2.5);
  sun.position.set(12, 18, 10);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -20;
  sun.shadow.camera.right = 20;
  sun.shadow.camera.top = 20;
  sun.shadow.camera.bottom = -20;
  sun.shadow.camera.near = 0.5;
  sun.shadow.camera.far = 60;
  sun.shadow.bias = -0.0001;
  sun.shadow.normalBias = 0.02;
  sun.shadow.radius = 3;
  scene.add(sun);

  const fill = new THREE.DirectionalLight(0xc8d8ff, 0.6);
  fill.position.set(-8, 10, -6);
  scene.add(fill);

  const hemi = new THREE.HemisphereLight(0x87CEEB, 0x4a3a2a, 0.5);
  scene.add(hemi);

  const rim = new THREE.DirectionalLight(0xffd0a0, 0.8);
  rim.position.set(-10, 5, 15);
  scene.add(rim);

  return { ambient, sun, fill, hemi, rim };
}

/* ================================================================ public API */
export function mountSceneBuilder({ state, toast }) {
  let renderer, scene, camera, orbit, walk;
  let envMap = null;
  let mode = 'dollhouse'; // or 'walk'
  let raf = null;
  let container = null;
  let roomCenters = []; // { code, name, position, lookAt }
  let onUpdateCb = null;

  function ensureContainer() {
    container = document.getElementById('tour-canvas-wrap');
    return container;
  }

  function init() {
    if (renderer) return;
    ensureContainer();
    const w = container.clientWidth || window.innerWidth;
    const h = container.clientHeight || window.innerHeight;

    renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(w, h);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.4;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);

    scene = new THREE.Scene();
    envMap = buildSkyEnvironment(renderer, 'walk');
    scene.environment = envMap;
    scene.background = envMap;
    scene.fog = new THREE.Fog(0xb8dbe8, 60, 200);

    addLights(scene);

    camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 500);
    camera.position.set(15, 18, 15);
    camera.lookAt(0, 1, 0);

    orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true;
    orbit.dampingFactor = 0.06;
    orbit.maxPolarAngle = Math.PI * 0.49;
    orbit.minDistance = 3;
    orbit.maxDistance = 60;

    walk = new PointerLockControls(camera, renderer.domElement);

    window.addEventListener('resize', onResize);

    animate();
  }

  function onResize() {
    if (!renderer || !container) return;
    const w = container.clientWidth, h = container.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  }

  /* =============== walk-mode movement =============== */
  const moveKeys = { w: false, a: false, s: false, d: false, shift: false };
  function bindWalkKeys() {
    const down = (e) => {
      const k = e.key.toLowerCase();
      if (k in moveKeys) { moveKeys[k] = true; e.preventDefault(); }
      if (k === 'shift') moveKeys.shift = true;
      if (k === 'escape' && mode === 'walk') setMode('dollhouse');
    };
    const up = (e) => {
      const k = e.key.toLowerCase();
      if (k in moveKeys) moveKeys[k] = false;
      if (k === 'shift') moveKeys.shift = false;
    };
    document.addEventListener('keydown', down);
    document.addEventListener('keyup', up);
  }
  bindWalkKeys();

  function tickWalk(dt) {
    const speed = (moveKeys.shift ? 5 : 2.6) * dt;
    const dir = new THREE.Vector3();
    if (moveKeys.w) dir.z -= 1;
    if (moveKeys.s) dir.z += 1;
    if (moveKeys.a) dir.x -= 1;
    if (moveKeys.d) dir.x += 1;
    if (dir.lengthSq() > 0) {
      dir.normalize().multiplyScalar(speed);
      walk.moveRight(dir.x);
      walk.moveForward(-dir.z);
      camera.position.y = 1.6; // lock eye height
    }
  }

  let lastT = performance.now();
  function animate() {
    raf = requestAnimationFrame(animate);
    const now = performance.now();
    const dt = Math.min(0.05, (now - lastT) / 1000);
    lastT = now;
    if (mode === 'dollhouse') orbit.update();
    else tickWalk(dt);
    renderer.render(scene, camera);
    onUpdateCb?.({ position: camera.position, mode });
  }

  /* =============== mode switching =============== */
  function setMode(next) {
    mode = next;
    if (next === 'walk') {
      orbit.enabled = false;
      // Drop camera into first room at eye height
      const start = roomCenters[0];
      if (start) {
        camera.position.set(start.position.x, 1.6, start.position.z);
      } else camera.position.set(0, 1.6, 0);
      try { walk.lock(); } catch {}
    } else {
      try { walk.unlock(); } catch {}
      orbit.enabled = true;
      camera.position.set(15, 18, 15);
      orbit.target.set(0, 1, 0);
      orbit.update();
    }
    // Swap env on mode change for vibe
    const newEnv = buildSkyEnvironment(renderer, next);
    scene.environment = newEnv;
    if (next === 'walk') scene.background = newEnv;
    if (envMap) envMap.dispose();
    envMap = newEnv;
  }

  /* =============== build =============== */
  async function build(rooms, styleDNA = {}) {
    init();
    // Clear previous geometry
    const toRemove = [];
    scene.traverse(obj => { if (obj.userData?.disposable) toRemove.push(obj); });
    toRemove.forEach(o => {
      o.parent?.remove(o);
      o.geometry?.dispose?.();
      if (Array.isArray(o.material)) o.material.forEach(m => m.dispose?.());
      else o.material?.dispose?.();
    });
    roomCenters = [];

    if (!rooms || !rooms.length) return;

    const mats = MAT(envMap, styleDNA);

    // Build each room
    const { buildRoom } = await import('./scene-rooms.js');
    rooms.forEach((r, i) => {
      const center = buildRoom(scene, r, i, mats, APT_W, APT_D, ROOM_HEIGHT, WALL_THICKNESS);
      roomCenters.push({ code: r.code, name: r.name, position: center, lookAt: new THREE.Vector3(center.x, 1.4, center.z) });
      buildFurnitureForRoom(scene, r, center, mats, ROOM_HEIGHT);
    });

    // Exterior context: ground / pool / palms (only meaningful in dollhouse)
    const { buildExterior } = await import('./scene-exterior.js');
    buildExterior(scene, mats, APT_W, APT_D);
  }

  /* =============== teleport / fly camera =============== */
  function flyTo(roomCode, durMs = 1500) {
    const target = roomCenters.find(r => r.code === roomCode);
    if (!target) return;
    const startPos = camera.position.clone();
    const endPos = mode === 'walk'
      ? new THREE.Vector3(target.position.x, 1.6, target.position.z)
      : new THREE.Vector3(target.position.x + 8, 8, target.position.z + 8);
    const startLook = orbit.target.clone();
    const endLook = target.lookAt.clone();
    const t0 = performance.now();
    function step() {
      const t = Math.min(1, (performance.now() - t0) / durMs);
      const e = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
      camera.position.lerpVectors(startPos, endPos, e);
      if (mode === 'dollhouse') {
        orbit.target.lerpVectors(startLook, endLook, e);
        orbit.update();
      }
      if (t < 1) requestAnimationFrame(step);
    }
    step();
  }

  /* =============== capture =============== */
  function capture() {
    if (!renderer) return null;
    renderer.render(scene, camera); // ensure latest
    return renderer.domElement.toDataURL('image/jpeg', 0.92);
  }

  function onTabChange(tab) {
    if (tab === 'tour' && container) {
      // Trigger resize after tab becomes visible
      setTimeout(onResize, 50);
    }
  }

  function dispose() {
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', onResize);
    renderer?.dispose();
    renderer = null;
  }

  return {
    init, build, setMode, flyTo, capture, dispose,
    onTabChange,
    get rooms() { return roomCenters; },
    get camera() { return camera; },
    get mode() { return mode; },
    onUpdate(cb) { onUpdateCb = cb; },
  };
}
