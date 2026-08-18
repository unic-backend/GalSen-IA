# Aider — third-party notice

| | |
|---|---|
| Upstream | `https://github.com/Aider-AI/aider` |
| Licence | Apache License 2.0 |
| Consulted | 2026-08-09 |
| What was taken | **The edit-block format, as an idea.** No source code, no file, no fragment. |
| How the program is used | Called as a **subprocess**, from its own virtualenv (ADR-028). Never imported. |

## What GalSen IA borrowed

Aider popularised a way of letting a language model change existing code
without rewriting whole files: the model emits a *search/replace block* naming a
file, the exact text to find and the text to put in its place, and the program
applies it deterministically.

```
path/to/file.py
<<<<<<< SEARCH
the exact existing text
=======
what replaces it
>>>>>>> REPLACE
```

That convention is what `src/code_edit/edit_blocks.py` implements, in its own
Python, with its own parser, its own safety rules and its own tests. The
implementation shares no code with aider.

## Why no code was copied, and no dependency added

Aider is Apache-2.0 and written in Python, so neither the licence nor the
language would have prevented vendoring it. Its shape did.

Aider is a command-line application of roughly a hundred thousand lines,
carrying its own model layer (litellm), its own configuration system and its own
git handling. Inside GalSen IA that would be a second Router Engine, a second
Model Engine and a second Agent Runtime sitting beside the ones ADR-003 and
`docs/architecture/overview.md` already define — two architectures deciding the
same things. Copying it in would mean maintaining a fork of an application we do
not develop; importing it as a library would import that whole second stack to
use a text format.

## Licence position

A file format is not a work of authorship: re-implementing one from its public
description triggers no obligation under Apache-2.0, because nothing licensed
was copied. This notice therefore exists for **honesty and traceability**, not
because a licence compels it — someone reading `edit_blocks.py` in five years
should know where the convention came from.

Had any aider code been copied, Apache-2.0 would additionally require
preserving the licence text, the attribution notices, and a statement of
changes. None of that applies here, and if it ever does, this file is where it
goes.

## The program itself

Aider is also used *as a program*, by the Coding Engine (ADR-028):
`src/coding_engine/adapters/aider_adapter.py` runs the `aider` executable as a
subprocess, from its own virtualenv, pointed at whatever model the GalSen Model
Engine selected. It is never imported and never a dependency — if it is not
installed, the adapter reports how to install it and every other engine keeps
working.

Installing it into the platform environment was tried and is documented as a
mistake: `pip install aider-chat` downgraded numpy to 1.26 to satisfy its own
tree, which broke `opencv-python-headless` and with it the Vision Intelligence
Engine. Hence `scripts/install_coding_engines.sh` and the isolated virtualenv.

The command-line flags used come from aider's published options documentation,
and one behaviour was found by running the real program: **aider exits 0 even
when every model call failed**. The adapter therefore reads litellm's error
signatures from stdout instead of trusting the exit code. Reporting that run as
a success would have been exactly the fabrication `.claude/rules/verification.md`
forbids.
