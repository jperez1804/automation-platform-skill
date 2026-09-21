# Provider mode + Chatwoot mirror

**What it is:** a way to sell a tenant **our Meta infrastructure without our bot**. We send the
campaign templates and own opt-out/suppression; every message is mirrored into the client's own
helpdesk, their agents answer from there, and their replies go out through our engine. Built for
**arka** (2026-09-16/17); Chatwoot is the first consumer but any **API-channel** helpdesk fits the
same shape.

**When to reach for it:** the client already has (or wants) their own inbox and team, says "we just
want you to send the messages", already used another provider (YCloud, 360dialog) with Chatwoot, or
wants to own the conversation for compliance/CRM reasons. It is also the honest answer to "can we
point your webhook at my n8n?" — never repoint a WABA webhook that a live campaign depends on;
mirror instead (see `arka/docs/ventas/fanout-webhook-esteban.md` for that conversation).

**What the tenant still gets from us:** template sending + ramp/caps, opt-out and the suppression
list, the 24h-window rule, `lead_log`/funnel/dashboard, the T1 "new lead" alert, and error notes
back into their inbox. What they lose: our wizard (no qualification, no scripted flow).

---

## Architecture

```
Runner: Send Template ──┬─→ Mark Sent
                        └─→ Call Chatwoot Bridge  {type:'outgoing', kind:'template', text: mirror_text}

Router: Normalize → dedup → lock → Determine Route ──┬─→ Route Switch → Send (bypass) → Persist → Release lock
   (mode=chatwoot: everything except opt-out is a    └─→ Call Chatwoot Bridge {type:'incoming'}
    silent suppress_send turn; opt-out still ours)

Chatwoot (API-channel inbox, webhook_url = ours)
   → v2-chatwoot-webhook → filter → [download attachment → upload to Meta /media]
   → POST /webhook/inbox {action:'send', …, media?} → sender → WhatsApp
   → on failure: private note back into the conversation
```

Three moving parts, all per-tenant, none of them touching the shared sender:

| Piece | Workflow | Role |
|---|---|---|
| Outbound mirror | `v2-chatwoot-bridge` (sub-workflow) | contact/conversation upsert + create message (text or attachment) |
| Inbound silence + mirror | router (`Determine Route`, `Prepare Chatwoot Mirror`, `Call Chatwoot Bridge`) | bot says nothing, event is mirrored |
| Return path | `v2-chatwoot-webhook` + `v2-inbox-webhook` | agent replies → WhatsApp, with notes on failure |

## Env (whitelist them under compose `environment:` — an `.env` var alone is invisible)

```
<TENANT>_CONVERSATION_MODE=chatwoot   # 'bot' restores the wizard with no redeploy — keep this escape hatch
CHATWOOT_BASE_URL=https://<host>
CHATWOOT_ACCOUNT_ID=1
CHATWOOT_INBOX_ID=<API-channel inbox id>
CHATWOOT_API_TOKEN=<profile access token of a user in that account>
CHATWOOT_WEBHOOK_SECRET=<openssl rand -hex 24>   # path/query secret of OUR webhook
```

## Router: making the bot silent without going blind

- `direct()` gains `suppressSend` → emits `suppress_send: true`. The existing plumbing does the rest:
  the sender's `Check Suppress Send` switch skips the Meta POST, the persister writes the **inbound
  row only**, the advisory lock still releases, and `v2-outreach-reconcile` still flips recipients to
  `replied` (it only needs the inbound row). The dashboard funnel keeps working with the bot off.
- In `chatwoot` mode: **opt-out unchanged** (suppression + confirmation reply — compliance is ours),
  everything else (defer, unsupported, free text) → silent mirror, route `chatwoot_mirror`.
- **First-reply alert:** no fresh `session_memory` row = first inbound in the TTL → set
  `handoff:true, handoff_target:'ventas', send_email_alert:true` so the persister's existing
  escalation + WA-template + email branch fires once per conversation. ⚠️ It fires for *any* first
  inbound, including spam (a phishing number triggered it on arka); restrict to campaign recipients
  if that becomes noisy.
