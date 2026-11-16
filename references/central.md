# Central — the agency panel

`https://central.botargento.com.ar` · repo `jperez1804/botargento-central` (local
`C:\Desarollo\jperez\bot-argento-sales\central`) · image `ghcr.io/jperez1804/central:<sha>` · VPS
`/opt/n8n/central/` (`central`, `central-postgres` 16, `central-docker-proxy` read-only socket proxy).

The agency's own panel, not a tenant's. It **watches** tenants and never writes to their databases or
containers. Same stack as the tenant dashboard (Next.js 16, postgres.js, next-auth magic link, Vitest +
Playwright), own Postgres schema `central`, SQL migrations applied at container start.

The source of truth for details is the repo's `docs/`: `BLUEPRINT.md` (all phases), `redes.md`
(Instagram/Zernio), `api-interna.md`, `whatsapp-alerts.md`, `infra-status.md` (deploy log),
`referencias-arka.md`.

## Sections (state 2026-11-16, prod `e1eb09c`)

| Section | What | State |
|---|---|---|
| Inicio / Clientes | clients, phase + history (`client_change_phase`), contacts, infra links, MRR (`v_mrr`) | live |
| Cobros | monthly billing periods (due on the 10th), payments, waive | live |
| Salud | in-process monitor: containers via the socket proxy, http through Traefik (Traefik 404 = router lost), TLS, restarts, n8n executions/silence per tenant API key, Zernio account health; alerts by mail + WhatsApp (template `central_alert` via the ventas n8n relay) + healthchecks.io heartbeat | live |
| Soporte | tickets + internal API | **postponed** (techdebt `2026-11-12-central-phase3-support.md`) |
| Redes | Instagram @jonatanperez.ia.dev through **Zernio**: Cuentas, Bandeja (DMs), Automatizaciones (comment → DM with follower gate), Bienvenida (welcome workflow + ice breakers), Métricas (daily sync), Publicar (carousels, reels, images, stories; keyword automation tied on publish; catalog music on reels) | live — see `personal-brand-social-media` skill `references/central-redes.md` |

## Operating rules

- Merge only via the global `pr-merger` with Jonatan's «mergea» quoted; **«mergea» never authorizes a
  deploy** — a separate «deployá». Deploy only via the project agent `central-deployer`
  (`update-central.sh <sha>`, backup before migrations, rollback by SHA); the main session verifies.
- Read-only ops via `central-ops` (logs, SELECTs, backup, restart). Both agents live in
  `central/.claude/agents/` (junction in the workspace root `.claude/agents/central/`).
- Secrets live in `/opt/n8n/central/central.env` (0600) and `.env.local`; never printed or committed.
- Changing Zernio config (webhook registration, reconnecting the account) needs Jonatan's OK.

## Zernio gotchas worth remembering

- Connect URL must not carry `language` (400 outside the hosted WhatsApp signup).
- Catalog music (`audioConfiguration`) only on **reels** and only with **Facebook Login** (account linked
  to a Facebook Page: "Jonatan Perez IA DEV", reconnected 2026-11-15; same Zernio account id kept, so
  automations survived). Carousels/images/stories can't take music through the API — only in the IG app.
- A comment that doesn't match the keyword is a Zernio **miss** (`misses.samples` on
  `GET /v1/comment-automations/{id}`), not a failure; logs stay empty. Add typo variants as extra keywords.
- `${JSON.stringify(x)}::jsonb` stores a JSON string with postgres.js — use `::text::jsonb`.
