# GalSen IA - Verification

The difference between a platform and a pile of code is that someone ran it.

---

# Definition of done

A phase is done when **all** of these are true:

1. The code imports without error
2. Its tests exist and pass - you ran them, in this session
3. It is integrated (registry, API, config) where the architecture says it belongs
4. `docs/memory/` reflects it

Not done: "should work", "the logic is correct", "tests will pass".
If you did not run it, say so in those words.

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
