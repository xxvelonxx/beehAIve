/* CayenaBot — scene-rooms.js
 * Builds room geometry from bbox + wall descriptions.
 * Walls cut for doors/windows using THREE.Shape + holes; glass panes inserted.
 */

import * as THREE from 'three';

/* convert bbox (% of plan) to world-space rect centered around origin */
function bboxToWorld(bbox, aptW, aptD) {
  const x = (bbox.x / 100) * aptW - aptW / 2;
  const z = (bbox.y / 100) * aptD - aptD / 2;
  const w = (bbox.width / 100) * aptW;
  const d = (bbox.height / 100) * aptD;
  return { x, z, w, d, cx: x + w / 2, cz: z + d / 2 };
}

/* parse a wall description string into an opening type */
function parseOpening(desc) {
  if (!desc) return null;
  const s = desc.toLowerCase();
  if (s.includes('abierto') || s.includes('arco')) return { type: 'open' };
  if (s.includes('ventanal') || s.includes('piso-techo') || s.includes('floor-to-ceiling')) return { type: 'glassWall' };
  if (s.includes('ventana')) return { type: 'window' };
  if (s.includes('puerta doble') || s.includes('doble')) return { type: 'doubleDoor' };
  if (s.includes('puerta')) return { type: 'door' };
  return null; // solid wall
}

/* Build a wall mesh from a 2D shape (with optional holes), extruded out as wall thickness */
function buildWallShape(width, height, openings, mats) {
  const group = new THREE.Group();
  const shape = new THREE.Shape();
  shape.moveTo(-width / 2, 0);
  shape.lineTo(width / 2, 0);
  shape.lineTo(width / 2, height);
  shape.lineTo(-width / 2, height);
  shape.lineTo(-width / 2, 0);

  const glassFills = [];
  if (openings && openings.length) {
    openings.forEach(op => {
      const hole = new THREE.Path();
      hole.moveTo(op.x1, op.y1);
      hole.lineTo(op.x2, op.y1);
      hole.lineTo(op.x2, op.y2);
      hole.lineTo(op.x1, op.y2);
      hole.lineTo(op.x1, op.y1);
      shape.holes.push(hole);
      if (op.glass) glassFills.push(op);
    });
  }

  const geom = new THREE.ExtrudeGeometry(shape, { depth: 0.12, bevelEnabled: false });
  geom.translate(0, 0, -0.06);
  const wall = new THREE.Mesh(geom, mats.wall);
  wall.castShadow = true;
  wall.receiveShadow = true;
  wall.userData.disposable = true;
  group.add(wall);

  // glass panes + frames + muntins
  glassFills.forEach(op => {
    const gw = op.x2 - op.x1, gh = op.y2 - op.y1;
    const glassGeom = new THREE.PlaneGeometry(gw, gh);
    const glass = new THREE.Mesh(glassGeom, mats.glass);
    glass.position.set((op.x1 + op.x2) / 2, (op.y1 + op.y2) / 2, 0);
    glass.userData.disposable = true;
    group.add(glass);

    // chrome perimeter frame
    const frameThickness = 0.04;
    const frameDepth = 0.06;
    const frame = new THREE.Group();
    const fmat = mats.chrome;
    const top = new THREE.Mesh(new THREE.BoxGeometry(gw, frameThickness, frameDepth), fmat);
    top.position.set((op.x1 + op.x2) / 2, op.y2, 0);
    const bot = new THREE.Mesh(new THREE.BoxGeometry(gw, frameThickness, frameDepth), fmat);
    bot.position.set((op.x1 + op.x2) / 2, op.y1, 0);
    const left = new THREE.Mesh(new THREE.BoxGeometry(frameThickness, gh, frameDepth), fmat);
    left.position.set(op.x1, (op.y1 + op.y2) / 2, 0);
    const right = new THREE.Mesh(new THREE.BoxGeometry(frameThickness, gh, frameDepth), fmat);
    right.position.set(op.x2, (op.y1 + op.y2) / 2, 0);
    [top, bot, left, right].forEach(m => { m.userData.disposable = true; frame.add(m); });

    // muntins (interior dividers): horizontal at 1/3 and 2/3 height for tall windows,
    // single vertical center for wide windows
    const muntinT = 0.025;
    if (gh > 1.4) {
      // horizontal muntin at 40% height
      const hb = new THREE.Mesh(new THREE.BoxGeometry(gw, muntinT, frameDepth * 0.7), fmat);
      hb.position.set((op.x1 + op.x2) / 2, op.y1 + gh * 0.4, 0);
      hb.userData.disposable = true;
      frame.add(hb);
    }
    if (gw > 1.6) {
      const vb = new THREE.Mesh(new THREE.BoxGeometry(muntinT, gh, frameDepth * 0.7), fmat);
      vb.position.set((op.x1 + op.x2) / 2, (op.y1 + op.y2) / 2, 0);
      vb.userData.disposable = true;
      frame.add(vb);
    }

    group.add(frame);
  });

  group.userData.disposable = true;
  return group;
}

