# CRM-lite ("Leads") — one person, N opportunities

The sales pipeline inside the dashboard: a board, a list, a per-opportunity card, reminders, and a WhatsApp notice to the advisor when a reminder comes due. Built 2026-09 on `client1`, the test tenant, over ten rounds and one re-architecture. **Not yet on any other tenant.**

**The source of truth for the business rules is the dashboard repo: `docs/crm-oportunidades.md`** (17 numbered rules + a Mermaid ER diagram, updated in the same PR as any rule change). This file carries the platform-level facts: what exists, what is deployed where, the n8n side, and the gotchas that cost time.

## The model, and why it changed

Until migration `0010` a lead **was** the person: `contact_wa_id` was the key of `dashboard.lead_state`, of the API routes, of the URLs. That broke on 2026-09-23 when a lead closed by hand did not reappear after the person wrote again — a manual close is sticky, so the card stayed in the collapsed rail.

The fix (option A, chosen by Jonatan) splits the two things a "lead" was conflating:

| Concept | Table | Key |
|---|---|---|
| The **person** | `dashboard.contacts` (renamed from `manual_leads`) | `contact_wa_id`, the WhatsApp id |
| The **commercial process** | `dashboard.opportunities` | `id BIGSERIAL`, plus `seq` 1..N per person |

**The rule that decides everything: "una derivación por rubro es una oportunidad."** Only two things create one — a **bot handoff** for a rubro the person has no open opportunity in, or an **advisor** by hand. Plain messages create nothing; they count as activity for every open opportunity of that person. People who wrote and never reached a handoff are **not on the board** — they live in Conversaciones under a "Sin derivar" filter with a one-click "Abrir oportunidad".

Each opportunity carries a **rubro** (`kind`, a vertical intent key: Ventas, Alquileres, Tasaciones…), its own stage, owner, priority, budget, reminder and activity. What belongs to the person (name, origin, what the bot captured, opt-out, the WhatsApp conversation) is shared.

Sync happens **at read time**, not by a trigger: `src/lib/queries/opportunity-sync.ts` runs idempotent `INSERT … SELECT … ON CONFLICT DO NOTHING` at the start of every CRM read. There is no cleaner hook — the bot writes `automation.*` through n8n, and a DB trigger would be DDL on a schema the dashboard only reads.

## The WhatsApp reminder notice (the one place n8n writes `dashboard.*`)

An advisor schedules "volver a contactar el día X"; when it comes due, n8n sends them a WhatsApp.

- Workflow **`v2-crm-reminders.json`** in the engine repo, 7 nodes, independent of the router. Installed with `node scripts/patch-tenant-live.mjs <tenant> crm-reminders`, which **creates** it when the tenant has no id yet (the only other create-capable target is `inbox`) and syncs it from the repo afterwards. 10 assertions in the `verify` target.
- **Goes only to the advisor who owns the opportunity.** The `JOIN` on `team_members` also requires `active`, `notify_whatsapp` and a non-empty `whatsapp_number`. No owner → **no notice**, and the panel marks it "Sin responsable · no se avisa", visible to any asesor so it does not die in silence.
- **Office hours only: 9 to 19, Monday to Friday**, tenant timezone. Something due Friday 19:05 goes out Monday 9:00.
- **One notice per reminder, ever.** `next_action_notified_at` is what stops a resend. Marking it done closes it; re-scheduling clears the column and re-arms the notice. **If the advisor ignores the message, nothing nudges them again** — accepted 2026-09-25, revisit after a few weeks of real use.
- A **rejected send does not mark the column**, so it retries next cycle. `CRM_REMINDER_MAX_AGE_DAYS` (7) stops that loop over a dead number. This is deliberately **not** the campaign runner's behaviour, which marks `sent` even on failure and never retries.
- Template **`crm_reminder`**, approved, UTILITY/`es_AR`. Full contract in `MIGRATION-crm-reminders-client1.md` (engine repo). **The fixed text header must not be sent as a component** — that is what triggers #132000. The URL button's prefix is baked into the template and points at client1's domain, so **another tenant needs its own approved template**. ventas has one (id `933329702739707`, same text, prefix `dashboard.ventas…`) — submitted as UTILITY, **Meta filed it as MARKETING**; works the same, costs a few cents more. Contract in `Sales Automation/docs/ventas/templates/crm_reminder.md`.
- **A tenant whose router is not the engine's** (ventas: the Sales Automation `_src` router) is registered in `scripts/tenants.json` with `routerSource: "external"`. The deployer then refuses every router-editing target there and allows only `inbox`, `crm-reminders` and `verify`; `verify` skips the engine topology checks. On ventas it reports two pre-existing inbox gaps (no suppression check, no takeover expiry) as FAIL — real, and unrelated to the CRM.
- Turning it on is **two files on the tenant's VPS dir**: the `.env` AND the n8n service's `environment:` block (`CRM_REMINDER_TEMPLATE_NAME`, `CRM_REMINDER_TEMPLATE_LANG`), then recreate only the n8n container between campaign-runner ticks (:00/:30). ventas' VPS has the standalone `docker-compose`, not the `docker compose` plugin.

