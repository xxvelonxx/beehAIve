/* CayenaBot — showroom-templates.js
 * Static templates for the published showroom ZIP. Kept separate from
 * showroom-publish.js to stay <500 lines per file (R3).
 */

function escHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ============================================================ VIEWER CSS */
export const VIEWER_CSS = (accent = '#c4773b') => `
*, *::before, *::after { box-sizing: border-box; }
html, body { margin: 0; padding: 0; height: 100%; background: #0b0d14; color: rgba(255,255,255,0.85); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; overflow: hidden; }
:root { --accent: ${accent}; --accent-glow: ${accent}55; }

.viewer-shell { position: fixed; inset: 0; display: flex; flex-direction: column; }
.viewer-top {
  display: flex; align-items: center; gap: 14px;
  padding: 10px 16px; background: rgba(11,13,20,0.85);
  backdrop-filter: blur(10px); border-bottom: 1px solid rgba(255,255,255,0.06);
  z-index: 20;
}
.viewer-top .brand { display: flex; align-items: center; gap: 10px; }
.viewer-top .brand img { max-height: 32px; max-width: 140px; }
.viewer-top .brand-name { font-weight: 600; font-size: 15px; }
.viewer-top .unit-name { color: rgba(255,255,255,0.55); font-size: 13px; }
.viewer-top .unit-picker { margin-left: auto; display: flex; gap: 6px; flex-wrap: wrap; }
.viewer-top .unit-picker a {
  padding: 6px 12px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.7); border-radius: 6px; font-size: 12px; text-decoration: none;
  transition: all 0.2s;
}
.viewer-top .unit-picker a:hover { color: white; border-color: var(--accent); }
.viewer-top .unit-picker a.active { background: var(--accent); color: white; border-color: var(--accent); }
.viewer-top .home-link {
  padding: 6px 12px; background: transparent; border: 1px solid rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.6); border-radius: 6px; font-size: 12px; text-decoration: none;
}

.viewer-main { flex: 1; position: relative; overflow: hidden; background: #050608; }
#tour-canvas-wrap { position: absolute; inset: 0; }
#tour-canvas-wrap canvas { display: block; }

.tour-mode-bar {
  position: absolute; top: 16px; left: 16px;
  display: flex; gap: 4px; z-index: 10;
  background: rgba(8,10,18,0.85); backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 4px;
}
.tour-mode-bar button {
  padding: 8px 14px; background: transparent; color: rgba(255,255,255,0.55);
  border: none; border-radius: 6px; font-size: 13px; cursor: pointer;
  transition: all 0.2s;
}
.tour-mode-bar button:hover { color: white; }
.tour-mode-bar button.active { background: var(--accent); color: white; }
.tour-minimap {
  position: absolute; bottom: 16px; right: 16px;
  width: 200px; padding: 10px;
  background: rgba(8,10,18,0.85); backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 12px; z-index: 10;
  transition: width 0.3s;
}
.tour-minimap.expanded { width: 320px; }
.tour-minimap canvas { width: 100%; display: block; cursor: pointer; border-radius: 6px; }
.tour-minimap .label { font-size: 11px; color: rgba(255,255,255,0.45); margin-bottom: 6px; text-align: center; }
.tour-info {
  position: absolute; bottom: 16px; left: 16px;
  padding: 10px 14px;
  background: rgba(8,10,18,0.85); backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; z-index: 10;
  font-size: 13px; max-width: 240px;
}
.tour-info .room-name { font-weight: 600; color: var(--accent); }
.tour-walk-btn {
  position: absolute; bottom: 90px; left: 50%; transform: translateX(-50%);
  width: 64px; height: 64px; border-radius: 50%;
  background: var(--accent); color: white; border: none;
  font-size: 24px; z-index: 10; cursor: pointer;
  box-shadow: 0 6px 24px var(--accent-glow);
  display: none; align-items: center; justify-content: center;
}
.tour-walk-btn.visible { display: flex; }

/* landing styles */
.landing { min-height: 100vh; padding: 48px 24px; max-width: 1200px; margin: 0 auto; overflow-y: auto; height: auto; }
.landing-hero { text-align: center; margin-bottom: 56px; }
.landing-hero img.logo { max-height: 64px; max-width: 240px; margin-bottom: 24px; }
.landing-hero h1 { font-weight: 300; font-size: 48px; letter-spacing: -1px; margin: 0 0 8px; }
.landing-hero .by { color: rgba(255,255,255,0.5); font-size: 15px; }
.landing-hero .accent { color: var(--accent); }
.unit-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 20px; }
.unit-card-public {
  display: block; text-decoration: none; color: inherit;
  background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08);
  border-radius: 14px; overflow: hidden; transition: all 0.2s;
}
.unit-card-public:hover { transform: translateY(-3px); border-color: var(--accent); box-shadow: 0 12px 32px rgba(0,0,0,0.4); }
.unit-card-public .thumb { aspect-ratio: 16/10; background: linear-gradient(135deg,#1a1a2e,#2a2a3e); display: flex; align-items: center; justify-content: center; font-size: 48px; color: rgba(255,255,255,0.3); }
.unit-card-public .thumb img { width: 100%; height: 100%; object-fit: cover; }
.unit-card-public .body { padding: 16px 20px; }
.unit-card-public .body .code { color: var(--accent); font-weight: 700; font-size: 14px; }
.unit-card-public .body h3 { margin: 4px 0 8px; font-size: 22px; font-weight: 500; }
.unit-card-public .body .meta { color: rgba(255,255,255,0.5); font-size: 13px; }
.contact-bar { margin-top: 56px; padding: 24px; background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; text-align: center; }
.contact-bar a { color: var(--accent); margin: 0 12px; text-decoration: none; }
.contact-bar a:hover { text-decoration: underline; }
.cayena-credit { text-align: center; color: rgba(255,255,255,0.25); font-size: 11px; margin-top: 32px; }
@media (max-width: 600px) { .landing-hero h1 { font-size: 32px; } .landing { padding: 28px 16px; } }
`;

