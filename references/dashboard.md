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
- Intent vocabulary (e.g., for real-estate: `ventas`, `alquileres`, `tasaciones`, `emprendimientos`, `admin`, `otras`; for architecture: `proyecto_lead`, `construccion_lead`, `gestiones_lead`, `desarrollo_lead`, `proveedor_intake`, `mano_obra_intake`)
- Terminal flows (which intents end in handoff vs continue)
- Per-intent chart colors (hardcoded hex — these are domain-meaning colors, NOT brand colors)
- Handoff target labels (`escalations.handoff_target` substring → human label)
- Attribution modes (last-touch / first-touch / any-touch)
- Locale-specific labels for the UI
- **Feature flags** — see below

`VERTICAL=<key>` env var picks which file to load. Adding a new vertical = one new file (~1 hour). Shipped verticals: `real-estate` (client1, since v1), `architecture` (Plec, since 2026-05-19), `outbound-sales` (ventas, arka), `outbound-wholesale` (Tasty, since 2026-09-27 — spreads `outbound-sales` and only swaps the `crm` block: a new key is the way to give one tenant its own pipeline, since nothing in `src` branches on the key string). Registry: `src/config/verticals/index.ts`.

### `verticalConfig.features` — the "business type" mechanism

Each vertical declares its capabilities via an optional `features` object. The dashboard renders feature-gated UI only when the flag is truthy. Default for any vertical with no `features` key = "no extra features" (same as real-estate today).

```ts
export type VerticalFeatures = {
  providersTab?: boolean;     // /providers route + sidebar item, queries automation.v_providers
  laborPoolTab?: boolean;     // /labor-pool route + sidebar item, queries automation.v_labor_pool
  campaignsTab?: boolean;     // /campaigns route — read-only OUTBOUND funnel, queries outreach.v_*
  botResolutionKpi?: boolean; // Panel "Resueltas por el bot" tile. Default-ON (undefined=show);
                              // set false where a handoff IS the goal (outbound-sales).
};
```

Current declarations:

| Vertical | features |
|---|---|
| `real-estate` (client1) | (omitted — no extra features) |
| `architecture` (plec) | `{ providersTab: true, laborPoolTab: true }` |
| `outbound-sales` (ventas) | `{ campaignsTab: true, botResolutionKpi: false }` (since 2026-06-10) |
| `services` (future) | `{ laborPoolTab: true }` only — no formal supplier directory |

**Cross-schema feature (`campaignsTab`).** Unlike the other tabs (which read `automation.v_*`), the
`/campaigns` page reads the **`outreach.v_*`** views (`v_campaign_stats`, `v_outreach_overview`,
`v_campaign_daily`, `v_quality_current`) + the `outreach.quality_log` table — the outbound funnel for
the ventas tenant. This required: (a) a dashboard migration **`migrations/0003_outreach_grants.sql`**
that conditionally `GRANT`s `SELECT` on `outreach.*` to `dashboard_app` (no-op for tenants without the
schema), applied as superuser by `provision-tenant.sh`; and (b) **NOT** adding these to
`REQUIRED_VIEWS` / `verify-view-compat.mjs` (automation-only, boot-verified — would crash other
tenants). Read-only still holds: `dashboard_app` is SELECT-only on `outreach.*` too. The page is
v1-read-only (no campaign controls — those stay in SQL + the n8n runner; see `outbound-sales.md`).
The quality badge is fed by an n8n Graph poll, not the dashboard (the dashboard never calls Meta).

When adding a new feature flag:

1. Add the boolean to `VerticalFeatures` in `src/config/verticals/_types.ts`
2. Read it in `app/(dashboard)/layout.tsx` (sidebar) to add a nav item conditionally
3. Add a new icon key to `NavIconKey` + `ICON_MAP` in `Sidebar.tsx` and `MobileNav.tsx`
4. Defense-in-depth: every gated page calls `if (!verticalConfig().features?.flag) notFound()` early; same in the corresponding `/api/export/...` route
5. Each vertical's `<vertical>.ts` opts in or out

**Why a flat features object instead of a `businessType` enum:** verticals self-describe their capabilities, no central mapping to maintain. A future vertical that needs an unusual combination doesn't require a new enum value.

### Sidebar / route guards

Routes that depend on features (`/providers`, `/labor-pool` today; more to come) follow this pattern:

```ts
// app/(dashboard)/providers/page.tsx
import { notFound } from "next/navigation";
import { verticalConfig } from "@/config/verticals";

export default async function ProvidersPage(/* ... */) {
  if (!verticalConfig().features?.providersTab) {
    notFound();
  }
  // ...
}
```

Sidebar in `app/(dashboard)/layout.tsx` assembles the nav list by composing:

```
base nav (always, from vertical.nav)
  + featureItems   (conditionally appended per vertical.features)
  + SETTINGS_NAV_ITEM   (only if sessionRole.role === "admin")
```

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

### Full-width views (`data-board-bleed`)

