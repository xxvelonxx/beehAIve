/* CayenaBot — scene-furniture.js
 * Procedural furniture per room type. Realistic proportions, PBR materials.
 * Detects room type from name/code, builds appropriate set.
 */

import * as THREE from 'three';

function classify(room) {
  const n = (room.name || '').toLowerCase();
  if (n.includes('sala') || n.includes('living') || n.includes('estar')) return 'living';
  if (n.includes('comedor') || n.includes('dining')) return 'dining';
  if (n.includes('cocina') || n.includes('kitchen')) return 'kitchen';
  if (n.includes('baño') || n.includes('bath') || n.includes('bano')) return 'bathroom';
  if (n.includes('habitación') || n.includes('habitacion') || n.includes('dormit') || n.includes('cuarto') || n.includes('bedroom') || n.includes('master')) return 'bedroom';
  if (n.includes('terraza') || n.includes('balcón') || n.includes('balcon') || n.includes('terrace') || n.includes('balcony')) return 'terrace';
  if (n.includes('estudio') || n.includes('office') || n.includes('oficina')) return 'office';
  if (n.includes('closet') || n.includes('vestidor') || n.includes('walk-in')) return 'closet';
  return 'living';
}

function tagDisposable(obj) {
  obj.traverse?.(c => {
    c.userData = { ...c.userData, disposable: true, kind: 'furniture' };
    if (c.isMesh) { c.castShadow = true; c.receiveShadow = true; }
  });
  obj.userData = { ...obj.userData, disposable: true, kind: 'furniture' };
  return obj;
}

/* ---------------- LIVING ---------------- */
function buildLiving(group, mats) {
  // L-shaped sofa
  const sofa = new THREE.Group();
  const seat = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.45, 0.95), mats.leather);
  seat.position.set(0, 0.45, 0);
  const back = new THREE.Mesh(new THREE.BoxGeometry(2.6, 0.65, 0.18), mats.leather);
  back.position.set(0, 0.95, -0.4);
  const armL = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.55, 0.95), mats.leather);
  armL.position.set(-1.3, 0.6, 0);
  const armR = armL.clone(); armR.position.x = 1.3;
  const ext = new THREE.Mesh(new THREE.BoxGeometry(0.95, 0.45, 1.4), mats.leather);
  ext.position.set(1.3 + 0.475, 0.45, 0.7);
  const cushion1 = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.18, 0.55), mats.fabric);
  cushion1.position.set(-0.8, 0.78, 0.1);
  const cushion2 = cushion1.clone(); cushion2.position.set(0.6, 0.78, 0.1);
  sofa.add(seat, back, armL, armR, ext, cushion1, cushion2);
  group.add(sofa);

  // marble coffee table with chrome legs
  const table = new THREE.Group();
  const top = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.7), mats.marble);
  top.position.y = 0.45;
  const leg = (x, z) => {
    const l = new THREE.Mesh(new THREE.CylinderGeometry(0.025, 0.025, 0.45, 16), mats.chrome);
    l.position.set(x, 0.225, z);
    return l;
  };
  table.add(top, leg(-0.65, -0.3), leg(0.65, -0.3), leg(-0.65, 0.3), leg(0.65, 0.3));
  table.position.set(0, 0, 1.4);
  group.add(table);

  // rug
  const rug = new THREE.Mesh(new THREE.PlaneGeometry(3.2, 2.2), mats.fabric);
  rug.rotation.x = -Math.PI / 2;
  rug.position.set(0, 0.005, 1);
  group.add(rug);

  // floor lamp
  const lamp = new THREE.Group();
  const base = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 0.04, 24), mats.gold);
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 1.6, 16), mats.gold);
  pole.position.y = 0.8;
  const shade = new THREE.Mesh(new THREE.ConeGeometry(0.28, 0.35, 24, 1, true), mats.fabric);
  shade.position.y = 1.7;
  shade.rotation.x = Math.PI;
  lamp.add(base, pole, shade);
  lamp.position.set(2.2, 0, -1);
  group.add(lamp);
  const bulb = new THREE.PointLight(0xffd089, 0.9, 5, 1.4);
  bulb.position.set(2.2, 1.7, -1);
  group.add(bulb);

  // plant
  group.add(buildPlant(mats, -2.3, 0, -1.4));
}