- Mirror branch = **second output of `Determine Route`**, placed **below** the main chain: n8n v1
  sorts sibling branches by position and runs the top one depth-first to completion, so the lock
  releases before the (slow) mirror runs. `executeWorkflow` with `waitForSubWorkflow:false` +
  `onError: continueRegularOutput` — Chatwoot being down must never break the engine.
- Keep `text_body` readable for media (`📷 Imagen: <pie>`, `🎤 Nota de voz`): the dashboard renders
  `text_body` and never looks at `message_type`.

## Bridge: contact → conversation → message

1. `GET /contacts/search?q=+E164&include=contact_inboxes`; create with `POST /contacts {name,
   phone_number, inbox_id}` if missing (on 422 search again — race); PATCH the name when the stored
   one is generic and we now know the business name (`outreach.recipients.business_name` beats the
   Meta profile name).
2. Reuse the newest conversation with `inbox_id === INBOX_ID && status !== 'resolved'`; else
   `POST /conversations {source_id: phone, inbox_id, contact_id, status:'open'}`.
3. `POST /conversations/{id}/messages {content, message_type:'incoming'|'outgoing', private:false,
   content_attributes:{ mirror:'botargento', kind, wa_message_id }}`.

**The anti-echo marker is load-bearing.** Chatwoot fires `message_created` for messages *we* create
through the API too; without the marker our own outgoing mirrors would be sent to the contact again.
(Incoming mirrors are filtered earlier by `message_type`, but keep the marker on both.)

**Templates:** Meta never returns the rendered body, so the runner renders `mirror_text` from a local
`TEMPLATE_BODIES` map (`{{1}}` → business name, plus the header image URL and the button labels) with
a `[plantilla <name>] …` fallback for unmapped templates.

## Return path: Chatwoot → WhatsApp

- Chatwoot cannot sign webhooks or set headers → auth with a **query token**, fail closed (401).
  Configure it with `PATCH /api/v1/accounts/{a}/inboxes/{i} {channel:{webhook_url}}`.
- Respond 200 **first**, then do the work: Chatwoot retries and times out otherwise.
- Filter: `event==='message_created'` · `message_type==='outgoing'` (also `1`/`'1'`) · `!private` ·
  `inbox.id` matches (the account holds other projects' inboxes) · **no mirror marker** · non-empty
  content or an attachment.
- Phone: `conversation.meta.sender.phone_number` → fallback `conversation.contact_inbox.source_id`.
- Forward to our own `/webhook/inbox` (`action:'send'`, `X-Inbox-Token`) rather than calling Graph
  directly: that endpoint already enforces the suppression gate and the 24h window, logs
  `sent_by='human'`, and is what the dashboard uses. Map its failures to **private notes**:
  403 → unsubscribed, 409 → outside 24h, 502 → Meta error, 401 → bad token.
- **Loop one message at a time** (`Loop Items`, batch 1): parallel HTTP items arrive out of order.

## Attachments

**Inbound (WhatsApp → Chatwoot).** `Normalize Event` must keep `media_id / mime / voice / caption /
filename` (it classifies media as `unsupported` and drops the object by default — that's where the
information is lost). Then: Graph `GET /{media_id}` → **size gate before downloading** (`file_size`)
→ binary download (the URL needs the Bearer token and expires in minutes) → validate (reject HTML or
JSON error bodies — an expired URL returns 200 HTML) → `POST /conversations/{id}/messages` as
**multipart** with `attachments[]`; Chatwoot parses `content_attributes` sent as a form field. Any
failure → exactly **one** fallback text line ("🎤 Nota de voz recibida (no se pudo adjuntar: …)"),
never a silent drop and never two messages for one event.

**Outbound (Chatwoot → WhatsApp).** Chatwoot `data_url` downloads **anonymously** (signed redirect,
~5 min). Validate against Meta's limits, then **upload to `/{phone_number_id}/media` and send by
`id`** — not by `link`: uploading validates type/size synchronously, so the agent gets a real reason
in a private note instead of a silent non-delivery.

| Attachment | Sent as | Meta accepts | Max |
|---|---|---|---|
| image | `image` + caption | jpeg, png | 5 MB |
| file | `document` + caption + filename | any | 100 MB |
| audio | `audio` (no caption) | aac, amr, mpeg, mp4, ogg/opus | 16 MB |
| video | `video` + caption | mp4, 3gpp | 16 MB |

Anything else for its type (webp/gif/heic image, webm audio) → send as **document** + explanatory
note; there is no ffmpeg in the n8n container, so never promise conversion. Text travels as the
caption of the first caption-capable attachment; with an audio first, send the text as its own
message before it. Chatwoot's attachment payload has **no `content_type` and no filename** (derive
the name from the last path segment). Chatwoot 4.17's voice recorder produces **mp3**, so recorded
voice notes arrive as normal audio, not as a WhatsApp PTT bubble.

