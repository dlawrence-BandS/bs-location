# B&S Location Performance Dashboard

GA4 location performance by TV region, region, and city — built for working with TV/media buying agencies. Static single-file dashboard, same stack as the other dashboards (BigQuery + GIS OAuth, no embedded keys).

## Setup (one-off)

1. **Backfill BigQuery** (from April 2024):
   ```
   py backfill_geo.py
   ```
   Creates dataset `geo_dashboard` (europe-west2) with `tv_region_map`, `geo_daily`, `geo_channel_daily`. Finds your service account key automatically. Re-run with `--refresh` to top up the last 4 days, or `--map-only` to just rebuild the TV region mapping.

2. **Scheduled query**: In BigQuery console → Scheduled queries → create from `daily_refresh.sql`. Daily, 09:00 UTC, location europe-west2 (same pattern as the brand dashboard).

3. **OAuth client ID**: In `index.html`, replace `PASTE_OAUTH_CLIENT_ID_HERE...` with the client ID from the Brand Performance dashboard (CONFIG block, near the top of the script). Add the new GitHub Pages URL to the OAuth client's authorised JavaScript origins.

4. **Push to GitHub Pages** as usual (suggested repo: `bs-location`).

## Things to check / edit

- **STORES** array in index.html — 7 stores seeded, marked EDIT ME. Verify names and coordinates, add the rest.
- **TV household figures** in the TV_REGIONS array — reasonable BARB-based estimates, editable. Agencies may have exact universes; swap them in.
- **City → TV region mapping** — 209 cities covered in `backfill_geo.py` (TV_REGION_MAP). Unmapped UK traffic lands in "UK - Other". Add cities there and re-run `py backfill_geo.py --map-only` then `--refresh`.

## Agency access

Two options:
- Give agency contacts Google accounts **BigQuery Data Viewer** on the project — they can then use the live dashboard directly.
- Or export CSVs from any tab and send those.

Campaign flights are stored in the browser (localStorage) — use Export/Import JSON on the Campaign Impact tab to share flight definitions between people.

## Tabs

- **Overview** — UK KPIs, TV region league with revenue-per-1k-households index, revenue share, top cities
- **Trends** — any metric, daily/weekly/monthly, by TV region or nation, YoY/PoP overlay, campaign flights shaded ON AIR
- **TV Regions** — metric bars, per-1k-household index vs UK=100, full metrics table
- **Cities** — searchable/sortable table (top 400), gainers/decliners vs comparison
- **Map** — Leaflet bubble map, sized by metric, coloured by TV region, optional store markers
- **Channel Mix** — weekly stacked channels per region, plus the TV halo view (Direct + Organic Search, indexed)
- **Campaign Impact** — define flights (dates, test/control regions), run test-vs-control uplift analysis with baseline indexing, carryover, and estimated incremental volume

Ask AI drawer works the same as the other dashboards — Anthropic key in localStorage, claude-haiku.
