/* CayenaBot — app.js
 * Bootstrap, routing, project state, autosave, toasts.
 * Wires every module together.
 */

import { mountLoginScreen, getSession, endSession, findUser } from './auth.js';
import { mountConfig, getKey } from './config.js';
import { mountChat } from './chat.js';
import { mountPlanAnalyzer } from './plan-analyzer.js';
import { mountSceneBuilder } from './scene-builder.js';
import { mountTour } from './tour.js';
import { mountGallery } from './gallery.js';
import { mountRender } from './render.js';
import { mountExport } from './export.js';
import { mountStyleWizard } from './style-wizard.js';

/* ====================================================== state */
export const state = {
  user: null,           // { id, name, color, initials, emoji }
  project: null,        // active project object
  autosaveTimer: null,
  modules: {},          // mounted module references
};

/** Empty project skeleton. */
function blankProject(userId) {
  const id = 'p_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
  return {
    id,
    userId,
    name: 'Proyecto ' + new Date().toLocaleDateString('es-DO'),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    planImage: null,           // dataURL
    rooms: [],                 // [{ code, name, bbox, ... }]
    chat: [],                  // [{ role, content, ts }]
    galleryKeys: [],           // IDB keys (image binaries live in IndexedDB)
    galleryMeta: [],           // [{ key, caption, source, ts }]
    styleDNA: {},              // { architecture, interior, decoration, materials, palette, lighting }
    thumbDataUrl: null,        // small thumbnail (data URL) for project card
  };
}

/* ====================================================== persistence */
const PROJ_KEY_PREFIX = 'cayenabot_proj_';
const projKey = (uid, pid) => `${PROJ_KEY_PREFIX}${uid}_${pid}`;

export function listProjects(userId) {
  const out = [];
  for (let i = 0; i < localStorage.length; i++) {
    const k = localStorage.key(i);
    if (!k || !k.startsWith(PROJ_KEY_PREFIX + userId + '_')) continue;
    try { out.push(JSON.parse(localStorage.getItem(k))); } catch {}
  }
  return out.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
}

export function saveProject(p) {
  if (!p) return;
  p.updatedAt = Date.now();
  try {
    localStorage.setItem(projKey(p.userId, p.id), JSON.stringify(p));
    setAutosaveStatus('Guardado ✓');
  } catch (err) {
    console.error(err);
    toast('Error guardando: localStorage lleno. Exporta el proyecto a JSON.', 'error');
  }
}

export function deleteProject(userId, projectId) {
  localStorage.removeItem(projKey(userId, projectId));
}

export function setAutosaveStatus(msg) {
  const el = document.getElementById('autosave-indicator');
  if (!el) return;
  el.textContent = msg;
  el.classList.add('saved');
  clearTimeout(setAutosaveStatus._t);
  setAutosaveStatus._t = setTimeout(() => { el.textContent = ''; el.classList.remove('saved'); }, 2000);
}

/* ====================================================== routing */
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.toggle('active', s.id === id));
}

export function goLogin() {
  state.user = null;
  state.project = null;
  showScreen('login-screen');
  mountLoginScreen(onLoginSuccess);
}

function onLoginSuccess(user) {
  state.user = user;
  goProjects();
}

export function goProjects() {
  state.project = null;
  if (state.autosaveTimer) clearInterval(state.autosaveTimer);
  showScreen('projects-screen');
  renderProjectsScreen();
}

export function goWorkspace(project) {
  state.project = project;
  saveProject(project);
  showScreen('workspace-screen');
  renderWorkspace();

  // Autosave every 30s
  if (state.autosaveTimer) clearInterval(state.autosaveTimer);
  state.autosaveTimer = setInterval(() => { if (state.project) saveProject(state.project); }, 30000);
}

