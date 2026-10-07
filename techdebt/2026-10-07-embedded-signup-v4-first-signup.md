# First real Embedded Signup v4 signup not yet observed

**Opened 2026-10-07.** The onboarding page went live on v4 (config `1423827086618896`, `extras: { setup: {}, version: 'v4' }`) on 2026-10-07 and the dialog was verified up to the phone-number screen, but **no signup has gone all the way through** (`/complete` → token exchange → assets saved) on v4 — there was no spare number to test with.

**When the next client onboards:** check the backend session reaches `assets_saved`. If it fails, get the Session ID shown on the page and read that session's events (`raw_payload` holds Meta's message event). Rollback: `META_CONFIG_ID=1842361349779469` on Railway + the previous `whatsapp.html` (Bitbucket `main` before `dc2045e`).

Close this file once one real signup reaches `assets_saved`.
