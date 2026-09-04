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
- Páginas Amarillas **Argentina** is unreliable (fuzzy-matches the query, e.g. "banfield"→"lonas")
  — prefer Cylex. (In **Spain** it's the opposite: `paginasamarillas.es` is the workhorse and
  `cylex.es` is unusable — see the Spain field-learnings section.)
- Parse with `scripts/botargento-scraping/parse_listings.py`.
- **Not every town has a Cylex slug.** Smaller localities 404 (seen: Ingeniero Budge, Budge, Villa
  Fiorito, Don Orione, Bernal, Ezpeleta). That's fine: **each per-city page returns a ~21-result
  *regional* set** (the cabecera's page already lists businesses from neighbouring towns), so a
  404 town's studios are usually captured via a nearby cabecera page + the **address-based locality
  filter**. So scrape the cabeceras and let the address filter do the locality work; don't depend on
  a slug per town. Heavy overlap across same-zone pages → dedup by URL handles it (≈45–55 unique
  businesses per partido after dedup).
- **The "no results, showing nearby" fallback can jump provinces.** A thin/empty town page (e.g.
  Villa Albertina) returned *Córdoba* studios (Capilla del Monte / Jesús María, area codes
  `0351/0354x/0352x`). The locality + relevance filter must drop these; never trust the raw page.

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

**Practical Maps notes (learned in the field):**
- **Maps `text` output is concise and returns INLINE** — it does *not* exceed the inline cap, so
  it is *not* auto-saved to a `tool-results` file (unlike Cylex markdown). You can't feed inline
  output to a parser. Either curate the businesses into a CSV by hand (the same studios repeat
  across queries, so **cross-check each phone against its repeated occurrences** for accuracy), or
  push the batch big enough to overflow to a file — but that risks timeouts (>12 JS pages). In
  practice Maps is an **inline → manual-curation** step (there is no `parse_maps.py` in the skill).
- **Map-pack block shape** (anchor parsing on the `011 …` phone line, walk up):
  `NAME` / `[No hay opiniones]` / `CATEGORY` (Arquitecto / Estudio de arquitectura / …) /
  `["review snippet"]` / `ADDRESS` / `Abierto|Cerrado` / `· Cierra …` / `011 …` (phone) /
  `Sitio web` / `Indicaciones`.
- **Recurring sponsored ad-noise to filter** (appears under `Patrocinado` at the top of almost
  every query, usually out-of-area): `MCA - Marcos Cabral 826 Alvear`, `FC Housing · Ruta
  Provincial 16`, `CREARQ CONSTRUCCIONES · DFE`, `BD Studio · 0221` (La Plata), `Ravignani 2170`
  (CABA edificio), `CHECA · 1380 Perú` (CABA). Also drop universidades, inmobiliarias, abogados,
  agrimensores, "planos municipales" rows.
- **The `15` mobile can hide on Maps.** The *same* studio often shows a `15-` mobile on Cylex/its
  profile but a non-`15` (landline-looking) number in the Maps map-pack — e.g. Agora `011
  15-5836-6475` (Cylex) vs `011 5836-6475` (Maps); D'Aloia `011 5322-0808` (looks fijo) vs `011
  15-5322-0808` (mobile, in a different query). **The `15`-bearing form is the WhatsApp-capable
  one** — prefer it. Maps is genuinely useful here: it surfaced `15-` mobiles for studios Cylex had
  listed only as a landline.

### 4 — Classify phones (mobile vs landline)
Only **mobiles** can have WhatsApp. Classify each number (AR rules below) and build the
international `wa.me` digits. Use `scripts/botargento-scraping/classify_phones.py`.
- **Alta**: explicit mobile `15` prefix group.
- **Media**: AR `011` number whose subscriber part starts `2/3/6/7`.
- **Drop**: `011` starting `4/5` (landline → no WhatsApp).
- **Dedup the candidate pool by `wa_id`, NOT by phone string.** Two phone *strings* — the `15-`
  form and the non-`15` form, or the same studio from two sources — collapse to the **same
  `wa_id`** after `classify()`. If you only dedup raw phone strings you get duplicate `wa_id`s
  downstream (e.g. *Bojko Arquitectura* came in from Maps and from Cylex → one `wa_id`; the seed
  showed 88 rows vs 87 `yes` until deduped by `wa_id`, merging `source`). Dedup the pool **and** the
  final seed by `wa_id`.
- **A well-classified mobile set validates ~85–90% `yes`** on checknumber (this run: 87/100), so
  this pre-filter is worth doing carefully before paying.

### 5 — Validate WhatsApp via checknumber.ai (primary)
Definitive `yes/no` per number from **checknumber.ai** (bulk checker). Pre-filter landlines in
Step 4 first — don't pay to confirm a fijo. Use
`scripts/botargento-scraping/checknumber_validate.py` (submit → poll → download → emit a
`wa_id,whatsapp` map). Key from env **`CHECKNUMBER_API_KEY`**.

- API: `POST https://api.checknumber.ai/v1/tasks` (multipart `file=@numbers.txt` E.164 one-per-line
  + `task_type="ws"`, header `X-API-Key`) → `task_id`; `POST /gettasks` (form `task_id`) until
  `status="exported"` → download `result_url` (a **.zip** containing `all.csv` with columns
  `number,activated`=yes/no, plus `activated.txt`/`unregistered.txt`).
