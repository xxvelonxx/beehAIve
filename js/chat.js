/* CayenaBot — chat.js
 * Multi-provider AI chat. OpenRouter free models primary, Groq/OpenAI/Claude
 * paid fallback ONLY if user supplied that key.
 * Strict free-model whitelist (R10). No silent escalation to paid.
 */

import { getKey, FREE_OPENROUTER_MODELS, BLACKLIST_MODELS, DR_MARKET } from './config.js';
import { searchWeb } from './search.js';

const SYSTEM_PROMPT = `Eres CayenaBot, asistente AI de PropTech para República Dominicana. Hablas español dominicano profesional. Conoces:
- Precios de construcción USD/m² por zona DR (Santo Domingo, Punta Cana, Cabarete, Las Terrenas, Santiago, Cap Cana).
- Materiales locales (porcelanato, mármol, granito, cuarzo, vidrio, cemento, varilla, block).
- Normativa: R-001, Ley 675, DGII 3%, retiros, zona sísmica.
- ROI Airbnb por zona.
- 4 paletas de materiales regionales (Caribe, Mediterráneo, Tropical Asia, Urbano Moderno).

Capacidades:
- Búsqueda web (auto-detectada por preguntas de precio/locación/normativa).
- Análisis de planos (el usuario sube imagen, otro módulo extrae habitaciones).
- Construcción de tour 3D Three.js desde los datos del plano (otro módulo).
- Para generar UN render de marketing premium, incluye: [RENDER: prompt detallado en inglés con estilo, materiales, iluminación, cámara]
- Para vídeos: [VIDEO: prompt en inglés]

Responde de forma concisa, directa, sin emojis innecesarios. Cita valores reales del mercado DR cuando sea relevante.`;

/* ====================================================== queue */
const queue = [];
let busy = false;
let aborter = null;

/* ====================================================== model attempts */
async function callOpenRouter(model, messages, key, signal) {
  const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {
    method: 'POST',
    signal,
    headers: {
      'Authorization': 'Bearer ' + key,
      'Content-Type': 'application/json',
      'HTTP-Referer': location.href,
      'X-Title': 'CayenaBot',
    },
    body: JSON.stringify({ model, messages, temperature: 0.7, max_tokens: 1500 }),
  });
  if (!r.ok) throw new Error(`OpenRouter ${r.status}`);
  const j = await r.json();
  return j?.choices?.[0]?.message?.content || '';
}

async function callGroq(messages, key, signal) {
  const r = await fetch('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    signal,
    headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'llama-3.3-70b-versatile', messages, temperature: 0.7, max_tokens: 1500 }),
  });
  if (!r.ok) throw new Error(`Groq ${r.status}`);
  const j = await r.json();
  return j?.choices?.[0]?.message?.content || '';
}

async function callOpenAI(messages, key, signal) {
  const r = await fetch('https://api.openai.com/v1/chat/completions', {
    method: 'POST',
    signal,
    headers: { 'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'gpt-4o-mini', messages, temperature: 0.7, max_tokens: 1500 }),
  });
  if (!r.ok) throw new Error(`OpenAI ${r.status}`);
  const j = await r.json();
  return j?.choices?.[0]?.message?.content || '';
}

/* ====================================================== orchestrator */
async function generate(messages, signal, toast) {
  const orKey = getKey('openrouter');
  const groqKey = getKey('groq');
  const oaKey = getKey('openai');

  // Try free OpenRouter models in whitelist order
  if (orKey) {
    for (const model of FREE_OPENROUTER_MODELS) {
      if (BLACKLIST_MODELS.includes(model)) continue;
      try {
        return await callOpenRouter(model, messages, orKey, signal);
      } catch (e) {
        if (e.name === 'AbortError') throw e;
        console.warn(`[chat] ${model} falló:`, e.message);
      }
    }
  }
  // Try Groq if user supplied
  if (groqKey) {
    try { return await callGroq(messages, groqKey, signal); }
    catch (e) { if (e.name === 'AbortError') throw e; console.warn('[chat] Groq falló:', e.message); }
  }
  // Last resort: OpenAI (paid) only if explicit key
  if (oaKey) {
    try { return await callOpenAI(messages, oaKey, signal); }
    catch (e) { if (e.name === 'AbortError') throw e; console.warn('[chat] OpenAI falló:', e.message); }
  }
  throw new Error('Sin API keys configuradas. Abre ⚙ y agrega OpenRouter (gratis).');
}

/* ====================================================== auto web search */
function shouldSearch(text) {
  const s = text.toLowerCase();
  return /\b(busca|precio|costo|costó|valor|cuanto cuesta|cuanto vale|normativa|ley\b|regulación|tasa|airbnb|alquiler|m2|m²|metro cuadrado)\b/.test(s);
}

/* ====================================================== render/video tag detection */
const RENDER_RE = /\[RENDER:\s*([^\]]+)\]/gi;
const VIDEO_RE  = /\[VIDEO:\s*([^\]]+)\]/gi;

