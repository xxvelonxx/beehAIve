/* CayenaBot — scene-exterior.js
 * Outdoor context surrounding the apartment: grass plane, infinity pool,
 * deck chairs, palm trees. Adds the "luxury resort" vibe in dollhouse mode.
 */

import * as THREE from 'three';

function tag(o) {
  o.traverse?.(c => { c.userData = { ...c.userData, disposable: true }; if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; } });
  o.userData = { ...o.userData, disposable: true };
  return o;
}

function buildPalm(mats, height = 5) {
  const palm = new THREE.Group();
  // trunk (slightly tapered cylinder)
  const trunk = new THREE.Mesh(
    new THREE.CylinderGeometry(0.16, 0.22, height, 12),
    mats.trunk,
  );
  trunk.position.y = height / 2;
  palm.add(trunk);
  // crown of fronds
  const crown = new THREE.Group();
  for (let i = 0; i < 9; i++) {
    const frond = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 2.2), mats.leaf);
    frond.position.y = height + 0.05;
    frond.rotation.y = (i / 9) * Math.PI * 2;
    frond.rotation.x = -0.6;
    frond.position.x = Math.cos((i / 9) * Math.PI * 2) * 0.15;
    frond.position.z = Math.sin((i / 9) * Math.PI * 2) * 0.15;
    crown.add(frond);
  }
  palm.add(crown);
  return palm;
}

function buildPool(mats, w, d) {
  const pool = new THREE.Group();
  // pool basin (slightly recessed)
  const basin = new THREE.Mesh(
    new THREE.BoxGeometry(w, 0.4, d),
    new THREE.MeshStandardMaterial({ color: 0xe8e2d8, roughness: 0.4, metalness: 0.05 }),
  );
  basin.position.y = -0.18;
  pool.add(basin);
  // water
  const water = new THREE.Mesh(new THREE.PlaneGeometry(w - 0.2, d - 0.2), mats.water);
  water.rotation.x = -Math.PI / 2;
  water.position.y = 0.02;
  pool.add(water);
  return pool;
}

function buildDeckChair(mats) {
  const c = new THREE.Group();
  const base = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.08, 1.7), mats.wood);
  base.position.y = 0.2;
  c.add(base);
  const cushion = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.07, 1.6), mats.fabric);
  cushion.position.y = 0.27;
  c.add(cushion);
  const back = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.05, 0.6), mats.fabric);
  back.position.set(0, 0.5, -0.55);
  back.rotation.x = -0.6;
  c.add(back);
  // legs
  for (const [x, z] of [[-0.22, -0.7], [0.22, -0.7], [-0.22, 0.7], [0.22, 0.7]]) {
    const l = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.2, 8), mats.chrome);
    l.position.set(x, 0.1, z);
    c.add(l);
  }
  return c;
}

export function buildExterior(scene, mats, aptW, aptD) {
  const root = new THREE.Group();

  // Wide ground plane
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(80, 80),
    mats.grass,
  );
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = -0.05;
  ground.receiveShadow = true;
  root.add(ground);

  // Pool to the south of the apartment
  const pool = buildPool(mats, 8, 4);
  pool.position.set(0, 0, aptD / 2 + 4);
  root.add(pool);

  // Deck chairs alongside pool
  const c1 = buildDeckChair(mats); c1.position.set(-3.2, 0, aptD / 2 + 5.5); c1.rotation.y = Math.PI / 2;
  const c2 = buildDeckChair(mats); c2.position.set(3.2, 0, aptD / 2 + 5.5); c2.rotation.y = -Math.PI / 2;
  root.add(c1, c2);

  // Palm trees in 4 corners
  const palmPositions = [
    [-aptW / 2 - 4, 0, -aptD / 2 - 4],
    [aptW / 2 + 4, 0, -aptD / 2 - 4],
    [-aptW / 2 - 6, 0, aptD / 2 + 6],
    [aptW / 2 + 6, 0, aptD / 2 + 6],
    [-aptW / 2 - 8, 0, 0],
    [aptW / 2 + 8, 0, 0],
  ];
  palmPositions.forEach(([x, y, z]) => {
    const palm = buildPalm(mats, 4 + Math.random() * 1.5);
    palm.position.set(x, y, z);
    palm.rotation.y = Math.random() * Math.PI * 2;
    root.add(palm);
  });

  tag(root);
  scene.add(root);
}
