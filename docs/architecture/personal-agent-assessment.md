# Personal Computer Agent — What This Repository Already Does

VOLET 34, phase 1.1. Measured on 2026-08-12 by running the code, not by reading
it. Every verdict below names the command that produced it.

The brief asks for an agent that operates a real computer. This document answers
one question: **which parts of that already exist here, and what exactly do they
do?** Building on top of a wrong answer to that question is how a roadmap wastes
a month.

---

## 1. The headline: the brain is unreachable

```
$ python -m pytest tests/test_generation_end_to_end.py -rs
SKIPPED — Aucun fournisseur configuré — critère C1 non vérifiable.
  Local (Ollama): Aucun serveur Ollama sur http://localhost:11434.
  API compatible OpenAI: Aucune URL déclarée.
7 passed, 2 skipped
```

Two providers are registered (`local`, `openai_compatible`); **neither answers**.
Every capability below is a limb; today they have no head. This is the operator's
move — `ollama serve` with a context window of at least 8192 — and it costs
nothing.

Sovereignty, measured:

```python
>>> ModelManagerImpl().sovereignty_report()
{'sovereign_mode': True, 'providers': ['local', 'openai_compatible'],
 'third_party_providers': [], 'reference': 'ADR-014'}
```

---

## 2. Computer control — what the agent can and cannot touch

### 2.1 Files: confined, and read-only by default

```python
>>> fs = FileSystemTool({"allow_write": False})
>>> fs.root
'/home/user/GalSen-IA'
>>> fs.execute("read", "/etc/passwd")
ValueError: Accès refusé: '/etc/passwd' est hors du répertoire autorisé
>>> fs.execute("read", "../../../etc/passwd")
ValueError: Accès refusé
```

Absolute paths, `..` segments and symlinks are all resolved against one declared
root before any operation. Writing is **off by default**: an agent reports what
should change instead of changing it.

**Chapter 07 landed on 2026-08-12**, and it did not widen anything. `src/storage/roots.py`
lets an operator declare several named roots — `projets:/home/awa/projets:rw`,
`documents:C:\Users\awa\Documents:rw` — each read-only unless `:rw` says
otherwise. Everything outside them is still refused, symlinks included, and a
relative path is **refused as ambiguous** when several roots exist rather than
guessed.

`src/storage/reversible.py` makes move, rename, remove and archive undoable, and
**nothing is deleted**: a removal moves into `.galsen-corbeille` inside the same
root. The journal is written *before* the file moves — the reverse order would
leave a window where something moved and nothing knew how to put it back.

### 2.2 Commands: no shell, and it holds

```python
>>> term.execute(["echo", "bonjour"])          # rc=0, stdout='bonjour'
>>> term.execute(["rm", "-rf", "/tmp/x"])      # refusé : 'rm' non autorisée
>>> term.execute(["bash", "-c", "id"])         # refusé : 'bash' non autorisée
>>> term.execute("echo salut; id")             # rc=0, stdout='salut; id'
```

The last line is the one that matters. The `;` stayed a character inside an
argument; it did not become a second command. Commands run through the process
API, never a shell, from an allowlist of six executables
(`python`, `python3`, `py`, `pytest`, `git`, `echo`), each with a timeout.

**Chapter 08 landed on 2026-08-12** and did not widen the allowlist. It added
`src/sandbox/`: kernel limits applied between `fork` and `exec` — CPU, memory,
processes, file size, wall clock, captured output — and an environment
**allowlist**, so agent code sees no secret the parent holds.

What it does **not** confine is written in `policy.NON_GARANTI` and returned by
`describe()`: the filesystem and the network. Without namespaces, a child reads
and writes wherever the user can. Those two stay held by what already held them —
declared roots (ch. 07), the approval gate, the executable allowlist. A sandbox
that suggests a boundary it does not have is more dangerous than none, because
one entrusts it with what one would not have.

### 2.3 Sight: delivered as a tool. GUI: still absent

**Chapter 05 landed on 2026-08-12.** `ScreenTool` reads the accessibility tree,
returns elements carrying identity — role, label, bounds — and refuses with a
named reason where no display exists. On this container it reports *"aucune
session graphique détectée"* rather than an empty list.

The platform backends (AT-SPI, UI Automation, macOS AX) are declared and report
themselves unimplemented: verifying them needs a machine with a desktop, the way
TEST 2 and TEST 6 need one with Docker. That dependency is stated rather than
papered over with untested code.

**Chapter 06 landed the same day.** `GUITool` proposes a gesture and executes
none without an approved decision — the path `GuardedEditor` established for
files (VOLET 31), reused rather than reinvented. A gesture names its target or is
refused, and five refusals precede the gate: no target, no label, no position,
disabled element, password field.

