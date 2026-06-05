# Stack overview

The platform is **four cooperating pillars** plus one shared database. Everything else (Hostinger VPS, Traefik, GitHub Actions) is operational glue.

```
                  ┌─────────────────────┐
                  │  Meta WhatsApp API  │
                  └──────────┬──────────┘
                             │ webhook (per-tenant override)
                             ▼
┌──────────────┐    ┌────────────────────────┐    ┌──────────────────────┐
│ Landing page │    │ n8n WhatsApp           │◀──▶│ Postgres `automation`│
│  (HTML/CSS)  │    │  router + wizards      │    │  schema (SHARED)     │
│  Calendar +  │    │  (per-tenant n8n)      │    │  session_memory      │
│  WA FAB      │    └──────────┬─────────────┘    │  lead_log            │
└──────────────┘               │ (writes)         │  escalations         │
                               │                  │  inventory           │
                               │                  └──────────┬───────────┘
                               │                             │ SELECT only
                               │                             ▼
                  ┌────────────────────────┐    ┌──────────────────────┐
                  │ Meta Tech Provider     │    │ Multi-tenant         │
                  │  backend (Hono/SQLite) │    │  dashboard (Next.js) │
                  │  embedded signup +     │    │  Auth.js magic link  │
                  │  per-WABA webhook      │    │  per-tenant Docker   │
                  │  override              │    │  behind Traefik      │
                  └────────────────────────┘    └──────────────────────┘
                          (Railway)                  (Hostinger VPS)
```

## 1. Landing page

**Repo:** `C:\Desarollo\jperez\BotArgentoLandingPageRepo\landingpage`

- Pure vanilla HTML + CSS + JS — no framework, no build step. Hosted as static files.
- Animated particles, scroll-spy navbar, FAQ accordion, floating WhatsApp FAB, IntersectionObserver reveal animations.
- Fonts: Sora (headings), Geist (body) — both Google Fonts.
- **Lead capture flow:** no backend form. CTA → Google Calendar booking link. Secondary CTA → `wa.me/<number>?text=<prefilled>`. gtag events for both.
- Per-agency rebrand: swap copy, color palette CSS vars, calendar link, WhatsApp number, logo SVG.

## 2. WhatsApp automation (n8n)

**Repo:** `C:\Desarollo\jperez\n8n\whatsapp-automation-claude`

Files (all are n8n workflow JSON exports):

| File | Role |
|---|---|
| `v2-meta-receive-router.json` | **Entry workflow.** GET (webhook verification) + POST (message receipt). Normalize event → dedup on `(direction, message_id)` → Postgres advisory lock on `contact_wa_id` → load session → switch route → call child wizard. |
| `v2-inventory-wizard.json` | Multi-step search wizard. Single Code node implementing 5-step state machine (zone → property type → bedrooms → price → results). |
| `v2-tasaciones-wizard.json` | 6-step valuation intake form. |
| `v2-otras-consultas.json` | 3-step general inquiry form. |
| `v2-emprendimientos.json` | Investment project listing + advisor handoff. |
| `v2-send-whatsapp-message.json` | **Shared sender.** HTTP POST to Meta `/messages` endpoint. Used by all child wizards. |
| `v2-persist-session-and-logs.json` | **Shared persister.** Upsert `session_memory` + insert `lead_log` (in/out) + conditionally insert `escalations` + send SMTP handoff email. |
| `v2-error-handler.json` | Global error trap → log to `escalations` → throttled alert email → fallback WhatsApp message to user. |
| `v2-sync-inventory.json` | Cron 15-min: read Google Sheets → upsert `automation.inventory`. |
| `postgres-setup.sql` | Verbatim DDL for the shared `automation` schema. |

**The router/sender/persister/error-handler are the engine — vertical-agnostic.** Wizards are vertical-specific JS state machines.

See `references/whatsapp-automation.md` for the deep dive (mermaid diagram, execution order, contract between router and child).

## 3. Multi-tenant dashboard

**Repo:** `C:\Desarollo\jperez\n8n\botargento-dashboard`

