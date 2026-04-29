/* CayenaBot — plan-analyzer.js
 * Floor plan upload → OpenRouter Gemini 2.5 Flash vision → room JSON.
 * Defensive: robust JSON extraction, bbox validation, fallback model.
 */

import { getKey, VISION_MODELS } from './config.js';

const ANALYSIS_PROMPT = `Eres un arquitecto. Analiza este plano arquitectónico y devuelve EXCLUSIVAMENTE un JSON array (sin markdown, sin explicación) con TODAS las habitaciones visibles.

Cada objeto debe tener exactamente estos campos:
{
  "code": "A-01",
  "name": "Sala / Living",
  "bbox": { "x": 10, "y": 5, "width": 30, "height": 25 },
  "estimated_dimensions": "6.5m x 4.2m",
  "wall_north": "ventanal piso-techo con vista al mar",
  "wall_south": "puerta doble hacia comedor",
  "wall_east": "pared sólida con arte",
  "wall_west": "abierto hacia terraza",
  "floor_material": "porcelanato italiano gran formato",
  "ceiling_height": "2.8m"
}

Reglas:
- bbox es porcentaje (0-100) del plano completo: x e y son la esquina superior-izquierda; width y height el tamaño.
- Las habitaciones NO deben superponerse más del 20%.
- Para cada pared (north/south/east/west), describe en español lo que hay: "puerta", "ventana", "ventanal", "abierto", "pared sólida", o combinaciones cortas.
- Estima dimensiones en metros con base en escala típica residencial.
- Si no estás seguro de un campo, da tu mejor estimación; nunca devuelvas null.

Devuelve SOLO el JSON array, empezando con [ y terminando con ].`;

/* ====================================================== robust JSON parsing */
function extractJsonArray(text) {
  if (!text) throw new Error('Respuesta vacía');
  let t = String(text).trim();

  // Strip ```json fences
  t = t.replace(/^```(?:json)?\s*/i, '').replace(/```\s*$/, '');

  // First [ ... last ]
  const first = t.indexOf('[');
  const last = t.lastIndexOf(']');
  if (first === -1 || last === -1 || last < first) {
    throw new Error('No se encontró array JSON en la respuesta');
  }
  let chunk = t.slice(first, last + 1);

  // Fix common issues: trailing commas, smart quotes
  chunk = chunk
    .replace(/[“”]/g, '"')
    .replace(/[‘’]/g, "'")
    .replace(/,(\s*[\]}])/g, '$1');

  try {
    return JSON.parse(chunk);
  } catch (e) {
    // Last resort: try removing trailing comments
    const cleaned = chunk.replace(/\/\/[^\n]*/g, '').replace(/\/\*[\s\S]*?\*\//g, '');
    return JSON.parse(cleaned);
  }
}

/* ====================================================== validation */
function validateRooms(rooms) {
  if (!Array.isArray(rooms) || rooms.length === 0) {
    throw new Error('No se detectaron habitaciones');
  }

  // All bboxes at 0,0 → model failed
  const allZero = rooms.every(r =>
    !r.bbox || (Number(r.bbox.x) === 0 && Number(r.bbox.y) === 0)
  );
  if (allZero) throw new Error('El modelo no entendió el plano (todas las habitaciones en 0,0). Sube una imagen más clara.');

  // Normalize + clamp values
  rooms.forEach((r, i) => {
    r.code = String(r.code || `A-${String(i + 1).padStart(2, '0')}`);
    r.name = String(r.name || `Habitación ${i + 1}`);
    r.bbox = {
      x: clamp(Number(r.bbox?.x) || 0, 0, 100),
      y: clamp(Number(r.bbox?.y) || 0, 0, 100),
      width: clamp(Number(r.bbox?.width) || 10, 1, 100),
      height: clamp(Number(r.bbox?.height) || 10, 1, 100),
    };
    r.estimated_dimensions = String(r.estimated_dimensions || '4m x 4m');
    r.wall_north = String(r.wall_north || 'pared sólida');
    r.wall_south = String(r.wall_south || 'pared sólida');
    r.wall_east = String(r.wall_east || 'pared sólida');
    r.wall_west = String(r.wall_west || 'pared sólida');
    r.floor_material = String(r.floor_material || 'porcelanato');
    r.ceiling_height = String(r.ceiling_height || '2.7m');
  });

  // Reject if pairwise overlap >50% of smaller area for too many pairs
  let badOverlaps = 0;
  for (let i = 0; i < rooms.length; i++) {
    for (let j = i + 1; j < rooms.length; j++) {
      const ovr = bboxOverlapRatio(rooms[i].bbox, rooms[j].bbox);
      if (ovr > 0.5) badOverlaps++;
    }
  }
  if (badOverlaps > rooms.length / 2) {
    throw new Error('Habitaciones superpuestas. El modelo no separó bien los espacios — reintenta con un plano más limpio.');
  }
  return rooms;
}

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function bboxOverlapRatio(a, b) {
  const ax2 = a.x + a.width, ay2 = a.y + a.height;
  const bx2 = b.x + b.width, by2 = b.y + b.height;
  const ox = Math.max(0, Math.min(ax2, bx2) - Math.max(a.x, b.x));
  const oy = Math.max(0, Math.min(ay2, by2) - Math.max(a.y, b.y));
  const inter = ox * oy;
  const minArea = Math.min(a.width * a.height, b.width * b.height);
  return minArea > 0 ? inter / minArea : 0;
}

