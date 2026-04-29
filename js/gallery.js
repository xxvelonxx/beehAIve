/* CayenaBot — gallery.js
 * Image grid + lightbox + downloads. Images live in IndexedDB (idb-keyval),
 * NOT localStorage (R9 — base64 blobs blow past the 5-10MB cap).
 */

const idb = window.idbKeyval; // UMD global

const MAX_IMAGES_PER_PROJECT = 50;

function imgKey(projectId, key) { return `cayenabot_img_${projectId}_${key}`; }

export function mountGallery({ state, save, toast }) {
  const grid = document.getElementById('gallery-grid');
  const empty = document.getElementById('gallery-empty');
  const downloadAllBtn = document.getElementById('download-all-btn');

  async function refresh() {
    const p = state.project;
    grid.innerHTML = '';
    if (!p?.galleryMeta?.length) {
      empty.hidden = false;
      return;
    }
    empty.hidden = true;

    for (const meta of p.galleryMeta) {
      const url = await idb.get(imgKey(p.id, meta.key));
      if (!url) continue;
      const card = document.createElement('div');
      card.className = 'gallery-item';
      const img = document.createElement('img');
      img.src = url;
      img.loading = 'lazy';
      img.alt = meta.caption || '';
      const cap = document.createElement('div');
      cap.className = 'gallery-caption';
      cap.textContent = (meta.caption || meta.source || '').slice(0, 60);
      card.append(img, cap);
      card.onclick = () => openLightbox(url, meta);
      grid.appendChild(card);
    }
  }

  function openLightbox(url, meta) {
    const lb = document.createElement('div');
    lb.className = 'lightbox';
    lb.innerHTML = `<button class="close" type="button">✕</button>`;
    const img = document.createElement('img');
    img.src = url;
    lb.appendChild(img);
    const dl = document.createElement('a');
    dl.href = url;
    dl.download = `cayenabot_${(meta.caption || 'render').replace(/\W+/g, '_').slice(0, 30)}.jpg`;
    dl.textContent = '⬇ Descargar';
    dl.style.cssText = 'position:absolute;bottom:24px;left:50%;transform:translateX(-50%);background:#c4773b;color:white;padding:10px 20px;border-radius:8px;text-decoration:none;font-weight:600;';
    lb.appendChild(dl);
    lb.addEventListener('click', (e) => {
      if (e.target === lb || e.target.classList.contains('close')) lb.remove();
    });
    document.body.appendChild(lb);
  }

  async function addImage(dataUrl, meta = {}) {
    const p = state.project;
    if (!p) return;
    p.galleryMeta = p.galleryMeta || [];
    // Cap and evict oldest
    if (p.galleryMeta.length >= MAX_IMAGES_PER_PROJECT) {
      const old = p.galleryMeta.shift();
      try { await idb.del(imgKey(p.id, old.key)); } catch {}
      toast?.(`Galería llena (${MAX_IMAGES_PER_PROJECT}). Imagen más antigua eliminada.`, 'info');
    }
    const key = 'k_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2, 7);
    await idb.set(imgKey(p.id, key), dataUrl);
    const m = { key, caption: meta.caption || '', source: meta.source || '', ts: Date.now() };
    p.galleryMeta.push(m);
    // Save first thumbnail as project thumb
    if (!p.thumbDataUrl) {
      p.thumbDataUrl = await downscale(dataUrl, 400);
    }
    save?.();
    refresh();
    return key;
  }

  async function downscale(dataUrl, maxW = 400) {
    return new Promise((res) => {
      const img = new Image();
      img.onload = () => {
        const ratio = Math.min(1, maxW / img.width);
        const w = Math.round(img.width * ratio);
        const h = Math.round(img.height * ratio);
        const cv = document.createElement('canvas');
        cv.width = w; cv.height = h;
        cv.getContext('2d').drawImage(img, 0, 0, w, h);
        res(cv.toDataURL('image/jpeg', 0.7));
      };
      img.onerror = () => res(dataUrl);
      img.src = dataUrl;
    });
  }

  async function getAllImages() {
    const p = state.project;
    if (!p?.galleryMeta) return [];
    const out = [];
    for (const m of p.galleryMeta) {
      const url = await idb.get(imgKey(p.id, m.key));
      if (url) out.push({ ...m, dataUrl: url });
    }
    return out;
  }

  downloadAllBtn.onclick = async () => {
    const all = await getAllImages();
    if (!all.length) return toast?.('No hay imágenes', 'info');
    all.forEach((m, i) => {
      const a = document.createElement('a');
      a.href = m.dataUrl;
      a.download = `cayenabot_${i + 1}_${(m.caption || 'render').replace(/\W+/g, '_').slice(0, 24)}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    });
  };

  refresh();
  return { addImage, refresh, getAllImages };
}
