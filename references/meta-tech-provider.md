# Meta Tech Provider backend (embedded signup)

Source: `C:\Desarollo\jperez\n8n\botargento-backend`

Jonatan is a registered **Meta Tech Provider**. This backend brokers the **Embedded Signup** flow that lets a client onboard their own WhatsApp Business Account without leaving Jonatan's onboarding page. After signup it persists Meta identifiers, encrypts the access token, and supports a two-stage webhook activation that ultimately points Meta callbacks at the tenant's own n8n instance.

This backend is **control-plane only**. It does NOT process runtime WhatsApp messages — that is the tenant's n8n.

## Stack

Hono + TypeScript (strict, ES2022) + better-sqlite3 12.8.0 (WAL mode + foreign keys) + Drizzle ORM + Zod + pino + ULID. Deployed on Railway with persistent `/data` volume.

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

## Reusable pieces (per-agency clone)

For a new agency the backend itself is **shared infrastructure** (one Railway deployment serves all tenants). What changes per agency is just data: a new `organizations` row, a new `onboarding_session`, a new WABA + phone, a new encrypted credential. The CORS_ORIGINS env var may need to be updated to allow the new agency's onboarding page domain.

## Where the deep architecture decisions live

- **`README.md`** — Quick start, env vars, API endpoints, onboarding flow diagram, Railway deployment, Meta app setup
- **`Feature-META_SOLUTION_ID.md`** — Detailed Meta integration docs, Embedded Signup contract (Facebook SDK, code exchange TTL), Tech Provider setup steps
- **`CLAUDE.md`** — code rules + non-negotiable rules (above)
