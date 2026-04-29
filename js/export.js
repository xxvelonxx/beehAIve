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
  for (const m of (p.galleryMeta || [])) {
    const url = await idb.get(`cayenabot_img_${state.project.id}_${m.key}`);
    if (url) p.images[m.key] = url;
  }
  return p;
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
  const items = (p.galleryMeta || []).map(m => ({ ...m, url: p.images[m.key] })).filter(x => x.url);
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
  const items = (p.galleryMeta || []).map(m => ({ ...m, url: p.images[m.key] })).filter(x => x.url);
  const dna = p.styleDNA || {};
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

${(p.rooms || []).length ? `<section class="page">
  <h2>Especificaciones</h2>
  <table class="rooms-table">
    <thead><tr><th>Código</th><th>Habitación</th><th>Dimensiones</th><th>Piso</th></tr></thead>
    <tbody>
      ${p.rooms.map(r => `<tr><td>${escapeHtml(r.code)}</td><td>${escapeHtml(r.name)}</td><td>${escapeHtml(r.estimated_dimensions)}</td><td>${escapeHtml(r.floor_material)}</td></tr>`).join('')}
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

/* ============ Standalone platform export ============ */
async function exportStandalone(state, toast) {
  // Bundles project + images into a single HTML file with a minimal viewer
  const p = await fullProjectWithImages(state);
  const items = (p.galleryMeta || []).map(m => ({ ...m, url: p.images[m.key] })).filter(x => x.url);
  const html = `<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"><title>${escapeHtml(p.name)}</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,sans-serif;background:#0b0d14;color:#fff}
header{padding:24px;border-bottom:1px solid rgba(255,255,255,0.1);text-align:center}
header h1{margin:0;font-weight:300;font-size:32px}
header p{margin:6px 0 0;color:rgba(255,255,255,0.5)}
nav{display:flex;justify-content:center;gap:8px;padding:12px;background:#11141d}
nav button{padding:8px 16px;background:none;color:#fff;border:1px solid rgba(255,255,255,0.1);border-radius:6px;cursor:pointer}
nav button.active{background:#c4773b;border-color:#c4773b}
.tab{display:none;padding:24px}.tab.active{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.grid img{width:100%;aspect-ratio:4/3;object-fit:cover;border-radius:8px;cursor:pointer}
.rooms{display:grid;gap:8px;max-width:800px;margin:0 auto}
.room{padding:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.08);border-radius:8px}
.room strong{color:#c4773b}
</style></head><body>
<header>
  <h1>${escapeHtml(p.name)}</h1>
  <p>Generado con CayenaBot · ${new Date(p.updatedAt || Date.now()).toLocaleDateString('es-DO')}</p>
</header>
<nav>
  <button class="active" onclick="showTab(this,'gal')">Galería</button>
  <button onclick="showTab(this,'rooms')">Habitaciones</button>
</nav>
<div id="gal" class="tab active">
  <div class="grid">
    ${items.map(it => `<img src="${it.url}" alt="${escapeHtml(it.caption || '')}" onclick="lightbox(this.src)">`).join('')}
  </div>
</div>
<div id="rooms" class="tab">
  <div class="rooms">
    ${(p.rooms || []).map(r => `<div class="room"><strong>${escapeHtml(r.code)} · ${escapeHtml(r.name)}</strong><br>${escapeHtml(r.estimated_dimensions)} · ${escapeHtml(r.floor_material)}</div>`).join('')}
  </div>
</div>
<script>
function showTab(btn,id){
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('active'));
  btn.classList.add('active');
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active',t.id===id));
}
function lightbox(src){
  const lb=document.createElement('div');
  lb.style.cssText='position:fixed;inset:0;background:rgba(0,0,0,0.9);display:flex;align-items:center;justify-content:center;z-index:999;cursor:pointer';
  const img=document.createElement('img');img.src=src;img.style.cssText='max-width:95vw;max-height:95vh;border-radius:8px';
  lb.appendChild(img);lb.onclick=()=>lb.remove();document.body.appendChild(lb);
}
</script></body></html>`;
  downloadFile(`cayenabot_standalone_${Date.now()}.html`, html, 'text/html');
  toast?.('Plataforma standalone exportada', 'success');
}

function escapeHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

/* ============ public mount ============ */
export function mountExport({ state, toast }) {
  document.getElementById('export-json-btn').onclick = () => exportJSON(state, toast);
  document.getElementById('export-pdf-btn').onclick = () => exportPDF(state, toast);
  document.getElementById('export-html-btn').onclick = () => exportHtmlGallery(state, toast);
  document.getElementById('export-platform-btn').onclick = () => exportStandalone(state, toast);
  return {};
}
