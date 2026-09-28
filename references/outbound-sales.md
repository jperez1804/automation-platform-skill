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
| | `v2-quality-poll.json` (Graph→`outreach.quality_log`, every 6 h) |
| | `v2-outreach-reconcile.json` (funnel state from `lead_log`+`suppression`, every 5 min) |
| | read-only dashboard `campaignsTab` (see `dashboard.md`) |

The shared sender stays generic — but gained one **backwards-compatible** branch: a `wa_message`
passthrough (send a full Meta payload verbatim if present, else the buttons/text ternary), so the
ventas wizard can emit the in-window `cta_url` showcase. Worth upstreaming.

**Live state (verified 2026-07-30):** infra fully operational — real sales number
(`+54 9 11 2558-9239`), templates approved, dashboard live (`dashboard.ventas.botargento.com.ar`),
all 8 workflows ACTIVE, quality GREEN. The **first real campaign** (`arquitectura-zonasur-2026-06`,
87 architecture studios, 15/day) ran 2026-06-11 → 2026-06-19 and **finished: 12 replied (13.8%),
4 opted out, 71 no-reply**. A 1-recipient demo campaign (2026-06-21) converted **Tasty** into a live
Phase-B tenant. Since then the runner is active but **starved (0 pending recipients)** — Phase A did
its job and effort moved to Phase-B client tenants (Tasty, ArtBox, Arka). Inbound still works
organically (leads through 2026-07-25).
**Note:** the campaign-runner must be **activated** (its schedule) for hands-off daily sending — manual
`Execute workflow` only fires once.

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

