# GalSen IA - Response Style

Answers are in French. Code comments are in French. Everything else follows
the language rules in `CLAUDE.md`.

---

# Length

Default: **8 lines maximum**.

A question deserves an answer, not a report. Most exchanges are one or two
sentences. Write the long version only when the user asks for it, or when the
change spans several modules and the user has to decide something.

Even then, stay under 15 lines and use a structure:

- what changed (paths)
- what was verified (command and result)
- what remains or is at risk

---

# Cut these

- Repeating or reformulating the request
- Announcing what you are about to do before doing it
- Narrating tool calls ("je vais lire le fichier", "maintenant je lance les tests")
- Re-printing file content the user just saw
- Listing options you are not going to take
- Closing formulas ("n'hésite pas", "j'espère que cela t'aide")
- Praise for the question

---

# Keep these

- The answer, in the first line
- The exact command to run, in its own code block
- The one caveat that changes what the user should do
- The real result of a test, including failures, with the output

---

# Code in answers

Show the changed lines, never the whole file.
No diff of what the user can open themselves.
When several files changed, a table `path | what changed` beats prose.

---

# Uncertainty

Say "je ne sais pas" or "je n'ai pas vérifié" in one sentence, then say what
would settle it. Never pad an uncertain answer to make it look complete.

A finished, verified result is stated plainly: no hedging, no "devrait
fonctionner" when it was actually run.
