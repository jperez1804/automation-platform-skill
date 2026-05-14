# Reference instance: Bot Argento (real estate)

> **Important framing.** This file documents Bot Argento as the **reference instance** of the platform — the first concrete deployment, in the real-estate vertical. It is NOT canonical. Other agencies on the platform will have their own brand, copy, vertical config, and inventory shape. Treat the contents below as **example, not requirement**. When the user asks "how should the brand voice / vertical config / pricing look?", remind them this is one example and the platform supports any.

## What Bot Argento is

A WhatsApp/Instagram automation service for Latin American (primarily Argentine) businesses. Founder-led, sold per-month with a launch discount. Currently a single deployed tenant (`client1`, real-estate brokerage).

- **Domain:** `botargento.com.ar`
- **Founder:** Jonatan Pérez, Buenos Aires
- **Credentials:** Meta Tech Provider (badge on landing page), OpenAI partner badge
- **Contact:** info@botargento.com.ar / WhatsApp `+54 9 11 2191 1850` / Calendly link `calendar.app.google/xtAn39HqKc7nDYmA7`

## Real-estate vertical config (the v1 vertical)

Currently the only `src/config/verticals/<vertical>.ts` shipped. Defines:

**Intent menu (the WhatsApp main menu):**
- `1) Ventas` — sales (search wizard)
- `2) Alquileres` — rentals (search wizard, same shape as sales)
- `3) Tasaciones` — valuations (multi-step intake form)
- `4) Administración / Propietarios` — direct routing
- `5) Otras Consultas` — general inquiry form
- `6) Emprendimientos` — investment projects listing
- `0)` — return to main menu

**Inventory data sources (real-estate flavor):**
- Google Sheets ID: `1u4YkqBlPSN6UrUW_ra4hYWuRzEj8fxNp3xqWjjV1-LY`
- Tabs: `inventory_sales`, `inventory_rents`, `emprendimientos`
- ~250 sample listings each in sales + rents
- 8 zones (Buenos Aires neighborhoods), 2 main property types, multiple bedroom counts

**Qualification snapshot fields collected:**
- `selected_zone`, `selected_property_type`, `selected_bedrooms`, `selected_price_range`
- `lead_name`, `handoff_intent`, `preferred_contact_slot`
- `budget_amount`, `budget_currency` (default USD), `payment_mode`, `purchase_timing`

**Handoff targets:** `valuations`, `sales`, `rents`, `questions`, `owners`. Each has an optional internal WhatsApp number env var (`VALUATIONS_WHATSAPP_NUMBER`, etc.) for team notifications.

## Brand voice (Spanish, founder-direct)

Verbatim copy snippets from `landingpage/index.html`. Tone: direct, outcome-driven, non-corporate. Pain-first framing. Plain language, low jargon.

> **Hero kicker:** "¿Cuántas oportunidades estás perdiendo hoy?"
> **Hero pitch:** "BotArgento responde consultas, califica oportunidades y deriva a tu equipo cuando hace falta."
> **Subhead:** "IA, flujos y reglas de negocio trabajando 24/7 sobre tus canales."
> **Differentiator:** "Cada automatización es a medida, no genérica."
> **About:** "Mi enfoque combina implementación, reglas de negocio e integraciones con una mirada práctica del proceso comercial y de soporte."

**Stats called out in hero:** 24/7 + < 5 días setup. Proof badges: Meta Technology Provider + OpenAI.

## Pricing (Bot Argento's specific pricing — not canonical)

- **Standard:** ARS 100,000 / month, ongoing service
- **Launch offer:** ARS 50,000 first month (50% off) + free setup + personalized training
- Includes: automation, lead qualification, handoff setup, integrations, adjustments
- No per-message pricing
- Lead capture flow: no form. CTA → Google Calendar booking. Secondary → WhatsApp FAB with prefilled message.

## Brand visual identity

**Colors (CSS vars in `landingpage/styles.css`):**
- Primary: `#75aadb` (light blue / Argentine "celeste")
- Accent: `#e8b84b` (gold)
- Success / WhatsApp: `#25d366`
- Background: `#050e1f` (deep navy)

**Typography (Google Fonts):**
- Headings: **Sora** (weights 600, 700, 800)
- Body: **Geist** (weights 300–700)

**Logo:** `icon-concept-mando-stars.svg` — gamepad + stars concept, 38×38px header icon.

**Visual language:** aurora blobs, gradient overlays, particle canvas in hero, card-based layout, glass-morphism borders.

## Landing page sections (the template structure)

1. **Hero** — gradient text, animated particles, 24/7 + <5 días stats, Meta/OpenAI proof badges
2. **Features (6 cards)** — Instagram/WhatsApp, Flows, Capture, Handoff, Analytics, Integrations
3. **How It Works (3 steps)** — Connect channels → Define rules → Activate & optimize
4. **Pricing (single card)** — Monthly plan + launch offer ribbon
5. **FAQ (6 questions)** — 24/7 operation, no code needed, channels, AI usage, integrations, adaptability
6. **About Me (founder card)** — Jonatan Pérez photo, Meta Technology Provider badge, Buenos Aires, LinkedIn CTA
7. **Contact / CTA** — "Demo de diagnóstico" → Google Calendar
8. **Footer** — email, Privacy, Terms, Data Deletion

Same structure works for any agency — swap copy, colors, calendar link, WhatsApp number, logo.

## Current production state (snapshot — verify before acting)

**As of 2026-05-02** (source: dashboard project memory `project_theming_rollout_2026-05-02.md`):

- Only `client1` is deployed on the production VPS
- Image digest: `sha256:27c7c14e3928…`
- Migration `0002_app_settings.sql` applied with back-fill `primary_color='#3b82f6'`
- `jonatanperez1804@gmail.com` is `admin` on `client1`
- `info@botargento.com.ar` is `viewer` on `client1`
- `client1` listed in `/opt/scripts/tenants.txt` (so `tenant=all` deploys include it)

**Always verify** before recommending — production state changes. The live source is `git log` on the dashboard repo + `ssh vps` queries against `n8n-client1-postgres`.

## What to use this file for vs not for

**Use for:**
- "Show me an example of how the brand is wired" → point at the `#75aadb`/`#e8b84b` palette + Sora/Geist + the verbatim copy snippets above.
- "What's an example vertical config?" → real-estate intent menu above + `inventory` Sheets tab structure.
- "What's the current production status?" → 2026-05-02 snapshot, but flag that it should be verified.

**Don't use for:**
- Defining a *new* agency's brand — that comes from the new agency, not from Bot Argento. Cloning Bot Argento's palette into a competing agency would be wrong.
- Assuming all agencies sell at ARS 100k/mo — Bot Argento's pricing reflects Argentine market positioning. Other agencies will price differently.
- Treating real-estate intents (`ventas`/`alquileres`/`tasaciones`) as the canonical menu — they're real-estate-specific.