**Flow v3 (2026-09, current).** Steps: `intro` → `rubro` (**always asked** — the campaign vertical
no longer skips it) → `hoy` → `interes` (pain: "2 a 3 horas por día contestando lo mismo" + "un lead
que espera más de 5 minutos se enfría", single «Veámoslo» button) → `oferta` (showcase + promo, reply
button) → `handoff` (confirmation + web cta_url). **Handoff + email alert fire on the offer tap**,
not when the showcase is shown. Plus the hardening defaults: `dormant` anti-loop guard,
`guided_ventas_precio` (price answer + handoff) and `guided_ventas_consulta` (free-text handoff), and
burst grouping. Meta button titles are capped at **20 chars** ("Estudio Arquitectura", "Quiero un mes
gratis" are exactly 20).

**Pricing ladder (2026-09-16).** The wizard quotes a ladder and hands off rather than a single
number: Atención 100.000 · Atención + Audios 140.000 · Cierre 200.000 (adds follow-up of inquiries
that didn't close) · a-medida from 300.000 (own-CRM integration) · Bot de Ventas +100.000 as an
add-on. First month free, install included. For an inmobiliaria the outbound bot is the *add-on*,
not the pitch — they want inbound + audio + follow-up + CRM. Keep `PRICE_TEXT` in `_src/ventas.js`
and the landing (`BotArgentoLandingPageRepo`) in sync; they contradicted each other for a day
("50 % OFF" vs "primer mes GRATIS").

**UX revision (2026-06-08, superseded by v3 above):** the `intro` re-ask is **skipped** for campaign prospects (a
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

**⚠ Two field lessons from Arka's first real campaign day (2026-09-09, wa_id 34669365849 "FiMov"):**

1. **Exact-token opt-out matching is not enough.** A human wrote *"Que no nos interesa"* — no token
   matched (`no me interesa` ≠ `no nos interesa`) and the wizard re-asked the pitch question at
   someone who had just said no. Fix (deployed on arka, apply to every outbound tenant): after the
   exact-token check, add a **regex fallback for negative-interest phrasings** — e.g.
   `/\bno\b.{0,20}\binteres\w*/` (covers "no me/nos interesa", "no estamos interesados", leading
   "que...") and `/\bno\b[,.\s]{0,3}gracias\b/`. Bias toward suppression on ambiguity: compliance
   rule #3 says suppression is absolute — a false-positive opt-out is safer than messaging a no.
   Bare "no" must still NOT opt out.
2. **Clinics/SMBs run their own WhatsApp auto-responders → bot-vs-bot loops.** FiMov's booking bot
   auto-replied to the template; our wizard treated it as engagement, and each "No he entendido"
   re-ask triggered another canned auto-reply — **13 identical round-trips in ~2 minutes**. Any
   naive re-ask branch will loop against an auto-responder. Fix (deployed on arka): a
   **consecutive-miss guard** (`guided_misses` in the qualification snapshot) — miss 1 re-asks,
   miss 2 sends one final polite message re-showing the option buttons and parks the session in a
   `dormant` step, where unrecognized input produces **no outbound at all** (inbound still logged)
   and any valid option/affirmative resumes the script and resets the counter. Also note the
   auto-reply signature for triage: inbound arriving seconds after template delivery with long
   canned text ("Gracias por contactar...", horario, etc.) is a machine, not a reply.
3. **The router's per-contact lock does not serialize, and auto-responders expose it.** Two messages
   439 ms apart produced two identical replies on ventas (2026-09-17) and left `guided_misses` at 0,
   so the miss guard never counted. `pg_advisory_lock` is session-scoped on a pooled connection
   (re-entrant), and `Release Advisory Lock` never runs. The fix that works today is **burst
   grouping** — every message waits ≥4 s before consuming. Full write-up and the rest of the
   defaults: `whatsapp-automation.md` §Conversation hardening. Ventas' port lives in
   `Sales Automation/scripts/burst/` (`burst-nodes.mjs` is the single source of the 10 nodes,
   `harness-burst.mjs` has 65 assertions).
4. **A lead who asks something off-script must not get the menu back.** *"Enviame valores y lo
   evaluo"* at an option step got *"No te entendí"* + the brochure again, and no alert fired because
   handoff only triggered on a button tap; the lead sat unanswered five days. Every outbound wizard
   now answers **price intent** with the real numbers at any step and hands off, and treats free text
   that looks like a question (`?` or ≥3 words) at a warm step as a handoff with the lead's words
   quoted — both gated by an auto-responder blocklist so machines don't page a human.
5. **Ops: multi-statement `psql -c` is one implicit transaction.** `psql -c "INSERT; UPDATE;
   DELETE"` rolls back EVERYTHING if any statement errors — even after printing `INSERT 0 1`.
   A manual suppression "applied" this way silently vanished when a later statement failed.
   Run critical writes as separate `-c` calls (or explicit BEGIN/COMMIT) and re-SELECT to verify.
6. **Meta creates a template's first language as `en` unless you pick otherwise.** On tasty it
   happened twice (`outreach_intro`, then `outreach_intro_pack` — approved as `en`, unusable with
   `template_lang='es_AR'`). Select **Español (ARG)** explicitly when creating, then check with
   `GET /<waba_id>/message_templates?name=<name>` that the `language` is `es_AR` before pointing a
   campaign at it (the es_AR copy ended up as `outreach_intro_pack_es` / `_v2`).
7. **Tasty's field lessons (2026-09-11 → 09-28)** — prospects' away-bots faking handoffs,
   delayed-delivery bots the timing check can't see, and declines phrased without "interés" — are
   written up as platform defaults in `whatsapp-automation.md` §Conversation hardening §6b–§8.

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

## Funnel reconciliation (`v2-outreach-reconcile.json`, 2026-06-10)

**The gap it fills:** a prospect's reply flows through the shared engine into `automation.lead_log` /
`session_memory`, but **nothing was updating `outreach.recipients.status` to `replied`** — so the
dashboard funnel (reply rate, "Respondieron") sat at 0 even after real replies. Rather than surgery on
the live router, a small **scheduled reconciler** (every 5 min) derives the terminal funnel states from
the source-of-truth tables: `replied` = recipient still `sent/delivered/read` with an inbound
`lead_log` row at/after `last_send_at`; `opted_out` = recipient whose `wa_id` is in
`outreach.suppression`. Idempotent, no params, no router risk; ~5-min lag (fine for an observability
dashboard). Standalone workflow like the quality poll — imported/wired/activated via the same scripts.
(`sent → delivered → read` still need Meta status webhooks, which remain deferred.)

## Scripts

`build.mjs` (targets `ventas` / `campaign-runner` / `router`), `import-n8n.mjs` (idempotent; ORDER list
includes quality-poll + reconcile), `wire-n8n.mjs` (REST: creates the `Postgres Ventas` credential +
attaches to all Postgres nodes + wires the router's executeWorkflow ids — replaces manual MCP wiring;
n8n 2.x credential gotcha: `sshTunnel:false` present, `ssh*` fields ABSENT), `set-error-workflow.mjs`,
`patch-wizard-live.mjs` (manifest-based, no hardcoded ids; patches a Code node in place without
re-import — structural changes like a new node still need re-import or a manual PUT),
`seed-recipients.mjs` (CSV → SQL; **refuses rows without `opt_in_basis`**), and `set-opt-in-basis.mjs`
(stamps one defensible basis onto a scraped CSV before seeding). No `patch-persister-template.mjs` — the
copied persister is already template-capable.

**Activation gotcha:** importing/wiring does NOT activate a workflow. The schedule-triggered ones
(`campaign-runner`, `quality-poll`, `outreach-reconcile`) and the `router` must be POSTed to
`/workflows/<id>/activate` (or toggled in the UI) or they never fire on their own.

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

## Provider mode + Chatwoot mirror (first built for arka, 2026-09-16)

Some clients want **our Meta infrastructure but their own inbox**: we send the templates and own
opt-out/suppression, our bot stays silent, and every message is mirrored into the client's helpdesk
where their agents answer. **Full playbook: `references/chatwoot-mirror.md`** (architecture, env,
the three workflows, attachments in both directions, Chatwoot API specifics, install checklist).

In one paragraph: a router flag (`<TENANT>_CONVERSATION_MODE=chatwoot|bot`) turns every non-opt-out
inbound into a silent `suppress_send` turn that still logs, still reconciles the funnel and still
fires the T1 first-reply alert; a fire-and-forget bridge sub-workflow mirrors inbound events and sent
templates into the client's inbox with an anti-echo marker (`content_attributes.mirror`); a webhook
back from the helpdesk forwards agent replies — and attachments, uploaded to Meta `/media` first —
through our own `/webhook/inbox`, posting a private note when a send is refused.

- ⚠️ **Compliance, not Chatwoot-specific: the inbox `send` action must check
  `outreach.suppression`** (403, fail-closed). arka shipped without it and an agent reply reached an
  opted-out contact (2026-09-16). The dashboard uses the same endpoint, so **any tenant with the
  two-way inbox** has the gap until patched. **Fixed pattern (2026-09-18, engine repo
  `v2-inbox-webhook.json`, live on client1):** `Check Window` also returns `suppressed`, reading
  `outreach.suppression` only if `to_regclass` finds it and through `query_to_xml(format(…))` so the
  name resolves at run time — one webhook for inbound and outbound tenants. `Gate Window` returns
  403 before the 24h 409, fail-closed (anything but an explicit `false`). **ventas still runs the
  old webhook** without it; port that one change there. ventas also logs a burst sent during a
  takeover as one joined `lead_log` row; client1's `Log Human Inbound` writes one row per message
  (`human_log_rows` + `jsonb_array_elements`).


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

See `references/tenants-status.md` → **Bot Argento Sales** (state lives there; this file is
architecture). As of 2026-07-30: **live, Phase A complete, outbound idle** — campaign 1 finished
2026-06-19 (12/87 replied), no new campaign seeded since; inbound half + dashboard operational.
Proposed next feature: two-way inbox (`Sales Automation/docs/ventas/two-way-inbox-plan.md`, not started).
