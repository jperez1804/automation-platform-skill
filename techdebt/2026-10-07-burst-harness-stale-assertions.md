# Burst harness: 3 stale assertions (ventas)

**Opened 2026-10-07** (known since 2026-10-02). `Sales Automation/scripts/burst/harness-burst.mjs` reports 62/65: the 3 failures are **pre-existing** — they still expect the «¿rubro?» question that the ventas wizard stopped asking campaign prospects on 2026-09-25. The wizard is right; the assertions are stale.

**Fix:** update the 3 expectations to the current first step («¿hoy cómo atendés?»), re-run, expect 65/65. The main harness `scripts/harness-ventas.mjs` is green (36/36).
