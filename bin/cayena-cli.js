#!/usr/bin/env node
/* CayenaBot CLI — autonomous showroom generator.
 *
 * Drops a floor plan in, gets a complete showroom out. No UI clicking.
 *
 * Usage:
 *   node bin/cayena-cli.js --plan path/to/plan.png \
 *                          --name "Cap Cana Penthouse" \
 *                          --out outputs/cap-cana/ \
 *                          [--realismo]   # generate fal.ai hero renders
 *                          [--captures 6] # number of capture angles
 *
 * Required env vars:
 *   OPENROUTER_KEY   for plan analysis (Gemini Vision)
 * Optional env vars:
 *   FAL_KEY          for Realismo Pro photoreal renders
 *
 * Output structure:
 *   outputs/<name>/rooms.json           extracted room data
 *   outputs/<name>/captures/*.jpg       Three.js views (dollhouse + per-room hero)
 *   outputs/<name>/realismo/*.jpg       fal.ai photoreal versions (if --realismo)
 *   outputs/<name>/showroom.zip         self-contained showroom for hosting
 *
 * The CLI spawns a local server, drives the actual browser app via Puppeteer,
 * and reuses 100% of the existing scene/render/publish modules.
 */

const fs = require('fs');
const path = require('path');
const { spawn, spawnSync } = require('child_process');

/* =================================== arg parsing */
const args = {};
for (let i = 2; i < process.argv.length; i++) {
  const a = process.argv[i];
  if (a.startsWith('--')) {
    const k = a.slice(2);
    const v = process.argv[i + 1];
    if (v && !v.startsWith('--')) { args[k] = v; i++; }
    else args[k] = true;
  }
}
const planPath = args.plan;
const projectName = args.name || path.basename(planPath || 'project', path.extname(planPath || ''));
const outDir = args.out || `outputs/${projectName.replace(/\W+/g, '_')}`;
const captureCount = Number(args.captures || 6);
const wantRealismo = !!args.realismo;
const wantPublish = args.publish !== 'false';

if (!planPath) {
  console.error('Usage: cayena-cli.js --plan <path/to/plan.png> [--name "..."] [--out dir/] [--realismo]');
  process.exit(1);
}
if (!fs.existsSync(planPath)) {
  console.error('Plan file not found:', planPath);
  process.exit(1);
}

const orKey = process.env.OPENROUTER_KEY;
const falKey = process.env.FAL_KEY;
if (!orKey) {
  console.error('OPENROUTER_KEY env var required for plan analysis');
  process.exit(1);
}
if (wantRealismo && !falKey) {
  console.warn('⚠ --realismo requested but FAL_KEY not set — Realismo Pro skipped');
}

const repoRoot = path.resolve(__dirname, '..');
fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(path.join(outDir, 'captures'), { recursive: true });
if (wantRealismo) fs.mkdirSync(path.join(outDir, 'realismo'), { recursive: true });

