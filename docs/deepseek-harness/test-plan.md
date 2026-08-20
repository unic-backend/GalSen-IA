# D11.1 — Test plan (Phase 10)

**Written**: 2026-08-20. **Defines** tests; writes none. Phase 8's decision was
Option C and **implementation is not authorized** (ADR-035), so this document is
what must exist *before* a first line of adapter code, not alongside it.

Phase 10's rule, quoted: *"Run the existing test suite before and after any
implementation. Do not delete, disable, weaken, or bypass existing tests."*

---

## What already exists, measured

```bash
python -m pytest tests/test_coding_adapters.py tests/test_coding_engine.py \
                 tests/test_api_coding.py -q
# → 141 passed, 3 deselected in 15.56s
```

**141 tests already cover the coding layer**, with classes per adapter —
`TestAiderDisponibilite`, `TestAiderCommande`, `TestAiderNormalisation`,
`TestSweAgent`, `TestOpenHands`, `TestVivants`.

`INFERENCE`: a fourth adapter does not need a new test *architecture*. It needs
**the same classes, for a fourth engine**, plus the seven cross-cutting suites
below. That is another consequence of ADR-028's seam being real.

---

## The thirteen suites Phase 10 requires

Each names the file it would live in, what it asserts, and — where it matters —
the failure it exists to catch.

### 1. Provider routing → `tests/test_coding_adapters.py`

- `dsh` declares its capabilities and is routed **by capability, never by name**.
- A task whose inferred capability is `dsh`'s specialty scores it highest.
- **The failure this catches**: a router that special-cases the new engine.
  `router.py`'s own docstring forbids it — *"ne connaît aucun des trois moteurs
  par son nom"* — and a test is what keeps that true for a fourth.

### 2. Fallback → `tests/test_coding_engine.py`

- With `dsh` unavailable, routing still returns a decision naming the remaining
  candidates.
- With **all four** unavailable, the engine reports unavailability with a reason
  per engine — the state D05 measured today, which must not regress.

### 3. Failure recovery → `tests/test_coding_engine.py`

- A DSH process that exits non-zero produces a structured `CodingTaskResult`
  with a status, never an exception crossing the adapter boundary.
- A timeout is reported as a timeout, distinct from a failure.

### 4. Permissions → `tests/test_deepseek_adapter_permissions.py` *(new)*

- Every tool call the adapter forwards passes `authorize(tool_id, actor)`.
- **Only the four allowlisted tools** — `rag`, `embeddings`, `web_search`,
  `metrics` — are reachable; a fifth is refused with the exposure reason.
- **The failure this catches**: an adapter that widens its own allowlist. The
  assertion is on the *table*, so adding a row is a visible diff.

### 5. Security → same file

- The adapter never passes an environment variable outside
  `ENVIRONMENT_TRANSMIS` (`PATH, LANG, LC_ALL, TZ, HOME, TMPDIR`).
- No credential appears in any recorded output — asserted through
  `src/security/redaction.py`, names not values.
- **The sandbox is asserted to report, not to confine**: on a host without
  Landlock, the test asserts DSH is *reported unconfined*, matching its own rule
  that *"silent unconfined passthrough is never legal"*. **This test must not
  assert confinement on a host that cannot provide it** — that would pin a
  fabricated guarantee.

### 6. Tool execution → `tests/test_coding_adapters.py`

- A forwarded tool call produces the same result as the direct call, and an
  `AuditEvent` with the **same `request_id`**.

### 7. Session continuity → `tests/test_deepseek_adapter_session.py` *(new)*

- One session per task: the session is created by the adapter and ended with the
  task.
- **No session survives the task** — the assertion that makes DSH's resume
  behaviour inert, and the one that depends on the `UNKNOWN` still open since
  D00.2.
- **This suite cannot be written until condition 3 closes.** Recorded as
  blocked rather than sketched.

### 8. Context preservation → same file

- The subject travels with the task and is never read back from a DSH session
  identifier.
- A task without a subject is refused before the adapter is called.

### 9. Coding tasks → `tests/test_deepseek_adapter_tasks.py` *(new, and gated)*

- The same fixture task set through `aider` and through `dsh`, asserting on
  **structure** — a result is produced, a status is set, edits are parseable —
  **never on quality**.
- **Quality is not a test.** It is a measurement, it belongs to ADR-035's
  condition 1, and asserting a quality threshold here would pin a number nobody
  measured.

### 10. Regression → the existing suite, unchanged

- `python -m pytest -q` before and after, and the counts compared.
- **Nothing is deleted, disabled, weakened or bypassed.** The current baseline
  is **6 958 passed, 12 skipped, 1 failed** — the failure being the `v0.1.0`
  tag, which fails identically on `main`.

### 11. Latency → `tests/test_deepseek_adapter_perf.py` *(new, and honest)*

- Measures **adapter overhead**: the round trip minus the direct call.
- **Asserts a shape, not a threshold** — that the figure is produced and
  recorded with the machine that produced it. A hard millisecond bound would
  fail on a loaded runner and be weakened rather than fixed, which
  `.claude/rules/verification.md` names as the way tests die.

### 12. Resource usage → same file

- Peak RSS with and without the adapter, recorded.
- Node's own footprint recorded separately, since it is a second runtime.

### 13. Removal of the adapter → `tests/test_coding_engine.py`

- With the `dsh` declaration removed, the suite passes unchanged and routing
  works over the remaining three.
- **The failure this catches**: coupling that accumulates quietly. This is the
  test that keeps ADR-035's *"removable by deleting a declaration"* true rather
  than merely stated.

---

## Two suites that cannot be written yet, and why

| Suite | Blocked by |
|---|---|
| **7 — session continuity** | what `dsh-headless` persists is `UNKNOWN` (D00.2, unclosed after three phases) |
| **9 — coding tasks** | requires an install this environment cannot perform and the directive forbids |

Naming them as blocked is the point. A test plan that lists thirteen suites as
though all thirteen were writable today would be the first fabrication of the
programme.

## The order

1. Run `pytest -q`, record the baseline.
2. Write suites **1, 2, 3, 13** — they need no DSH at all, and they assert the
   properties that make the experiment reversible.
3. Close ADR-035's three conditions.
4. Write **4, 5, 6, 8, 11, 12**.
5. Write **7** and **9** last, once conditions 3 and 1 have closed.
6. Run `pytest -q` again; compare.

**Step 2 is worth noticing**: four of the thirteen suites can be written *before
anything is installed*, because they test **our** seam rather than their
harness. If they were written and the integration never happened, they would
still be worth having — they assert that the coding router stays name-blind and
that an adapter is removable.
