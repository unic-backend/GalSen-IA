---
name: systematic-debugging
description: Use when a test fails, a behaviour is wrong, or something that worked stops working — before proposing any fix. Four phases, in order, root cause before code.
---

# Systematic Debugging

`.claude/rules/verification.md` already states the principle:

> *"If something that worked stops working after your change, that is your change
> until proven otherwise. Find the cause; do not work around the symptom."*

One sentence, and it has been enough — three times in one session, by instinct.
**Three for three by instinct is not a process.** This skill is the procedure, so
that the result does not depend on whoever is at the keyboard being careful that
day.

Related but different: `debug-issue` navigates the code graph — *where* the
relevant code is. This skill decides *what to do next*, and calls that one.

---

## The rule that orders everything

**No fix is proposed before the root cause is named.**

Not "probably", not "most likely". Named, with the evidence that names it. A fix
applied to a cause nobody has stated is a guess, and a guess that works is worse
than one that fails — it removes the symptom and leaves the defect.

---

## Phase 1 — Root cause investigation

**Before touching anything.**

1. **Read the error completely.** All of it: the message, the full traceback, the
   exit code, the line numbers, the assertion's actual-versus-expected. The
   answer is inside it more often than not.
   *Measured here:* a sabotage that "did not fire" was diagnosed as a broken
   test. The real cause was in the output all along — the appended line had glued
   onto the previous one because the file had no trailing newline. **The test was
   right; the sabotage was not.**

2. **Reproduce it.** Same command, twice. If it is not reproducible, gather more
   data — **do not guess**. An intermittent failure that gets a fix is an
   intermittent failure with one more untested change in it.

3. **Establish what is yours.** Before blaming the change, measure the baseline:
   ```
   git stash && python -m pytest <cible> -q   # untouched
   git stash pop && python -m pytest <cible> -q
   ```
   *Measured here:* 40 failures and 16 errors looked like a regression. The
   untouched baseline on the same machine failed identically — the container had
   been provisioned without `bcrypt`, which `requirements.txt` declares. **Ten
   minutes of measurement replaced an afternoon of blaming the wrong commit.**

4. **Instrument every boundary you cross.** When the path spans components — API
   → engine → store, routine → orchestrator → agent — print what enters and what
   leaves each one **before** proposing anything. A wrong value is easy to find
   and impossible to guess.

5. **Do not read documentation about behaviour you can measure.** Five lines that
   run beat a paragraph that describes.
   *Measured here:* whether `PRAGMA data_version` detects another connection's
   writes was settled by a five-line experiment. The answer — it does not, on a
   fresh connection — changed the design.

---

## Phase 2 — Pattern

Once the cause is reproducible, before fixing:

- **Does it appear elsewhere?** Grep the shape, not the symptom. A defect written
  once was usually written twice.
- **Is the neighbour affected?** `query_graph_tool` with `callers_of` — a
  signature, a return type or an assumption that changed touches everyone who
  called it.
- **Has this happened before?** Search `docs/memory/completed-work.md` for the
  subject. This repository has paid for the same class of defect more than once,
  and the entry usually says what fixed it.

---

## Phase 3 — Hypothesis, then evidence

State it in one sentence, out loud, in this form:

```
Je pense que <cause> produit <symptôme>, parce que <observation>.
Ce qui le prouverait : <l'expérience>.
```

Then run the experiment. **The experiment comes before the fix**, and it is
usually smaller: a print, a one-line script, a single test run with one value
changed.

If the experiment refutes the hypothesis, that is the phase working. Write the
next one. Two refuted hypotheses in a row usually mean phase 1 was cut short —
go back to it rather than trying a third.

---

## Phase 4 — Fix, and prove it

1. **A test that fails first.** Reproduce the defect as a test and watch it go
   red. A test written after the fix proves the fix compiles, nothing more.
2. Fix the **cause**.
3. **Watch the test go green.**
4. **Run the callers' tests too**, not just the file you edited.
5. **Run the whole suite** — `.claude/rules/post-integration-validation.md`: a
   passing new test says nothing about the twenty subsystems it did not touch.
6. Report with real output, **produced in this message**
   (`.claude/rules/verification.md`).

---

## Red flags — stop and go back to phase 1

| You are about to say | What it actually means |
|---|---|
| "Let me try changing this and see" | No hypothesis. Phase 3 has not happened. |
| "It's probably the cache / the environment / a flake" | A guess wearing a diagnosis. Measure it. |
| "It works now" (nothing else changed) | The cause is unknown and still there. |
| "The test is wrong" | Sometimes true. **Measured here: usually not.** Prove the test wrong before editing it. |
| "I'll add a retry" | Retries hide non-determinism; they do not remove it. |
| "This is unrelated to my change" | Possibly. `.claude/rules/verification.md`: prove it, state what you checked. |

---

## The rationalisations, named so they are recognisable

- *"The suite is slow, I'll run just this file."* Phase 4 step 5 exists because a
  fix that breaks a neighbour is a regression, not a fix.
- *"I already know what this is."* Then phase 3 costs one sentence and one
  command. If you are right it is nearly free; if you are wrong it saved the day.
- *"The user is waiting."* They are waiting for a working platform. A symptom
  removed today comes back with the cause attached.

---

## What this skill does not do

It does not touch `src/agent/self_healer.py`. That is an **autonomous** repair
engine with its own immutability policies and guarded editor. This skill is a
method for a **supervised** agent — a different layer, and the audit that
proposed it said so explicitly.

---

*Origin: `systematic-debugging` from `obra/superpowers` at `b36e0829` (MIT),
adopted as candidate C2 of `docs/research/superpowers-audit.md`. The procedure is
reimplemented, not copied: every example above is a real failure from this
repository, because a procedure illustrated with someone else's failures is one
nobody here recognises.*