/* =================================== helpers */
function log(msg) { console.log(`[cayena] ${msg}`); }
function readFileAsDataUrl(p) {
  const ext = path.extname(p).toLowerCase().replace('.', '') || 'png';
  const mime = { png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp' }[ext] || 'image/png';
  const buf = fs.readFileSync(p);
  return `data:${mime};base64,${buf.toString('base64')}`;
}
function dataUrlToBuffer(dataUrl) {
  return Buffer.from(dataUrl.split(',')[1], 'base64');
}

/* =================================== ensure puppeteer */
function ensurePuppeteer() {
  try { require.resolve('puppeteer'); return require('puppeteer'); }
  catch {
    log('Installing puppeteer...');
    spawnSync('npm', ['i', '--no-save', 'puppeteer'], { cwd: repoRoot, stdio: 'inherit' });
    return require('puppeteer');
  }
}

/* =================================== main */
(async () => {
  const puppeteer = ensurePuppeteer();

  // Spawn local static server
  log(`Serving ${repoRoot} on :3030...`);
  const server = spawn('npx', ['--yes', 'serve', '.', '-l', '3030', '--no-clipboard'],
    { cwd: repoRoot, stdio: ['ignore', 'pipe', 'pipe'] });
  server.stdout.on('data', d => { /* quiet */ });
  await new Promise(r => setTimeout(r, 3000));

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox',
        '--use-angle=swiftshader', '--use-gl=angle', '--enable-unsafe-swiftshader',
        '--ignore-certificate-errors'],
      defaultViewport: { width: 1600, height: 1000 },
    });
    const page = await browser.newPage();
    page.on('pageerror', e => console.log('  [pageerror]', e.message));
    page.on('console', m => {
      const t = m.text();
      if (m.type() === 'error' && !t.includes('favicon')) console.log('  [err]', t);
    });

    // Inject session + keys + project skeleton with plan
    const planDataUrl = readFileAsDataUrl(planPath);
    const projId = 'p_cli_' + Date.now().toString(36);
    const unitId = 'u_cli_' + Math.random().toString(36).slice(2, 8);

    await page.evaluateOnNewDocument(({ projId, unitId, projectName, planDataUrl, orKey, falKey }) => {
      const userId = 'JAG';
      localStorage.setItem('cayenabot_session', JSON.stringify({ userId, since: Date.now() }));
      localStorage.setItem('cayenabot_key_openrouter', orKey);
      if (falKey) localStorage.setItem('cayenabot_key_fal', falKey);
      const proj = {
        id: projId, userId, name: projectName,
        createdAt: Date.now(), updatedAt: Date.now(),
        branding: { devName: '', logoDataUrl: '', primaryColor: '#c4773b',
                    contact: { email: '', whatsapp: '', web: '' } },
        units: [{ id: unitId, code: 'A', name: 'Tipo A',
                  planImage: planDataUrl, rooms: [], galleryMeta: [], styleDNA: {} }],
        activeUnitId: unitId,
        chat: [], thumbDataUrl: null,
        published: { lastBundleAt: 0, bundleSize: 0 },
      };
      localStorage.setItem(`cayenabot_proj_${userId}_${projId}`, JSON.stringify(proj));
    }, { projId, unitId, projectName, planDataUrl, orKey, falKey: falKey || '' });

    log('Loading app...');
    await page.goto('http://localhost:3030/', { waitUntil: 'networkidle0', timeout: 30000 });
    await page.waitForSelector('.project-card', { timeout: 15000 });
    await page.evaluate(() => document.querySelector('.project-card').click());
    await page.waitForSelector('#workspace-screen.active');
    await new Promise(r => setTimeout(r, 600));

    // Step 1: analyze plan with Gemini Vision
    log('Analyzing plan with Gemini Vision (~15-30s)...');
    const rooms = await page.evaluate(async () => {
      const { analyzePlan } = await import('./js/plan-analyzer.js');
      const u = window.__cayena.activeUnit(window.__cayena.state.project);
      const out = await analyzePlan(u.planImage);
      u.rooms = out;
      window.__cayena.save();
      return out;
    });
    log(`✓ ${rooms.length} rooms detected`);
    fs.writeFileSync(path.join(outDir, 'rooms.json'), JSON.stringify(rooms, null, 2));

    // Step 2: build 3D
    log('Building Three.js scene...');
    await page.click('.tab[data-tab="tour"]');
    await new Promise(r => setTimeout(r, 300));
    await page.evaluate(() => window.__cayena.modules.tour.build());
    await page.waitForSelector('#tour-canvas-wrap canvas', { timeout: 20000 });
    await new Promise(r => setTimeout(r, 4000));

    // Step 3: capture multiple angles
    log(`Capturing ${captureCount} 3D views...`);
    const cameraShots = [
      { name: 'dollhouse_front',  pos: [13, 11, 14],  look: [0, 1.2, 0] },
      { name: 'dollhouse_side',   pos: [-15, 10, 8],  look: [0, 1.2, 0] },
      { name: 'dollhouse_back',   pos: [-8, 12, -14], look: [0, 1.2, 0] },
      { name: 'dollhouse_corner', pos: [16, 7, 16],   look: [0, 1.4, 0] },
    ];
    // Per-room walk shots based on detected rooms
    rooms.slice(0, captureCount - cameraShots.length).forEach((r) => {
      const cx = (r.bbox.x + r.bbox.width / 2) / 100 * 18 - 9;
      const cz = (r.bbox.y + r.bbox.height / 2) / 100 * 14 - 7;
      let lx = cx, lz = cz - 3;
      const wallsDesc = [r.wall_north, r.wall_south, r.wall_east, r.wall_west].join(' ').toLowerCase();
      // Look toward window
      if (/ventanal|piso-techo/.test(r.wall_north)) lz = cz - 6;
      else if (/ventanal|piso-techo/.test(r.wall_south)) lz = cz + 6;
      else if (/ventanal|piso-techo/.test(r.wall_east)) lx = cx + 6;
      else if (/ventanal|piso-techo/.test(r.wall_west)) lx = cx - 6;
      cameraShots.push({
        name: `walk_${r.code}_${r.name.replace(/\W+/g, '_').slice(0, 16)}`,
        pos: [cx, 1.6, cz], look: [lx, 1.5, lz], walk: true,
      });
    });

    const captures = [];
    for (const s of cameraShots.slice(0, captureCount)) {
      await page.evaluate(({ pos, look, walk }) => {
        const sb = window.__cayena.modules.scene;
        if (walk) sb.setMode('walk'); else sb.setMode('dollhouse');
        const cam = sb.camera;
        cam.position.set(pos[0], pos[1], pos[2]);
        cam.lookAt(look[0], look[1], look[2]);
      }, s);
      await new Promise(r => setTimeout(r, 800));
      const dataUrl = await page.evaluate(() => window.__cayena.modules.scene.capture());
      const fp = path.join(outDir, 'captures', `${s.name}.jpg`);
      fs.writeFileSync(fp, dataUrlToBuffer(dataUrl));
      captures.push({ ...s, file: fp });
      log(`  → captures/${s.name}.jpg`);
    }

    // Step 4: optional Realismo Pro for hero shots
    if (wantRealismo && falKey) {
      log('Running Realismo Pro on top 3 hero shots (~30-90s each)...');
      // Reposition camera back to first hero shot, then call realism()
      const heroShots = cameraShots.slice(4, 7); // walk shots are usually most useful
      for (const s of heroShots) {
        await page.evaluate(({ pos, look }) => {
          const sb = window.__cayena.modules.scene;
          sb.setMode('walk');
          const cam = sb.camera;
          cam.position.set(pos[0], pos[1], pos[2]);
          cam.lookAt(look[0], look[1], look[2]);
        }, s);
        await new Promise(r => setTimeout(r, 800));
        try {
          const result = await page.evaluate(async () => {
            return await window.__cayena.modules.render.realism();
          });
          if (result?.dataUrl) {
            const fp = path.join(outDir, 'realismo', `${s.name}_photoreal.jpg`);
            fs.writeFileSync(fp, dataUrlToBuffer(result.dataUrl));
            log(`  ✓ realismo/${s.name}_photoreal.jpg (${result.label})`);
          } else {
            log(`  ✗ ${s.name}: realismo returned null`);
          }
        } catch (e) { log(`  ✗ ${s.name}: ${e.message}`); }
      }
    }

    // Step 5: publish ZIP
    if (wantPublish) {
      log('Generating showroom ZIP...');
      const zipB64 = await page.evaluate(async () => {
        const { mountShowroomPublish } = await import('./js/showroom-publish.js');
        // Reuse existing module from state (already mounted)
        const pub = window.__cayena.modules.publish;
        // Override the download trigger: capture the blob instead
        const orig = window.URL.createObjectURL;
        let captured = null;
        window.URL.createObjectURL = (b) => { captured = b; return 'blob:cap'; };
        // Don't actually trigger anchor download
        const fakeA = document.createElement('a');
        const origCreate = document.createElement.bind(document);
        const origAppend = document.body.appendChild.bind(document.body);
        document.body.appendChild = (n) => { if (n.tagName === 'A' && n.download) return n; return origAppend(n); };
        await pub.publishZip();
        document.body.appendChild = origAppend;
        window.URL.createObjectURL = orig;
        if (!captured) return null;
        const reader = new FileReader();
        return await new Promise(res => {
          reader.onload = () => res(reader.result);
          reader.readAsDataURL(captured);
        });
      });
      if (zipB64) {
        fs.writeFileSync(path.join(outDir, 'showroom.zip'), Buffer.from(zipB64.split(',')[1], 'base64'));
        log(`  ✓ showroom.zip (${(fs.statSync(path.join(outDir, 'showroom.zip')).size / 1024).toFixed(0)} KB)`);
      } else log('  ✗ ZIP capture failed');
    }

    log('\n✓ Done. Outputs: ' + outDir);
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(e => { console.error(e); process.exit(1); });