/* ====================================================== call OpenRouter */
async function callVision(model, dataUrl, key) {
  const resp = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + key,
      'Content-Type': 'application/json',
      'HTTP-Referer': location.href,
      'X-Title': 'CayenaBot',
    },
    body: JSON.stringify({
      model,
      messages: [{
        role: 'user',
        content: [
          { type: 'image_url', image_url: { url: dataUrl, detail: 'high' } },
          { type: 'text', text: ANALYSIS_PROMPT },
        ],
      }],
      max_tokens: 4000,
      temperature: 0.2,
    }),
  });

  if (!resp.ok) {
    const txt = await resp.text().catch(() => '');
    throw new Error(`Vision API ${resp.status}: ${txt.slice(0, 200)}`);
  }
  const j = await resp.json();
  const content = j?.choices?.[0]?.message?.content;
  if (!content) throw new Error('Sin contenido en la respuesta');
  return content;
}

export async function analyzePlan(dataUrl) {
  const key = getKey('openrouter');
  if (!key) throw new Error('Configura tu API key de OpenRouter en ⚙ Configuración.');

  let lastErr = null;
  for (const model of VISION_MODELS) {
    try {
      const raw = await callVision(model, dataUrl, key);
      const arr = extractJsonArray(raw);
      return validateRooms(arr);
    } catch (e) {
      lastErr = e;
      console.warn(`[plan-analyzer] ${model} falló:`, e.message);
    }
  }
  throw lastErr || new Error('Análisis falló en todos los modelos');
}

/* ====================================================== UI mount */
export function mountPlanAnalyzer({ state, save, toast }) {
  const dropzone = document.getElementById('plan-dropzone');
  const input = document.getElementById('plan-file-input');
  const previewWrap = document.getElementById('plan-preview-wrap');
  const preview = document.getElementById('plan-preview');
  const status = document.getElementById('plan-status');
  const roomsList = document.getElementById('rooms-list');
  const buildActions = document.getElementById('build-actions');
  const analyzeBtn = document.getElementById('analyze-plan-btn');
  const clearBtn = document.getElementById('clear-plan-btn');
  const buildBtn = document.getElementById('build-3d-btn');

  function refresh() {
    const p = state.project;
    if (!p) return;
    if (p.planImage) {
      preview.src = p.planImage;
      previewWrap.hidden = false;
    } else {
      previewWrap.hidden = true;
    }
    renderRooms(p.rooms);
  }

  function renderRooms(rooms) {
    roomsList.innerHTML = '';
    if (!rooms || !rooms.length) {
      buildActions.hidden = true;
      return;
    }
    rooms.forEach(r => {
      const div = document.createElement('div');
      div.className = 'room-card';
      const c = document.createElement('span'); c.className = 'code'; c.textContent = r.code;
      const n = document.createElement('span'); n.className = 'name'; n.textContent = r.name;
      const d = document.createElement('span'); d.className = 'dim'; d.textContent = r.estimated_dimensions;
      div.append(c, n, d);
      roomsList.appendChild(div);
    });
    buildActions.hidden = false;
  }

  function readFile(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
  }

  async function handleFile(file) {
    if (!file) return;
    if (file.size > 12 * 1024 * 1024) {
      toast('Archivo muy grande (>12MB). Reduce la imagen.', 'error');
      return;
    }
    const url = await readFile(file);
    state.project.planImage = url;
    state.project.rooms = [];
    save();
    refresh();
    status.textContent = 'Plano cargado. Click "Analizar plano con AI" para detectar habitaciones.';
    status.className = 'status-line';
  }

  dropzone.onclick = () => input.click();
  input.onchange = (e) => handleFile(e.target.files?.[0]);

  ['dragenter', 'dragover'].forEach(ev => dropzone.addEventListener(ev, (e) => {
    e.preventDefault(); dropzone.classList.add('dragover');
  }));
  ['dragleave', 'drop'].forEach(ev => dropzone.addEventListener(ev, (e) => {
    e.preventDefault(); dropzone.classList.remove('dragover');
  }));
  dropzone.addEventListener('drop', (e) => {
    e.preventDefault();
    handleFile(e.dataTransfer?.files?.[0]);
  });

  clearBtn.onclick = () => {
    state.project.planImage = null;
    state.project.rooms = [];
    save();
    refresh();
    status.textContent = '';
  };

  analyzeBtn.onclick = async () => {
    const p = state.project;
    if (!p?.planImage) return;
    analyzeBtn.disabled = true;
    status.className = 'status-line';
    status.textContent = 'Analizando plano con Gemini Vision... (puede tardar 15-30s)';
    try {
      const rooms = await analyzePlan(p.planImage);
      p.rooms = rooms;
      save();
      renderRooms(rooms);
      status.className = 'status-line success';
      status.textContent = `✓ ${rooms.length} habitaciones detectadas`;
      toast(`${rooms.length} habitaciones detectadas`, 'success');
    } catch (e) {
      console.error(e);
      status.className = 'status-line error';
      status.textContent = '✗ ' + e.message;
      toast(e.message, 'error');
    } finally {
      analyzeBtn.disabled = false;
    }
  };

  buildBtn.onclick = () => {
    if (!state.project?.rooms?.length) return;
    document.querySelector('.tab[data-tab="tour"]').click();
    state.modules?.tour?.build?.();
  };

  refresh();
  return { refresh };
}
