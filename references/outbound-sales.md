# Outbound sales engine (Bot Argento Sales)

The inbound platform answers customers who message first. **Bot Argento Sales is the mirror image:
outbound first-contact** — it cold-messages a list of prospects, and when they reply, the existing
inbound engine takes over. Built first as **Jonatan's own client-acquisition tool** (Phase A), and
designed to be **sold to clients as an "outbound campaigns" add-on** (Phase B).

- **Workspace:** `C:\Desarollo\jperez\bot-argento-sales\Sales Automation\` (mirrors the Plec layout).
- **Tenant:** its own n8n + Postgres + a **dedicated sales WABA**. Subdomain `ventas.botargento.com.ar`.
- **Reference instance for outbound** the way Plec is the reference instance for inbound.

## Which half of Meta's rulebook

The whole inbound platform operates only inside the **24h customer-initiated service window** (free
text). Outbound flips this:

- **First contact must be a pre-approved template** (Marketing category) — and cold-blasting tanks the
  WABA quality rating → restriction/ban.
- **The reply opens the 24h window** → the real pitch runs **free** in the existing router + a wizard.

So the design rule is: **the template's only job is to earn a reply.** Don't pitch in the template;
pitch in-window. This aligns compliance and cost (Marketing templates cost per message in AR;
in-window replies are free).

## What's reused vs net-new

| Reused as-is (copied from `whatsapp-automation-claude`) | Net-new (this engine) |
|---|---|
| `v2-send-whatsapp-message.json` | `outreach.*` schema (campaigns / recipients / suppression) |
| `v2-persist-session-and-logs.json` (already dual-mode template handoff) | `v2-campaign-runner.json` (the outbound workflow) |
| `v2-error-handler.json` | `v2-ventas-wizard.json` (the pitch; self-sales-specific) |
| router skeleton (verify/normalize/dedup/lock/session) | router opt-out branch → `outreach.suppression` |

No shared-engine edits: the campaign-runner sends templates via its **own** HTTP node, so the shared
sender stays generic.

## `outreach.*` schema (honors invariant #1)

A **new schema**, not new tables inside `automation.*` — so the frozen `automation.*` invariant holds.
Reply conversations still land in `automation.lead_log` / `session_memory` via the shared engine.

- `outreach.campaigns` — `name, vertical, template_name, template_lang, daily_cap, send_hour_start/end, status (draft|active|paused|done)`.
- `outreach.recipients` — `campaign_id, wa_id, business_name, contact_name, vertical, source, opt_in_basis, status (pending|sent|delivered|read|replied|failed|opted_out), message_id, last_send_at, touch_count`. `UNIQUE(campaign_id, wa_id)`.
- `outreach.suppression` — `wa_id PK, reason, campaign_id` — absolute do-not-contact, checked before every send.

DDL appended after the `automation.*` block in
`bot-argento-sales/Sales Automation/n8n/compose/postgres-setup.sql`.

## Campaign runner (`v2-campaign-runner.json`)

Schedule (30 min) → `Read Pending Batch` (Postgres gating SQL) → `Build Payloads` (Code:
`_src/campaign-runner.js` → Meta template payload) → `Loop Over Items` → `Wait` (randomized 20–60s) →
`Send Template` (HTTP → Meta, auth via `$env.META_ACCESS_TOKEN`) → `Mark Sent` (Postgres).

Gating (in SQL): active campaign, pending recipient, not suppressed, inside AR-local send window,
under `daily_cap`, small batch per tick. **Kill switch:** `outreach.campaigns.status='paused'`.

## Ventas wizard (`v2-ventas-wizard.json`, `_src/ventas.js`)

`Trigger → Read Recipient (Postgres lookup by wa_id) → Run Wizard Step`. Same `finalize()` contract
as inbound wizards. Steps: `intro` (greet + 1-line pitch + social proof) → `rubro` (skipped if the
campaign vertical is known) → `hoy` (how they handle WhatsApp today) → showcase handoff
(`intent='ventas_lead'`, `handoff_target='ventas'` → `VENTAS_WHATSAPP_NUMBER` = Jonatan, template
mode). Personalization via the `Read Recipient` node is **TTL-proof** (doesn't depend on
`session_memory`, which expires at 30 min).

**UX revision (2026-06-08):** the `intro` re-ask is **skipped** for campaign prospects (a
`Read Recipient` row exists) or affirmative entries — tapping the cold template's `Ver ejemplo`
goes straight to `hoy` instead of re-asking "¿te muestro?". The old `demo` Sí/Después step is gone:
after `hoy`, `buildShowcaseHandoff` sends an **in-window `cta_url` interactive message** (free — no
template billing) showing Jonatan's live demo bots (wa.me links) + an **Agendar Demo** URL button,
and fires the handoff **immediately** (auto-alert: a URL button can't call back to the bot, so
reaching the showcase = the qualified-lead trigger). To carry an arbitrary Meta payload to the
prospect, the wizard's `finalize()` emits `wa_message` and the **shared sender** got a generic
passthrough branch (`$json.wa_message` sent verbatim, else the buttons/text ternary) — backwards
compatible, worth upstreaming. cta_url URL buttons may point at a calendar (unlike *template* URL
buttons, which forbid wa.me — subcode 2388081).

Router (`_src/router-determine-route.js`): no numbered menu — everything → ventas wizard, except
unambiguous opt-out tokens (`PARA`/`BAJA`/`STOP`/`cancelar`/`no me interesa`/...) → `optout` → router
writes `outreach.suppression` + confirms. (Bare "no" is intentionally NOT an opt-out token — it's a
valid wizard answer.)

**Quick-reply template buttons (2026-06-08):** if the cold template uses quick-reply buttons (e.g.
`Ver ejemplo` / `No me interesa`) instead of a "Respondé SÍ/PARA" text CTA, taps arrive as
`message.type === 'button'` (`button.text`/`button.payload`) — a DIFFERENT webhook shape from the
`interactive`→`button_reply` that the wizard's own buttons emit. The router's **Normalize Event**
node (templated inside `scripts/wizards/build.mjs`, not in `_src/`) must have the `type:'button'`
branch that extracts `button.text` into `text_body`; without it taps fall through to `unsupported`
and the whole reply flow dies. Extracting the visible **text** (not just payload) is what lets the
`No me interesa` button match the `no me interesa` opt-out token. This makes the button label double
as the opt-out, so the template footer can drop "Respondé PARA…".

## Launching a campaign (the sell flow)

Step-by-step runbook: `bot-argento-sales/Sales Automation/docs/ventas/campaign-runbook.md`. The data
model in one line: **one `campaigns` row per campaign + one `recipients` row per prospect** (the
recipient row is a `pending→sent→…→replied` state machine, mutated in place — never one row per
message). Flow: build CSV (`wa_id,business_name,contact_name,vertical,source,opt_in_basis`) →
`seed-recipients.mjs --campaign <id>` (refuses rows w/o `opt_in_basis`) → `INSERT outreach.campaigns`
(create `paused`) → `status='active'` → runner sends under cap/window → watch `quality_rating`, ramp
30–50/day → `status='paused'` kill switch.

## Scripts

`build.mjs` (targets `ventas` / `campaign-runner` / `router`), `import-n8n.mjs`,
`set-error-workflow.mjs`, `patch-wizard-live.mjs` (manifest-based, no hardcoded ids), and
`seed-recipients.mjs` (CSV → SQL emitter; **refuses rows without `opt_in_basis`**). No
`patch-persister-template.mjs` — the copied persister is already template-capable.

## Recipient sourcing (botargento-scraping)

Where the recipients come from. The **botargento-scraping** module (see
`references/botargento-scraping.md`) is the front of this funnel: via the scrapling MCP it scrapes
business directories (Cylex), enriches with Google Maps, classifies AR phones (drops landlines —
only mobiles can have WhatsApp), and **validates presence via checknumber.ai** (definitive
`yes/no`; min batch 100; key in env `CHECKNUMBER_API_KEY`). It emits the exact seeder CSV
`wa_id,business_name,contact_name,vertical,source,opt_in_basis`, keeping only `whatsapp=yes` rows,
with **`opt_in_basis` left blank on purpose** — so `seed-recipients.mjs` forces a deliberate,
defensible basis per batch before anything sends. (`contact_name` is blank unless enriched by an
optional free wa.me name-pass — checknumber returns no name.) Discipline: send only validated
`yes` numbers (fewer failed sends → protects the quality rating) and feed the ramped runner, never
a bulk blast. The module only writes a CSV — never `automation.*` (invariant #1 holds).

## Compliance — the rules that keep the WABA alive

(Full doc: `bot-argento-sales/Sales Automation/docs/ventas/outreach-compliance.md`.)

1. Dedicated sales WABA — never a client's number.
2. Ramp **30–50/day** for 1–2 weeks regardless of Meta tier (`daily_cap` default 40).
3. Suppression is absolute; one block+report hurts more than ten ignores.
4. `opt_in_basis` required per recipient (defensible source; the seeder enforces it).
5. Business hours only; watch quality rating, pause on yellow.
6. **Validate one vertical first** (architecture — Plec as proof) before cloning to real-estate /
   services. Run them as separate campaigns under one WABA, ramped one at a time.

## Phase B — onboard the outbound add-on onto an existing tenant

Because `outreach.*` is per-tenant (each tenant has its own Postgres) and the runner is a portable
module, selling outbound to a client who already has the inbound bot is:

1. Apply the `outreach.*` block to the client's Postgres.
2. Import `v2-campaign-runner.json` into the client's n8n; wire the Postgres credential + the HTTP
   node's Meta auth; add the router opt-out branch (or import the sales router if they don't have one).
3. Write the client's **own** pitch wizard (promo / winback / reactivation — not Jonatan's `ventas.js`).
4. Create the client's Marketing template, seed recipients with `opt_in_basis`, ramp.

So `bot-argento-sales` is the worked reference; a client deployment copies the runner + schema and
swaps the pitch wizard + template + brand env vars.

## Status

See `references/tenants-status.md` → **Bot Argento Sales**. As of 2026-06-04: **scaffolded locally,
not yet on the VPS, no WABA**.
