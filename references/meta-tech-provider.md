# Meta Tech Provider backend (embedded signup)

Source: `C:\Desarollo\jperez\n8n\botargento-backend`

Jonatan is a registered **Meta Tech Provider**. This backend brokers the **Embedded Signup** flow that lets a client onboard their own WhatsApp Business Account without leaving Jonatan's onboarding page. After signup it persists Meta identifiers, encrypts the access token, and supports a two-stage webhook activation that ultimately points Meta callbacks at the tenant's own n8n instance.

This backend is **control-plane only**. It does NOT process runtime WhatsApp messages — that is the tenant's n8n.

## Stack

Hono + TypeScript (strict, ES2022) + better-sqlite3 12.8.0 (WAL mode + foreign keys) + Drizzle ORM + Zod + pino + ULID. One Docker container on the Hostinger VPS with a named volume for `/data` (see **Deployment** below). Railway until 2026-10-24.

## Two-stage onboarding state machine

```
started ──▶ signup_completed ──▶ assets_saved ──▶ webhook_ready
                                                      │
                                                      └─▶ failed (any step)
```

### Stage 1: signup completion (synchronous, called from frontend)

1. Frontend `POST /api/meta/embedded-signup/sessions { organization_name }` → backend creates `onboarding_session` (status `started`)
2. Frontend launches Meta Embedded Signup popup via `FB.login({ config_id: META_CONFIG_ID })`
3. User completes Meta flow → Meta returns OAuth `code` (30-second TTL) + asset IDs (`waba_id`, `phone_number_id`, `business_id`) to the frontend
4. Frontend immediately `POST /api/meta/embedded-signup/complete { session_id, code, ... }` → backend:
   - Exchanges `code` for business integration token via `GET /oauth/access_token` (non-retryable, 30s TTL — must succeed first try)
   - Persists `meta_business_accounts`, `whatsapp_business_accounts`, `phone_numbers` (idempotent insert-or-get)
   - Encrypts token with AES-256-GCM, stores in `credentials` table
   - Calls `POST /{waba_id}/subscribed_apps` to subscribe app with **app-level default webhook**
   - Calls `POST /{phone_number_id}/register` to register the phone for messaging
   - Status → `assets_saved`

### Stage 2: webhook activation (admin-triggered, asynchronous)

1. Admin (agency staff) `POST /api/admin/onboarding/:id/activate-webhook { webhook_url, verify_token }` (gated by `X-Admin-Key` header)
2. Backend calls `POST /{waba_id}/subscribed_apps` again, this time with `override_callback_uri` + `verify_token` set to the tenant's own n8n endpoint (e.g., `https://client1.botargento.com.ar/webhooks/whatsapp`)
3. Status → `webhook_ready`. Meta will now route this WABA's webhooks to the tenant's n8n.

**Why two stages:** the embedded signup completion is non-retryable (30s code TTL), so it has to be fast and minimal. Webhook activation can wait — it's how you control when a tenant goes live, and it's per-WABA (not app-wide), so each tenant's n8n only sees its own customer's events.

## Embedded Signup version — v4 since 2026-10-07

Meta deprecates **Embedded Signup v2 on 2026-10-15**. The onboarding page (`BotArgentoLandingPageRepo/landingpage/v5/whatsapp.html` — the file that is live as `botargento.com.ar/whatsapp.html`; `landingpage/whatsapp.html` is the older style — published **by FTP**; repo on Bitbucket, `main` = `dc2045e`) moved to **v4** on 2026-10-07:

- **The version lives in the Facebook Login for Business configuration, not in code.** A configuration created with the **Products** step (WhatsApp Cloud API selected) is v4. Current one: **`1423827086618896`** (variation «Registro insertado de WhatsApp»; products Cloud API + Marketing Messages API; asset WhatsApp accounts with default Manage; permissions `whatsapp_business_management` + `whatsapp_business_messaging`). Old v2-era config: `1842361349779469` (rollback value). A third one, «BotArgento WhatsApp Signup» `1302011241803276`, exists with unknown origin — don't delete.
- The page reads `config_id` from the backend (`META_CONFIG_ID` in the VPS `backend.env`; `/api/meta/embedded-signup/config` is public and shows it) and sends `extras: { setup: {}, version: 'v4' }` — no `featureType`, no `sessionInfoVersion` (those are v2/v3). `version: 'v4'` is what Meta's own launcher sends. `solutionID`, if ever set, goes inside `setup`.
- **v4 reports user errors as `CANCEL` with `error_message`** (not `ERROR`); the page handles both. Message events carry **no `version` field** — you can't read the version from the result; the tell is the dialog showing the Marketing Messages terms (only the new config has that product).
- The `v25.0` in the dialog URL is the **SDK/Graph version** (`META_API_VERSION`), unrelated to the signup version. Moving to v26 is a separate, unhurried change.
- The **portfolio is chosen in step 2 «Activos comerciales»**, after the phone number — not on the first screen.
- **Meta's own launcher** (App Dashboard → Use cases → Conectar en WhatsApp → Administrador de registro insertado → «Lanzamiento del registro insertado») launches any config/version/feature type without our code — use it to tell "our bug" from "Meta's side".
- Backend needed **no code change**. The full signup (backend saves the assets) on v4 was not run end-to-end before publishing — first real client confirms it; if it fails, ask for the Session ID on screen.

