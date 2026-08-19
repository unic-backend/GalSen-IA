# GalSen IA — Post-integration validation

Established by the project owner on 2026-08-19. **Permanent.**

This rule exists because a passing new test says nothing about the twenty
subsystems it did not touch. "The integration works" and "the platform still
works" are two claims, and only the second one matters to a user.

---

# The rule

**After any completed phase, integration, provider, engine, module or external
repository — before starting the next one — run a complete validation.**

Not a compilation. Not the new tests. The whole thing.

```
INTEGRATE → TEST → REGRESSION CHECK → VALIDATE EXISTING SYSTEMS → only then, next
```

The next external integration may begin **only** when regression status is
`PASS`, or when a non-critical limitation has been documented and explicitly
accepted.

---

# What to run

- The complete test suite — not the subset near the change
- Linting (`ruff check src tests`)
- Any configured type or build check
- The provider health paths and API surface, where the change touched them

# What to verify

Sixteen things, and the first two are the ones most often skipped:

1. Existing functionality still works
2. **Previous integrations still work** — a regression can land two integrations later
3. Existing video generation still works
4. Existing providers still work
5. `ProviderRegistry` still functions
6. `ModelRouter` still functions
7. `CreativeEngine` still functions
8. Memory systems still function
9. Reference systems still function
10. API and schema compatibility preserved
11. Authentication and authorization still function
12. Security boundaries intact
13. Self-healing still functions
14. Provenance still functions
15. No secret or credential introduced
16. No test deleted, disabled or weakened

Plus: no unnecessary dependency, no silent schema change, `UNKNOWN` behaviour
still returns `UNKNOWN`.

---

# When something fails

**Stop. Do not start the next integration.**

Report, in this shape:

```
Composant touché : <où>
Cause racine     : <pourquoi, pas le symptôme>
Gravité          : <ce qui casse pour un utilisateur>
Correctif proposé: <ce qui le répare>
Test qui le prouve: <le test qui échouait et passe maintenant>
```

Fix it when it can be fixed safely. When it cannot, **document it as a blocker**
— never hide it, and never soften it into a note.

---

# What this rule forbids

- Declaring a phase complete because it compiles
- Declaring a phase complete because the *new* tests pass
- Running only the tests near the change
- Fabricating a measurement instead of running one
- Sacrificing a working capability to land a new integration

**Every new provider is additive and replaceable.** A capability that worked
yesterday and does not work today is a regression, whatever else was gained.

---

# Relation to the other rules

`.claude/rules/verification.md` defines when *a phase* is done. This rule
defines when *the platform* is still whole. They stack: a phase that satisfies
verification but breaks a neighbouring subsystem is not finished.
