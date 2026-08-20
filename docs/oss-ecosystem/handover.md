# Handover — OPEN-SOURCE ECOSYSTEM AUDIT, stopped at 14 of 22 phases

**Written**: 2026-08-20, at the end of E06.1, because the session's budget ran
out mid-programme. **This file exists so the next session asks the user
nothing.** Read it, then start at E06.2.

---

## 1. Where exactly the work stopped

```
VOLET            OPEN-SOURCE ECOSYSTEM AUDIT & INTEGRATION
Plan             12 chapitres → 22 phases   (docs/memory/phase-plan.md)
Terminées        14 : E01.1 E01.2 E02.1 E02.2 E03.1 E03.2 E03.3 E03.4
                      E04.1 E04.2 E04.3 E04.4 E05 E06.1
Phase courante   E06.2 — attend une confirmation de l'utilisateur
Restantes        8 : E06.2 E07 E08 E09 E10 E11 E12.1 E12.2
Cadence          deux phases par tour (convenue le 2026-08-19)
Branche          claude/unit-tests-notification-search-file-4z0ok1
Dernier commit   f52b143  — tout est poussé, rien en local
```

**Nothing is half-written.** Every finished phase is committed, pushed, and
followed by a full regression. There is no partial document to repair.

---

## 2. The first three commands of the next session

```bash
git fetch origin
git reset --hard origin/claude/unit-tests-notification-search-file-4z0ok1
ls docs/oss-ecosystem/          # 14 fichiers attendus, dont celui-ci
```

**Why this matters, measured twice already**: this environment recycles its
container, and the local clone silently falls back to an old commit
(`8879e8b`). A missing `docs/oss-ecosystem/` means a stale clone, **never a lost
programme**. Do the fetch before concluding anything.

---

## 3. The rules this programme runs under — do not renegotiate them

| Rule | Source |
|---|---|
| **§12: implement nothing.** Zero lines of `src/`, zero dependencies, zero tests added, altered or removed | the directive |
| **One turn = two phases**, then stop with `Je continue ?` | `.claude/rules/phase-protocol.md` + the agreed cadence |
| **Every phase ends with a full regression**, never a compile | `.claude/rules/post-integration-validation.md` |
| Never `INTEGRATE` on popularity | §3 |
| Unreadable source → `UNKNOWN` **with the exact failure**, never memory | §7, §8, §10 |
| Answer the user in French; docs in English; comments in French | `CLAUDE.md` |

Verification command used at every phase boundary, and its expected result:

```bash
git diff --stat origin/main -- src/ tests/    # doit être VIDE
ruff check .                                   # All checks passed!
python -m pytest -q
# → 1 failed, 6967 passed, 12 skipped, 3 deselected
```

**The single failure is expected and is not ours**:
`tests/test_release_check.py::TestEtiquette::test_l_etiquette_de_la_version_courante_existe_bien`.
The `v0.1.0` tag has never been pushed; it fails identically on `main` and in
CI. **Do not fix it, do not skip it, do not mention it as a regression.**

---

## 4. This host, measured — not assumptions

| Fact | Measured |
|---|---|
| GPU | **none** (`ls /dev/nvidia*` → nothing) |
| CPU / RAM / disk | 4 CPUs · ~15 GB free · 28 GB free |
| `ffmpeg` | **`command not found`** (2026-08-20) |
| Python | **3.11.15** — `pyproject.toml` pins `py311`, CI runs 3.11 |
| `raw.githubusercontent.com` | **200** — licence files are readable this way |
| `pypi.org` | **200** — package metadata readable |
| `api.github.com` | **403** — stars, releases, issue counts are `UNKNOWN` |
| Hugging Face | **403** — no model weights can be fetched |

Consequence already recorded: vLLM, SGLang and Unsloth **cannot be benchmarked
here**. Every performance cell for them is `UNKNOWN`, and inventing a number is
the one thing this programme must never do.

---

## 5. What the fourteen finished phases established

So the next session does **not** re-derive any of it.

### The twelve candidates, final column