/* ---------------- DINING ---------------- */
function buildDining(group, mats) {
  const top = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.05, 0.95), mats.wood);
  top.position.y = 0.74;
  group.add(top);
  const legGeom = new THREE.BoxGeometry(0.06, 0.74, 0.06);
  [-0.95, 0.95].forEach(x => {
    [-0.42, 0.42].forEach(z => {
      const l = new THREE.Mesh(legGeom, mats.wood);
      l.position.set(x, 0.37, z);
      group.add(l);
    });
  });
  // 6 chairs
  const chairPositions = [
    [-0.65, -0.7], [0, -0.7], [0.65, -0.7],
    [-0.65, 0.7], [0, 0.7], [0.65, 0.7],
  ];
  chairPositions.forEach(([x, z]) => {
    const ch = buildChair(mats);
    ch.position.set(x, 0, z);
    if (z > 0) ch.rotation.y = Math.PI;
    group.add(ch);
  });
  // pendant light
  const pendant = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.06, 24), mats.gold);
  pendant.position.set(0, 2.3, 0);
  group.add(pendant);
  const cord = new THREE.Mesh(new THREE.CylinderGeometry(0.005, 0.005, 0.5, 6), mats.chrome);
  cord.position.set(0, 2.55, 0);
  group.add(cord);
  const pL = new THREE.PointLight(0xffd089, 1.2, 6, 1.6);
  pL.position.set(0, 2.2, 0);
  group.add(pL);
}

function buildChair(mats) {
  const ch = new THREE.Group();
  const seat = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.05, 0.45), mats.fabric);
  seat.position.y = 0.45;
  const back = new THREE.Mesh(new THREE.BoxGeometry(0.45, 0.55, 0.05), mats.fabric);
  back.position.set(0, 0.72, -0.22);
  const lg = new THREE.BoxGeometry(0.04, 0.45, 0.04);
  [-0.2, 0.2].forEach(x => [-0.2, 0.2].forEach(z => {
    const l = new THREE.Mesh(lg, mats.wood); l.position.set(x, 0.225, z); ch.add(l);
  }));
  ch.add(seat, back);
  return ch;
}

/* ---------------- KITCHEN ---------------- */
function buildKitchen(group, mats) {
  // Island with marble top
  const island = new THREE.Group();
  const ibody = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.9, 1.0), mats.wood);
  ibody.position.y = 0.45;
  const itop = new THREE.Mesh(new THREE.BoxGeometry(2.5, 0.06, 1.1), mats.marble);
  itop.position.y = 0.93;
  island.add(ibody, itop);
  group.add(island);
  // 3 bar stools
  for (let i = 0; i < 3; i++) {
    const s = new THREE.Group();
    const seat = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.18, 0.05, 24), mats.leather);
    seat.position.y = 0.78;
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.03, 0.03, 0.78, 12), mats.chrome);
    post.position.y = 0.39;
    s.add(seat, post);
    s.position.set(-0.7 + i * 0.7, 0, 0.85);
    group.add(s);
  }
  // wall cabinets (on -z)
  const cab = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.8, 0.35), mats.wood);
  cab.position.set(0, 1.85, -1.6);
  group.add(cab);
  const counter = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.06, 0.6), mats.marble);
  counter.position.set(0, 0.93, -1.4);
  group.add(counter);
  const counterBase = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.9, 0.55), mats.wood);
  counterBase.position.set(0, 0.45, -1.4);
  group.add(counterBase);
  // chrome appliance (oven block)
  const oven = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.8, 0.55), mats.chrome);
  oven.position.set(1.0, 0.4, -1.4);
  group.add(oven);
}