- **Minimum batch = 500 numbers per job (as of 2026-07-01).** checknumber raised the floor from
  100 to **500** — a sub-500 job is rejected pre-billing with
  `{"error":"invalid_batch_size", ..."only N compliant numbers remain for ws, which is less than the
  minimum 500"}` (dupes/invalids don't count toward the 500). Accumulate ≥500 real mobile candidates
  before validating (or `--pad`, which now wastes far more — avoid).
- **Billing is per 100-block (min 500) → submit the largest EXACT 100-multiple ≤ pool.** A 507-
  or 761-number job bills the next full block (600/800), so round the batch to an exact 100-multiple
  and fill the gap with REAL scraped numbers — a 761-pool should go as 800 with 39 fresh scrapes,
  not be trimmed to 500 (superseded rule) and never padded with dummies (Tasty c2 2026-08-28,
  800 exact). Earlier: TastyLivingSoils 2026-07-03 trimmed 520→500, job `d940r2mp2jvhha3a7ig0`,
  422 yes / 78 no ≈ 84%. A 402 insufficient-balance rejection is PRE-billing (no job, no charge —
  top up and retry the same command).
- **Fill mandatory batch space with REAL numbers, never synthetic fillers:** (1) format-ambiguous
  provincial numbers (e.g. La Plata `0221` displayed without `15` → classify=Desconocida but usually
  mobiles) converted to best-guess mobile E.164 — checknumber resolves them; (2) if still short,
  vertical-relevant landlines as `54`+digits (no `9`) — WhatsApp Business can register a fijo, so
  even those slots return information. **Plan geography to 500 up
  front**: at the architecture yield (~19 mobiles/partido) that's ~26 partidos, and at the factory
  yield (~24% of listings, see the ArtBox 2026-07-01 run) ~2,000+ listings — so pick a vertical/zone
  broad enough, or batch several verticals together, to clear 500. The old MIN_BATCH=100 in
  `checknumber_validate.py` is stale; the API is the source of truth. **Scope-sizing rule of thumb (architecture, GBA):** ~19 unique
  mobiles per *partido*; ~5 partidos ≈ 48; **~9 zona-sur partidos ≈ 100**. Plan the geography to the
  100-batch up front. Richest seams seen: the **Canning–Mariano Castex office cluster** (Ezeiza/E.
  Echeverría border) and the **Quilmes/Lanús** centros.
- **Windows env gotcha:** `CHECKNUMBER_API_KEY` may be set at the *User* level but absent from the
  process env (`$env:CHECKNUMBER_API_KEY` empty). Inject it before running:
  `$env:CHECKNUMBER_API_KEY = [Environment]::GetEnvironmentVariable('CHECKNUMBER_API_KEY','User')`.
- **Reuse prior results for free.** A previous job's `wa_map.csv` can be reused offline — filter out
  any synthetic fillers (`54911900000xx` from a past `--pad`) and look up overlapping `wa_id`s
  instead of re-paying. (Saved re-validating 14 numbers in this run.) Or re-parse a saved archive
  with `--from result.zip`.
- Jobs are fast: a 100-number job went `processing → exported` in ~25 s (≈5 polls).
- Track record: the **2026-06-08 GBA Zona Sur** run validated 100 mobiles in one real batch →
  **87 `yes` / 13 `no`** (no padding). An earlier small set: 4/4 wa.me-Confirmed → `yes`, 4/4
  landlines → `no`, and it resolved 10 wa.me-"Unconfirmed" mobiles (7 yes / 3 no). Strictly more
  decisive than wa.me.

**Legacy fallback (free, zero-cost spot check):** `wa.me/<intl-number>` via `bulk_get`
(`main_content_only: false`); the line before `Open app` is a **profile name** (registered) or a
bare number (inconclusive). Use `scripts/botargento-scraping/check_whatsapp.py` only as a manual
fallback or to harvest profile names for `contact_name` (checknumber gives no name).
- **Parser shape gotcha:** with `main_content_only:false` wa.me returns **full-page markdown**
  where the profile name is an `### <name>` **h3 heading immediately before a `[Open app](…)`
  link** — *not* the bare `Open app` line that `check_whatsapp.py` (and `emit --wa-names`) expect
  (that parser is for the `extraction_type:"text"` shape). On the markdown shape both report
  everything "Unconfirmed". A small markdown-aware extractor (anchor on `[Open app]`, take the
  preceding `### `) recovers the names. Names are usually the business name but sometimes a real
  person (e.g. *Sandra Misiak* for "Studio PLASMA") — handy for `contact_name`. A wa.me name is a
  strong positive but still **not authoritative for the seed — only checknumber `yes` gates it.**

### 6 — Emit the seed-ready recipient CSV
`scripts/botargento-scraping/emit_recipients_csv.py --checknumber <map.csv>` writes the **exact
seeder contract** plus a richer human-review CSV, keeping only `whatsapp=yes` rows. `contact_name`
is blank by default (checknumber returns no name); optionally enrich it with `--wa-names <wa.json>`
from a free wa.me pass.
- **`emit` does not dedup by `wa_id`** — if the merged input still holds the `15`/non-`15`
  collision (or the same studio from two sources), the seed can carry a duplicate `wa_id`
  (harmless to the seeder's `ON CONFLICT … DO NOTHING`, but emit a clean file). Dedup the seed by
  `wa_id` afterwards, **merging `source`** (e.g. `Cylex` + `Google Maps` → `Cylex+Google Maps`).
- **Deliverable layout (workspace convention):** save a run under
  `<project>/<Agency>/run_<Zone>_<Date>/` (e.g. `BotArgento/run_ZonaSur_2026-06-08/`) holding the
  final CSVs (`prospects-<vertical>.csv` + `.review.csv` + an all-candidates audit), the validated
  `wa_map.csv`, the `merged-all.csv` emit input, a one-page `SUMMARY.md`, and a `raw/` subfolder
  with the per-zone scrapes/intermediates. Keep ONE combined seed per campaign (not per-partido)
  unless the campaign is intentionally split.

### Field learnings — AMBA multizona (TastyLivingSoils growshops/viveros, 2026-07-02/03)
- **Cylex CABA is ONE city slug `buenos-aires`** — per-barrio slugs and `capital-federal` 404.
  Pagination is `<categoria>-<n>.html` (vivero→6 pages, plantas→7; most categories single-page).
  The `/s?q=` search endpoint now 404s. CABA addresses need a **postal-code filter** (C1xxx or
  bare 1000–1499 in the address tail, case-insensitive city labels) — city-label matching alone
  drops most rows.
- **In GBA, Cylex has almost no growshops** (per-cabecera growshop/cannabis pages mostly 404;
  its `tienda+de+cannabis` pages bleed holistic/tarot noise → BAD_WORDS). **Google Maps town-by-town
  is the primary source for the grow vertical**; Cylex still adds viveros (mostly landlines).
  Conurbano is celular-first: Maps mobile-rate ~60–76% (Oeste highest) vs CABA ~40%.
- **Maps tokenizes queries** — "growshop", "grow shop" and "tienda de cultivo" return the same set
  (verified with spot checks: 0 new). Don't spend queries on term variants; DO vary the *category*
  (growshop / tienda de cannabis / vivero / centro de jardinería / hidroponía / macetas / semillería
  / "distribuidora … mayorista" / product terms like "sustratos", "tierra fértil").
- **Zone-assignment gotchas:** Maps results bleed across partido borders, and GBA reuses
  CABA-sounding street names (Talcahuano→Banfield, Granaderos→Banfield, Aristóbulo del
  Valle→Bernal, Av. Adolfo Alsina→Lomas). Verify by CP / final address component before assigning
  zone; product queries ("macetas en X", "tierra fértil") zoom way out and drift zones the most.
- **Provincial numbers usually display WITHOUT `15`** (`0221 679-9560`) → classify=Desconocida even
  when they're mobiles. Track them as "a confirmar" and resolve via checknumber as batch filler —
  but see campaign 2 below: on AMBA-fringe architecture they validated at only **12%** (mostly
  disguised landlines), so rank them BELOW Media, at the bottom of the mobile tier, never above.
- **Multi-zone campaign pattern:** per-zone run folders + per-zone parser variants
  (`parse_listings_zona<zona>_grow.py`), `merge_pool.py` per zone then again into a campaign pool;
  a `build_relevamiento.py`-style script joins ALL listings (mobiles + landlines) into one
  client-facing per-zone CSV with a WhatsApp-apt flag — landline rows become the "call them
  instead" deliverable after validation. Working reference: `TastyLivingSoils/` scripts.

### Field learnings — CABA + GBA Norte/Oeste (BotArgento architecture c2, 2026-07-31)
Second architecture campaign (run `BotArgento/run_NorteOesteCABA_2026-07-30/`, scripts
`consolidate_c2.py` / `build_pool_c2.py` / `build_batch_c2.py` / `emit_outputs_c2.py`).
Funnel: 1,240 Cylex + ~250 Maps → 1,218 unique pool → exact-1000 batch → **480 yes**.
- **Cylex CABA is DEEP for architecture**: single `buenos-aires` slug, `arquitecto` = 281
  results / 15 pages, `estudio+de+arquitectura` = 268 / 14 pages (vs most categories
  single-page). The header `(Resultados 1 - 20 de NNN)` gives the total — fetch page 1
  first, then compute the page count. ~20-24 listings/page, heavy overlap between the two
  categories (dedup by URL/phone handles it).
- **All 18 GBA cabecera slugs resolved** (Norte: vicente-lopez, san-isidro, san-fernando,
  tigre, san-martin, san-miguel, malvinas-argentinas, `jose-c.-paz` (with the dot), pilar,
  escobar; Oeste: san-justo, ramos-mejia, moron, hurlingham, ituzaingo, caseros, merlo,
  moreno) — no 404s, unlike the small zona-sur towns.
- **Cylex CP parsing trap**: the address format is `STREET NUM, CP City`. NEVER regex-scan
  the whole address for a CP — street numbers 1800-1899 masquerade as zona-sur postal codes
  (e.g. "Balbastro 1878" drops a CABA row). Take the CP as the token LEADING a comma
  segment, scanning segments right-to-left; tolerate full-form CPs with trailing letters
  (`C1408GTT`) and trailing sub-segments ("…, C1406 CIUDAD DE BUENOS AIRES, XIII"). Ranges:
  C-prefix or 1000-1499 = CABA, 16xx = Norte, 17xx = Oeste, 18xx = Sur. When the CP is
  bogus (Cylex glitches duplicate the street number as CP, e.g. "2908 San Isidro"), fall
  through to town-name matching. CP beats town names: streets named "Matanza"/"Florida"
  fool a town-first matcher.
- **Maps per CABA barrio works** ("estudio de arquitectura en <barrio> caba", 22 barrios
  queried) and is mobile-rich where Cylex lists landlines. Sponsored ad-noise roster grew:
  KLS Arquitectos (Canning = zona sur), Grupo CRBN, Grupo 8.66 (desarrollo inmobiliario),
  ConsorciosPRO, plus the known CREARQ/BD Studio set.
- **Hit rates (n=1000, architecture)**: Alta (15-) **87%** · Media (011 2/3/6/7) **80%** ·
  **fijos 20%** (AR fijos beat Spain's 14% — 490 fijos yielded 99 leads, so a 1000-batch
  padded with real fijos is worth it) · **provincial-without-15 best-guess mobiles only
  12%** — most were disguised landlines; sink them below Media in the batch ranking.
- **Dedup against prior campaigns is free money**: 6 pool wa_ids overlapped campaign 1's
  `wa_map.csv` and were excluded before submitting (never re-pay a validated wa_id).
- **CONTAMINATION INCIDENT (found 2026-08-11, root-caused 2026-08-12)**: the consolidator
  globbed the session `tool-results/mcp-scrapling-bulk_stealthy_fetch-*.txt` dir — which is
  SHARED by every campaign run in the same long-lived session. TastyLivingSoils growshop
  dumps (later purged from the dir) were swept in, passed the CABA CP filter, and **148
  grow/vivero rows reached the validated seed** (127 overlapping a paying client's pool —
  double-messaging risk, plus double-paid validation). Caught only at seeding time; 247
  rows curated out, 233 seeded. Fixes now in `consolidate_c2.py`: (1) **always filter
  parsed pages by their `url` against the run's own search categories**, never trust the
  file list; (2) prefer passing explicit dump paths captured at fetch time over globbing.
  Curation keyword sweeps have their own trap: `plant`-style keywords killed 4 real
  "arquitectura + paisaje" studios — cross-check drops against the raw architecture pages
  (ground truth = which search page the listing came from) before discarding.
- **`classify_phones.py` provincial-15 bug FIXED 2026-07-31**: the old greedy
  `re.match(r"0(\d+)")` swallowed the entire digit string for provincial mobiles written
  with `15` ("0351 15-323-2993" → garbage wa_id). Area code = first token; self-test now
  covers it. If a copy of the old classify() lives elsewhere, re-check it.

### Field learnings — Interior AR, primera vez fuera del AMBA (Tasty c2, 2026-08-28)
Nine zones in one campaign (run folders `TastyLivingSoils/run_*_2026-08-28/`, scripts
`consolidate_tasty2.py` — per-city config dict — / `build_pool_tasty2.py` / `build_batch_tasty2.py`).
Funnel: 824 unique → exact-800 batch → job daarljup2jvtve5thdhg: **493 yes (62%)**.
- **Provincial-without-`15` numbers are NOT the 12% dead weight architecture saw**: in the
  grow vertical they validated **58%** (64% when the business name matched the relevance
  regex, 47% generic). The vertical dominates: celular-first verticals validate provincials
  fine; office verticals don't. Rank by name relevance, not just phone shape.
- Hit by zone: small-province capitals (Neuquén, Salta, San Juan, NEA, Catamarca…) **83%**;
  Bs.As. interior 68%; Santa Fe/Paraná 71%; Rosario 58%; Córdoba 54%; **MdP only 43%**
  (fijo-dependent plaza). AMBA mop-up 80%.
- **Billing insight that beats the "exact 500" rule**: checknumber bills per 100-block with
  a 500 minimum — so the right target is the largest 100-multiple ≤ pool (761 bills as 800
  → fill the 39 with real scrapes, never dummies; invalids don't count toward the minimum
  and valid-looking fakes just burn budget). A 402 insufficient-balance rejection happens
  PRE-billing and creates no job (safe to retry after top-up).
- **Cylex interior coverage is thin and patchy**: Rosario ~120 listings, Córdoba ~180
  (fertilizantes 42!), Bahía Blanca ~80; but Paraná/Mendoza-growshop/Tucumán-growshop
  slugs 404 — Maps is the primary source everywhere outside the big three. `hidroponia`
  404s in every city. City slugs: `cordoba`, `rosario`, `mar-del-plata`,
  `san-miguel-de-tucuman` (not `tucuman`), `bahia-blanca` all resolve.
- **Maps drift is the top noise source in small towns**: a query for a town with no
  growshop zooms out and returns CABA (whole queries lost: Azul, Batán, 9 de Julio,
  Tres Arroyos, Dolores) — check result addresses/area codes, never trust the query.
- **Homonym traps**: kill-list must match the LAST address segment only (street "Córdoba
  3977, Mar del Plata" ≠ city Córdoba); Maps town queries return same-name towns in other
  provinces (Vivero San Lorenzo with 0387=Salta in a Santa Fe query; 03329 San Pedro ads
  in Santa Fe). Area code is the tiebreaker.
- Área codes seen per metro: 0341/03476 Rosario, 0351/0354x Córdoba, 0223 MdP,
  0261/0260 Mendoza/San Rafael, 0381 Tucumán, 0291/02932 Bahía/Punta Alta, 0342 Santa Fe,
  0343 Paraná, 0299/0298 Neuquén/Roca, 0387 Salta, 0264 San Juan, 0266 San Luis,
  0379 Corrientes, 0362 Resistencia, 0385 Sgo. del Estero, 0383 Catamarca, 0388 Jujuy.

### Field learnings — Spain / Barcelona (Arka Systems clinics, 2026-07-22)
First non-AR market. Working reference: `ArkaSystems/` scripts (`parse_listings_barcelona_pa.py`,
`build_pool_barcelona.py`). Full notes also in the project memory `spain-scraping-playbook`.
- **Sources invert vs Argentina.** `paginasamarillas.es` is the structured workhorse:
  `https://www.paginasamarillas.es/search/<que>/all-ma/<provincia>/all-is/<ciudad>/all-ba/all-pu/all-nc/<pagina>`
  (free-text kebab slug for `<que>` works, e.g. `clinica-dental`). ~30 listings/page, total count
  in the header as `(NNN)`; needs `bulk_stealthy_fetch` (plain fetch → 403) and markdown overflows
  to `tool-results` files → script-parse. Phone is **visible as markdown link text right after
  "Ver teléfono"** (`[936300109](…/f/<town>/…)`); ~60% of listings expose it.
  **`cylex.es` is UNUSABLE** — interactive Cloudflare challenge that stealthy_fetch does not pass
  (403 "Performing security verification"); don't burn time on it.
- **PA locality trap:** a "city" search includes advertisers that merely *serve* that city from
  anywhere in Spain ("Presta servicio en BARCELONA" — seen from Cardedeu and even Albacete). The
  **real town is the detail-URL slug `/f/<town>/`** — filter on that, not on the search scope.
- **Google Maps per district** works as in AR (text extraction, inline, manual curation), with two
  quirks: **estética/beauty map-packs show NO phone numbers** (booking-first layout — cover that
  vertical via PA only), and a `<categoria> <distrito>` query can redirect to a single place page
  (Gràcia + "clinica dental" did) — reword the query ("dentista gracia"). Markdown extraction of
  Maps is useless (content collapses to ~2.6k chars of tile URLs) — text only.
- **ES phone classification is trivial** (no `15`/`011` gymnastics): 9 digits; mobile starts `6`
  or `71–74`; landline starts `8`/`9` (Barcelona `93x`); exclude `900/800/902` special numbers.
  `wa_id = 34 + 9 digits` — **no `9` insertion** like AR.
- **Hit rates (n=500, Barcelona clinics):** mobiles **92% yes** (243/263 — even better than AR's
  84–87%), landlines **14% yes** (34/237 — WhatsApp Business on a fijo is real but minority).
  Mobiles carry the batch; landline padding still pays ~1 lead per 7 numbers. Small practices
  (fisioterapia) are mobile-first and validate best; big clinics publish landlines.
- **RGPD framing for ES clients:** public B2B commercial contact data under legitimate interest
  (LOPDGDD art. 19); keep per-row `source`; `opt_in_basis` blank until deliberately set (same
  compliance gate as AR).

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
  `api.whatsapp.com/send`); the profile name (registered) or a bare number (can't tell). Use only
  for spot checks or to harvest `contact_name`. Two output shapes: `extraction_type:"text"` →
  profile name is the line before a bare `Open app`; `main_content_only:false` markdown → profile
  name is an `### ` h3 right before `[Open app](…)`. `check_whatsapp.py` parses the first shape only.

---

## Reference: scrapling MCP tips

- **Fetcher choice:** `stealthy_fetch` / `bulk_stealthy_fetch` (browser, beats protections, runs
  JS) for directories and Google Maps — set `network_idle: true`, and `extraction_type: "text"`
  for Maps. `get` / `bulk_get` (plain HTTP, fast) for `wa.me` (set `main_content_only: false` so
  the profile-name line is included).
- **Big outputs go to a file, not inline.** Large results are written to
  `…/tool-results/mcp-scrapling-*.txt` (JSON `{result:[{status,content,url}, …]}`) and only a
  path is returned. `content` is a list of strings → join with `"\n"`. Parse with Python/jq —
  **don't** Read it line-by-line. **WARNING: that dir is shared by every run in the session
  and files persist across campaigns (until purged) — never glob it by tool-name pattern
  alone.** Record the exact file paths as each fetch returns them, and make the parser
  filter pages by `url` against the run's own search categories (see the campaign-2
  contamination incident) — a bare glob once dragged another campaign's growshops into an
  architecture seed. *Exception:* **Cylex markdown overflows to a file** (7 pages ≈ 72k chars; 12 ≈
  130–155k), but **Google Maps `text` stays under the cap and returns inline** even at 12 queries —
  so Maps must be curated from the inline result, not parsed from a file (see Step 3).
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
