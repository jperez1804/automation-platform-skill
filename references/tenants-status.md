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
| `client1` | real-estate | **Live** (dashboard refresh PRs 1→13.1 deployed 2026-06-01 — same image as Plec) | `client1.botargento.com.ar` (n8n), `dashboard.client1.botargento.com.ar` | 2026-06-01 | See `reference-instance.md` + §Client1 dashboard refresh below |
| `plec` | architecture | **Live** (Bot v2.4 en prod, handoff via Meta template HSM, dashboard operativo · pendiente: landing page) | `plec.botargento.com.ar` (n8n), `dashboard.plec.botargento.com.ar` (dashboard) | 2026-05-29 | See §Plec Arquitectos below |
| `bot-argento-sales` | outbound-sales | **Containers provisioned** (n8n + Postgres + TLS live on VPS 2026-06-05; no WABA yet) | `ventas.botargento.com.ar` (n8n) | 2026-06-05 | See §Bot Argento Sales below |

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
- Meta template HSM for handoff notifications. Procedure documented in `whatsapp-automation-claude/MIGRATION-template-mode-client1.md`. Template was created and approved (`handoff_notification`, es_AR) but the persister patch + env vars haven't been applied yet — client1 still on text mode and subject to the 24h messaging window. Will be done in a separate session connected to client1's n8n via MCP.

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

**Stage:** Containers provisioned — the **outbound** companion to the inbound platform (the mirror image: it
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
- Pending (outbound half): remove test number `+1 555-990-2333` from the WABA → first campaign
  (`outreach.campaigns` row, architecture vertical, `template_name=outreach_intro`, `daily_cap=40` →
  seed recipients CSV with `opt_in_basis` via `seed-recipients.mjs` → activate `v2-campaign-runner`,
  ramp 30–50/day, watch quality rating).

### Pending (next sessions)

1. ~~**Provision VPS tenant**~~ — done 2026-06-05 (see above).
2. ~~**Sales WABA onboarding**~~ — done 2026-06-05 with a TEST number 🟡; swap to the real dedicated
   sales number + long-lived token before campaign go-live.
3. ~~**Import + wire**~~ — done 2026-06-05 (see above).
4. **Templates** — submit `outreach_intro` (Marketing) + `handoff_notification` (Utility) under the
   sales WABA; set `META_HANDOFF_TEMPLATE_NAME` once approved.
5. **First campaign** — `outreach.campaigns` row (architecture vertical), seed recipients, ramp 30–50/day.
6. `SALES_CALENDAR_URL` for the demo CTA.

### References for Bot Argento Sales

- Architecture + Phase-B recipe: `references/outbound-sales.md`
- Live state: `C:\Desarollo\jperez\bot-argento-sales\Sales Automation\docs\ventas\infra-status.md`
- Flow spec: `…\docs\ventas\flow-v2.md` · Compliance: `…\docs\ventas\outreach-compliance.md`
- Plan that generated this scaffold: `C:\Users\jperez\.claude\plans\i-think-we-should-linear-corbato.md`

## How to add a new tenant to this file

When a new agency starts onboarding, add:

1. A row in **Tenant index** (initial stage = `Discovery`).
2. A new `## <Tenant Name>` section with the same structure: confirmed facts, pending list, vertical-specific notes, references.
3. Update the per-tenant section as the tenant progresses through the pipeline. Never overwrite — strike old facts and add new dated entries.
