# Postgres `automation` schema

**This schema is identical for every agency on the platform.** It is not vertical-specific. The DDL below is the canonical source. New verticals do **not** modify these tables — they add views (`automation.v_<vertical>_*`) on top, or use the existing generic columns.

Source of truth: `C:\Desarollo\jperez\n8n\whatsapp-automation-claude\postgres-setup.sql`.

## Schema split

| Schema | Owner | Written by | Read by |
|---|---|---|---|
| `automation.*` | n8n workflows | router/wizards/persister | dashboard (SELECT only via `dashboard_app` role) |
| `dashboard.*` | dashboard app | dashboard — **plus exactly one column written by n8n**: `opportunities.next_action_notified_at`, the CRM reminder notice (`migrations/0011_n8n_reminder_grants.sql`, `references/crm-leads.md`) | dashboard |
| `runtime.*` | n8n engine (internal state) | router only — `inbound_buffer` via `consume_inbound_buffer()` | nobody else; `PUBLIC` revoked, so the dashboard role cannot read raw message text. See §`runtime` schema below. Applied on client1 2026-09-15 only. |

The CRM's own tables (`dashboard.contacts`, `dashboard.opportunities`, `dashboard.lead_events`, `dashboard.team_members`) live on the dashboard side and exist only on `client1` today — see `references/crm-leads.md` for the model and the per-tenant state.

The dashboard's DB user `dashboard_app` has `SELECT`-only on `automation.*`. Any `INSERT`/`UPDATE`/`DELETE` attempt against `automation.*` from the dashboard is a bug and will be rejected by the DB role. This is the load-bearing isolation that makes the dashboard safe to deploy without coupling it to n8n's write path.

## Tables

### `automation.session_memory`

Per-contact conversation state. One row per WhatsApp ID. Loaded on every inbound message.

| Column | Type | Notes |
|---|---|---|
| `contact_wa_id` | TEXT | **PK.** Meta WhatsApp ID. |
| `updated_at` | TIMESTAMPTZ | Defaults `NOW()`. Used by router for TTL check (`SESSION_MEMORY_TTL_MS`, default 1800000ms = 30 min). |
| `profile_name` | TEXT | From Meta payload. |
| `lead_name` | TEXT | Captured during qualification. |
| `qualification_snapshot_json` | JSONB | **The vertical-agnostic payload.** Free-form bag of qualification data the wizard accumulates (selected zone, property type, bedrooms, budget; or for a different vertical, project type, area, style, etc.). |
| `last_turns_json` | JSONB | Recent turns for context. |
| `session_summary` | TEXT | Wizard-generated rolling summary. |
| `last_message_id` | TEXT | Last inbound message ID processed. |
| `last_route` | TEXT | Last child workflow visited. |
| `last_confidence` | DOUBLE PRECISION | Reserved for AI-triage confidence (currently unused; OpenAI not wired up in v2). |

**Reuse pattern across verticals:** keep the column shape; change only what goes inside `qualification_snapshot_json`. Never add per-vertical columns here.

### `automation.lead_log`

Append-only log of every inbound and outbound message. Powers the dashboard's conversations + KPI views.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `log_timestamp` | TIMESTAMPTZ | When the row was written |
| `direction` | TEXT | `inbound` or `outbound` |
| `event_type` | TEXT | Message vs status |
| `route` | TEXT | Which child workflow handled it |
| `execution_id` | TEXT | n8n execution ID (links to error context) |
| `message_id` | TEXT | Meta message ID (used for dedup) |
| `related_message_id` | TEXT | For outbound: the inbound that triggered it |
| `contact_wa_id` | TEXT | Customer's WhatsApp ID |
| `profile_name`, `lead_name` | TEXT | Same as session_memory |
| `phone_number_id` | TEXT | Tenant's WhatsApp phone (multi-phone tenants) |
| `message_type` | TEXT | text/image/audio/etc |
| `text_body` | TEXT | Raw message body |
| `intent` | TEXT | Wizard-classified intent |
| `target_zone` | TEXT | Wizard output (real-estate flavor; for other verticals reuse as "location" or leave empty) |
| `budget_amount`, `budget_currency` | NUMERIC, TEXT | Captured budget |
| `property_type` | TEXT | Real-estate vocab; for other verticals reuse as "service category" |
| `bedrooms` | INTEGER | Real-estate vocab; nullable for other verticals |
| `payment_mode`, `purchase_timing` | TEXT | Captured qualifiers |
| `confidence` | DOUBLE PRECISION | AI confidence (when AI triage is enabled) |
| `handoff` | BOOLEAN | True if this turn triggered handoff |
| `handoff_reason` | TEXT | Wizard-supplied reason |
| `matched_listing_ids` | TEXT | Comma-joined listing IDs returned in this turn |
| `listing_count` | INTEGER | Convenience count |
| `session_summary` | TEXT | Snapshot of session_summary at this point |