/* ---------------- BEDROOM ---------------- */
function buildBedroom(group, mats) {
  // bed frame + mattress + headboard + 2 nightstands
  const frame = new THREE.Mesh(new THREE.BoxGeometry(1.85, 0.3, 2.1), mats.wood);
  frame.position.y = 0.15;
  const mattress = new THREE.Mesh(new THREE.BoxGeometry(1.75, 0.25, 2.0), mats.fabric);
  mattress.position.y = 0.42;
  const head = new THREE.Mesh(new THREE.BoxGeometry(2.0, 1.1, 0.12), mats.fabric);
  head.position.set(0, 0.85, -1.0);
  const pillow1 = new THREE.Mesh(new THREE.BoxGeometry(0.8, 0.12, 0.4), mats.ceiling);
  pillow1.position.set(-0.45, 0.62, -0.85);
  const pillow2 = pillow1.clone(); pillow2.position.x = 0.45;
  group.add(frame, mattress, head, pillow1, pillow2);

  const ns = (x) => {
    const g = new THREE.Group();
    const body = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.5, 0.42), mats.wood);
    body.position.y = 0.25;
    const top = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.04, 0.45), mats.marble);
    top.position.y = 0.52;
    const lampbase = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.08, 0.04, 16), mats.gold);
    lampbase.position.y = 0.56;
    const lampshade = new THREE.Mesh(new THREE.ConeGeometry(0.14, 0.22, 16, 1, true), mats.fabric);
    lampshade.position.y = 0.72;
    lampshade.rotation.x = Math.PI;
    g.add(body, top, lampbase, lampshade);
    g.position.set(x, 0, -0.95);
    return g;
  };
  group.add(ns(-1.3), ns(1.3));

  // Dresser
  const dr = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.85, 0.5), mats.wood);
  dr.position.set(0, 0.42, 1.4);
  group.add(dr);
  const drMirror = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.8, 0.02), mats.glass);
  drMirror.position.set(0, 1.4, 1.65);
  group.add(drMirror);
}

/* ---------------- BATHROOM ---------------- */
function buildBathroom(group, mats) {
  // freestanding tub
  const tub = new THREE.Mesh(new THREE.CylinderGeometry(0.45, 0.42, 0.5, 32), mats.ceiling);
  tub.scale.set(1.4, 1, 1);
  tub.position.set(-0.8, 0.25, 0);
  group.add(tub);
  // vanity
  const vanity = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.85, 0.5), mats.wood);
  vanity.position.set(1.0, 0.42, -1.0);
  group.add(vanity);
  const vTop = new THREE.Mesh(new THREE.BoxGeometry(1.45, 0.05, 0.55), mats.marble);
  vTop.position.set(1.0, 0.86, -1.0);
  group.add(vTop);
  const sink = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 12, 0, Math.PI * 2, 0, Math.PI / 2), mats.ceiling);
  sink.scale.y = 0.5;
  sink.position.set(1.0, 0.86, -1.0);
  group.add(sink);
  // mirror
  const mirror = new THREE.Mesh(new THREE.PlaneGeometry(1.2, 0.9), mats.chrome);
  mirror.position.set(1.0, 1.6, -1.22);
  group.add(mirror);
  // chrome faucet
  const faucet = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.3, 12), mats.chrome);
  faucet.position.set(1.0, 1.0, -1.05);
  faucet.rotation.x = -0.3;
  group.add(faucet);
}

