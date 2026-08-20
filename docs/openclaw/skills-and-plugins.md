# O07 — Skills and plugins, untrusted until audited (§12)

**Built**: 2026-08-19. GalSen IA facts VERIFIED FROM REPOSITORY with paths;
OpenClaw facts VERIFIED FROM OFFICIAL SOURCE, read today.

§12's rule: *"Never automatically install arbitrary third-party skills. Every
skill/plugin must be treated as untrusted until audited."* And a nine-item
checklist per candidate: source, licence, dependencies, permissions, network
access, filesystem access, execution behaviour, security risk, provenance.

**The finding of this phase is that §12 describes `src/plugins/`.** As with the
`NudgeEngine` two programmes ago, the requirement presented as new is already
built here — and this time it is built *harder* than the thing it would be
guarding.

---

## 1. What GalSen IA already enforces

All VERIFIED FROM REPOSITORY.

| §12 asks for | Where it lives |
|---|---|
| A declaration before anything runs | `manifest.py` — `CHAMPS_OBLIGATOIRES = (plugin_id, version, author, description, entry_point)`, none with a default, *"un défaut silencieux ferait passer un oubli pour une décision"* |
| **Permissions declared** | `PluginManifest.effects` (`read`/`write`/`external`) and `.scopes` (`public`/`system`/`user_private`) — the same vocabulary `tools/tools.yaml` uses |
| Network access visible | `leaves_the_machine` — true when `Effect.EXTERNAL` is declared |
| Private-data access visible | `reaches_private` — true when `DataScope.USER_PRIVATE` is declared |
| **Not enabled on install** | `enabled: bool = False` — *"Activer est une décision humaine distincte"* |
| Forbidden combinations refused | `forbidden_combination(manifeste)` |
| A static audit | `review.py` — parses the entry point as a syntax tree and compares **what it imports** against **what its manifest declares** |
| Execution bounded | `execution.py`, `POLITIQUE_GREFFON` — a `SandboxPolicy` |
| The refusal rules published | `contract.refusal_rules()` — the complete list in one place, because *"un auteur qui découvre un refus au moment d'être refusé a lu une documentation incomplète"* |
| Provenance | `author` — and the docstring is honest: *"Une chaîne libre : ce dépôt ne vérifie aucune identité et ne prétend pas le contraire"* |

**Two sentences from `review.py` are worth more than the table**, because they
are the discipline §12 is really asking for:

> *"A manifest saying 'no network' next to a file importing `urllib` is a
> discrepancy — a fact about two documents, not a judgement about their author."*

> *"Reporting 'no discrepancy' as 'safe' would be the most damaging thing this
> file could do, so it says so in its own report."*

And one rule that has no equivalent anywhere in what was read of OpenClaw:
**editing a plugin disables it.** The authorisation was granted for what its
author wrote; once someone else edits it, the thing running is no longer the
thing approved.

---

## 2. What OpenClaw's plugin model states

`docs/tools/plugin.md`, read 2026-08-19, VERIFIED FROM OFFICIAL SOURCE:

| Question | Answer from the source |
|---|---|
| Manifest format | `openclaw.plugin.json` — **fields not enumerated** in this document |
| Permissions / effects / scopes declared | **not stated** |
| Enabled on install | **variable**: *"Bundled plugins follow their built-in default-on/default-off metadata unless config explicitly overrides it"*; non-bundled workspace plugins are *"disabled by default; explicitly enable or allowlist them before using local workspace code"* |
| Review before install | `security.installPolicy` — *"a trusted local policy command before a plugin install or update proceeds"*, which *"can allow, warn, or block the install"*. **No mandatory static analysis is described.** |
| What a plugin may access | **not stated** — *"It mentions plugin ownership/permission blocking but not capability boundaries."* |

Plus, from O05: **ClawHub states no licensing policy** for published skills, and
its review is described only as *"the release stays hidden from normal
install/download surfaces until review and verification finish"* with
*"automated security checks"* whose content is not described.

