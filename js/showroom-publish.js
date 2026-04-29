/* CayenaBot — showroom-publish.js
 * Bundle a project (multi-unit) into a self-contained showroom ZIP.
 * The ZIP has no external dependencies — all assets are bundled.
 *
 * Output structure:
 *   index.html              landing with branding + unit cards
 *   embed.html              single-iframe-friendly first-unit tour
 *   unit-A.html, unit-B.html, ...   per-unit tour pages
 *   assets/viewer.css       tour-page styling (subset of app CSS)
 *   assets/viewer.js        mini-app: builds Three.js scene from data
 *   assets/scene/*.js       scene-builder + materials + rooms + furniture + exterior (copied)
 *   assets/vendor/three/    Three.js core + addons (copied from /vendor/)
 *   assets/data/project.json    branding + units list (no images)
 *   assets/data/{unitId}.json   per-unit rooms + styleDNA
 *   assets/img/u_{unitId}_{key}.jpg  gallery images, one file each
 *   README.txt              hosting instructions
 *
 * Hosting: drag the unzipped folder to Netlify Drop, GitHub Pages,
 * any static host, OR just open index.html locally with file://.
 */

const idb = window.idbKeyval;

/* ============================================================ helpers */
function escHtml(s) {
  return String(s || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

async function fetchText(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Fetch ${url}: ${r.status}`);
  return r.text();
}

async function fetchBytes(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`Fetch ${url}: ${r.status}`);
  return r.arrayBuffer();
}

function dataUrlToBlob(dataUrl) {
  const [meta, data] = dataUrl.split(',');
  const mime = (meta.match(/data:([^;]+)/) || [, 'image/jpeg'])[1];
  const isB64 = meta.includes('base64');
  if (isB64) {
    const bin = atob(data);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return { blob: new Blob([arr], { type: mime }), mime };
  }
  return { blob: new Blob([decodeURIComponent(data)], { type: mime }), mime };
}

function extFromMime(mime) {
  if (mime.includes('png')) return 'png';
  if (mime.includes('webp')) return 'webp';
  if (mime.includes('svg')) return 'svg';
  return 'jpg';
}

function safeFilename(s) {
  return String(s || 'project').replace(/[^a-zA-Z0-9_-]+/g, '_').slice(0, 40) || 'project';
}

/* ============================================================ assemble bundle */
async function buildBundle(state, toast) {
  if (!window.JSZip) throw new Error('JSZip no cargó (vendor/jszip.min.js)');
  const zip = new window.JSZip();
  const p = state.project;
  if (!p) throw new Error('Sin proyecto activo');
  if (!p.units?.length) throw new Error('El proyecto no tiene unidades');

  const brand = p.branding || { primaryColor: '#c4773b' };

  /* ---- 1. Vendor Three.js (core + addons) ---- */
  const threeFiles = [
    'vendor/three/build/three.module.js',
    'vendor/three/examples/jsm/controls/OrbitControls.js',
    'vendor/three/examples/jsm/controls/PointerLockControls.js',
    'vendor/three/examples/jsm/geometries/RoundedBoxGeometry.js',
  ];
  for (const f of threeFiles) {
    const txt = await fetchText('./' + f);
    zip.file('assets/' + f, txt);
  }

  /* ---- 2. Scene module sources (copied verbatim) ---- */
  const sceneFiles = [
    'js/scene-builder.js',
    'js/scene-materials.js',
    'js/scene-rooms.js',
    'js/scene-furniture.js',
    'js/scene-exterior.js',
  ];
  for (const f of sceneFiles) {
    let txt = await fetchText('./' + f);
    // Rewrite import paths so the bundled scene-builder.js can find its peers
    // and the three addons. The published structure keeps js/* as
    // assets/scene/* and three/* as assets/vendor/three/*.
    txt = txt.replace(/from ['"]\.\/scene-([a-z]+)\.js['"]/g, (m, n) => `from './scene-${n}.js'`);
    zip.file('assets/scene/' + f.split('/').pop(), txt);
  }

  /* ---- 3. project + per-unit JSON (rooms, styleDNA, branding) ---- */
  const unitsMeta = p.units.map(u => ({
    id: u.id,
    code: u.code,
    name: u.name,
    roomCount: u.rooms?.length || 0,
    galleryCount: u.galleryMeta?.length || 0,
    heroImageRef: u.galleryMeta?.[0] ? `assets/img/u_${u.id}_${u.galleryMeta[0].key}.jpg` : null,
  }));

  zip.file('assets/data/project.json', JSON.stringify({
    name: p.name,
    branding: brand,
    units: unitsMeta,
    generatedAt: new Date().toISOString(),
    generator: 'CayenaBot v4.1',
  }, null, 2));

  for (const u of p.units) {
    zip.file(`assets/data/${u.id}.json`, JSON.stringify({
      id: u.id,
      code: u.code,
      name: u.name,
      rooms: u.rooms || [],
      styleDNA: u.styleDNA || {},
    }, null, 2));
  }

  /* ---- 4. Gallery images (one file per image, from IndexedDB) ---- */
  for (const u of p.units) {
    for (const m of (u.galleryMeta || [])) {
      const dataUrl = await idb.get(`cayenabot_img_${p.id}_${u.id}_${m.key}`);
      if (!dataUrl) continue;
      const { blob, mime } = dataUrlToBlob(dataUrl);
      const ext = extFromMime(mime);
      zip.file(`assets/img/u_${u.id}_${m.key}.${ext}`, blob);
    }
  }
  // Logo
  if (brand.logoDataUrl) {
    const { blob, mime } = dataUrlToBlob(brand.logoDataUrl);
    const ext = extFromMime(mime);
    zip.file(`assets/img/logo.${ext}`, blob);
    brand._logoFile = `assets/img/logo.${ext}`;
  }

  /* ---- 5. Viewer CSS + JS ---- */
  zip.file('assets/viewer.css', VIEWER_CSS(brand.primaryColor || '#c4773b'));
  zip.file('assets/viewer.js', VIEWER_JS);

  /* ---- 6. HTML pages ---- */
  zip.file('index.html', LANDING_HTML(p, brand));
  zip.file('embed.html', EMBED_HTML(p, brand));
  for (const u of p.units) {
    zip.file(`unit-${u.code}.html`, UNIT_HTML(p, brand, u));
  }

  /* ---- 7. README ---- */
  zip.file('README.txt', README_TXT(p));

  /* ---- 8. Generate ---- */
  toast?.('Empaquetando ZIP...', 'info');
  const blob = await zip.generateAsync(
    { type: 'blob', compression: 'DEFLATE', compressionOptions: { level: 6 } },
    (meta) => {
      if (meta.percent && meta.percent % 20 < 1) {
        // light progress hint
      }
    }
  );
  return blob;
}

/* ============================================================ public mount */
export function mountShowroomPublish({ state, toast }) {
  async function publishZip() {
    if (!state.project) {
      toast?.('Abre un proyecto primero', 'error');
      return;
    }
    try {
      const blob = await buildBundle(state, toast);
      const fname = `cayenabot_showroom_${safeFilename(state.project.name)}_${Date.now()}.zip`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url; a.download = fname;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => { a.remove(); URL.revokeObjectURL(url); }, 200);
      const sizeMB = (blob.size / 1024 / 1024).toFixed(1);
      toast?.(`Showroom listo (${sizeMB} MB) — descargando ${fname}`, 'success', 5000);
      // Stash bundle metadata
      state.project.published = { lastBundleAt: Date.now(), bundleSize: blob.size };
    } catch (e) {
      console.error(e);
      toast?.('Error: ' + e.message, 'error');
    }
  }

  function embedSnippet(unitCode) {
    const code = unitCode || state.project?.units?.[0]?.code || 'A';
    const fname = `cayenabot_showroom_${safeFilename(state.project?.name || 'project')}`;
    return `<iframe src="${fname}/unit-${code}.html" style="width:100%;height:600px;border:0;border-radius:12px" allow="fullscreen" loading="lazy"></iframe>`;
  }

  return { publishZip, embedSnippet };
}

/* ============================================================ TEMPLATES (filled by part 2) */
let LANDING_HTML, UNIT_HTML, EMBED_HTML, VIEWER_CSS, VIEWER_JS, README_TXT;

/* The templates module sets these on import. We pull it via a side-effect
 * import below so the bundle file stays editable in two parts without
 * a circular dep. */
import * as TPL from './showroom-templates.js';
LANDING_HTML = TPL.LANDING_HTML;
UNIT_HTML = TPL.UNIT_HTML;
EMBED_HTML = TPL.EMBED_HTML;
VIEWER_CSS = TPL.VIEWER_CSS;
VIEWER_JS = TPL.VIEWER_JS;
README_TXT = TPL.README_TXT;
