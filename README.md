# CayenaBot v4.1

**Showroom-as-a-service para desarrolladores inmobiliarios.** Cliente entrega los planos de su proyecto, nosotros le entregamos un showroom completo: tour 3D interactivo + renders + brochure, listo para publicar.

Inspirado en [Hauzd](https://hauzd.com/es), pero auto-generado desde planos con AI en minutos en vez de semanas con artistas 3D.

## Cómo se usa

1. **Login** (avatar + 6 dígitos)
2. **Nuevo proyecto** → es el desarrollo (un edificio, una comunidad)
3. **Branding 🎨** → logo del cliente, color principal, contacto (email / WhatsApp / web)
4. **Unidades** → cada unidad = un tipo de apartamento (Penthouse, 2-bed, etc.)
   - Sube su plano → "Analizar AI" → Gemini detecta habitaciones
   - "Editar 3D" → Three.js construye la unidad
5. **Tour 3D** → dollhouse + walk + ☀️/🌙 día/noche + 🪑/🏗 muebles ON/OFF
6. **Galería** → captura el 3D, o genera renders premium con fal.ai FLUX ($0.04/img)
7. **Publicar** → genera un ZIP autocontenido con landing multi-unidad + tours + branding
   - El cliente lo sube a Netlify Drop, GitHub Pages, o cualquier hosting estático
   - Funciona offline también (`file://`)
8. **Embed** → `<iframe src="…/embed.html">` para insertar el tour en el sitio web del cliente

## Las 5 reglas de oro

1. **Three.js es el producto.** No imágenes AI pretendiendo ser un tour.
2. **Calidad > cantidad.** 1 render bueno > 100 malos.
3. **Modular siempre.** Archivos separados, < 500 líneas, ES modules, cero duplicación.
4. **Gratis no escala para renders.** fal.ai FLUX cuando importa la calidad.
5. **Si no puedes probarlo, no lo subas.** Cada feature funciona end-to-end antes de commit.

## Correr localmente

```bash
npm start                # → http://localhost:3000
# o directamente
npx serve . -l 3000
```

## API keys (Configuración ⚙)

- **OpenRouter** (`sk-or-v1-…`, gratis) — análisis de planos + chat
- **fal.ai** (`fal-…`, ~$0.04/render) — renders FLUX Pro premium
- Opcional: OpenAI / Claude / Groq / Skybox / HuggingFace / SerpAPI

Las keys quedan **solo en localStorage del navegador**. Cualquiera con DevTools las puede ver — uso interno del equipo, no abrir al público sin un proxy backend.

## Stack

- **Three.js 0.165** — un único version vía importmap
- **OpenRouter** — Gemini 2.5 Flash (vision + chat) — modelos gratis
- **fal.ai FLUX** — renders premium
- **DuckDuckGo** — búsqueda web gratis ilimitada
- **DOMPurify**, **idb-keyval**, **JSZip** — vendored localmente

Sin build step. Sin bundler. ES modules + CDNs vendored.

## Usuarios del equipo

| ID  | Color | Pass    |
|-----|-------|---------|
| ISA | rosa  | 151202  |
| JAG | gold  | 121174  |
| PAM | azul  | 260572  |
| ALV | verde | 221297  |

Cada usuario tiene namespace propio en localStorage (`cayenabot_proj_{userId}_{projId}`).

## Estructura

```
index.html              shell + importmap
css/style.css           dark luxury theme, mobile-first
js/app.js               routing + state + autosave + project migration
js/auth.js              4 usuarios + sesión
js/config.js            keys + DR market data + free-model whitelist
js/units.js             multi-unit CRUD (★ corazón del modelo)
js/branding.js          logo + color + contacto del cliente
js/plan-analyzer.js     plano → JSON via Gemini Vision
js/scene-builder.js     ★ Three.js scene + cameras + day/night + furniture toggle
js/scene-materials.js   PBR materials library
js/scene-rooms.js       wall extrusion + door/window cuts
js/scene-furniture.js   muebles procedurales por tipo de cuarto
js/scene-exterior.js    grass, piscina, palmas
js/tour.js              minimap, mode bar, fly-to, day/night, furniture toggle
js/chat.js              multi-provider con whitelist estricta
js/render.js            fal.ai FLUX queue API
js/gallery.js           grid + lightbox + IndexedDB (per-unit)
js/style-wizard.js      6-step Style DNA per unit
js/export.js            JSON / PDF / HTML gallery
js/showroom-publish.js  ★ ZIP standalone con landing multi-unidad
js/showroom-templates.js   plantillas HTML/CSS/JS del showroom publicado
js/search.js            DuckDuckGo + SerpAPI fallback
vendor/                 Three.js, DOMPurify, idb-keyval, JSZip vendored
samples/v41/            screenshots del flujo end-to-end
```

## Showroom publicado — qué entrega el ZIP

```
cayenabot_showroom_<proyecto>.zip
├── index.html             landing con branding + grid de unidades
├── unit-A.html, unit-B... tour 3D por unidad
├── embed.html             versión iframe-friendly
├── assets/
│   ├── viewer.css         styling del viewer
│   ├── viewer.js          mini-app del tour (subset de tour.js)
│   ├── scene/             scene-builder + materials + rooms + furniture + exterior
│   ├── vendor/three/      Three.js + addons (1.3 MB)
│   ├── data/
│   │   ├── project.json   branding + lista de unidades
│   │   └── {unitId}.json  rooms + styleDNA por unidad
│   └── img/               imágenes de galería + logo
└── README.txt             instrucciones de hosting
```

ZIP típico ≈ 280 KB sin renders, +200-500 KB por render incluido.

## Deep-link URL params del tour

```
?isTour=1            (señaliza modo tour)
&unit=B              (cambiar de unidad)
&room=2              (volar a habitación N)
&mode=walk           (modo walk al cargar)
&night=1             (noche al cargar)
&furniture=0         (sin muebles al cargar)
```

## Capturas

`samples/v41/`:
- `pub_01_landing.png` — landing del showroom publicado
- `pub_02_unit_A_dollhouse.png` — tour de unidad A en dollhouse + minimap
- `pub_03_unit_A_night.png` — modo noche dramatic
- `pub_05_unit_B.png` — diferente unidad, diferente plano
- `v41_01_units_tab.png` — pestaña de gestión interna de unidades
