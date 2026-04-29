/* CayenaBot — export.js
 * Exports: project JSON, PDF brochure (canvas-rendered, no jsPDF dep),
 * standalone HTML gallery, fully-self-contained platform HTML.
 */

const idb = window.idbKeyval;

function downloadFile(filename, content, mime = 'application/octet-stream') {
  const blob = content instanceof Blob ? content : new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 100);
}

async function fullProjectWithImages(state) {
  const p = JSON.parse(JSON.stringify(state.project));
  p.images = {};
  // Flatten images across all units; key includes unitId to avoid collisions
  for (const u of (p.units || [])) {
    for (const m of (u.galleryMeta || [])) {
      const url = await idb.get(`cayenabot_img_${state.project.id}_${u.id}_${m.key}`);
      if (url) p.images[`${u.id}_${m.key}`] = url;
    }
  }
  return p;
}

function flatGallery(p) {
  const out = [];
  for (const u of (p.units || [])) {
    for (const m of (u.galleryMeta || [])) {
      const url = p.images[`${u.id}_${m.key}`];
      if (url) out.push({ ...m, url, unitCode: u.code, unitName: u.name });
    }
  }
  return out;
}

/* ============ JSON export ============ */
async function exportJSON(state, toast) {
  const p = await fullProjectWithImages(state);
  const json = JSON.stringify(p, null, 2);
  const fname = `cayenabot_${(p.name || 'proyecto').replace(/\W+/g, '_')}_${Date.now()}.json`;
  downloadFile(fname, json, 'application/json');
  toast?.('JSON exportado', 'success');
}

/* ============ HTML gallery export ============ */
async function exportHtmlGallery(state, toast) {
  const p = await fullProjectWithImages(state);
  const items = flatGallery(p);
  const html = `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(p.name)} — CayenaBot</title>
<style>
body{margin:0;font-family:-apple-system,sans-serif;background:#0b0d14;color:#fff;padding:20px}
h1{margin:0 0 6px;font-weight:600}
.muted{color:rgba(255,255,255,0.5);font-size:13px;margin-bottom:24px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:14px}
.item{border:1px solid rgba(255,255,255,0.1);border-radius:10px;overflow:hidden;background:rgba(255,255,255,0.03)}
.item img{width:100%;display:block;aspect-ratio:4/3;object-fit:cover}
.item .cap{padding:10px;font-size:12px}
.item .cap strong{display:block;color:#c4773b;margin-bottom:3px}
.dl{display:inline-block;padding:6px 12px;background:#c4773b;color:white;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;margin-top:6px}
</style></head><body>
<h1>${escapeHtml(p.name)}</h1>
<div class="muted">${items.length} imágenes · CayenaBot · ${new Date(p.updatedAt || Date.now()).toLocaleString('es-DO')}</div>
<div class="grid">
${items.map((it, i) => `<div class="item">
<img src="${it.url}" loading="lazy" alt="">
<div class="cap"><strong>${escapeHtml(it.caption || 'Imagen ' + (i + 1))}</strong>
<span style="color:rgba(255,255,255,0.4)">${escapeHtml(it.source || '')}</span><br>
<a class="dl" href="${it.url}" download="cayenabot_${i + 1}.jpg">⬇ Descargar</a></div></div>`).join('\n')}
</div></body></html>`;
  downloadFile(`cayenabot_galeria_${Date.now()}.html`, html, 'text/html');
  toast?.('Galería HTML exportada', 'success');
}

