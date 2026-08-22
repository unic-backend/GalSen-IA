# GalSen IA - Verification

The difference between a platform and a pile of code is that someone ran it.

---

# Definition of done

A phase is done when **all** of these are true:

1. The code imports without error
2. Its tests exist and pass - you ran them, **in this message**
3. It is integrated (registry, API, config) where the architecture says it belongs
4. `docs/memory/` reflects it

Not done: "should work", "the logic is correct", "tests will pass".
If you did not run it, say so in those words.

---

# Freshness

**If you have not run the verification command in this message, you cannot claim
it passes.**

Point 2 used to say "in this session". A session is long - this file has been
edited in sessions that ran for hours - and "I ran the suite" quietly comes to
mean "I ran the suite at some point, before three more edits". That claim is not
false to the person making it, which is exactly why it is the easy one to make.

The command is cheap. The claim is not: it is what a reader acts on.

Three consequences, and none of them is a courtesy:

- A result from earlier in the conversation is **evidence about the past**. Cite
  it as such ("the suite passed before this change"), never as the current state.
- A claim that survives an edit needs a run **after** that edit. Editing a file
  and reporting the previous run is how a broken change gets reported as
  finished.
- "Nothing I touched could affect it" is a prediction. Predictions are what
  running the command replaces.

Where this came from: `verification-before-completion`, from the Superpowers
audit (`docs/research/superpowers-audit.md`, candidate C3). The rest of that
skill was **not** adopted - this repository's three verification rules were
already stronger. One clause was missing, and this is it.

---

# Reporting results

Report what happened, not what was supposed to happen.

- Tests pass → say how many, and which command ran them
- Tests fail → paste the real failure output, then fix the cause
- You skipped a check → say which one and why

Never present an unverified change as finished. Never soften a failure. A test
suite that hangs, errors on collection or is skipped is **not** a passing suite.

If a test fails for a reason unrelated to your change (environment, missing
service, a pre-existing failure), prove it: state what you checked to reach that
conclusion.

---

# Never do this to make tests pass

- Deleting or skipping a failing test
- Weakening an assertion to match wrong output
- Catching an exception to hide it
- Mocking the very thing under test
- **Pinning a fabricated value.** A test asserting the output of something that
  does not really work makes the fabrication permanent. Four such tests have
  already reached `main` here — `test_calendar_tool.py` asserted
  `result[0]["title"] == "Réunion d'équipe"` for a meeting nobody scheduled.
  An unfinished capability reports a status; it never returns a plausible
  answer. Full reasoning → `docs/roadmap/roadmap.md`, *How something new enters
  the platform*.

A failing test is information. Removing it destroys the information and keeps
the bug.

---

# Before touching existing code

Read it first. All of it, in the region you are changing.

Check who calls it (`Grep`) before changing a signature, a return type or a
public name. A change that compiles but breaks three callers is a regression,
not a refactor.

When you change shared behaviour, run the tests of the callers too, not only
the tests of the file you edited.

---

# Regressions

If something that worked stops working after your change, that is your change
until proven otherwise. Find the cause; do not work around the symptom.

Say it plainly when it happens: "j'ai casse X, voici la cause, voici le
correctif". Hiding a regression costs the project far more than admitting one.

**How to find the cause: `.claude/skills/systematic-debugging`.** The sentence
above is the principle; that skill is the procedure — four phases, root cause
before any fix, with the red flags that mean you skipped one. Use it whenever a
test fails, a behaviour is wrong, or something that worked stops working.

The reason it exists rather than staying a principle: this repository has
followed those phases correctly three times in one session **by instinct**, and
an instinct that works when the operator is careful is exactly what fails on the
day they are not.
