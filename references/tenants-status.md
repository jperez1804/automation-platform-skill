# Tenants — onboarding status (per-agency state)

> **Purpose.** Track where each agency sits on the onboarding pipeline. This file is **state, not architecture** — it changes as tenants progress. Always **verify against the live VPS** (`ssh vps 'docker ps'`, `cat /opt/scripts/tenants.txt`) before acting on anything here. The architectural how-to lives in `new-vertical-playbook.md`; this file just records *who's where*.
>
> **Update protocol.** When a tenant moves from one stage to another, update its row + the per-tenant section. Don't delete history — strike-through old facts so the audit trail survives.

## Onboarding pipeline (the canonical stages)

1. **Discovery** — proposal in flight, no infra
2. **DNS reserved** — A records exist at the registrar, no containers
3. **Containers provisioned** — n8n + Postgres + dashboard up, TLS issued
4. **WABA active** — Meta embedded signup done, per-WABA webhook override applied, real WhatsApp messages flow
5. **Live** — vertical config + wizards + landing page shipped, client using it daily

## Tenant index

| Tenant | Vertical | Stage | Subdomains | Last update | Detail |
|---|---|---|---|---|---|
| `client1` | real-estate | **Live** | `client1.botargento.com.ar` (n8n), `dashboard.client1.botargento.com.ar` | 2026-05-02 | See `reference-instance.md` |
| `plec` | architecture | **Containers provisioned + n8n wired** (pending WABA + handoff data) | `plec.botargento.com.ar` (n8n), `dashboard.plec.botargento.com.ar` (not yet provisioned) | 2026-05-14 | See §Plec Arquitectos below |

## Plec Arquitectos

**Stage:** Containers provisioned + n8n fully wired + sync workflow active. Only WABA + customer handoff data + dashboard provisioning pending. Live snapshot in `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\n8n-implementation.md` §0.

### Confirmed at session 2026-05-04

- Vertical: **architecture** (new — not yet built into the dashboard).
- Subdomains decided (match canonical pattern):
  - `plec.botargento.com.ar` → n8n
  - `dashboard.plec.botargento.com.ar` → dashboard
- `provision-tenant.sh` lines 292/308 already produce the right hostname for `tenant=plec` — **no script edit needed**.
- VPS verified: `srv1545757` / `187.127.6.44`, 42 GB free, Traefik healthy, only `client1` deployed.

### Updated 2026-05-05

- ✅ DNS A records created at Donweb (`plec` and `dashboard.plec` → `187.127.6.44`, TTL 3600). Verified via `nslookup` from `8.8.8.8` and `getent hosts` from the VPS — both resolve correctly.
- TLS not yet issued (expected — no container on :443 to answer TLS-ALPN-01).

### Updated 2026-05-08 (n8n + Postgres deployed)

- ✅ `/opt/n8n/plec/` provisioned on VPS (compose + .env + postgres-setup.sql).
- ✅ Containers `n8n-plec` (n8nio/n8n:2.4.7) + `n8n-plec-postgres` (postgres:16) running, healthy.
- ✅ TLS LE issued for `https://plec.botargento.com.ar/`, valid → 2026-08-06.
- ✅ Schema `automation.*` (7 tables + 7 views, including Phase 2 providers + labor_pool) bootstrapped.
- ✅ `plec` added to `/opt/scripts/tenants.txt`.
- ⚠️ n8n 2.x ignores basic auth env vars — used user management for owner creation.
- ⚠️ VPS uses `docker-compose` v2.27 (binary with hyphen), not the `docker compose` plugin.

### Updated 2026-05-14 (n8n wiring + sync e2e tested + active)

