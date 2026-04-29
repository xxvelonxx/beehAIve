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
function buildSkyEnvironment(renderer, mode = 'day') {
  let stops;
  if (mode === 'night') {
    // Dramatic night: deep navy + moonlit horizon glow
    stops = ['#020410', '#050c1f', '#0a1428', '#1a2540', '#2a3550'];
  } else {
    // Bright day: tropical golden-hour sky
    stops = ['#4a90d9', '#87CEEB', '#b8dbe8', '#f5e6d0', '#d4a574'];
  }

  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  const grd = ctx.createLinearGradient(0, 0, 0, 512);
  stops.forEach((c, i) => grd.addColorStop(i / (stops.length - 1), c));
  ctx.fillStyle = grd;
  ctx.fillRect(0, 0, 512, 512);

  // Add subtle stars to night sky for drama
  if (mode === 'night') {
    for (let i = 0; i < 80; i++) {
      const x = Math.random() * 512;
      const y = Math.random() * 256; // upper half only
      const r = Math.random() * 1.2 + 0.3;
      const a = Math.random() * 0.7 + 0.3;
      ctx.fillStyle = `rgba(255,255,255,${a})`;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

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
  let lights = null;     // { ambient, sun, fill, hemi, rim }
  let isNight = false;
  let furnitureVisible = true;

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
    envMap = buildSkyEnvironment(renderer, 'day'); // start bright
    scene.environment = envMap;
    scene.background = new THREE.Color(0x87CEEB); // sky blue background
    scene.fog = new THREE.Fog(0xb8dbe8, 60, 200);

    lights = addLights(scene);

    // FOV 38 ≈ Hauzd's framing — narrower than typical Three.js demos so
    // architectural geometry doesn't look fish-eyed.
    camera = new THREE.PerspectiveCamera(38, w / h, 0.1, 500);
    camera.position.set(13, 11, 14); // lower angle, closer — emphasizes cutaway
    camera.lookAt(0, 1.2, 0);

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
      camera.position.set(13, 11, 14);
      orbit.target.set(0, 1.2, 0);
      orbit.update();
    }
    // Cutaway: hide ceilings in dollhouse so all rooms are visible from above
    applyCutaway();
    // Background tint for the mode
    if (next === 'walk' && envMap) scene.background = envMap;
    else scene.background = new THREE.Color(isNight ? 0x050c1f : 0x87CEEB);
  }

  /** Hide ceilings + roof when in dollhouse mode (Hauzd-style cutaway). */
  function applyCutaway() {
    const showCeilings = mode === 'walk';
    scene.traverse(o => {
      if (o.userData?.kind === 'ceiling') o.visible = showCeilings;
    });
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

    // Apply current cutaway state to the freshly-built ceilings
    applyCutaway();
    // Reapply night state if we're in night already (env map binds to materials at build)
    if (isNight) setDayNight(true);
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

  /* =============== day / night toggle =============== */
  function setDayNight(night) {
    if (!lights) return;
    isNight = !!night;
    // Swap env map for dramatic reflections (dark sky vs sunny sky)
    if (renderer) {
      const newEnv = buildSkyEnvironment(renderer, isNight ? 'night' : 'day');
      // Drop intensity at night so dark env doesn't kill visibility
      scene.environment = newEnv;
      scene.environmentIntensity = isNight ? 0.35 : 1.0;
      if (envMap) envMap.dispose();
      envMap = newEnv;
    }

    if (isNight) {
      lights.ambient.color.setHex(0x3a4a6a);
      lights.ambient.intensity = 0.25;
      lights.sun.color.setHex(0xb8c8e8);     // moon
      lights.sun.intensity = 0.6;
      lights.sun.position.set(-12, 14, -8);
      lights.fill.color.setHex(0x4060a0);
      lights.fill.intensity = 0.25;
      lights.hemi.color.setHex(0x1a2540);
      lights.hemi.groundColor.setHex(0x0a0612);
      lights.hemi.intensity = 0.45;
      lights.rim.color.setHex(0xffd089);
      lights.rim.intensity = 0.4;
      scene.background = new THREE.Color(0x050c1f);
      if (scene.fog) { scene.fog.color.setHex(0x0a1428); scene.fog.near = 30; scene.fog.far = 120; }
      if (renderer) renderer.toneMappingExposure = 1.0;
      // Boost per-room point lights — they become the primary illumination
      scene.traverse(o => {
        if (o.isPointLight && o.userData.disposable) {
          o.intensity = 4.0;
          o.distance = 14;
          o.color.setHex(0xffc080);
        }
      });
    } else {
      lights.ambient.color.setHex(0xfff8f0);
      lights.ambient.intensity = 0.4;
      lights.sun.color.setHex(0xffecd0);
      lights.sun.intensity = 2.5;
      lights.sun.position.set(12, 18, 10);
      lights.fill.color.setHex(0xc8d8ff);
      lights.fill.intensity = 0.6;
      lights.hemi.color.setHex(0x87CEEB);
      lights.hemi.groundColor.setHex(0x4a3a2a);
      lights.hemi.intensity = 0.5;
      lights.rim.color.setHex(0xffd0a0);
      lights.rim.intensity = 0.8;
      scene.background = new THREE.Color(0x87CEEB);
      if (scene.fog) { scene.fog.color.setHex(0xb8dbe8); scene.fog.near = 60; scene.fog.far = 200; }
      if (renderer) renderer.toneMappingExposure = 1.4;
      scene.traverse(o => {
        if (o.isPointLight && o.userData.disposable) {
          o.intensity = 0.9;
          o.distance = 12;
          o.color.setHex(0xfff0d0);
        }
      });
    }
  }

  /* =============== furniture visibility toggle =============== */
  function setFurnitureVisible(visible) {
    furnitureVisible = !!visible;
    scene.traverse(o => {
      if (o.userData?.kind === 'furniture') o.visible = furnitureVisible;
    });
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
    setDayNight, setFurnitureVisible,
    onTabChange,
    get rooms() { return roomCenters; },
    get camera() { return camera; },
    get mode() { return mode; },
    get isNight() { return isNight; },
    get furnitureVisible() { return furnitureVisible; },
    onUpdate(cb) { onUpdateCb = cb; },
  };
}
