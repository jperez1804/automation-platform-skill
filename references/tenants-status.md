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
| `client1` | real-estate | **Live** (dashboard refresh 2026-06-01; **engine upgrades 2026-09-15**: post-handoff window, voice-note transcription, burst grouping, spoken answers to option lists — POC, first tenant with them) | `client1.botargento.com.ar` (n8n), `dashboard.client1.botargento.com.ar` | 2026-09-16 | See `reference-instance.md` + §Client1 engine upgrades + §Client1 dashboard refresh below |
| `plec` | architecture | **Live** (Bot v2.4 en prod, handoff via Meta template HSM, dashboard operativo · pendiente: landing page) | `plec.botargento.com.ar` (n8n), `dashboard.plec.botargento.com.ar` (dashboard) | 2026-05-29 | See §Plec Arquitectos below |
| `bot-argento-sales` | outbound-sales | **Live — CAMPAIGN 2 ACTIVE since 2026-08-11** (`arquitectura-norteoestecaba-2026-08`, IMAGE-header template `outreach_intro_img` w/ 3 buttons incl. "Quizás más adelante"→`later` pool, 233 recipients, 15/day, CABA+Norte+Oeste; benchmark: campaign 1 text 13.8% reply) | `ventas.botargento.com.ar` (n8n), `dashboard.ventas.botargento.com.ar` (dashboard) | 2026-08-11 | See §Bot Argento Sales below |
| `artbox` | outbound-sales (factories) | **Containers provisioned** (n8n + Postgres up, `automation.*` + `outreach.*` applied; DNS + Meta creds pending) | `artbox.botargento.com.ar` (n8n, DNS pending) | 2026-07-02 | See §ArtBox below |
| `tasty` | outbound-sales (growshops) | **Live** — campaign 3 `growshops-amba-2026-07` ACTIVE since 2026-07-12 (419 recipients, cap 15/day) | `tasty.botargento.com.ar` (n8n), `dashboard.tasty.botargento.com.ar` | 2026-07-12 | Dashboard latest + acciones de campaña habilitadas 2026-09-04 (inbox apagado). Workspace: `C:\Desarollo\jperez\TastyLivingSoil\Tasty Automation\` — full log in its `docs/ventas/infra-status.md` (no per-tenant section here yet) |
| `arka` | outbound-sales (clínicas · **España**) | **Live — REAL CAMPAIGN ACTIVE** (`clinicas-barcelona-2026-09`: 277 seeded, cap 15/day, window 10–12 Madrid L–V, first sends Mon 2026-09-07; flow v3 Veámoslo; all 8 workflows ACTIVE) | `arka.botargento.com.ar` (n8n), `dashboard.arka.botargento.com.ar` — dashboard latest + acciones de campaña habilitadas 2026-09-04 (inbox APAGADO, env pre-staged sin cablear) | 2026-09-04 | See §Arka Systems below |
| `aurelioski` | rental (**nuevo vertical** · ski, Bariloche) | **Discovery — propuesta FINAL lista para enviar** (PDF; setup $0 · $100k/mes · 1er mes 50%; mockup = flujo real: menú numerado 4 opciones + wizard botones); bot INBOUND; dolor: volumen de consultas | `aurelioski.botargento.com.ar` (propuesto; sin infra) | 2026-08-19 | See §Aurelio Ski below |

## Client1 engine upgrades — 2026-09-15 / 16

First tenant with the conversational upgrades (POC — Jonatan wants every functionality here before porting). Client1 has no `_src` workspace: the engine repo `whatsapp-automation-claude` is its source of truth. Runbooks and rollback ids: `MIGRATION-*-client1.md` and `_client1_backup/_versions.txt` in that repo; architecture in `whatsapp-automation.md` §Conversational upgrades.

| Date | Delivery | Router versionId | Persister versionId |
|---|---|---|---|
| 2026-09-15 | Post-handoff window | `06938789-1734…` | `7d408179-cca2…` |
| 2026-09-15 | Voice-note transcription | `13e80f2f-7905…` | `c1c57a06-be0a…` |
| 2026-09-15 | Burst grouping (+ `runtime` schema DDL) | `6e2ed6b0-28de…` | `88cbf3dd-88ae…` |
| 2026-09-15 | Spoken answers to option lists (smoke-test fix) | `2349373c-eaf5…` | — |
| 2026-09-16 | Deployer refactored to `patch-tenant-live.mjs` + `tenants.json` (no live change) | — | — |

- **Env / VPS 2026-09-15:** `OPENAI_API_KEY` rotated in `/opt/n8n/client1/.env` (the previous keys had been exposed on Bitbucket; Jonatan inactivated all old keys). The first transcription call returned `429 credit_balance_exhausted` until the OpenAI org was topped up. `n8n-client1` recreated with `--no-deps`. `.env` and its backups chmod `600` (was `664`).
- **Smoke test (real WhatsApp, 2026-09-15):** transcription correct, but "Tres habitaciones", "Quiero hablar con un asesor" and "Me gustaría un departamento" were rejected by the wizards → fixed the same day with sentence → option resolution in `Determine Route`. **Retest of that fix pending**, plus smoke tests for burst grouping and the post-handoff window.
- **Traffic reality:** a 30-day `lead_log` check showed 4 contacts and 0 real bursts (all quick follow-ups came after a bot reply). Grouping shipped for completeness of the POC, not demand.
- **Deploy/verify:** `node scripts/patch-tenant-live.mjs client1 <target>`; `verify` = 35 checks.

## Client1 dashboard refresh — 2026-06-01

Same image jump that Plec received progressively over 2026-05-22 → 2026-06-01. Client1 was running the pre-refresh image `c0f2b12e7a22` (built 2026-05-03) when Plec onboarded its visual refresh sequence; deferred for client1 until Plec validated the whole thing in production. Single pull + recreate the day after the last hotfix.

**Deployed image**: `sha256:9a70d0bd5d8b...` (built 2026-06-01, same SHA Plec runs).

**Brand-specific config preserved unchanged** in `/opt/n8n/client1/dashboard.compose.yml`:

| Var | Value |
|---|---|
| `CLIENT_NAME` | `Inmobiliaria` |
| `CLIENT_PRIMARY_COLOR` | `#3b82f6` (Tailwind blue-500) |
| `CLIENT_LOGO_URL` | `/logos/client.svg` |
| `VERTICAL` | `real-estate` |
| `AUTH_URL` | `https://dashboard.client1.botargento.com.ar` |
| `AUTH_EMAIL_FROM` | `no-reply@botargento.com.ar` |

The refresh's design was multi-tenant + theme-driven by construction — `#3b82f6` propagates as the chart-1 rank color (replacing Plec's `#facc15` yellow), active nav rail, focus rings, WindowToggle active state. Charts no longer reuse per-intent `IntentDef.color` hex (PR 4 ignores it by rank).

**Pages that 404 correctly on client1** (vertical-gated via `verticalConfig.features.{providersTab,laborPoolTab}` which only `architecture` sets):
- `/providers`
- `/labor-pool`

**Real-estate tier handling vs Plec**: client1 didn't receive a `handoffTargets[].priority` re-balance like Plec did 2026-05-27. Real-estate's `handoffTargets` in `botargento-dashboard/src/config/verticals/real-estate.ts` does NOT set a `priority` field on any entry → the `PRIORITY_BY_TARGET` map in the persister returns `3` (default tier T3 "Calificado") for every escalation. Badges on `/handoffs` will render uniformly T3 until the client requests a re-balance. **NOT a regression — operating as designed.**

**Migrations applied at boot**: dashboard container entrypoint ran `pnpm db:migrate` (3 files already applied: `0000_init.sql`, `0001_escalation_type.sql`, `0002_app_settings.sql`) and `pnpm db:verify-views` (7/7 required `automation.v_*` present).

