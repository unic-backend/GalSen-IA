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

**Against the brief**, which asks for `C:\`, external drives and project folders:
the mechanism is right and the reach is one directory. What is missing is not
safety — it is **multiple declared roots**, and reversibility for move/rename/
archive. That is chapter 07, and it must not be bought by widening the root to
the whole machine.

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

**Against the brief**, which asks the agent to "run commands and scripts" and
"use development tools": six executables is a deliberate floor, not an oversight.
Widening it is a security decision with a shape — an allowlist per task, not a
global one — and it belongs with the sandbox (chapter 08), not before it.

### 2.3 Sight and GUI: absent

Nothing captures a screen, moves a pointer or knows a window exists. The vision
engine reads image files; it has never seen a desktop. This is the largest
genuine gap in the brief, and chapters 05–06.

### 2.4 The browser is not a browser

`BrowserTool` exposes `visit`, `get_text`, `get_title`, `get_links` — built on
`urllib` and regular expressions. No JavaScript, no clicking, no session. Any
application-shaped page is out of reach. The brief's "browser/computer-use
agents" has, today, **no counterpart here**.

---

## 3. Tools: nineteen enabled, all importable

```
filesystem terminal git github web_search browser api database model memory
rag embeddings ocr pdf email calendar logging metrics agri_advice   → enabled
docker                                                              → disabled
```

All twenty modules import cleanly. `docker` is off **for a stated security
reason**, not neglect: from inside the production container it would need the
host's Docker socket, which is root on the host — an agent could start a
privileged container mounting `/`. The brief asks for a sandbox; this is why the
sandbox cannot simply be "re-enable Docker".

---

## 4. Multi-agent: ten agents, and the honest bit

| Agent | Enabled | Brief's equivalent |
|---|---|---|
| router, planner | yes | orchestration, planning |
| coder, reviewer, tester | yes | **software engineer agent** |
| security | yes | **security agent** |
| researcher | yes | **research agent** |
| documentation, deployment, monitor | yes | — |

Missing against the brief: **file organiser**, **project manager**, **business
opportunity analyst**. Three of six requested specialists exist; three do not.

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

Missing: **working-style learning** (feedback is captured, nothing turns it into
preferences), **proactive discovery** (nothing runs unprompted), and a
**repository map** (the coder edits files; it has no model of a large codebase).

---

## 6. Verdict, capability by capability

| Brief | Verdict |
|---|---|
| Access desktop environments | **absent** |
| Navigate local storage, multiple drives | **partial** — one declared root, no drive concept |
| Understand file structures | present (read, list, search) |
| Organise, rename, move, archive | **absent** — writing is off, no reversible operation |
| Analyse existing projects | **partial** — file-level, no repository map |
| Write / modify / debug code | present, gated (VOLET 31) |
| Run commands and scripts | **partial** — six executables, no sandbox |
| See the screen, drive a GUI | **absent** |
| Multi-agent collaboration | present, three specialists missing |
| Memory | present |
| Security, approval, logs | **present and ahead of the brief** |
| Continuous improvement, style learning | **absent** |
| Proactive opportunity discovery | **absent** |
| MCP | **absent** |

**Six of fourteen are absent, four partial, four present.** The four that are
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