The layout caps pages at 1280px except when the page root carries `data-board-bleed` (`has-[[data-board-bleed]]:max-w-none` in `src/app/(dashboard)/layout.tsx`, pure CSS). Since PR #48 (2026-10-02) that is **/leads, Derivaciones, Conversaciones, Seguimiento and Campañas**; Panel, Settings and the conversation thread keep the reading width. To widen another page, add the attribute to its root `<div>` — nothing else.

**Campañas filter** (#48): chips «Todas · N» / «Activas · N», URL state `?status=active` (survives the poller's `router.refresh()`); only the table is filtered, tiles and chart stay global.

**e2e timezone** (#49): Playwright runs the browser in `America/Argentina/Buenos_Aires` (`timezoneId` + `locale` in `playwright.config.ts`) and `localDateInput` in `tests/e2e/leads.spec.ts` computes in that zone. CI is UTC; between 21:00 and midnight AR the reminder test used to read «pasado mañana».

### URL state over component state

Table filters, pagination, analytics window (`?window=7|14|28|56`), intent attribution (`?touch=last|first|any`), heatmap filtering (`?heatmapIntent=`) — all live in the URL. Survives reload, shareable.

### CSV export

Streamed via `csv-stringify` to handle multi-MB exports without OOM. Rate-limited 10/min per session. Since #45 the transcript's `text` column says `[foto]` / `[documento]` where a message had no text and prefixes a voice note's transcript with `[audio]` (`transcriptText` in `src/lib/media/bubble.ts`); `lead_log.text_body` is never rewritten.

### Media in the thread (photos, voice notes, PDFs a lead sent) — 2026-09-28, PRs #44 + #45

Where the bytes come from is the whole design: the tenant's n8n router captures media into `automation.media_assets` (see `postgres-schema.md`; today only plec's router does), and the dashboard **reads** it in two deliberately different ways:

- **The thread** (`getConversation`, `src/lib/queries/contacts.ts`) LEFT JOINs the view `automation.v_media_assets`, which has **no `content` column**, so a page render can never drag binaries across the wire. `LeadLogEntry` gained `messageType` and `media: MediaRef | null`.
- **The bytes** are served by `GET /api/media/[id]` (`src/app/api/media/[id]/route.ts` → `src/lib/queries/media.ts`), the single place the base table is read: one row, by our BIGSERIAL id, never Meta's `media_id` or its lookaside URL. `requireRoleApi("viewer")` on top of the proxy guard (an anonymous request gets the proxy's 307 to `/login` first — the 401 JSON is defense-in-depth). Headers: `Cache-Control: private, no-store`, `X-Content-Type-Options: nosniff`, and an **inline allowlist** (jpeg, png, webp, ogg, mpeg, mp4 audio, pdf) — anything else, `image/svg+xml` and `text/html` included, is forced to download as `application/octet-stream`, because the mime type comes from Meta and must never pick what executes on the dashboard's origin. Not audited per request on purpose (a thread with twenty photos would write twenty rows per view); exports stay the audited action.
- **The bubble** (`src/components/dashboard/MediaBubble.tsx`, rendered by `ConversationTimeline` for every entry) decides through the pure `presentMedia()` in `src/lib/media/bubble.ts` with copy from `src/config/media-labels.ts` (no Spanish in JSX): `<img>` for a photo (a plain `<img>`, not `next/image` — an optimizer would cache a lead's private photo server-side), native `<audio controls preload="none">` for a voice note with the transcript underneath (native because **Safari on iOS 26 plays `audio/ogg`** — tested 2026-09-28 on the real thing; no WASM decoder needed), "Descargar PDF · 294 KB" for a document. Every empty case explains itself from `fetch_status` or, with no row, from `message_type`: *Foto — ya no disponible* (swept by the 90-day retention, or before capture existed), *Archivo muy grande*, *No se pudo recuperar*, *Video — no se guarda*.
- **Boot**: `v_media_assets` is in `REQUIRED_VIEWS` (8 views). It exists on all six tenants, empty where the router does not capture, so the shared image boots everywhere and shows "ya no disponible" for old media rather than `42P01`.
- **Dev/CI**: `scripts/dev-automation-setup.sql` mirrors the table + view and `lead_log.message_id`; the seed gives contact `5491155501004` a stored 1×1 PNG, a swept photo and a `too_large` document, which `tests/e2e/media.spec.ts` opens.

Gotcha found on the way: on an iPhone, a magic link tapped from the **Gmail app** is consumed inside Gmail's in-app browser — the login succeeds *there* (an audit `login` row ~15 s after issue) and Safari has no session; a second tap is a used token (`Verification` error). It looks like a rate limit and is not. Open the link in Safari (long-press → copy, or Gmail › Default apps).

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
| `VERTICAL` | Vertical config key: `real-estate`, `architecture`, `outbound-sales`, `outbound-wholesale` |
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
- **`docs/crm-oportunidades.md`** — the CRM's 17 business rules + ER diagram, the source of truth for anything about Leads/opportunities. Platform-level summary and per-tenant state: `references/crm-leads.md`.
- **`CLAUDE.md`** — the 10 non-negotiable rules (above).
