# Central phase 3 (Soporte) postponed

**Opened 2026-11-12.** Jonatan liked the plan but does not want it built yet; phase 4 (Redes) goes first. Full design: `central/docs/BLUEPRINT.md` § Fase 3, plus the details agreed in chat:

- `migrations/0005_support.sql` (number it whatever is next when picked up): `maintenance_plans` (one per client, optional; defaults L-V 9-19, critical 8 h / rest 48 h, warranty, includes / excludes), `tickets` (impact bajo·medio·alto·critico, status abierta·en_curso·esperando_cliente·resuelta·cerrada, origin manual·monitor·n8n·whatsapp, `response_due_at`, `first_response_at`, `resolved_at`, `external_ref` unique, `assigned_to`, `contact_wa_id`), `ticket_events` (timeline). SLA set by trigger on insert; first comment or «en curso» stamps the first response; `error_to_ticket` (down/crashed → alto, else medio; idempotent) and `errors.ticket_id` FK; audit everything.
- Pages: `/soporte` (filters, SLA chip a tiempo / por vencer <2 h / vencido, KPIs), `/soporte/nuevo`, `/soporte/[id]` with timeline + composer, «Soporte» tab in the client file, «Crear ticket» on `/salud/errores/[id]`, counts on Inicio, sidebar entry. Port from `crm-central/central/db/migraciones/0005_mantenimiento.sql` and `0009_monitor.sql` (`error_a_incidencia`).
- Internal API (contract already in `central/docs/api-interna.md`): `GET /api/internal/clients/lookup?phone=`, `POST /api/internal/tickets`. Wiring the ventas router («soporte» → ticket) is a separate deploy with its own OK.
- Who creates tickets in v1: Jonatan by hand, or from a Salud error with one click. Nothing opens tickets automatically.

**Open decisions to ask when it is picked up:** SLA in calendar hours (recommended) or business hours; mail for new critical tickets and overdue ones, or no ticket mail at all. WhatsApp stays only for down/recovered.

Close this file when phase 3 ships.
