---
name: automation-platform
description: Complete knowledge base for Jonatan's vertical-agnostic WhatsApp automation platform — the n8n router/wizards, the shared Postgres `automation` schema (session_memory, lead_log, escalations, inventory) used by every agency, the multi-tenant Next.js dashboard with vertical config, the Hono Meta Tech Provider backend (embedded signup), and the Hostinger VPS topology (Traefik, per-tenant Docker, ssh vps alias). Bot Argento (real estate) is the reference instance. Use this skill whenever the user mentions his automation platform, an agency he's onboarding, WhatsApp Cloud API, n8n workflow design for a service-vertical assistant, the multi-tenant dashboard, the automation Postgres schema, Meta embedded signup, the VPS / Hostinger / `ssh vps` / Traefik / per-tenant compose, or any time a new vertical (architecture, dental, gym, fitness, services) needs to be plugged into the platform. Trigger even when the user does not explicitly say "platform" — any of those concrete signals is enough.
---

# Jonatan's WhatsApp Automation Platform

This skill puts you in full context of the **vertical-agnostic WhatsApp automation platform** Jonatan built and resells per agency. Bot Argento (real estate) is the first reference instance, but the **platform itself stays the same** for any new agency — architecture studio, dental clinic, gym, services. What changes per agency is only:

- the **vertical config** (intents, terminal flows, chart colors)
- the **brand** (name, color, copy, landing page)
- the **inventory shape** (rows in the same `automation.inventory` table; column semantics may shift)

Everything else — n8n workflows, Postgres `automation` schema, Next.js dashboard, Hono Meta backend, Hostinger VPS topology, deploy pipeline — is shared.

**Outbound companion.** The platform now also has an **outbound** sibling — **Bot Argento Sales** — the mirror image of the inbound engine: it cold-messages prospects with a Meta template that earns a reply, then the existing router + a pitch wizard qualify them in-window. Built first as Jonatan's own client-acquisition tool, and designed to be **sold to clients as an "outbound campaigns" add-on**. See `references/outbound-sales.md`. A tenant can also buy that outbound half **without our bot** — "provider mode": we send the templates and own opt-out/suppression, while the conversation lives in the client's own helpdesk (Chatwoot), mirrored both ways. First sold to arka; see `references/chatwoot-mirror.md`. The **front of that funnel** is the **botargento-scraping** module — it scrapes prospect numbers from the public web, validates which are real WhatsApp accounts, and emits the CSV that seeds `outreach.recipients`. See `references/botargento-scraping.md`.

## The four pillars

| # | Pillar | Repo (on Jonatan's machine) | Role |
|---|---|---|---|
| 1 | **Landing page** | `C:\Desarollo\jperez\BotArgentoLandingPageRepo\landingpage` | Vanilla HTML/CSS/JS lead capture template. Cloned + rebranded per agency. Lead routes to Google Calendar + WhatsApp FAB. |
| 2 | **WhatsApp automation** | `C:\Desarollo\jperez\n8n\whatsapp-automation-claude` | n8n workflows: thin router → child wizards → shared sender + persister + error handler. Reads/writes the Postgres `automation` schema. **The engine is shared; wizard contents are vertical-specific.** |
| 3 | **Multi-tenant dashboard** | `C:\Desarollo\jperez\n8n\botargento-dashboard` | Next.js 15 + Drizzle + Auth.js magic-link. Per-tenant Docker container behind Traefik on the VPS. Vertical config (`src/config/verticals/<vertical>.ts`) makes it multi-vertical. Read-only against `automation.v_*` views. |
| 4 | **Meta Tech Provider backend** | `C:\Desarollo\jperez\n8n\botargento-backend` | Hono + SQLite. Two-stage Meta embedded signup: signup completion → admin-activated per-WABA webhook override pointing to tenant's n8n. Deployed on Railway. Jonatan is a registered Meta Tech Provider. |

## How to use this skill

This is a **reference**, not a procedure. Read the SKILL.md (this file) for the index, then load the specific reference file that matches the user's question. Do **not** load every reference at once — they're sized for progressive disclosure.