**Smoke test passed 2026-06-01** by user: Panel KPIs, charts rank palette, /handoffs strip + table, /conversations row-as-Link, /conversations/[waId] thread (post PR 13.1 fix — thread on the wide column, rail on the 300 px), /follow-up tonal pills, /settings brand picker contrast meter, dark mode toggle.

**WABA topology (confirmed 2026-06-05):** client1's production number is `+54 9 11 2558-9302` on WABA
**BotArgento2 (`912244891288296`)**, app subscription `override_callback_uri → client1.botargento.com.ar`.
A second app (**Manychat**) is also subscribed to that WABA — legacy, candidate for cleanup. Don't add
other tenants' numbers to this WABA: overrides are per-WABA.

**Pending for client1** (intentional, no client request yet):
- ~~Meta template HSM for handoff notifications. Procedure documented in `whatsapp-automation-claude/MIGRATION-template-mode-client1.md`. Template was created and approved (`handoff_notification`, es_AR) but the persister patch + env vars haven't been applied yet — client1 still on text mode and subject to the 24h messaging window. Will be done in a separate session connected to client1's n8n via MCP.~~ **Outdated (noted 2026-09-16):** client1's live persister sends handoff notifications with the `handoff_notification` template. The 2026-09 follow-up notifications were built on template mode and had to respect its body rules (Meta #132018: no newlines in body parameters, header ≤ 60 chars).

---

## Plec Arquitectos

**Stage:** Live — bot v2.3 atendiendo WhatsApp, dashboard operativo con dashboards y tabs gated por vertical, tier matrix re-balanceada para reflejar la urgencia operativa real. Pending: emails reales de cada equipo (Plec sigue usando `jonatanperez1804@gmail.com` para todos los handoffs durante test phase) + landing page rebrandeada. Live snapshot en `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\n8n-implementation.md` §0 y `infra-status.md`.

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

### Updated 2026-05-22 (WABA + go-live)

- ✅ Meta WABA `1473386571198969` configured · phone number `1142902705574108` (+54 9 11 5139-8977) verified · `META_ACCESS_TOKEN` set in `/opt/n8n/plec/.env` · webhook override apuntando a `https://plec.botargento.com.ar/webhook/whatsapp/meta` (Tech Provider backend lo armó).
- ✅ SMTP credential `SMTP Handoff` wired to persister + error handler via Resend.
- ✅ Router activated. Bot recibiendo + respondiendo mensajes reales.
- ⏸️ Per-equipo numbers (`<TARGET>_WHATSAPP_NUMBER` × 7) y `ALERT_EMAIL_TO` siguen apuntando a Jonatan durante test phase. Hay que rotarlos a los datos operativos de Plec cuando ellos los confirmen.

### Updated 2026-05-23 (UX polish + handoff priority system)

- ✅ Interactive reply buttons en 4 prompts Yes/No (terreno, planos, obra_iniciada, planos aprobados).
- ✅ m² option list unificado en construccion + desarrollo (mismos 4 buckets que proyecto — la decisión cambió post 2026-05-27 para desarrollo, ver más abajo).
- ✅ Tier priority (T1/T2/T3/T4) end-to-end: schema column `automation.escalations.priority`, persister derivation via `PRIORITY_BY_TARGET` map, WhatsApp header markers (⚡ T1 / ⭐ T2 / 📋 T4), dashboard `/handoffs` badge + sort default (priority ASC, createdAt DESC), email body `Priority: T<n>` line.
- ✅ `handoff_summary_lines` wizard→persister contract: cada wizard emite resumen vertical-aware que el persister muestra en email + WhatsApp del asesor (en vez del bloque "Collected answers" genérico real-estate-coded).
- ✅ Opción 5 (Proveedores) simplificada — drop "Ya soy proveedor" path (era dead-weight UX, derivaba a Compras igual sin diferenciar).
- ✅ Persister `<UPPER>_WHATSAPP_NUMBER` env convention generic (era hardcoded a real-estate); `brandName` fallback chain (BRAND_NAME → ARCHITECTURE_BRAND_NAME → REAL_ESTATE_BRAND_NAME → 'Bot').

### Updated 2026-05-27 (re-balance tier matrix + Desarrollo restructure + drop "Estoy buscando")

- ✅ **Tier matrix flip** (acordado con cliente en reunión): T1 ⚡ ahora cubre architect + development + municipal (eran T3/T2). T2 ⭐ cubre technical + sales (toda Construcción). T3 vacío (fallback). T4 📋 sin cambio. Distribución del menú: ~61% T1, ~22% T2, ~17% T4. Aplicado a persister live + dashboard `architecture.ts`.
- ✅ **Opción 4 (Desarrollo)** reestructurada de 4 a 3 sub-opciones: rename "Invertir en proyectos" → "Invertir en pozo"; drop "Comprar una propiedad" (path que leía `automation.inventory` para seleccionar emprendimiento); reordenar "Desarrollar terreno" 3→2 y "Asociarse" 4→3. Sync workflow `v2.0 - Sync Inventory (Plec)` queda activo (la tabla sigue refrescándose por si vuelve el feature o se construye una vista de catálogo en el dashboard).
- ✅ "Desarrollar un terreno" — superficie del terreno cambia de option list (4 buckets) a texto libre — el cliente necesitaba capturar terrenos grandes con valor preciso (ej. "1850 m²", "una hectárea").
- ✅ Drop "[Estoy buscando]" del step `¿Ya tenés terreno?` (Opción 1).

### Updated 2026-05-28 (4 ajustes menores post-reunión)

- ✅ **Opción 1 — drop "Ya tengo planos"**: sub-menú baja de 4 a 3 opciones (idea / anteproyecto / cotizar). El path `planos` (que pedía descripción libre) se elimina. Quien tiene planos canaliza por "Quiero cotizar proyecto".
- ✅ **Opción 2.4 rename** "Cotizar obra" → "Reforma / Ampliación". Solo label, `value` interno `cotizar` se mantiene para no romper queries históricas. El flow downstream queda idéntico.
- ✅ **Opción 4.1 (Invertir en pozo)** → direct handoff. Se eliminaron los 2 steps de calificación (monto + zona). El equipo de Desarrollos califica el lead en la conversación directa.
- ✅ **Opción 1.3 (Cotizar proyecto)** → drop step `plazo`. Después de zona + m² va directo al handoff (era zona → m² → plazo → handoff; ahora zona → m² → handoff). El arquitecto puede preguntar plazo en la conversación humana si lo necesita.
- ✅ **Opción 5 + 6 — silenciar handoff**: drop email + WA + escalation row para nuevas altas de proveedores y mano de obra. El INSERT a `automation.providers` / `automation.labor_pool` sigue funcionando. El equipo Plec consulta `/providers` y `/labor-pool` en el dashboard (pull-only). Wizards modificados: `_src/proveedores.js` y `_src/mano-obra.js` con `handoff: false, sendEmailAlert: false` en el `finalize()` del `insertAndHandoff`.

### Updated 2026-05-29 (rotation de handoff numbers + table truncate + template mode handoffs)

**Bloque 1 — rotation operativa para go-live**:
- ✅ Rotated 7 `<TARGET>_WHATSAPP_NUMBER` env vars from Jonatan (`5491121911850`) to el número de operaciones de Plec (`5491140839109`). Aplicado via `sed -i` en `/opt/n8n/plec/.env`.
- ✅ `ALERT_EMAIL_TO` queda en `jonatanperez1804@gmail.com` como safety net (decisión explícita del cliente).
- ✅ Truncate de 5 tablas pre-go-live: `lead_log` (760→0), `escalations` (59→0), `session_memory` (5→0), `providers` (6→0), `labor_pool` (6→0). `inventory` preservada (3 filas reales del Sheet Plec).
- ✅ Backup del `.env` en `/opt/n8n/plec/.env.bak.<timestamp>` por rollback.