/* ============ PDF brochure (canvas-rendered, no external lib) ============ */
async function exportPDF(state, toast) {
  // Strategy: render an A4-landscape brochure to canvas, save as a single
  // image PDF using a minimal hand-rolled writer. To keep dependency-free
  // we instead emit a PRINTABLE HTML file that the user can save as PDF
  // via browser. This is more reliable than embedding a PDF library.
  const p = await fullProjectWithImages(state);
  const items = flatGallery(p);
  const allRooms = (p.units || []).flatMap(u => (u.rooms || []).map(r => ({ ...r, unitCode: u.code, unitName: u.name })));
  const dna = (p.units?.[0]?.styleDNA) || {};
  const dnaList = Object.values(dna).map(d => d?.name).filter(Boolean).join(' · ');

  const html = `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>${escapeHtml(p.name)} — Brochure</title>
<style>
@page { size: A4 landscape; margin: 12mm; }
body{margin:0;font-family:Georgia,serif;color:#1a1a1a;background:#f8f5ef}
.cover{height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center;text-align:center;background:linear-gradient(135deg,#f8f5ef,#e8dfd0);page-break-after:always}
.cover h1{font-size:64px;margin:0;font-weight:300;letter-spacing:-1px}
.cover .sub{margin-top:18px;font-style:italic;color:#8a7a5e;font-size:18px}
.cover .dna{margin-top:32px;font-size:13px;letter-spacing:2px;text-transform:uppercase;color:#c4773b}
.page{height:100vh;display:flex;flex-direction:column;page-break-after:always;padding:20px}
.page h2{font-weight:300;font-size:32px;border-bottom:1px solid #c4773b;padding-bottom:8px}
.gallery{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;flex:1;align-content:start}
.gallery img{width:100%;height:100%;object-fit:cover;max-height:240px;border-radius:4px}
.rooms-table{width:100%;border-collapse:collapse;font-size:13px}
.rooms-table th{text-align:left;border-bottom:2px solid #c4773b;padding:6px 10px}
.rooms-table td{border-bottom:1px solid #ddd;padding:6px 10px}
.footer{margin-top:auto;padding-top:14px;font-size:11px;color:#888;border-top:1px solid #ddd;display:flex;justify-content:space-between}
</style></head><body>

<section class="cover">
  <h1>${escapeHtml(p.name)}</h1>
  <div class="sub">Una propiedad presentada por CayenaBot</div>
  ${dnaList ? `<div class="dna">${escapeHtml(dnaList)}</div>` : ''}
</section>

${items.length ? `<section class="page">
  <h2>Galería</h2>
  <div class="gallery">
    ${items.slice(0, 6).map(it => `<img src="${it.url}" alt="">`).join('')}
  </div>
  <div class="footer"><span>CayenaBot · República Dominicana</span><span>${new Date().toLocaleDateString('es-DO')}</span></div>
</section>` : ''}

${allRooms.length ? `<section class="page">
  <h2>Especificaciones</h2>
  <table class="rooms-table">
    <thead><tr><th>Unidad</th><th>Código</th><th>Habitación</th><th>Dimensiones</th><th>Piso</th></tr></thead>
    <tbody>
      ${allRooms.map(r => `<tr><td>${escapeHtml(r.unitCode)} · ${escapeHtml(r.unitName)}</td><td>${escapeHtml(r.code)}</td><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.estimated_dimensions)}</td><td>${escapeHtml(r.floor_material)}</td></tr>`).join('')}
    </tbody>
  </table>
  <div class="footer"><span>CayenaBot · ${escapeHtml(p.name)}</span><span>${new Date().toLocaleDateString('es-DO')}</span></div>
</section>` : ''}

<script>
window.addEventListener('load', () => setTimeout(() => window.print(), 400));
</script>
</body></html>`;

  const w = window.open('', '_blank');
  if (!w) { toast?.('Permite popups para generar el PDF', 'error'); return; }
  w.document.write(html);
  w.document.close();
  toast?.('Usa el diálogo de impresión → Guardar como PDF', 'info');
}

/* The legacy "standalone HTML" export is replaced by Publish Showroom (ZIP)
 * in showroom-publish.js — wired from the Publicar tab via mountExport. */

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ============ public mount ============ */
export function mountExport({ state, toast }) {
  const $ = (id) => document.getElementById(id);
  $('export-json-btn') && ($('export-json-btn').onclick = () => exportJSON(state, toast));
  $('export-pdf-btn')  && ($('export-pdf-btn').onclick  = () => exportPDF(state, toast));
  $('export-html-btn') && ($('export-html-btn').onclick = () => exportHtmlGallery(state, toast));
  // Publish ZIP button (delegated to the publish module)
  const pubBtn = $('publish-zip-btn');
  if (pubBtn) {
    pubBtn.onclick = async () => {
      pubBtn.disabled = true;
      const orig = pubBtn.textContent;
      pubBtn.textContent = 'Empaquetando...';
      try {
        await state.modules?.publish?.publishZip();
      } finally {
        pubBtn.disabled = false;
        pubBtn.textContent = orig;
      }
    };
  }
  return {};
}