/* ============================================================ VIEWER JS */
export const VIEWER_JS = `
import { mountSceneBuilder } from './scene/scene-builder.js';

const params = new URLSearchParams(location.search);
const unitFile = document.documentElement.dataset.unit;

(async function boot() {
  const data = await fetch('./assets/data/' + unitFile + '.json').then(r => r.json());
  const stateStub = { project: { units: [data], activeUnitId: data.id } };
  const scene = mountSceneBuilder({ state: stateStub, toast: () => {} });
  scene.init();
  await scene.build(data.rooms || [], data.styleDNA || {});

  // === Build minimap + mode bar inline (subset of tour.js logic) ===
  const wrap = document.getElementById('tour-canvas-wrap');
  let activeRoomCode = data.rooms?.[0]?.code;

  // Mode bar
  const bar = document.createElement('div');
  bar.className = 'tour-mode-bar';
  const mkBtn = (label, fn, active) => {
    const b = document.createElement('button');
    b.textContent = label;
    if (active) b.classList.add('active');
    b.addEventListener('click', () => fn(b));
    return b;
  };
  bar.appendChild(mkBtn('🏠 3D', (b) => {
    bar.querySelectorAll('button').forEach(x => x.dataset.mode && x.classList.remove('active'));
    b.classList.add('active'); b.dataset.mode = 'd';
    scene.setMode('dollhouse');
    walkBtn.classList.remove('visible');
  }, true));
  const walkM = mkBtn('🚶 Walk', (b) => {
    bar.querySelectorAll('button[data-mode]').forEach(x => x.classList.remove('active'));
    b.classList.add('active'); b.dataset.mode = 'w';
    scene.setMode('walk');
    walkBtn.classList.add('visible');
  });
  bar.appendChild(walkM);
  const sep = document.createElement('span');
  sep.style.cssText = 'width:1px;background:rgba(255,255,255,0.1);margin:4px 6px';
  bar.appendChild(sep);
  const dn = mkBtn('☀️ Día', (b) => {
    const goingNight = !scene.isNight;
    scene.setDayNight(goingNight);
    b.textContent = goingNight ? '🌙 Noche' : '☀️ Día';
    b.classList.toggle('active', goingNight);
  });
  bar.appendChild(dn);
  const fn = mkBtn('🪑 Muebles', (b) => {
    const next = !scene.furnitureVisible;
    scene.setFurnitureVisible(next);
    b.classList.toggle('active', next);
    b.textContent = next ? '🪑 Muebles' : '🏗 Estructura';
  }, true);
  bar.appendChild(fn);

  // Capture button — works offline, just downloads the current 3D view as JPG.
  // Realismo Pro is editor-only (requires fal.ai key) — viewers download the
  // raw capture and the developer can post-process if they want.
  const cap = document.createElement('button');
  cap.textContent = '📸 Capturar';
  cap.title = 'Descarga la vista actual como JPG';
  cap.addEventListener('click', () => {
    const url = scene.capture();
    if (!url) return;
    const a = document.createElement('a');
    a.href = url;
    a.download = 'cayenabot_' + (data.code || 'unit') + '_' + Date.now() + '.jpg';
    document.body.appendChild(a); a.click(); a.remove();
  });
  bar.appendChild(cap);

  wrap.appendChild(bar);

  // Minimap
  const map = document.createElement('div');
  map.className = 'tour-minimap';
  map.innerHTML = '<div class="label">Plano</div>';
  const cv = document.createElement('canvas');
  cv.width = 320; cv.height = 200;
  map.appendChild(cv);
  wrap.appendChild(map);
  map.addEventListener('click', (e) => {
    if (e.target.classList.contains('label')) { map.classList.toggle('expanded'); return; }
    const rect = cv.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    const room = (data.rooms || []).find(r =>
      x >= r.bbox.x && x <= r.bbox.x + r.bbox.width &&
      y >= r.bbox.y && y <= r.bbox.y + r.bbox.height
    );
    if (room) { activeRoomCode = room.code; scene.flyTo(room.code, 1500); updateInfo(); drawMap(); }
  });

  function drawMap(camPos = null) {
    const ctx = cv.getContext('2d');
    const W = cv.width, H = cv.height;
    ctx.fillStyle = '#0a0e1a';
    ctx.fillRect(0, 0, W, H);
    (data.rooms || []).forEach(r => {
      const rx = (r.bbox.x / 100) * W, ry = (r.bbox.y / 100) * H;
      const rw = (r.bbox.width / 100) * W, rh = (r.bbox.height / 100) * H;
      ctx.fillStyle = r.code === activeRoomCode ? 'rgba(196,119,59,0.35)' : 'rgba(255,255,255,0.08)';
      ctx.fillRect(rx, ry, rw, rh);
      ctx.strokeStyle = r.code === activeRoomCode ? '#c4773b' : 'rgba(255,255,255,0.18)';
      ctx.lineWidth = r.code === activeRoomCode ? 2 : 1;
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.font = '10px sans-serif';
      ctx.fillText((r.name || '').slice(0, 14), rx + 4, ry + 12);
    });
    if (camPos) {
      const aptW = 18, aptD = 14;
      const cx = ((camPos.x + aptW / 2) / aptW) * W;
      const cy = ((camPos.z + aptD / 2) / aptD) * H;
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#c4773b';
      ctx.shadowColor = '#c4773b'; ctx.shadowBlur = 12;
      ctx.fill(); ctx.shadowBlur = 0;
    }
  }
  drawMap();
  scene.onUpdate(({ position }) => drawMap(position));

  // Info bar
  const info = document.createElement('div');
  info.className = 'tour-info';
  wrap.appendChild(info);
  function updateInfo() {
    const r = (data.rooms || []).find(x => x.code === activeRoomCode) || data.rooms?.[0];
    if (!r) return;
    info.innerHTML = '';
    const n = document.createElement('div'); n.className = 'room-name'; n.textContent = r.name; info.appendChild(n);
    const d = document.createElement('div'); d.textContent = r.estimated_dimensions || ''; info.appendChild(d);
    const c = document.createElement('div'); c.style.color = 'rgba(255,255,255,0.4)'; c.style.fontSize = '11px'; c.textContent = r.code; info.appendChild(c);
  }
  updateInfo();

  // Walk button
  const walkBtn = document.createElement('button');
  walkBtn.className = 'tour-walk-btn';
  walkBtn.textContent = '🚶';
  walkBtn.addEventListener('click', () => {
    scene.setMode('walk');
    bar.querySelectorAll('button[data-mode]').forEach(x => x.classList.remove('active'));
    walkM.classList.add('active'); walkM.dataset.mode = 'w';
    walkBtn.classList.add('visible');
  });
  wrap.appendChild(walkBtn);

  // Keyboard nav
  document.addEventListener('keydown', (e) => {
    const idx = (data.rooms || []).findIndex(r => r.code === activeRoomCode);
    if (idx < 0) return;
    if (e.key === 'ArrowRight' && data.rooms[idx + 1]) {
      activeRoomCode = data.rooms[idx + 1].code; scene.flyTo(activeRoomCode); updateInfo();
    }
    if (e.key === 'ArrowLeft' && data.rooms[idx - 1]) {
      activeRoomCode = data.rooms[idx - 1].code; scene.flyTo(activeRoomCode); updateInfo();
    }
  });

  // Apply URL params
  if (params.get('night') === '1') { scene.setDayNight(true); dn.click(); dn.click(); /* already toggled by click; force */ scene.setDayNight(true); dn.textContent = '🌙 Noche'; dn.classList.add('active'); }
  if (params.get('furniture') === '0') { scene.setFurnitureVisible(false); fn.classList.remove('active'); fn.textContent = '🏗 Estructura'; }
  if (params.get('mode') === 'walk') { walkM.click(); }
})();
`;

