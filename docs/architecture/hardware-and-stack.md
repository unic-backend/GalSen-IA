# Hardware, Software Stack, Upgrade Paths

VOLET 34, chapter 14 — the last chapter of the VOLET. The brief asks for
hardware requirements, a software stack and upgrade paths.

**What this document is:** the numbers this repository can justify. Where a
figure was measured, the command that produced it is next to it. Where it comes
from an ADR, the ADR is named. Where nothing here can measure it — GPU training,
notably — it says so instead of quoting a benchmark from memory.

---

## 1. What the platform runs on today, measured

```
$ python -c "import platform, os, sys; print(sys.version.split()[0], platform.machine(), os.cpu_count())"
3.11.15 x86_64 4
$ free -h | head -2
              total   used   free
Mem:           15Gi  704Mi   14Gi
$ python -m pytest -q
2599 passed, 7 skipped in 120s
```

The whole suite — 2 599 tests, every engine, the API, the sandbox, SQLite —
runs on **4 cores and under 1 GB of resident memory**, with no GPU. That is the
honest baseline: everything built in VOLETs 01–34 *except model inference* is
cheap.

The expensive part is the part that is not running here: **the model**.

---

## 2. Four profiles, and what each one can actually do

| Profile | Hardware | What runs | What does not |
|---|---|---|---|
| **Development** | 4 cores, 8 GB RAM, no GPU | Everything except generation and embeddings | The brain. `/generate` answers `503` (criterion C1) |
| **Small deployment** | 4–8 cores, 16 GB RAM, no GPU | Above + a 7–8B model quantised Q4 through Ollama (~6–8 GB RAM, ADR-014) + embeddings on CPU | Fast generation. Expect seconds per response, not tokens streaming |
| **Comfortable deployment** | 8 cores, 32 GB RAM, 12–16 GB VRAM | The same, on GPU: interactive generation, embeddings in batch | Training |
| **Training** | 24 GB VRAM (rented A100 or consumer card) | QLoRA fine-tune of a 7–8B base + DPO (`docs/architecture/training-infrastructure.md`) | Nothing else needs it |

**The 24 GB figure is the one this repository cannot verify.** It comes from
ADR-014 and the training-infrastructure document, not from a run here — there is
no GPU in this environment, and `scripts/training/` has never been executed.
Treat it as a plan, not a measurement.

### Storage

| What | Size | Source |
|---|---|---|
| The repository | ~16 MB of git history | `du -sh .git` |
| Python dependencies | ~1.5–2 GB installed (PyTorch dominates) | `requirements.txt` + `requirements-embeddings.txt` |
| Embedding model weights | ~90 MB | ADR-015 |
| A 7–8B model, Q4 GGUF | ~4–5 GB | ADR-014 |
| SQLite data directory | grows with use; `VACUUM INTO` backups double it briefly | `scripts/backup.py` |

A small deployment wants **20 GB of disk** to be comfortable, and that number is
dominated by two things nobody thinks about: PyTorch, and the model file.

---

## 3. The software stack, and why each piece is there

Versions are **pinned** (`requirements.txt`) — a release must rebuild
identically. What follows is the shape, not the list.

| Layer | Choice | Why this one |
|---|---|---|
| Language | **Python 3.11** | ADR-001 |
| API | **FastAPI + Uvicorn** | ADR-002; the OpenAPI description is generated, and ADR-011 relies on it to mark routes deprecated |
| Persistence | **SQLite** | ADR-005. One file, no server to operate. The trigger for PostgreSQL is written and unmet: a second instance (ADR-009, ADR-013) |
| Models | **Ollama / any OpenAI-compatible endpoint** | ADR-003 + ADR-014. No third-party provider is registered in sovereign mode |
| Embeddings | **Sentence Transformers**, optional | ADR-015. Absent → lexical retrieval, and the answer **says which path served it** |
| Vision / OCR | Pillow, OpenCV, Tesseract | Optional; absent → the tool reports unavailable rather than guessing |
| Perception | **Accessibility tree** (AT-SPI / UIA / AX) | VOLET 34 ch. 05. Screenshots are the fallback, not the default |
| Sandbox | **`setrlimit` + process groups** | VOLET 34 ch. 08. Docker is disabled on purpose: it would need the host socket, which is root on the host |
| Interop | **MCP server**, JSON-RPC 2.0, no dependency | VOLET 34 ch. 09 |
| Tests | pytest, ruff | `.claude/rules/testing.md` |