| If the user asks about… | Read |
|---|---|
| The overall stack, what each repo does, how they fit together | `references/stack-overview.md` |
| Postgres tables, schema, queries, dedup, session storage, escalations | `references/postgres-schema.md` |
| n8n workflows, router, wizards, mermaid diagram, message flow, error handler | `references/whatsapp-automation.md` |
| The dashboard (Next.js, vertical config, tenant config, design tokens, auth, magic link) | `references/dashboard.md` |
| Meta embedded signup, WABA, phone number registration, Tech Provider flow — **incl. the v4 migration (2026-10-07: config `1423827086618896`, `extras: { setup: {}, version: 'v4' }`) and why Coexistence doesn't work for Argentine numbers** | `references/meta-tech-provider.md` §Embedded Signup version, §Coexistence |
| **Tech debt and dated re-checks** (e.g. Coexistence for Argentina on 2026-10-21) | `techdebt/README.md` |
| Bot Argento branding, real-estate vertical, Spanish copy, current production state | `references/reference-instance.md` |
| VPS, Hostinger, `ssh vps`, Traefik, per-tenant compose, deploy gotchas, MCP limitations — **incl. the 2026-09-09 all-tenant 404 outage (Traefik v3.0 vs Docker 29) and the post-reboot smoke rule** | `references/vps-deployment.md` |
| Onboarding a new agency / new vertical — step-by-step | `references/new-vertical-playbook.md` |
| Per-tenant onboarding state — who's at which pipeline stage (`client1`, `plec`, …) | `references/tenants-status.md` |
| Outbound sales / cold-outreach campaigns, opt-in & ban-avoidance rules, the campaign runner, the `outreach.*` schema, the sellable add-on | `references/outbound-sales.md` |
| Sourcing/scraping prospect WhatsApp numbers from the web (the lead-gen leg that feeds outbound) — scrapling MCP, Cylex/Google Maps, AR phone classification, checknumber.ai validation, the seed-ready CSV | `references/botargento-scraping.md` |
| **"Provider mode"** — the client owns the conversation in **their own helpdesk (Chatwoot)** and we only send templates + keep opt-out: the bot-silent router flag, the mirror bridge, the webhook back, attachments both ways, the suppression gate, per-tenant install checklist | `references/chatwoot-mirror.md` |
| Engine upgrades shipped 2026-09 (post-handoff window, voice-note transcription, burst grouping, spoken answers to option lists), **porting them to another tenant**, the tenant-config deployer (`patch-tenant-live.mjs` + `tenants.json`) | `references/whatsapp-automation.md` §Conversational upgrades, then `whatsapp-automation-claude/PORTING-conversational-upgrades.md` |
| **The CRM-lite ("Leads")** — the sales pipeline in the dashboard: one person / N opportunities, the rubro rule, "Sin derivar", the reminder notice to the advisor on WhatsApp, **which tenants have it (`client1`, `ventas`, `plec`, `tasty` — the reminder notice on the first three; tasty's template still pending at Meta)**, and the gotchas | `references/crm-leads.md`, then the dashboard repo's `docs/crm-oportunidades.md` for the 17 business rules |
| **Defaults every new automation must ship with** — the advisory lock that doesn't serialize, burst grouping (+ the `Inbound Ready` contract), the anti-loop `dormant` guard and silent turns, never dead-ending a lead (price intent, free-text handoff), opt-out regex, declines without "interés" (closed / wrong number / has supplier), detecting the prospects' own auto-responders (wording + timing, and the delayed-delivery blind spot), regression harnesses fed with real messages | `references/whatsapp-automation.md` §Conversation hardening |
| **Media (voice notes, photos, PDFs)** — capture into `automation.media_assets` after the reply, retention, where the bytes physically live (Postgres TOAST vs n8n's `binaryData/` files), `store_failed` visibility, **which tenants have it (n8n capture: `plec` and `client1`; the table: all six)**, the engine deployer's `media` target and the porting runbook (`whatsapp-automation-claude/PORTING-media-capture.md`), the three n8n facts that let a "verified" branch ship dead, and the dashboard plan (bytes route → iPhone Ogg/Opus gate → bubble) | `references/whatsapp-automation.md` §Conversational upgrades (Media capture row, Adoption per tenant, design rules) · `references/postgres-schema.md` §`automation.media_assets` · `Plec Automation/docs/plec-arquitectos/plan-media-v2.md` |

## Tech debt folder

`techdebt/` holds one file per pending item, named `YYYY-MM-DD-<slug>.md` with the date to look at it again. **When this skill loads, list `techdebt/` and tell Jonatan about any item whose date is today or past** before starting the task. Resolved items are deleted; what stays true moves into `references/`.

## Agents

Four named subagents live in `agents/` of this skill and are exposed **globally** through the
junction `~/.claude/agents` → `~/.claude/skills/automation-platform/agents`, so they are available
from any project/session (each new client is a new working directory). Invoke by name
("usá el agente `campaign-ops`…") or let Claude pick them from their descriptions. Each agent loads
its own references — the caller does not need to have this skill loaded.

| Agent | Use it for | Writes? |
|---|---|---|
| `campaign-ops` | Outbound campaign status, funnel reports, queue/cap questions, recipient lookups | No — SELECT only, proposes SQL |
| `dashboard-deployer` | Ship the shared dashboard image to ONE tenant (selective commit → CI → `docker-compose --env-file` → smoke) | Yes, scoped to the named tenant |
| `n8n-deployer` | Per-agency `_src` → `build.mjs` → `patch-wizard-live.mjs`; engine repo `patch-tenant-live.mjs <tenant> <target>` (`tenants.json`; structural router upgrades — audio, grouping, post-handoff window — and porting them); router/wizard/runner patches, n8n API gotchas | Yes, in-place patch of existing workflow ids (structural targets insert nodes; never re-import) |
| `tenant-onboarder` | New client: workspace scaffold, discovery notes, proposal (structured-menu mockups + pricing), Meta checklist, `tenants-status.md` | Yes, only in the agency workspace + tenants-status |

Edit the `.md` files in `agents/` (they are versioned with this repo); the junction makes the change
visible immediately. Don't put agents anywhere else.

## n8n MCP cross-references

When the work involves writing or editing n8n workflows, also consult these `n8n-mcp-skills` skills (they cover n8n mechanics; this skill covers the platform's specific use of those mechanics):

- `n8n-mcp-skills:n8n-workflow-patterns` — webhook + database + AI agent + batch processing patterns
- `n8n-mcp-skills:n8n-code-javascript` — `$input`/`$json`/`$node`, helpers, DateTime, batch loops
- `n8n-mcp-skills:n8n-expression-syntax` — `{{ }}` syntax, common errors
- `n8n-mcp-skills:n8n-node-configuration` — operation-aware field configuration
- `n8n-mcp-skills:n8n-mcp-tools-expert` — guidance for the n8n MCP itself

## Three non-negotiable platform invariants

1. **The `automation.*` Postgres schema is fixed across every agency.** Same DDL: `session_memory`, `lead_log`, `escalations`, `inventory`. New verticals add **views** (`automation.v_<vertical>_*`) on top, not new tables. The dashboard reads only views; the n8n router writes to the four base tables.
2. **The dashboard never writes to `automation.*`.** Enforced at the DB-role level — `dashboard_app` user has SELECT-only on `automation.*`, full access to `dashboard.*`. Any attempt to insert/update/delete in `automation.*` from the dashboard is a bug.
3. **No conversation may dead-end or loop.** Every tenant ships the hardening defaults in `references/whatsapp-automation.md` §Conversation hardening: burst grouping, the consecutive-miss `dormant` guard with silent turns, opt-out regex on top of exact tokens, and a wizard that answers price intent and hands off free-text questions instead of repeating the menu. A lead who asks something the script didn't anticipate must reach a human, never "No te entendí" twice.

## Per-agency artifacts directory (workspace convention)

Per agency, Jonatan keeps a working directory at `C:\Desarollo\jperez\<agency-slug>\<Agency> Automation\` for *agency-specific artifacts only* — never a fork of the shared platform code. Reference instance: `C:\Desarollo\jperez\plecarquitectos\Plec Automation\`.

```
<Agency> Automation/
├── docs/                  # proposal, infra-status, handoff docs
├── n8n/
│   ├── compose/           # docker-compose.yml + .env destined for /opt/n8n/<tenant>/ on the VPS
│   └── wizards/           # wizard JSON exports adapted for this vertical
├── dashboard/
│   ├── vertical/          # draft of <vertical>.ts before PR to the shared dashboard repo
│   └── tenant/            # tenant config (CLIENT_NAME, color, logo) + brand assets
├── landing/               # rebranded clone of BotArgentoLandingPageRepo/landingpage
└── handoff/               # emails / phone numbers / SMTP creds (sensitive)
```

Why it matters: this is the *handoff zone* between agency-specific drafts and the shared repos. Wizard JSONs here get imported into the shared n8n; vertical config drafts here get promoted via PR to the shared dashboard; compose files here get rsynced to `/opt/n8n/<tenant>/` on the VPS. **The shared repos remain source of truth for the platform's code.** Don't suggest creating a parallel `n8n/` or `dashboard/` codebase here — that would break invariant #1 (one engine, per-tenant config).

## Things this skill is NOT

- Not a code generator or scaffolder — it puts you in context, you write the code conversationally.
- Not tied to any specific arq agency name. The platform is sold to whoever; brand always lives in env vars and per-agency config files.
- Not a substitute for reading the actual repos when implementing. It captures the **what** and **why**; the **how** lives in the source files.
