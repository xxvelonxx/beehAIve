/* CayenaBot — config.js
 * API key storage (localStorage), connection tests, embedded DR market data.
 * NO HARDCODED KEYS in source. Users paste keys into settings; UI warns about visibility.
 */

const PROVIDERS = [
  {
    id: 'openrouter',
    label: 'OpenRouter (chat + plan analysis, modelos gratis)',
    placeholder: 'sk-or-v1-...',
    test: testOpenRouter,
    gold: false,
  },
  {
    id: 'fal',
    label: 'fal.ai (renders premium FLUX, $0.04/img) — RECOMENDADO',
    placeholder: 'fal-...',
    test: testFal,
    gold: true,
  },
  {
    id: 'groq',
    label: 'Groq (chat rápido, gratis)',
    placeholder: 'gsk_...',
    test: testGroq,
    gold: false,
  },
  {
    id: 'openai',
    label: 'OpenAI (opcional, pagado)',
    placeholder: 'sk-...',
    test: testOpenAI,
    gold: false,
  },
  {
    id: 'anthropic',
    label: 'Claude (opcional, pagado)',
    placeholder: 'sk-ant-...',
    test: testAnthropic,
    gold: false,
  },
  {
    id: 'serpapi',
    label: 'SerpAPI (búsqueda Google, opcional)',
    placeholder: 'tu-serpapi-key',
    test: testSerpApi,
    gold: false,
  },
  {
    id: 'skybox',
    label: 'Skybox AI / Blockade Labs (panoramas 360° reales)',
    placeholder: 'tu-skybox-key',
    test: null,
    gold: false,
  },
  {
    id: 'huggingface',
    label: 'HuggingFace (vídeo, opcional)',
    placeholder: 'hf_...',
    test: null,
    gold: false,
  },
];

const KEY_PREFIX = 'cayenabot_key_';
export const getKey = (id) => localStorage.getItem(KEY_PREFIX + id) || '';
const setKey = (id, val) => {
  if (val) localStorage.setItem(KEY_PREFIX + id, val.trim());
  else localStorage.removeItem(KEY_PREFIX + id);
};

export function mountConfig({ toast }) {
  const modal = document.getElementById('config-modal');
  const body = document.getElementById('config-body');
  body.innerHTML = '';

  const warning = document.createElement('div');
  warning.className = 'config-warning';
  warning.textContent = '⚠ Las claves se guardan en este navegador (localStorage). Cualquiera con DevTools puede verlas. Solo para uso interno del equipo.';
  body.appendChild(warning);

  PROVIDERS.forEach(p => {
    const row = document.createElement('div');
    row.className = 'config-row' + (p.gold ? ' gold' : '');

    const label = document.createElement('label');
    label.textContent = p.label;
    if (p.gold) label.className = 'gold';

    const inputRow = document.createElement('div');
    inputRow.className = 'row';
    const input = document.createElement('input');
    input.type = 'password';
    input.placeholder = p.placeholder;
    input.value = getKey(p.id);
    input.addEventListener('change', () => setKey(p.id, input.value));
    inputRow.appendChild(input);

    if (p.test) {
      const btn = document.createElement('button');
      btn.className = 'test-btn';
      btn.type = 'button';
      btn.textContent = 'Probar';
      const result = document.createElement('div');
      result.className = 'test-result';
      btn.onclick = async () => {
        setKey(p.id, input.value);
        result.textContent = 'Probando...';
        result.className = 'test-result';
        try {
          const ok = await p.test(input.value.trim());
          result.textContent = ok ? '✓ OK' : '✗ Falló';
          result.className = 'test-result ' + (ok ? 'ok' : 'fail');
        } catch (e) {
          result.textContent = '✗ ' + (e.message || 'error');
          result.className = 'test-result fail';
        }
      };
      inputRow.appendChild(btn);
      row.append(label, inputRow, result);
    } else {
      row.append(label, inputRow);
    }

    body.appendChild(row);
  });

  modal.hidden = false;
}

/* ============ TEST FUNCTIONS ============ */
async function testOpenRouter(key) {
  if (!key) return false;
  const r = await fetch('https://openrouter.ai/api/v1/models', {
    headers: { 'Authorization': 'Bearer ' + key },
  });
  return r.ok;
}
async function testFal(key) {
  if (!key) return false;
  // No public list endpoint; do a tiny health hit
  const r = await fetch('https://queue.fal.run/fal-ai/flux/schnell', {
    method: 'POST',
    headers: { 'Authorization': 'Key ' + key, 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt: 'test', image_size: { width: 256, height: 256 }, num_inference_steps: 1 }),
  });
  return r.status !== 401 && r.status !== 403;
}
async function testGroq(key) {
  if (!key) return false;
  const r = await fetch('https://api.groq.com/openai/v1/models', {
    headers: { 'Authorization': 'Bearer ' + key },
  });
  return r.ok;
}
async function testOpenAI(key) {
  if (!key) return false;
  const r = await fetch('https://api.openai.com/v1/models', {
    headers: { 'Authorization': 'Bearer ' + key },
  });
  return r.ok;
}
async function testAnthropic(key) {
  if (!key) return false;
  // Anthropic doesn't allow CORS from browsers normally — best-effort check
  try {
    const r = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ model: 'claude-haiku-4-5-20251001', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] }),
    });
    return r.status !== 401 && r.status !== 403;
  } catch { return false; }
}
async function testSerpApi(key) {
  if (!key) return false;
  const url = 'https://serpapi.com/search.json?engine=google&q=test&api_key=' + encodeURIComponent(key);
  try {
    const r = await fetch('https://corsproxy.io/?url=' + encodeURIComponent(url));
    if (!r.ok) return false;
    const j = await r.json();
    return !j.error;
  } catch { return false; }
}