## Coexistence (WhatsApp Business app + API on one number) — AVAILABLE in Argentina, verified 2026-10-13

A client keeps using the WhatsApp Business app on their number **and** the bot runs on the same number through the Cloud API. Verified end to end with the sales number `+5491165978398` (phone_number_id `1363953910136191`, WABA `1600788471522545`), connected to the ventas tenant on 2026-10-13. Meta support's claim that Argentina is unsupported was wrong (twice it recited the old exclusion list backwards; case `29343441661908513`). The config does not matter either: production config `1423827086618896` (with Marketing Messages) works.

**What triggers it:** `extras.featureType = 'whatsapp_business_app_onboarding'` on `FB.login`, with the same v4 config. Without the featureType an app number hits «Este número ya está registrado… desconéctalo» on the SMS screen — so the standard button is safe for app users, it just can't onboard them.

**The client's flow (v4 is "phone number first"):** «Crea uno nuevo» → type the app number → Meta recognises it and switches to Coexistence by itself (shows the app's business profile) → **pick the existing portfolio** (the step defaults to «create», which is how the test made a stray portfolio «Jonatan» `4012727335701166`) → scan the QR from the app (also sent as a WhatsApp message) → WABA name / time zone → terms → `FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING` with `phone_number_id`, `waba_id`, `business_id`. **If it asks for an SMS/call code, cancel**: the number wasn't accepted and verifying it would move it off the app. Requirements per Meta: app ≥ 2.24.17, number active in the app ≥ 7 days (a number created in the app the same day went to the SMS screen on 2026-10-07).

**What we ship (all live since 2026-10-14):**