Reading and acting stay two tools, and a test asserts `ScreenTool` has not grown
a click. The platform backends still need a machine with a desktop.

### 2.4 The browser is not a browser

`BrowserTool` exposes `visit`, `get_text`, `get_title`, `get_links` — built on
`urllib` and regular expressions. No JavaScript, no clicking, no session. Any
application-shaped page is out of reach. The brief's "browser/computer-use
agents" has, today, **no counterpart here**.

### 2.5 MCP: served before consumed

> **Added 2026-08-12 by VOLET 34 chapter 09** (`src/mcp/`).

The server speaks JSON-RPC 2.0 with no dependency — `initialize`, `tools/list`,
`tools/call`, `ping`. Three properties matter more than the protocol:

- **The exposure is a whitelist of eight**, not the catalogue of twenty-one.
  `terminal`, `gui`, `screen`, `filesystem`, `database`, `email`, `calendar`,
  `git`, `github`, `api`, `browser`, `model` are refused **with a reason**.
  Serving the whole catalogue would hand an outside agent the platform's hands.
- **No anonymous call.** Without an identity resolver the server refuses
  everything: a server that serves without an identity can neither authorise nor
  trace, and "the risk stays on our side" stops being true.
- **The audit records the tool, the operation and the subject — never the
  arguments.** Arguments carry somebody's text, and the audit persists.

The client half decides *before* connecting and connects to nothing: servers are
**pinned** (no dynamic discovery), and a third-party tool description is treated
as data — neutralised, marked as third-party, and flagged when it contains
imperatives aimed at a model. That is tool poisoning, the most documented
client-side MCP vulnerability, and the flag never deletes the suspicious text:
erasing the attempt would erase the evidence of the attempt.

---

## 3. Tools: twenty-one enabled, all importable

> **Updated 2026-08-12 by VOLET 34 chapters 05 and 06.** `screen` reads the
> accessibility tree; `gui` proposes gestures and executes none without a human
> decision. They are two tools on purpose: an agent can be given eyes without
> being given hands.

```
filesystem terminal screen gui git github web_search browser api database model
memory rag embeddings ocr pdf email calendar logging metrics agri_advice → enabled
docker                                                                   → disabled
```

All twenty-two modules import cleanly. `docker` is off **for a stated security
reason**, not neglect: from inside the production container it would need the
host's Docker socket, which is root on the host — an agent could start a
privileged container mounting `/`. The brief asks for a sandbox; this is why the
sandbox cannot simply be "re-enable Docker".

---

## 4. Multi-agent: thirteen agents

| Agent | Enabled | Brief's equivalent |
|---|---|---|
| router, planner | yes | orchestration, planning |
| coder, reviewer, tester | yes | **software engineer agent** |
| security | yes | **security agent** |
| researcher | yes | **research agent** |
| documentation, deployment, monitor | yes | — |
| **organizer** | yes | **file organiser** (ch. 11) |
| **project_manager** | yes | **project manager** (ch. 11) |
| **opportunity** | yes | **business opportunity analyst** (ch. 11) |

> **Updated 2026-08-12 by VOLET 34 chapter 11.** All six requested specialists
> now exist; this section previously read "three of six". Each of the three new
> ones is built around its own failure mode rather than its feature:
> `organizer` **proposes and never moves** — it is suspended in
> `requires_approval` by construction, and every move it later performs is
> reversible; `project_manager` reports task state from what agents actually
> returned and **produces no deadline, estimate or percentage**, because none
> exists anywhere in the platform; `opportunity` attaches a source to every
> statement and answers `insufficient_evidence` rather than composing a
> plausible market analysis — the failure that would cost a real person real
> money. Reachable through three workflows: `rangement`, `suivi`, `veille`.

Delegation between agents is bounded (depth 3, no cycles, no self-delegation),
results are validated against a contract before aggregation, and every agent
write goes through the approval gate.

---

## 5. Memory, learning, control

| Capability | State |
|---|---|
| Short/long-term memory | `src/memory_engine/`, persistent (ADR-005) |
| Semantic retrieval | `src/embeddings/`, degrades to lexical and **says so** (ADR-015) |
| Knowledge base | 250 verifiable passages, from this repository's own docs |
| Approval checkpoints | ADR-006, persistent; code writes gated by construction |
| Activity log | `src/audit_engine/`, persistent, filterable, `/trace/{request_id}` |
| Permissions | RBAC per key, ownership per subject (ADR-010) |
| Learning from use | consented capture, PII scrubbing, DPO pairs, lineage (VOLET 33) |
| Backups | `VACUUM INTO` hot backup of the data directory |
| **Posture, measured** | `src/security/posture.py` — nine sections read from the real configuration, each carrying what it does **not** guarantee (ch. 13) |
| **Checkpoints** | `src/security/checkpoints.py` — file operations, approval decisions and backups in one view, with `reversible` per line and **no global undo** (ch. 13) |

