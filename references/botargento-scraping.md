# botargento-scraping — the lead-sourcing leg (web → validated `wa_id` → outreach)

The inbound platform answers people who message first; **Bot Argento Sales** cold-messages
prospects it already has in `outreach.recipients`. This module is the **front of that funnel**:
it sources prospect WhatsApp numbers from the public web, validates which are real WhatsApp
accounts, and emits the exact CSV that `seed-recipients.mjs` loads into `outreach.recipients`.

- **It only produces a CSV.** It never touches the DB and never writes `automation.*`
  (honors invariant #1). The outbound seeder is what writes `outreach.*`.
- **Engine:** the **scrapling MCP** (`stealthy_fetch`, `bulk_stealthy_fetch`, `get`, `bulk_get`).
- **Parsing/CSV:** Python 3 (on Windows call it `py`, not `python`).
- Scripts live in `automation-platform/scripts/botargento-scraping/`. At deploy time they can
  also sit beside `bot-argento-sales/Sales Automation/scripts/seed-recipients.mjs`.

Load the tools first (schemas are deferred):
`ToolSearch` → `select:mcp__scrapling__stealthy_fetch,mcp__scrapling__bulk_stealthy_fetch,mcp__scrapling__get,mcp__scrapling__bulk_get`

## Workflow (run in order)

### 1 — Scrape directory listings (name + phone + address)
Use a directory that returns structured listings with phones. **Cylex (`cylex.com.ar`) works
well** and exposes per-city category URLs:
`https://www.cylex.com.ar/<ciudad>/<categoria>.html`
(e.g. `/lomas-de-zamora/arquitecto.html`, `/banfield/estudio+de+arquitectura.html`).
- Try both a generic category (`arquitecto`) and a phrase (`estudio+de+arquitectura`).
- Cover **every locality in the target area** — a "partido"/county has many towns (e.g. Lomas de
  Zamora ⊃ Banfield, Temperley, Turdera, Llavallol …).
- Fetch several localities at once with `bulk_stealthy_fetch` (+ `network_idle: true`).
- Páginas Amarillas is unreliable (fuzzy-matches the query, e.g. "banfield"→"lonas") — prefer Cylex.
- Parse with `scripts/botargento-scraping/parse_listings.py`.

### 2 — Consolidate, filter, dedup
- Parse each page into `{name, url, phone, address}`.
- **Filter by locality** (drop neighbouring counties that bleed in) and **by relevance** (drop
  inmobiliarias, hosting, grabación, "consulting" placeholder rows, etc.).
- **Dedup** by company URL / normalized name — and also **by phone** (the same studio shows up
  under name variants across sources).

### 3 — Enrich with Google Maps
Google Maps adds businesses missing from the directory and often **alternate phones**.
`stealthy_fetch` with `extraction_type: "text"` returns the map-pack text (name, category,
address, phone) even in the "limited view":
`https://www.google.com/maps/search/<query+url+encoded>`
Run a few queries (`estudio de arquitectura en <town>`, `arquitecto <town>`); results overlap →
dedup. When the same business has a different number per source, keep the directory number as
primary and the other as an additional phone.

### 4 — Classify phones (mobile vs landline)
Only **mobiles** can have WhatsApp. Classify each number (AR rules below) and build the
international `wa.me` digits. Use `scripts/botargento-scraping/classify_phones.py`.
- **Alta**: explicit mobile `15` prefix group.
- **Media**: AR `011` number whose subscriber part starts `2/3/6/7`.
- **Drop**: `011` starting `4/5` (landline → no WhatsApp).

### 5 — Validate WhatsApp via checknumber.ai (primary)
Definitive `yes/no` per number from **checknumber.ai** (bulk checker). Pre-filter landlines in
Step 4 first — don't pay to confirm a fijo. Use
`scripts/botargento-scraping/checknumber_validate.py` (submit → poll → download → emit a
`wa_id,whatsapp` map). Key from env **`CHECKNUMBER_API_KEY`**.

- API: `POST https://api.checknumber.ai/v1/tasks` (multipart `file=@numbers.txt` E.164 one-per-line
  + `task_type="ws"`, header `X-API-Key`) → `task_id`; `POST /gettasks` (form `task_id`) until
  `status="exported"` → download `result_url` (a **.zip** containing `all.csv` with columns
  `number,activated`=yes/no, plus `activated.txt`/`unregistered.txt`).
- **Minimum batch = 100 numbers per job.** Accumulate ≥100 mobile candidates across
  localities/verticals before validating (or `--pad`, which wastes credits — avoid).
- Validated 2026-06-08 against this session's set: 4/4 wa.me-Confirmed → `yes`, 4/4 landlines →
  `no`, and it resolved the 10 wa.me-"Unconfirmed" mobiles (7 yes / 3 no). It is strictly more
  decisive than wa.me.

**Legacy fallback (free, zero-cost spot check):** `wa.me/<intl-number>` via `bulk_get`
(`main_content_only: false`); the line before `Open app` is a **profile name** (registered) or a
bare number (inconclusive). Use `scripts/botargento-scraping/check_whatsapp.py` only as a manual
fallback or to harvest profile names for `contact_name` (checknumber gives no name).

### 6 — Emit the seed-ready recipient CSV
`scripts/botargento-scraping/emit_recipients_csv.py --checknumber <map.csv>` writes the **exact
seeder contract** plus a richer human-review CSV, keeping only `whatsapp=yes` rows. `contact_name`
is blank by default (checknumber returns no name); optionally enrich it with `--wa-names <wa.json>`
from a free wa.me pass.

## Handoff to outbound (`seed-recipients.mjs` contract)
The seed CSV header is **exactly** (order-independent, but use this order):

```
wa_id,business_name,contact_name,vertical,source,opt_in_basis
```

- `wa_id` — validated E.164 digits, no symbols (e.g. `5491122768374`). The seeder strips
  non-digits anyway, but emit clean.
- `business_name` — the studio/company name.
- `contact_name` — blank by default (checknumber gives no name); optionally the **WhatsApp profile
  name** from a wa.me enrichment pass (`--wa-names`).
- `vertical` — e.g. `architecture` (matches the campaign vertical).
- `source` — the directory/directories (`Cylex`, `Google Maps`, `Cylex+Google Maps`). Always
  populated (per the standing "Source column" preference).
- `opt_in_basis` — **left blank on purpose** (see compliance below).

Then:
```
node "C:\Desarollo\jperez\bot-argento-sales\Sales Automation\scripts\seed-recipients.mjs" \
     --campaign <id> prospects-<vertical>.csv > seed.sql
ssh vps 'docker exec -i n8n-ventas-postgres psql -U n8n -d n8n' < seed.sql
```
`seed-recipients.mjs` upserts into `outreach.recipients` (`ON CONFLICT (campaign_id, wa_id) DO
NOTHING`). Reply conversations then flow through the shared inbound engine into
`automation.lead_log` / `session_memory`. See `references/outbound-sales.md`.

## Compliance — why `opt_in_basis` is blank by design
Per `outbound-sales.md`, cold-blasting tanks the WABA quality rating → restriction/ban, and
`opt_in_basis` is **required per recipient** (the seeder refuses rows without it). A scraped
public-directory listing is a **thin** basis. So this module deliberately leaves `opt_in_basis`
empty, forcing a deliberate, defensible value per batch before any send. Discipline:
1. Send only **checknumber.ai `yes`** numbers — definitive presence means far fewer failed sends,
   which directly protects the quality rating.
2. Feed the **ramped** runner (30–50/day, `daily_cap` default 40) — never a bulk blast.
3. Suppression is absolute; one block+report hurts more than ten ignores.
4. Validate **one vertical first** (architecture / Plec as proof) before cloning.

---

## Reference: AR phone classification & wa.me validation

### Number anatomy
- Country code `54`. Mobiles add a `9` after the country code in international/WhatsApp format:
  `+54 9 <area> <subscriber>`.
- Buenos Aires metro area code is `11` (written locally `011`). Local mobile dialing uses a `15`
  prefix group: `011 15-XXXX-XXXX`.
- Landlines in `011` typically start the 8-digit subscriber with `4` or `5`; mobile subscriber
  parts very commonly start `2`, `3`, `6`, `7`.

### Confidence heuristic
| Signal | Confidence | WhatsApp? |
|---|---|---|
| Standalone `15` group (`011 15-…`) | Alta | Yes (mobile) |
| `011`, subscriber starts `2/3/6/7` | Media | Probable mobile |
| `011`, subscriber starts `4/5` | — | No (landline) |
| Provincial `0<area>` without `15` | Desconocida | Can't tell from format |

### Building the wa.me number
Buenos Aires mobile: `549` + `11` + `<8-digit subscriber>` → `011 15-5383-6814` →
`5491153836814` → `https://wa.me/5491153836814`. Provincial mobile: `549` + `<area>` +
`<subscriber>` (drop the leading `0` and the `15` group).

### Two bugs to avoid (both hit during the first run)
1. **`15` false positive**: don't test `'15' in phone_string` — `5152` contains `15`. Tokenize on
   spaces/dashes and check `'15' in tokens`.
2. **Lost area code**: `"011"` already contains the area `11`; stripping the first 3 chars removes
   `0`+`11`. Rebuild as `'549' + '11' + subscriber`, not `'5491' + subscriber`.

### Validation backends
- **Primary — checknumber.ai** (paid, definitive yes/no, min batch 100). See Step 5 for the API.
  `CHECKNUMBER_API_KEY` lives in the per-tenant/handoff env, never committed.
- **Fallback — wa.me** (free, inconclusive): `GET https://wa.me/<intl>` (redirects to
  `api.whatsapp.com/send`); the line before `Open app` is the profile name (registered) or the
  bare number (can't tell). Use only for spot checks or to harvest `contact_name`.

---

## Reference: scrapling MCP tips

- **Fetcher choice:** `stealthy_fetch` / `bulk_stealthy_fetch` (browser, beats protections, runs
  JS) for directories and Google Maps — set `network_idle: true`, and `extraction_type: "text"`
  for Maps. `get` / `bulk_get` (plain HTTP, fast) for `wa.me` (set `main_content_only: false` so
  the profile-name line is included).
- **Big outputs go to a file, not inline.** Large results are written to
  `…/tool-results/mcp-scrapling-*.txt` (JSON `{result:[{status,content,url}, …]}`) and only a
  path is returned. `content` is a list of strings → join with `"\n"`. Parse with Python/jq —
  **don't** Read it line-by-line. Several batches accumulate as separate files — glob them when
  consolidating.
- **Batching:** `bulk_stealthy_fetch` can time out ("No pages finished … within 60s") or overflow.
  Keep batches ≲12 URLs; fall back to `bulk_get` (non-JS) or smaller batches.
- **Windows:** call Python as `py`; console mojibake (`Tomás`→`Tom�s`) is only console encoding —
  write CSVs with `encoding="utf-8-sig"` and accents are correct. A CSV open in Excel raises
  `PermissionError` → write `*_v2.csv`. Pipe UTF-8 with
  `py -c "import sys;sys.stdout.reconfigure(encoding='utf-8');..."`.
- **Cylex query patterns:** per-city category `…/<ciudad>/<categoria>.html`; search
  `…/s?q=<query>&p=<page>` (the `&l=` location param does *not* constrain to a city — use per-city
  URLs). Each listing in the markdown is a company link
  `[Name](https://www.cylex.com.ar/<city>/<slug>-<id>.html)` followed by an open/closed line, an
  address line (has a comma), and a phone line.
