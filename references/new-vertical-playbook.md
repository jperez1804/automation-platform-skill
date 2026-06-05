# New-vertical playbook

How to plug a new agency / vertical into the platform end-to-end. The platform is designed so this takes hours, not weeks. Bot Argento (real estate) was the first vertical; the same recipe works for architecture, dental, gym, services, anything else where WhatsApp-first lead intake + qualification + handoff is the value prop.

## Mental model

What's **shared** (don't touch):
- Postgres `automation` schema (DDL frozen)
- n8n router / sender / persister / error handler / sync workflows
- Dashboard Next.js codebase (one image, deployed per tenant)
- Meta Tech Provider backend (one Railway deployment, multi-tenant)
- VPS topology (Hostinger VM, Traefik, per-tenant compose)
- CI/CD pipeline (GitHub Actions → GHCR → SSH deploy)

What's **per-vertical** (you write):
- A `src/config/verticals/<vertical>.ts` file in the dashboard repo
- A set of cloned wizard JSONs in n8n with a rewritten state machine inside the Code node
- An `automation.inventory` shape (rows in the same table; column semantics shift to fit the vertical)

What's **per-agency / per-tenant** (you configure):
- A new tenant directory `/opt/n8n/<clientN>/` with `dashboard.compose.yml` + `dashboard.env`
- A new Postgres database
- A new WABA + phone number (onboarded via the Meta Tech Provider backend)
- A new domain `dashboard.<clientN>.botargento.com.ar` (or another base — Traefik-routed)
- A landing page clone with new copy/colors/calendar link

## Per-agency workspace directory (step 0)

Before touching code, create the per-agency artifacts directory on Jonatan's laptop:

```
C:\Desarollo\jperez\<agency-slug>\<Agency> Automation\
├── docs/                  # proposal, infra-status.md, handoff docs
├── n8n/
│   ├── compose/           # docker-compose.yml + .env destined for /opt/n8n/<tenant>/
│   └── wizards/           # wizard JSON exports adapted for this vertical
├── dashboard/
│   ├── vertical/          # draft of <vertical>.ts before PR to the shared dashboard repo
│   └── tenant/            # tenant config (CLIENT_NAME, color, logo) + brand assets
├── landing/               # rebranded clone of BotArgentoLandingPageRepo/landingpage
└── handoff/               # emails / phone numbers / SMTP creds (sensitive)
```