/* ---------------- TERRACE ---------------- */
function buildTerrace(group, mats) {
  // 2 lounge chairs
  const chair = (x) => {
    const c = new THREE.Group();
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.18, 1.8), mats.wood);
    base.position.y = 0.18;
    const back = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.06, 0.7), mats.wood);
    back.position.set(0, 0.4, -0.5);
    back.rotation.x = -0.5;
    const cushion = new THREE.Mesh(new THREE.BoxGeometry(0.55, 0.1, 1.6), mats.fabric);
    cushion.position.y = 0.32;
    c.add(base, back, cushion);
    c.position.set(x, 0, 0);
    return c;
  };
  group.add(chair(-0.6), chair(0.6));
  // planters with palms
  group.add(buildPlant(mats, -1.5, 0, 1.2, 1.4));
  group.add(buildPlant(mats, 1.5, 0, 1.2, 1.4));
  // railing
  const rail = new THREE.Mesh(new THREE.BoxGeometry(3.5, 0.05, 0.05), mats.chrome);
  rail.position.set(0, 1.05, 1.7);
  group.add(rail);
  for (let i = -1.6; i <= 1.6; i += 0.4) {
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1.05, 8), mats.chrome);
    post.position.set(i, 0.525, 1.7);
    group.add(post);
  }
}

/* ---------------- OFFICE ---------------- */
function buildOffice(group, mats) {
  const desk = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.05, 0.7), mats.wood);
  desk.position.y = 0.74;
  group.add(desk);
  [[-0.7, 0.32], [0.7, 0.32], [-0.7, -0.32], [0.7, -0.32]].forEach(([x, z]) => {
    const l = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.74, 0.05), mats.wood);
    l.position.set(x, 0.37, z);
    group.add(l);
  });
  const chair = buildChair(mats);
  chair.position.set(0, 0, 0.8);
  group.add(chair);
  // bookshelf
  const shelf = new THREE.Mesh(new THREE.BoxGeometry(2.0, 2.2, 0.3), mats.wood);
  shelf.position.set(0, 1.1, -1.4);
  group.add(shelf);
}

/* ---------------- CLOSET ---------------- */
function buildCloset(group, mats) {
  const wardrobe = new THREE.Mesh(new THREE.BoxGeometry(2.4, 2.4, 0.6), mats.wood);
  wardrobe.position.set(0, 1.2, -0.8);
  group.add(wardrobe);
  const island = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.9, 0.6), mats.wood);
  island.position.set(0, 0.45, 0.5);
  group.add(island);
  const top = new THREE.Mesh(new THREE.BoxGeometry(1.45, 0.04, 0.65), mats.marble);
  top.position.set(0, 0.93, 0.5);
  group.add(top);
}

/* ---------------- generic helpers ---------------- */
function buildPlant(mats, x, y, z, scale = 1) {
  const g = new THREE.Group();
  const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.22 * scale, 0.18 * scale, 0.3 * scale, 16), mats.accent);
  pot.position.y = 0.15 * scale;
  g.add(pot);
  // 5 flat leaves arranged as fan
  for (let i = 0; i < 6; i++) {
    const leaf = new THREE.Mesh(new THREE.PlaneGeometry(0.18 * scale, 0.6 * scale), mats.leaf);
    leaf.position.y = 0.55 * scale;
    leaf.rotation.y = (i / 6) * Math.PI * 2;
    leaf.rotation.x = -0.4;
    leaf.rotation.z = -0.2;
    g.add(leaf);
  }
  g.position.set(x, y, z);
  return g;
}

/* ================================================================ public */
export function buildFurnitureForRoom(scene, room, center, mats, height) {
  const type = classify(room);
  const group = new THREE.Group();
  switch (type) {
    case 'living':   buildLiving(group, mats); break;
    case 'dining':   buildDining(group, mats); break;
    case 'kitchen':  buildKitchen(group, mats); break;
    case 'bedroom':  buildBedroom(group, mats); break;
    case 'bathroom': buildBathroom(group, mats); break;
    case 'terrace':  buildTerrace(group, mats); break;
    case 'office':   buildOffice(group, mats); break;
    case 'closet':   buildCloset(group, mats); break;
    default:         buildLiving(group, mats);
  }
  group.position.set(center.x, 0, center.z);
  tagDisposable(group);
  scene.add(group);
  return group;
}