/* ============================================================ LANDING */
export const LANDING_HTML = (proj, brand) => `<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>${escHtml(proj.name)}${brand.devName ? ' · ' + escHtml(brand.devName) : ''}</title>
<link rel="stylesheet" href="./assets/viewer.css" />
<style>html, body { overflow-y: auto; }</style>
</head><body>
<div class="landing">
  <div class="landing-hero">
    ${brand._logoFile ? `<img class="logo" src="${brand._logoFile}" alt="logo" />` : ''}
    <h1>${escHtml(proj.name)}</h1>
    <div class="by">${brand.devName ? 'Por <span class="accent">' + escHtml(brand.devName) + '</span>' : ''}</div>
  </div>
  <div class="unit-grid">
    ${proj.units.map(u => {
      const heroFile = u.galleryMeta?.[0] ? `assets/img/u_${u.id}_${u.galleryMeta[0].key}.jpg` : null;
      return `<a class="unit-card-public" href="./unit-${escHtml(u.code)}.html">
        <div class="thumb">${heroFile ? `<img src="${heroFile}" alt="${escHtml(u.name)}" />` : '🏛'}</div>
        <div class="body">
          <div class="code">UNIDAD ${escHtml(u.code)}</div>
          <h3>${escHtml(u.name)}</h3>
          <div class="meta">${u.rooms?.length || 0} habitaciones · ${u.galleryMeta?.length || 0} imágenes</div>
        </div>
      </a>`;
    }).join('\n')}
  </div>
  ${(brand.contact?.email || brand.contact?.whatsapp || brand.contact?.web)
    ? `<div class="contact-bar">
        ${brand.contact.email ? `<a href="mailto:${escHtml(brand.contact.email)}">✉ ${escHtml(brand.contact.email)}</a>` : ''}
        ${brand.contact.whatsapp ? `<a href="https://wa.me/${escHtml(brand.contact.whatsapp.replace(/\D/g, ''))}">📱 WhatsApp</a>` : ''}
        ${brand.contact.web ? `<a href="${escHtml(brand.contact.web)}" target="_blank" rel="noopener">🌐 Sitio web</a>` : ''}
      </div>` : ''}
  <p class="cayena-credit">Showroom generado con CayenaBot v4.1 · ${new Date().toISOString().slice(0, 10)}</p>
</div>
</body></html>`;

