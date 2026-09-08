# GalSen IA - Work Cadence

**Le 04/09/2026, sur décision du propriétaire, ce fichier a perdu tout ce qui
arrêtait le travail :**

- la limite de 25 minutes et son check-in obligatoire (« Je continue ou
  j'arrête ici ? », puis attendre une réponse pour reprendre) ;
- le découpage imposé en phases de 8 minutes, vérifiables une à une, avec
  interdiction d'en commencer une avant d'avoir fini la précédente ;
- « ask before writing code » quand une tâche ne se découpe pas.

Ce qui reste ci-dessous ne bloque rien. La section *Token economy* est
conservée telle quelle parce que `.claude/rules/verification.md` y renvoie
**nommément** pour délimiter sa règle de fraîcheur.

**Ne pas remettre ces arrêts sans une demande explicite du propriétaire.**

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

**That last line does not override freshness.** It means: do not re-run a
*previous phase's* verification while starting a new one. It does **not** license
reporting an earlier run as the current state — `.claude/rules/verification.md`,
*Freshness*, wins on that, and it wins by name.

The distinction is not academic. Measured on 2026-08-22
(`.claude/skills/testing-instructions/scenarios/verification-freshness.md`): an
agent asked *"la suite passe toujours ?"* after docs-only edits answered **"Oui"**
and cited this very line to justify not re-running. **A rule that can be
recruited to excuse a stale claim is a rule that needs its boundary written
down.**

What is never cut to save tokens: reading the code before changing it,
running the tests, and reporting a failure with its real output.

An answer that is short because the work was skipped is a false economy.