### What is deliberately absent

Written here because "we did not get to it" and "we decided against it" look
identical from outside, and only one of them should be revisited.

| Absent | Trigger that would change the answer |
|---|---|
| PostgreSQL, Redis | A second instance. Not before (ADR-013) |
| Qdrant / a vector database | ~100 000 vectors. On a corpus of 250 passages it is a service to operate for nothing |
| LangGraph, AutoGen, CrewAI | Nothing. The comparison is in `agent-foundations-comparison.md`: the repository already has planning, retries, validation, trace and history |
| A real browser (Playwright) | A page the current `urllib`-based tool cannot read *and* a task that needs it. Chromium is present in some environments; the Python package is not installed here |
| DeepSpeed | Full training above ~13B, or a step that will not fit at batch size 1 |
| Kubernetes | ADR-009: one instance holds a lock. Horizontal scaling is a decision nobody has taken |

---

## 4. Upgrade paths

Each of these is a **single step with a written trigger**, not a rewrite. That
is the property the architecture was built for, and the one worth checking every
time something new is proposed.

### 4.1 Give the platform a brain (criterion C1, open)

```bash
ollama serve
ollama pull qwen2.5-coder:14b      # or any model with ≥ 8192 context
```

Nothing else changes: `local_provider.py` already speaks it, the registry
already lists it, `/health` already reports it. **This is the single highest-value
step available, and it costs nothing.**

### 4.2 Persist everything

```bash
export GALSEN_STORAGE_BACKEND=sqlite
export GALSEN_DATA_DIR=/var/lib/galsen
python scripts/backup.py            # hot backup, VACUUM INTO
```

Memory, models, knowledge, audit and approvals move to disk. `/security/posture`
stops reporting the three "in-memory, lost on restart" gaps (ch. 13).

### 4.3 Semantic retrieval

```bash
pip install -r requirements-embeddings.txt
```

~90 MB of weights, PyTorch as the real cost. Retrieval quality is measured, not
assumed: `src/training/evaluation.py` holds the lexical baseline (0.40) to
compare against.

### 4.4 Let agents touch a real disk

```bash
export GALSEN_STORAGE_ROOTS="documents:/home/awa/Documents:rw,archives:/mnt/disque:ro"
```

Read-only unless `:rw` is explicit. Every move is journalled and undoable
(ch. 07), and `/security/checkpoints` lists what can still be undone (ch. 13).

### 4.5 Serve tools to other agents

```bash
# the MCP server exposes eight tools out of twenty-one, identity required
python -c "from src.mcp import MCPServer; print(MCPServer(executor=None).exposure_report())"
```

The terminal, screen, GUI, filesystem and database never leave the host (ch. 09).

### 4.6 Train SamP / ToP

The only path that needs hardware this project does not have. The recipe is
written (`scripts/training/`), the lineage registry exists, and **nothing has
been executed**. The first model to train is not an LLM but the **embedding
model** (VOLET 27): it trains on CPU or a modest GPU, its effect is measured
without human judgement, and it improves search, memory and RAG at once.

### 4.7 Scale horizontally

Not a path today. ADR-009 gives one instance an exclusive lock, and
`scaling_report()` on `/health` says so rather than letting an operator discover
it by running two. Changing it means an ADR first: shared session state, a
distributed lock, and PostgreSQL by the same trigger as ADR-013.

---

## 5. What would make this document wrong

- **A GPU appears.** Every number in §2 for the training and comfortable
  profiles becomes measurable, and should be replaced by a measurement.
- **The corpus grows past ~100 000 vectors.** The vector-database line moves
  from "absent" to "next step".
- **A second instance is wanted.** Three rows of §3 change at once — that is why
  they share one trigger.

Until then, the honest summary is short: **everything except the model runs on a
laptop, and the model is a 5 GB file away.**

---

## References

- ADR-001 (Python), ADR-002 (stack), ADR-003 (providers), ADR-005 (SQLite),
  ADR-009 (single instance), ADR-013 (PostgreSQL trigger), ADR-014
  (sovereignty), ADR-015 (embeddings), ADR-017 (new capabilities are tools)
- `docs/architecture/training-infrastructure.md` — the 24 GB figure and the QLoRA recipe
- `docs/architecture/personal-agent-assessment.md` — what exists, capability by capability
- `docs/deployment/production-readiness.md` — operating the deployment
