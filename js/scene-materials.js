/* CayenaBot — scene-materials.js
 * PBR material library. All materials reflect the env map for realism.
 * Style DNA optionally tints palette and material choices.
 */

import * as THREE from 'three';

function makeTileTexture(color1 = '#f0ece6', color2 = '#e8e2d8', tile = 4) {
  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  const s = 512 / tile;
  for (let y = 0; y < tile; y++) {
    for (let x = 0; x < tile; x++) {
      ctx.fillStyle = (x + y) % 2 === 0 ? color1 : color2;
      ctx.fillRect(x * s, y * s, s, s);
      ctx.strokeStyle = 'rgba(0,0,0,0.06)';
      ctx.strokeRect(x * s, y * s, s, s);
    }
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(2, 2);
  return t;
}

function makeWallTexture(base = '#e8e4dc') {
  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 512, 512);
  // subtle noise for texture
  const id = ctx.getImageData(0, 0, 512, 512);
  const d = id.data;
  for (let i = 0; i < d.length; i += 4) {
    const n = (Math.random() - 0.5) * 12;
    d[i] = Math.max(0, Math.min(255, d[i] + n));
    d[i + 1] = Math.max(0, Math.min(255, d[i + 1] + n));
    d[i + 2] = Math.max(0, Math.min(255, d[i + 2] + n));
  }
  ctx.putImageData(id, 0, 0);
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(3, 2);
  return t;
}

function makeWoodTexture(base = '#5c3d2e') {
  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 512, 512);
  // wood grain stripes
  for (let i = 0; i < 60; i++) {
    ctx.fillStyle = `rgba(0,0,0,${Math.random() * 0.18})`;
    ctx.fillRect(0, i * 9 + Math.random() * 4, 512, 1 + Math.random() * 2);
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(2, 2);
  return t;
}

function makeMarbleTexture(base = '#f0ece6') {
  const cv = document.createElement('canvas');
  cv.width = 512; cv.height = 512;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = base;
  ctx.fillRect(0, 0, 512, 512);
  // veining
  for (let i = 0; i < 8; i++) {
    ctx.beginPath();
    ctx.moveTo(Math.random() * 512, 0);
    let x = Math.random() * 512, y = 0;
    while (y < 512) {
      x += (Math.random() - 0.5) * 80;
      y += 20 + Math.random() * 30;
      ctx.lineTo(x, y);
    }
    ctx.strokeStyle = `rgba(120,100,90,${0.1 + Math.random() * 0.2})`;
    ctx.lineWidth = 1 + Math.random() * 2;
    ctx.stroke();
  }
  const t = new THREE.CanvasTexture(cv);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function makeGrassTexture() {
  const cv = document.createElement('canvas');
  cv.width = 256; cv.height = 256;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#3a5e2a';
  ctx.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 1000; i++) {
    ctx.fillStyle = `rgba(${60 + Math.random() * 40}, ${100 + Math.random() * 60}, 40, ${0.4 + Math.random() * 0.4})`;
    ctx.fillRect(Math.random() * 256, Math.random() * 256, 1, 2 + Math.random() * 2);
  }
  const t = new THREE.CanvasTexture(cv);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.colorSpace = THREE.SRGBColorSpace;
  t.repeat.set(20, 20);
  return t;
}

/** Build the canonical material set, applying style DNA tweaks. */
export function MAT(envMap, styleDNA = {}) {
  const accent = (styleDNA.palette && styleDNA.palette[0]) || null;
  const mats = {
    floor: new THREE.MeshStandardMaterial({
      map: makeTileTexture(),
      roughness: 0.25,
      metalness: 0.05,
      envMap, envMapIntensity: 0.8,
    }),
    floorWood: new THREE.MeshStandardMaterial({
      map: makeWoodTexture(),
      roughness: 0.55,
      metalness: 0.0,
      envMap, envMapIntensity: 0.2,
    }),
    floorMarble: new THREE.MeshStandardMaterial({
      map: makeMarbleTexture(),
      roughness: 0.15,
      metalness: 0.05,
      envMap, envMapIntensity: 1.0,
    }),
    wall: new THREE.MeshStandardMaterial({
      map: makeWallTexture(),
      roughness: 0.65,
      metalness: 0.0,
      envMap, envMapIntensity: 0.3,
    }),
    ceiling: new THREE.MeshStandardMaterial({
      color: 0xfafafa,
      roughness: 0.85,
      metalness: 0.0,
      envMap, envMapIntensity: 0.15,
    }),
    leather: new THREE.MeshStandardMaterial({
      color: accent ? new THREE.Color(accent).multiplyScalar(0.5) : 0x3d2b1f,
      roughness: 0.6,
      metalness: 0.05,
      envMap, envMapIntensity: 0.4,
    }),
    fabric: new THREE.MeshStandardMaterial({
      color: 0xc4b5a3,
      roughness: 0.85,
      metalness: 0.0,
      envMap, envMapIntensity: 0.2,
    }),
    wood: new THREE.MeshStandardMaterial({
      map: makeWoodTexture('#6b4a36'),
      roughness: 0.55,
      metalness: 0.0,
      envMap, envMapIntensity: 0.25,
    }),
    chrome: new THREE.MeshStandardMaterial({
      color: 0xcccccc,
      roughness: 0.1,
      metalness: 0.9,
      envMap, envMapIntensity: 1.5,
    }),
    gold: new THREE.MeshStandardMaterial({
      color: 0xc4773b,
      roughness: 0.25,
      metalness: 0.85,
      envMap, envMapIntensity: 1.2,
    }),
    glass: new THREE.MeshStandardMaterial({
      color: 0x88bbdd,
      roughness: 0.05,
      metalness: 0.1,
      transparent: true,
      opacity: 0.32,
      envMap, envMapIntensity: 1.5,
      side: THREE.DoubleSide,
    }),
    water: new THREE.MeshStandardMaterial({
      color: 0x4a90c8,
      roughness: 0.05,
      metalness: 0.4,
      transparent: true,
      opacity: 0.82,
      envMap, envMapIntensity: 1.6,
    }),
    marble: new THREE.MeshStandardMaterial({
      map: makeMarbleTexture(),
      roughness: 0.18,
      metalness: 0.05,
      envMap, envMapIntensity: 0.95,
    }),
    grass: new THREE.MeshStandardMaterial({
      map: makeGrassTexture(),
      roughness: 0.95,
      metalness: 0.0,
      envMap, envMapIntensity: 0.1,
    }),
    leaf: new THREE.MeshStandardMaterial({
      color: 0x3a6e2a,
      roughness: 0.7,
      metalness: 0.0,
      envMap, envMapIntensity: 0.3,
      side: THREE.DoubleSide,
    }),
    trunk: new THREE.MeshStandardMaterial({
      color: 0x6b4a32,
      roughness: 0.9,
      metalness: 0.0,
      envMap, envMapIntensity: 0.1,
    }),
    accent: new THREE.MeshStandardMaterial({
      color: accent ? new THREE.Color(accent) : 0xc4773b,
      roughness: 0.4,
      metalness: 0.2,
      envMap, envMapIntensity: 0.7,
    }),
  };
  return mats;
}
