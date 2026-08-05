# GalSen IA - Work Cadence

Long autonomous runs are the main way work gets lost here: an hour of effort
that ends on a timeout leaves nothing behind. Work in phases, check in often.

---

# The 25 minute limit

At the start of any task, record the wall-clock time (`Get-Date` on Windows).

Check the elapsed time at every phase boundary. At **25 minutes**, stop -
even mid-plan, even if the next step feels small.

When you stop, report in this shape and wait:

```
25 min atteintes. Fait : <phases terminees>. En cours : <phase, etat exact>.
Reste : <phases restantes, estimation>.
Je continue ou j'arrete ici ?
```

Never restart the clock by yourself. Only the user's answer restarts it.

This limit is about elapsed time, not about difficulty. A hard task that
finishes in 10 minutes needs no check-in; an easy task still running at 25
minutes does.

---

# Phases

Split before starting, not when you are already lost.

A phase is:

- one coherent unit (one module, one engine, one test suite)
- **8 minutes of work maximum**
- verifiable on its own - it compiles, imports, or passes its tests

Never begin a phase without finishing and verifying the previous one.
Never redo a completed phase.
After an interruption, resume from the last verified phase - never from zero.

If a task cannot be split into phases under 8 minutes, it is not understood
well enough yet. Ask before writing code.

Announce the phase plan in one line per phase, then execute. Do not describe
a plan you have not been asked to review.

---

# One thing at a time

Do not globalise. Building four services at once produces four half-built
services and no way to test any of them.

Finish one, verify it, log it, then take the next.

When the user asks for several things, do them in sequence and say which one
is in progress. Breadth is what turns 20 minutes of work into an hour.

---

# Token economy

Cheap by default, thorough where it counts:

- Search for what you need (`Grep`, `Glob`), do not read whole files to find one function
- Read a file once; the content stays in context
- Never re-print a file to show a change - name the path and the lines
- Edit the lines that change, never rewrite a whole file
- Run the targeted test file during a phase; run the full suite once, at the end
- Do not re-verify what a previous phase already verified

What is never cut to save tokens: reading the code before changing it,
running the tests, and reporting a failure with its real output.

An answer that is short because the work was skipped is a false economy.