**Bloque 2 — Meta template HSM para handoffs**:
- ⚠️ **Issue descubierto pre-go-live**: con texto free-form la WhatsApp Cloud API silently descarta handoffs a números que no escribieron al business en 24h. El número de ops Plec (5491140839109) nunca había escrito → handoffs no llegaban.
- ✅ Template `handoff_notification` (Utility, `es_AR`) creado en Plec WABA (`1473386571198969`). Aprobado por Meta.
- ✅ Persister upgraded a dual-mode: si `$env.META_HANDOFF_TEMPLATE_NAME` está set → payload `type: 'template'`. Si no → fallback a `type: 'text'`. Commit `dea7efa` en engine repo, commit `2417656` en Plec Automation.
- ✅ Env vars seteadas en `/opt/n8n/plec/.env` + `docker-compose.yml`: `META_HANDOFF_TEMPLATE_NAME=handoff_notification` + `META_HANDOFF_TEMPLATE_LANG=es_AR`.
- ✅ Container recreado (`docker-compose up -d --force-recreate n8n`). Smoke test OK.
- 📘 **Pattern documentado** en `whatsapp-automation.md` §6 "Template-mode handoffs" — incluye las 2 restricciones de Meta encontradas (#132018 newlines en parámetros, #132005 header limit 60 chars) y el procedure step-by-step para onboardear futuros tenants a template mode.
- 🛠️ **Helpers nuevos** en `Plec Automation/scripts/`:
  - `patch-persister-template.mjs` — REST PUT para parchar persister live de un tenant.
  - `sync-persister-snapshot.mjs` — copia config del persister live al engine snapshot, para mantener `whatsapp-automation-claude/v2-persist-session-and-logs.json` alineado.

### Distribución actual del menú (post 2026-05-28)

Total sub-opciones: **17**. T1 ⚡ ≈ 59% (Opción 1.* + 3.* + 4.*) · T2 ⭐ ≈ 24% (Opción 2.*) · T4 📋 ≈ 18% (Opción 5 + 6.*).

### Pending (post go-live)

1. ~~**n8n + Postgres**~~ — done 2026-05-08
2. ~~**Dashboard**~~ — done 2026-05-19
3. ~~**WABA onboarding**~~ — done 2026-05-22
4. ~~**SMTP credential**~~ — done 2026-05-22
5. ~~**Architecture vertical config**~~ — done 2026-05-19
6. ~~**n8n wizards**~~ — done 2026-05-08, refinados continuamente
7. ~~**Providers + labor_pool dashboard tabs**~~ — done 2026-05-20
8. ~~**Handoff priority system**~~ — done 2026-05-23, re-balanceado 2026-05-27
9. **Per-equipo data** — rotar los 7 `<TARGET>_WHATSAPP_NUMBER` y `ALERT_EMAIL_TO` de placeholder (`5491121911850` / `jonatanperez1804@gmail.com`) a los datos reales que confirme Plec.
10. **Landing page clone** — Plec brand sobre `BotArgentoLandingPageRepo/landingpage`. No bloquea operación pero ayuda al onboarding orgánico de nuevos clientes.
11. **Google Sheets OAuth → Service Account** (tech debt) — la app OAuth quedó *unverified*, no escala bien. Migrar a Service Account cuando Plec haga go-live agresivo.
12. **`automation.v_architecture_*` views** (opcional) — solo si emergen métricas architecture-specific que las 7 views actuales no cubren.

### Helpers Plec-specific (en el repo `Plec Automation`)

- **`scripts/patch-wizard-live.mjs <proyecto|construccion|desarrollo>`** — genérico, parametrizable. Lee el `parameters.jsCode` del Code node `Run Wizard Step` desde el snapshot regenerado (`n8n/wizards/v2-<wizard>-wizard.json`) y hace PUT al workflow live de Plec n8n. Usa la whitelist de `ALLOWED_SETTINGS` para evitar el 400 "additional properties" del n8n REST. Requiere env var `PLEC_N8N_API_KEY`. Reemplaza al viejo `patch-desarrollo-live.mjs` que era hardcoded a un solo wizard. **Pattern reusable**: para cualquier tenant futuro que necesite parchear wizards en vivo, clonar este script cambiando el mapping `WIZARDS` con los IDs del tenant y el `N8N_BASE` URL.
- **`scripts/import-n8n.mjs`** — idempotent importer con manifest persistido (gitignored). Sube los 11 workflows de cero o los actualiza in-place. Usado en el provisionamiento inicial 2026-05-08.

### Vertical-specific notes (Plec, estado actual)

- **Menú principal (6 opciones)** — Proyecto arquitectónico / Construcción / Gestiones municipales / Desarrollo inmobiliario / Proveedores / Mano de obra. Documentado en §3 de `flow-v2.md`.
- **Opción 1 — Proyecto arquitectónico** (3 sub-opciones post 2026-05-28):
  - 1. Tengo una idea → terreno (Sí/No) → zona → m² → Arquitecto ⚡
  - 2. Quiero un anteproyecto → terreno (Sí/No) → zona → m² → Arquitecto ⚡
  - 3. Quiero cotizar proyecto → zona → m² → Arquitecto ⚡
- **Opción 2 — Construcción / Dirección de obra** (4 sub-opciones):
  - 1. Construir desde cero / 2. Continuar una obra / 4. Reforma / Ampliación → planos → m² → zona → Comercial ⭐
  - 3. Dirección de obra → obra_iniciada → Técnico ⭐ (fast-track)
- **Opción 3 — Gestiones municipales** (4 sub-opciones): permiso / regularización / final / consulta → municipio → planos_aprobados → Gestión municipal ⚡
- **Opción 4 — Desarrollo inmobiliario** (3 sub-opciones post 2026-05-28):
  - 1. Invertir en pozo → **direct handoff** (sin calificación) → Desarrollos ⚡
  - 2. Desarrollar un terreno → zona → superficie (texto libre) → estado_dominial → Desarrollos ⚡
  - 3. Asociarme para un desarrollo → zona → tipo_aporte → descripción → Desarrollos ⚡
- **Opción 5 — Proveedores** (alta-only, sin sub-menú): rubro → empresa → zona → INSERT `automation.providers` + Compras 📋
- **Opción 6 — Mano de obra** (2 sub-opciones): busco trabajo / ofrezco servicios → especialidad → zona → nombre → INSERT `automation.labor_pool` + RRHH 📋
- **Three platform databases** the bot writes: `lead_log` (conversations), `automation.providers` (Opción 5 → Conditional INSERT), `automation.labor_pool` (Opción 6 → Conditional INSERT). Dashboard tabs gated via `features.providersTab` / `features.laborPoolTab`.

### References for Plec

- Proposal: `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\flow-v2.html`
- Infra status doc (live): `C:\Desarollo\jperez\plecarquitectos\Plec Automation\docs\plec-arquitectos\infra-status.md`
- Plan that generated this state: `C:\Users\jperez\.claude\plans\can-you-check-the-stateless-origami.md`

## Bot Argento Sales

**Stage:** Live (Phase A complete, outbound idle since 2026-06-19 — see the 2026-07-30 entry) — the **outbound** companion to the inbound platform (the mirror image: it
cold-messages prospects with a Meta template that earns a reply, then the existing router + a `ventas`
pitch wizard qualify them in-window and hand off to Jonatan). Architecture + the Phase-B add-on recipe
live in `outbound-sales.md`. Dual purpose: Phase A = Jonatan's own client acquisition; Phase B = sold
to clients as an "outbound campaigns" add-on dropped into their existing tenant.

**Workspace:** `C:\Desarollo\jperez\bot-argento-sales\Sales Automation\` (mirrors the Plec layout).
**Subdomain:** `ventas.botargento.com.ar` → n8n (container `n8n-ventas`). Dedicated **sales WABA**.

### Confirmed at session 2026-06-04 (scaffold)

- Slug/path `bot-argento-sales` → `…\Sales Automation\`; outbound state in a new `outreach.*` schema
  (campaigns/recipients/suppression) — `automation.*` stays frozen (invariant #1). Reply
  conversations land in `automation.*` via the shared engine.
- Reuses engine JSONs (send / persist [already dual-mode template handoff] / error-handler) copied
  from `whatsapp-automation-claude`. Net-new: `v2-campaign-runner.json` + `v2-ventas-wizard.json` +
  the router's opt-out branch.
- ✅ Scaffolded + smoke-tested locally: `build.mjs` emits 3 valid JSONs; `ventas.js` steps
  entry→intro→rubro→hoy→demo→handoff (+ known-vertical skip + decline); `campaign-runner.js` emits
  valid Meta template payloads (cap/suppression gated in SQL); `seed-recipients.mjs` rejects rows
  without `opt_in_basis`.
- **Deviations from the original plan:** personalization uses a `Read Recipient` Postgres node, not a
  `session_memory` seed (TTL-proof); no `patch-persister-template.mjs` (copied persister already
  template-capable).

### Updated 2026-06-05 (VPS tenant provisioned)

- ✅ DNS A `ventas.botargento.com.ar` → `187.127.6.44`. **Zone lives at HostMar (`ns3/ns4.hostmar.com`)
  — the Hostinger MCP DNS tools return an empty zone for `botargento.com.ar`; records are managed in
  the HostMar panel.**
- ✅ `/opt/n8n/ventas/` provisioned (compose + `.env` mode 0600 + `postgres-setup.sql`).
- ✅ Containers `n8n-ventas` (n8nio/n8n:2.4.7) + `n8n-ventas-postgres` (postgres:16) up, healthy.
- ✅ TLS LE issued for `https://ventas.botargento.com.ar/`, valid → 2026-09-03. First ACME attempt
  failed (DNS not propagated at start) and stuck in Traefik's in-memory backoff — fixed with
  `docker restart traefik` (~3 s blip; plec + client1 verified healthy after).
- ✅ Schemas applied: `automation.*` (7 tables + 7 views) + `outreach.*` (campaigns/recipients/suppression).
- ✅ `ventas` appended to `/opt/scripts/tenants.txt` (safe: `update-dashboards.sh` skips tenants
  without `dashboard.compose.yml`).
- ⚠️ **Root access lesson:** `deploy` has no sudo and `/opt/n8n/` is root-owned. Hostinger MCP
  key-attach does NOT apply live to an existing VM; the working path is `VPS_setRootPasswordV1`
  (applies live) + password SSH as root. Rotated password stored in
  `…\Sales Automation\handoff\vps-root-access.md` (gitignored).
- ⏸️ n8n owner account not created yet (n8n 2.x owner wizard at first visit).
- ⏸️ `.env` placeholders pending: `META_ACCESS_TOKEN`, `META_PHONE_NUMBER_ID`, `SALES_CALENDAR_URL`,
  `VENTAS_WHATSAPP_NUMBER`.

### Updated 2026-06-05 (later session — import + wire complete)

- ✅ n8n owner account created by Jonatan; API key issued (stored in `…\Sales Automation\handoff\n8n-api-key.txt`).
- ✅ `VENTAS_WHATSAPP_NUMBER=5491121911850` set in `.env` (local + VPS) + container recreated.
- ✅ All 6 workflows imported via `import-n8n.mjs` (manifest persisted).
- ✅ **New helper `scripts/wire-n8n.mjs`** (REST-based, idempotent, no MCP needed — improvement over
  Plec's manual MCP wiring): creates the `Postgres Ventas` credential (`SMuNLLXrMffqrFyw`) and
  attaches it to all 12 Postgres nodes, wires the router's 3 executeWorkflow ids from the import
  manifest. Credential id persisted in `scripts/wire-manifest.json` (gitignored). Reusable for
  Phase-B client deployments.
- ✅ Error handler set as `settings.errorWorkflow` on the other 5 workflows (`set-error-workflow.mjs`).
- ✅ Verified via API: 0 Postgres nodes missing credentials, 0 unwired executeWorkflow nodes, all
  workflows **inactive by design** (router activates at WABA go-live; campaign-runner with the first campaign).
- 📘 **n8n 2.x public-API credential gotcha:** POST `/credentials` for type `postgres` requires
  `sshTunnel: false` to be present and the `ssh*` fields to be ABSENT (conditional allOf schema —
  including them errors with "prohibited type").

### Updated 2026-06-05 (third session — WABA creds live, TEST number)

- ✅ Jonatan completed embedded signup + activated ("published") all workflows.
- ✅ `META_VERIFY_TOKEN` rotated to Jonatan's value; webhook GET handshake verified live (200 +
  challenge echo at `/webhook/whatsapp/meta`).
- ✅ `META_ACCESS_TOKEN` + `META_PHONE_NUMBER_ID=1146399881891574` set + container recreated; token
  smoke-tested against Graph API.
- 🟡 **The onboarded number is a Meta TEST number** (`+1 555-990-2333`): max 5 pre-verified
  recipients, quality `UNKNOWN`. Good for E2E dev; a real dedicated AR number is REQUIRED before the
  first cold campaign. Token may be short-lived (verify ~24h later; durable = Tech Provider backend token).
- 🐛 **Smoke-test bug found+fixed**: rubro button label 'Arquitectura / Estudio' (22 chars) →
  Graph API `(#131009) Parameter value is not valid`. **Meta interactive button titles hard-cap at
  20 chars** (add to the #132018/#132005 list of Meta limits). Shortened to 'Arquitectura', all other
  labels audited ≤20, patched live via `patch-wizard-live.mjs ventas`.
- ⏸️ **Smoke test blocked mid-flow by Meta** `(#131037) needs display name approval`:
  `name_status=PENDING_REVIEW` for display name "Automatizaciones de Jonatan Perez" (set at
  onboarding). ALL sends blocked until Meta approves (intro/rubro/hoy went out before enforcement
  kicked in; wizard logic itself verified working through 3 steps).
- 📌 **Decision (2026-06-05): abandon the test number** — Jonatan will register a **real dedicated
  sales number** instead (avoids display-name review on a throwaway + the 5-recipient cap, and is
  required for campaigns anyway).
- ⚠️ **Near-miss (2026-06-05):** Jonatan first added the new number (`+54 9 11 2558-9239`,
  phone_number_id `1139408332586305`, `name_status=APPROVED`, `status=PENDING` because nobody called
  `/register`) to WABA **BotArgento2 (`912244891288296`)** — but that WABA hosts **client1's
  PRODUCTION number** (`+54 9 11 2558-9302`, quality Alta) and its app subscription has
  `override_callback_uri → client1.botargento.com.ar`. **Webhook overrides are per-WABA, not
  per-number** — repointing it would have broken client1 live. Compliance rule #1 (dedicated sales
  WABA) exists for exactly this. Also noted: **Manychat** is a second subscribed app on BotArgento2
  (legacy? candidate for cleanup).
- 📌 ~~Resolution: Option A (fresh WABA via embedded signup)~~ → **Actual resolution (2026-06-07):**
  Jonatan moved -9239 in Business Manager onto the existing **dedicated sales WABA**
  ("Automatizaciones de Jonatan Perez" `3920862298209294`, override already → ventas n8n, only the
  BotArgento app subscribed). Claude registered it manually via Graph
  `POST /{phone_number_id}/register` (the step Business-Manager-added numbers always lack).
- ✅ **Real sales number LIVE (2026-06-07):** `+54 9 11 2558-9239`, phone_number_id
  **`1189088647624468`** (changed from `1139408332586305` — **phone_number_id is per-WABA**; it
  changes when a number moves WABA). `status=CONNECTED`, `name_status=APPROVED`,
  `quality_rating=GREEN`. Two-step PIN set at registration → stored in
  `…\Sales Automation\handoff\waba-sales-number.md`. `META_PHONE_NUMBER_ID` swapped in `.env`
  (local + VPS) + container recreated.

### Updated 2026-06-07 (smoke test PASSED + templates submitted)

- ✅ **Full-flow smoke test passed on the real number** (intro→rubro→hoy→demo).
- ✅ Copy tweak: dropped the social-proof line from the intro greeting (rebuilt + live-patched).
- ✅ **Both templates created via Graph API** (`POST /{waba_id}/message_templates`) under the sales
  WABA, status `PENDING`: `handoff_notification` (Utility, `27499304549724179`, header {{1}} +
  4 body params, buttonless) + `outreach_intro` (Marketing, `1882014265822175`, 2 body params +
  opt-out footer).
- 📘 **New Meta gotcha:** template URL buttons may NOT contain WhatsApp deep links (`wa.me`) —
  error subcode `2388081` "No se permiten los enlaces directos a WhatsApp en los botones". Ventas'
  handoff template is therefore buttonless (body text `wa.me/{{2}}` is clickable anyway); the
  persister's `Prepare Handoff WA Notification` node was patched (local + live) to drop the button
  component. **Engine TODO:** make the button component env-conditional in
  `whatsapp-automation-claude`'s persister so buttonless tenants don't need a hand-patch.
- ✅ **Both templates APPROVED same day** (2026-06-07). `SALES_CALENDAR_URL` set (Google appointment
  schedule) + container recreated.
- ✅ **E2E handoff test PASSED (2026-06-07 13:01)**: lead from a third number ran
  intro→rubro→hoy→demo, got the calendar link, escalation row written
  (`ventas_demo_requested`), and the `handoff_notification` template landed on Jonatan's WhatsApp
  with all params rendered. **The inbound half of Bot Argento Sales is operational.**
- Note: handoff priority renders T3 (persister `PRIORITY_BY_TARGET` has no `ventas` entry → default
  3). Optional tweak: map `ventas → 1` to badge demo-requests as T1 ⚡.
### Updated 2026-06-09 (read-only campaigns dashboard built)

- **First use of the `campaignsTab` feature** (reusable, Phase-B-ready). `botargento-dashboard` gained an
  `outbound-sales` vertical + `features.campaignsTab` + a read-only `/campaigns` page (quality badge +
  KPI tiles + per-campaign funnel table + daily-sends chart). Pattern cloned from the `providersTab`.
- Outbound funnel data comes from new `outreach.v_*` views (`v_campaign_stats` / `v_outreach_overview`
  / `v_campaign_daily`) in the ventas DB. Quality rating via `outreach.quality_log` + `v_quality_current`,
  fed by a scheduled n8n Graph poll (`v2-quality-poll.json`, ACTIVE, every 6 h) — **Approach 2**: the
  dashboard stays pure-Postgres-read; n8n is the only thing talking to Meta. (Real-time
  `phone_number_quality_update` webhook branch deferred — needs the Meta field toggle + router surgery.)
- Grant: `migrations/0003_outreach_grants.sql` conditionally grants `dashboard_app` SELECT on
  `outreach.*` (no-op for client1/plec — guarded by `IF EXISTS schema 'outreach'`); applied as superuser
  by `provision-tenant.sh`. **Lesson:** `dashboard_app` is granted per-schema in `0000_init.sql`
  (automation only) — a new readable schema needs its own additive grant migration; never add
  `outreach.v_*` to the dashboard's `REQUIRED_VIEWS` (automation-only, boot-verified, would crash other tenants).
- ⏸️ Dashboard **container** not provisioned yet: needs DNS `dashboard.ventas.botargento.com.ar`, a logo
  asset, and `provision-tenant.sh ventas VERTICAL=outbound-sales`. Plan: `expressive-churning-hennessy.md`.
- ✅ **DNS moved to Cloudflare (2026-06-10) — subdomain cap gone, platform-wide.** The DonWeb legacy
  reseller plan capped subdomains at 5/account (not liftable; DonWeb only offered a ~$112k ARS
  Cloud-Server upsell — declined, since the need was DNS records, not compute). Resolved by moving the
  `botargento.com.ar` **zone to Cloudflare free** (unlimited records). NS at **nic.ar** changed to
  `julissa.ns.cloudflare.com` / `mark.ns.cloudflare.com`; **all records DNS-only (grey)** — Cloudflare
  is pure authoritative DNS, DonWeb still hosts email + root site (email verified post-migration). This
  **unblocks the whole platform** — subdomains are now free + unlimited, so any number of agencies can be
  onboarded. **⚠️ Migration gotchas to remember for future zones:** (1) Cloudflare's auto-scan imports
  only common/email names (mail/www/ftp/mx) and **silently skips custom subdomains** — the VPS records
  (client1/plec/ventas + dashboards) had to be added by hand or those tenants would have gone dark on
  cutover; (2) it defaults every record to **Proxied (orange)** — must flip all to **DNS only (grey)**
  or email/FTP break and Traefik's LE TLS breaks; (3) preserve DKIM + the **Resend** records
  (`resend._domainkey`, `send` MX/TXT) — dashboard magic-link auth depends on them; (4) `.com.ar` NS
  delegation is changed at **nic.ar**. (Propagated 2026-06-10; dashboard container provisioned same day.)
- ✅ **Dashboard container LIVE (2026-06-10):** `provision-tenant.sh ventas` (`VERTICAL=outbound-sales`)
  → `n8n-ventas-dashboard` running at `https://dashboard.ventas.botargento.com.ar` (LE cert ✓, first
  try), migrations 0000–0003 incl. the `outreach` grant, `dashboard_app` reads `outreach.v_*`
  (badge GREEN). 📘 **Provisioning gotcha:** `provision-tenant.sh` bash-`source`s the tenant n8n `.env`
  — **quote any multi-word value** (`BRAND_NAME="Bot Argento"`) or it dies with "Argento: command not
  found"; docker-compose strips the quotes so n8n still gets the bare value. Last step: Jonatan's
  magic-link login + eyeball `/campaigns`.
- Tech debt (v2): campaign controls (pause/cap/seed) from the dashboard — needs a separate writable role.

- ~~Pending (outbound half): remove test number `+1 555-990-2333` from the WABA → first campaign~~ —
  first campaign launched 2026-06-11 (see below).

### Updated 2026-06-11 → 2026-06-21 (first campaigns ran)

- ✅ **Campaign 1 `arquitectura-zonasur-2026-06` launched 2026-06-11** (87 architecture studios,
  `daily_cap=15`, template `outreach_intro`). Runner + quality-poll + reconcile all activated
  (`v2-outreach-reconcile.json` added 2026-06-10 to derive `replied`/`opted_out` funnel states —
  see `outbound-sales.md` §Funnel reconciliation).
- ✅ **Session TTL bumped 30min → 72h (2026-06-19)** after a live lead's 1h47m-delayed reply got
  dropped — `SESSION_MEMORY_TTL_MS=259200000`, compose rewired to read `.env` (was hardcoded).
  Detail in the workspace `infra-status.md`.
- ✅ **Campaign 2 `tasty-living-soils-demo-2026-06`** (2026-06-21): 1-recipient demo → replied →
  **converted: Tasty is now a live Phase-B tenant** (see §tenant index).

### Updated 2026-07-30 (live-state check — campaign 1 complete, outbound idle)

Verified against the live VPS (containers + Postgres), not just docs:

- ✅ Infra healthy: `n8n-ventas` / postgres / dashboard all up; **all 8 workflows ACTIVE**;
  quality poll firing on schedule, `v_quality_current` = **GREEN**.
- ✅ **Campaign 1 finished sending 2026-06-19.** Final funnel over 87 recipients: **12 replied
  (13.8%)**, 4 opted out (4.6%), 71 sent-no-reply. Suppression list: 6 numbers.
- 🟡 Campaign row still `status='active'` but **0 pending recipients — the runner has been starved
  since 2026-06-19**. Housekeeping: mark it `done`.
- ✅ Inbound half still working organically: last `lead_log` row 2026-07-25, last escalation
  2026-07-22 (23 total).
- 📌 **Phase A did its job; effort shifted to Phase B client sales** (Tasty live, ArtBox inbound
  live, Arka in discovery+). Bot Argento Sales is now the idle worked reference for outbound.
- ⏸️ **Two-way inbox** (`docs/ventas/two-way-inbox-plan.md`, 2026-07-01) remains **proposed, not
  started** — no code written.

### Pending (next sessions)

1. ~~**Provision VPS tenant**~~ — done 2026-06-05 (see above).
2. ~~**Sales WABA onboarding**~~ — done 2026-06-05 with a TEST number 🟡 → real number 2026-06-07.
3. ~~**Import + wire**~~ — done 2026-06-05 (see above).
4. ~~**Templates**~~ — both submitted + APPROVED 2026-06-07; `META_HANDOFF_TEMPLATE_NAME` set.
5. ~~**First campaign**~~ — `arquitectura-zonasur-2026-06` ran 2026-06-11 → 2026-06-19 (12/87 replied).
6. ~~`SALES_CALENDAR_URL` for the demo CTA~~ — set 2026-06-07.
7. **Second campaign** — runner is active but starved; needs a new CSV → `seed-recipients.mjs` →
   campaign row (next architecture batch or another vertical).
8. **Housekeeping** — set campaign 1 `status='done'`; remove test number `+1 555-990-2333` from the WABA.
9. **Two-way inbox** — decide whether to build (plan exists, feature-flagged `inboxTab`, Phase-B sellable).

### References for Bot Argento Sales

- Architecture + Phase-B recipe: `references/outbound-sales.md`
- Live state: `C:\Desarollo\jperez\bot-argento-sales\Sales Automation\docs\ventas\infra-status.md`
- Flow spec: `…\docs\ventas\flow-v2.md` · Compliance: `…\docs\ventas\outreach-compliance.md`
- Plan that generated this scaffold: `C:\Users\jperez\.claude\plans\i-think-we-should-linear-corbato.md`

## ArtBox

**Stage:** Containers provisioned — first **client sale of the outbound engine** (Phase B, but as a
fresh outbound-first tenant, not an add-on to an existing inbound tenant). Cold outreach to
**fábricas/industrias GBA Zona Sur** pitching uniforms/personalized staff merch. Dedicated line,
WABA onboarding done by Jonatan (embedded signup with the client).

**Workspace:** `C:\Desarollo\jperez\ArtBox\ArtBox Automation\`
**Subdomain:** `artbox.botargento.com.ar` → n8n (container `n8n-artbox`).
**Prospects ready:** `C:\Desarollo\jperez\scraping project\ArtBox\run_ZonaSur_2026-07-01\prospects-factories.csv`
— 315 checknumber-validated numbers (vertical `factories`), `opt_in_basis` blank pending a per-batch basis.

### Updated 2026-07-02 (VPS tenant provisioned)

- ✅ Pivot confirmed: cold outbound (bot-argento-sales clone), replacing the earlier warm-base
  seasonal-campaigns proposal (`docs/propuesta-campanas-temporada.md`, now superseded).
- ✅ `/opt/n8n/artbox/` created (root mkdir + chown via paramiko with the rotated root password from
  `bot-argento-sales/…/handoff/vps-root-access.md`) — compose + `.env` (0600) + `postgres-setup.sql`
  uploaded; local copies in `ArtBox Automation/n8n/compose/`.
- ✅ Containers `n8n-artbox` (n8nio/n8n:2.4.7) + `n8n-artbox-postgres` (postgres:16) up, healthy.
  Compose drops the legacy `N8N_BASIC_AUTH_*` vars (n8n 2.x ignores them).
- ✅ Schemas applied from the bot-argento-sales SQL (generic): `automation.*` (7 tables + 7 views) +
  `outreach.*` (4 tables + 4 views incl. quality_log).
- ✅ `artbox` appended to `/opt/scripts/tenants.txt`.
- ✅ **DNS + TLS live (2026-07-02):** A record added by Jonatan in Cloudflare; first ACME attempt had
  NXDOMAIN'd pre-propagation and stuck in Traefik's in-memory backoff — `docker restart traefik`
  fixed it (other tenants verified 200 after). LE cert valid → 2026-09-30; n8n answers HTTPS 200.
- ✅ **Meta creds live (2026-07-02):** the ArtBox number lives on the client's own WABA
  **"Matias Armolla" (`1681666796437018`)**, number **+54 9 11 6597-8419**, phone_number_id
  **`1213540318503648`**, display name "Productos Artbox de Matias Armolla",
  `status=CONNECTED` (already registered), `name_status=AVAILABLE_WITHOUT_REVIEW`,
  `quality_rating=UNKNOWN` (fresh). **The ventas container's `META_ACCESS_TOKEN` works for this WABA
  too** (same Tech Provider system-user token across the portfolio) — copied into
  `/opt/n8n/artbox/.env` + container recreated + Graph smoke-tested. Local `.env` synced back.
- ⚠️ **Webhook override NOT set yet** on the ArtBox WABA (BotArgento app subscribed, no
  `override_callback_uri`). Must be set to `https://artbox.botargento.com.ar/webhook/whatsapp/meta`
  (verify token = artbox `.env`'s `META_VERIFY_TOKEN`) **after** the router is imported + active,
  since the override POST fires the GET handshake immediately.
- ⏸️ `VENTAS_WHATSAPP_NUMBER` = Jonatan placeholder until ArtBox confirms the salesperson number.
- ~~⏸️ n8n owner account not created~~ ✅ **Owner + API key done (2026-07-03)** — key in
  `ArtBox Automation/handoff/n8n-api-key.txt`, verified against the REST API.

### Updated 2026-07-03/06 (workspace + flow doc + confirmed first message)

- ✅ Workspace scaffolded as a git repo mirroring bot-argento-sales (`docs/artbox/`,
  `n8n/wizards/_src/`, `scripts/wizards/`, `handoff/` gitignored).
- ✅ Client-facing flow doc `docs/artbox/flujo-campana-fabricas.md` + `.html` (WhatsApp-style
  mockups). Assistant script draft: qué necesitás → volumen → handoff — pending client validation.
- ✅ **First message confirmed with the client** (contact: Matías Armolla): "Hola, soy Matías de
  ArtBox. Hacemos productos personalizados, indumentaria y merchandising para empresas. ¿Te interesa
  conocer nuestros productos a un precio de preventa?" — **3 quick-reply buttons**:
  `Ver propuesta` (→ wizard) / `Puede ser más adelante` (**soft defer** — ack + end, NO suppression,
  reachable in future campaigns; needs a net-new defer branch in the router) / `No me interesa`
  (opt-out → suppression). All ≤25 chars. **Not yet submitted to Meta.**
- 📌 Live-state check 2026-07-12: still 0 workflows imported, 0 templates on the WABA, no webhook
  override — infra idle and healthy, waiting on the build phase.

### Updated 2026-07-12 (engine deployed — INBOUND HALF LIVE)

- ✅ Flow signed off by Jonatan; template gained an **image header** (photo per campaign via new
  `outreach.campaigns.header_image_url` column — applied live + in postgres-setup.sql).
- ✅ Engine cloned from bot-argento-sales into `ArtBox Automation` (git): `_src/artbox.js` wizard
  (necesidad → volumen → handoff target `ventas` T1, reason `artbox_lead_calificado`), router with
  **defer branch** (`puede ser más adelante` → ack, NO suppression) + opt-out branch, runner with
  IMAGE header support and **no body params** (confirmed template has none). Persister patched with
  an ArtBox `ventas` header label (fallback would have read "Nuevo handoff: ventas").
- ✅ 8 workflows imported + wired via scripts (0 missing creds / 0 unwired). **7 ACTIVE** — 📘 n8n
  2.x refuses to publish the router until its executeWorkflow targets are published; activate in
  dependency order. Campaign-runner deliberately inactive until the first campaign.
- ✅ Webhook override SET on WABA `1681666796437018` → artbox n8n; GET handshake verified
  (200 + challenge echo). **The inbound half is operational.**
- ✅ `handoff_notification` (Utility, ArtBox-branded, buttonless) submitted → id `4472845659666448`,
  status PENDING.
- ⏸️ Marketing template blocked on ArtBox's product photo (image header needs a sample upload).

### Pending (next sessions)

1. Smoke test from a third number (wizard + defer + opt-out + dedup).
2. On `handoff_notification` approval: set `META_HANDOFF_TEMPLATE_NAME=handoff_notification` in
   `.env` (local + VPS) + recreate the container.
3. Product photo from ArtBox (public HTTPS URL) → submit the Marketing template → on approval set
   `outreach.campaigns.header_image_url`.
4. Rotate `VENTAS_WHATSAPP_NUMBER` to the ArtBox salesperson.
5. Dashboard container (`dashboard.artbox.botargento.com.ar`, `VERTICAL=outbound-sales`).
6. First campaign: stamp `opt_in_basis`, seed the 315, **activate campaign-runner**, ramp 30–50/day.

## Arka Systems

**Stage:** Live (inbound half) — smoke-tested 2026-08-03, awaiting seed+pilot GO — **first
Spain-market tenant.** Client sale of the outbound engine (Phase B,
Tasty/ArtBox pattern). Arka Systems (arkasystems.es, Barcelona — Esteban Pérez & Harvey Bince)
sells AI automation (WhatsApp agents 24/7, voice, RAG); campaign cold-messages **clínicas de
Barcelona** (dental / fisioterapia / estética / oftalmología) pitching Arka's services, with their
own Voraldent dental-clinic case as social proof.

**Workspace:** `C:\Desarollo\jperez\arkasystems\ArkaSystems Automation\`
**Scraping provenance:** `C:\Desarollo\jperez\scraping project\ArkaSystems\` (run 2026-07-22)

### Confirmed at session 2026-07-27 (workspace + flow doc)

- ✅ Scraping delivered 2026-07-22: 1.040 clinics → 500 checknumber-validated → **277 confirmed
  WhatsApp leads** (dental 103, fisio 135, estética 31, oftalmo 8). Seed
  `handoff/prospects-clinicas.csv`, `opt_in_basis` blank pending RGPD wording with the client.
- ✅ Workspace scaffolded (mirrors Tasty layout; engine dirs are placeholders with READMEs).
- ✅ Client-facing flow doc `docs/ventas/flujo-campana-clinicas.md` + branded `.html`
  (WhatsApp mockups, BORRADOR v1 27/07/2026) — template draft `Ver cómo funciona` /
  `Quizás más adelante` (defer) / `No me interesa` (opt-out), wizard = 1 question
  ("¿Cómo gestionáis hoy las citas por WhatsApp?") → Voraldent proof + Agendar demo cta_url →
  handoff. Template spec in `docs/ventas/templates/outreach_intro.md` (**es_ES**).
- 📌 User decision: campaign 1 = **all 277** (4 categories, one campaign, ramped; category on
  each recipient row for per-category metrics).
- ⚠️ **ES deltas to respect at engine-clone time:** timezone **Europe/Madrid** (runner gating SQL
  + container TZ + dashboard `CLIENT_TIMEZONE`), locale `es-ES` (tuteo — no voseo), template lang
  `es_ES`, opt-out tokens `baja`/`stop`/`no me interesa`, `wa_id = 34` + 9 digits (no AR `9`).

### Updated 2026-07-28 (client feedback → flow doc v2)

- ✅ Arka sent their own copy for both messages, incorporated into the flow doc + template spec:
  - Template body v2 (signed Esteban, "presupuestos en 'me lo pienso'" hook) **with an IMAGE
    header** — creative pending from Arka. Engine consequence: the runner clone must be
    **ArtBox-lineage** (IMAGE header + `outreach.campaigns.header_image_url`).
  - Wizard question v2: "¿Qué le come más tiempo hoy a vuestra recepción?" → buttons
    `Responder mensajes` / `Confirmar citas` / pain-tailored step-2 reply + Agendar demo.
- ⚠️ Their third button `Perseguir presupuestos` = **22 chars > the 20-char interactive-button
  limit**; proposed `Seguir presupuestos` (19) — pending client confirmation.

### Updated 2026-07-30 (WABA live + templates submitted)

- ✅ Header image received (`assets/campana-clinicas-v2.jpeg`, 1200×628 64 KB, on spec) and
  embedded in the flow-doc HTML mockup. Flow doc gained the documented **step 3** (team alert
  with lead card mockup).
- ✅ **Arka WABA is live**: WABA `2857116591318282` (BM `807638368889424`), number
  **+34 613 79 32 10**, phone_number_id `1311525598700114`, CONNECTED/VERIFIED, name "Arka
  Systems", quality UNKNOWN. **The shared Tech Provider system-user token (app BotArgento)
  works against it** — details in workspace `handoff/waba-arka-number.md`.
- ✅ **Both templates submitted 2026-07-30 via Graph API, PENDING**: `outreach_intro`
  (Marketing **es_ES**, IMAGE header via resumable-upload sample, id `2103562077251490`) +
  `handoff_notification` (Utility es_ES, Arka-branded Tasty clone, id `887803953988703`).

### Updated 2026-07-31 — ✅ templates APPROVED + ALL client blockers closed

- ✅ Both templates APPROVED (verified via Graph; quality UNKNOWN, no sends yet).
- ✅ Client answers received: WABA **payment method configured** + number profile completed;
  `VENTAS_WHATSAPP_NUMBER=34671286513`; `SALES_CALENDAR_URL=https://calendar.app.google/znui2XQQBUH9YqBJ8`;
  send-time image → `https://botargento.com.ar/arka/campana-clinicas-v2.jpeg` (upload pending);
  `Seguir presupuestos` + step-2 approach confirmed (v1 per-pain drafts in flow doc §3);
  logo received (`assets/logo-arka.png`, needs SVG wrap for the dashboard).
- ✅ `opt_in_basis` wording **APPROVED by Arka same day** (interés legítimo art. 19 LOPDGDD) —
  stamp at seed time. **No client blockers remain** — everything left is build work (+ the
  image upload to botargento.com.ar/arka/ and the Cloudflare A record, both Jonatan's).

### Updated 2026-07-31 (engine clone DONE — simulated, not deployed)

- ✅ Engine cloned from ArtBox and adapted, all flows verified by local simulation: `arka.js`
  wizard (dolor → per-pain reply + cta_url Agendar demo → T1 handoff), router (Quizás-defer +
  ES opt-out tokens, es-ES copy), runner (IMAGE header + `{{1}}` body param, es_ES), compose
  slug `arka` **TZ Europe/Madrid** (SQL + gating swapped), persister patched (Clínicas header
  label + es_ES fallback). `handoff/arka.env` generated with real secrets; `assets/logo.svg`
  ready for the dashboard. 8 workflow JSONs built/copied; import ORDER verified.

### Updated 2026-07-31 (VPS tenant deployed — INBOUND HALF LIVE)

- ✅ Image hosted (botargento.com.ar/arka/…jpeg) + DNS A `arka` created (both Jonatan).
- ✅ `/opt/n8n/arka/` provisioned (root pw = **Tasty** handoff's `vps-root-access.md`, NOT the
  superseded bot-argento-sales one); containers up; schemas applied; `arka` in tenants.txt;
  TLS LE first try (valid → 2026-10-29).
- ✅ n8n owner + API key via REST (📘 2.4.x: POST /rest/api-keys REQUIRES the `scopes` array —
  fetch allowed list from /rest/api-keys/scopes). 8 workflows imported + wired (`Postgres Arka`,
  3 executeWorkflow ids, error workflow ×7) + `SMTP Handoff` Resend credential attached to
  persister/error-handler email nodes (📘 smtp schema: `secure:true` → `disableStartTls` must be
  ABSENT). **7 ACTIVE** in dependency order; campaign-runner off until campaign 1.
- ✅ Webhook override SET on WABA `2857116591318282` → arka n8n; handshake verified (challenge
  echo + 403 on wrong token). Secrets in workspace `handoff/` (arka.env, n8n-owner-arka.md,
  n8n-api-key.txt).

### Updated 2026-08-03 — SMOKE TEST COMPLETE, engine 100% validated

- ✅ Happy path ×2 (organic entry w/ intro; dolor button → per-pain reply + demo; T1 escalations;
  handoff template + email delivered). Post-handoff free-text behaves as designed.
- ✅ **Defer branch** live-verified: "Quizás más adelante" → route `defer`, friendly ack, NO
  suppression. ✅ **Opt-out branch**: "No me interesa" → route `optout`, confirmation, suppression
  row written. Test wa_id (Jonatan `5491121911850`) then DELETEd from suppression (session_memory
  also reset during testing). Quality GREEN, **TIER_250**, poll logging every 6h.

### Updated 2026-08-03 (dashboard LIVE)

- ✅ `https://dashboard.arka.botargento.com.ar` provisioned ("Arka Systems · Panel de
  reportes"): VERTICAL=outbound-sales, color `#d99b2f` (logo amber), TZ Europe/Madrid,
  locale patched es-AR→es-ES (script hardcodes es-AR), logo.svg mounted, migrations 0000–0003,
  7/7 views, `dashboard_app` reads `outreach.v_*` (GREEN badge data confirmed). Allowlist:
  Jonatan (admin) + hola@arkasystems.es (viewer). 📘 Gotchas: `provision-tenant.sh` runs ON
  the VPS (checks `/opt/n8n/<t>` locally; stage as `/tmp/dashrepo/{scripts,migrations}`);
  manual recreates MUST pass `--env-file dashboard.env` or `TENANT_DB_URL` loses its password
  (28P01 boot loop).

### Updated 2026-09-04 — REAL CAMPAIGN LAUNCHED (stage: Live)

- Flow v3 shipped 2026-09-03 (client change): dolor → per-pain reply + **Veámoslo** button →
  contact promise + IG + **Visitar la web** cta_url (arkasystems.es); **T1 handoff fires on the
  Veámoslo tap**. Calendar link dropped. Deployed via the **n8n-deployer agent** (40 sim checks,
  live patch). Test campaigns 1–4 all validated E2E (resets via the documented procedure).
- **Campaign 5 `clinicas-barcelona-2026-09` ACTIVE**: 277 seeded from the stamped CSV (0 skipped,
  category split verified), cap 15/day, window **10:00–12:00 Europe/Madrid, Mon–Fri**, image
  header. Launch pre-flight: quality GREEN TIER_250, templates APPROVED, suppression empty.
  First sends **Monday 2026-09-07 10:00** (activation happened after Friday's window).
  ~19 business days at cap 15; consider raising toward 30–50 after week 1 if GREEN.
  Kill switch: `status='paused'` on campaign 5.
- ✅ Dashboard redeployed to the latest inbox build (dashboard-deployer agent): image
  `dff4119f` → `f1cbed82` (commit `69ecf86`), gates green, `--env-file` respected, migration
  `0004_inbox_read_state` applied, smoke tests pass, other tenants untouched, school-WIP preserved.

### Pending (next sessions)

1. Monday ≥10:05 Madrid: verify first sends (`sent` counts, no `failed`), quality stays GREEN,
   replies flow `guided_arka_dolor → interes → handoff`, T1 alerts reach 34671286513.
2. Week-1 review with Arka (reply rate, per-category split) → raise cap toward 30–50 if GREEN.
3. Later: 2nd checknumber batch (540 landlines + metro area), other cities (Madrid/València).

### References for Arka Systems

- Flow doc: `…\ArkaSystems Automation\docs\ventas\flujo-campana-clinicas.md` (+ `.html`)
- Infra status: `…\ArkaSystems Automation\docs\ventas\infra-status.md`
- Scraping report (client-facing): `…\ArkaSystems Automation\docs\ventas\REPORTE_Relevamiento_Barcelona.md`
- Spain field-learnings: `references/botargento-scraping.md` §España / Barcelona

## Aurelio Ski

**Stage:** Discovery — rental de equipos de ski en **Bariloche**; primer tenant del vertical
**rental/turismo**. Bot **inbound** (no outbound). Dolor declarado: el volumen de consultas
diarias por WhatsApp compite con la atención en mostrador.

**Workspace:** `C:\Desarollo\jperez\aurelioski\Aurelio Ski Automation\`

### Confirmed at session 2026-08-18 (workspace + propuesta)

- ✅ Workspace scaffoldeado (convención estándar; engine dirs = placeholders con README).
- ✅ **Propuesta v1** en `docs/aurelio-ski/propuesta.md` — dolor→solución, flujo ejemplo,
  showcase de los 4 bots vivos como prueba, tabla de alcance, plan 3 semanas, **inversión en
  placeholders (Jonatan completa)**, CTA con demo pre-firma opcional.
- Slug propuesto `aurelioski`; es-AR; TZ AR. Pendientes clave en el `infra-status.md` del
  workspace: precio, número WhatsApp (nuevo vs migrado), vertical `rental` para el dashboard
  (intents draft: disponibilidad, precios, equipos/talles, horarios, seña/reserva), opcional
  portugués (turismo brasileño), timing vs temporada.

### Updated 2026-08-19 — propuesta FINAL (aprobada por Jonatan)

- ✅ Precios confirmados: **setup bonificado ($0) · $100.000/mes · primer mes 50% ($50.000)**.
- ✅ Versión HTML brandeada (patrón flow-doc Arka, acento dorado Bot Argento) + **PDF listo
  para enviar** (`Propuesta-AurelioSki-BotArgento.pdf`).
- ✅ Mockup corregido en revisión de Jonatan al **flujo real de la plataforma**: menú principal
  numerado (1 Alquiler de equipos · 2 Clases de ski · 3 Horarios y ubicación · 4 Otra
  consulta) → wizard con botones (equipos → personas → fecha) → resumen + notificación al
  equipo. **Ese menú es el draft de intents del vertical `rental`.**
- Próximo: Jonatan la envía → registrar fecha de envío acá para el follow-up. Si piden el
  demo pre-firma (CTA de la propuesta): wizard rental de 4-5 pasos en número de prueba.

## How to add a new tenant to this file

When a new agency starts onboarding, add:

1. A row in **Tenant index** (initial stage = `Discovery`).
2. A new `## <Tenant Name>` section with the same structure: confirmed facts, pending list, vertical-specific notes, references.
3. Update the per-tenant section as the tenant progresses through the pipeline. Never overwrite — strike old facts and add new dated entries.