**Indexes:**
- `ux_lead_log_direction_message` — UNIQUE on `(direction, message_id) WHERE message_id <> ''`. **This is the dedup index.** The router checks for an existing inbound row with the same `message_id` and short-circuits if found.
- `ix_lead_log_contact_timestamp` — on `(contact_wa_id, log_timestamp DESC)`. Powers the per-contact conversation timeline in the dashboard.

**Reuse pattern across verticals:** the property_type/zone/bedrooms columns have real-estate names but the *role* is generic (categorical qualifier, location qualifier, count qualifier). For a non-property vertical, fill them with whatever fits or leave empty. Don't rename — the dashboard's queries depend on these column names.

### `automation.escalations`

Append-only log of every handoff or workflow error.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `escalation_timestamp` | TIMESTAMPTZ | |
| `escalation_type` | TEXT | `workflow_error` (from error handler) vs customer handoff (e.g., `valuations`, `sales`, `questions`). The dashboard's "errors" filter uses this to separate operational issues from real handoffs. |
| `workflow_name`, `execution_id`, `workflow_id`, `execution_url`, `last_node_executed`, `mode`, `stack` | TEXT | n8n execution context — populated by the error handler for `workflow_error` rows |
| `contact_wa_id`, `profile_name`, `lead_name` | TEXT | Customer identity |
| `inbound_message_id`, `agent_message_id` | TEXT | Message IDs around the escalation point |
| `reason` | TEXT | Wizard-supplied or error message |
| `intent`, `target_zone`, `budget_amount`, `budget_currency`, `property_type`, `bedrooms`, `payment_mode`, `purchase_timing` | (mixed) | Snapshot of qualification at handoff time |
| `matched_listing_ids`, `matched_listing_urls` | TEXT | What we showed the customer |
| `transcript_summary` | TEXT | Wizard's session summary at handoff |
| `fallback_sent` | BOOLEAN | Did the error handler send a fallback message to the user |
| `alert_email_to` | TEXT | Where the SMTP alert was sent (`ALERT_EMAIL_TO` env var) |
| `latest_user_message` | TEXT | Most recent customer text |
| `handoff_target` | TEXT | **Phase 1 addition.** Standardized routing target (`valuations`, `sales`, `rents`, `questions`, etc.). Indexed. |
| `preferred_contact_slot` | TEXT | **Phase 1 addition.** Customer-supplied preferred contact time. |
| `created_at` | TIMESTAMPTZ | |

**Indexes:**
- `ix_escalations_timestamp` on `escalation_timestamp DESC` — recent first
- `ix_escalations_handoff_target` on `handoff_target` — for per-team queues

The Phase 1 ALTERs (`handoff_target`, `preferred_contact_slot`) are idempotent (`ADD COLUMN IF NOT EXISTS`), so re-running `postgres-setup.sql` on existing installs is safe.

### `automation.providers` (Phase 2 — canonical platform table since 2026-05-20)

Supplier / vendor directory. Wizards INSERT here when a contact registers as a supplier. The dashboard exposes a `/providers` route gated by `verticalConfig.features.providersTab` — present on every tenant, but only the verticals that opt in show the UI.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `contact_wa_id` | TEXT | Customer's WhatsApp ID, NOT NULL default `''` |
| `business_name` | TEXT | Vendor/company name, NOT NULL default `''` |
| `category` | TEXT | Rubro/category, NOT NULL default `''` |
| `zone` | TEXT | Service zone, NOT NULL default `''` |
| `email`, `phone` | TEXT | Contact info, NOT NULL default `''` |
| `status` | TEXT | `'new'` (default) / `'approved'` / `'rejected'` |
| `notes` | TEXT | Free-text, NOT NULL default `''` |
| `lead_name`, `profile_name` | TEXT | Captured identity |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

**Indexes:** `ix_providers_status_category` `(status, category)`, `ix_providers_zone`, `ix_providers_contact`, `ix_providers_created_at DESC`.

**Insert pattern used by wizards:** "Conditional INSERT" — a Postgres node downstream of the wizard's Code node runs `INSERT … SELECT … WHERE $N::boolean = true`. The wizard sets the flag true only on the final turn, so the same node handles every step of the multi-turn conversation. Avoids modifying the shared persister.

### `automation.labor_pool` (Phase 2 — canonical platform table since 2026-05-20)