| Layer | Where | Behaviour |
|---|---|---|
| Onboarding page | `landingpage/v5/whatsapp.html` (Bitbucket `main` `015411a`) | Second button «Ya uso la app de WhatsApp Business» adds the featureType; the FINISH handler accepts both events; `/complete` gets `signup_type: 'coexistence'`. |
| Backend | `src/routes/*` (`signup_type` enum `standard` \| `coexistence`, migration `0002_coexistence_signup`) | Coexistence skips `POST /{phone}/register` and calls `POST /{phone}/smb_app_data` (`smb_app_state_sync` + `history`) — allowed only within **24 h** of the signup. History arrives as webhooks and lands in `webhook_events`. Admin «import» (`/api/admin/*`) takes `signup_type` too. |
| Engine (n8n, ventas only so far) | `Sales Automation/scripts/coex/` (`coex-nodes.mjs`, `patch-coex-live.mjs`, `patch-handoff-sender-live.mjs`, `harness-coex.mjs`) | `smb_message_echoes` (the owner answering from the app) → `Pause On Echo`: `conversation_control` mode `human`, `taken_by whatsapp_app`, 12 h (`COEX_ECHO_PAUSE_HOURS`), renewed per echo, never shortens a manual takeover; the echo is logged as outbound `sent_by='human'`. `Determine Route` checks the pause **before** answering non-text content (a sticker mid-pause used to get «solo texto»). The inbox replies from the number the contact wrote to; the handoff template always goes out from `META_PHONE_NUMBER_ID` (the template lives on that WABA; #132001 otherwise). `history` / `smb_app_state_sync` payloads are ignored by the router. Limits: 20 msg/s, no groups. |

**Every new Coexistence client needs the engine part ported** (the landing page promises the 12 h pause): run the `scripts/coex/` patches against that tenant's router / inbox / persister via `ventas-deployer` or `n8n-deployer`, declare `COEX_ECHO_PAUSE_HOURS` if a different window is wanted, and create the handoff template on the new WABA or keep `META_PHONE_NUMBER_ID` on a WABA that has it.

**Still open:** subscribe `account_update` (disconnection arrives as `PARTNER_REMOVED`); history and contacts into the dashboard; first Coexistence onboarding of a real client (only our own number so far).

## Meta Graph API endpoints used

| Method | Endpoint | When | Service file |
|---|---|---|---|
| `GET` | `/oauth/access_token` | Stage 1 — exchange code for token | `src/services/meta-auth.ts` |
| `GET` | `/debug_token` | Optional — inspect token scopes/expiry (uses system user token) | `src/services/meta-auth.ts` |
| `POST` | `/{waba_id}/subscribed_apps` | Stage 1 (default webhook) and Stage 2 (override webhook) | `src/services/meta-waba.ts` |
| `POST` | `/{phone_number_id}/register` | Stage 1 — register phone for messaging | `src/services/meta-waba.ts` |

All Graph calls go through the shared `src/services/meta-graph.ts` fetch wrapper.

**Field-name discipline:** all Meta API field names match official docs exactly: `config_id`, `solutionID`, `waba_id`, `phone_number_id`, `override_callback_uri`, `verify_token`, `messaging_product`. Don't paraphrase — Meta's parser is strict.

## Backend webhook handling

`POST /api/webhooks/meta/whatsapp` is the **app-level** webhook for control-plane events (e.g., `account_update`):

- Verification: `GET ...?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...` returns the challenge.
- Receipt: events logged to `webhook_events` with idempotency key, marked `processed: false` for async handling (future).
- **Does NOT process runtime customer messages.** Those go directly to the tenant's n8n via the per-WABA override.

## Auth model

| Route prefix | Auth | Rate limit |
|---|---|---|
| `GET /health`, `GET /ready` | None | None |
| `GET /config`, `POST /sessions`, `GET /sessions/:id`, `POST /complete`, `POST /events` | None (public — needed for the onboarding popup) | IP-based |
| `GET /api/webhooks/meta/whatsapp`, `POST /api/webhooks/meta/whatsapp` | Verify token (Meta) | None |
| `GET /api/admin/*`, `POST /api/admin/*` | `X-Admin-Key` header (must match `ADMIN_API_KEY` env var) | None |

**Who logs in:**
- **Agency staff** (Jonatan + ops) hit admin endpoints with the X-Admin-Key (typically via a CLI or admin UI).
- **Clients** never log in to this backend — they only interact via the embedded signup popup.

## Database (9 tables, all under default schema)

| Table | Purpose | Key relationships |
|---|---|---|
| `organizations` | Each client | PK ULID |
| `onboarding_sessions` | Signup state machine | FK `organization_id`; tracks `meta_business_id`, `waba_id`, `phone_number_id` |
| `meta_business_accounts` | Meta business mapping | FK `organization_id`; unique on `meta_business_id` |
| `whatsapp_business_accounts` | WABA records | FK `organization_id`, `meta_business_account_id`; unique on `waba_id`; column `webhook_override_uri` holds the per-tenant webhook URL |
| `phone_numbers` | WhatsApp phone records | FK `organization_id`, `waba_id`; unique on `phone_number_id` |
| `credentials` | Encrypted tokens (AES-256-GCM) | FK `organization_id`; `credential_type` enum, `scopes` JSON, `expires_at` |
| `onboarding_events` | Frontend `WA_EMBEDDED_SIGNUP` payloads | FK `session_id`; raw event log (success/cancel/error) |
| `webhook_events` | Control-plane webhook log | Idempotent on `idempotency_key`, `processed` bool |
| `audit_logs` | State transition audit trail | `entity_type`, `entity_id`, `action`, `old_value`/`new_value` JSON |

DDL: `src/db/schema.ts` (Drizzle definitions) and `src/db/migrations/0000_complete_argent.sql` (raw SQL).

Connection: `src/db/client.ts` enables WAL mode + foreign keys at startup.

## Code organization (backend CLAUDE.md verbatim)

1. **One service per concern.** `meta-auth`, `meta-waba`, `onboarding`, `crypto` are separate files.
2. **Routes are thin.** Validate input, call service, return response. No business logic in routes.
3. **All Meta API field names match official docs exactly.**
4. **Never expose secrets in responses.** Admin endpoints return credential metadata only.
5. **Fail fast on env.** If a required env var is missing, crash at startup with a clear message.
6. **Max 250 lines per file.** Extract if longer.
7. **No barrel exports.** Import directly from source files.

## Non-negotiable rules

1. TypeScript strict mode. No `any`, no `ts-ignore`.
2. **Never store plaintext tokens.** Always encrypt with `crypto` service (AES-256-GCM).
3. Never return raw credentials in API responses. Metadata only.
4. Every status transition gets an audit log entry.
5. All Zod schemas defined and validated before service calls.
6. Meta field names match official docs exactly.
7. **Do not add webhook processing for runtime WhatsApp messages — that is handled by tenant n8n instances.**
8. SQLite WAL mode must be enabled on connection.
9. All timestamps are ISO 8601 strings.
10. CORS must be restricted to configured origins only.

## Environment variables

**Required:**
| Variable | Description |
|---|---|
| `META_APP_ID` | Facebook App ID |
| `META_APP_SECRET` | Facebook App Secret |
| `META_CONFIG_ID` | Facebook Login for Business `config_id` |
| `META_WEBHOOK_VERIFY_TOKEN` | Verify token for app-level webhook |
| `ENCRYPTION_KEY` | 32-byte hex for AES-256-GCM |
| `ADMIN_API_KEY` | Admin auth key (required in `X-Admin-Key` header) |

**Optional:**
| Variable | Default | Description |
|---|---|---|
| `META_API_VERSION` | `v25.0` | Graph API version |
| `META_SOLUTION_ID` | — | Only for multi-partner solution flow |
| `META_SYSTEM_USER_TOKEN` | — | For optional token debug/inspection |
| `DATABASE_PATH` | `./data/botargento.db` | SQLite file path |
| `CORS_ORIGINS` | `https://botargento.com.ar,...` | Comma-separated allowed origins |
| `PORT` | `3000` | Server port |
| `NODE_ENV` | `development` | `development` or `production` |
| `LOG_LEVEL` | `info` | pino log level |

## Deployment — Hostinger VPS since 2026-10-24

Moved off Railway after Railway's 2026-10-21 secret-store incident (workspace variables matched the
attacker's search pattern). The move doubled as a **full secret rotation**: new `ENCRYPTION_KEY`
(database re-encrypted with `scripts/rotate-encryption-key.mjs`), new `ADMIN_API_KEY`,
new `META_WEBHOOK_VERIFY_TOKEN`, Meta app secret reset. Railway project to be deleted after 2026-10-25.

| Thing | Value |
|---|---|
| Public URL | `https://api.botargento.com.ar` — Cloudflare **A record** → 187.127.6.44, DNS only. **Never existed before:** Railway was called by its generated URL directly. |
| VPS dir | `/opt/n8n/control-plane/` — `backend.compose.yml` + `backend.env` (0600, never in Git) |
| Container / image | `botargento-backend` ← `ghcr.io/jperez1804/botargento-backend:<BACKEND_TAG>` (`latest` or `sha-<commit>`), built by `.github/workflows/release.yml` on push to `main` |
| Data | volume `botargento_backend_data` → `/data/botargento.db`; migrations run at container start |
| Backups | nightly 03:00, `/home/deploy/backup-backend.sh` → `/home/deploy/backups/backend/` (14 kept) |
| Deploy | `ssh vps 'cd /opt/n8n/control-plane && docker-compose --env-file backend.env -f backend.compose.yml pull backend && docker-compose --env-file backend.env -f backend.compose.yml up -d backend'` |
| Agents | project-scoped in the repo: `backend-ops` (read-mostly) and `backend-deployer` (ship / rollback / one env key) |

**Who calls the API (update all three if the host ever changes again):**
1. Onboarding page `API_BASE` (`landingpage/v5/whatsapp.html`, FTP-published).
2. Meta App Dashboard → WhatsApp → Configuration: callback `https://api.botargento.com.ar/api/webhooks/meta/whatsapp` + verify token.
3. Anyone holding the admin key (`/api/admin/*`). Per-WABA webhook overrides point at tenant n8n domains, not here.

Gotcha: the auto-mode permission classifier blocks `docker-compose up` on the VPS as a production
deploy — hand the exact command to Jonatan to run with `!`.

## Reusable pieces (per-agency clone)

For a new agency the backend itself is **shared infrastructure** (one container on the VPS serves all tenants). What changes per agency is just data: a new `organizations` row, a new `onboarding_session`, a new WABA + phone, a new encrypted credential. The CORS_ORIGINS env var may need to be updated to allow the new agency's onboarding page domain.

## Where the deep architecture decisions live

- **`README.md`** — Quick start, env vars, API endpoints, onboarding flow diagram, VPS deployment, Meta app setup
- **`deploy/vps/MIGRATION.md`** — the Railway → VPS runbook as actually executed (2026-10-23/24), incl. the key-rotation script and rollback
- **`Feature-META_SOLUTION_ID.md`** — Detailed Meta integration docs, Embedded Signup contract (Facebook SDK, code exchange TTL), Tech Provider setup steps
- **`CLAUDE.md`** — code rules + non-negotiable rules (above)