## Compliance (the part that bit us)

**The inbox `send` action must check `outreach.suppression` before sending — 403, fail-closed.**
arka shipped without it and an agent's "ok" from Chatwoot reached a contact who had opted out an hour
earlier. The same endpoint backs the dashboard, so the gap is not Chatwoot-specific: any tenant with
the two-way inbox has it until patched. Canonical fix (engine repo `v2-inbox-webhook.json`):
`Check Window` also returns `suppressed`, reading `outreach.suppression` only when `to_regclass`
finds it (via `query_to_xml(format(…))` so the name resolves at run time) — one webhook works for
inbound-only and outbound tenants; `Gate Window` answers 403 before the 24h 409.

Also tell the client, in writing, what the system does and doesn't block — their agents trust the
guide (`arka/docs/ventas/chatwoot-guia-esteban.md` is the template, artifact for sharing).

## Install checklist for a new tenant

1. Client creates an **API-channel inbox** and gives you: base URL, account id, inbox id, a profile
   access token. Verify with `GET /api/v1/profile` and `GET /accounts/{a}/inboxes` (the token is an
   admin's; other inboxes in the account belong to other projects — always filter by inbox id).
2. Generate `CHATWOOT_WEBHOOK_SECRET`; add all `CHATWOOT_*` + `<TENANT>_CONVERSATION_MODE` to `.env`
   **and** the compose `environment:` block; recreate the n8n container.
3. Import + activate `v2-chatwoot-bridge`, then patch router/runner (**order matters**: n8n 2.x
   refuses to PUT a workflow that references an unpublished sub-workflow).
4. Import + activate `v2-chatwoot-webhook`; `PATCH` the inbox `webhook_url` to
   `https://<tenant>.botargento.com.ar/webhook/chatwoot?token=<secret>`.
5. Confirm the suppression gate is present in that tenant's `v2-inbox-webhook`.
6. Smoke without touching real leads: fake `media_id` → fallback note; a real upload of a public
   jpg/pdf; a send to a number outside the window → 409; a send to a suppressed number → 403.
   Then a human E2E with two internal numbers, and delete the test contact/conversations.
7. Write the client guide; keep the mode flag documented as the rollback.

## Gotchas worth remembering

- Structural n8n changes here are GET→merge→PUT on the same id (never re-import: ids change and the
  `executeWorkflow` wiring breaks). `patch-wizard-live.mjs` only swaps Code-node `jsCode`.
- The n8n API cannot start a workflow run; smoke structural changes with a temporary webhook
  workflow and delete it afterwards.
- `Normalize Event`, `Prepare Chatwoot Mirror` and the bridge Code nodes belong in `_src/` + a
  `build.mjs` target, or the next session will hand-edit live JSON.
- Chatwoot conversations reopen as new ones once **resolved** — agents resolving threads is normal,
  don't treat it as an error.
- Known limits today: reopening a >24h conversation needs a template (not exposed in Chatwoot), and
  a Meta 4xx on the final send still surfaces as "error HTTP 500" (the shared sender has no
  `onError`; fixing it would suppress error-handler alerts for the router path, so it was left).

**Live reference implementation:** tenant `arka` — `C:\Desarollo\jperez\arkasystems\ArkaSystems
Automation\` (`n8n/wizards/_src/chatwoot-*.js`, `v2-chatwoot-bridge.json`,
`v2-chatwoot-webhook.json`; log in `docs/ventas/infra-status.md` 2026-09-16/17; commits `fff794f`,
`6e4503d`, `25028dc`).
