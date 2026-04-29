/* CayenaBot — tour.js
 * Hauzd-style tour UI: floor plan minimap, mode bar, smooth camera flights,
 * URL deep-linking ?isTour=1&room=2&mode=walk, walk-forward button.
 */

import { activeUnit } from './app.js';

export function mountTour({ state, scene, toast }) {
  const wrap = document.getElementById('tour-canvas-wrap');
  const empty = document.getElementById('tour-empty');
  let modeBar = null;
  let minimap = null;
  let infoBar = null;
  let walkBtn = null;
  let activeRoomCode = null;

  function clearOverlays() {
    [modeBar, minimap, infoBar, walkBtn].forEach(el => el?.remove());
    modeBar = minimap = infoBar = walkBtn = null;
  }

  function build() {
    // URL deep-link: switch active unit BEFORE reading rooms
    const u0 = new URL(location.href);
    if (u0.searchParams.get('isTour') === '1') {
      const unitCode = u0.searchParams.get('unit');
      if (unitCode && state.project?.units) {
        const target = state.project.units.find(x => x.code === unitCode);
        if (target) state.project.activeUnitId = target.id;
      }
    }

    const u = activeUnit(state.project);
    if (!u?.rooms?.length) {
      empty.hidden = false;
      wrap.hidden = true;
      return;
    }
    empty.hidden = true;
    wrap.hidden = false;
    clearOverlays();

    scene.build(u.rooms, u.styleDNA || {});
    activeRoomCode = u.rooms[0].code;
    buildModeBar();
    buildMinimap();
    buildInfoBar();
    buildWalkBtn();

    // URL deep-link extras (room, mode, night, furniture)
    if (u0.searchParams.get('isTour') === '1') {
      const r = u0.searchParams.get('room');
      const m = u0.searchParams.get('mode');
      const night = u0.searchParams.get('night') === '1';
      const noFurn = u0.searchParams.get('furniture') === '0';
      if (r && u.rooms[parseInt(r, 10)]) flyTo(u.rooms[parseInt(r, 10)].code);
      if (m === 'walk') scene.setMode('walk');
      if (night) scene.setDayNight(true);
      if (noFurn) scene.setFurnitureVisible(false);
    }

    scene.onUpdate(({ position }) => {
      drawMinimap(position);
    });

    document.addEventListener('keydown', onKey);
  }

  function onKey(e) {
    const u = activeUnit(state.project);
    if (!u?.rooms?.length) return;
    const idx = u.rooms.findIndex(r => r.code === activeRoomCode);
    if (e.key === 'ArrowRight') flyTo(u.rooms[(idx + 1) % u.rooms.length].code);
    if (e.key === 'ArrowLeft')  flyTo(p.rooms[(idx - 1 + p.rooms.length) % p.rooms.length].code);
  }

  function buildModeBar() {
    modeBar = document.createElement('div');
    modeBar.className = 'tour-mode-bar';
    const modes = [
      { id: 'dollhouse', label: '🏠 3D' },
      { id: 'walk', label: '🚶 Walk' },
    ];
    modes.forEach(m => {
      const b = document.createElement('button');
      b.textContent = m.label;
      b.dataset.modeId = m.id;
      if (m.id === scene.mode) b.classList.add('active');
      b.onclick = () => {
        modeBar.querySelectorAll('button[data-mode-id]').forEach(x => x.classList.remove('active'));
        b.classList.add('active');
        scene.setMode(m.id);
        if (walkBtn) walkBtn.classList.toggle('visible', m.id === 'walk');
      };
      modeBar.appendChild(b);
    });

    // Separator
    const sep = document.createElement('span');
    sep.style.cssText = 'width:1px;background:rgba(255,255,255,0.1);margin:4px 6px';
    modeBar.appendChild(sep);

    // Day/night toggle
    const dayNightBtn = document.createElement('button');
    dayNightBtn.textContent = '☀️ Día';
    dayNightBtn.title = 'Alternar día / noche';
    dayNightBtn.dataset.toggle = 'daynight';
    dayNightBtn.onclick = () => {
      const goingNight = !scene.isNight;
      scene.setDayNight(goingNight);
      dayNightBtn.textContent = goingNight ? '🌙 Noche' : '☀️ Día';
      dayNightBtn.classList.toggle('active', goingNight);
    };
    modeBar.appendChild(dayNightBtn);

    // Furniture toggle
    const furnBtn = document.createElement('button');
    furnBtn.textContent = '🪑 Muebles';
    furnBtn.title = 'Mostrar / ocultar muebles';
    furnBtn.dataset.toggle = 'furniture';
    furnBtn.classList.add('active'); // default visible
    furnBtn.onclick = () => {
      const next = !scene.furnitureVisible;
      scene.setFurnitureVisible(next);
      furnBtn.classList.toggle('active', next);
      furnBtn.textContent = next ? '🪑 Muebles' : '🏗 Estructura';
    };
    modeBar.appendChild(furnBtn);

    wrap.appendChild(modeBar);
  }

  function buildMinimap() {
    minimap = document.createElement('div');
    minimap.className = 'tour-minimap';
    const lbl = document.createElement('div'); lbl.className = 'label'; lbl.textContent = 'Plano';
    const cv = document.createElement('canvas');
    cv.width = 320; cv.height = 200;
    minimap.append(lbl, cv);
    minimap.addEventListener('click', (e) => {
      // Toggle expand
      if (e.target === lbl) {
        minimap.classList.toggle('expanded');
        return;
      }
      // Click on a room → fly there
      const rect = cv.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width) * 100;
      const y = ((e.clientY - rect.top) / rect.height) * 100;
      const u = activeUnit(state.project);
      const room = (u?.rooms || []).find(r =>
        x >= r.bbox.x && x <= r.bbox.x + r.bbox.width &&
        y >= r.bbox.y && y <= r.bbox.y + r.bbox.height
      );
      if (room) flyTo(room.code);
    });
    wrap.appendChild(minimap);
    drawMinimap();
  }

  function drawMinimap(camPos = null) {
    if (!minimap) return;
    const cv = minimap.querySelector('canvas');
    const ctx = cv.getContext('2d');
    const W = cv.width, H = cv.height;
    ctx.fillStyle = '#0a0e1a';
    ctx.fillRect(0, 0, W, H);
    const rooms = activeUnit(state.project)?.rooms || [];
    rooms.forEach(r => {
      const x = (r.bbox.x / 100) * W;
      const y = (r.bbox.y / 100) * H;
      const w = (r.bbox.width / 100) * W;
      const h = (r.bbox.height / 100) * H;
      ctx.fillStyle = r.code === activeRoomCode ? 'rgba(196,119,59,0.35)' : 'rgba(255,255,255,0.08)';
      ctx.fillRect(x, y, w, h);
      ctx.strokeStyle = r.code === activeRoomCode ? '#c4773b' : 'rgba(255,255,255,0.18)';
      ctx.lineWidth = r.code === activeRoomCode ? 2 : 1;
      ctx.strokeRect(x, y, w, h);
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.font = '10px -apple-system, sans-serif';
      ctx.fillText(r.name.slice(0, 14), x + 4, y + 12);
    });
    // Camera dot (project camera world XZ to bbox space)
    if (camPos) {
      const aptW = 18, aptD = 14;
      const cxN = ((camPos.x + aptW / 2) / aptW) * W;
      const cyN = ((camPos.z + aptD / 2) / aptD) * H;
      ctx.beginPath();
      ctx.arc(cxN, cyN, 5, 0, Math.PI * 2);
      ctx.fillStyle = '#c4773b';
      ctx.shadowColor = '#c4773b';
      ctx.shadowBlur = 12;
      ctx.fill();
      ctx.shadowBlur = 0;
    }
  }

  function buildInfoBar() {
    infoBar = document.createElement('div');
    infoBar.className = 'tour-info';
    updateInfo();
    wrap.appendChild(infoBar);
  }

  function updateInfo() {
    if (!infoBar) return;
    const u = activeUnit(state.project);
    if (!u) return;
    const r = u.rooms.find(x => x.code === activeRoomCode) || u.rooms[0];
    if (!r) return;
    infoBar.innerHTML = '';
    const name = document.createElement('div');
    name.className = 'room-name';
    name.textContent = r.name;
    const dim = document.createElement('div');
    dim.textContent = r.estimated_dimensions;
    const code = document.createElement('div');
    code.style.color = 'var(--muted)';
    code.style.fontSize = '11px';
    code.textContent = r.code;
    infoBar.append(name, dim, code);
  }

  function buildWalkBtn() {
    walkBtn = document.createElement('button');
    walkBtn.className = 'tour-walk-btn';
    walkBtn.textContent = '🚶';
    walkBtn.title = 'Caminar (pointer-lock + WASD)';
    walkBtn.onclick = () => {
      scene.setMode('walk');
      const dollBtn = modeBar.querySelector('button:first-child');
      const walkM = modeBar.querySelector('button:last-child');
      dollBtn.classList.remove('active');
      walkM.classList.add('active');
      walkBtn.classList.add('visible');
    };
    wrap.appendChild(walkBtn);
  }

  function flyTo(code) {
    activeRoomCode = code;
    scene.flyTo(code, 1500);
    updateInfo();
    drawMinimap(scene.camera?.position);
  }

  function onTabChange(tab) {
    scene.onTabChange?.(tab);
    if (tab === 'tour' && activeUnit(state.project)?.rooms?.length && !document.querySelector('#tour-canvas-wrap canvas')) {
      build();
    }
  }

  return { build, flyTo, onTabChange };
}