- ✅ All 11 workflows (3 engine + 6 wizards + sync + router) imported via REST script (`scripts/import-n8n.mjs` in the agency workspace; idempotent with manifest persistence).
- ✅ `Postgres Plec` credential (`6RG53rnCi0KRqixa`) attached to 13 nodes across 7 workflows via MCP `n8n_update_partial_workflow`.
- ✅ Router's 8 `executeWorkflow` nodes wired with the right `workflowId`s.
- ✅ Error handler set as the per-workflow `settings.errorWorkflow` on the other 10 workflows. (No global error workflow setting in n8n's API — must be set per-workflow.)
- ✅ Google Sheets OAuth credential (`AM0j0JTGLxj4iCRJ`) created via UI (OAuth flow can't be automated). App published in *unverified* state with hardcoded n8n scopes (`drive.file` + `spreadsheets`). **Tech debt: migrate to Service Account** (see Plec n8n-implementation.md §13).
- ✅ Sync inventory workflow tested end-to-end: insert (3 emprendimientos), update in-place (status change), cleanup DELETE on Sheet row removal. **Activated** (cron every 15 min).
- ✅ **Sheet schema mismatch resolved** — Plec's "emprendimientos" Sheet has columns `name | link | initial_investment | currency | status`, distinct from the platform's listing-shaped inventory. Mapping established in `_src/sync-inventory-build.js`. **Lesson:** the platform's `automation.inventory` schema enforces `NOT NULL` on all text columns; verticals that don't fill some of them must send `''` (empty string), not `NULL`. Numeric columns (`bedrooms`/`bathrooms`/`area_m2`) are nullable.
- ⏸️ Router still inactive — waiting on SMTP relay credential, `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, the 7 `<TARGET>_WHATSAPP_NUMBER`s, `ALERT_EMAIL_TO`.

### Pending (in order)

1. ~~**n8n + Postgres**~~ — done 2026-05-08
2. **Dashboard** — `./scripts/provision-tenant.sh plec` from `botargento-dashboard`
3. **WABA onboarding** — embedded signup + activate-webhook to `https://plec.botargento.com.ar/webhooks/whatsapp`
4. **SMTP credential + handoff data** — get from Plec, configure SMTP credential in n8n, add `META_*` and `<TARGET>_WHATSAPP_NUMBER`s to `/opt/n8n/plec/.env`, restart container, activate router.
5. **Architecture vertical config** — `src/config/verticals/architecture.ts` (clone `real-estate.ts`)
6. ~~**n8n wizards**~~ — done 2026-05-08 (6 wizards + router + sync, all in `n8n/wizards/`)
7. **`automation.v_architecture_*` views** — over the shared `automation.inventory` table
8. **Landing page clone** — Plec brand on top of `BotArgentoLandingPageRepo/landingpage`
9. **Handoff config** — collect Plec's real emails/numbers per equipo (Arquitecto / Comercial / Técnico / Gestión / Desarrollos / Compras / RRHH + `alertas@plec.com.ar`)

### Vertical-specific notes

- **Menú principal (6 opciones)** — Proyecto arquitectónico / Construcción / Gestiones municipales / Desarrollo inmobiliario / Proveedores / Mano de obra. Documented in §3 of `flow-v2.html`.
- **Opción 1 sub-flows** (3 paths, fully step-by-step in §4 of `flow-v2.html`):
  - "Quiero diseñar mi casa" → terreno + zona + m² + nombre/contacto → Arquitecto
  - "Ya tengo un croquis" → zona + m² + descripción/archivo + nombre/contacto → Arquitecto
  - "No sé por dónde empezar" → idea + zona + presupuesto orientativo + nombre/contacto → Arquitecto
- **Opción 2 sub-flows:** Construir de 0 / Ampliar o remodelar (→ Comercial), Dirección de obra (→ Técnico, lead caliente).
- **Three platform databases** the bot writes: `lead_log` (conversations), `providers` (Opción 5 → `automation.providers` insert), `labor_pool` (Opción 6 → `automation.labor_pool` insert). The latter two **may need new tables** — flag for review against the platform invariant "no new base tables, only views". Likely solution: store both as rows in `automation.inventory` with `source_sheet='plec_providers'` / `'plec_labor_pool'`, then expose via views.

### References for Plec

- Proposal: `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\flow-v2.html`
- Infra status doc (live): `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\infra-status.md`
- Plan that generated this state: `C:\Users\jperez\.claude\plans\can-you-check-the-stateless-origami.md`

## How to add a new tenant to this file

When a new agency starts onboarding, add:

1. A row in **Tenant index** (initial stage = `Discovery`).
2. A new `## <Tenant Name>` section with the same structure: confirmed facts, pending list, vertical-specific notes, references.
3. Update the per-tenant section as the tenant progresses through the pipeline. Never overwrite — strike old facts and add new dated entries.
