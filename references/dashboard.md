# Multi-tenant dashboard

Source: `C:\Desarollo\jperez\n8n\botargento-dashboard`

Per-tenant analytics portal. One Docker container per tenant at `dashboard.<clientN>.botargento.com.ar`. Each tenant has their own Postgres (with both `automation.*` and `dashboard.*` schemas). The dashboard is read-only against `automation.*` and writes only to `dashboard.*`.

## Stack

Next.js 15 (App Router) + TypeScript strict + Tailwind CSS v4 + shadcn/ui + Recharts + TanStack React Table + Drizzle ORM + Postgres + Auth.js v5 (Resend magic link) + Docker + Traefik. pnpm. Dockerfile multi-stage (deps → build → runtime).

## Directory layout

```
src/
├── app/
│   ├── (auth)/                 Public: login, verify magic link
│   ├── (dashboard)/            Protected: overview, conversations, handoffs, follow-up, settings
│   └── api/                    Route handlers: auth callback, CSV exports, settings updates
├── components/
│   ├── dashboard/              Page-specific (KPI cards, charts, tables, timelines)
│   ├── layout/                 Shell (sidebar, header, branding)
│   └── ui/                     shadcn primitives
├── config/
│   ├── tenant.ts               Runtime config from CLIENT_* env vars
│   └── verticals/              Pluggable domain logic — v1 ships real-estate.ts
├── db/
│   ├── client.ts               Drizzle + Postgres client
│   ├── schema.ts               dashboard.* tables (allowed_emails, audit_log, app_settings, magic_link_tokens)
│   └── views.ts                Typed wrappers for automation.v_* views
├── lib/
│   ├── auth.ts                 Auth.js config + Resend integration
│   ├── env.ts                  Zod-validated env at boot
│   ├── queries/                ALL SQL lives here (metrics, intents, contacts, handoffs, follow-up)
│   ├── role-guard.ts           requireRole("admin") for privileged routes
│   └── logger.ts, csv.ts, date.ts
├── middleware.ts               Auth guard for (dashboard)/* routes
└── proxy.ts                    Next 16 proxy config
migrations/                     SQL migrations for dashboard.* (applied at container start)
scripts/
├── provision-tenant.sh         First-time client onboarding runbook
├── update-dashboards.sh        On VPS — pulls image, restarts containers
├── seed-dev.ts                 14 days of fake lead data
├── verify-view-compat.mjs      Boot check: required automation.v_* views exist
└── container-entrypoint.sh     Runs migrations + view verification at boot
```

## The 10 non-negotiable rules (copy from dashboard CLAUDE.md)

1. **The dashboard never writes to `automation.*`.** DB role `dashboard_app` has SELECT-only. Any insert/update/delete attempt is a bug.
2. **No hardcoded Spanish strings in JSX.** All UI text comes from `verticalConfig` or `tenantConfig`.
3. **No `process.env.X` in feature code.** Read through validated config modules (`src/config/tenant.ts`, `src/config/env.ts`).
4. **Every page query is a Server Component.** Never fetch data from a Client Component.
5. **Every auth-sensitive action is logged to `dashboard.audit_log`.** Logins, denials, exports, theme updates, role denials.
6. **Magic link tokens are SHA-256 hashed before storage.** Never plaintext, never logged.
7. **Migrations are additive only.** No `DROP COLUMN` or destructive changes without a multi-deploy migration plan.
8. **Max 300 lines per component file.** Extract when larger.
9. **All env vars validated with Zod at boot.** Container fails fast on misconfiguration, not at request time.
10. **No secrets in Git, ever.** `.env*` is in `.gitignore`. Secrets live in `/opt/n8n/<clientN>/dashboard.env` on the VPS (mode 0600).

## Key patterns

### Vertical config (`src/config/verticals/<vertical>.ts`)

Single file per vertical. Defines:
- Intent vocabulary (e.g., for real-estate: `ventas`, `alquileres`, `tasaciones`, `emprendimientos`, `admin`, `otras`)
- Terminal flows (which intents end in handoff vs continue)
- Per-intent chart colors (hardcoded hex — these are domain-meaning colors, NOT brand colors)
- Attribution modes (last-touch / first-touch / any-touch)
- Locale-specific labels for the UI

`VERTICAL=<key>` env var picks which file to load. Adding a new vertical = one new file (~1 hour). v1 ships `real-estate.ts`.

### Tenant config (`src/config/tenant.ts`)

Read at runtime from `CLIENT_*` env vars:

| Variable | Purpose |
|---|---|
| `CLIENT_NAME` | Header + email subject |
| `CLIENT_LOGO_URL` | Path or URL to tenant logo |
| `CLIENT_PRIMARY_COLOR` | CSS accent + chart primary |
| `CLIENT_TIMEZONE` | IANA tz; default `America/Argentina/Buenos_Aires` |
| `CLIENT_LOCALE` | BCP-47; default `es-AR` |

White-label from day one. The env-var value is the **boot fallback**; the live primary color comes from `dashboard.app_settings` (admins change it via `/settings`).

### Auth pattern

