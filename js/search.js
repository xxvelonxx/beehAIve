/* CayenaBot — search.js
 * DuckDuckGo-first web search (free, unlimited). SerpAPI fallback only if
 * user pasted a SerpAPI key into settings (R7: zero hardcoded keys).
 */

import { getKey } from './config.js';

const PROXY = 'https://corsproxy.io/?url=';

/* ============ DuckDuckGo Instant Answer ============ */
async function ddgInstant(query) {
  const url = `https://api.duckduckgo.com/?q=${encodeURIComponent(query)}&format=json&no_html=1&skip_disambig=1`;
  try {
    const r = await fetch(PROXY + encodeURIComponent(url));
    if (!r.ok) return [];
    const j = await r.json();
    const out = [];
    if (j.AbstractText) out.push({ title: j.Heading || query, snippet: j.AbstractText, url: j.AbstractURL });
    (j.RelatedTopics || []).forEach(t => {
      if (t.Text && t.FirstURL) out.push({ title: t.Text.split(' - ')[0], snippet: t.Text, url: t.FirstURL });
    });
    return out;
  } catch { return []; }
}

/* ============ DuckDuckGo HTML scrape (lite) ============ */
async function ddgHtml(query) {
  const url = `https://html.duckduckgo.com/html/?q=${encodeURIComponent(query)}`;
  try {
    const r = await fetch(PROXY + encodeURIComponent(url));
    if (!r.ok) return [];
    const html = await r.text();
    const out = [];
    // Naïve regex scrape — just enough to feed AI context
    const re = /<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)<\/a>[\s\S]*?<a[^>]+class="result__snippet"[^>]*>([\s\S]*?)<\/a>/g;
    let m;
    while ((m = re.exec(html)) && out.length < 8) {
      const title = m[2].replace(/<[^>]+>/g, '').trim();
      const snippet = m[3].replace(/<[^>]+>/g, '').trim();
      out.push({ title, snippet, url: m[1] });
    }
    return out;
  } catch { return []; }
}

/* ============ SerpAPI (only if user-supplied key) ============ */
async function serpApi(query, key) {
  const url = `https://serpapi.com/search.json?engine=google&q=${encodeURIComponent(query)}&api_key=${encodeURIComponent(key)}&hl=es&gl=do&num=5`;
  try {
    const r = await fetch(PROXY + encodeURIComponent(url));
    if (!r.ok) return [];
    const j = await r.json();
    return (j.organic_results || []).map(x => ({
      title: x.title, snippet: x.snippet, url: x.link,
    }));
  } catch { return []; }
}

/* ============ public ============ */
export async function searchWeb(query, max = 5) {
  // 1) instant answers
  let results = await ddgInstant(query);
  // 2) HTML scrape if instant gave nothing useful
  if (results.length < max) {
    const more = await ddgHtml(query);
    results = results.concat(more);
  }
  // 3) SerpAPI only if user key present
  const sk = getKey('serpapi');
  if (sk && results.length < max) {
    const sr = await serpApi(query, sk);
    results = results.concat(sr);
  }
  return results.slice(0, max);
}