/* Decide opening rectangles for a wall given a description */
function openingsFor(desc, wallWidth, wallHeight) {
  const op = parseOpening(desc);
  if (!op) return [];
  switch (op.type) {
    case 'open': {
      // big arch 2.4m tall, centered, 70% width
      const w = Math.min(wallWidth * 0.7, 3);
      return [{
        x1: -w / 2, x2: w / 2,
        y1: 0.05, y2: Math.min(2.4, wallHeight - 0.1),
        glass: false,
      }];
    }
    case 'glassWall': {
      const w = wallWidth * 0.85;
      return [{
        x1: -w / 2, x2: w / 2,
        y1: 0.1, y2: wallHeight - 0.1,
        glass: true,
      }];
    }
    case 'window': {
      const w = Math.min(wallWidth * 0.55, 1.8);
      return [{
        x1: -w / 2, x2: w / 2,
        y1: 1.0, y2: 2.0,
        glass: true,
      }];
    }
    case 'doubleDoor': {
      const w = Math.min(wallWidth * 0.5, 1.8);
      return [{
        x1: -w / 2, x2: w / 2,
        y1: 0.05, y2: Math.min(2.2, wallHeight - 0.2),
        glass: false,
      }];
    }
    case 'door': {
      return [{
        x1: -0.45, x2: 0.45,
        y1: 0.05, y2: Math.min(2.1, wallHeight - 0.2),
        glass: false,
      }];
    }
    default: return [];
  }
}

/* pick floor material based on description */
function pickFloorMaterial(desc, mats) {
  const s = (desc || '').toLowerCase();
  if (s.includes('mármol') || s.includes('marmol') || s.includes('marble')) return mats.floorMarble;
  if (s.includes('madera') || s.includes('teca') || s.includes('parquet') || s.includes('wood') || s.includes('teak')) return mats.floorWood;
  return mats.floor;
}

/**
 * Build one room. Returns its world center as Vector3.
 */
