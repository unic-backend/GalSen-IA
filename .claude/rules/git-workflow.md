# Git Workflow — GalSen IA

## Hard Rules
- NEVER push directly to the `main` branch.
- NEVER force push to `main`.
- Always work on a feature branch.

## Branch Naming
- feature/short-description
- fix/short-description
- docs/short-description
- chore/short-description

## Commit Messages
- Write commit messages in **English**.
- Use the Conventional Commits style when possible:
  - feat: ...
  - fix: ...
  - docs: ...
  - chore: ...
  - refactor: ...

## Good Practices
- Make small and focused commits.
- Write clear commit messages that explain why the change was made.
- Update documentation (especially memory files and CHANGELOG) in the same commit when relevant.

---

## How a branch ends

Everything above governs how a branch is born. Nothing governed how it ends —
and the end is where the irreversible operations live. Merges, force pushes and
branch deletions have all been performed here from memory, in whatever order
seemed right at the time.

**Five steps, always in this order.** The order is the point: step 1 protects
steps 4 and 5.

### 1. Verify the tests — first, not last

```
python -m pytest -q
ruff check src tests scripts
```

Run in the message that reports the result (`.claude/rules/verification.md`).
A branch merged on a remembered test run is a branch merged on nothing.

**A red suite does not automatically stop the merge** — but it changes what has
to be said. Name the failure, and say whether it fails identically on the base
branch. `v0.1.0` is the standing example: red in CI, red on `main`, never a
regression, **not to be "fixed"**.

### 2. Measure the base branch too

```
git fetch origin main
```

Compare against the base's own last CI run before concluding anything. This is
the step that separates *"my branch is red"* from *"everything is red"*, and it
has been skipped often enough to be worth its own line. Do not take a claim from
a pull-request description — including one you wrote — as evidence about CI.

### 3. Know where you are

```
git log --oneline origin/main..HEAD
git diff --stat origin/main..HEAD
git status --short
```

Three questions: which commits are mine, what do they touch, and is the tree
clean. A surprise here is a reason to stop, not to continue carefully.

### 4. Present the options — and wait

Never choose for the user. Present exactly what applies:

```
Travail terminé. Que veux-tu ?
1. Fusionner dans <base> et pousser
2. Ouvrir une pull request
3. Laisser la branche telle quelle
```

**The integration decision belongs to the owner**, not to whoever finished the
work. This is `.claude/rules/phase-protocol.md`'s stop, applied to the moment
where mistakes are least recoverable.

Discarding work happens only when the owner asks for it in those words.

### 5. Execute exactly what was chosen

- **Push**: `git push -u origin <branch>`. On rejection, `git fetch` and
  **rebase onto** the remote — never force by reflex. `--force-with-lease` is for
  a branch whose history the owner has explicitly agreed to discard.
- **After a merged pull request**: the branch is finished. Restart it from the
  updated base (`git checkout -B <branch> origin/main`) rather than stacking new
  commits on merged history.
- **Deleting a branch**: only after its work is on the base, and only when asked.

---

*Origin: `finishing-a-development-branch` from `obra/superpowers` at `b36e0829`
(MIT), adopted as candidate C5 of `docs/research/superpowers-audit.md`. Steps 2,
3 and the rebase clause are this repository's own — they come from mistakes made
here, not from the source.*