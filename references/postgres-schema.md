# Postgres `automation` schema

**This schema is identical for every agency on the platform.** It is not vertical-specific. The DDL below is the canonical source. New verticals do **not** modify these tables — they add views (`automation.v_<vertical>_*`) on top, or use the existing generic columns.

Source of truth: `C:\Desarollo\jperez\n8n\whatsapp-automation-claude\postgres-setup.sql`.

## Schema split

| Schema | Owner | Written by | Read by |
|---|---|---|---|
| `automation.*` | n8n workflows | router/wizards/persister | dashboard (SELECT only via `dashboard_app` role) |
| `dashboard.*` | dashboard app | dashboard | dashboard |

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

## Dashboard-side views (read-only consumers)

The dashboard reads only `automation.v_*` views (Drizzle-typed wrappers in `src/db/views.ts` of the dashboard repo). v1 ships:

- `v_daily_metrics`
- `v_contact_summary`
- `v_handoff_summary`
- `v_follow_up_queue`
- `v_flow_breakdown`

Adding a new vertical does not require new views unless the metric semantics change. New verticals get their differentiation from the **dashboard's `verticalConfig`** (intents, terminal flows, colors), not from the schema.

## Tech debt to know about

The `v2-inventory-wizard` workflow currently reads **Google Sheets directly at runtime** (not the `automation.inventory` table). The sync workflow exists and populates the table, but the wizard hasn't been switched over. When migrating, check whether the wizard JS still queries Sheets — if so, update it to query `automation.inventory` for performance + resilience.
