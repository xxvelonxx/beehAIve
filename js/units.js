/* CayenaBot — units.js
 * Hauzd-style multi-unit management. Each unit has its own floor plan,
 * room JSON, gallery, and 3D scene. Switching active unit re-binds the
 * plan analyzer + scene + tour + gallery to that unit's data.
 *
 * The "Unidades" workspace tab shows a card grid of all units with quick
 * actions: upload plan, analyze with Gemini, build 3D, edit name/code,
 * delete. Adding a unit creates a fresh slot; the user can then upload
 * a different floor plan into it.
 */

import { activeUnit } from './app.js';
import { analyzePlan } from './plan-analyzer.js';

export function mountUnits({ state, save, toast }) {
  const panel = document.getElementById('panel-units');
  if (!panel) return {};

  function unitsArr() { return state.project?.units || []; }

  function activate(unitId) {
    if (!state.project) return;
    state.project.activeUnitId = unitId;
    save?.();
    render();
    // Notify other modules to rebind
    state.modules?.plan?.refresh?.();
    state.modules?.gallery?.refresh?.();
  }

  function addUnit() {
    if (!state.project) return;
    const code = nextCode(unitsArr().map(u => u.code));
    const u = {
      id: 'u_' + Math.random().toString(36).slice(2, 8),
      code,
      name: 'Tipo ' + code,
      planImage: null,
      rooms: [],
      galleryMeta: [],
      styleDNA: state.project.units[0]?.styleDNA ? JSON.parse(JSON.stringify(state.project.units[0].styleDNA)) : {},
    };
    state.project.units.push(u);
    state.project.activeUnitId = u.id;
    save?.();
    render();
    toast?.(`Unidad ${u.code} creada`, 'success');
  }

  function nextCode(existing) {
    const letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    for (const c of letters) if (!existing.includes(c)) return c;
    return 'U' + (existing.length + 1);
  }

  function deleteUnit(uid) {
    if (!state.project) return;
    if (state.project.units.length <= 1) {
      toast?.('Debe quedar al menos una unidad', 'error');
      return;
    }
    if (!confirm('¿Eliminar esta unidad? Su plano, habitaciones y galería se pierden.')) return;
    state.project.units = state.project.units.filter(u => u.id !== uid);
    if (state.project.activeUnitId === uid) {
      state.project.activeUnitId = state.project.units[0].id;
    }
    save?.();
    render();
  }

  function renameUnit(uid, field, value) {
    const u = unitsArr().find(x => x.id === uid);
    if (!u) return;
    u[field] = value;
    save?.();
  }

  async function readFile(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
  }

  async function uploadPlan(uid, file) {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      toast?.('Archivo muy grande (>12MB)', 'error');
      return;
    }
    const url = await readFile(file);
    const u = unitsArr().find(x => x.id === uid);
    if (!u) return;
    u.planImage = url;
    u.rooms = [];
    save?.();
    render();
    toast?.(`Plano cargado en ${u.code}. Click "Analizar AI" para detectar habitaciones.`, 'info');
  }

  async function runAnalyze(uid) {
    const u = unitsArr().find(x => x.id === uid);
    if (!u || !u.planImage) return;
    const card = panel.querySelector(`[data-unit="${uid}"]`);
    const status = card?.querySelector('.unit-status');
    if (status) { status.textContent = 'Analizando con Gemini Vision...'; status.className = 'unit-status'; }
    try {
      const rooms = await analyzePlan(u.planImage);
      u.rooms = rooms;
      save?.();
      render();
      toast?.(`${rooms.length} habitaciones detectadas en ${u.code}`, 'success');
    } catch (e) {
      if (status) { status.textContent = '✗ ' + e.message; status.className = 'unit-status error'; }
      toast?.(e.message, 'error');
    }
  }

  function build3D(uid) {
    activate(uid);
    document.querySelector('.tab[data-tab="tour"]').click();
    state.modules?.tour?.build?.();
  }

  function purify(s) { return window.DOMPurify ? window.DOMPurify.sanitize(s) : String(s).replace(/[<>]/g, ''); }

  function render() {
    const p = state.project;
    if (!p) { panel.innerHTML = ''; return; }
    panel.innerHTML = '';
    const wrap = document.createElement('div');
    wrap.className = 'units-wrap';
    const header = document.createElement('div');
    header.className = 'units-header';
    header.innerHTML = `
      <div>
        <h3 style="margin:0">Unidades del proyecto</h3>
        <p class="muted" style="margin:4px 0 0;font-size:13px">Cada unidad = un tipo de apartamento. Sube su plano, analízalo con AI, y construye su tour 3D.</p>
      </div>
      <button class="primary-btn" id="add-unit-btn">＋ Agregar unidad</button>
    `;
    wrap.appendChild(header);

    const grid = document.createElement('div');
    grid.className = 'units-grid';
    p.units.forEach(u => {
      const card = document.createElement('article');
      card.className = 'unit-card' + (u.id === p.activeUnitId ? ' active' : '');
      card.dataset.unit = u.id;
      const isActive = u.id === p.activeUnitId;

      const thumb = document.createElement('div');
      thumb.className = 'unit-thumb';
      if (u.planImage) {
        const img = document.createElement('img');
        img.src = u.planImage;
        thumb.appendChild(img);
      } else {
        thumb.textContent = '📐';
      }
      card.appendChild(thumb);

      const body = document.createElement('div');
      body.className = 'unit-body';
      body.innerHTML = purify(`
        <div class="unit-row">
          <input class="unit-code" data-unit="${u.id}" data-field="code" value="${u.code}" maxlength="4" />
          <input class="unit-name" data-unit="${u.id}" data-field="name" value="${u.name}" placeholder="Nombre del tipo" />
        </div>
        <div class="unit-meta">
          <span>${u.rooms?.length || 0} habitaciones</span>
          <span>${u.galleryMeta?.length || 0} imágenes</span>
        </div>
        <div class="unit-status"></div>
      `);
      card.appendChild(body);

      const actions = document.createElement('div');
      actions.className = 'unit-actions';

      const fileInput = document.createElement('input');
      fileInput.type = 'file';
      fileInput.accept = 'image/*';
      fileInput.hidden = true;
      fileInput.onchange = (e) => uploadPlan(u.id, e.target.files?.[0]);
      const uploadBtn = document.createElement('button');
      uploadBtn.className = 'secondary-btn';
      uploadBtn.textContent = u.planImage ? '🔄 Cambiar plano' : '⬆ Subir plano';
      uploadBtn.onclick = () => fileInput.click();
      actions.append(fileInput, uploadBtn);

      if (u.planImage) {
        const analyzeBtn = document.createElement('button');
        analyzeBtn.className = 'secondary-btn';
        analyzeBtn.textContent = u.rooms?.length ? '🔁 Re-analizar' : '🤖 Analizar AI';
        analyzeBtn.onclick = () => runAnalyze(u.id);
        actions.appendChild(analyzeBtn);
      }

      if (u.rooms?.length) {
        const buildBtn = document.createElement('button');
        buildBtn.className = 'primary-btn';
        buildBtn.textContent = '🏠 Editar 3D';
        buildBtn.onclick = () => build3D(u.id);
        actions.appendChild(buildBtn);
      }

      const activateBtn = document.createElement('button');
      activateBtn.className = 'secondary-btn';
      activateBtn.textContent = isActive ? '✓ Activa' : 'Activar';
      activateBtn.disabled = isActive;
      activateBtn.onclick = () => activate(u.id);
      actions.appendChild(activateBtn);

      const delBtn = document.createElement('button');
      delBtn.className = 'secondary-btn danger-btn';
      delBtn.textContent = '🗑';
      delBtn.title = 'Eliminar unidad';
      delBtn.onclick = () => deleteUnit(u.id);
      actions.appendChild(delBtn);

      card.appendChild(actions);
      grid.appendChild(card);
    });
    wrap.appendChild(grid);
    panel.appendChild(wrap);

    // Wire field changes
    panel.querySelectorAll('.unit-code, .unit-name').forEach(inp => {
      inp.addEventListener('change', (e) => {
        const uid = e.target.dataset.unit;
        const field = e.target.dataset.field;
        const v = e.target.value.trim();
        if (v) renameUnit(uid, field, v);
      });
    });

    panel.querySelector('#add-unit-btn').onclick = addUnit;
  }

  function onTabChange(tab) {
    if (tab === 'units') render();
  }

  render();
  return { render, onTabChange, activate, addUnit };
}