- **Passwordless magic link** via Resend.
- Allowlist check at **two** points: when a magic link is requested, AND in the sign-in callback (defense in depth — token leak alone is not enough to log in if email isn't allowlisted).
- Magic link tokens SHA-256 hashed before storage in `dashboard.magic_link_tokens`. Never plaintext.
- Session: JWT (Auth.js default, no sessions table), max age 7 days.
- Roles: `dashboard.allowed_emails.role ∈ {viewer, admin}`. Default viewer; admin promotion explicit. Privileged routes: `await requireRole("admin")` from `src/lib/role-guard.ts` — viewers redirected to `/`, `role_denied` audit row written.

### Server Components by default

Every data-fetching surface is a Server Component awaiting Drizzle queries from `src/lib/queries/*.ts`. `"use client"` only when interactivity (charts, table sort, dialog) needs it. **No REST API for data** — pages query Postgres directly. Client Components don't fetch.

### URL state over component state

Table filters, pagination, analytics window (`?window=7|14|28|56`), intent attribution (`?touch=last|first|any`), heatmap filtering (`?heatmapIntent=`) — all live in the URL. Survives reload, shareable.

### CSV export

Streamed via `csv-stringify` to handle multi-MB exports without OOM. Rate-limited 10/min per session.

## Design system (Reserved Operations aesthetic)

Monochrome canvas + tenant's `--client-primary` as the only accent color. Always reference CSS vars from feature code — do not introduce new hex literals.

| Token | Default | Purpose |
|---|---|---|
| `--client-primary` | `#3b82f6` | Tenant accent. Injected from `dashboard.app_settings` per request. |
| `--ink` | `#111827` | Primary text |
| `--muted-ink` | `#6b7280` | Secondary text / kicker captions |
| `--soft-ink` | `#9ca3af` | Tertiary captions |
| `--rule` | `#e5e7eb` | Hairline borders + dividers |
| `--surface` | `#ffffff` | Card backgrounds |
| `--canvas` | `#fafafa` | Page background, hover states |
| `--good` | `#059669` | Positive deltas (semantic, brand-independent) |
| `--bad` | `#dc2626` | Negative deltas (semantic, brand-independent) |

**Hardcoded semantic palettes (intentional — domain meaning, not brand):**
- Priority chips: red (`#F4CCCC`/`#8A1A1A`), orange (`#FCE5CD`/`#8A4B00`), green (`#E6F4EA`/`#1B5E20`)
- Per-intent chart colors live in `src/config/verticals/<vertical>.ts`

**Typography:**
- Body / nav / table: **Geist Sans** (`--font-geist-sans`)
- Display headings + hero KPI values: **Fraunces** (`--font-fraunces`, `SOFT` + `opsz` axes) — gives the editorial Reserved Operations gravitas
- Numerics + code + kicker labels: **Geist Mono** (`--font-geist-mono`) with `tabular-nums` always on
- Page masthead: 44px / Fraunces 600 / -tracking
- Section heading: 22px / Fraunces 500 + 10px mono kicker line above
- KPI value: 40px / Fraunces 600 / `tabular-nums`
- Body: 14px / 400
- Table cells: 13px / 400
- Mono kicker: 10px / 500 / 0.18em letter-spacing / uppercase

**Style rules:**
- Border radius: 6px default (`rounded-md`), Cards 6px
- Cards carry a 2px **`--client-primary` top border** + standard 1px `--rule` hairline. The accent strip is the only color on the card by default.
- Spacing base: 4px
- Flat surfaces, hairline borders, no shadows, information-dense
- Page-load reveal is the **only** motion: `[data-reveal]` with staggered `--reveal-delay` per top-level section. Respects `prefers-reduced-motion`.
- Background: `--canvas` plus ~3% inline-SVG paper-grain texture on `<body>`
- Locale: es-AR, DD/MM/YYYY, thousand separator `.`, decimal `,`
- Timezone: America/Argentina/Buenos_Aires (overridable per tenant)

## Environment variables

| Variable | Description |
|---|---|
| `TENANT_DB_URL` | Postgres connection (includes `dashboard_app` user) |
| `VERTICAL` | Vertical config key (e.g. `real-estate`) |
| `CLIENT_NAME` | Header + email subject |
| `CLIENT_LOGO_URL` | Logo path/URL |
| `CLIENT_PRIMARY_COLOR` | CSS accent + chart primary |
| `CLIENT_TIMEZONE` | IANA tz |
| `CLIENT_LOCALE` | BCP-47 |
| `AUTH_SECRET` | 32-byte hex for JWT signing |
| `AUTH_URL` | Full external URL of this deploy |
| `AUTH_EMAIL_FROM` | Sender (Resend-verified domain) |
| `RESEND_API_KEY` | Resend API key |

## Operator commands (run on the VPS via `ssh vps`)

The dashboard's README documents one-liner `docker exec psql` patterns for managing tenants:

- Add a new allowlisted email (viewer): `INSERT INTO dashboard.allowed_emails (email, role) VALUES ('user@example.com', 'viewer')`
- Promote to admin: `UPDATE dashboard.allowed_emails SET role='admin' WHERE email='user@example.com'`
- Read recent audit log: `SELECT * FROM dashboard.audit_log ORDER BY created_at DESC LIMIT 50`
- Change boot-fallback primary color: edit `dashboard.env` then restart container; admins can also change it live via `/settings`

## Where the deep architecture decisions live

- **`docs/BLUEPRINT.md`** — full 16-section architecture spec, written for fresh Claude instances. Vision, success metrics, tech rationale, multi-tenant model.
- **`docs/INTENT_KPIS_PLAN.md`** — design rationale for per-intent analytics (handoff rates, completion %, time-to-handoff).
- **`docs/THEMING_DEPLOY_RUNBOOK.md`** — runbook used during the 2026-05-02 theming + Reserved Operations rollout. The pattern (canary on `client1`, additive migration, smoke test, then `tenant=all`) is the template for any future cross-cutting deploy.
- **`CLAUDE.md`** — the 10 non-negotiable rules (above).