Reference instance: `C:\Desarollo\jperez\plecarquitectos\Plec Automation\` (Plec Arquitectos).

This directory holds **agency-specific artifacts only** — never a fork of the platform code. The flow is:

- `n8n/compose/` is the staging area for the files that will end up at `/opt/n8n/<tenant>/` on the VPS (rsync or scp from here).
- `n8n/wizards/` holds JSON exports of vertical-adapted wizards before importing into the shared n8n instance.
- `dashboard/vertical/<vertical>.ts` is drafted here, then promoted via PR to `botargento-dashboard/src/config/verticals/`.
- `dashboard/tenant/` holds the agency's brand assets (logo SVG, palette spec) and the values that will become env vars at provision time.
- `landing/` is a clone of `BotArgentoLandingPageRepo/landingpage` rebranded for this agency.
- `handoff/` collects the team WhatsApp numbers + admin emails + SMTP creds. Sensitive — keep out of any public git remote.

## The 7-step recipe

### 1. Define the vertical

Decide:

- **Intent vocabulary** — the WhatsApp main menu options. For real estate it's `ventas`/`alquileres`/`tasaciones`/`emprendimientos`/`admin`/`otras`. For a hypothetical dental clinic: `appointment`/`quote`/`emergency`/`info`. For an architecture studio: probably `presupuesto`/`visita`/`consulta-tecnica`/`servicios`. Keep it short — WhatsApp menus over ~6 options confuse users.
- **Terminal flows** — which intents end in human handoff vs continue conversationally. (Real estate: tasaciones always handoff; ventas only handoff when the user picks a listing.)
- **Qualification fields** — what to collect before handoff. Map to existing `lead_log` columns where possible (`intent`, `target_zone`, `budget_amount`, `property_type`, `bedrooms`, `payment_mode`, `purchase_timing`); leave nullable when not applicable.
- **Handoff targets** — which internal teams receive notifications. Maps to `escalations.handoff_target` and per-target WhatsApp number env vars.

### 2. Add `src/config/verticals/<vertical>.ts` to the dashboard repo

Single file. Defines:
- Intent keys + display labels (Spanish unless overridden by `CLIENT_LOCALE`)
- Per-intent chart colors (hardcoded hex — domain meaning, not brand)
- Terminal flows set (which `lead_log.route` tokens count as "completed" for each intent's funnel)
- Handoff target labels — substring matches against `escalations.handoff_target` to map to human-friendly team names
- Attribution mode defaults
- Window options + comparison template
- **`features`** — opt-in to feature-gated UI: `providersTab` (`/providers`), `laborPoolTab` (`/labor-pool`). Omit when the vertical doesn't need them — defaults to "no extra features".

Use `src/config/verticals/real-estate.ts` (baseline, no features) or `architecture.ts` (both features enabled) as the template. Estimated time: ~1 hour. **Don't forget to register the vertical in `src/config/verticals/index.ts`** — the registry resolves `VERTICAL=<key>` against this map; an unregistered key throws at runtime even if the file exists.

Push, merge, build new image — same image now serves the new vertical.

**Intent key convention:** the `key` in each `IntentDef` is the literal value n8n writes to `lead_log.intent`. So if your wizard emits `intent: 'proyecto_lead'`, the vertical's IntentDef key must be `'proyecto_lead'` (not the display label). Get this wrong and the dashboard shows 0 counts even with traffic.

**Terminal routes are `lead_log.route` tokens, not `lead_log.intent` values.** The wizard emits a final `route` like `guided_proyecto_handoff` on the handoff turn; that token is what completion-rate UI matches against `terminalIntents[]`.

### 3. Adapt n8n wizards

Clone the wizard JSONs and rewrite the JS state machine inside each Code node. The router/sender/persister/error-handler stay untouched.

Steps per wizard:

1. Copy `v2-inventory-wizard.json` → `v2-<vertical>-wizard.json`
2. Open in n8n → edit the Code node → rewrite the `STEPS` array, the `switch (currentStep)` cases, and `buildPrompt()` calls to match the new vertical's flow
3. Update the router workflow (`v2-meta-receive-router.json`) `MENU` switch to call the new wizard for the corresponding menu choice
4. If your vertical reads from a different inventory shape, point the wizard at `automation.inventory WHERE source_sheet='<vertical>_<table>'` instead of Google Sheets

Test on a non-prod n8n before deploying to a tenant.

For Plec a richer pattern emerged: instead of editing JSON files by hand, keep the Code-node JS in `n8n/wizards/_src/*.js` files and have a small `scripts/wizards/build.mjs` generator embed them into the `v2-*.json` outputs. The JSONs become idempotent build artifacts; diffs in code review stay in the `.js` files (with syntax highlighting, linter, normal escaping). Worth replicating for any vertical that adds 3+ custom wizards.

#### Post-import wiring procedure

After importing wizards to a tenant's n8n, the credentials + `executeWorkflow` IDs + `errorWorkflow` setting need to be wired. **Don't paste JSONs through MCP one-by-one** — see `references/whatsapp-automation.md` § "Post-deploy wiring operations" for the proven recipe (bulk-import REST script + `n8n_update_partial_workflow` MCP for credential/ID patches + per-workflow `errorWorkflow` PUT loop).

### 4. Adapt `automation.inventory` usage

The DDL stays. Three options for fitting your vertical:

| Friction | Approach |
|---|---|
| **Lowest** | Reuse existing columns. Treat `property_type` → service category, `zone` → location/branch, `bedrooms`/`bathrooms` → leave NULL, `area_m2` → relevant numeric metric (or NULL). Title/description/price/URL columns work as-is. |
| **Medium** | Add a vertical-specific view on top: `CREATE VIEW automation.v_<vertical>_catalog AS SELECT listing_id, title, price, ... FROM automation.inventory WHERE source_sheet='<vertical>_*'`. The wizard reads the view, not the table. |
| **Highest** | Add a parallel `automation.<vertical>_inventory` table with a different shape. Drawback: the dashboard's existing `v_*` views won't pick it up — you'd need to extend dashboard views too. Avoid unless really necessary. |

The sync workflow (`v2-sync-inventory.json`) needs a small edit: point at the new tenant's Sheets ID via env var (or skip entirely if the new vertical doesn't sync from Sheets).

#### Sheet schema considerations (lessons from Plec 2026-05-09)

When the agency's Sheet has columns that don't match the platform's listing-shaped inventory, **don't push back on the agency's schema** — they know their domain. Adapt the sync workflow's `Build Sync SQL` Code node to map their columns onto inventory's. Two hard-learned rules:

1. **`automation.inventory` enforces NOT NULL on every text column** (`property_type`, `operation_type`, `zone`, `short_description`, `features`, `agent_name`, `title`, `listing_url`, `currency`, `status`, `listing_id`, `source_sheet`). For columns where the vertical has no semantic mapping, send **`''` (empty string), not `NULL`** — the platform's convention. Numeric columns (`price`, `bedrooms`, `bathrooms`, `area_m2`) are nullable and can stay `NULL`.
2. **Derive a stable `listing_id` from a Sheet column the agency controls.** Slugifying the title/name is fine (`'Torres del Sur' → 'torres-del-sur'`). The composite PK is `(listing_id, source_sheet)`, so as long as the agency doesn't rename a row in-place its identity survives across syncs. If they do rename, the slug changes → old row gets cleaned up (DELETE in the sync's NOT IN clause) and new one gets inserted. Tell the agency this up-front.

The Plec example (`name | link | initial_investment | currency | status` Sheet → inventory): see `C:\Desarollo\jperez\plecarquitectos\Plec Automation\n8n\wizards\_src\sync-inventory-build.js`.

#### Google Sheets credential — prefer Service Account over OAuth

For server-to-server Sheets reads (which is what the sync workflow is), **use a Service Account, not the OAuth2 user-flow credential**. Reasons:

- No browser popup, no consent screen, no test users to manage.
- No 7-day refresh-token expiry (a real problem with apps in Google's *Testing* mode).
- No "unverified app" warning when publishing.
- Audit trail in the Sheet shows the bot identity, not a human's.
- n8n's "Google Sheets OAuth2 API" credential **hardcodes scopes** including `spreadsheets` (sensitive, read+write) — you can't restrict to `spreadsheets.readonly` without using a different credential type entirely.

Setup (~10 min): GCP Console → IAM & Admin → Service Accounts → Create → generate JSON key → share Sheet with the SA email as Viewer → in n8n use **"Google Service Account API"** credential type → paste email + private key. Then in the sync workflow swap `credentials.googleSheetsOAuth2Api` for `credentials.googleApi`.

OAuth user-flow is acceptable only during dev iteration when ownership of the integration is temporarily Jonatan's gmail; migrate to SA before handing the agency the keys.

### 5. Provision the tenant

On Jonatan's laptop, in the dashboard repo:

```bash
./scripts/provision-tenant.sh <clientN>
```

The script (interactive, target ≤15 min):
- Verifies n8n + Postgres exist for that tenant on the VPS
- Pre-flight: checks that all `REQUIRED_VIEWS` (currently 7, including `v_providers`/`v_labor_pool` since 2026-05-20) exist in the tenant Postgres — fails fast otherwise
- Generates strong DB password + `AUTH_SECRET`
- Applies `dashboard.*` migrations to the tenant's Postgres
- Prompts for: `CLIENT_NAME`, `CLIENT_PRIMARY_COLOR`, `VERTICAL` (default `real-estate`), Resend credentials, allowlist of admin emails
- Generates `/opt/n8n/<clientN>/dashboard.compose.yml` + `dashboard.env` (mode 0600) on the VPS via SSH
- Pulls image from GHCR, starts the container
- Appends `<clientN>` to `/opt/scripts/tenants.txt` so future `tenant=all` deploys include it

After it finishes: dashboard is reachable at `dashboard.<clientN>.botargento.com.ar`, ready for first admin login (magic link via Resend).

**Driving the script non-interactively** (e.g. from CI, or with a heredoc): the script uses `read -rp` for inputs. The two `docker exec ... psql -c` calls in the pre-flight and the `primary_color` UPDATE intentionally **omit `-i`** so they don't drain piped stdin (this caused real bugs before the 2026-05-20 fix — the inputs would silently EOF and the script would exit with "CLIENT_NAME is required"). The remaining `docker exec -i` calls in the script keep `-i` because they pipe heredocs or files into psql.

**Logo placement:** drop the agency's `logo.svg` at `/opt/n8n/<clientN>/assets/logo.svg` (mode 644, deploy-owned) **before** running the script — the dashboard container mounts it read-only at boot, and a missing file makes the container fail to start. If the source is a PNG or another raster format, wrap it in an SVG with an embedded base64 `<image>` — the compose hardcodes `.svg`.

### 6. Onboard the client's WhatsApp Business Account via the Meta Tech Provider backend

1. Client visits the onboarding page → embedded signup popup → completes Meta flow
2. Frontend POSTs `/api/meta/embedded-signup/complete` to the backend → token exchange, asset persistence, app subscription with default webhook → status `assets_saved`
3. Agency staff (Jonatan or ops) hits `POST /api/admin/onboarding/:id/activate-webhook` (with `X-Admin-Key`) supplying `webhook_url=https://<clientN>.botargento.com.ar/webhooks/whatsapp` and a `verify_token`
4. Backend re-subscribes the app with the per-WABA `override_callback_uri` → status `webhook_ready`
5. Meta will now route this client's WhatsApp events to their own n8n. Test with a real message.

### 7. Brand the landing page

Clone `BotArgentoLandingPageRepo/landingpage` to a new directory (or git remote), then:

- Swap the `--color-primary`, `--color-accent`, `--color-bg` CSS vars to the agency's palette
- Replace copy in each section (hero, features, how it works, pricing, FAQ, about, CTA)
- Replace logo SVG, fonts (if changing from Sora/Geist), favicon
- Update the Calendar booking link + WhatsApp FAB number + `wa.me` prefilled message
- Update gtag tracking ID
- Deploy as static files (no build step)

For the architecture vertical specifically, lean on the existing skills `frontend-design`, `ui-ux-pro-max`, `brand`, and `design` for the copy + visual work — don't try to invent typography and colors from scratch.

## Required environment variables (per tenant)

**For n8n (the WhatsApp automation):**

| Variable | Required | Notes |
|---|---|---|
| `META_VERIFY_TOKEN` | yes | You choose; must match the value passed to `activate-webhook` |
| `META_ACCESS_TOKEN` | yes | The encrypted token from the Tech Provider backend's `credentials` table |
| `META_PHONE_NUMBER_ID` | yes | This tenant's WhatsApp phone number ID |
| `ALERT_EMAIL_TO` | yes | Where handoff + error emails go (per-agency) |
| `ALERT_FROM_EMAIL` | yes | SMTP sender |
| `META_GRAPH_VERSION` | no | Default `v22.0` |
| `SESSION_MEMORY_TTL_MS` | no | Default `1800000` (30 min) |
| `DEFAULT_ASSISTANT_LANGUAGE` | no | Default `es` |
| `<VERTICAL>_*` | no | Per-vertical overrides (currency, brand name, market name, sheet ID) |
| `<TARGET>_WHATSAPP_NUMBER` | no | Per-team internal notification numbers (e.g. `VALUATIONS_WHATSAPP_NUMBER`) |
| `OPENAI_API_KEY`, `OPENAI_MODEL`, `AI_CONFIDENCE_THRESHOLD` | no | Wired but not used in v2 wizards. Reserved for AI triage. |

**For the dashboard:**

| Variable | Required | Notes |
|---|---|---|
| `TENANT_DB_URL` | yes | Includes the `dashboard_app` user |
| `VERTICAL` | yes | Picks `src/config/verticals/<key>.ts` |
| `CLIENT_NAME` | yes | Header + email subject |
| `CLIENT_LOGO_URL` | yes | Logo path/URL |
| `CLIENT_PRIMARY_COLOR` | yes | Boot fallback for `--client-primary` |
| `CLIENT_TIMEZONE` | no | Default `America/Argentina/Buenos_Aires` |
| `CLIENT_LOCALE` | no | Default `es-AR` |
| `AUTH_SECRET` | yes | 32-byte hex |
| `AUTH_URL` | yes | Full external URL of this deploy |
| `AUTH_EMAIL_FROM` | yes | Resend-verified sender |
| `RESEND_API_KEY` | yes | Resend API key |

## Smoke test checklist (after provisioning)

1. Dashboard reachable at `https://dashboard.<clientN>.botargento.com.ar` (TLS auto-issued by Traefik)
2. Magic-link login works (Resend deliverability — check Resend dashboard for sent events)
3. First admin can promote others via `/settings` (or via SQL UPDATE for existing tenants)
4. Send a real WhatsApp message to the tenant's phone number → router fires → `automation.lead_log` row appears (verify via `ssh vps 'docker exec n8n-<clientN>-postgres psql -c "SELECT * FROM automation.lead_log ORDER BY id DESC LIMIT 5"'`)
5. Trigger a handoff → `automation.escalations` row appears + alert email arrives at `ALERT_EMAIL_TO`
6. Dashboard overview page shows the new lead within ~1 minute (Server Components, no caching)
7. CSV export works (rate-limited 10/min)
8. Force an error in n8n (disable a credential temporarily) → error handler logs to `escalations` with `escalation_type='workflow_error'` + alert email + fallback WhatsApp message to user

## Common pitfalls

- **Forgetting `tenants.txt`:** if the new tenant isn't in `/opt/scripts/tenants.txt`, future `tenant=all` deploys will skip it. Always confirm the provision script appended it.
- **Hardcoded Spanish strings:** rule #2 of the dashboard CLAUDE.md. New verticals must surface labels via `verticalConfig`, not JSX literals.
- **Writing to `automation.*` from the dashboard:** rule #1. The DB role enforces this; if you see a permission error, that's the error talking, not a bug. Move the write into the n8n persister instead.
- **Reusing the laptop SSH key for GitHub Actions:** keep `~/.ssh/id_ed25519` (laptop) and `~/.ssh/botargento_deploy` (Actions) split. Rotating one shouldn't lock the other out.
- **Skipping migrations on a fresh tenant:** the dashboard container's entrypoint (`scripts/container-entrypoint.sh`) runs migrations + view-compat checks at boot. If the required `automation.v_*` views don't exist on the tenant DB, the container fails fast — that's a feature, not a bug. Run `postgres-setup.sql` from the n8n repo first to create the base schema.

## Cross-references

- `references/dashboard.md` — vertical config + tenant config detail
- `references/whatsapp-automation.md` — wizard pattern + child-workflow contract
- `references/postgres-schema.md` — column-by-column reuse map across verticals
- `references/meta-tech-provider.md` — exact embedded signup + webhook activation flow
- `references/vps-deployment.md` — provisioning paths, SSH access, deploy gotchas
- `references/reference-instance.md` — Bot Argento as the worked example (don't copy its brand for a new agency!)
- `references/outbound-sales.md` — **Outbound add-on** (cold-outreach campaigns): onboarding it onto an existing tenant is in that file's §"Phase B — onboard the outbound add-on onto an existing tenant".
