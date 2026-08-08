# GalSen IA — Phase Protocol

This rule overrides any impulse to be efficient by doing more at once.
It is not a suggestion and it is not negotiable by the assistant.

The work is organised in **VOLETs → chapters → phases**. Only phases are
executed. A chapter is never executed as a unit.

---

# 1. Opening a VOLET — the plan comes first

Before writing a single line of code for a new VOLET, read it and publish a
**phase plan**. Nothing else happens in that turn.

The plan is written to `docs/memory/phase-plan.md` and shown to the user in this
exact shape:

```
VOLET 04 — Roadmap
10 chapitres → 12 phases

Ch. 01  Vision            → 1 phase
Ch. 02  Macro-phases      → 2 phases  (2.1 inventaire, 2.2 arbitrage)
Ch. 03  Priorités         → 1 phase
...
Total : 12 phases. Je commence par la phase 1.1 et je m'arrête après.
```

Rules for the plan:

- Count the chapters from the VOLET file itself, never from memory.
- A phase is **8 minutes of work maximum** and verifiable on its own.
- A chapter that cannot be split holds exactly **one** phase. Say so explicitly:
  `Ch. 07 → 1 phase (indivisible)`.
- The total number of phases is stated. It is normal that it exceeds the number
  of chapters.
- The plan is announced, not submitted for review. Execution starts at phase 1
  in the **next** turn, after the user confirms.

---

# 2. Executing — one phase, then full stop

**One turn = one phase. Never two.**

After finishing a phase:

1. Verify it (it imports, its tests run and pass — `.claude/rules/verification.md`).
2. Report in this shape and **stop**:

```
Phase 2.1 terminée — <ce qui a été fait, 2 lignes max>
Vérifié : <commande> → <résultat réel>
Suivante : phase 2.2 — <ce qu'elle fera>
Je continue ?
```

3. Wait. Do not start phase 2.2. Do not "prepare" it, do not read files for it,
   do not open a plan for it.

Only an explicit answer from the user resumes the work: **« continuer »**,
**« confirmer »**, **« oui »**, **« vas-y »**, or an equivalent instruction. A
question, a remark, or silence is not a confirmation.

If the user answers something else, answer that and stop again. The pending
phase stays pending.

---

# 3. What is forbidden

- Chaining two phases in the same turn, even short ones.
- Executing a whole chapter because "it is small".
- Starting a phase that is not the next one in the plan.
- Announcing a phase as finished without having run its verification.
- Rewriting the plan mid-VOLET to merge phases together.

The single exception: **a chapter holding exactly one phase** is executed in one
turn — because that phase *is* the chapter. It still ends with a stop and a
`Je continue ?`.

---

# 4. Tracking

`docs/memory/phase-plan.md` holds, at all times:

```
VOLET en cours   : 04
Phases           : 12
Phase courante   : 2.2 — en attente de confirmation
Terminées        : 1.1, 2.1
```

Update it at the end of every phase, before stopping. It is loaded at session
start, so an interrupted session resumes at the right phase instead of guessing.

A phase plan without a current phase means the VOLET is finished: report it,
propose the next VOLET, and wait.

---

# 5. Relation to the 25-minute rule

`.claude/rules/work-cadence.md` still applies. The two rules do not conflict:
the phase protocol stops the work far more often than the 25-minute limit ever
will. If the 25 minutes are reached inside a single phase, that phase was
mis-sized — say so, and split it before continuing.
