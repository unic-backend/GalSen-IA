# O05 — Licence audit (§18), the gate

**Read**: 2026-08-19, from `github.com/openclaw/openclaw` and its `docs/`
sources. Every row carries where it came from.

§18's instruction is the one this phase exists to obey: **do not assume all
OpenClaw ecosystem components share the same license.** Three of the four
previous programmes were reshaped by exactly that assumption failing, so the
phase checks the layers separately rather than reading the root file and moving
on.

---

## The six things §18 asks for

| §18 asks | Answer | Class |
|---|---|---|
| Repository licence | **MIT**, and the grant is **filed** | VERIFIED FROM OFFICIAL SOURCE |
| Dependency licences | **`UNKNOWN`** — see the measured failure below | UNKNOWN |
| Plugin / skill licensing | **`UNKNOWN`, and structurally so** — see §3 | UNKNOWN |
| Commercial restrictions | **none in MIT**; none found in what was read | VERIFIED FROM OFFICIAL SOURCE |
| Attribution requirements | **yes** — MIT's notice clause | VERIFIED FROM OFFICIAL SOURCE |
| Redistribution requirements | **yes** — same clause; no copyleft obligation | VERIFIED FROM OFFICIAL SOURCE |

---

## 1. The repository licence — a real grant, unlike the last programme's subject

```
MIT License

Copyright (c) 2026 OpenClaw Foundation

Permission is hereby granted, free of charge, to any person obtaining a copy
```

`raw.githubusercontent.com/openclaw/openclaw/main/LICENSE`, read 2026-08-19.
`package.json` declares `"license": "MIT"` at version `2026.8.1`.

**Both halves are present**, and that is worth stating plainly because the
previous programme's subject had only one. Call.md declared MIT in its manifest
and had **no `LICENSE` file on any branch**, so it was filed `MIT DECLARED`.
OpenClaw is filed **`MIT` — declared and granted**.

MIT's obligations, for the record: the copyright notice and permission notice
must be included in copies and substantial portions. No copyleft, no commercial
restriction, no source-disclosure obligation.

---

## 2. Dependencies — `UNKNOWN`, and here is the exact failure

The dependency tree could not be read. Measured twice:

```
WebFetch raw.githubusercontent.com/openclaw/openclaw/main/package.json
  (asking only for the dependencies and devDependencies objects)
→ "DEPENDENCIES SECTION NOT PRESENT IN RECEIVED CONTENT"
```

The file is fetched and converted, but its `dependencies` block falls beyond
what the fetch returns. `pnpm-lock.yaml` — which holds the full resolved tree —
is present in the repository and is far larger; nothing available in this
environment can read it whole.

**So dependency licences are `UNKNOWN`**, and the word is used in §18's sense:
not "probably MIT", not "no copyleft found". Nobody looked, and this phase says
so rather than reasoning from the root licence downward — which is the exact
assumption §18 forbids.

`INFERENCE`, labelled: this is a **larger** unknown than it was for the previous
subject. Call.md declared 54 runtime and dev dependencies and each was
enumerated. OpenClaw is a **pnpm monorepo** with `apps/`, `packages/` (22
workspace packages), `extensions/`, `ui/`, `skills/` and `custodian-skills/` —
so the tree is bigger and the fan-out wider.

**What would settle it**: `pnpm licenses list` after an install, in an
environment allowed to install. That is an operator gesture, and it is recorded
as one rather than guessed at.

---

## 3. The ecosystem does not share one licence — measured, not assumed

This is the section §18 was written for, and it is not a formality here.

**Workspace packages carry no licence field.**

| Read | `name` | `license` | `private` |
|---|---|---|---|
| `packages/plugin-sdk/package.json` | `@openclaw/plugin-sdk` | **absent** | `true` |
| `packages/sdk/package.json` | `@openclaw/sdk` | **absent** | `true` |

Both VERIFIED FROM OFFICIAL SOURCE, read 2026-08-19. Under npm semantics a
package with no `license` field is unlicensed **as a package**; being `private`
and inside an MIT repository is a reasonable reading that the root grant covers
them, but **that is a reading, not a grant**. Recorded as `INFERENCE`, not as a
finding.

**The in-repo skills are wrappers around other people's software.** `skills/`
holds **51 entries** and **no `LICENSE` at that level**. Their names say what
they wrap: `1password`, `notion`, `trello`, `spotify-player`, `obsidian`,
`github`, `gh-issues`, `openai-whisper` and `openai-whisper-api`,
`sherpa-onnx-tts`, `tmux`, `things-mac`, `apple-notes`, `apple-reminders`,
`peekaboo`, `himalaya`, `xurl`.

`INFERENCE`, and it is the same shape the Research programme found in
Agent-Reach: **a skill's licence is not the licence of the thing it drives.**
Running the `notion` skill means accepting Notion's terms; running
`openai-whisper-api` means accepting an API provider's. §18's separate line for
*"plugin/skill licensing"* exists because of exactly this, and the honest answer
per skill is `UNKNOWN` until each is read.

**ClawHub does not state a licensing policy.** `docs/clawhub/publishing.md`,
read 2026-08-19: on licensing of published skills — **not stated**. On review:
*"The release stays hidden from normal install/download surfaces until review
and verification finish"* and *"ClawHub stores the release and starts automated
security checks"*, with no detail on what those checks are. On who may publish:
*"you use your personal owner or an org owner where you have publisher access"*,
and scope collisions are rejected.

So the distribution surface for third-party skills **carries no licence
requirement that was found**, which means the ecosystem's licence position
cannot be summarised at all — it is per-skill, per-publisher, and unstated by
default.

---

## 4. Does the gate close?

**No — and this phase says so plainly rather than manufacturing a blocker.**

O05 was declared a gate in the phase plan, with the stated rule that *an
incompatible or unfilable licence ends the programme*. Neither happened:

- The licence **is** filed, and it **is** MIT.
- MIT is compatible with everything this repository does. No copyleft, no
  commercial restriction, and the attribution obligation is one notice.

**What is not settled is different from incompatible.** Dependencies are
`UNKNOWN` because they could not be read here, and the skill ecosystem is
`UNKNOWN` **by construction** because it has no single licence to know. Neither
is a refusal; both are conditions.

**Conditions recorded for O12, gate 11 (*are licences compatible?*)**:

1. **Core**: `YES` — MIT, granted, attribution only.
2. **Dependencies**: `UNKNOWN` — requires `pnpm licenses list` in an environment
   allowed to install. **Must be run before any adapter ships**, not before the
   audit concludes.
3. **Skills / plugins**: `UNKNOWN` and **per-item**. §12 already requires every
   skill to be treated as untrusted until audited (O07 owns this); §18 adds that
   each also carries its own licence and, where it wraps a service, that
   service's terms.

`INFERENCE` for O11: the licence position **argues for the narrowest possible
adapter**. Every skill or plugin brought in is a separate licence question and a
separate terms question; an adapter that exposes **no** OpenClaw skills has none
of them, and O03's four-tool allowlist already points the same way for a
different reason.

---

## 5. What this phase refused to do

- **Infer dependency licences from the root licence.** §18 forbids it in one
  sentence, and it is the assumption that reshaped three previous programmes.
- **Call the ecosystem "MIT".** Two workspace packages have no licence field and
  51 skills wrap other people's software.
- **Treat `UNKNOWN` as a blocker.** It is a condition with a named, cheap
  resolution — one command, in an environment that may install.
- **Treat "MIT is filed" as sufficient.** It answers one of §18's six lines.