/* ============================================================ UNIT */
export const UNIT_HTML = (proj, brand, unit) => `<!DOCTYPE html>
<html lang="es" data-unit="${escHtml(unit.id)}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no" />
<title>${escHtml(unit.name)} · ${escHtml(proj.name)}</title>
<link rel="stylesheet" href="./assets/viewer.css" />
<script type="importmap">
{
  "imports": {
    "three": "./assets/vendor/three/build/three.module.js",
    "three/addons/": "./assets/vendor/three/examples/jsm/"
  }
}
</script>
</head><body>
<div class="viewer-shell">
  <header class="viewer-top">
    <div class="brand">
      ${brand._logoFile ? `<img src="${brand._logoFile}" alt="logo" />` : ''}
      <div>
        <div class="brand-name">${escHtml(proj.name)}</div>
        <div class="unit-name">Unidad ${escHtml(unit.code)} · ${escHtml(unit.name)}</div>
      </div>
    </div>
    <nav class="unit-picker">
      ${proj.units.map(u => `<a href="./unit-${escHtml(u.code)}.html" class="${u.id === unit.id ? 'active' : ''}">${escHtml(u.code)}</a>`).join('')}
    </nav>
    <a href="./index.html" class="home-link">← Inicio</a>
  </header>
  <div class="viewer-main">
    <div id="tour-canvas-wrap"></div>
  </div>
</div>
<script type="module" src="./assets/viewer.js"></script>
</body></html>`;