### The write contract

**n8n writes exactly one column of `dashboard.*`: `opportunities.next_action_notified_at`.** Nothing else — no events, no stages. Written down in the dashboard's `CLAUDE.md` (Reglas No Negociables) and `docs/crm-oportunidades.md`, and enforceable via `migrations/0011_n8n_reminder_grants.sql`: `USAGE` on the schema, `SELECT` on four tables, `UPDATE` of that one column, guarded by role existence.

On client1 the grant is a **no-op because n8n connects as the cluster superuser**. It is there so the contract is explicit and so this works on a tenant where n8n is not superuser.

## Which tenants have it — verified live 2026-09-26

**`client1` and `ventas`** (since 2026-09-25). client1 is the test tenant, assigned to no real client, which is why its data was migrated without ceremony. ventas is Bot Argento’s own outbound sales tenant, and the first vertical where the rules differ (see **Outbound** below).

| Tenant | Vertical | CRM visible? | Dashboard revision | Last migration | `opportunities` table | Reminder workflow |
|---|---|---|---|---|---|---|
| **client1** | `real-estate` | **yes** | `3fe13a0` | `0012` | yes | `5DHBIyV3lPK1HmwF`, active + enabled |
| plec | `architecture` | no | `f3446c1` | `0000_init` | no | — |
| **ventas** | `outbound-sales` | **yes** (`CRM_ENABLED=1`, `CRM_SINCE=2026-09-25T21:29-03:00`) | `3fe13a0` | `0012` | yes (154 contacts: 122 `campaign` / 32 `whatsapp`; 1 opportunity, opened by hand) | `x60IO7UgJpgduurW`, active + enabled 2026-09-26 (template `933329702739707`; first real notice not yet observed — armed on a Saturday) |
| tasty | `outbound-sales` | no | `01bf683` | `0004` | no | — |
| arka | `outbound-sales` | no | `67f241a` | `0004` | no | — |
| artbox | — (Postgres only, no dashboard container) | no | — | none | no | — |

