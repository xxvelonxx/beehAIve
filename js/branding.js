/* CayenaBot — branding.js
 * Per-project white-label settings: developer name, logo, primary color,
 * contact (email / WhatsApp / web). Applied to the published showroom.
 */

export function mountBranding({ state, save, toast }) {
  const modal = document.getElementById('branding-modal');
  if (!modal) return { open: () => {} };
  const body = document.getElementById('branding-body');
  const closeBtn = document.getElementById('close-branding');
  closeBtn.onclick = () => { modal.hidden = true; };

  function purify(s) { return window.DOMPurify ? window.DOMPurify.sanitize(s) : String(s).replace(/[<>]/g, ''); }

  function readFile(file) {
    return new Promise((res, rej) => {
      const r = new FileReader();
      r.onload = () => res(r.result);
      r.onerror = () => rej(r.error);
      r.readAsDataURL(file);
    });
  }

  async function downscaleLogo(dataUrl, maxW = 280, maxH = 96) {
    return new Promise(res => {
      const img = new Image();
      img.onload = () => {
        const ratio = Math.min(1, maxW / img.width, maxH / img.height);
        const w = Math.round(img.width * ratio);
        const h = Math.round(img.height * ratio);
        const cv = document.createElement('canvas');
        cv.width = w; cv.height = h;
        const ctx = cv.getContext('2d');
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(img, 0, 0, w, h);
        res(cv.toDataURL('image/png'));
      };
      img.onerror = () => res(dataUrl);
      img.src = dataUrl;
    });
  }

  function render() {
    const p = state.project;
    if (!p) return;
    const b = p.branding = p.branding || {
      devName: '', logoDataUrl: '', primaryColor: '#c4773b',
      contact: { email: '', whatsapp: '', web: '' },
    };
    body.innerHTML = '';

    body.insertAdjacentHTML('beforeend', purify(`
      <p class="muted" style="margin:0 0 16px">Estos datos aparecen en el showroom publicado que entregas al cliente.</p>
    `));

    const fields = [
      { id: 'b-devname', label: 'Nombre del desarrollador / inmobiliaria', val: b.devName,
        ph: 'ACME Developers', set: v => b.devName = v },
      { id: 'b-email', label: 'Email de contacto', val: b.contact.email,
        ph: 'ventas@acme.com', set: v => b.contact.email = v },
      { id: 'b-wa', label: 'WhatsApp (con código país)', val: b.contact.whatsapp,
        ph: '+1809-555-0000', set: v => b.contact.whatsapp = v },
      { id: 'b-web', label: 'Sitio web', val: b.contact.web,
        ph: 'https://acme.com', set: v => b.contact.web = v },
    ];

    fields.forEach(f => {
      const row = document.createElement('div');
      row.className = 'config-row';
      const lbl = document.createElement('label');
      lbl.textContent = f.label;
      const input = document.createElement('input');
      input.id = f.id;
      input.type = 'text';
      input.placeholder = f.ph;
      input.value = f.val || '';
      input.addEventListener('change', () => { f.set(input.value.trim()); save?.(); });
      row.append(lbl, input);
      body.appendChild(row);
    });

    // Color picker row
    const colorRow = document.createElement('div');
    colorRow.className = 'config-row';
    const cl = document.createElement('label');
    cl.textContent = 'Color principal (acentos del showroom)';
    const colorInput = document.createElement('input');
    colorInput.type = 'color';
    colorInput.value = b.primaryColor;
    colorInput.style.width = '60px';
    colorInput.style.height = '40px';
    colorInput.style.padding = '4px';
    colorInput.addEventListener('change', () => { b.primaryColor = colorInput.value; save?.(); });
    colorRow.append(cl, colorInput);
    body.appendChild(colorRow);

    // Logo upload
    const logoRow = document.createElement('div');
    logoRow.className = 'config-row';
    const ll = document.createElement('label');
    ll.textContent = 'Logo (PNG/SVG, se redimensiona a 280×96)';
    logoRow.appendChild(ll);
    const preview = document.createElement('div');
    preview.style.cssText = 'background:#fff;padding:12px;border-radius:8px;margin:8px 0;text-align:center;min-height:60px;display:flex;align-items:center;justify-content:center';
    if (b.logoDataUrl) {
      const img = document.createElement('img');
      img.src = b.logoDataUrl;
      img.style.maxWidth = '100%';
      img.style.maxHeight = '80px';
      preview.appendChild(img);
    } else {
      preview.innerHTML = '<span style="color:#888;font-size:12px">Sin logo</span>';
    }
    logoRow.appendChild(preview);
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = 'image/*';
    fileInput.addEventListener('change', async (e) => {
      const file = e.target.files?.[0];
      if (!file) return;
      const dataUrl = await readFile(file);
      b.logoDataUrl = await downscaleLogo(dataUrl);
      save?.();
      render();
      toast?.('Logo actualizado', 'success');
    });
    logoRow.appendChild(fileInput);
    if (b.logoDataUrl) {
      const removeBtn = document.createElement('button');
      removeBtn.className = 'secondary-btn';
      removeBtn.style.marginLeft = '8px';
      removeBtn.textContent = 'Quitar logo';
      removeBtn.onclick = () => { b.logoDataUrl = ''; save?.(); render(); };
      logoRow.appendChild(removeBtn);
    }
    body.appendChild(logoRow);
  }

  function open() {
    if (!state.project) return toast?.('Abre un proyecto primero', 'error');
    render();
    modal.hidden = false;
  }

  return { open };
}
