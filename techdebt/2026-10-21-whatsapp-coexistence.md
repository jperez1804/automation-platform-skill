# Check: WhatsApp Coexistence availability for Argentina — due 2026-10-21

**Opened 2026-10-07.** Coexistence = a client keeps using the WhatsApp Business app on their number **and** the bot runs on the same number through the API (Embedded Signup with `featureType: 'whatsapp_business_app_onboarding'`).

## Where it stands

- It **does not work** for us today: every attempt (our test page with the v4 config `1423827086618896`, with and without `sessionInfoVersion: '3'`, and **Meta's own launcher** in the App Dashboard) shows the plain "new number + SMS/call" screen. Tech Provider complete, App Review approved, webhook fields `history` / `smb_app_state_sync` / `smb_message_echoes` subscribed, app 2.26, Argentine number.
- Meta's **support AI** said Argentina isn't a supported region, then contradicted itself on which regions are (claimed "only EEA, UK, Japan, Australia", which looks inverted — those were historically the exclusions). **Not confirmed by an official source.** Jonatan asked support for the official country list or a human agent.
- Requirements it listed: number active in the app **≥ 7 days**; **no Marketing Messages (MM Lite)** on the number.

Details: `references/meta-tech-provider.md` §Coexistence.

## Meta support case

**Case 29343441661908513** (Direct Support, opened 2026-10-12 by Jonatan, topic «WhatsApp Tech Provider: Onboarding», type «Embedded Signup - Coexistence Onboarding»): https://business.facebook.com/direct-support/case-detail/29343441661908513/?business_id=807638368889424 — asks whether coexistence is available for Argentina, an ETA, the official country list, whether Marketing Messages in our config matters, and a beta/waitlist. Evidence attached: Meta's own launcher (config 1423827086618896, v4, session info 3, feature type «Registro de app de WhatsApp Business»), number 5491165978398 (sales number on the app), End Client BM 807638368889424 (BotArgento). If the answer is «not available», follow up with a «WABiz: Feature Request» case.

### Reply received 2026-10-13 — contradicts the changelog

Support says: not available for Argentina, no ETA, "limited to EEA, UK, Japan, Australia, Nigeria and South Africa"; no country list published (watch the changelog); no beta/waitlist; **Marketing Messages / MM Lite on the config or number makes it ineligible**; app ≥ 2.24.17; number active ≥ 7 days.

The official changelog (`…/whatsapp/changelog`) says otherwise: **2025-02-11** Coexistence launched with no country limit in the entry; **2025-10-23** it was *added* for Australia, Japan, Philippines, Russia, South Korea, Turkey, EEA/EU, UK, i.e. the regions excluded at launch. Nigeria and South Africa appear in no availability entry. The doc page lists no country limits at all, only app ≥ 2.24.17, Tech Provider, and a working webhook. Support's list looks like the **old exclusion list read backwards** (second time it happens). So Argentina is probably **not** the blocker, and the likeliest real cause is **Marketing Messages in config `1423827086618896`**.

**Next test (cheap, no production impact):** Jonatan created config **`28469481039412526`** on 2026-10-13 (Cloud API only, Cuentas de WhatsApp with default Administrar, the two whatsapp_* permissions; test only, NOT in Railway). Test it with Meta's launcher (v4, session info 3, «Registro de app de WhatsApp Business») with the sales number (≥ 7 days on the app from 2026-10-14). Cancel at any SMS/call code screen. If Coexistence appears → follow «If it's available». If not, reply on the case quoting the 2025-10-23 changelog entry and ask for a human agent.

**Result 2026-10-13 (number at 6 days on the app):** still NOT offered. With config `28469481039412526` + `whatsapp_business_app_onboarding` + v4 + session info 3 (dialog `facebook.com/v26.0/dialog/oauth`), the first step went straight to «Agrega tu número de teléfono de WhatsApp» with only «Crea uno nuevo» / «número virtual»; no portfolio step, no option to connect the app. Session ID `01a1353d-feb8-73cb-aa81-af93aa0665c3` (give it to Meta). Cancelled. **✅ 2026-10-13 — COEXISTENCE WORKS IN ARGENTINA.** Meta's launcher, config `28469481039412526` (Cloud API only), v4, session info 3, `whatsapp_business_app_onboarding`, «Crea uno nuevo» + typed +5491165978398 → **«Verifica los detalles de tu cuenta»** with the app's business profile (Botargento Ventas), i.e. the Coexistence branch (session `01a1354b-2a2c-789d-9735-2b4e9d54e18e`). Meta support's region list was wrong. **Same result with the production config `1423827086618896` (with Marketing Messages)** → MM is NOT the blocker; neither config matters. Why 07-10 went to the SMS screen is unknown: the number had been created in the app that same day, and probably wasn't recognized yet. Open question: does the production page (extras `{ setup: {}, version: 'v4' }`, **no featureType**) also switch to Coexistence when an app number is typed? If yes, real clients can land in Coexistence today and the backend doesn't handle `FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING` (and would call `/register`). Test: launcher with tipo de función «Ninguna» + type the app number, stop at the profile screen.

**Correction (v4 public preview doc, `…/embedded-signup/version-4-public-preview`):** in v4 there is **no separate «connect the app» option**. The flow is «Phone Number First»: pick «Crea uno nuevo», type the number, and if it is a WhatsApp Business app number Meta switches to Coexistence by itself. You then see the business profile → portfolio → **QR scanned from the app** (also sent as a WhatsApp message) → WABA name/time zone → terms → success event with WABA id + phone number id. If it goes to the **SMS/voice code** screen instead, the number was not accepted for Coexistence → cancel there. So the 13-10 test stopped one screen too early. Re-test with config `28469481039412526` by typing the number. (The 07-10 test on our page with the MM config reached the SMS screen.)

(Superseded:) The 7-day rule does **not** explain it: the «connect existing app» option is shown *before* any number is entered, so Meta can't be gating it on the number's age (that check, if any, happens after entering the number). The gate is on Meta's side (app / portfolio / user region). → Jonatan replies on the case with the changelog entry and this session ID; no need to wait.

## How to check on 2026-10-21

0. **First, ask Jonatan for the reply on case 29343441661908513** (only he can open Direct Support).

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