| Project | Verdict |
|---|---|
| Transformers | `ALREADY_PRESENT` — training only, imported inside a function body |
| vLLM | `ALREADY_PRESENT` — the platform's own error message names it *and its port* |
| SGLang | `OPTIONAL` — same seam, unnamed |
| llama.cpp | `OPTIONAL` — already one layer down, since Ollama is built on it |
| LiteLLM | `DEFER` — and **`OUTSIDE`** if it ever enters |
| LangGraph | `KEEP_EXISTING` |
| LlamaIndex | `REJECT` |
| Qdrant | `DEFER` — two named conditions, neither true |
| OpenHands | `ALREADY_PRESENT` — one of three declared adapters |
| Unsloth | `DEFER` — needs a GPU host, an authorised dataset, a family to train |
| whisper.cpp | `KEEP_EXISTING` |
| Open WebUI | `REJECT` — licence **and** architecture |

**Zero `INTEGRATE` out of twelve.** 2 `NO OVERLAP`, 4 `PARTIAL`, 4 `HIGH`,
2 `DIRECT DUPLICATE`.

### The three measurements that carry the programme

1. **Vector search.** `SQLiteVectorStore.search()` re-reads every row and calls
   `json.loads` per row on **every query** — ADR-015's premise, *"une matrice en
   mémoire"*, is not what the code does.

   | Vectors | current | cached matrix | factor |
   |---:|---:|---:|---:|
   | 10 000 | 1 232 ms | **0.37 ms** | 3 360 × |
   | 100 000 | 13 132 ms | **3.88 ms** | 3 388 × |

   Matrix RAM at 100 000: **153.6 MB**. *(E01 measured 1 943 / 27 944 ms on the
   same current path; two runs on a shared 4-CPU host vary by about two. The
   conclusion holds either way.)*
   **This settles Qdrant**: a caching bug was about to be blamed on a database.

2. **Dependency weight.** llama.cpp bindings **4** unconditional dependencies,
   Transformers **9** (torch is an *extra*), vLLM **97 declared** including
   `torch==2.13.0` and a CUDA stack, SGLang **128** including
   `cuda-python>=13.0`. Declared, not optional.

3. **RBAC.** `POST /coding/task` is gated by `Permission.TOOL_EXECUTE`, held by
   `admin`, `operator` **and `user`**. `resolve_workspace()` accepts **any
   existing directory on the host**; `allow_network`, `allow_push`, `dry_run`
   come from the request body; `GALSEN_CODING_REQUIRE_CONTAINER` defaults off.

### The two findings about GalSen IA itself — Ch. 07 must carry them

**Neither is fixed. Both are named. §12 forbids fixing them here.**

1. **The vector-search caching bug** (measurement 1 above). The fix that
   suggests itself — a matrix cached and invalidated on write — is **a
   suggestion, not a task** (`.claude/rules/spec-driven-governance.md`).
2. **§4F's constraint is unmet**: an ordinary `user` can submit a
   repository-modifying task naming any host directory. **The exposure is
   latent** — all three coding engines are unavailable, so nothing executes —
   and it must be reported as latent, never as exploitable. Suggested shape,
   again *not a task*: a distinct `CODE_EXECUTE` permission for `operator` and
   `admin`, plus a permitted workspace root.

Plus a third, smaller: **`litellm==1.81.10` is installed in this environment,
declared by no requirements file and imported by nothing.** Unowned, not
dangerous. This repository did not install it, so removing it is not this
programme's call.

### Two licence rows that are not clean

| Project | Its manifest says | Its `LICENSE` file says |
|---|---|---|
| **LiteLLM** | `MIT` | MIT **except `enterprise/`**, whose licence file returns **404** (fetched 2026-08-20) |
| **Open WebUI** | `Other/Proprietary License` | BSD-3-Clause **+ clause 4**: no rebranding above **50 end users / 30 days** |

Both were found only by reading the file. For LiteLLM the manifest was the
*more permissive* of the two readings — which is why §8's rule is that a
manifest is a declaration and a file is a grant.

---

## 6. What each remaining phase must do

**E06.2 — licence matrix, part 2.** Six projects: LlamaIndex, Qdrant,
OpenHands, Unsloth, whisper.cpp, Open WebUI. Same columns as
`licence-matrix.md` part 1 — name, version, commercial use, redistribution,
attribution, modification, patent grant, model-weight restrictions, notable
condition, compatibility with ADR-036. **The six licence files were already
fetched and verified on 2026-08-20**:

```
langchain-ai/langgraph    MIT — Copyright (c) 2024 LangChain, Inc.
run-llama/llama_index     MIT — Copyright (c) Jerry Liu
qdrant/qdrant             Apache License 2.0
All-Hands-AI/OpenHands    MIT — Copyright © 2025 OpenHands contributors
unslothai/unsloth         Apache License 2.0
ggml-org/whisper.cpp      MIT — Copyright (c) 2023-2026 The ggml authors
```

Re-fetch to confirm; they are cheap and `raw.githubusercontent.com` answers.

**E07 — security audit (§9).** Dependency risk, arbitrary code execution,
network access, credential handling, sandboxing, filesystem access, model
download behaviour, remote execution, tool execution, prompt-injection exposure,
data exfiltration. **This is where the three GalSen IA findings land.**
Existing material to reuse rather than rewrite: `src/sandbox/policy.py`
(`ENVIRONMENT_TRANSMIS` = six variables), `src/tool/authorization.py`,
`src/security/trust.py`, `src/security/redaction.py`, `src/plugins/review.py`,
`tests/test_sovereignty_subordinate_runtimes.py`.

**E08 — performance audit (§10).** Report only what was measured: the three
vector-search scales, the dependency counts, the host figures. Everything about
vLLM / SGLang / Unsloth stays `UNKNOWN`. **Never fabricate a missing figure.**

**E09 — provider independence + minimum architecture (§6, §11).** The answer
the evidence already points to: the minimum architecture is **the current one**,
with a documentation gap named — the deployment docs should say what the
unavailability message already says, that any OpenAI-compatible server serves
this platform. Writing those docs is **not** in scope.

**E10 — feasibility gates (§7).** The fourteen questions, applied per candidate.
Insufficient evidence → `UNKNOWN`, never a guess.

**E11 — integration plan and order (§11, §12).** With zero `INTEGRATE`, this
chapter's honest output is *what would be done first if anything were ever
authorised*, plus the explicit statement that **nothing is authorised**.

**E12.1 — the ADR.** Next free number is **ADR-037** (36 ADRs exist, ADR-036 is
the newest). Suggested title in the house style:
`037-the-twelve-are-audited-and-none-is-integrated.md`.
**`tests/test_published_numbers.py` will fail** until `CLAUDE.md`'s ADR counter
goes 37 → 38. That test has caught this three times; expect it and fix the
counter in the same commit.

**E12.2 — final report.** §14's **22 numbered items, answered in order**, as
`docs/oss-ecosystem/final-report.md`. Never claim *"production ready"*.
Then update `docs/changelog/CHANGELOG.md`, `docs/memory/completed-work.md`,
`priorities.md` / `pending-work.md` as the memory rules require, close
`docs/memory/phase-plan.md`, and rewrite `docs/memory/session-state.md`.

---

## 7. Style notes, so the successor's output matches the fourteen files already written

- Every document opens with what was **measured**, its date, and its method.
- Every document ends with a **"What this phase refuses to conclude"** section.
  It is not decoration — it is where overreach gets caught.
- Numbers carry their units and their host. An unmeasured figure is `None` or
  `UNKNOWN`, **never `0`**.
- `ABSENT` ≠ `UNKNOWN`: one is measured and will not change by waiting, the
  other is waiting for a measurement.
- Commit messages: English, Conventional Commits, **no double quotes** (they
  break the shell here — use `git commit -F <file>` with a heredoc).

---

## 8. Outside this programme, and owed to the owner alone

- **`git push origin v0.1.0`** — the tag has never been pushed. Correct target
  **`383fcf7`** (`chore(release): prepare v0.1.0`, 2026-08-11, matching the
  changelog's `## [0.1.0] - 2026-08-11`). It is the single red test in CI.
  **Pushing it triggers `release.yml`, which builds the image and publishes a
  GitHub release** — an owner decision, not a repair. Refused from this
  environment: `HTTP 403`, measured twice. **Do not attempt it again.**
- ADR-035's three conditions (measure DSH quality on a machine allowed to
  install, read `@anthropic-ai/claude-agent-sdk`'s licence, determine what
  `dsh-headless` persists).
- `ollama serve` — gates C1, generation and semantic retrieval.
- `LICENSE` and `NOTICE` name **"GalSen IA"**; substituting a legal name or a
  registered entity is the owner's one-line edit.
