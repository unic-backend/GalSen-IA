# O06 — Model providers (§10) and memory (§11)

**Built**: 2026-08-19. GalSen IA facts are VERIFIED FROM REPOSITORY with paths;
OpenClaw facts are VERIFIED FROM OFFICIAL SOURCE, read today, with the document
named.

---

# O06.1 — Model providers (§10)

## §10's checklist, answered

| §10 asks about | Present in OpenClaw's 60-provider list |
|---|---|
| Claude | **yes** — Anthropic |
| Kimi | **yes** — Moonshot AI |
| LiteLLM | **yes** |
| vLLM | **yes** — *"vLLM (local models)"* |
| SGLang | **yes** — *"SGLang (local models)"* |
| Local models | **yes** — llama.cpp, LM Studio, Ollama, inferrs |
| Future providers | plugin-shaped; `UNKNOWN` in detail |

`docs/providers/index.md`, VERIFIED FROM OFFICIAL SOURCE. **Provider coverage is
not the problem**, and this phase says so before saying what is.

## The conflict is not coverage — it is sovereignty

GalSen IA's provider architecture is not a list. It is a **refusal with a
default**, decided in ADR-014 and quoted here verbatim:

> `GALSEN_SOVEREIGN_MODE` defaults to **true**. In that mode: the hosted
> providers are **not registered at all** — not registered-and-idle. A provider
> that is not in the registry cannot be selected by any path, accidental key or
> not.

Only `LocalProvider` (Ollama) and `OpenAICompatibleProvider` are available in
that mode, and the ADR is explicit that the second *"is not a dependency on
OpenAI: it is a protocol that vLLM, llama.cpp, LM Studio and the project's own
server all speak."*

The test ADR-014 demands is equally explicit: *"with sovereign mode on and every
hosted key set, no external endpoint is reachable from the model path."*

**Now place OpenClaw beside that.** It carries its own provider configuration
and its own credential store — O01 measured that a Fleet cell holds *"its own
state, credentials, workspace, channel accounts, token"*. An OpenClaw instance
configured with an Anthropic key reaches Anthropic. It does not consult
`GALSEN_SOVEREIGN_MODE`, because it has never heard of it.

`INFERENCE`, and it is the sharpest one in the programme so far:
**an OpenClaw instance with its own provider credentials is a hole in ADR-014's
guarantee, and the guarantee is stated as absolute.** Not "a risk to manage" —
the ADR's own test asserts *no external endpoint is reachable from the model
path*, and a second runtime with its own keys makes that assertion false while
leaving it passing, because it tests GalSen IA's model path and OpenClaw is not
on it.

## What §10 requires, restated as a constraint on any adapter

§10 says *"Do NOT make OpenClaw the model router"* and *"GALSEN-IA ModelRouter
remains authoritative."* Two arrangements satisfy that; one does not.

| Arrangement | Verdict |
|---|---|
| OpenClaw holds provider keys and calls models itself | **REJECT** — defeats ADR-014's default, and the existing sovereignty test would not catch it |
| OpenClaw configured with **one** provider pointing at GalSen IA's own OpenAI-compatible endpoint | **VIABLE** — every inference then passes through `ModelRouter`, `routing_policy` and `config/model_routing.yaml` |
| OpenClaw with no model at all, used only for non-inference work | viable but pointless — the agent loop is the thing |

**The second is the only real option**, and it is available precisely because
`OpenAICompatibleProvider` exists on our side and OpenClaw supports
OpenAI-compatible endpoints among its sixty. That is a genuine compatibility
finding, not a workaround.

`UNKNOWN`, recorded rather than assumed: whether OpenClaw can be **constrained**
to a single provider — configuration read-only to the agent, no fallback, no
`ClawRouter` — was not verified. `docs/gateway/configuration.md` was not read.
O11 needs it before proposing anything, because *"configured with one provider"*
is worth nothing if a skill can add a second.

---

# O06.2 — Memory (§11)

## What GalSen IA already has, and what each is for

§11 names seven memories. All exist; none is a duplicate of another.