Talent / oficios pool. Wizards INSERT here when a worker registers (seeking work or offering services). Dashboard route `/labor-pool` gated by `verticalConfig.features.laborPoolTab`.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK |
| `contact_wa_id` | TEXT | NOT NULL default `''` |
| `worker_name` | TEXT | NOT NULL default `''` |
| `mode` | TEXT | `'seeking'` (busca trabajo) or `'offering'` (ofrece servicios) |
| `specialty` | TEXT | NOT NULL default `''` |
| `zone`, `phone` | TEXT | NOT NULL default `''` |
| `status` | TEXT | `'new'` / `'contacted'` / `'archived'` |
| `notes`, `lead_name`, `profile_name` | TEXT | NOT NULL default `''` |
| `created_at`, `updated_at` | TIMESTAMPTZ | |

**Indexes:** `ix_labor_pool_status_specialty`, `ix_labor_pool_mode_specialty`, `ix_labor_pool_zone`, `ix_labor_pool_contact`, `ix_labor_pool_created_at DESC`.

### `automation.inventory`

Per-tenant catalog. Synced from Google Sheets (currently) by `v2-sync-inventory.json` every 15 min.

| Column | Type | Notes |
|---|---|---|
| `listing_id` | TEXT | Composite PK part 1 |
| `source_sheet` | TEXT | Composite PK part 2 (e.g., `inventory_sales`, `inventory_rents`) |
| `status` | TEXT | `available` / `sold` / etc. |
| `property_type` | TEXT | Real-estate vocab; for other verticals reuse as service category |
| `operation_type` | TEXT | `sale`/`rent`; for non-property reuse as flow type or empty |
| `zone` | TEXT | Location |
| `price`, `currency` | NUMERIC, TEXT | |
| `bedrooms`, `bathrooms`, `area_m2` | INTEGER, INTEGER, NUMERIC | Numeric metrics; nullable |
| `title`, `short_description`, `features` | TEXT | Free-text |
| `listing_url` | TEXT | Public URL (the wizard returns this to the customer) |
| `agent_name` | TEXT | Assigned agent |
| `synced_at` | TIMESTAMPTZ | Last sync timestamp |
| `created_at` | TIMESTAMPTZ | |

**Indexes:**
- `ix_inventory_status_operation` on `(status, operation_type)`
- `ix_inventory_zone` on `zone`
- `ix_inventory_synced_at` on `synced_at DESC`

**Reuse pattern across verticals:** if the real-estate column names violate the new vertical too much (e.g., a dental clinic's "treatments" don't have `bedrooms`), prefer one of:

1. **Reuse as-is** with empty/NULL columns where they don't apply (lowest friction).
2. **Add a vertical-specific view** on top: `CREATE VIEW automation.v_dental_treatments AS SELECT listing_id, title, price, ... FROM automation.inventory WHERE source_sheet='treatments'`.
3. **Add a parallel table** `automation.<vertical>_inventory` if the shape really doesn't fit, but the dashboard's existing `automation.v_*` views won't pick it up automatically — you'd need to extend the views.

### `automation.media_assets` (canonical since 2026-09-28; written by plec's router only, so far)

WhatsApp media kept so it can be shown or played later. DDL: `Plec Automation/n8n/compose/media-assets.sql` (idempotent — `IF NOT EXISTS`, `OR REPLACE`, role-guarded grant; applied on all six tenants 2026-09-25/28). Why bytea and not a volume or S3: ~45 media/month × ~42 KB ≈ 10 MB at a 90-day steady state, no new infrastructure, rides the DB backup, and the dashboard already has a read-only connection.

| Column | Type | Notes |
|---|---|---|
| `id` | BIGSERIAL | PK; what the dashboard's bytes route is keyed by (`/api/media/[id]`), never Meta's id |
| `message_id` | TEXT UNIQUE | Joins to `lead_log.message_id`; UNIQUE so a retried execution updates instead of duplicating |
| `contact_wa_id` | TEXT | |
| `media_kind` | TEXT | `audio` / `image` / `document` are captured; `video` / `sticker` are not (decision 2026-09-28) |
| `media_id` | TEXT | Meta's media id, kept so a failed download is retryable (~30 days on Meta's side) |
| `mime_type` | TEXT | From Graph's metadata (`audio/ogg` for voice notes — the iOS playback question) |
| `byte_size` | INTEGER | Real length of `content`, not what Meta declared |
| `content` | BYTEA | NULL when nothing was stored; over ~2 KB Postgres keeps it in TOAST |
| `fetch_status` | TEXT | `stored` · `too_large` · `unsupported` · `meta_failed` · `download_failed` · `read_failed` · `store_failed` · `skipped` — a row is written on **every** path so the UI can say why a bubble is empty |
| `transcription_status` | TEXT | Audio only; the only durable record of how the transcription went |
| `created_at` | TIMESTAMPTZ | Retention key |

**Indexes:** `ix_media_assets_contact (contact_wa_id, created_at DESC)`, `ix_media_assets_created_at (created_at)`, plus the PK and the UNIQUE.