export function buildRoom(scene, room, index, mats, aptW, aptD, height, thickness) {
  const w = bboxToWorld(room.bbox, aptW, aptD);
  const group = new THREE.Group();
  group.userData = { disposable: true, roomCode: room.code, roomName: room.name };

  // floor
  const floorMat = pickFloorMaterial(room.floor_material, mats);
  const floorGeom = new THREE.BoxGeometry(w.w, 0.06, w.d);
  const floor = new THREE.Mesh(floorGeom, floorMat);
  floor.position.set(w.cx, 0, w.cz);
  floor.receiveShadow = true;
  floor.userData.disposable = true;
  scene.add(floor);

  // baseboards (zócalo) — 8cm dark band along all 4 walls at floor level
  // Huge "real space" effect for almost free in geometry cost.
  const baseH = 0.08, baseT = 0.02;
  const baseMat = mats.wood; // dark wood baseboard
  const bbN = new THREE.Mesh(new THREE.BoxGeometry(w.w, baseH, baseT), baseMat);
  bbN.position.set(w.cx, baseH / 2 + 0.005, w.z + baseT / 2);
  const bbS = new THREE.Mesh(new THREE.BoxGeometry(w.w, baseH, baseT), baseMat);
  bbS.position.set(w.cx, baseH / 2 + 0.005, w.z + w.d - baseT / 2);
  const bbE = new THREE.Mesh(new THREE.BoxGeometry(baseT, baseH, w.d), baseMat);
  bbE.position.set(w.x + w.w - baseT / 2, baseH / 2 + 0.005, w.cz);
  const bbW = new THREE.Mesh(new THREE.BoxGeometry(baseT, baseH, w.d), baseMat);
  bbW.position.set(w.x + baseT / 2, baseH / 2 + 0.005, w.cz);
  [bbN, bbS, bbE, bbW].forEach(m => { m.userData = { disposable: true, kind: 'baseboard' }; scene.add(m); });

  // ceiling — tagged so dollhouse mode can hide it (cutaway view)
  const ceilingGeom = new THREE.BoxGeometry(w.w, 0.06, w.d);
  const ceiling = new THREE.Mesh(ceilingGeom, mats.ceiling);
  ceiling.position.set(w.cx, height + 0.03, w.cz);
  ceiling.userData = { disposable: true, kind: 'ceiling' };
  scene.add(ceiling);

  // ceiling crown molding — thin band where wall meets ceiling
  const cmH = 0.05, cmT = 0.02;
  const cmMat = mats.ceiling; // white crown for now
  const cmN = new THREE.Mesh(new THREE.BoxGeometry(w.w, cmH, cmT), cmMat);
  cmN.position.set(w.cx, height - cmH / 2, w.z + cmT / 2);
  const cmS = new THREE.Mesh(new THREE.BoxGeometry(w.w, cmH, cmT), cmMat);
  cmS.position.set(w.cx, height - cmH / 2, w.z + w.d - cmT / 2);
  const cmE = new THREE.Mesh(new THREE.BoxGeometry(cmT, cmH, w.d), cmMat);
  cmE.position.set(w.x + w.w - cmT / 2, height - cmH / 2, w.cz);
  const cmW = new THREE.Mesh(new THREE.BoxGeometry(cmT, cmH, w.d), cmMat);
  cmW.position.set(w.x + cmT / 2, height - cmH / 2, w.cz);
  [cmN, cmS, cmE, cmW].forEach(m => { m.userData = { disposable: true, kind: 'crown' }; scene.add(m); });

  // 4 walls
  // North (+Z side, looking south)
  const north = buildWallShape(w.w, height, openingsFor(room.wall_north, w.w, height), mats);
  north.position.set(w.cx, 0, w.z);
  north.rotation.y = Math.PI; // facing south (into the room)
  scene.add(north);

  // South wall
  const south = buildWallShape(w.w, height, openingsFor(room.wall_south, w.w, height), mats);
  south.position.set(w.cx, 0, w.z + w.d);
  scene.add(south);

  // East wall
  const east = buildWallShape(w.d, height, openingsFor(room.wall_east, w.d, height), mats);
  east.position.set(w.x + w.w, 0, w.cz);
  east.rotation.y = -Math.PI / 2;
  scene.add(east);

  // West wall
  const west = buildWallShape(w.d, height, openingsFor(room.wall_west, w.d, height), mats);
  west.position.set(w.x, 0, w.cz);
  west.rotation.y = Math.PI / 2;
  scene.add(west);

  // Per-room point light for warmth
  const pl = new THREE.PointLight(0xfff0d0, 0.9, 12, 1.6);
  pl.position.set(w.cx, height - 0.4, w.cz);
  pl.castShadow = false;
  pl.userData.disposable = true;
  scene.add(pl);

  return new THREE.Vector3(w.cx, 1.6, w.cz);
}
