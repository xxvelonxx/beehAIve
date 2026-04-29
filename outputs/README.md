# outputs/

Auto-generated showrooms land here. **Do not edit manually** — files are
overwritten on each Action run for the same plan name.

## Structure

```
outputs/<plan-name>/
├── rooms.json              extracted by Gemini Vision
├── captures/               6 Three.js views (dollhouse + walk hero)
│   ├── dollhouse_front.jpg
│   ├── dollhouse_side.jpg
│   ├── dollhouse_back.jpg
│   ├── dollhouse_corner.jpg
│   └── walk_<room>_*.jpg
├── realismo/               (only if FAL_KEY secret was set)
│   └── walk_<room>_*_photoreal.jpg
└── showroom.zip            self-contained showroom ready to host
```

## What to do with these

- **Send `showroom.zip` to your client.** They drop it on Netlify Drop
  (or any static host), share the URL with prospects.
- **`captures/` and `realismo/`** are the marketing images — drop into
  brochures, listings, social.
- **`rooms.json`** is the structured data you can re-import into the
  CayenaBot editor for further tuning.