- **Stack:** Next.js 15 (App Router) + TypeScript strict + Tailwind v4 + shadcn/ui + Recharts + TanStack Table + Drizzle + Postgres + Auth.js v5 (Resend magic link) + Docker + Traefik.
- **Multi-tenancy model:** one Docker container per tenant. Dashboard at `dashboard.<clientN>.botargento.com.ar`. Each container reads the tenant's own Postgres database. There is **no shared dashboard DB across tenants** — each tenant has its own Postgres instance with both `automation.*` and `dashboard.*` schemas.
- **Vertical multi-tenancy:** the same Docker image serves any vertical. The active vertical is selected by env var `VERTICAL=<key>` which loads `src/config/verticals/<key>.ts`. v1 ships `real-estate.ts`. New vertical = one new file (~1 hour of work).
- **White-label tenant config:** `CLIENT_NAME`, `CLIENT_LOGO_URL`, `CLIENT_PRIMARY_COLOR`, `CLIENT_TIMEZONE`, `CLIENT_LOCALE` env vars injected at runtime.
- **Read-only against `automation.*`** — DB role `dashboard_app` has SELECT-only on `automation.*`, full access to `dashboard.*`.

See `references/dashboard.md` for the 10 non-negotiable rules + design tokens + auth pattern.

## 4. Meta Tech Provider backend

**Repo:** `C:\Desarollo\jperez\n8n\botargento-backend`

- **Stack:** Hono + TypeScript + better-sqlite3 (WAL) + Drizzle + Zod + pino. Deployed on Railway with persistent `/data` volume.
- Jonatan is a **registered Meta Tech Provider**. This backend brokers the **Embedded Signup** flow that lets a client onboard their own WhatsApp Business Account (WABA) without leaving Jonatan's site.
- **Two-stage onboarding state machine:** `started` → `signup_completed` → `assets_saved` → `webhook_ready`. Stage 1 finishes at the embedded signup callback; Stage 2 (admin-triggered) installs the **per-WABA webhook override** that points Meta callbacks at the tenant's own n8n endpoint (e.g., `https://client1.botargento.com.ar/webhooks/whatsapp`).
- **Auth model:** public routes (sessions, complete) rate-limited by IP. Admin routes (`/api/admin/*`) gated by `X-Admin-Key` header.
- **Token security:** business integration tokens encrypted with AES-256-GCM in `src/services/crypto.ts` before storage. Decrypted only when calling Meta.
- **Does NOT process runtime WhatsApp messages.** That's the tenant's n8n. This backend is control-plane only.

See `references/meta-tech-provider.md` for the full state machine + Graph API endpoints.

## How the pillars connect at runtime

1. **Onboarding (one-time):** Client visits Jonatan's onboarding page → embedded signup popup → Tech Provider backend exchanges code for token, persists WABA + phone, encrypts token. Admin later activates per-WABA webhook override → Meta starts sending the client's WhatsApp events to that client's n8n.
2. **Steady state — inbound message:** Customer sends WhatsApp message → Meta POSTs to tenant's n8n router → router dedup + lock + session load → routes to wizard → wizard returns `{reply_text, route, qualification_snapshot, handoff, ...}` → shared sender posts to Meta → shared persister writes `session_memory`, `lead_log`, optionally `escalations` + SMTP email.
3. **Dashboard view:** Agency operator opens `dashboard.<clientN>.botargento.com.ar` → magic-link login (Resend) → Server Components query Postgres views (`automation.v_*`) → render KPIs, conversations, handoffs, follow-up queue.
4. **Lead acquisition (top of funnel):** Prospect lands on agency landing page → clicks Calendar CTA or WhatsApp FAB → enters the WhatsApp router from the very first message.

## Outbound companion (Bot Argento Sales)

The four pillars above are all **inbound** — they answer customers who message first, inside Meta's
24h service window. A fifth, **outbound** engine reverses the direction: it cold-messages prospects
with a pre-approved Marketing template, and when they reply the existing router + a pitch wizard
qualify them in-window. It **reuses** the shared sender / persister / error-handler / router skeleton,
**adds** a new `outreach.*` Postgres schema (campaigns / recipients / suppression — `automation.*`
stays frozen) plus a `v2-campaign-runner.json` workflow, and runs as its own tenant on a **dedicated
sales WABA**. Built first as Jonatan's own client-acquisition tool, and offered per-tenant as a
sellable add-on (drop `outreach.*` + the runner into any existing tenant, swap the pitch wizard +
template). See `references/outbound-sales.md`.

## What's NOT in the platform (intentional gaps)

- **No CRM**, no calendar integration beyond the public Google Calendar booking link, no payment processing.
- **No AI agent yet** in production wizards. `OPENAI_API_KEY` and `OPENAI_MODEL` are present in `variables.txt` but unused in v2 — current wizards are deterministic state machines. AI triage for "Otras Consultas" is on the roadmap.
- **No shared central dashboard.** Each tenant has its own Docker container reading its own database. Agency-side aggregation across all tenants would be new work.
- **No mobile app.** All client-facing is WhatsApp + landing page.