| §11 names | Where | What it is |
|---|---|---|
| GalSen IA memory | `src/memory_engine/` — 11 modules | the platform store: manager, retriever, indexer, cache, ranker, summarizer, quality, layers |
| `CharacterMemory` | `src/creative/world.py:263` | what is remembered of a recurring entity — *"sans rien garantir"*; §18 forbids claiming perfect character consistency, so the class has **no field that asserts it** |
| `WorldMemory` | `src/creative/world.py:332` | what recurs across worlds, **kept separate from characters** — *"fusionner la boutique et le boutiquier fait qu'on ne peut pas déplacer la boutique sans toucher à la personne qui y travaille"* |
| `ReferenceMemory` | `src/creative/reference/memory.py:49` | the reference registry, backed by the platform memory — and **says** when it is not integrated rather than implying persistence it lacks |
| `LanguageKnowledgeBase` | `src/creative/language/knowledge.py` | language knowledge, with the promotion ladder that caps at `CORROBORATED` |
| user memory | `MemoryItem.user_id`, filtered in SQL | per-subject isolation (O04) |
| project memory | `src/creative/` project scoping + `media` project store | per-project |

**Seven memories, and the separations are load-bearing.** Each was written
because merging it with its neighbour caused a specific failure, and two of them
say so in their own docstrings.

## What OpenClaw persists

`docs/openclaw-agent-runtime.md`, read 2026-08-19, VERIFIED FROM OFFICIAL
SOURCE:

- *"State lives in the OpenClaw state directory"* — a shared runtime state
  database at `state/openclaw.sqlite`, and **per-agent** state at
  `agents/<agentId>/agent/openclaw-agent.sqlite`.
- *"Session rows live there alongside other per-agent state"*; transcript history
  under `agents/<agentId>/sessions/`.
- Reset: *"Delete those paths for a full reset"*, plus `/new`, `/reset`, and
  `openclaw sessions cleanup`.
- **A memory system distinct from session transcripts: not stated.**

`INFERENCE`: what OpenClaw persists is **session state and transcripts**, not a
memory architecture. It is closer to `src/agent/context.py` than to
`src/memory_engine/`.

## §11's question, answered

§11 asks which of three the arrangement should be. The answer is the third, with
the boundary drawn explicitly.

**`A CONTROLLED COMBINATION`** — and the control is one sentence:

> **OpenClaw's SQLite files are session scratch. GalSen IA's memory engine is
> the source of truth. Nothing moves from the first to the second except through
> `live_context/memory.py`'s gate — permission *and* a declared link.**

Why not the other two:

- **`GALSEN-IA MEMORY` alone** would mean OpenClaw writes nothing between
  turns, which is not how its runtime works — the state directory is not
  optional.
- **`OPENCLAW SESSION MEMORY` alone** would put conversation state outside every
  guarantee this repository has built: no `user_id` filter, no consent scope, no
  retention policy, no *"absence de portée vaut refus"*. §28's five acts —
  record, retain, upload, index, share — would all happen, silently, in a SQLite
  file nobody declared.

**The duplication §11 warns about is real and specific.** OpenClaw's per-agent
SQLite would hold conversation history that `memory_engine` also holds if
anything is promoted — two stores, two retention rules, and only one of them
governed by `retention.authorize_act()`. The rule above exists so the answer to
*"which one is true?"* is never "both".

## The measured obstacle to the combination

`live_context/memory.py` (written in the previous programme) already refuses a
write without **permission and a declared link**, and refuses a consent naming
somebody else. Feeding it from OpenClaw requires knowing **which subject** a
session belongs to.

O04 measured that OpenClaw's answer is *"Session IDs select routing; they do not
authorize one tenant against another."* A routing key is not a subject.

`INFERENCE` for O11 and O12: **the controlled combination requires GalSen IA to
assign and hold the subject itself**, never to read it back from OpenClaw's
session. That is implementable — the adapter creates the session on behalf of a
known actor — but it means the adapter, not OpenClaw, owns the identity for
every write. Recorded as a design constraint, not as a blocker.

---

## What O06 hands forward

1. **Provider coverage is not the obstacle** — every family §10 names is
   supported.
2. **Provider *configuration* is.** An OpenClaw holding its own keys defeats
   ADR-014's default, and the existing sovereignty test would still pass while
   the guarantee was false. → O12, and it is a `REJECT` for that arrangement.
3. **One viable shape**: OpenClaw configured against GalSen IA's own
   OpenAI-compatible endpoint, so `ModelRouter` stays authoritative.
4. **`UNKNOWN` to close before O11 concludes**: can OpenClaw be constrained to
   exactly one provider, with configuration the agent cannot edit?
5. **Memory answer**: controlled combination, session scratch versus source of
   truth, with the gate already written.
6. **Identity constraint**: the adapter assigns the subject; OpenClaw's session
   ID is never read as one.