**Retention** is not a scheduled job: the insert statement is a data-modifying CTE whose main statement is `DELETE … WHERE created_at < now() - $retention` (same shape as `runtime.consume_inbound_buffer`), parameterised by `MEDIA_RETENTION_DAYS` (default 90). n8n's own copy of each download (`binaryData/` on disk, filesystem mode) is pruned with execution data at ~11–14 days, i.e. sooner.

**View `automation.v_media_assets`** exposes everything **except `content`** (plus `has_content`), so a list query can never drag binaries across the wire. `dashboard_app` has SELECT on the view **and** on the base table including `content` — the one place the dashboard reads the base table is the bytes route, deliberately. Not in `REQUIRED_VIEWS` yet; now that every tenant has it, adding it there is the right guard for a fresh tenant (Fase C of `plan-media-v2.md`).

**Writers:** the router's `Store Media` (success) and `Store Failed` (its error output → `fetch_status='store_failed'`, content NULL, never clobbering stored bytes). The dashboard never writes it (invariant 2).

## Dashboard-side views (read-only consumers)

The dashboard reads only `automation.v_*` views (Drizzle-typed wrappers in `src/db/views.ts` of the dashboard repo). Current set (7 views — also the list in `REQUIRED_VIEWS`, checked by `scripts/verify-view-compat.mjs` at every container boot — missing any one of them is a fast-fail):

| View | Source table(s) | Purpose |
|---|---|---|
| `v_daily_metrics` | lead_log + escalations | KPI cards on overview |
| `v_flow_breakdown` | lead_log | Per-intent volume over time |
| `v_contact_summary` | lead_log | Conversations list |
| `v_handoff_summary` | escalations | Handoff target counts |
| `v_follow_up_queue` | lead_log + escalations | Follow-up priority queue |
| `v_providers` | providers | Supplier directory (`/providers` route) |
| `v_labor_pool` | labor_pool | Talent pool (`/labor-pool` route) |

**Invariant:** the underlying tables and views are identical for every tenant — UI differentiation comes from `verticalConfig.features`, not from per-tenant schema variations. When extending the dashboard with a new vertical capability, the cleanest path is: add view to platform `postgres-setup.sql` → apply idempotently to existing tenant Postgres → add Drizzle types + select function to `src/db/views.ts` → add to `REQUIRED_VIEWS` → gate the UI route with a `verticalConfig.features.<flag>` check.

Adding a new vertical does not require new views unless the metric semantics change. New verticals get their differentiation from the **dashboard's `verticalConfig`** (intents, terminal flows, colors, features), not from the schema.

## `runtime` schema (engine-internal, 2026-09)

Source: `whatsapp-automation-claude/runtime-inbound-buffer.sql` (idempotent). **Not** part of the shared `automation` DDL: it holds transient engine state, lives in its own schema so invariant #1 stays intact, and `PUBLIC` has no access (the dashboard role cannot read raw message text). Applied on client1 2026-09-15; other tenants get it with the burst-grouping upgrade.

### `runtime.inbound_buffer`

| Column | Type | Notes |
|---|---|---|
| `seq` | BIGSERIAL | arrival order |
| `message_id` | TEXT PK | Meta `wamid`; `INSERT … ON CONFLICT DO NOTHING` makes Meta retries harmless |
| `contact_wa_id` | TEXT | |
| `text_body`, `message_type`, `media_id` | TEXT | |
| `meta_ts` | BIGINT | Meta timestamp (seconds) |
| `consumed_by` | TEXT | `message_id` of the execution that answered the group, or `expired` |
| `consumed_at`, `created_at` | TIMESTAMPTZ | |

Indexes: partial `(contact_wa_id, seq) WHERE consumed_at IS NULL`, and `(created_at)`.

### `runtime.consume_inbound_buffer(contact, message_id, force, max_hold_ms, fresh_seconds)`

One atomic call per buffered execution, after its wait:
1. `pg_advisory_xact_lock(7301, hashtext(contact))` — one consumer per contact; the two-int key space never collides with the router's single-bigint session lock.
2. Expire pending rows older than `fresh_seconds` (120): waits lost to an n8n restart are never absorbed later.
3. Return nothing if this message was already absorbed, or if a newer one is still waiting — unless `force`, or the group is older than `max_hold_ms`.
4. Otherwise mark every pending row consumed and return them; delete rows older than 2 days.

Verified on client1: a rolled-back transaction covering fresh, newest, already-absorbed, max-hold, force, stale and duplicate cases, then 5 concurrent race rounds in which each burst was absorbed exactly once.

## Tech debt to know about

~~The `v2-inventory-wizard` workflow currently reads **Google Sheets directly at runtime** (not the `automation.inventory` table).~~ **Resolved on client1 2026-09-11:** `Read Inventory` is a Postgres node on `automation.inventory` (including `use_type`). Tenants cloned from older exports may still read Sheets — check the wizard's `Read Inventory` node type before assuming either way.
