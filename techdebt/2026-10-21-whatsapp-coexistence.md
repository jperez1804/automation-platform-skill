# Check: WhatsApp Coexistence availability for Argentina — due 2026-10-21

**Opened 2026-10-07.** Coexistence = a client keeps using the WhatsApp Business app on their number **and** the bot runs on the same number through the API (Embedded Signup with `featureType: 'whatsapp_business_app_onboarding'`).

## Where it stands

- It **does not work** for us today: every attempt (our test page with the v4 config `1423827086618896`, with and without `sessionInfoVersion: '3'`, and **Meta's own launcher** in the App Dashboard) shows the plain "new number + SMS/call" screen. Tech Provider complete, App Review approved, webhook fields `history` / `smb_app_state_sync` / `smb_message_echoes` subscribed, app 2.26, Argentine number.
- Meta's **support AI** said Argentina isn't a supported region, then contradicted itself on which regions are (claimed "only EEA, UK, Japan, Australia", which looks inverted — those were historically the exclusions). **Not confirmed by an official source.** Jonatan asked support for the official country list or a human agent.
- Requirements it listed: number active in the app **≥ 7 days**; **no Marketing Messages (MM Lite)** on the number.

Details: `references/meta-tech-provider.md` §Coexistence.

## How to check on 2026-10-21

1. Ask Jonatan whether Meta support answered (official doc link / human agent / date for Argentina).
2. Re-read Meta's doc: `https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users` — look for a supported-countries list.
3. Re-test with **Meta's own launcher** (App Dashboard → Use cases → Conectar en WhatsApp → Administrador de registro insertado → «Lanzamiento del registro insertado»): v4, session info 3, «Registro de app de WhatsApp Business», using Jonatan's sales number (created in the app on 2026-10-07, so ≥ 7 days by then). **Cancel if it asks for an SMS/call code** — that would move the number off the app.

## If it's available

Plan in phases, each with Jonatan's OK:
1. **Config:** probably a new Login for Business config with **Cloud API only** (ours includes Marketing Messages). Test with Jonatan's sales number.
2. **Onboarding page + backend:** two buttons («Tengo un número nuevo» / «Ya uso la app de WhatsApp Business»); handle `FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING` (carries `phone_number_id`, `waba_id`, `business_id`); **skip `/register`**; call `POST /<PHONE_NUMBER_ID>/smb_app_data` with `sync_type` `smb_app_state_sync` and `history` **within 24 h**.
3. **Engine (n8n):** `smb_message_echoes` (the owner answering from the app) must pause the bot like a takeover; the router must ignore `history` / `smb_app_state_sync` payloads. Limits: 20 msg/s, no groups.
4. **Dashboard:** history and contacts into the panel (optional).
5. Subscribe `account_update` too (disconnection arrives as `PARTNER_REMOVED`).

## If it's still not available

Set a new check date (rename the file), and keep telling clients the two options: delete the account in the app and onboard the number by SMS (answers from the dashboard inbox), or a new number for the bot.