/* ============ DR MARKET DATA ============ */
export const DR_MARKET = {
  constructionPricesUSD: {
    'Santo Domingo':   { estandar: [700, 1200],  premium: [1200, 2000], lujo: [2000, 3500] },
    'Punta Cana':      { estandar: [800, 1400],  premium: [1400, 2500], lujo: [2500, 4500] },
    'Cabarete/Sosúa':  { estandar: [750, 1300],  premium: [1300, 2200], lujo: [2200, 4000] },
    'Las Terrenas':    { estandar: [700, 1200],  premium: [1200, 2000], lujo: [2000, 3800] },
    'Santiago':        { estandar: [600, 1000],  premium: [1000, 1800], lujo: [1800, 3000] },
    'Cap Cana':        { estandar: null,         premium: [1500, 2500], lujo: [2500, 5000] },
  },
  salePricesUSD: {
    'Santo Domingo Piantini/Naco': [1800, 3500],
    'Santo Domingo Ensanche Serrallés': [1500, 2800],
    'Punta Cana beachfront': [3000, 6000],
    'Punta Cana inland': [1500, 3000],
    'Cabarete beachfront': [2500, 4500],
    'Sosúa': [1200, 2500],
    'Las Terrenas': [1500, 3500],
    'Cap Cana': [4000, 10000],
    'Jarabacoa': [800, 1800],
    'Santiago centro': [1000, 2000],
  },
  materialsRD: [
    { name: 'Porcelanato italiano', price: 'USD 45-65/m²' },
    { name: 'Mármol travertino', price: 'USD 80-120/m²' },
    { name: 'Deck teca', price: 'USD 90-150/m²' },
    { name: 'Granito negro', price: 'USD 70-100/m²' },
    { name: 'Cuarzo Silestone', price: 'USD 120-200/m²' },
    { name: 'Vidrio templado 10mm', price: 'USD 85-130/m²' },
    { name: 'Cemento gris (funda 42.5kg)', price: 'RD$340-380' },
    { name: 'Varilla 3/8"', price: 'RD$35-45/pie' },
    { name: 'Block 6"', price: 'RD$28-35/u' },
    { name: 'Alambre dulce', price: 'RD$55-65/lb' },
    { name: 'Arena lavada', price: 'RD$1,200-1,600/m³' },
    { name: 'Grava', price: 'RD$1,400-1,800/m³' },
  ],
  regionalPalettes: {
    'Caribe':         'porcelanato italiano, mármol travertino, deck teca, piedra coral, estuco veneciano, concreto expuesto, granito negro, cuarzo Silestone, aluminio anodizado bronce. Mobiliario: ratán, teca, bambú. Vegetación: palmeras, buganvillas, heliconias, frangipani.',
    'Mediterráneo':   'terracota artesanal, mármol Crema Marfil, piedra caliza, azulejo zellige, roble europeo, hierro forjado, estuco cal. Mobiliario: lino, olivo, mimbre. Vegetación: olivos, lavanda, cipreses, jazmín.',
    'Tropical Asia':  'piedra volcánica, teak indonesio, terrazo artesanal, bambú carbonizado, piedra arenisca. Mobiliario: teak macizo, bambú curvado, piedra monolítica. Vegetación: frangipani, lotus, helechos, bambú gigante.',
    'Urbano Moderno': 'concreto pulido, porcelanato gran formato, Dekton, cuarzo Caesarstone, vidrio piso-techo, acero inoxidable. Mobiliario: modular, vidrio, acero, cuero. Vegetación: monstera, fiddle leaf, jardín vertical.',
  },
  regulations: 'Normativa RD: R-001 (sismorresistente), Ley 675 propiedad horizontal, DGII 3% transferencia, retiros mínimos según municipio, zona sísmica II-III. Marcas locales: León Jimenes, Windoor, Corona.',
  airbnbROI: {
    'Santo Domingo': '6-8%',
    'Punta Cana': '10-14%',
    'Cap Cana': '8-12%',
    'Cabarete': '10-15%',
    'Las Terrenas': '9-13%',
  },
};

export const FREE_OPENROUTER_MODELS = [
  'google/gemini-2.5-pro-exp-03-25:free',
  'google/gemini-2.5-flash-preview-05-20:free',
  'qwen/qwen3-235b-a22b:free',
  'deepseek/deepseek-chat-v3-0324:free',
  'meta-llama/llama-3.3-70b-instruct:free',
];

export const BLACKLIST_MODELS = [
  'moonshotai/kimi-vl-a3b-thinking:free',
  'moonshotai/kimi-vl-a3b:free',
];

export const VISION_MODELS = [
  'google/gemini-2.5-flash-preview-05-20:free',
  'qwen/qwen-2.5-vl-72b-instruct:free',
];
