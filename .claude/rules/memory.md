# GalSen IA - Memory Rules

The memory files in `docs/memory/` are the project's long-term state.
They exist so a new session starts informed instead of re-deriving context.

---

# Session state (loaded automatically)

`docs/memory/session-state.md` is injected into every new session by the
`SessionStart` hook (`scripts/session_bootstrap.py`). You already have it when
a session opens - do not re-read it, and never ask the user "where were we".

You **must** rewrite it:

- at every 25-minute check-in
- when the user ends a session or says they are stopping
- before any long operation that could be interrupted

It answers four questions, nothing more, 20 lines maximum:

```
**En cours**        : the one task in flight, with its exact state
**Termine**         : what this session finished
**Prochaine etape** : the very next action, concrete enough to start blind
**Bloque**          : what is waiting on the user or on an external answer
```

An out-of-date `session-state.md` is worse than an empty one: it sends the next
session down a path that no longer exists. Rewrite it fully, never append.

---

# Reading

The rest of memory is read on demand, in this order, stopping as soon as you
have what you need:

1. `priorities.md` - what matters right now
2. `current-objectives.md` - what is actively being built
3. `pending-work.md` - what is queued

Read `vision.md` only for direction or scope decisions.
Read `knowledge-index.md` only to locate domain knowledge.
Read `multi-platform-directive.md` before any decision touching platform coverage.

Never read `completed-work.md` in full: it is an append-only log.
Search it for the specific subject you need.

Memory describes the project as it was written, not as it is now.
Before acting on an entry that names a file, function or flag, verify it still exists.

---

# Writing

Update memory after meaningful progress, never mid-task.
Meaningful means: an engine or module completed, an architectural decision taken,
a direction changed, or work discovered that someone else must pick up.

Do not record: refactors visible in git history, code structure, or anything
already documented in an ADR. Memory holds what the repository cannot tell you.

When you update memory, update the whole picture in the same pass:

| File | Update when |
|------|-------------|
| `completed-work.md` | Append one entry for what was finished |
| `current-objectives.md` | An objective is reached, dropped or added |
| `pending-work.md` | Remove what is now done, add what was discovered |
| `priorities.md` | The ranking actually changed |
| `knowledge-index.md` | New domain knowledge exists to point to |

Leave a file untouched when nothing in it changed. An unchanged file is
information too.

Finishing work without retiring the matching objective leaves the memory lying
about the project state. That is worse than not writing at all.

---

# Entry format

One entry, one fact. No prose paragraphs.

```
- 2026-08-04 - Memory engine done (`src/memory_engine/`) - in-memory only, persistence still needs an ADR.
```

Absolute dates, never "yesterday" or "last week".
Name the path the entry is about.
Add the reason only when it is not obvious from the change itself.

Before adding an entry, look for one covering the same subject.
Update that entry instead of creating a near-duplicate.

---

# Rulings

An ADR holds a decision. `completed-work.md` holds an outcome. Between them sits
everything a piece of work actually decided on the way - which library to reuse,
which of two readings of a spec to follow, what to leave out - and none of it was
written anywhere.

Those are **rulings**, and they have one format:

```
Décision : <ce qui a été décidé> — <pourquoi> — <ce que ça coûte si c'est faux>
```

The third clause is the one that does not exist anywhere else in this repository,
and it is the reason the format is worth having. "I chose X because Y" is a
justification, and a justification is written by someone who already believes
they are right. **Naming the cost of being wrong is the only part that can be
checked later**, and it is the part a reader needs in order to decide whether to
revisit the ruling or leave it alone.

A ruling whose third clause is "nothing" is not a ruling - it was not a decision,
it was a step. Do not write it down.

Where rulings go: in the phase report that made them, and in `completed-work.md`
when the work is logged. Not in an ADR - an ADR that absorbed every mid-task
judgement would stop being readable, which is what killed the practice of writing
them down in the first place.

**What is deliberately not adopted with it.** The source of this format pairs it
with *"rulings, not stalls"* - decide rather than ask, do not pause between
tasks. That contradicts `.claude/rules/phase-protocol.md`, which is permanent.
**The format is adopted; the cadence is refused.** A ruling here records a
judgement that was the assistant's to make; it never converts a question the user
should have answered into a decision taken without them.

Where this came from: `subagent-driven-development`, via the Superpowers audit
(`docs/research/superpowers-audit.md`, candidate C4).

---

# Size

`completed-work.md` grows forever and is loaded by humans and agents alike.

Above 200 lines, move the oldest entries into
`docs/memory/archive/completed-work-<year>.md` and leave a one-line pointer at
the top of the current file. Never delete history.

The other memory files stay short by design. If one exceeds ~50 lines, its
content belongs in `docs/architecture/` or `docs/knowledge/`, not in memory.

---

# Never

Never write secrets, API keys, tokens or credentials into memory files.
Never record a client's personal data.
Never contradict an ADR from memory: change the ADR first.
