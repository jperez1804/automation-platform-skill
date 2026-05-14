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
| Meta embedded signup, WABA, phone number registration, Tech Provider flow | `references/meta-tech-provider.md` |
| Bot Argento branding, real-estate vertical, Spanish copy, current production state | `references/reference-instance.md` |
| VPS, Hostinger, `ssh vps`, Traefik, per-tenant compose, deploy gotchas, MCP limitations | `references/vps-deployment.md` |
| Onboarding a new agency / new vertical — step-by-step | `references/new-vertical-playbook.md` |
| Per-tenant onboarding state — who's at which pipeline stage (`client1`, `plec`, …) | `references/tenants-status.md` |

## n8n MCP cross-references

When the work involves writing or editing n8n workflows, also consult these `n8n-mcp-skills` skills (they cover n8n mechanics; this skill covers the platform's specific use of those mechanics):

- `n8n-mcp-skills:n8n-workflow-patterns` — webhook + database + AI agent + batch processing patterns
- `n8n-mcp-skills:n8n-code-javascript` — `$input`/`$json`/`$node`, helpers, DateTime, batch loops
- `n8n-mcp-skills:n8n-expression-syntax` — `{{ }}` syntax, common errors
- `n8n-mcp-skills:n8n-node-configuration` — operation-aware field configuration
- `n8n-mcp-skills:n8n-mcp-tools-expert` — guidance for the n8n MCP itself

## Two non-negotiable platform invariants

1. **The `automation.*` Postgres schema is fixed across every agency.** Same DDL: `session_memory`, `lead_log`, `escalations`, `inventory`. New verticals add **views** (`automation.v_<vertical>_*`) on top, not new tables. The dashboard reads only views; the n8n router writes to the four base tables.
2. **The dashboard never writes to `automation.*`.** Enforced at the DB-role level — `dashboard_app` user has SELECT-only on `automation.*`, full access to `dashboard.*`. Any attempt to insert/update/delete in `automation.*` from the dashboard is a bug.

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