/* ====================================================== UI mount */
export function mountChat({ state, save, toast }) {
  const messagesEl = document.getElementById('chat-messages');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-input');
  const stopBtn = document.getElementById('chat-stop');
  const sendBtn = document.getElementById('chat-send');

  const purify = (s) => window.DOMPurify ? window.DOMPurify.sanitize(s) : String(s).replace(/[<>]/g, '');

  function renderHistory() {
    messagesEl.innerHTML = '';
    (state.project?.chat || []).forEach(m => addBubble(m, false));
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addBubble(m, save_ = true) {
    const div = document.createElement('div');
    div.className = 'chat-msg ' + m.role;
    const av = document.createElement('div');
    av.className = 'avatar-sm';
    if (m.role === 'user') {
      av.style.background = state.user?.color || '#5b8def';
      av.textContent = state.user?.initials || 'U';
    } else {
      av.textContent = '🌶';
    }
    const bub = document.createElement('div');
    bub.className = 'bubble';
    const html = formatContent(m.content);
    bub.innerHTML = purify(html);
    div.append(av, bub);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    if (save_) save?.();
    return bub;
  }

  function formatContent(text) {
    // Convert markdown-ish: **bold**, code fences, links
    let s = String(text)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
    s = s.replace(/```([\s\S]*?)```/g, (_, code) => `<pre>${code}</pre>`);
    s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\n/g, '<br>');
    return s;
  }

  async function handleSubmit() {
    const text = input.value.trim();
    if (!text) return;
    input.value = '';

    const userMsg = { role: 'user', content: text, ts: Date.now() };
    state.project.chat = state.project.chat || [];
    state.project.chat.push(userMsg);
    addBubble(userMsg);

    queue.push(text);
    drain(toast);
  }

  async function drain() {
    if (busy) return;
    if (!queue.length) return;
    busy = true;
    sendBtn.disabled = true;
    stopBtn.hidden = false;
    aborter = new AbortController();

    try {
      const text = queue.shift();
      // Web search augmentation
      let context = '';
      if (shouldSearch(text)) {
        try {
          const results = await searchWeb(text, 3);
          if (results?.length) {
            context = '\n\n[Resultados web]\n' + results.map(r => `- ${r.title}: ${r.snippet}`).join('\n');
          }
        } catch (e) { console.warn('search fail', e); }
      }

      // Build messages
      const history = (state.project.chat || []).slice(-12).map(m => ({ role: m.role, content: m.content }));
      const messages = [
        { role: 'system', content: SYSTEM_PROMPT + '\n\n[Datos DR]\n' + JSON.stringify(DR_MARKET, null, 0).slice(0, 2000) + (context ? context : '') },
        ...history,
      ];

      const reply = await generate(messages, aborter.signal, toast);

      const assistantMsg = { role: 'assistant', content: reply, ts: Date.now() };
      state.project.chat.push(assistantMsg);
      const bub = addBubble(assistantMsg);

      // Auto-trigger render tags
      const renderMatches = [...reply.matchAll(RENDER_RE)];
      if (renderMatches.length && state.modules?.render) {
        for (const m of renderMatches.slice(0, 2)) {
          const prompt = m[1].trim();
          state.modules.render.queueRender(prompt).catch(e => console.warn(e));
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') {
        toast?.('Error: ' + e.message, 'error');
        const errMsg = { role: 'assistant', content: '⚠ ' + e.message, ts: Date.now() };
        state.project.chat.push(errMsg);
        addBubble(errMsg);
      }
    } finally {
      busy = false;
      sendBtn.disabled = false;
      stopBtn.hidden = true;
      aborter = null;
      if (queue.length) drain();
    }
  }

  form.onsubmit = (e) => { e.preventDefault(); handleSubmit(); };
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  });
  stopBtn.onclick = () => aborter?.abort();

  renderHistory();
  return { renderHistory };
}
