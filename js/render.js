/* CayenaBot — render.js
 * fal.ai FLUX hero renders ($0.04/img). 3-5 per project, premium quality.
 * Free Gemini-image is a labeled "draft" fallback only — never primary (R1).
 */

import { getKey } from './config.js';

const FAL_BASE = 'https://queue.fal.run';

/* ============ fal.ai queue helpers ============ */
async function falSubmit(endpoint, body, key) {
  const r = await fetch(`${FAL_BASE}/${endpoint}`, {
    method: 'POST',
    headers: { 'Authorization': 'Key ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const t = await r.text().catch(() => '');
    throw new Error(`fal.ai ${r.status}: ${t.slice(0, 200)}`);
  }
  return r.json();
}

async function falPoll(statusUrl, key, signal) {
  for (let i = 0; i < 90; i++) {  // up to ~3 minutes
    if (signal?.aborted) throw new Error('Cancelado');
    const r = await fetch(statusUrl, { headers: { 'Authorization': 'Key ' + key } });
    if (!r.ok) throw new Error('fal poll falló');
    const j = await r.json();
    if (j.status === 'COMPLETED') return j;
    if (j.status === 'FAILED' || j.status === 'CANCELED') throw new Error('fal job ' + j.status);
    await new Promise(res => setTimeout(res, 2000));
  }
  throw new Error('Timeout esperando fal.ai');
}

async function falFetch(resultUrl, key) {
  const r = await fetch(resultUrl, { headers: { 'Authorization': 'Key ' + key } });
  if (!r.ok) throw new Error('fal result falló');
  return r.json();
}

/* ============ image URL → dataURL (for IDB storage) ============ */
async function urlToDataUrl(url) {
  const r = await fetch(url);
  const blob = await r.blob();
  return new Promise((res, rej) => {
    const reader = new FileReader();
    reader.onload = () => res(reader.result);
    reader.onerror = () => rej(reader.error);
    reader.readAsDataURL(blob);
  });
}

/* ============ public render functions ============ */
export async function renderFluxPro(prompt, opts = {}) {
  const key = getKey('fal');
  if (!key) throw new Error('Configura tu fal.ai API key (renders premium $0.04/img)');
  const body = {
    prompt,
    image_size: opts.image_size || { width: 1024, height: 768 },
    num_inference_steps: 28,
    guidance_scale: 3.5,
    output_format: 'jpeg',
    safety_tolerance: '5',
  };
  const submit = await falSubmit('fal-ai/flux-pro/v1.1', body, key);
  const status = await falPoll(submit.status_url, key);
  const result = await falFetch(submit.response_url, key);
  const url = result?.images?.[0]?.url;
  if (!url) throw new Error('Sin imagen en respuesta de fal.ai');
  return await urlToDataUrl(url);
}

export async function renderFluxKontext(prompt, refImageDataUrl) {
  const key = getKey('fal');
  if (!key) throw new Error('Configura tu fal.ai API key');
  const body = {
    prompt,
    image_url: refImageDataUrl,
    guidance_scale: 7.5,
    num_inference_steps: 28,
    strength: 0.85,
    output_format: 'jpeg',
    image_size: { width: 1024, height: 768 },
    safety_tolerance: '5',
  };
  const submit = await falSubmit('fal-ai/flux-pro/kontext', body, key);
  const status = await falPoll(submit.status_url, key);
  const result = await falFetch(submit.response_url, key);
  const url = result?.images?.[0]?.url || result?.image?.url;
  if (!url) throw new Error('Sin imagen en respuesta');
  return await urlToDataUrl(url);
}

export async function renderFluxSchnell(prompt) {
  const key = getKey('fal');
  if (!key) throw new Error('Configura tu fal.ai API key');
  const body = {
    prompt,
    image_size: { width: 1024, height: 768 },
    num_inference_steps: 4,
    output_format: 'jpeg',
  };
  const submit = await falSubmit('fal-ai/flux/schnell', body, key);
  const status = await falPoll(submit.status_url, key);
  const result = await falFetch(submit.response_url, key);
  const url = result?.images?.[0]?.url;
  if (!url) throw new Error('Sin imagen');
  return await urlToDataUrl(url);
}

/* ============ Free draft fallback (Gemini image via OpenRouter) ============ */
export async function renderGeminiDraft(prompt) {
  const key = getKey('openrouter');
  if (!key) throw new Error('Sin OpenRouter key');
  const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    headers: {
      'Authorization': 'Bearer ' + key,
      'Content-Type': 'application/json',
      'HTTP-Referer': location.href,
      'X-Title': 'CayenaBot',
    },
    body: JSON.stringify({
      model: 'google/gemini-2.5-flash-image-preview:free',
      modalities: ['image', 'text'],
      messages: [{ role: 'user', content: prompt }],
    }),
  });
  if (!r.ok) throw new Error('Gemini image ' + r.status);
  const j = await r.json();
  const img = j?.choices?.[0]?.message?.images?.[0]?.image_url?.url;
  if (!img) throw new Error('Sin imagen en respuesta Gemini');
  return img.startsWith('data:') ? img : await urlToDataUrl(img);
}