/* ============================================================ EMBED */
export const EMBED_HTML = (proj, brand) => {
  const first = proj.units[0];
  // Same as UNIT but minimal chrome
  return `<!DOCTYPE html>
<html lang="es" data-unit="${escHtml(first.id)}">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>${escHtml(proj.name)}</title>
<link rel="stylesheet" href="./assets/viewer.css" />
<style>.viewer-top { padding: 8px 14px; } .viewer-top .home-link { display: none; }</style>
<script type="importmap">
{
  "imports": {
    "three": "./assets/vendor/three/build/three.module.js",
    "three/addons/": "./assets/vendor/three/examples/jsm/"
  }
}
</script>
</head><body>
<div class="viewer-shell">
  <header class="viewer-top">
    <div class="brand">
      ${brand._logoFile ? `<img src="${brand._logoFile}" alt="logo" />` : ''}
      <div class="brand-name">${escHtml(proj.name)}</div>
    </div>
    <nav class="unit-picker">
      ${proj.units.map(u => `<a href="./unit-${escHtml(u.code)}.html" target="_top" class="${u.id === first.id ? 'active' : ''}">${escHtml(u.code)}</a>`).join('')}
    </nav>
  </header>
  <div class="viewer-main">
    <div id="tour-canvas-wrap"></div>
  </div>
</div>
<script type="module" src="./assets/viewer.js"></script>
</body></html>`;
};

/* ============================================================ README */
export const README_TXT = (proj) => `CayenaBot Showroom — ${proj.name}
Generado: ${new Date().toISOString()}

Cómo publicar este showroom:

  Opción A — Netlify Drop (más fácil, gratis, 1 minuto):
    1. Visita https://app.netlify.com/drop
    2. Arrastra esta carpeta entera (no el ZIP, la carpeta descomprimida).
    3. Te entregan una URL pública tipo https://random.netlify.app
    4. Comparte esa URL con tus clientes.

  Opción B — GitHub Pages:
    1. Crea un repo nuevo público en GitHub.
    2. Sube todos estos archivos al repo (root del repo).
    3. Settings → Pages → Source: main branch / root.
    4. URL será https://tuusuario.github.io/repo-nombre/

  Opción C — Cualquier hosting estático:
    Sube el contenido de esta carpeta a tu hosting (cPanel, S3, Vercel,
    Cloudflare Pages, etc). Asegúrate que index.html quede en la raíz.

  Opción D — Local (sin internet):
    Solo abre index.html con tu navegador. Algunos navegadores bloquean
    módulos ES vía file://. Si pasa, levanta un server local:
      python3 -m http.server 8080
    y abre http://localhost:8080.

Embed en el sitio web del cliente:
  <iframe src="URL/embed.html" style="width:100%;height:600px;border:0" allow="fullscreen"></iframe>

Estructura:
  index.html              Landing: lista de unidades.
  unit-A.html, unit-B...   Tour 3D por unidad.
  embed.html              Versión iframe-friendly.
  assets/                 CSS, JS, Three.js, datos, imágenes.

Requiere navegador con WebGL (todos los modernos).
Generado por CayenaBot v4.1 · https://cayenabot.com
`;
