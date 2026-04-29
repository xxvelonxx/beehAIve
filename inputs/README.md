# inputs/

## planos/

Drop floor plan images here (PNG / JPG / WebP). Each filename becomes the
project name in the output.

When you push a new file under `planos/`, GitHub Actions automatically:

1. Sends the image to Gemini Vision → extracts rooms, dimensions, openings
2. Builds the Three.js 3D apartment from the data
3. Captures 6 hero views (4 dollhouse angles + 2 walk-mode interiors)
4. If `FAL_KEY` secret is set → runs Realismo Pro on 3 of them (~$0.12)
5. Generates a complete showroom ZIP
6. Commits everything to `outputs/<plan-name>/` on the same branch

Result available in ~3-5 minutes. No UI, no clicking, no local install.

## Required setup (once)

Repo → Settings → Secrets and variables → Actions → New repository secret:

| Secret           | Required | What it does                                         |
|------------------|----------|------------------------------------------------------|
| `OPENROUTER_KEY` | yes      | Gemini Vision plan analysis (free tier OK)           |
| `FAL_KEY`        | optional | Enables Realismo Pro photoreal renders (~$0.04/img)  |

Get keys at:
- OpenRouter: https://openrouter.ai/keys (free)
- fal.ai:     https://fal.ai/dashboard/keys (~$5 buys 100+ renders)

## Naming tips

Use descriptive filenames — they become folder names in `outputs/`:

```
inputs/planos/cap-cana-penthouse.png        → outputs/cap-cana-penthouse/
inputs/planos/santo-domingo-piantini.jpg    → outputs/santo-domingo-piantini/
```

## Re-running

Already-processed plans are skipped on push. To re-run a specific plan,
go to Actions → "Auto-generate showroom from plano" → Run workflow → fill
in the plan path.

## Local CLI (alternative to GitHub Actions)

If you have OpenRouter/fal.ai keys locally and want to run it on your Mac:

```bash
npm install
OPENROUTER_KEY=sk-or-... FAL_KEY=fal-... \
  node bin/cayena-cli.js --plan inputs/planos/myplan.png --realismo
```

Output lands in `outputs/myplan/` same as the Action would produce.