**Two keys gate it (since PR #36).** The VERTICAL declares the capability (`features.crmTab` + a `crm` block: `real-estate` and `outbound-sales` have it, `architecture` does not) and the TENANT turns it on with **`CRM_ENABLED=1`** in `dashboard.env`. Both on purpose: three tenants run `outbound-sales` (ventas, tasty, arka) and only ventas bought the CRM. `CRM_SINCE` (ISO) keeps replies/handoffs before that instant from opening opportunities on their own.

**The env-var trap that nearly broke the deploy:** every `dashboard.compose.yml` lists its variables explicitly in `environment:` as `${VAR}`; `--env-file` only feeds that interpolation and **does not inject a variable the compose does not name**. Adding `CRM_ENABLED=1` to the `.env` alone does nothing — the line `CRM_ENABLED: "${CRM_ENABLED}"` has to be in the compose too. Same trap as `SESSION_MEMORY_TTL_MS` on the n8n side. Open corollary: if the compose names it and the `.env` does not set it, the interpolation yields `""` and the zod `enum(...).optional()` rejects it at boot.

**But the migrations would run.** All of them track `DASHBOARD_TAG=latest`, so the next `up -d` on any tenant pulls this image and applies `0005`…`0011`: it creates the CRM tables empty, drops an empty `lead_state`, and grants n8n the one column. Harmless, invisible to the user, and intended — Jonatan does not pin versions on purpose. Worth saying out loud before someone runs `update-dashboards.sh tenant=all` and is surprised by a migration run.

**To bring it to a real tenant you need two things**, neither of which is a deploy: a vertical with a `crm` block and `crmTab: true` (today that means a real-estate agency, or porting the block to another vertical), and — for the reminder notice — **its own approved `crm_reminder` template**, because the URL button's prefix is baked into client1's domain inside Meta.

Verified live on client1: first real notice delivered and recorded, closed from the panel three minutes later; the next cycle sent nothing. PRs #13–#34 on the dashboard; the engine side is on `main` at `8319436`. Rollback image `client1-rollback-20260925-a` → `7cd0e83`.

## Outbound: the rules that change when WE write first

`docs/crm-oportunidades.md` §“Reglas por vertical” is the source of truth. Decided with Jonatan 2026-09-25 from ventas’ own numbers: 154 people replied to campaigns, 22 reached a handoff, **132 replied and never derived** — the inbound rule would have hidden 132 engaged people.

| | Inbound (`real-estate`) | Outbound (`outbound-sales`) |
|---|---|---|
| What opens (`crm.opener`) | `handoff` — a bot handoff of a rubro | `reply` — the person’s first inbound message; the campaign already chose them. A handoff pushes to Calificado |
| Where the rubro comes from (`crm.kinds`, `crm.kindFromCampaign`) | the handoff’s intent | the PROSPECT: `outreach.recipients.vertical` of the latest campaign that wrote to them, else the wizard’s `rubro`, else blank |
| Stages | Nuevo → Calificado → Visita → Reserva → Cerrado / Perdido | Nuevo → Calificado → Demo → Propuesta → Cerrado / Perdido |
| Inactivity | 30 days, warn at 7 | 14 days, warn at 3 |
| Origin | `whatsapp` / manual | `campaign` when the number is in `outreach.recipients` |
| Name | typed > `lead_name` > profile | typed > **`recipients.business_name`** > `lead_name` > profile |

`crmKinds()` (`src/lib/crm/intent.ts`) replaces `verticalConfig().intents` everywhere in the CRM — without it outbound fell into a synthetic “Otras” rubro, neither filterable nor editable. There is **no e2e for outbound** (the suite runs `VERTICAL=real-estate`); the reply-mode sync is pinned by six live-DB unit tests that create a minimal `outreach` schema in the dev/CI database.

## Gotchas that cost time

- **postgres.js**: `IN ${sql([...])}` guesses identifier-vs-value from the preceding text and breaks inside `FILTER(...)`. Use `= ANY(${arr}::text[])`. Drizzle swaps the json/timestamp serializers, so raw `sql` must pass `${JSON.stringify(x)}::jsonb` and ISO strings.
- **One pool per process.** `src/db/client.ts` cached the client only on `global` and only outside production, and `sql` is a Proxy — so production built a fresh pool per query. With 3–4 queries per page nobody noticed; CRM pages do 10+ and `/leads` died with Postgres `53300`. Fixed with a module singleton (PR #31). **If you add queries per render, check this first.**
- **A bare `/leads` means "restore my last filters"** to `lib/crm/filter-memory`, so no internal link may produce one: the Tablero tab bounced straight back to the List (PR #32). If you add state restored from an empty URL, check no link generates it.
- **`has_column_privilege` is useless for auditing the grant on client1** — n8n is superuser, so it answers yes to everything. Read `pg_attribute.attacl` / `pg_class.relacl`, or test with an ordinary role on a scratch database.
- **Migrations must tolerate `automation.*` not existing yet** (fresh DB, CI): guard with `information_schema`, the way `0001` and `0010` do.
- **Hydration flake in CI on `/conversations`**: the first click can land before React hydrates and silently do nothing. The house pattern is to retry the click→effect pair inside `expect(async () => {…}).toPass({timeout: 30_000})`. It passes locally and only fails in CI.
- **The e2e suite is memory-hungry.** Full runs have been killed on Jonatan's laptop (16 GB, Chrome eating most of it). CI is the run that counts.
- **Team WhatsApp numbers were stored unnormalized** until `0011`: the zod schema accepted 8–15 digits, so a local `1155550000` was saved as typed and the notice would never arrive. Now it goes through `normalizeLeadPhone`, the same helper the manual-lead form uses, and the form previews what will be stored.

## Finding the WABA id for a tenant (reusable recipe)

Needed to read an approved template back from the Graph API, and **not** stored in any repo or in `/opt/n8n/<tenant>/.env` (only `META_PHONE_NUMBER_ID`). It cannot be derived from the phone number id, and the n8n system-user token only has `whatsapp_business_management` + `whatsapp_business_messaging` — **not** `business_management` — so every edge off the business node answers #200.

What works: the webhooks n8n has already stored. Pull the long ids out of `execution_data` in the tenant's Postgres, then try each against `GET /{id}?fields=id,name`; the one that answers is the WABA.

For client1: business `807638368889424`, **WABA `912244891288296`** ("BotArgento2"), phone number id `960701240462680`, app `1142418790661281`.

## Selling it

Same shape as the two-way inbox and the campaign actions: env-gated per tenant, so nobody sees it until it is turned on. The reminder notice is the part a client feels immediately — it is the difference between a CRM they have to remember to open and one that comes to them. Costs one UTILITY template message per notice on the client's WABA.
