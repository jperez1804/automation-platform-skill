# automation-platform — Claude Code skill

A reference skill for Jonatan's vertical-agnostic WhatsApp automation platform.
It puts Claude Code in full context of the platform's four pillars (landing
page · n8n WhatsApp automation · multi-tenant dashboard · Meta Tech Provider
backend), the shared Postgres `automation` schema, the Hostinger VPS topology,
and the per-agency onboarding pipeline.

> **Personal skill.** This repo is published for backup and reference. The
> documentation references absolute paths on Jonatan's laptop
> (`C:\Desarollo\jperez\...`, `C:\Users\jperez\...`). A fork will need to adapt
> those to its own filesystem.

## What's inside

```
automation-platform/
├── SKILL.md                              ← skill manifest (frontmatter + index)
├── references/
│   ├── stack-overview.md                 ← the four repos and how they fit
│   ├── postgres-schema.md                ← session_memory / lead_log / escalations / inventory
│   ├── whatsapp-automation.md            ← n8n router + wizards + post-deploy wiring
│   ├── dashboard.md                      ← Next.js multi-tenant dashboard
│   ├── meta-tech-provider.md             ← embedded signup + webhook activation
│   ├── reference-instance.md             ← Bot Argento (real-estate, live tenant)
│   ├── vps-deployment.md                 ← Hostinger VM, Traefik, per-tenant compose
│   ├── new-vertical-playbook.md          ← step-by-step recipe for onboarding an agency
│   ├── outbound-sales.md                 ← Bot Argento Sales (cold outreach add-on)
│   ├── botargento-scraping.md            ← lead-sourcing leg: web → validated wa_id → outreach
│   └── tenants-status.md                 ← live state of each tenant in the pipeline
└── scripts/
    └── botargento-scraping/              ← scraper + AR phone classifier + checknumber.ai validator (wa.me fallback) + CSV emitter
```

## How Claude Code discovers it

Claude Code reads skills from `~/.claude/skills/<name>/SKILL.md`. To install:

```bash
git clone https://github.com/jperez1804/automation-platform-skill.git "$HOME/.claude/skills/automation-platform"
```

On Windows (PowerShell):

```powershell
git clone https://github.com/jperez1804/automation-platform-skill.git "$env:USERPROFILE\.claude\skills\automation-platform"
```

After cloning, restart Claude Code so the skill list refreshes. The skill name
will appear in available-skills listings and Claude will load `SKILL.md`
automatically when relevant prompts fire (any mention of the platform, n8n,
the `automation.*` schema, the dashboard, a new agency, Meta WABA, the VPS,
etc.).

## How it works (progressive disclosure)

`SKILL.md` is the index — read it first; it routes to the right reference file
for the user's question. Don't load every reference at once: each is sized for
focused consultation. The "If the user asks about…" table in `SKILL.md` makes
the routing explicit.

## Conventions

- Two non-negotiable platform invariants are stated in `SKILL.md`:
  1. The `automation.*` Postgres schema is fixed across every agency.
  2. The dashboard never writes to `automation.*`.
- Per-agency artifacts live in a separate workspace directory
  (`<agency-slug>/<Agency> Automation/`), **never** as forks of the shared
  platform code. See `SKILL.md` § "Per-agency artifacts directory" and
  `references/new-vertical-playbook.md` for the directory shape.

## Updating

When a tenant moves through the pipeline or a transversal lesson surfaces
(e.g. a new pattern, a gotcha worth recording), update the relevant
reference file directly. `tenants-status.md` is the highest-churn file by
design — it's living state. Strike-through old facts instead of deleting
them so the audit trail survives.

## License

MIT — but the contents are heavily Jonatan-specific. Use as reference,
adapt for your own platform.