> **Updated 2026-08-12.** Proactive discovery was the last capability the brief
> asked for and this repository lacked. `src/proactive/` closes it: seven
> detectors read state the platform already measures — model availability,
> approvals waiting over 24 h, blocking import cycles, code no test reaches,
> a **measured** drop in quality, files worth tidying, security gaps — and each
> observation carries its evidence and names who must decide. **Nothing is
> executed.** A detector that cannot measure stays silent; one that fails is
> reported as failed, never confused with a silent one. Dismissed suggestions do
> not return unless their evidence fingerprint changes, so silencing "3 untested
> files" cannot hide "300 untested files" six months later. Triggering is
> explicit — `scripts/proactive_scan.py` (cron-able), `GET
> /proactive/suggestions`, or `due()` — because a background thread nobody
> verified would be the worst outcome: discovery believed active and not running.

> **Updated 2026-08-12 by VOLET 34 chapter 12.** Working-style learning is no
> longer missing. `src/training/working_style.py` derives preferences from what a
> subject actually corrected — length, formatting, language — each one carrying
> its observation count and the feedback ids behind it, and **nothing is asserted
> below three concordant observations**. Only consented feedback feeds it:
> `feedback.py` says a non-consented return corrects *that* answer and nothing
> else, and a durable profile is something else. The preferences reach the model:
> `AgentContext.generate` prepends them to the prompt, and the audit records
> `style_applied`. `src/training/improvement.py` compares two equal windows of
> feedback and answers `insufficient_data` rather than calling a three-sample
> difference a trend.

> **Updated 2026-08-12 by VOLET 34 chapter 10.** The third gap listed here — the
> coder having no model of a large codebase — is closed. `src/agent/repo_graph.py`
> derives the import graph (310 code files, 1 194 internal edges) and answers
> *who breaks if I change this*; `src/agent/symbol_index.py` indexes **5 762
> symbols**, methods included, and turns `verification.md`'s "check who calls it
> before changing a signature" into a query.
>
> The measured gain is in the coding loop: `GuardedEditor` picked the test to run
> **by filename**, which found one for 67 of 308 files (21.75 %) and left the other
> 78 % applied-but-unverified. Selecting by import reaches **270 of 310** (87 %).
> Two cheap facts fell out of the graph: three import cycles, **none of them
> blocking** — all deferred inside function bodies.

---

## 6. Verdict, capability by capability

| Brief | Verdict |
|---|---|
| Access desktop environments | **partial** — reads the accessibility tree; platform backends need a desktop to verify |
| Navigate local storage, multiple drives | **present** — several named roots, read-only by default (ch. 07) |
| Understand file structures | present (read, list, search) |
| Organise, rename, move, archive | **present** — reversible, journalled, nothing deleted (ch. 07) |
| Analyse existing projects | **present** — import graph, impact radius and symbol index over 310 files (ch. 10) |
| Write / modify / debug code | present, gated (VOLET 31) |
| Run commands and scripts | **present** — six executables, plus a resource sandbox with its escape tests (ch. 08) |
| See the screen | **partial** — contract, refusals and element identity delivered (ch. 05) |
| Drive a GUI | **partial** — gate, refusals and action contract delivered (ch. 06); backends need a desktop |
| Multi-agent collaboration | **present** — all six requested specialists exist (ch. 11) |
| Memory | present |
| Security, approval, logs | **present and ahead of the brief** — now measured in one place, `/security/posture` (ch. 13) |
| Continuous improvement, style learning | **present** — preferences derived with evidence, applied to prompts; trends refused below sample size (ch. 12) |
| Proactive opportunity discovery | **present** — seven measured detectors, nothing executed, no repetition (`src/proactive/`) |
| MCP | **partial** — server delivered, whitelisted and identified (ch. 09); client decides before connecting but connects to nothing |

**None of fifteen is absent: four partial, eleven present.** The four that are
present are the ones that are hardest to retrofit — permissions, approval,
audit, ownership — and they are why the missing six can be built without turning
this into a tool that deletes a user's drive on a bad inference.

---

## 7. What this changes in the plan

Nothing in the chapter list of `VOLET_34.md` moves. Two things are now measured
rather than assumed:

1. **The sandbox (ch. 08) must come before wider command execution.** The
   allowlist of six is what currently stands between an agent and the host, and
   it is the only thing.
2. **Chapter 07 is about *roots and reversibility*, not about access.** The path
   confinement already works; what is missing is declaring several roots and
   making move/rename/archive undoable.