**`security.installPolicy` is the right shape** — an operator-owned hook that
can block. It is a place to *put* a policy, not a policy. What GalSen IA has is
the policy.

---

## 3. §12's nine-item checklist, applied to the 51 in-repo skills

`skills/` holds **51 entries** (O05, VERIFIED FROM OFFICIAL SOURCE). Applying
§12 to them as a set rather than one by one, because the set-level answer is
already decisive:

| §12 item | Answer for the set |
|---|---|
| source | in-repo, `openclaw/openclaw` |
| licence | **`UNKNOWN`** — no `LICENSE` at `skills/` level (O05) |
| dependencies | **`UNKNOWN`** — each wraps an external program |
| permissions | **`UNKNOWN`** — not stated in the plugin document |
| network access | **`UNKNOWN` per skill** — `openai-whisper-api`, `notion`, `trello`, `xurl` self-evidently reach the network; the others are unread |
| filesystem access | **`UNKNOWN` per skill** — `obsidian`, `apple-notes`, `bear-notes` read personal stores |
| execution behaviour | **shells out to third-party CLIs**, by construction |
| security risk | **`UNKNOWN`, and not summarisable** at set level |
| provenance | repository is known; the wrapped programs' provenance is each their own |

**Nine items, seven `UNKNOWN`.** And they are not `UNKNOWN` for lack of effort —
they are `UNKNOWN` because **the answer is per-skill and there are 51 of them**,
each with its own wrapped program, its own licence, and its own terms of
service.

`INFERENCE`: auditing 51 skills to §12's standard is a programme in itself, and
it would have to be redone whenever the set changes. That cost is not a reason
to skip the audit; it is a reason to **not need it**.

---

## 4. The decision this phase produces

**Expose no OpenClaw skill or plugin. None.**

Not "audit them first" — **none**, and the reasoning is that every argument
points the same way:

1. **§12 requires an audit per skill.** 51 in-repo, plus ClawHub's open set. The
   audit never finishes because the set keeps moving.
2. **O05 found the ecosystem has no single licence**, and ClawHub states no
   licensing policy. Each skill is a separate licence question *and* a separate
   terms-of-service question for whatever it drives.
3. **O03's allowlist is already four tools**, chosen from GalSen IA's own 24.
   The useful surface an external runtime needs is small and **already exists
   here**, under authorisation that works per call.
4. **GalSen IA's own plugin system is stricter** — declared effects and scopes,
   disabled on install, static discrepancy check, edit-disables-approval. Piping
   OpenClaw skills in would route third-party code around a gate this repository
   built precisely for third-party code.

`OPENCLAW_COMPLEMENT` is therefore **not** available for skills. The verdict is
`REJECT` for the skill and plugin surface specifically, while leaving the rest
of the programme open — that is what a per-capability matrix is for.

---

## 5. What this means for an adapter, if one is ever approved

- The adapter exposes GalSen IA tools **to** OpenClaw, through O03's four-tool
  allowlist and `authorize()` per call.
- It exposes **nothing from OpenClaw's skill ecosystem** back into GalSen IA.
- `security.installPolicy` would be configured to **block** — its documented
  ability to *"allow, warn, or block"* used as a second lock, on the assumption
  that the first lock is not being relied on.
- Any future proposal to enable one specific skill re-enters through
  `src/plugins/` — manifest, declared effects and scopes, disabled on install,
  static review, named human decision — or it does not enter.

---

## 6. What O07 did not do

- **Audit any individual skill.** Fifty-one audits is not a phase, and doing
  three would produce a false sense of coverage.
- **Read `openclaw.plugin.json`'s schema.** The document that names it does not
  enumerate its fields, and no schema file was located. Recorded `UNKNOWN`
  rather than guessed.
- **Judge OpenClaw's plugin model as bad.** It is thinner than this
  repository's, and `security.installPolicy` is a sound hook. The decision above
  follows from GalSen IA already having the policy, not from the other side
  lacking one.
