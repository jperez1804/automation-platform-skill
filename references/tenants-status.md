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
| `plec` | architecture | **Dashboard provisioned + features shipped** (pending WABA, SMTP, handoff data, landing) | `plec.botargento.com.ar` (n8n), `dashboard.plec.botargento.com.ar` (dashboard) | 2026-05-20 | See §Plec Arquitectos below |

## Plec Arquitectos

**Stage:** Dashboard provisioned + architecture vertical shipped + Phase 2 providers/labor-pool tabs live. Only WABA + SMTP + handoff data + landing page pending. Live snapshot in `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\n8n-implementation.md` §0 and `infra-status.md`.

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

### Updated 2026-05-19 (dashboard provisioning + architecture vertical)

- ✅ Vertical `architecture` shipped to `botargento-dashboard` (commit `5b4e91e`): `src/config/verticals/architecture.ts` with 6 intents (`proyecto_lead`/`construccion_lead`/`gestiones_lead`/`desarrollo_lead`/`proveedor_intake`/`mano_obra_intake`), 7 handoff targets, registered in `index.ts`.
- ✅ `provision-tenant.sh` patched to prompt `VERTICAL` (was hardcoded `real-estate`). Same commit.
- ✅ **CI release.yml unblocked** (commit `5865e37`): added `"packageManager": "pnpm@10.33.0"` to `package.json`. Was failing since 2026-05-15 because corepack auto-resolved to pnpm 11.x (needs Node 22.13+, but Dockerfile uses Node 20). Side effect: client1 now eligible to receive updates too.
- ✅ Script stdin-drain bug fixed (commit `ee03f77`): pre-flight `docker exec -i ... psql -c` dropped `-i` so piped input stops being consumed by docker.
- ✅ Dashboard provisioned: `dashboard.plec.botargento.com.ar` 307→/login, TLS LE valid, magic-link login probado por Jonatan, allowlist (jonatan admin + plec.arq viewer).

### Updated 2026-05-20 (Phase 2 dashboard tabs shipped)

- ✅ Schema backfill: `automation.providers` + `automation.labor_pool` + 9 indices + `v_providers` / `v_labor_pool` added to canonical `whatsapp-automation-claude/postgres-setup.sql` (commit `a66bcd0`). Applied idempotently to client1's Postgres too — same schema across every tenant, UI differentiation is what changes.
- ✅ `VerticalConfig.features` mechanism (commit `4cca5a0` on dashboard): optional `{ providersTab?: boolean; laborPoolTab?: boolean }` on each vertical config. Architecture opts into both; real-estate stays as-is.
- ✅ Pages `/providers` and `/labor-pool` live in Plec with filters (search/category-or-specialty/zone/status with 300ms debounce), pagination (50/page via URL params), CSV export. Each page + export route does `notFound()` if its feature flag is off.
- ✅ `REQUIRED_VIEWS` boot check extended to 7 views (`v_providers` + `v_labor_pool` added). Verified passing on Plec: `✓ All 7 required views present`.
- ✅ Sidebar + MobileNav icons added: `Truck` (providers), `HardHat` (labor-pool).

### Pending (in order)

1. ~~**n8n + Postgres**~~ — done 2026-05-08
2. ~~**Dashboard**~~ — done 2026-05-19
3. **WABA onboarding** — embedded signup + activate-webhook to `https://plec.botargento.com.ar/webhooks/whatsapp`
4. **SMTP credential + handoff data** — get from Plec, configure SMTP credential in n8n, add `META_*` and `<TARGET>_WHATSAPP_NUMBER`s to `/opt/n8n/plec/.env`, restart container, activate router.
5. ~~**Architecture vertical config**~~ — done 2026-05-19
6. ~~**n8n wizards**~~ — done 2026-05-08
7. ~~**Providers + labor_pool dashboard tabs**~~ — done 2026-05-20
8. **`automation.v_architecture_*` views** (optional) — only if architecture-specific metric queries warrant them (the existing 7 views may be enough)
9. **Landing page clone** — Plec brand on top of `BotArgentoLandingPageRepo/landingpage`
10. **Handoff config** — collect Plec's real emails/numbers per equipo (Arquitecto / Comercial / Técnico / Gestión / Desarrollos / Compras / RRHH + `alertas@plec.com.ar`)

### Vertical-specific notes

- **Menú principal (6 opciones)** — Proyecto arquitectónico / Construcción / Gestiones municipales / Desarrollo inmobiliario / Proveedores / Mano de obra. Documented in §3 of `flow-v2.md`.
- **Opción 1 sub-flows** (3 paths, fully step-by-step in §4 of `flow-v2.md`):
  - "Quiero diseñar mi casa" → terreno + zona + m² + nombre/contacto → Arquitecto
  - "Ya tengo un croquis" → zona + m² + descripción/archivo + nombre/contacto → Arquitecto
  - "No sé por dónde empezar" → idea + zona + presupuesto orientativo + nombre/contacto → Arquitecto
- **Opción 2 sub-flows:** Construir de 0 / Ampliar o remodelar (→ Comercial), Dirección de obra (→ Técnico, lead caliente).
- **Three platform databases** the bot writes: `lead_log` (conversations), `automation.providers` (Opción 5 → Conditional INSERT from wizard), `automation.labor_pool` (Opción 6 → Conditional INSERT from wizard). **Resolved 2026-05-20:** `providers` + `labor_pool` are now canonical platform tables present on every tenant (Phase 2 in `postgres-setup.sql`). Dashboard tabs are gated per vertical via `features.providersTab` / `features.laborPoolTab`.

### References for Plec

- Proposal: `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\flow-v2.html`
- Infra status doc (live): `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\infra-status.md`
- Plan that generated this state: `C:\Users\jperez\.claude\plans\can-you-check-the-stateless-origami.md`

## How to add a new tenant to this file

When a new agency starts onboarding, add:

1. A row in **Tenant index** (initial stage = `Discovery`).
2. A new `## <Tenant Name>` section with the same structure: confirmed facts, pending list, vertical-specific notes, references.
3. Update the per-tenant section as the tenant progresses through the pipeline. Never overwrite — strike old facts and add new dated entries.
