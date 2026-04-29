# CayenaBot v4

AI PropTech para República Dominicana — tours 3D interactivos, renders premium, chat con datos del mercado DR.

## Las 5 reglas de oro

1. **Three.js es el producto.** No imágenes AI pretendiendo ser un tour.
2. **Calidad > cantidad.** 1 render bueno > 100 malos. 5 features perfectas > 20 rotas.
3. **Modular siempre.** Archivos separados, < 500 líneas, ES modules, cero duplicación.
4. **Gratis no escala para renders.** Usa fal.ai FLUX ($0.04/img) cuando importa la calidad.
5. **Si no puedes probarlo, no lo subas.** Cada feature funciona end-to-end antes de commit.

## Correr localmente

```bash
npm start
# o directamente
npx serve . -l 3000
```

Abre http://localhost:3000.

## Setup de keys

1. Click ⚙ en proyectos
2. Pega tu **OpenRouter** key (gratis — sk-or-v1-...) → habilita chat + análisis de planos
3. Pega tu **fal.ai** key (~$0.04 por render premium — fal-...) → habilita renders FLUX Pro

Las keys se guardan **solo en localStorage de tu navegador**. Cualquiera con DevTools puede verlas — uso interno del equipo.

## Flujo

1. Login (avatar + 6 dígitos)
2. Nuevo proyecto
3. Pestaña **Plano** → sube imagen → "Analizar plano con AI" (Gemini Vision)
4. "Construir 3D →" → pestaña **Tour 3D**
5. Cambia entre 🏠 Dollhouse y 🚶 Walk (WASD + mouse, click 🚶 botón gold)
6. Click una habitación en el minimap para volar allá
7. **Galería** → 📸 captura el 3D, ✨ genera renders fal.ai
8. **Chat** → pregunta sobre precios DR, materiales, normativa
9. **Exportar** → JSON, PDF brochure, galería HTML, plataforma standalone

## Deploy

```bash
git push
```

Render.com sirve automáticamente desde la rama (`render.yaml` + `_redirects` listos).

## Stack

- **Three.js 0.165** (importmap, una sola versión)
- **OpenRouter** (Gemini 2.5 Flash vision para planos, modelos gratis para chat)
- **fal.ai FLUX** Pro / Schnell (renders premium)
- **DuckDuckGo** (búsqueda web gratis ilimitada)
- **DOMPurify** (sanitización XSS)
- **idb-keyval** (imágenes en IndexedDB, no localStorage)

Sin build step. Sin bundler. ES modules + CDNs.

## Usuarios

| ID | Color | Pass |
|----|-------|------|
| ISA | rosa  | 151202 |
| JAG | gold  | 121174 |
| PAM | blue  | 260572 |
| ALV | green | 221297 |

Cada usuario tiene su propio espacio de proyectos (namespacing en localStorage).

## Estructura

```
index.html              shell + importmap
css/style.css           dark luxury theme, mobile-first
js/app.js               routing + state + autosave
js/auth.js              4 usuarios + sesión
js/config.js            keys + DR market data + free-model whitelist
js/plan-analyzer.js     plano → JSON via Gemini Vision
js/scene-builder.js     ★ Three.js scene + cameras
js/scene-materials.js   PBR materials library
js/scene-rooms.js       wall extrusion + door/window cuts
js/scene-furniture.js   muebles procedurales por tipo de cuarto
js/scene-exterior.js    grass, piscina, palmas
js/tour.js              minimap, mode bar, fly-to
js/chat.js              multi-provider con whitelist estricta
js/render.js            fal.ai FLUX queue API
js/gallery.js           grid + lightbox + IndexedDB
js/style-wizard.js      6-step Style DNA
js/export.js            JSON / PDF / HTML / standalone
js/search.js            DuckDuckGo + SerpAPI fallback
package.json · render.yaml · _redirects
```