/* ============ apply Style DNA to a prompt ============ */
function applyStyleDNA(prompt, dna = {}) {
  const parts = [prompt];
  if (dna.architecture) parts.push(dna.architecture.tags);
  if (dna.interior)     parts.push(dna.interior.tags);
  if (dna.decoration)   parts.push(dna.decoration.tags);
  if (dna.materials)    parts.push(dna.materials.tags);
  if (dna.lighting)     parts.push(dna.lighting.tags);
  parts.push('photorealistic, ultra detailed, 8k, architectural digest, professional real estate photography');
  return parts.filter(Boolean).join(', ');
}

/* ============ UI mount ============ */
export function mountRender({ state, gallery, toast }) {
  const heroBtn = document.getElementById('render-hero-btn');
  const captureBtn = document.getElementById('capture-3d-btn');

  async function queueRender(rawPrompt, source = 'chat') {
    const dna = state.project?.styleDNA || {};
    const prompt = applyStyleDNA(rawPrompt, dna);
    toast?.('Generando render con fal.ai FLUX Pro...', 'info');
    let dataUrl, label = 'fal.ai FLUX Pro';
    try {
      dataUrl = await renderFluxPro(prompt);
    } catch (e) {
      console.warn('FLUX Pro falló, intentando Schnell', e);
      try {
        dataUrl = await renderFluxSchnell(prompt);
        label = 'fal.ai FLUX Schnell';
      } catch (e2) {
        console.warn('Schnell falló, intentando Gemini draft', e2);
        try {
          dataUrl = await renderGeminiDraft(prompt);
          label = 'Gemini draft (calidad reducida)';
          toast?.('Usando draft Gemini — agrega fal.ai key para calidad real.', 'info');
        } catch (e3) {
          toast?.('Render falló: ' + e3.message, 'error');
          throw e3;
        }
      }
    }
    await gallery.addImage(dataUrl, { caption: rawPrompt.slice(0, 80), source: label });
    toast?.('Render listo ✓', 'success');
  }

  heroBtn.onclick = async () => {
    const prompt = window.prompt(
      'Prompt para el render hero (en inglés, recomendado):',
      'luxury living room with floor-to-ceiling ocean view, marble floors, Italian leather sofa, golden hour lighting'
    );
    if (!prompt) return;
    heroBtn.disabled = true;
    try { await queueRender(prompt, 'hero'); }
    finally { heroBtn.disabled = false; }
  };

  captureBtn.onclick = async () => {
    const sceneMod = state.modules?.scene;
    if (!sceneMod) return toast?.('Construye el 3D primero', 'error');
    const dataUrl = sceneMod.capture();
    if (!dataUrl) return toast?.('Captura falló', 'error');
    await gallery.addImage(dataUrl, { caption: 'Captura 3D', source: 'three.js' });
    toast?.('Captura agregada a galería', 'success');
  };

  return { queueRender };
}