/* ====================================================== projects screen */
function renderProjectsScreen() {
  const u = state.user;
  document.getElementById('current-user-badge').style.background = u.color;
  document.getElementById('current-user-badge').textContent = u.initials;

  const grid = document.getElementById('projects-grid');
  const empty = document.getElementById('projects-empty');
  const projects = listProjects(u.id);
  grid.innerHTML = '';
  empty.hidden = projects.length > 0;

  projects.forEach(p => {
    const card = document.createElement('article');
    card.className = 'project-card';

    const thumb = document.createElement('div');
    thumb.className = 'project-thumb';
    if (p.thumbDataUrl) {
      const img = document.createElement('img');
      img.src = p.thumbDataUrl;
      thumb.appendChild(img);
    } else {
      thumb.textContent = '🏛';
    }

    const meta = document.createElement('div');
    meta.className = 'project-meta';
    const nm = document.createElement('div');
    nm.className = 'name';
    nm.textContent = p.name;
    const dt = document.createElement('div');
    dt.className = 'date';
    dt.textContent = new Date(p.updatedAt || p.createdAt).toLocaleString('es-DO');
    meta.append(nm, dt);

    const actions = document.createElement('div');
    actions.className = 'project-card-actions';
    const openBtn = document.createElement('button');
    openBtn.textContent = 'Abrir';
    openBtn.onclick = () => goWorkspace(p);
    const delBtn = document.createElement('button');
    delBtn.className = 'danger';
    delBtn.textContent = 'Eliminar';
    delBtn.onclick = () => {
      if (confirm(`¿Eliminar "${p.name}"? No se puede deshacer.`)) {
        deleteProject(u.id, p.id);
        renderProjectsScreen();
      }
    };
    actions.append(openBtn, delBtn);

    card.append(thumb, meta, actions);
    card.addEventListener('click', (e) => {
      if (e.target.closest('button')) return;
      goWorkspace(p);
    });
    grid.appendChild(card);
  });
}

/* ====================================================== workspace */
function renderWorkspace() {
  const p = state.project;
  document.getElementById('project-name').value = p.name;
  document.getElementById('project-name').oninput = (e) => {
    p.name = e.target.value;
    saveProject(p);
  };

  // Tab switching
  document.querySelectorAll('.tab').forEach(t => {
    t.onclick = () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.toggle('active', x === t));
      const target = t.dataset.tab;
      document.querySelectorAll('.tab-panel').forEach(pn => pn.classList.toggle('active', pn.dataset.panel === target));
      // Notify modules of tab change
      Object.values(state.modules).forEach(m => m?.onTabChange?.(target));
    };
  });

  // Mount sub-modules (idempotent — they manage their own state)
  state.modules.plan = mountPlanAnalyzer({ state, save: () => saveProject(p), toast });
  state.modules.scene = mountSceneBuilder({ state, toast });
  state.modules.tour = mountTour({ state, scene: state.modules.scene, toast });
  state.modules.gallery = mountGallery({ state, save: () => saveProject(p), toast });
  state.modules.render = mountRender({ state, gallery: state.modules.gallery, toast });
  state.modules.chat = mountChat({ state, save: () => saveProject(p), toast });
  state.modules.exporter = mountExport({ state, toast });

  // Top bar buttons
  document.getElementById('save-project-btn').onclick = () => { saveProject(p); toast('Proyecto guardado', 'success'); };
  document.getElementById('back-to-projects').onclick = () => { saveProject(p); goProjects(); };
  document.getElementById('style-wizard-btn').onclick = () => state.modules.wizard?.open();
}

/* ====================================================== toasts */
export function toast(msg, kind = 'info', ms = 3200) {
  const stack = document.getElementById('toast-stack');
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.textContent = msg;
  stack.appendChild(el);
  setTimeout(() => el.remove(), ms);
}

/* ====================================================== boot */
function boot() {
  // Wire global topbar / modal buttons that exist before workspace mount
  document.getElementById('logout-btn').onclick = () => { endSession(); goLogin(); };
  document.getElementById('open-config-btn').onclick = () => mountConfig({ toast });

  document.getElementById('new-project-btn').onclick = () => {
    const p = blankProject(state.user.id);
    saveProject(p);
    goWorkspace(p);
  };

  document.getElementById('import-project-input').onchange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const obj = JSON.parse(text);
      if (!obj.id || !obj.userId) throw new Error('Formato inválido');
      // Re-namespace under current user
      obj.userId = state.user.id;
      obj.id = 'p_imp_' + Date.now().toString(36);
      saveProject(obj);
      renderProjectsScreen();
      toast('Proyecto importado', 'success');
    } catch (err) {
      toast('No se pudo importar: ' + err.message, 'error');
    } finally {
      e.target.value = '';
    }
  };

  // Close-modal handlers
  document.getElementById('close-config').onclick = () => { document.getElementById('config-modal').hidden = true; };
  document.getElementById('close-wizard').onclick = () => { document.getElementById('wizard-modal').hidden = true; };

  // Style wizard modal mount happens once; opening reuses it
  state.modules.wizard = mountStyleWizard({ state, save: () => state.project && saveProject(state.project), toast });

  // Resume session if present
  const session = getSession();
  if (session) {
    const u = findUser(session.userId);
    if (u) { state.user = u; goProjects(); return; }
  }
  goLogin();
}

document.addEventListener('DOMContentLoaded', boot);

/* tiny helper exposed for other modules */
export function safeHTML(el, dirty) {
  el.innerHTML = window.DOMPurify ? window.DOMPurify.sanitize(dirty) : String(dirty).replace(/[<>]/g, '');
}
