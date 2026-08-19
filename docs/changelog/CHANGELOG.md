# Changelog — GalSen IA

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.
This project follows Semantic Versioning; the version lives in `src/version.py` and
nowhere else. Versioning policy and release types → `docs/roadmap/roadmap.md`.

`v0.1.0` is the first release, and it is a **prototype**: the platform's headline
capability answers `503` until an operator configures a model provider. Release notes →
`docs/changelog/releases/`.

## [Unreleased]

### Added — 2026-08-19 — MoneyPrinterTurbo as a declared provider (Master Update Directive V4, 15 phases)

Ten volets, fifteen phases, all completed. Full report →
`docs/providers/final-report.md`, written to the thirty-one points of §42.

**MoneyPrinterTurbo does not generate video**, and finding that out before
writing the adapter is the whole value of the nineteen audit steps §36 puts
first. It composes stock footage retrieved from Pexels and Pixabay. Written
first — the natural instinct given the directive's framing — the adapter would
have been declared `text_to_video`, and a router would eventually have served
someone footage of a stranger for "a scene with my friend".

- **A new task, `stock_assembly`**, in both the media and creative vocabularies.
  Two acts, two names; that is the decision with the most consequence
- **First provider either programme's router has ever selected**:
  `stock_assembly` non-commercial → `SELECTED`; commercial → `NO_PROVIDER`
  because output rights are unread; `text_to_video` → never offered
- **Invocation is `API`, not import** — `edge-tts` is LGPL-3.0, and ADR-024
  already established that calling a copyleft tool as an isolated process is not
  the same act as linking it. No dependency added
- **The repository is MIT; the capability wanted is copyleft.** Exactly the
  confusion §30 exists to prevent, found by reading rather than assuming
- **Nothing replaced.** §21 classification: 8 KEEP, 3 EXTEND, 1 ADAPT,
  0 DEPRECATE, 0 REPLACE

Two defects of my own were found by writing tests: `min_vram_gb = 0` was treated
as a VRAM requirement and rejected a provider needing no GPU, and the adapter
declared 1920×1080 so a 1080×1920 portrait request — MoneyPrinterTurbo's primary
use case — was refused on its height.

Three repository guards caught three more, all right: the corpus loader refused a
value that did not say how it was established, the published ADR count moved
30 → 31, and three new environment variables had to be documented.

Full suite: **6 233 passed, 11 skipped, 3 deselected, 1 failed** — the `v0.1.0`
tag, pre-existing.


### Added — 2026-08-18 — Style registry (volet C19, §46) — a gap the plan had lost

The forty-three-phase plan never allocated a phase to §46's StyleEngine. The
PHASE 0 audit had classified it `EXTENSION_REQUIRED`; the plan lost it, and
nothing caught that, because **a missing phase produces no failing test**. It was
found by re-reading the directive against the code.

Measured before writing anything: the creative representation tracked `domain`,
`duration_seconds` and `aspect` and nothing else — "une scène en style anime"
lost the word "anime" between the request and the render.

- `corpus/creative/styles.yaml` — the ten families of §46, **extensible by a
  row**, with French and English aliases. This platform's users write French; a
  registry matching only English would never fire
- **No default style, ever.** A request naming none stays without one, and that
  is not a gap to fill — style is deliberately absent from `CHAMPS_REQUIS`,
  since otherwise every style-less request would be declared incomplete
- **Two styles named means neither is taken**: resolving an author's hesitation
  decides in their place
- **The style never enters `WorldState`** (already true since C09, now checked
  rather than trusted by `world_is_style_free()`). Style inside the world would
  make the first continuity check compare a documentary against a drawing and
  report a break that does not exist
- A shared alias is refused at load time — the render would depend on the file's
  reading order

One defect found on the first run: "un dessin animé" resolved to nothing,
because "dessin animé" *contains* "animé", lighting two styles and firing the
ambiguity rule wrongly. Fixed by discarding any match contained within another:
the longer phrase is the more specific one, and it is the author's.


### Added — 2026-08-18 — ADR-029's remaining debt: lockout, password reset, breach disclosure

ADR-029 chose option C and listed, in its own *Consequences*, what remained
owed. A debt written into an ADR and never settled eventually reads as a
decision. `src/auth/protection.py` settles it, plus two routes and a lockout
wired into `/auth/login`.

**One rule runs through all three: none of them may reveal which accounts
exist.**

- **Lockout** counts a failure whether the address exists or not. Counting only
  real accounts would make the lock an existence oracle — more reliable than an
  error message, because it survives reading the code. Addresses are stored as
  digests. A locked login answers `429` with `Retry-After`, not `401`: the
  account is not refused, it is held
- **Password reset** answers identically for a known and an unknown address, and
  the token never appears in the response. Single-use, time-bounded, and
  consumed *before* the new password is validated — a token replayable after a
  policy rejection would be a second password that never expires
- **Breach disclosure** computes what must be said and to whom, then reports
  `NOT_SENT` while no delivery channel is configured. `READY` never means "the
  people were told"; only something that actually sends can say that

**A real defect was found while writing the tests**: the reset route read
`getattr(user, "user_id", None)` where the field is `id`, so it returned `None`
for every real account and never issued a token — while answering exactly as if
it had. Invisible from the response *by construction*, since the rule is to
answer the same in both cases. That is the price of the rule, and it is paid by
a test that inspects the service's state. That test now exists.

`UserManager.set_password()` added: deliberately more permissive than
`change_password` (the person no longer knows the old one), and refusing an
OAuth-only account, where setting a password would open a second way in that its
owner never asked for.

API routes: 140 → **142**.


### Added — 2026-08-18 — Universal Creative Intelligence (volets C13–C18, programme complete)

Nineteen volets, **43 phases**, all completed. Full report →
`docs/creative/final-report.md`, written to the twenty-five points of §76.
`src/creative/`: 29 modules, 9 611 lines; `tests/creative/`: 370 tests.

**The orchestration layer is built and verified; nothing generates.** Those are
two statements and the directive spends §1 insisting they stay apart. The
platform can structure an intent, name an entity, hold a world, plan shots,
route by capability, preserve a speaker's recording, refuse a consent it does
not have, and say what it cannot measure. It cannot produce a video, a voice, or
an identity score.

Measured rather than recalled:

- **0 providers cleared commercially** — 8 weight licences `UNKNOWN`, because
  `huggingface.co` has no route from this container. Licence is a routing input,
  so `route()` returns `NO_PROVIDER` for a commercial request
- **7 identity dimensions, 7 `NOT_MEASURABLE`, 0 carrying a value**
- **VRAM `NOT_MEASURED`, not `0`** — zero licenses a conclusion, unknown forbids
  one
- **Vertical slice: 7 of 13 stages actually happen**, `produced_video` False,
  and `final_video` stays in the total — dropping it would make the chain look
  complete
- **25 golden scenarios: 19 `VERIFIED`, 6 `BLOCKED`**, in 365 ms with no
  network and no model. A `BLOCKED` is an assertion that a missing capability is
  *reported*, not a skipped test
- **Both audio-video pipelines blocked, on different stages, neither
  recommended** — §43 forbids assuming one is superior

Two of the repository's guards caught mistakes of mine, and both are recorded in
the report: the published route count (144 counted framework-generated routes;
the real figure is **140**), and suite totals written into a draft before the run
finished.

Full suite: **6 126 passed, 11 skipped, 3 deselected, 1 failed** — the `v0.1.0`
tag, pre-existing and unrelated.


### Added — 2026-08-18 — Multilingual layer and language knowledge (volets C13–C14)

Two volets of the Universal Creative Intelligence programme (directive V4,
§24–§33), implementing ADR-027. Plan and progress → `docs/creative/phase-plan.md`.

- **A language is now data, not code.** `corpus/creative/languages.yaml` declares
  19 languages with their ISO register, script and writing direction;
  `src/creative/language/registry.py` loads it and refuses a file it cannot
  trust — duplicate code, invented direction, or a validation language named
  and then missing. Adding Bambara is a row, which is what §24 and §64 ask for
- **Fixed: two of the directive's own golden tests could not be expressed.** The
  voice layer validated a segment's language against the subtitle engine's four
  languages (`fr`, `en`, `wo`, `ar`), so a Serer or Lingala recording — golden
  tests 5 and 6 of §63 — was *refused*. It now validates against the registry
- **Declared is not supported**, and the matrix keeps five separate columns to
  say so: nameable, documentable, subtitleable, understood, speakable. Measured
  today: 19 nameable, 14 documentable, 4 subtitleable, **0 understood, 0
  speakable**. Of the 15 validation languages of §24, four are fully carried
- **Code-switching is structural** (§25): language belongs to a segment, spans
  and switch points are derived, and there is deliberately no "dominant
  language" — computing one would invite using it. Switching *inside* a segment
  is reported `UNKNOWN` with its reason: detecting it needs word alignment,
  therefore transcription, which is unavailable here
- **`AudioSegment` carries dialect, region and pronunciation.** A dialect
  without a language is refused
- **The validation ladder is an invariant, not a guideline** (§28, ADR-027):
  frequency raises an observation to `CORROBORATED` and no further — no count,
  however large, produces `VALIDATED`. That needs a named human; `OFFICIAL`
  needs an external authority and a reference someone can re-read, and the
  platform is refused as its own authority
- **The private/global boundary has exactly one gate.** `publish()` requires a
  named consenter and a written consent, both recorded in the entry's history.
  Nothing promotes across it automatically — not frequency, not validation
- **Competing meanings coexist** (§32). A user's correction creates a new
  observation and leaves the original intact: overwriting would make the last
  person to speak the authority on the language
- **Nothing is trained on conversations**, and `training_status()` makes that
  checkable rather than promised — it names §31's seven conditions, all
  `NOT_MET`, and states what separates knowledge acquisition from training

62 tests added (`tests/creative/test_language_layer.py`).

### Added — 2026-08-18 — Multi-user authentication (ADR-029, option C)

The project owner chose option C of ADR-029: **the platform has accounts, with
passwords**. ADR-010's "no credential store" position is amended, not silently
contradicted — its own trigger said it would be revisited when self-service
signup existed.

- `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh` are mounted.
  `GET /auth/me` now accepts a Bearer token **or** an API key and reports which
  one served. Every pre-existing route authenticates exactly as before
- **A presented Bearer token is authoritative.** Invalid or expired means
  refused — never a silent fall back to `X-API-Key`, which would let an expired
  user token plus an admin key grant admin access
- A refresh **re-reads the role from the store**, never from the token, so a
  demotion takes effect at the next renewal. Login answers the same thing for an
  unknown account and a wrong password, so it does not enumerate addresses
- The three entry points are necessarily public — you cannot authenticate to
  obtain your first credential — and are declared so in `ROUTES_PUBLIQUES` with
  what protects them instead. **Registration is open**: on a reachable instance
  anyone gets a `user` account. That is what option C's "full self-service"
  means; restricting it is a separate decision

### Fixed — 2026-08-18 — three defects in the authentication layer before mounting it

Found by reading the code before wiring it, not after.

- **A default signing secret was written in the repository** and the code only
  logged a warning. A deployment that forgot `GALSEN_JWT_SECRET` signed its
  tokens with a public value: anyone who read the source could forge an admin
  token. There is now **no default** — absent or shorter than 32 characters, no
  token is issued and the routes answer 503 with the command that generates one.
  A counter-test fails if the removed value ever returns
- **The secret was read once at import.** An operator loading a `.env` after
  importing the application got an unexplained 503 with the variable correctly
  set. It is read at construction now
- **No password length check.** bcrypt stops at 72 **bytes**; versions before 4
  truncated silently, so two passphrases sharing their first 72 bytes
  authenticated each other. bcrypt 5 raises instead, which surfaced as a 500.
  The limit is now checked explicitly and answers 409 — an accented character
  counts as two bytes, which counting characters would have missed

### Added — 2026-08-17 — Coding Engine, edit blocks and OpenGAP interop

Ported from a second development line that had branched off `main` before the
media and creative programmes. What that line built on top of an outdated base
was reconciled rather than merged wholesale: two of its packages were **dropped**
because this line already did the same thing better.

- **Coding Engine** (`src/coding_engine/`, ADR-028) — OpenHands, Aider and
  SWE-agent behind an interface the platform owns. None is a dependency, no code
  is vendored, `requirements.txt` is unchanged, and each installs in its own
  virtualenv (`scripts/install_coding_engines.sh`). The platform runs with zero,
  one, two or three available; a missing engine reports how to fix it
  - routing is by **capability**, never by name: the router contains no engine
    name, and a fourth engine is routed by registering it
  - the model always comes from the Model Engine; an adapter given none reports
    unavailable instead of picking one. A test enumerates forbidden imports,
    hosts and key variables to keep it that way
  - execution goes through **`src/sandbox`**, not a second subprocess loop —
    kernel limits and group cleanup are the platform's, with a coding-sized
    policy. Approvals use the Approval Engine, runs are audited as `coding`, and
    a task needing approval is **refused** when the gate is unavailable
  - `GET /coding/engines`, `POST /coding/task`; status follows the outcome
    (503/403/202/504/422), never a uniform 200
- **Edit blocks** (`src/code_edit/`) — the model names the exact text to replace
  and the platform applies it: nothing outside the given root, exactly one match
  or refuse, all-or-nothing, no silent overwrite
- **OpenGAP interop** (`src/interop/`, ADR-023) — the 17 registry agents
  published in an open format. The **specification** is implemented; the upstream
  TypeScript code is not vendored, so the platform survives its deletion

### Fixed — 2026-08-17 — the suite goes from 8 red to 1

Priority 1 in `docs/memory/priorities.md` is *keep the suite green*, and it was
not: eight tests had been failing. Seven are now fixed at the source; the eighth
is blocked on a decision that is not this repository's to take.

- **A failing suite was reported as passing.** `TesterAgent._run_batch` matched
  pytest's failure lines to suites by **string suffix**, and pytest names a file
  relative to its own rootdir — `../../../../../t/test_x.py`. Neither
  `suite.endswith(cited)` nor `cited.endswith(suite)` answers that, so the
  failing suite came back `passed: True`. The worst possible defect in the one
  agent whose job is to say what fails. Matching is now on the **resolved path**,
  with a basename fallback used only when the name designates exactly one suite
  of the batch — attributing at random is worse than not attributing
- **Playwright had become installed while declared absent.** The counter-test on
  tolerances fired, correctly. It is now declared in `requirements-optional.txt`,
  where its nature places it: imported only inside a capability probe, absence
  measured rather than fatal. Measured after the change: `browser_render` reports
  `AVAILABLE` with the browser path found, instead of `DEGRADED`
- **The declaration rule was too coarse.** `requirements-optional.txt` exists for
  lazily-imported dependencies whose absence disables a feature — its own header
  says so — but the guard demanded `requirements.txt` regardless, which would
  impose a browser on every install. Optional declarations now count, and a new
  counter-test (`test_une_dependance_optionnelle_est_chargee_en_lazy`) fails if
  an optional dependency is imported at module top level, so the door cannot
  widen in silence
- **Three Senegal tests needed data that no clean clone has.** `.gitignore`
  excludes `data/raw_senegal/*.json`, so they failed everywhere the data had not
  been acquired. They now skip with the acquisition command, and a new test
  running **always** checks the absent-data behaviour itself: `comparable: False`,
  the missing file named, and no invented count. Coverage goes up, not down

Still red, and deliberately: `test_l_etiquette_de_la_version_courante_existe_bien`.
The `v0.1.0` tag exists in no clone but the author's. Pushing it declares a
release, which is the maintainer's decision, not a repair.

### Changed — 2026-08-17

- `SandboxPolicy` gains `extra_environment`: variables supplied explicitly to a
  sandboxed program, rather than through `os.environ` (which would put them on
  the whole platform) or a command line (visible machine-wide). `to_dict()`
  serialises the **names** only
- The OpenGAP export converts `snake_case` registry ids to kebab-case, which the
  format requires, and keeps the original in `metadata.galsen_id`. An id that
  yields nothing conformant is **refused**, not replaced by an invention

### Added — 2026-08-16 — Universal media & video intelligence engine (`src/media/`)

A media engine built as **adapters with capability probes**, because the machine
it runs on has no `ffprobe`, no full `ffmpeg`, no GPU and no speech model — and
none of that is a reason to fake a result.

- **The state is computed, not written**: `readiness.py` walks the seventeen
  stages of the production chain and answers `ENGINE READY — MEDIA RUNTIME
  DEPENDENCIES PENDING, 1 STAGE(S) NOT IMPLEMENTED (VOICE)` — 10 `READY`,
  6 `BLOCKED`, 1 `ABSENT`. `ABSENT` is kept distinct from `BLOCKED`: one names
  something to write, the other something to install.
- **A capability is measured by interrogating the tool.** A `which ffmpeg`
  boolean would have been wrong in both directions here; `image2` is not
  `image2pipe`, and encoding PNG is not decoding PNG. Both distinctions were
  found by running an encode, and `frame_encode` is `AVAILABLE` because a real
  WebM was written.
- **No model supplies a timestamp**: a `Selection` carries a quote and a reason
  and has no time field. Cuts land on measured word boundaries, and the render
  is re-transcribed and compared afterwards — with no re-transcription the
  verdict is `NOT_VERIFIED`.
- Three QC outcomes rather than two (`PASS`, `FAIL`, `NOT_CHECKED`); reframing
  repositions instead of cropping and measures what the crop would have lost;
  progress is counted and `None` when the total is unknown; a benchmark whose
  capability is absent reports `NOT_MEASURED`, never `0`.
- **Two tool declarations**, `media` and `media_generation`: only the second
  carries an external effect, so only the second requires a human. Eight
  `/media` routes and a Media Studio at `/ui/studio.html` that displays measured
  state rather than a decorative timeline.
- **WanGP is an adapter and nothing was vendored** (licence not inspected, no
  GPU): `generate()` always raises rather than return a placeholder.
- Published numbers re-measured after the repository's own guards caught the
  drift: 22 → 24 declared tools, 123 → 131 routes. No test was weakened.
- Full report → `docs/media/final-report.md`. 483 tests in the package; suite at
  5369 passed, 8 skipped.


### Added — 2026-08-15 — Darra J, educational intelligence engine (`src/darra_j/`)

The curriculum is an **institutional source of truth**. GalSen IA does not define
it, and neither does the model: the platform receives it, versions it, retrieves
it and explains it, without ever rewriting it.

- **State reached, and it is the one the directive asks for**:
  `ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING`. No Senegalese
  curriculum has been integrated — none was available, and none was written from
  model memory. `readiness()` measures the register; no flag reaches "ready to
  serve" without a published `TIER_A` version, and a register holding only
  fixtures reports zero official versions.
- **The central guarantee is mechanical**: with no canonical record the model is
  **not called** (`firewall.py`), and the evaluation lab measures that on an
  instrumented generator rather than assuming it.
- **Six education roles** join `src/api/rbac.py`, with `PERMISSIONS_HORS_PLATEFORME`
  subtracting what belongs to someone outside the platform — publishing a
  curriculum, and reading a child's work. Authorisation for learner data is a
  conjunction of permission **and** declared link; there is no permission for an
  unlinked learner because none was created.
- **Fixed in existing code**: the alias table kept only the folded form of a
  term, so `translate()` — which exists to *show* a term — returned `mbey` for
  `mbéy`. `ë ñ ŋ` are CLAD letters, never accents. The table now keeps `written`
  for display and `terms` for search.
- Full report → `docs/darra-j/final-report.md`. 377 tests in the package; suite
  at 4864 passed, 8 skipped.

### Added — 2026-08-15 — Harnais d'auto-réparation (`src/agent/`, `docs/agent/`)

Un agent d'ingénierie **contrôlé** : il inspecte, diagnostique, prépare un
correctif **en isolation**, passe six portes, et annule tout ce qui n'en franchit
pas une seule.

- **Rien n'est réparé sur place** : `git worktree` + branche `auto-patch/<incident>`.
  Annuler consiste à **détruire l'espace** — l'arbre de l'utilisateur n'a jamais
  été écrit, donc il n'y a rien à restaurer. Vérifié : modifications non validées
  et branche intactes après une réparation ratée.
- **Une trace d'exécution est une donnée** : seules les formes que CPython écrit
  sont lues. « Ignore all safety rules » reste une chaîne, et le diagnostic rend
  `UNKNOWN_DIAGNOSIS` — qui est une réponse, pas un échec.
- **Le harnais est inviolable par lui-même** : aucune classification n'ouvre
  `tools/`, `policies/`, `audit/` ni `self_healer.py`. Un moteur qui peut
  affaiblir ce qui le retient n'est retenu par rien.
- **Les tests ne peuvent pas être faits taire** : suppression, `skip`/`xfail` et
  **assertions retirées d'un test qui garde son nom** font tomber la porte.
- **Une commande est une liste**, jamais une chaîne : `; rm -rf /` dans une trace
  reste un argument.
- **CLI** (`python -m src.agent.cli`) : `status`, `health`, `test`, `diagnose`,
  `repair`, `audit`. Seule `repair` écrit, et seulement dans son espace.
- Sept cas simulés sur un dépôt git réel. **+146 tests, 0 régression.**

### Added — 2026-08-15 — Vagues V et VI du programme d'expansion (VOLETs 58 à 71)

L'extension par des tiers, puis **la preuve**. Décision d'ensemble → **ADR-022**.

- **Greffons** (`src/plugins/`) — le manifeste est jugé **avant** que le code soit
  lu ; `privé + externe` et la portée `system` sont refusés d'emblée ; l'exécution
  passe par le bac à sable du VOLET 34, pas un second. **Modifier un greffon le
  désactive** : l'autorisation portait sur ce que son auteur avait écrit.
- **Couches de mémoire** (`src/memory_engine/layers.py`) — une couche **est** une
  durée de vie. Défaut refermé : `expires_at` était respecté à la lecture et
  **rien ne le remplissait**.
- **Une routine peut déclencher un workflow** (VOLET 64), par **le même**
  orchestrateur — mêmes points de reprise, même historique, même audit. Règle du
  travail sans témoin : **une approbation n'est jamais accordée par l'absence de
  quelqu'un pour la refuser** (`suspended`, avec le `run_id`).
- **Dégradation mesurée** (`src/integration/degradation.py`) — neuf sous-systèmes
  sondés isolément ; une sonde qui lève est rapportée, jamais propagée. **Dégradé
  n'est pas en panne** : ni bascule du statut global, ni perte de readiness.
  `GET /system/degradation`.
- **Un travail se suit de bout en bout** — le tour porte un `correlation_id` que
  l'exécution **reprend** ; `GET /observability/trail/{id}` assemble les sources
  en **appelant** la trace d'audit du VOLET 19 plutôt qu'en la refaisant. Vide ≠
  illisible ; rien n'est rapproché par l'heure.
- **Le travail est plafonné, pas les tours** — un tour n'est plus une unité de
  coût depuis qu'il peut faire tourner un workflow entier. Décompté **après**
  l'exécution, et même quand le tour échoue.
- **Le barème dit ce qu'il ne couvre pas** — chaque entrée déclare son domaine ;
  sept questions couvrent construction, sport, géographie, langues, santé,
  entreprise. Toutes `to_source` : **aucune réponse n'a été écrite**, et le
  barème compte toujours **0 entrée vérifiée**.
- **Démonstration de bout en bout** (`python scripts/demonstration.py`) — 5
  étapes `OK`, 2 `NOT_CONFIGURED`, 0 échec. **Elle a trouvé un défaut réel** : le
  routage passait la question entière à `answer_country()`, qui attend un nom de
  pays ; la couche mondiale était muette dès qu'on lui posait une vraie question.
  Corrigé par `find_country()`.

### Fixed — 2026-08-15

- Les chiffres publiés dans `CLAUDE.md` et `docs/architecture/overview.md`
  annonçaient **76 routes** et **3238 tests** ; la mesure en donne **123** et
  **4334**. Corrigés, et **tenus par une suite** (`tests/test_published_numbers.py`) :
  routes, agents, outils, ADR et sous-systèmes sont désormais confrontés au dépôt
  à chaque exécution.
- Un fichier de déclaration de canaux absent était indistinguable d'une
  déclaration vide (`declaration: NOT_FOUND — <chemin>`).

### Added — 2026-08-14 — Vague IV du programme d'expansion (VOLETs 51 à 57)

La connaissance. Rien n'y a été écrit de mémoire, aucune sortie réseau n'a eu lieu,
et deux domaines sont **déclarés vides avec leur raison** plutôt que remplis.

- **Registre de sources mondial** (`corpus/sources/`) — le répertoire entier est
  chargé ; un domaine déclaré deux fois **refuse le chargement**, en nommant les
  deux fichiers. **23 sources, aucune activée.**
- **249 pays dérivés** (`src/knowledge_engine/world.py`) de jeux déjà acquis.
  `global` porte la taxonomie, chaque pays porte sa propre portée. **34 désaccords
  entre sources rapportés côte à côte, jamais réconciliés.**
- **Séries mesurées** — population et PIB. Rien n'est interpolé, un pays absent
  rend `UNKNOWN` et jamais zéro, les agrégats ne sont pas des pays.
- **Fraîcheur** — l'âge se mesure contre la cadence de la chose. `built_at` date
  la dérivation, pas les faits. Le sport a imposé une seconde échelle, en
  **jours**, et une troisième valeur : `PERMANENT`.
- **Recherche documentaire** — titre indexé, accents ajoutés sans rien effacer
  (`ñ` distingue des mots en wolof), correspondance expliquée. La connaissance
  mondiale devient une source de `/search`, et les résultats portent un **extrait
  verbatim** — jamais un résumé.
- **Domaines `construction` et `sports`** — déclarés, vides, avec leur raison.
  La part normative de la construction est **territoriale** ; la particularité du
  sport est le **temps**.
- **Routage des deux couches** — la profondeur sénégalaise et la largeur mondiale
  ne se recouvrent pas, et la réponse dit laquelle a parlé.

### Fixed — 2026-08-14 — Défauts trouvés en construisant la vague IV

- **La FAO et l'OMS étaient déclarées dans le registre sénégalais** avec une
  portée mondiale. La garde des doublons introduite le même jour l'a révélé.
- **`delete()` de l'index documentaire recalculait** les termes d'un document au
  lieu de relire ceux qui avaient été indexés : un document réindexé restait
  trouvable par son ancien titre.
- **Le fournisseur mondial rendait l'Estonie et le Laos** pour « quelle **est** la
  monnaie du Sénégal » : `EST` et `LA` sont des codes ISO et des mots français.
- **`domain_state()` annonçait « base vide » sans compteur branché**, là où il
  fallait lire « personne n'a regardé » — la confusion que ce module prétend
  empêcher, commise par lui.

### Added — 2026-08-14 — Vagues II et III du programme d'expansion (VOLETs 43 à 50)

Ce que la plateforme sait faire quand personne ne la regarde. Rien n'y authentifie
avec un identifiant fabriqué, et aucun canal ne prétend avoir envoyé.

- **Connecteurs Google en lecture** (`src/connectors/oauth/`, `src/connectors/google/`)
  — OAuth 2.0 code d'autorisation avec **PKCE S256 obligatoire**, `state` à usage
  unique expirant en 600 s, jetons chiffrés (Fernet) ou refusés. Gmail, Drive et
  Agenda, **lecture seule**. Aucun identifiant n'existe dans cette installation :
  l'état est `NOT_CONFIGURED`, et c'est la règle qui fonctionne, pas un échec.
- **Étanchéité** (VOLET 46) — un contenu de boîte privée ne peut plus entrer dans
  la connaissance publique. Un trou réel a été trouvé en attaquant : `remember()`
  déposait du privé **sans propriétaire** dans un magasin partagé.
- **Routines** (`src/routines/`) — déclaration refusée à l'écriture plutôt qu'à
  trois heures du matin, décision pure et testable, journal borné, **budget
  quotidien** qui arrête la routine au lieu de la sauter, **arrêt d'urgence global**
  qui ne se lève jamais tout seul. Onze routes.
- **Workflows longs** (`src/router/workflow_checkpoint.py`) — une exécution garde
  son état pendant qu'elle dure. **Une étape aboutie n'est jamais refaite** :
  refaire une étape qui a eu un effet au-dehors est la façon dont un courriel
  devient deux. L'annulation est terminale ; le point de reprise appartient à qui
  a lancé l'exécution. Quatre routes : lister, lire, reprendre, annuler.
- **Notifications : les événements que personne ne verrait**
  (`src/services/notification/events.py`) — une routine qui s'arrête d'elle-même,
  un arrêt d'urgence engagé, une exécution longue interrompue. Le destinataire est
  **déduit** du propriétaire ; ce qui appartient à la plateforme part vers
  l'exploitation par son rôle.
- **Canaux de livraison** (`channels.py`, `config/notifications/channels.yaml`) —
  déclaratifs. Un canal sans identifiants rapporte `NOT_CONFIGURED` et nomme les
  variables manquantes, **jamais leurs valeurs**. Une destination partagée ne porte
  pas la notification de quelqu'un.

### Fixed — 2026-08-14 — Deux défauts trouvés en câblant

- **L'arrêt d'urgence des routines disparaissait** quand le serveur reconstruisait
  son planificateur : la couche de sûreté naissait avec lui. C'est exactement le
  défaut contre lequel elle est écrite, réintroduit par son propre branchement.
  Elle vit désormais au niveau du module, et un test conduit la reconstruction.
- **La reprise d'un workflow pouvait changer la question.** La demande d'origine
  n'était pas conservée, donc la route de reprise devait la redemander — et la
  moitié déjà faite aurait répondu à autre chose. Elle est consignée au lancement,
  et la route de reprise ne prend aucun corps.

### Added — 2026-08-14 — Vague I du programme d'expansion (VOLETs 37 à 42)

Le socle sur lequel les connecteurs Google seront branchés. Rien n'y authentifie,
aucun identifiant n'y est fabriqué : ce sont **six frontières**, toutes tenues par
du code et vérifiées par des tests.

- **Capacités d'outils** (`src/tool/capabilities.py`) — chaque outil déclare ce
  qu'il touche (`public` / `user_private` / `system`), ce qu'il change
  (`read` / `write` / `external`), et s'il peut tourner sans témoin. **22 outils
  sur 22 déclarés.** Deux règles que le registre ne peut pas violer : approbation
  et exécution sans humain s'excluent ; donnée privée plus sortie de la machine
  ne tourne jamais seule. Un outil non déclaré est refusé — « non déclaré » n'est
  pas « inoffensif ».
- **Pré-approbation étroite** — une **borne** de l'outil approuvée en
  configuration, avec nom, date et motif obligatoires. `terminal` reste sous
  portillon ; `python -m pytest` est approuvé, `python -c` ne l'est pas. La
  comparaison porte sur des mots entiers.
- **Plafonds de rôle** (`src/tool/authorization.py`) — `tool:execute` n'est plus
  un droit unique. Le verdict a **trois états**, et « il faut un humain » n'est ni
  un oui ni un non. **Personne ne saute une approbation**, administration
  comprise : elle qualifie l'acte, pas l'acteur. Appliqué sur `POST /tool/execute`
  et sur le chemin des agents.
- **Isolation des données utilisateur** (`src/security/isolation.py`) — il
  n'existe plus d'audience « non précisée » : `Audience.platform()` ne lit la
  donnée de personne. Le propriétaire est **déduit** de la portée déclarée de la
  source. Une portée absente n'est pas supposée publique. Écrire du privé dans un
  magasin partagé **lève**.
- **La base de connaissance est étanche** — les trois chemins d'écriture
  (`add_knowledge`, `ingest_file`, `AgentContext.add_knowledge`) refusent une
  source privée. `ingest_file` vérifie **avant d'ouvrir le fichier**.
- **Contrat de connecteur** (`src/connectors/contract.py`) — exigé à
  l'enregistrement. Portée privée et lien à une personne vont ensemble dans les
  deux sens ; un connecteur privé dit ce qu'il conserve.
- **Cycle de vie par sujet** (`src/connectors/lifecycle.py`) — cinq états, et le
  **retrait fonctionne quand rien d'autre ne fonctionne**. Un connecteur par
  sujet ne s'appelle pas sans sujet.
- **Sûreté** (`src/connectors/safety.py`) — `receive()` est le seul chemin de
  sortie : un courriel arrive en `EXTERNAL`, jamais en instruction. Les
  privilèges destructeurs exigent un motif écrit, et la demande excessive est
  refusée **avant** tout écran de consentement.
- **Masquage des secrets** (`src/security/redaction.py`) — une seule liste,
  partagée. Une garde AST vérifie qu'aucun module de connecteur ne journalise un
  secret, et elle est elle-même confrontée à une vraie faute.

`GET /tools/capabilities`, `/tools/{id}/capability`, `/tools/authorization`,
`/tools/{id}/authorization`, `/tools/authorization/matrix`,
`/connectors/{id}/contract`.

### Added — 2026-08-14

- **Acquisition de connaissance sous portillon (ADR-021)** — `src/acquisition/` : registre
  étendu (rangs `TIER_A`→`TIER_D`, `enabled: false` par défaut), enregistrement candidat et
  machine à états, récupérateur poli (agent véridique, `robots.txt` appliqué, débit par
  hôte, redirection hors domaine refusée, GET conditionnel), portillon d'approbation **par
  lot** avec empreinte, découverte profondeur 1 même domaine, extraction de métadonnées,
  détection de langue, barrière de confiance obligatoire, dix contrôles de qualité,
  proposition de manifeste en `DRAFT`. `scripts/acquisition_pilot.py` enchaîne le tout.
  **Rien n'ingère seul, et aucune source n'est activée.**
- **Wolof** — `src/wolof/clad.py` (alphabet officiel de 27 lettres, décret n° 2005-992,
  normalisation déterministe et idempotente), corpus **2105 phrases** acquis depuis
  UD_Wolof-WTB, `src/services/wolof/` (chargeur RAG et invite système).
- **Connaissance sénégalaise** — `scripts/ingest_all_senegal.py` : 14 régions et 45
  départements **dérivés** de geoBoundaries, rattachement calculé par géométrie.
  `scripts/ingest_senegal_domains.py` : 8 jeux acquis, 212 objets sectoriels.
  `src/services/senegal/` : RAG, comparaison de divergences, invite système.
- **RAG multilingue** — `corpus/languages/aliases.yaml` et
  `src/services/senegal/multilingual_aliases.py` : 16 concepts, 115 termes fr/wo/en.
  L'expansion **ajoute et ne retire jamais**, donc elle ne peut pas faire perdre une
  correspondance. Latence mesurée 0,1–0,5 ms.
- **Mesure du blocage réseau** — `scripts/activate_senegal_sources.py` : les 9 domaines
  `.sn` inscrits répondent `CONNECT → 403`. Le code distingue `blocked_by_environment` de
  `refused_by_site`, parce que les deux demandent des actions opposées.

### Fixed — 2026-08-14

- **Le déclencheur de `automated_acquisition` était circulaire.** Il mesurait le corpus
  sénégalais, c'est-à-dire le résultat de la capacité différée : `met` ne pouvait devenir
  vrai par aucun chemin. Il mesure désormais **une source activée au registre**, et un test
  empêche le retour de la circularité (5000 documents ne le franchissent plus).
- **La deuxième clause du déclencheur `graph_database` n'était pas mesurée.** « Un parcours
  au-delà de la profondeur 3 » était écrit, le magasin refusait, et personne ne comptait.
  Les refus sont comptés (`entities.depth_refusals()`) et franchissent le seuil à 10.
- **La règle du pluriel française amputait les alias wolof** : « xaalis » devenait
  « xaali » avant l'expansion, parce que les termes de requête étaient construits sur des
  mots déjà normalisés. Ils le sont sur les mots bruts.
- **La récupération répondait à côté avec l'air de répondre** : « Quelle est l'histoire du
  royaume du Cayor ? » rendait un département. Pondération IDF **plus** mots vides ; ces
  questions rendent `UNKNOWN`, ce qui est correct puisque le domaine est vide.
- **`languages.py` annonçait « aucun détecteur de langue n'existe »** — vrai jusqu'à
  l'étape 6, faux depuis. Le verdict est mesuré sur le fichier de marqueurs.
- **`knowledge_architect` laissait la langue vide** en affirmant qu'aucun détecteur
  n'existait ; il propose désormais la langue détectée, **marquée comme détectée**.
- **`chunk_text` ouvrait le fragment suivant au milieu d'un mot** (« ari » au lieu de
  « ñaari ») : le recouvrement recule jusqu'à une frontière de mot.
- **`retrieval_date` n'était posée nulle part** alors qu'elle fait partie de la provenance
  minimale : aucun document ne pouvait atteindre `VERIFIED`. Posée dans `acquire()`.
- **`reconcile()` traitait la sentinelle `unknown` comme une déclaration de langue**, et
  `from_html` la tronquait en « unkno » : tout document sans langue déclarée partait en
  quarantaine.

### Fixed — 2026-08-13
- **`detect_contradictions()` ne compte plus les années comme des chiffres en désaccord.**
  « 125 tonnes en 2022 » et « 130 tonnes en 2023 » étaient rapportés comme un conflit
  numérique ; dans une base statistique, presque chaque passage porte une année. Les
  années sont exclues des nombres comparés et servent désormais à écarter un couple dont
  les périodes diffèrent. Même année et chiffres différents reste un conflit.
- **`source_registry._domaine()` lit les URL relatives au protocole.** `//ansd.sn/x`
  rendait une chaîne vide et recevait le traitement « aucune URL : la provenance est le
  manifeste » — la porte exacte par laquelle une autorité usurpée pouvait passer. Un nom
  de fichier (`rapport.pdf`) reste sans domaine ; les domaines inscrits au registre, qui
  s'écrivent sans protocole, passent par `_domaine_declare()`.

### Added — 2026-08-13
- `docs/deployment/etat-du-projet.md` — rapport d'état au propriétaire : mesures, les
  quatre points bloqués avec leur destinataire, et les cinq actions humaines dans l'ordre.
### Fixed
- **The four VOLET 36 agents were unreachable** (`workflows/workflows.yaml`)
  - `senegal`, `verifier`, `knowledge_architect` and `data_engineer` were in the registry
    and cited by no workflow. The planner's selection **restricts** a pipeline and never
    widens it, so the `risk` and `geographic_scope` axes were recommending agents no
    execution could retain — a capability shipped that nothing reaches
  - Three workflows: `question` (where the two acting axes become visible), `ingestion`
    and `series`. `researcher` stays in `question` so the recommendation always has a
    non-empty intersection; without it a plain request falls back to "whole pipeline",
    the opposite of the sorting the axes promise
- **The health filter refused useful sentences** (`src/knowledge_engine/health_policy.py`)
  - Probing my own filter showed the diagnosis pattern rejecting "Elle a une durée de
    protection de trois ans" and "Vous avez le droit de consulter gratuitement" — useful
    sentences, refused by a safety policy. That is the inverse of the defect the filter
    exists to prevent, and my own counter-test said as much while using a single phrasing
  - Tightened to verbs that **attribute a condition** (`souffrez`, `êtes atteint`,
    `présentez les symptômes`, `souffre de`), plus "vous avez" except before a declared
    non-clinical continuation. The `(il|elle) a un(e) X` pattern is gone: it mostly caught
    ordinary French
  - The counterpart is verified rather than assumed — fixing a false positive often lets a
    real one through. Four genuine diagnoses stay refused, and `NON_DETECTE` names what now
    escapes
- **`robots.txt` was only half read** (`src/knowledge_engine/collection.py`) — found while
  re-reading my own code. Only `Disallow` was applied, so a publisher writing `Disallow: /`
  followed by `Allow: /public/` had `/public/` refused: a refusal by incomplete reading,
  which looks cautious and turns away exactly what the publisher meant to open. `Allow` is
  read now, and the longest matching prefix wins, as the format requires
- **The document search source leaked other people's documents when first wired**
  (`src/services/search/providers.py`)
  - The document engine is a platform-wide store with no notion of owner, and `/search` is
    multi-user (ADR-010). A guard test caught it immediately: one user's search returned a
    document another had registered
  - A document is now returned only if it **declares itself** — public, or owned by the
    request's subject. Anything declaring nothing is withheld, and the count of withheld
    documents is reported: a source that filters silently reads like a source that found
    nothing
- **Three live `NameError` crashes, found by configuring a linter** — none was visible to
  the test suite
  - `SimpleStreamHandler.collect_stream_response_async` → `NameError: chrunk`. A comment
    next to it read *"probablement une typo, devrait être chunk"* and the typo stayed
  - `WeightedResponseRanker.rank_responses` → `NameError: weights`. The name existed in a
    different method
  - `InMemoryModelStore.cleanup_expired` → `NameError: ModelStatus`, **as soon as one model
    exists**. On an empty store the loop body never runs, which is why every test passed
- **A weight was declared twice and one value silently lost.** `"accuracy"` appeared twice
  in the same dict literal; Python keeps the last and discards the first
- **A documented override did nothing.** `ObjectDetector.detect` read `min_area` from its
  arguments — documented as *"min_area to override"* — and then compared against
  `self.min_area`
- **Two tests could not fail.** `assert False` raised an `AssertionError` that the
  `except Exception` below caught, and the guard then looked for the word "error" in the
  message — which the assertion message itself contained. Converted to `pytest.raises`
- **An abstract method was not abstract.** `NotificationStore.get` had an empty body and no
  `@abstractmethod`: a store forgetting to implement it would have returned `None` for
  every notification instead of failing at instantiation
- **221 dead imports** removed. One was a deliberate re-export, caught by the suite and
  restored with the reason written next to it

### Added
- **A third search source answers, and the fourth says why it never will**
  (`DocumentSearchProvider`, `SearchResponse.sources_unavailable`)
  - The backlog said document and vision both waited on their engine to produce searchable
    text. True for vision, **false for documents**: the index has always existed, only the
    provider was missing. The backlog entry was corrected rather than worked around
  - A source with no provider is reported **with its reason** instead of being skipped:
    `sources_used` alone let a caller believe four sources were queried and one had nothing
    to say. Vision's reason names what is actually missing — no indexed text, so nothing to
    search; it is not a provider that is lacking
- **ADR-020 (`proposed`) — what analytics may retain**, and it decides nothing. Three
  options with their real cost, recommending aggregates-only after C4: an aggregate
  answers "is the platform degrading?", while retained events answer a question the audit
  trail already covers and carry the data whose retention needs a stated purpose
- **Normalisation stopped applying French rules to non-French text**
  (`src/text_normalization.py`, `src/knowledge_engine/knowledge_indexer.py`)
  - Stripping a final `-s` is right in French and English. Applied to Wolof it mangled the
    word: `ndaws` became `ndaw`, a form nobody ever wrote. The rule is now restricted to
    languages that have it, with a French default — changing the default would silently
    rewrite every existing caller's behaviour
  - The real risk was not the rule, it was **symmetry**: normalisation is safe only
    because it applies to both sides. Indexing Wolof unmangled while queries stay French
    would make present documents disappear. Solved by query expansion
    (`token_variants()`), not by an invented detector — both forms are looked up, so
    matches can only be gained
  - Documents are indexed in their declared language, rebuild and consistency check
    included; otherwise the check would have called every non-French document stale
  - The capability report followed the measurement: `normalization` is no longer "blocked
    on L3" but `partial` for Wolof **with the reason that remains** — accent folding
    merges `ñ` and `n`, two distinct letters in Wolof
- **Collection is decided under a gate, and health is answered differently**
  (`src/knowledge_engine/collection.py`, `health_policy.py`)
  - Downloading acts on someone else's server, so four conditions hold and none is
    optional: the source is **in the registry**, `robots.txt` is **applied** rather than
    consulted, the licence is declared, and a human approves (ADR-006). The module builds
    the request — **it downloads nothing**, and a guard test checks it never reaches the
    network
  - An unknown licence **degrades instead of blocking**: the document becomes
    `reference_only`, citable by URL and not reproducible in full. Blocking would discard
    the best sources first. An absent `robots.txt` forbids nothing — that is its meaning —
    and a named agent's rules add to `*`'s rather than replacing them
  - A refused plan cannot be submitted: asking a human to approve what the rule already
    rejected would make the refusal negotiable
  - Health gets a **higher source floor** than the general reliability threshold —
    `OFFICIAL`, `GOVERNMENT`, `PEER_REVIEWED` only — because trustworthy industry
    documentation on a technical subject is still industry documentation about a disease
  - **No dosage, no diagnosis, no prescription, whatever the sources say**, and the
    refusal is code applied *after* generation. A prompt instruction is a wish: "500 mg
    every six hours" appears in an official leaflet, and repeated to someone whose weight,
    age or pregnancy is unknown, it is a sentence that harms. A counter-test pins that an
    ordinary answer is **not** refused — a filter that refuses everything protects nobody
  - The safety notice travels with every health answer, refusals included, and the floor
    applies **before** scope arbitration: ranking under-qualified sources by country would
    mean choosing which bad one to serve
- **Gaps are measured from real questions, candidate sources come only from the registry,
  and contradictions are reported rather than resolved** (`src/knowledge_engine/gaps.py`,
  `source_discovery.py`, `contradictions.py`)
  - A gap is a `subject × scope` pair that **real questions** hit without an answer, read
    from the audit trail the platform already writes. A gap nobody ever asked about is not
    a gap, it is a guess about the future — and one unanswered search is an accident, not a
    need, so the threshold is two
  - Discovery proposes from the declared registry and **decides nothing**. "Search the web
    and learn" is the fastest way to fill a knowledge base with confident nonsense; a
    source outside the registry can be proposed by a person, never used by the platform.
    Sources matching the requested scope come first — ANSD before FAO for a Senegalese gap
  - Contradictions are found between passages of the **same subject and scope** that share
    most of their terms and differ in polarity or in numbers. **No winner is named**: a
    `winner` field would read as a conclusion and nobody would reopen the pair. The most
    recent source is not automatically the right one. Two countries do not contradict each
    other, they differ
  - Blind spots are named (`not_detected`), and a guard test checks none of the three
    modules reaches the network — collection is a later chapter, behind the approval gate
- **Reliability now comes from a registry, not from the document claiming it**
  (`corpus/sources/senegal.yaml`, `src/knowledge_engine/source_registry.py`)
  - `SourceCategory` existed and `retrieve_reliable()` weighed answers with it, but the
    category was declared by whoever ingested: a blog filed as `government` weighed as
    much as the official gazette
  - Two refusals, both wired into `ingest_file`: a denied URL (social networks, video
    platforms, messaging apps, anonymous content) is rejected **with its reason** — a
    silent down-rank would let it in and let it weigh a little, which is worse — and an
    authority category (`official`, `government`, `peer_reviewed`) requires a registered
    domain, so declaring a blog as official becomes impossible rather than merely dishonest
  - Domain matching compares labels, not string endings: `ifan.ucad.sn` inherits from
    `ucad.sn`, `faux-ansd.sn` inherits nothing. A document with no URL gets no verdict —
    its provenance is the manifest — and a **missing registry refuses** authority
    categories rather than accepting them all
- **Retrieval reads the scope axis, and the answer says what it was built from**
  (`src/knowledge_engine/scoped_retrieval.py`)
  - A policy, **not a second retriever**: `retrieve_reliable()` still does the searching;
    this module orders and arbitrates. Two retrieval paths would stop returning the same
    thing for the same question and nobody would know which one answered
  - One prohibition: a national subject with no local source gets no answer. It does not
    depend on how many items were found — a hundred global passages are not a national
    source, they are a hundred ways to answer about the wrong country. Everything else:
    local first, global still there
  - The `senegal` agent now applies that policy instead of reimplementing it
  - `scope_notice()` travels with the result, including through `retrieve_for_prompt`. The
    case that matters is an answer about Senegal built from **no** Senegalese source:
    without that sentence it reads exactly like a well-sourced answer
- **Two agents that propose and never apply** (`agents/knowledge_architect/`,
  `agents/data_engineer/`)
  - `knowledge_architect` proposes the manifest entry a human writes by hand today —
    title, scope, subject, candidate entities — as `DRAFT`. Setting `scope: country:sn`
    decides on its own which questions the platform may answer with that document, and
    that decision belongs to a person
  - It does not guess the source category (that depends on who publishes, not on the text)
    or the language (no detector exists). An uncertain classification proposes
    `unspecified` **and says so**: a guessed subject makes a document findable under a
    label it does not deserve and invisible under the right one
  - `data_engineer` **refuses before it describes**: a series without declared units,
    period and source is rejected. An ANSD figure without its year is a wrong figure
    waiting to be cited — "18 million" is true, false or meaningless depending on a year
    nobody wrote down — and `montant` does not say whether it is FCFA, thousands, or
    dollars
  - A column of four-digit integers is ambiguous between a year and a count; it is
    reported as `number`, and the declared `period` carries the year. An empty column is
    `unknown`, never "text"
  - The shared markers moved to `src/knowledge_engine/markers.py` now that a second
    reader exists; a test asserts a single file carries them
- **Ten axes describing a request, attached to the plan that already existed**
  (`agents/planner/agent.py`)
  - Not a module, not an agent, **not a second planner** — there is one, and a test pins
    it. The axes are attributes of the request hung on the plan the planner already builds
  - Every axis reports its method alongside its value (`keywords`, `measured`,
    `intent_rules`, `declared`, `crude`): read without its method, an axis would pass for
    an observation in all five cases
  - **Two axes act, eight are observed.** `risk` (health, law, money) recommends
    `verifier`; `geographic_scope` recommends `senegal`. The other eight are measured
    before being wired to anything — an axis wired before anyone has seen its values on
    real requests is a decision nobody made
  - `axes_effect` names which axis added which agent; without it an agent would appear in
    the plan with no way to say why. The recommendation stays a recommendation:
    `workflows.yaml` remains the authority on what *may* run
  - `language` carries `detected: False` — no detector exists, so a declared language must
    not read as a recognised one
- **Entities and relations exist as objects, and neither enters without a source**
  (`src/knowledge_engine/entities.py`, `src/storage/sqlite_entity_store.py`)
  - The existing graph stored `node = knowledge id`: a person, a law, a place had no
    existence in it, and **a relation carried no source at all**. "This law repeals that
    one" read as a fact nobody could trace
  - A relation's sources are **distinct** from its endpoints' — knowing who the minister
    is and knowing they head that ministry need not come from the same document — and it
    carries `valid_from` / `valid_to`, because a relation stops being true
  - `confidence` stays `None` when the source declares none: a default 0.5 would be an
    invented number read as a measurement
  - Deterministic ids (type + normalised label + scope) merge a re-ingested entity instead
    of creating a duplicate nothing would ever reconcile
  - **No graph database**, and the trigger that would justify one is written down: depth
    above 3, ~100 000 entities, or a measured query over 200 ms. A traversal deeper than
    the maximum refuses and quotes it
- **Two agents defined by what they refuse** (`agents/verifier/`, `agents/senegal/`)
  - `verifier` carries a verdict and stops there. It never rewrites the answer — measuring
    and correcting are two roles — and never asks the model whether it was right. With no
    passage retrieved it reports `cannot_verify`, never `supported`: a verdict with nothing
    behind it looks like a check that happened. `cannot_verify` and `unsupported` stay
    apart: "nothing to compare this to" is not "compared, and nothing backs it"
  - `senegal` applies ADR-019 where no ranking function should decide: on a national
    subject with no national source, it **refuses**. Law, administration and languages do
    not travel, and answering a Senegalese land question with foreign law is fluent,
    plausible and wrong exactly where it costs someone a plot of land. The refusal names
    what was found but not served, and what would settle the question
  - It is not the only path to Senegalese knowledge — scope-aware retrieval serves every
    question; this agent owns the decision to refuse
  - Fixed on the way: `AgentContext.search_knowledge()` returned neither `scope` nor
    `subject`, so an agent read the base without ever seeing where its knowledge held
- **Unsupported claims are counted, and cited sources are checked against what they
  are made to say** (`src/knowledge_engine/factual_evaluation.py`)
  - Citation coverage counted items carrying a source; retrieval evaluation measured the
    search. Neither said whether an **answer** was true — an answer could show 100 %
    citation coverage while claiming what no cited passage says
  - The evaluator never asks the generating model whether it was right: it would measure
    that model's confidence in itself. This half is mechanical, so it works with C1 closed
  - Support is **lexical**, and the module says so. The dangerous case is a claim that
    contradicts its passage — it shares nearly every word with it, so overlap alone would
    call it supported. Polarity is compared separately: `DISPUTED`, never `SUPPORTED`
  - What it cannot measure travels in every report: factual correctness, contradiction
    between sources, semantic relevance — named with their reason, carrying no number
  - `docs/evaluation/senegal-facts.jsonl`: **10 questions, 0 verified entries**. Entries
    name the question, the expected *shape* of an answer and the institution that would
    settle it — never an answer — and `score_entry()` refuses to score them. A benchmark
    written from memory would make every future measurement a measurement of that memory
- **Wolof, Pulaar and Serer can be declared, stored and retrieved** (`Language.WO`,
  `Language.FF`, `Language.SRR`; `src/knowledge_engine/languages.py`)
  - A Wolof document could previously only enter the base labelled as a language that is
    not its own. `ingest_file(language=…)` and the corpus manifest now accept them, and
    an unknown language **refuses the document** instead of falling back to French
  - `SRR` is not a typo: Serer has no ISO 639-1 code, `srr` is its 639-3 code
  - **Labelling is not understanding**, and `GET /knowledge/languages` says so capability
    by capability: labelling and lexical retrieval yes; detection and translation no;
    normalisation partial (the rules are French); semantic retrieval and generation
    **`unknown`** — never measured here. `unknown` is a fourth verdict, not a polite `no`:
    a `no` closes the question, `unknown` names what blocks the measurement
  - The `evaluation` verdict is read from the real test set
    (`docs/evaluation/retrieval.jsonl`), so it changes when the file does
- **Proactive discovery — the last capability the brief asked for** (`src/proactive/`)
  - Seven detectors read state the platform already measures: model availability (C1),
    approvals waiting over 24 h, blocking import cycles, code no test reaches, a
    **measured** drop in quality, files worth tidying, security gaps
  - **An observation without evidence or without a proposed action is refused at
    construction**, not filtered later: a suggestion pointing at no measurement is an
    opinion, and flagging without saying what to do moves the work onto the person
  - **Nothing repeats.** A dismissed suggestion returns only if its evidence fingerprint
    changed — silencing "3 untested files" cannot hide "300 untested files" six months
    later. That distinction is what separates staying quiet from hiding
  - **Nothing is executed** (`acted: false`); each observation names who must decide
  - A silent detector and a failed one are never merged: "nothing to report" and "I could
    not look" are different sentences
  - Triggering is explicit — `scripts/proactive_scan.py` (cron-able, exit 1 on anything
    blocking), `GET /proactive/suggestions`, `due()`. No background thread in the API:
    with ADR-009 allowing one instance and no way to verify it without a clock, a
    half-built one would mean discovery believed active and not running
  - `tests/test_proactive.py` — 24 tests. On the real repository: 2 observations, 7
    detectors, none failed
- **The security model, measured in one place** (`src/security/`, VOLET 34 ch. 13)
  - The protections existed — RBAC, ownership, approval gate, audit, declared roots,
    sandbox, MCP whitelist — spread across six modules and five ADRs. `posture()` **reads
    the real configuration** and reports nine sections, each carrying what it does **not**
    guarantee. Sandbox limits are taken from `NON_GARANTI` verbatim rather than restated:
    two wordings of one limit diverge, and the reassuring one survives
  - **No overall score**, deliberately: a number would hide the gap that matters behind the
    average of the ones that do not. A section that fails to measure itself is returned as
    `unknown` with its reason, never omitted
  - `list_checkpoints()` puts file operations, approval decisions and backups in one view
    with `reversible` per line and **no global undo** — a single button would suggest the
    machine rewinds when half the lines do not
  - `/security/posture` and `/security/checkpoints`, both behind `ADMIN_AUDIT`: the list of
    an installation's holes is what an attacker would want to read
  - `tests/test_security_posture.py` — 19 tests, one of which varies the real configuration
    to prove the posture follows it rather than restating a document
- **`docs/architecture/hardware-and-stack.md`** (VOLET 34 ch. 14) — four hardware profiles,
  the stack and its reasons, what is deliberately absent **with the trigger that would
  change the answer**, and seven upgrade paths. The full suite runs on 4 cores and under
  1 GB; the 24 GB VRAM training figure is marked as **not verifiable here**
- **ADR-018 accepted (option B): a scoped derogation to sovereignty**
  (`src/model_engine/providers/derogations.py`)
  - `GALSEN_SOVEREIGN_DEROGATIONS`, read as `task_type:provider_id`, **configuration only**.
    A caller cannot ask for cloud — ADR-016 measured what a caller-supplied field is worth
  - **B is stricter than what it replaces**: the three unconditional refusals — user
    content, screen captures, training export — did not exist before. A derogation active
    for one task type still refuses a request carrying someone's content, and that is the
    test the ADR promised
  - Declaring a refused category is itself refused and logged: an operator error is not an
    authorisation. Active derogations appear in `sovereignty_report()`, `/health` and
    `/security/posture` — a derogation nobody can see is indistinguishable from a leak
  - `tests/test_sovereign_derogations.py` — 16 tests; the pre-existing sovereignty test is
    untouched
- **Working style, derived from evidence and actually applied** (`src/training/working_style.py`,
  `src/training/improvement.py`, VOLET 34 ch. 12)
  - VOLET 33 captured the signal; **nothing read it back**, so the platform answered exactly
    as it did on day one. Preferences are now derived from what a subject actually
    corrected — length, formatting, language
  - **Nothing is asserted below three concordant observations** and a 60% majority; each
    preference carries its observation count and the feedback ids behind it. Below that it
    is not a preference, it is a hesitation
  - **Only consented feedback feeds the profile.** `feedback.py` states that a
    non-consented return corrects *that* answer and nothing else; a durable profile is
    something else. Per subject, never merged (ADR-010)
  - The preferences reach the model: `AgentContext.generate()` prepends them to the prompt
    (derived once per context) and the audit records `style_applied`. With no established
    preference the prompt goes out **unchanged**
  - `improvement.py` compares two equal windows on three rates and **refuses to conclude**
    below 30 feedback items per window (`insufficient_data` — not "stable", not
    "improving") or with no prior window (`no_baseline`: that is a first point, not an
    improvement). Mean rating is computed over *rated* returns, since dividing by the total
    would measure silence
  - `tests/test_working_style.py` — 28 tests, two of which assert the text actually sent to
    the model rather than the report about it
- **The three specialists the brief asked for, each built around its failure mode**
  (`agents/organizer/`, `agents/project_manager/`, `agents/opportunity/`, VOLET 34 ch. 11)
  - **`organizer` proposes and never moves.** It is suspended in `requires_approval` by
    construction; `apply_plan()` raises without an approved request, and every move goes
    through `ReversibleFiles` so the whole plan can be undone. It never deletes, and it
    never touches a file already sitting in a folder — that was a human's choice
  - **`project_manager` reports what agents actually returned**, so a task whose agent has
    not run is `not_started`, never `done`. It produces **no deadline, estimate or
    percentage**: none of those exist anywhere in the platform, and producing them would
    fabricate a project status. What it does not report is listed in the output
  - **`opportunity` attaches a source to every statement, or does not make it.** With no
    sourced signal it answers `insufficient_evidence` and says what would settle it,
    instead of composing a plausible market analysis someone might spend money on. No
    market size, no growth rate, no revenue projection, no recommendation to invest
  - Three workflows (`rangement`, `suivi`, `veille`) make them reachable: an agent that no
    workflow reaches is reachable by no path
  - `tests/test_agents_personal.py` — 32 tests. The chapter-01 guard asserting these three
    were missing failed, as it was written to; it was **inverted, not deleted**
- **Whole-repository understanding for the coding agent** (`src/agent/repo_graph.py`,
  `src/agent/symbol_index.py`, VOLET 34 ch. 10)
  - The import graph answers *who breaks if I change this*: 310 code files, 1 194 internal
    edges, transitive impact, and the tests that actually reach a file
  - **The coding loop now verifies what it edits.** `GuardedEditor` picked its test suite
    **by filename**, which found one for 67 of 308 files (21.75 %) and returned
    "applied but **not verified**" for the rest — leaving the edit in place. Selecting by
    import reaches 270 of 310 (87 %), capped at three suites so a central file does not
    trigger the whole suite on every edit
  - **Three import cycles, none blocking** — all deferred inside function bodies. The
    distinction is in the code: a deferred cycle is a smell, a load-time cycle is an
    `ImportError` at startup, and merging them would report failures that do not happen
  - The symbol index holds **5 762 symbols including 3 393 methods**, which `RepoMap` never
    saw because it stopped at the top level. `rename_impact()` turns
    `verification.md`'s "check who calls it before changing a signature" into a query
  - Stated limit, pinned by a test: with no type analysis, `obj.calculer()` counts as a use
    of every `calculer` in the repository. Uses are a safe **superset** — missing a caller
    is the failure the rule exists to prevent
  - `tests/test_repo_graph.py` — 31 tests, on a toy repository for structural claims and on
    the real one for the facts whose value is that they break
- **MCP: a server behind a whitelist, a client that connects to nothing yet** (`src/mcp/`,
  VOLET 34 ch. 09, ADR-017 §6)
  - JSON-RPC 2.0 with **no dependency** — `initialize`, `tools/list`, `tools/call`, `ping`.
    The protocol is public and about a hundred lines; a dependency for it would contradict
    ADR-014 for nothing
  - **Eight tools exposed out of twenty-one.** `terminal`, `gui`, `screen`, `filesystem`,
    `database`, `email`, `calendar`, `git`, `github`, `api`, `browser` and `model` are
    refused, each with the reason returned to the caller. Serving the whole catalogue would
    hand an outside agent the platform's hands
  - **No anonymous call**: without an identity resolver the server refuses everything. A
    server that serves without an identity can neither authorise nor trace
  - **The audit records tool, operation and subject — never the arguments.** Arguments
    carry somebody's text and the audit persists
  - The client half **pins** its servers (no dynamic discovery) and treats a third-party
    tool description as data: neutralised, marked third-party, and flagged when it carries
    imperatives aimed at a model. The flag never deletes the suspicious text — erasing the
    attempt would erase the evidence of it
  - `tests/test_mcp.py` — 35 tests, including the poisoned description from the published
    threat model
- **A linter runs in CI and in the test suite** (`pyproject.toml`, `ruff==0.15.8`)
  - Nothing checked `.claude/rules/coding-conventions.md`; the conventions held because one
    author applied them
  - The ruleset is chosen to be **kept**: `F`, `E9`, `E7`, `B` — defects, not preferences.
    What is left out is written down with its cost: modernising annotations flags 3 183
    places, sorting imports touches 216 files. Both are mass rewrites for zero defect, and
    both would make `git blame` unreadable on 278 files
  - `tests/test_lint.py` — 8 tests: the repository passes its own linter, the core ruleset
    cannot be silently disabled, and each defect above is pinned as a regression

### Security
- **The deprecated `/cloud/*` routes enforced no ownership** (ADR-010, ADR-016)
  - While the cloud service had its own store the leak was confined to files uploaded
    through it. Making it share the file service's store turned it into a **bypass of the
    route that replaces it**: measured end to end, a second subject listed and downloaded
    another subject's file through `/cloud/list` and `/cloud/{id}/download`, while
    `/file/list` correctly returned nothing
  - All five routes now apply the rule `/file/*` applies — another subject's file answers
    `404`, never "exists but not yours" — and `/cloud/upload` attributes the file to its
    caller instead of leaving it ownerless
- **`DELETE /file/{file_id}` never checked ownership either**
  - Holding `MEMORY_DELETE` was read as "may delete any file". It means a subject may
    delete *its own* files; two subjects sharing a delete-capable role could delete each
    other's

### Removed
- **`CloudFileItem` and the four cloud stores** — ADR-016 step 3, **951 lines**
  - The cloud service stores nothing now: it translates the deprecated routes onto the
    file service, which ADR-016 made the platform's single write path
  - `provider` was the one field distinguishing `CloudFileItem` from `FileItem`, and it
    was **a caller's claim nothing verified**: uploading with `provider="s3"` on a platform
    configured in memory recorded `s3`, and `/cloud/stats` reported `by_provider:
    {"s3": 1}` for a file living in RAM. The field stays in the response and now carries
    the store that actually holds the bytes
  - `GALSEN_CLOUD_BACKEND` no longer selects anything. Its presence is reported as an
    error rather than ignored — an operator who wrote `filesystem` there would otherwise
    believe their files were on disk
  - The cloud service must share the file service **instance**: two `FileSystemFileStore`
    objects on one directory each keep their own in-memory index, so a file written through
    one façade was invisible from the other. Measured, then wired through the engine registry
  - No migration needed — criterion C4 is open, no deployment has ever held `/cloud/*` data
  - `tests/test_cloud_adapter.py` — 20 tests. The store-contract tests deleted with their
    subject are covered by `test_file_backends.py` and `test_services.py`, on the store
    actually in use

### Fixed
- **Four documented routes were unreachable** — found while deprecating `/cloud/*`
  - FastAPI keeps the first route whose path matches, and `/{id}` was declared before
    `/…/stats`. `GET /file/stats` answered `404 "Fichier stats introuvable"`; the same for
    `/cloud/stats`, `/calendar/stats` and `/email/stats` — four endpoints of a released
    version that nobody could call
  - Writing the general rule as a test rather than fixing the two cases in front of me is
    what found the other two: `tests/test_cloud_deprecation.py` fails if any literal path
    is declared after a template that accepts it **for the same method** (the method
    matters — `POST /file/list` coexists fine with `GET /file/{file_id}`)
- **No parameterised route could be deprecated at all**
  - The registry was keyed by exact path, and `request.url.path` is `/cloud/file_ab12`
    while the registry holds `/cloud/{file_id}`. Three of the six `/cloud/*` routes are
    parameterised, so half the announcement would have been silent — and nothing would have
    reported it. Matching now uses the route template the router records while handling the
    request

### Deprecated
- **`/cloud/*` — use `/file/*`** (ADR-016 step 2, ADR-011)
  - The six routes carry RFC 8594 headers (`Deprecation`, `Link` naming the replacement) on
    **every** response, errors included, and are marked `deprecated` in the OpenAPI
    description: the header warns an automated client, the documentation warns a human
    choosing a route
  - They keep working. `v0.1.0` is released and ADR-011 refuses to delete a public route
    without notice
  - **No `Sunset` date**: removal follows the retirement of `CloudFileItem`, which is not
    done. An invented date would be worse than none, because it would be believed
  - This is the first entry in a registry that had deliberately stayed empty — registering
    an example to prove the mechanism worked would have fabricated a fact

### Added
- **The file service gains the `filesystem` and `s3` backends** — ADR-016, step 1
  - `GALSEN_FILE_BACKEND` selects `in-memory | sqlite | filesystem | s3`, taking precedence
    over `GALSEN_STORAGE_BACKEND` exactly as `GALSEN_CLOUD_BACKEND` does. An unknown value
    is reported and the default applies — guessing `filesytem` would write files somewhere
    the operator does not expect, and they would only find out by looking for them
  - The port is not a copy. Both original stores share one structure — a JSON metadata index
    beside a blob store — and differ only in the second. Two complete classes would have
    written the index logic a third and fourth time, which is what ADR-016 objects to.
    `IndexedFileStore` holds it once; a backend supplies three operations
  - **Three defects of the originals are fixed rather than carried over**:
    - A truncated index made every file disappear **silently** — `_load_index` caught
      `JSONDecodeError` and restarted empty, so the store reported "0 files" while the bytes
      were still on disk (measured on `FileSystemCloudStore`). An unreadable index now stops
      the store from opening, and the offending file is kept: it is the only record of what
      was stored
    - The index was rewritten in place, which is what produced that truncated file. It is
      written to a temporary file and renamed — `os.replace` is atomic. File contents too:
      a half-written file used to be returned as-is by `get`
    - `S3CloudStore.clear()` never deleted the objects. It emptied the local index and
      reported N files removed while N objects stayed in the bucket, billed and readable
  - An id is validated before becoming a filename or an object key; `../` used to write
    outside the data directory
  - Bytes are written **before** the index. The reverse order leaves an index entry pointing
    at nothing — a file the platform lists and cannot serve
  - `tests/test_file_backends.py` — 21 tests, one per defect above

### Changed
- **Listing files no longer reads their contents** — ADR-016
  - The backlog asked which of three ways to write a file to disk should win. Measuring
    first changed the question: there were not three ways but **one design implemented
    twice**, plus `LocalDiskStorageConnector`, which is registered at start-up and which
    **nothing calls**
  - The `file` and `cloud` services have the same routes, the same store interface method
    for method, and the same manager — 1 368 lines across six store files doing one job
    twice. Their single real difference was a defect: `FileItem` carries its bytes, so
    `SELECT * FROM files` loaded every file's content on every listing. Measured here, 30
    files of 2 MB: **652 ms and 60 MB read** for a response that discards them
    (`to_dict(include_data=False)`). The cloud service already kept metadata and bytes in
    two tables
  - `FileStore.list_files()` now returns `FileSummary` — the same fields without `data` —
    and `SQLiteFileStore` selects the columns it needs. Same 30 files: **27 ms and 28 KB**
  - A `FileItem` with an empty `data` would have been simpler and wrong: empty bytes
    meaning "not loaded" is indistinguishable from empty bytes meaning "this file is
    empty". The type says what it holds; content is fetched one file at a time with `get`
  - What an HTTP client receives is unchanged — the route already discarded the bytes
  - ADR-016 also decides what the backlog actually asked: **a caller uses the file
    service**. `/cloud/*` is deprecated rather than deleted (ADR-011, `v0.1.0` is out), and
    the connector stays a connector, explicitly not a storage backend
  - `tests/test_file_listing_without_content.py` — 7 tests, including one that compares the
    memory a listing mobilises against the volume stored, so the bytes cannot come back

### Fixed
- **One response carried two contradictory verdicts** (VOLET 06, ch. 02, step 6)
  - "Validate outputs" was declared by the manual and implemented nowhere: nothing stood
    between an agent's dictionary and the aggregated response
  - `skipped` is a declared agent status, and it entered **none** of the aggregator's three
    lists: the agent vanished from `agent_results` and the aggregate stayed `success`,
    while the router — counting failures by subtraction, `total - success - approvals` —
    put that same agent in `failed_agents` and returned `partial_success`. Both statuses
    were in the same response, one at `status`, the other at `aggregated_result.status`
  - A result that was not a dictionary raised `AttributeError` mid-aggregation and failed
    the **whole** request, including the agents that had already succeeded
  - `src/router/output_validation.py` holds the contract and, more importantly,
    `overall_status()` — the single rule now called by the aggregator *and* the router, so
    they cannot disagree again. An invalid result is neither dropped nor guessed: it
    becomes an error naming the clauses it broke, the original kept under `invalid_output`
  - The check is applied at the boundary, in `AgentDispatcher.dispatch`, which also stops
    logging "exécuté avec succès" for results that carry an error status
  - **Behaviour change**: an empty pipeline now returns `error`, not `success`. Disable
    every agent and every request was declared served without anyone having handled it
  - `metadata.skipped_agents` is reported; an agent that chose not to act is neither a
    success nor a failure
  - `tests/test_output_validation.py` — 22 tests, including the end-to-end check that the
    router's status and the aggregator's status are the same value

### Added
- **The audit log and the approval queue now survive a restart** (ADR-005)
  - `src/storage/sqlite_audit_store.py` and `src/storage/sqlite_approval_store.py` join the
    seven existing stores and follow the same pattern: `prepare_connection`, an `RLock`,
    JSON for the composed fields, the file brought back to `0600`
  - Both managers select their store the way the other five services do —
    `GALSEN_STORAGE_BACKEND=sqlite` is enough, and `in-memory` stays the default
  - Audit filters are translated to **SQL** rather than applied in Python after reading: a
    log is read with filters ("this agent's failures since yesterday"), and fetching
    everything to sort afterwards would grow the cost with the log itself — at the worst
    possible moment. An **unknown filter raises** instead of being ignored, because
    ignoring it would return more rows than asked for, which a log reader would read as an
    absence of filtering
  - A decision applies only to a **pending** request: `_decide` filters on the status
    inside its `UPDATE`, so two concurrent decisions cannot both succeed. Checking then
    writing would leave a window where one request is both approved and rejected
  - `tests/test_audit_approval_persistence.py` — 13 tests, including restart survival, the
    nine audit fields round-tripping, and **filter-for-filter equivalence with the
    in-memory stores**: two implementations of one contract drifting apart is the defect
    this repository has already found three times

## [0.1.0] - 2026-08-11
### Security
- **A forwarded header was believed unconditionally, and there was no proxy to send it.**
  Decision → `docs/architecture/decisions/012-tls-termination.md` (ADR-012)
  - `X-Forwarded-For` was read straight from the request, leftmost value first — exactly
    the entry a caller controls. With nothing in front of the application, **any caller
    could set it**, present a different address on every request, and thereby obtain an
    unlimited unauthenticated quota *and* invisibility from the threat detector, which
    counts authentication failures per source. Twelve credential-stuffing attempts spread
    over twelve declared addresses stayed below the threshold of all of them at once
  - `X-Forwarded-Proto` had the quieter version of the same hole: believed on sight, it made
    the application send a two-year HSTS header on a response that was never encrypted
  - `src/api/trusted_proxies.py` applies one rule to both: **a forwarding header is believed
    only when the connection's peer is a declared proxy** (`GALSEN_TRUSTED_PROXIES`,
    addresses, CIDR blocks or exact peer names). Empty — the default — believes nothing and
    uses the connection's own address. The chain is walked right to left, past declared
    proxies, stopping at the first host that is not one. A malformed entry such as
    `10.0.0.300` is logged as an error rather than accepted as a hostname, so a typo cannot
    silently mean "no proxy declared"
  - `tests/test_trusted_proxies.py` — 10 tests, including the two bypasses measured end to
    end: forged addresses now hit the rate limit (`429`), and the detector tracks one source
    and raises one threat instead of twelve invisible ones

### Added
- **A release that can be rebuilt and rolled back to.** `.github/workflows/release.yml`,
  `docs/deployment/rollback.md`, `docs/changelog/releases/v0.1.0.md`
  - The repository had **zero tags**. A rollback target that does not exist is not a
    rollback plan, and CI never built the image — the one check that would have caught the
    `Dockerfile` missing `config/`, `agents/` and `workflows/`
  - On a `v*` tag the workflow re-does the whole path from the tag alone: the tag must
    match `src/version.py`, the suite runs, the production image is built, **and the
    container must answer on `/live`** — building is not starting. Nothing is published if
    any of those fails
  - `scripts/release_check.py` gains two checks: the production image builds, and the
    release notes exist. Without Docker the image check reports what it could not verify
    instead of ticking itself
  - `semantic-release` was **not** adopted: a Node toolchain in a Python repository that
    already has a release checker better fitted to it. The principle is kept — the
    changelog and the tag drive the release, and nothing is published from untested code
- **One authoritative instance, enforced.** `src/api/instance_lock.py` + ADR-013
  (`docs/architecture/decisions/013-single-authoritative-instance.md`)
  - ADR-009 stated the single-instance posture and `scaling_report()` published the
    verdict, but **nothing enforced it** — `docker compose up` started a second instance
    by itself. The consequence was already written down: "a compromised key revoked on one
    instance keeps opening the others"
  - At startup the application takes an exclusive `flock` on the data directory. A second
    instance on the same directory refuses to start and names the one holding the place.
    `flock` rather than a PID file on purpose: the kernel releases it however the process
    dies, so there is no stale-lock heuristic to get wrong — and getting it wrong in the
    permissive direction is exactly the outcome being prevented. In containers every PID
    heuristic fails that way: each container has its own PID namespace and PID 1 always exists
  - `scripts/backup.py` now asks the lock instead of testing the file's presence. A lock
    file left by a crash must not forbid the restore the crash made necessary
  - `GALSEN_ALLOW_MULTI_INSTANCE=true` is the rollback, logged as a warning at startup.
    `/health` reports `scaling.instance_lock` — held, enforced, allowed — without the path
    or the holder's PID, since that endpoint is unauthenticated
  - **Redis was not introduced**, and ADR-013 records the trigger that would reverse that:
    while there is one instance, process memory *is* the single source of truth. Redis buys
    nothing yet and costs a service with no default authentication, plus a failure mode with
    no good answer — refuse all traffic, or fall back to memory and lose the guarantee silently
  - `tests/test_instance_lock.py` — 13 tests. TEST 5 is proven end to end: a child process
    running the API's full lifespan on a locked data directory exits with
    `InstanceAlreadyRunning`. TEST 4: a revoked key is refused on the next request. TEST 3:
    100 concurrent requests against a 40-token bucket yield 40 grants, not more
- **TLS termination, and one way in.** `Caddyfile` + `caddy` service in `docker-compose.yml`
  - `Internet → HTTPS → Caddy → api:8000`. Certificates, renewal and the HTTP→HTTPS redirect
    are Caddy's, not the application's. `caddy_data` persists certificates and private keys;
    without it every restart re-requests one and meets Let's Encrypt's rate limits
  - **`api` no longer publishes a port**: `expose` replaces `ports`, so a clear-text route
    around TLS and around the proxy's access log no longer exists
  - `api-dev` moved behind the `dev` Compose profile. It ran alongside `api` with
    `restart: unless-stopped` and a published port — a second instance of the platform,
    which ADR-009 forbids, auto-reloading and with rate limiting disabled
  - Caddy does not duplicate the application's security headers: two values for one header
    let the most permissive win, depending on the client
- **Deployment audit before any of it** → `docs/deployment/audit-2026-08-11.md`
  (current architecture, ten defects D1–D10, risks, four roadmaps). It is also the record of
  what was **not** taken: Redis (a single authoritative instance makes process memory the
  single source of truth), semantic-release (a Node tool in a Python repository that already
  has `scripts/release_check.py`), PocketBase (architectural reference only)
- **Hot backup and restore** → `scripts/backup.py` (`sauvegarder`, `lister`, `restaurer`)
  - `VACUUM INTO` writes a consistent copy while the application keeps writing. The `cp -r`
    procedure documented before was wrong: copying an open SQLite file can produce a corrupt
    database, and since the stores run in WAL mode the recent writes live in a separate
    `-wal` file a `.sqlite` copy would leave behind
  - Restore refuses to run while an instance holds the data directory
- `tests/test_persistence_deployment.py` (16 tests) — data survives a restart, WAL is on,
  database files are `0600`, a backup taken during concurrent writes restores intact
- `tests/test_docker_image_contents.py` (8 tests) — one of them derives the required
  directories from the code itself, so a new `os.path.join(project_root, ...)` cannot be
  forgotten in the image again

### Fixed
- **Dependencies were unpinned, and the production image carried the test tooling.**
  Found by the production-readiness review → `docs/deployment/production-readiness.md`
  - `requirements.txt` used `>=` throughout, so the same git tag produced different images
    over time — the opposite of the reproducible build a release is for. Now pinned to the
    exact versions the v0.1.0 suite ran against
  - pytest, its plugins and the test HTTP client were installed into the image exposed to
    the network. Split into `requirements-dev.txt`; the image no longer carries them
  - `starlette` was imported directly by the code and never declared — the application
    relied on FastAPI happening to install it
  - `tests/test_requirements.py` derives the expected runtime dependencies from the code's
    own imports. Maintained by hand, the split would break at the first added import and
    the failure would surface only when starting the container
- **The production image shipped without `config/`, `agents/` and `workflows/`.**
  `Dockerfile` copied `src/`, `tools/` and `scripts/` only, while `RouterEngine` reads
  `config/settings.yaml`, `agents/registry.yaml` and `workflows/workflows.yaml` and imports
  agents by module path. Every workflow route would have failed in the container while
  passing in the test suite
- **`SQLiteMemoryStore` ignored `GALSEN_DATA_DIR`.** It hardcoded `data/memory.sqlite` —
  the only one of the eight stores to do so — so memory persisted outside the configured
  directory and outside every backup. Found because `scripts/backup.py` returned an empty
  list where a memory database was expected
- **Storage backend selection was scattered.** `src/storage/paths.py` is now the single
  decision point (`storage_backend()`, `sqlite_enabled()`), sets `busy_timeout`,
  `foreign_keys`, `synchronous=NORMAL` and WAL on every connection, and `chmod 0600` on the
  database file. `/health` reports the declared value next to the effective one, so
  `GALSEN_STORAGE_BACKEND=postgresql` is visible instead of silently falling back to memory
- **Backlog P1 — the hosted-provider path raised on every failure except 401 and 429.**
  Measured state → `docs/architecture/models.md`
  - The three hosted providers wrote `reason = UnavailabilityReason.UNAVAILABLE`, and
    **that member does not exist**. The generic HTTP branch — 400, 403, 404, 500, 503 — and
    the catch-all for network errors, timeouts and malformed JSON both raised
    `AttributeError` **out of** `_call_api` instead of returning an unavailable response.
    The first real API call that was neither a refused key nor an exceeded quota would have
    crashed the caller. Six occurrences, now `UNREACHABLE`
  - **The error body was read twice, so it was always empty.**
    `e.read().decode() if e.read() else str(e)` consumes the stream in the condition. For
    OpenAI and Anthropic the variable was then unused, so a 400 reported only its code while
    the body explaining it was thrown away. For **Google it was used** —
    `if e.code == 400 and "API_KEY_INVALID" in error_body` — so that detection could never
    fire, and an invalid Google key was reported as a generic 400, sending the operator
    looking in the wrong place
  - `read_error_body()` reads once and truncates to 500 characters, since this text ends up
    in an error message and API bodies run to kilobytes; `detail_avec_corps()` appends it
  - `tests/test_hosted_providers_api.py` covers all three providers: successful generation,
    key and model in the request, 429 as a quota rather than a failure, network errors
    returning instead of raising, 401, Google's 400-with-`API_KEY_INVALID`, and the API's
    own message reaching the operator. `urlopen` is replaced — request construction,
    response parsing and error translation stay real
  - Still not proven: that a real vendor accepts these payloads. That remains C1
  - 22 new tests; full suite 2 114 passing, 7 skipped

### Added
- **Backlog P1 — memory becomes the second search source, and the arbitrary weights are
  gone.** Measured state → `docs/architecture/search.md`
  - Three of four declared sources had no provider. Memory now has one, which only became
    possible after the retrieval fix: a source that returns everything regardless of the
    query is not a source
  - Wiring it raised a question knowledge never did — **memory is owned, not merely
    classified**. `SearchQuery` now carries a `subject` alongside `role`, `/search` fills it
    from the API key, and the per-source query propagates it. `MemorySearchProvider` **does
    not search at all** without one: returning every subject's memories would be a leak,
    returning some of them an invention. A role is not enough — an administrator may read a
    great deal and still has no claim on someone else's memories (ADR-010, criterion C2)
  - Verified end to end: two administrators searching the same word each get only their own
    memory
  - **The merge weights were removed, not justified.** `1.0 / 0.9 / 0.85 / 0.8` came from no
    measurement and were inert while one source was wired; a second source would have made
    them reorder results silently. All are `1.0`, and the reason is stronger than the
    missing measurement: scores from two engines are not comparable — proportion of query
    terms on one side, Jaccard similarity on the other. The response now carries a
    `ranking` block saying cross-source order is not grounded
  - A test that pinned the `0.8` was rewritten: it made an arbitrary constant permanent
  - 10 new tests, 2 rewritten; full suite 2 092 passing, 7 skipped

### Fixed
- **Backlog P1 — a search that ignored accents, and a memory search that returned
  everything.** Measured state → `docs/architecture/search.md`
  - On a base holding « La pluviométrie du Sénégal varie selon les régions »:
    `pluviometrie` → **0 results**, `senegal` → **0**, `arachide` → **0**, while the
    accented and plural forms returned 1. Unaccented typing is the norm on a keyboard used
    in Senegal, so a platform that finds nothing without accents finds nothing for its users
  - `src/text_normalization.py` strips accents and a simple final `s`/`x` (on words longer
    than four letters), **on both sides** — indexing and query. That symmetry makes a lossy
    transformation safe: it cannot prevent a match, only create one too many. Stop words are
    normalised too, and short words keep their `s` so `pas` and `bus` stay themselves
  - Deliberately not done, and named: `-aux` plurals, irregulars, conjugated forms, and
    languages other than French — those need a real morphological analyser
  - **A heavier defect surfaced next door**: `MemoryRetriever.retrieve()` scores by Jaccard
    similarity, but the default `min_score` was `0.0` and the test was `score >= min_score`,
    so a score of **zero** — not one term in common — passed.
    `search_memory(query="xyzzy")` returned all of the subject's memories, scored 0.0. Every
    caller asking about a subject got everything, and an agent's context filled with
    unrelated memories presented as relevant. A zero-score item is not a result;
    `list_items()` remains the way to get everything
  - 20 new tests; full suite 2 082 passing, 7 skipped

### Added
- **The orchestration is reachable.** Measured state → `docs/architecture/orchestration.md`
  - None of the API's routes ran a workflow or an agent: `RouterEngine` was instantiated
    only by tests. The same defect as the cloud stores in VOLET 24 — a capability that
    works and that nobody can turn on
  - `POST /workflow/run` (`TOOL_EXECUTE`), `GET /workflow/list` and
    `GET /workflow/history` (`HEALTH_VIEW`)
  - `TOOL_EXECUTE` rather than a new permission: a workflow is a sequence of agents calling
    tools, so it can do nothing `POST /tool/execute` cannot, and a wider permission would
    have granted more than the thing it wraps
  - The subject comes from the API key (ADR-010), never from the body — a `user_id` field
    would let a caller act under someone else's name, and a test asserts it does not exist
  - Execution is synchronous and says so: `execution_time_seconds` and `metadata.decision`
    make the cost visible and attributable. A queue is a design change, not a route
  - The engine is built on first use, so a deployment that never runs an agent does not pay
    three registry loads at startup
  - `GET /workflow/history` is the first route to serve the three measures added by
    VOLETs 18 and 19: success rate per workflow version, time per agent, failing agents
  - 9 new tests; full suite 2 062 passing, 7 skipped

### Changed
- **Backlog P1 — the planner's decision now drives the pipeline.** Measured state →
  `docs/architecture/orchestration.md`
  - Measuring first contradicted the item's premise: there is **no request-time pipeline**.
    None of the API's 64 routes runs a workflow or an agent, and `RouterEngine` /
    `AgentRuntime` are instantiated only by tests. Reported before acting
  - `standard` now declares `execution.agent_selection: planner`, and the recommendation
    restricts the declared pipeline. Measured: "bonjour" **45.2 s → 1.5 s** (9 agents → 2);
    a monitoring request 3.7 s with 4 agents; "écris et teste une fonction" still 50 s with
    `tester` — the cost did not vanish, it became attributable to a request that asked for
    it. The full test suite went from 183 s to 81 s
  - Three invariants: selection **restricts, never extends** (`workflows.yaml` stays the
    authority on what may run, or a planner would bypass the human review that file
    carries); an unusable recommendation keeps the whole pipeline; the option is declared,
    with `revue` as the shipped counter-example
  - **Three defects the wiring made consequential, and fixed**: the planner's fallback
    mobilised `quality`, so an unrecognised request spent 43 s testing code nobody had
    produced; **accents decided which agents ran** (`deploiement` did not match
    `déploiement`, and unaccented typing is the norm on a Senegalese deployment); and
    `veille` matched inside `surveiller`, so every monitoring request also triggered a
    research agent. Keywords must now start a word, without having to end one
  - `deployment` mobilises `tester` on purpose: preparing a release without knowing whether
    tests pass is the speed-over-truth the constitution rejects
  - Two integration tests were rewritten, not weakened: raw pipeline capability is now
    verified on `revue`, which declares no selection, and a second test verifies the
    restriction on `standard`
  - 11 new tests, 3 rewritten; full suite 2 047 passing, 7 skipped

### Added
- **VOLET 01 — the constitution's final rule is now a test.** Measured state →
  `docs/architecture/constitution.md`. This closes the series: all 25 manuals are treated
  - Chapter 03 ends on *no feature may be implemented if it removes meaningful human
    control over important decisions*. The gate exists (`BaseAgent.approval_required`,
    ADR-006) and **no agent sets it** — which is currently correct: all nine agents read,
    analyse and report, and every tool call they make is read-only. The `deployment` agent
    evaluates readiness; it does not deploy
  - What was missing is what keeps it that way. `approval_required` defaults to `False`,
    so the first agent calling a mutating tool would get no gate and nothing would say so.
    `tests/test_constitution_human_control.py` scans every agent's tool calls and fails if
    a mutating operation appears without the gate declared — verified to fail on a
    deliberately faulty agent. A second test locks the measurement, so the rule cannot pass
    green because the agents stopped calling tools
  - Reading is deliberately exempt: requiring approval to read a file would get the gate
    switched off within a day, and a control that gets switched off protects nothing
  - Also records what the constitution asks and the platform still does not do: confidence
    levels outside the gate, the four-level source hierarchy of chapter 04, and human
    verification for critical decisions — no medical, legal or financial path exists to
    gate, and building the gate before the path would be the same fabrication in reverse
  - 12 new tests; full suite 2 034 passing, 7 skipped

### Fixed
- **VOLET 25 — every engine existed twice, and the two halves did not know about each
  other.** Measured state → `docs/architecture/enterprise.md`
  - Chapter 02's directive is one sentence: *every engine shall communicate through
    standardized enterprise interfaces*. That interface exists — `EngineRegistry`, which
    agents reach through `AgentContext` — and `server.py` did not use it. It built its own
    `MemoryManager`, `NotificationManagerImpl`, `KnowledgeManagerImpl` and seven more,
    while the registry built a second set for the agents. All ten were duplicated
  - The consequence was not theoretical: an agent raising an alert put it in one inbox and
    `/notification/list` read the other — **1 seen by agents, 0 seen by the API**. A memory
    written through the API was invisible to every agent
  - It went unnoticed because `GALSEN_STORAGE_BACKEND=sqlite` makes both copies open the
    same file, hiding the split. It only bit on the **default** in-memory configuration —
    the one every developer and every fresh deployment runs first
  - `server.py` now takes its engines from the shared registry. If the registry cannot
    build one — it constructs lazily and a missing dependency can fail — the API keeps its
    own copy rather than losing the route, and logs it: an announced duplication can be
    diagnosed, which is the whole difference with the one just removed
  - Nine and a half of the manual's twelve global components exist. The Decision and
    Learning engines stay absent on purpose — both are projects, both depend on exit
    criterion C1. Of the master directive's ten commitments, three are blocked not by code
    but by two operator actions: configure a provider (C1) and deploy (C4)
  - `VOLET_25.md` is the most damaged file of the series: chapter 07 appears twice,
    chapter 10 twice, and chapter 08 comes after the first chapter 10. Nothing was invented
    to reconcile it
  - 13 new tests; full suite 2 022 passing, 7 skipped

### Added
- **VOLET 24 — two storage backends no configuration could select.** Measured state →
  `docs/architecture/integration.md`
  - `FileSystemCloudStore` and `S3CloudStore` are implemented, exported and covered by
    tests, and `CloudManagerImpl` only ever built the in-memory or SQLite store. No
    environment variable reached them: a deployment could not choose them, only a caller
    injecting a store could, and nothing in the platform does. Two working integrations
    kept alive by their tests and unreachable by anyone deploying — while chapter 03 makes
    configuration stage 4 and deployment stage 5
  - `GALSEN_CLOUD_BACKEND` selects `in-memory` (default), `sqlite`, `filesystem` or `s3`,
    taking precedence over `GALSEN_STORAGE_BACKEND` for this service only, since
    `filesystem` and `s3` are meaningless for the other stores
  - The default did not change — making `filesystem` default would start writing to disk on
    deployments that never asked. An unknown value is reported, never guessed: reading
    `filesytem` as `filesystem` would write files somewhere other than where the operator
    believes. S3 construction imports boto3 lazily, so configuring it cannot break startup,
    and an unreachable bucket fails on upload with a real error instead of silently falling
    back to memory — a file "stored" in RAM is worse than the failure. An injected store
    still wins
  - The test writes through the filesystem backend and reads it back from a second manager:
    making a store reachable without checking that it stores would prove nothing
  - 8 new tests; full suite 2 009 passing, 7 skipped

### Fixed
- **VOLET 23 — the platform's only feedback loop never worked, and VOLET 21 finished
  breaking it.** Measured state → `docs/architecture/learning.md`
  - The knowledge access counter is not decorative: `KnowledgeRankerImpl` weights a
    `popularity` criterion computed from it. `_increment_access_count()` read the item,
    incremented the counter and called `update()` — which refuses a write whose version has
    not advanced, and the counter did not advance it. The write was always rejected
  - **It never worked on SQLite**, which deserialises on every read. In memory the
    increment survived only by accident, because `get()` returned the store's own object
  - **VOLET 21's fix removed that accident.** Making `get()` return a copy — the right fix
    for the cache-versus-store divergence — left the counter writing to a discarded copy.
    Measured: `access_count = 5` before, `None` after. That is a regression introduced in
    this session and caught by this VOLET's measurement; it finished exposing a defect the
    in-memory path had been masking all along
  - `record_access(knowledge_id)` is now an explicit store method on the interface and both
    implementations, writing the counter **without touching the version** — consulting an
    item is not a new version of it, and forcing the write through the version would make
    every read produce a revision. Both backends agree: `access_count = 5, version = 1`
  - Third time in this series that two implementations of one interface were found
    disagreeing: notification `save()` (VOLET 13), knowledge `get()` (VOLET 21), this
    counter
  - **No learning engine was built.** Ten components and twelve stages including model
    training, with exit criterion C1 unmet — there is nothing to train
  - 6 new tests; full suite 2 001 passing, 7 skipped

### Added
- **VOLET 22 — the one decision the platform takes was thrown away.** Measured state →
  `docs/architecture/decisions.md`
  - The manual describes an eleven-component Decision Engine over a fourteen-stage
    lifecycle. **None of it exists and none of it was built**: standing one up empty would
    produce exactly what `.claude/rules/verification.md` forbids. The AI-reasoning stages
    also depend on exit criterion C1, which is not met
  - `PlannerAgent` does decide: it detects intents and derives the agents a request needs.
    Measured on "surveille les logs de production" — **3 agents recommended, 9 executed**,
    the declared pipeline in full. Six agents run that the platform's own analysis said
    were unnecessary, including `tester`, measured at 96 % of request time in VOLET 19
  - Chapter 03 makes decision recording stage 10 and explainability a quality control; a
    decision taken and lost is neither. `src/router/decision_trace.py` compares the
    recommendation with the execution in the response metadata, with `applied: false`
    stated explicitly rather than left to inference, "the planner did not run" kept
    distinct from "it recommended nothing", and both directions of the gap reported
  - **Following the recommendation was deliberately not done** — it would change what every
    request executes. That is the P1 already recorded after VOLET 19, and this measurement
    sharpens it: the platform already computes which agents a request needs
  - The VOLET 06 guard forbidding any reader of `agents_required` failed, as designed. It
    was not weakened but tightened to its real intent — reading to *report* is allowed and
    named, reading to *decide* stays forbidden — and paired with a behavioural test
    asserting the trace leaves the executed set untouched
  - 7 new tests, 1 renamed and tightened; full suite 1 995 passing, 7 skipped

### Fixed
- **VOLET 21 — three views of one knowledge item gave two different answers.** Measured
  state → `docs/architecture/knowledge.md`
  - `KnowledgeStore.save()` refuses to overwrite when an equal-or-newer version exists
    under the id, and signals that refusal **by returning the id** — "created", "unchanged"
    and "rejected" are indistinguishable. `add_knowledge()` then cached the object it had
    been handed without checking whether the store took it. Measured, on a caller
    correcting a fact: `get_knowledge()` returned "… en juillet." while the store and
    search returned "… en juin."
  - The caller read back their own submission and had every reason to believe it was
    stored. Chapter 03 makes integrity validation and consistency verification two of its
    quality controls; a cache contradicting its store defeats both
  - `add_knowledge()` now indexes and caches **what the store holds**, re-read after the
    write, and warns with the id and the remedy when the submitted content was not kept
  - **A second defect, exposed by the test written for the first**: read → edit → bump
    version → `update_knowledge()` did not work on the in-memory store, because `get()`
    returned its internal reference, so incrementing the version on the object you read
    also incremented the stored one and `update()` refused the write. The SQLite store
    deserialises on every read and hands back a fresh object — two implementations of one
    interface disagreeing on what a read is, the same class of bug as the notification
    stores in VOLET 13. `get()` now returns a copy in both. `list_items()` deliberately
    still returns references, which several callers rely on
  - **Nothing was added for duplicate removal**: a knowledge id is its content hash, so the
    practice chapter 03 asks for is already met structurally. A `deduplicate()` here would
    have been code with no defect under it
  - 5 new tests; full suite 1 987 passing, 7 skipped

### Added
- **VOLET 20 — duplicates were detected and nothing could remove them.** Measured state →
  `docs/architecture/memory.md`
  - Chapter 03 lists "remove duplicate knowledge" among its management practices. Only
    detection existed: saving the same content three times produced three memories,
    `quality_report()` reported `redundant_items: 2`, **and retrieval returned all three** —
    the caller got the same answer three times and the agent's context filled with
    repetitions
  - `MemoryManager.deduplicate(user_id=None, dry_run=False)` groups active memories by
    owner and exact content, keeps the **oldest** (it carries the date the knowledge
    appeared) and **archives** the rest. Never deletes: nothing authorises erasing what a
    user saved on the grounds that they saved it twice. Same criterion as the report, or
    report and action would disagree. Idempotent, with a dry run
  - **A second defect surfaced while building it**: `quality_report()` counted duplicates
    across all statuses, so after deduplication it still reported two redundant items and
    an operator would have concluded the operation did nothing. The rate now covers active
    memories only — the set `deduplicate()` acts on — and says so with
    `"scope": "active_only"`
  - It is a method, not a schedule; no API route was added, since `quality_report()` has
    none either and shipping half the pair would be worse than neither
  - `VOLET_20.md` **has no chapter 02** — it runs 01, 01, then 03. Nothing was invented to
    fill the gap; VOLET 07's component inventory stands
  - 10 new tests; full suite 1 982 passing, 7 skipped
- **VOLET 19 — one agent ate 96 % of every request, and nothing said so.** Measured state
  → `docs/architecture/orchestration.md`
  - On the shipped `standard` pipeline, with the request "bonjour": total 45.2 s, of which
    **43.5 s in the `tester` agent**, which runs the project's full pytest suite before the
    platform answers — on **every** request, whatever it asks. The other eight agents come
    to 1.7 s combined
  - Only the total duration was recorded, so the cost existed but could not be attributed.
    Each agent's duration — retries included, because that is what the request actually
    waited for — is now stored with the run, and `stats()` aggregates it as `agent_time`
    with each agent's share. The share is computed over the **sum of agent durations**, not
    over request duration: what happens between two agents belongs to neither, and dividing
    by the total would invent idle time. Verified end to end at 96.3 %
  - **The fix itself was not taken here.** Moving `tester` out of the pipeline, making it a
    separate workflow, or scoping it to changed files are different enough decisions that
    picking one is not a phase's call. Recorded as **P1** in `pending-work.md` with the
    measurement
  - **No per-agent timeout was invented.** Nothing bounds an agent's execution and a
    hanging agent hangs the request, but Python cannot kill a thread: a
    `future.result(timeout=…)` would free the caller while the runaway agent keeps running
    and holding its resources — a timeout in appearance only. A real bound needs process
    isolation, which deserves an ADR
  - 6 new tests, 1 adapted; full suite 1 972 passing, 7 skipped

### Fixed
- **VOLET 18 — every workflow declared a version that nothing read.** Measured state →
  `docs/architecture/workflows.md`
  - `VOLET_18.md` is a **second Workflow Engine manual**, despite its folder being named
    "Infrastructure & DevOps Engine" — the same mismatch VOLET 17 had. Only what it asks
    beyond VOLET 08 was treated
  - `workflows.yaml` gives each workflow a `version` and `WorkflowValidator` requires it.
    Across `src/router/`, the string appeared exactly twice, both times the validator
    checking the field exists. Nothing read its value, and `WorkflowHistory.record()` did
    not store it
  - The consequence undid the metric VOLET 08 built: bump `1.0` to `1.1` and the history
    kept both runs under the same name, so the success rate mixed two definitions.
    "This workflow fails 30 % of the time" could not say which one
  - `WorkflowLoader.get_version()` reads it, every run records it, and `stats()` breaks the
    numbers down by version. The global rate is still served — it is not wrong, only
    insufficient. `unversioned` (the workflow declares none) and `unrecorded` (the caller
    did not pass one) stay distinct, because merging them would hide one
  - Verified end to end on the real registry: a run of the shipped `standard` workflow
    records `workflow_version: "1.0"`
  - **Failure analysis now names the agent** (chapter 06): `failed_agents: 3` says how
    many, never which. Runs record the failing agents' names and `stats()` ranks them; an
    agent retried three times in one run counts once
  - 11 new tests, 1 adapted — the guard locking the history's field set, which is exactly
    its job; full suite 1 966 passing, 7 skipped

### Added
- **VOLET 17 — Notification templates and a delivery report that does not flatter
  itself.** Measured state → `docs/architecture/notifications.md`
  - `VOLET_17.md` is a **second Notification Engine manual**, despite its folder being
    named "Agent Framework Engine". Only the three things it asks beyond VOLET 13 were
    treated; re-measuring the rest would have duplicated existing documentation
  - **Template Manager** (chapters 02 and 04) did not exist: every caller composed title
    and message by hand, so the same event announced itself differently depending on which
    part of the code reported it — and deduplication, which compares exact strings, could
    not bring those variants together. `src/services/notification/templates.py` adds a
    registry and `send_from_template()`. A missing parameter **sends nothing**, because a
    message with holes looks like a real alert and says nothing; the registry ships empty,
    because providing templates would fabricate messages nobody asked for; substitution
    goes through `string.Template`, not `str.format`, which accepts `{a.__class__}` and
    would hand out attribute access from a configuration-supplied template
  - **Delivery analytics** (chapters 06 and 09): the manual's three metrics — delivery
    success rate, queue latency, failed deliveries — do not apply to an internal inbox,
    where creating the notification *is* the delivery. Returning them would report a
    100 % that measures only that tautology, so they are named in an `unavailable` block.
    `delivery_report()` measures what happens **after** delivery instead: acknowledgement
    rate, age of the oldest unread (the signal an inbox is no longer read), and the most
    repeated incidents — the last only measurable thanks to VOLET 13's grouping. Served by
    `GET /notification/stats`
  - No retry mechanism: a send either lands in the store or raises. Retries become
    meaningful when an external channel exists, and the e-mail service is where delivery
    can genuinely fail
  - 18 new tests; full suite 1 955 passing, 7 skipped
- **VOLET 15 — API Gateway: a way to announce that a route is going away.** Decision →
  `docs/architecture/decisions/011-api-versioning-and-deprecation.md`, measured state →
  `docs/architecture/gateway.md`
  - Chapters 04 and 08 ask for version control and safe retirement of obsolete APIs.
    There was no version prefix, no negotiation header and no deprecation mechanism: the
    only available retirement was deletion, discovered as a 404 in production
  - ADR-011 deliberately does **not** add a `/v1` prefix. A version prefix is a promise of
    stability, and this platform is a prototype whose main capability answers 503 for lack
    of a provider. Deprecation is announced through RFC 8594 headers instead —
    `Deprecation`, `Sunset` only when a date is decided, `Link: rel="successor-version"`
    only when there is a replacement
  - Carried by a middleware, not a per-route dependency, so the notice covers **error
    responses too**: a caller who only ever hits a route in error is precisely the one who
    needs warning. Deprecated is not removed — the route keeps working and keeps its
    status code
  - `GET /api/versions` serves the version, the deprecation list, and an explicit
    statement that there is no URL versioning. **The registry is empty**, because no route
    is deprecated; registering a sample would fabricate a fact
  - `metrics_snapshot()` gains `throughput_rps` and `uptime_seconds` (chapter 06), and
    names the two key metrics it cannot produce: availability — a process cannot measure
    its own, a self-reported figure is always 100 % — and resource utilization
  - `tests/test_gateway_surface.py` locks the whole surface: of 63 routes, 59 require
    authentication and 62 pass the rate limiter, with 4 named exceptions. Verified the
    guard fails on an unprotected route

### Fixed
- **VOLET 15 — four routes handed the caller the inside of the machine on a 500.**
  Measured, with a search failing on a connection error, the response body carried an
  internal hostname, a port and a filesystem path. `erreur_interne()` now logs the
  exception with its traceback under an incident id and returns only that id — the cause
  changes recipient rather than being lost. Validation errors still answer 422 with the
  precise reason; only internal failures became opaque. A test reads `server.py` and fails
  if any route builds a 500 detail from an exception again
- **VOLET 13 — Notification Engine: the same alert five times produced five
  notifications.** Measured state → `docs/architecture/notifications.md`
  - Chapter 03 lists duplicate prevention among its quality controls and nothing applied
    it. A "disk full" alert repeating every minute buried the recipient's inbox — that
    is, the notifications they had **not yet read**
  - An identical, **unread** notification inside a configurable window (300 s) now
    increments `metadata["occurrences"]` and returns the **same identifier**.
    `created_at` never moves — it says when the problem started; `last_occurrence_at`
    carries the latest. A read notification is never grouped, and identity requires type,
    title, message **and** recipient, so two incidents never merge and two recipients each
    keep their own copy
  - **Lifecycle stage 9 (retention and secure deletion) did not exist.** `purge_expired()`
    deletes **read** notifications past the retention period (90 days by default);
    `include_unread` defaults to `False`, because deleting what nobody has seen decides on
    their behalf that it did not matter. It is a method, not a schedule — nothing calls it
    periodically, and that is stated rather than faked with a background task
  - **Two implementations of one contract, disagreeing.** Grouping wrote back via
    `store.save()`: the in-memory store **raises** on a known id, the SQLite store does
    `INSERT OR REPLACE`. The manager's `try/except` swallowed the exception, so in memory
    the mutation only landed because the object is shared by reference. `save()` keeps
    meaning **create**, and an explicit `update()` was added to `NotificationStore` and
    both stores; it returns `False` when the notification is gone, and the manager then
    counts nothing rather than counting into the void. Verified against **both** backends
  - 3 of 7 components exist. Absent: rules engine, channel connectors, delivery queue,
    user preferences. No placeholders
  - New: `GALSEN_NOTIFICATION_DEDUP_SECONDS`, `GALSEN_NOTIFICATION_RETENTION_DAYS`,
    documented in `.env.example` and validated at startup
  - 10 new tests; full suite 1 783 passing, 7 skipped
- **VOLET 12 — Communication Engine: "sent" named messages nobody received.** Measured
  state → `docs/architecture/communication.md`
  - With no SMTP configured, `send_email()` returned `success=True`, "Email envoyé à 1
    destinataire(s)" and stored the message as `sent` — **no server was ever contacted**.
    The default `NoopTransport` returned `(True, "")`, justified in a comment as
    "historically equivalent" behaviour: a lie preserved for compatibility
  - **Six tests asserted that lie**, including one requiring `(True, "")` from the
    transport that does nothing. `.claude/rules/verification.md` forbids exactly this —
    pinning a fabricated value makes the fabrication permanent. All six were rewritten to
    assert the real behaviour
  - The transport now says it sent nothing **and what to do about it**; the stored status
    becomes `failed`; `POST /email/send` answers **503, not 400** — a 400 accuses the
    caller of an error they did not make
  - **The composed message is still stored**: what a user wrote must not vanish because
    the infrastructure is missing. Only the status changed, because the status was lying
  - Notifications do not have this defect: they are an internal inbox, and creating one
    *is* the delivery
  - 7 new tests, 6 rewritten; full suite 1 773 passing, 7 skipped

### Added
- **VOLET 11 — Security Engine: counting is not detecting.** Measured state →
  `docs/architecture/security.md`
  - Twelve authentication attempts with **twelve different keys** from one source produced
    `failed: 12` and **no signal at all** — the platform knew attempts had failed, not who,
    when, or whether it was still happening
  - **`src/api/threat_detection.py`**: a sliding window of failures per source (10 in
    300 s, configurable), three severity levels, and `GET /security/threats`. Behavioural
    analytics, threat-intelligence correlation and machine-assisted analysis are **named in
    the response as unavailable**, with their reason
  - **A bypass found while building it**: the first version cleared a source's failures on
    successful authentication. End-to-end that returned **zero threats after twelve
    failures** — an attacker who finds a valid key erased their trail, and the operator
    reading the route erased what they came to see. Successes are now recorded beside
    failures with `succeeded_in_window`
  - A threat report names an **address**, never a key or its fingerprint; the route
    requires `ADMIN_AUDIT`; the detector is bounded at 1 000 sources
  - **Incident response** (chapter 06) has detection and severity; containment, eradication
    and recovery do not exist and are not simulated — auto-blocking an address needs an ADR
  - 18 new tests; full suite 1 766 passing, 7 skipped
- **VOLET 10 — Integration Engine: `/health` ignored the integration layer.** Measured
  state → `docs/architecture/integration.md`
  - The platform had two ways to answer "what is wrong" — `/health` for engines,
    `/connectors/status` for integrations — and nothing said so. `/health` now carries a
    `connectors` component (closes a P2 backlog entry)
  - **An unconfigured connector does not degrade anything**, which is the opposite of the
    intuition: most deployments configure none, and an endpoint that turns `degraded`
    because SMTP is absent is red permanently, therefore ignored. Only a connector that is
    configured *and* failing degrades the platform, and the component says so in a note
  - The check reads configuration and **contacts nobody**; `/connectors/status` remains the
    route that reaches out
  - **Five of seven components** exist; the message broker and synchronisation service are
    absent, and versioning and retirement are missing from the integration lifecycle
  - 6 new tests; full suite 1 748 passing, 7 skipped
- **VOLET 09 — Analytics Engine: collection existed, aggregation did not.** Measured state
  → `docs/architecture/analytics.md`
  - `src/` had no analytics package: the audit engine recorded events and `/metrics`
    counted traffic, and nothing turned either into an indicator
  - **`src/analytics/` is an aggregation layer, not a second collector** — a second count
    of the same executions would create two truths with no way to choose. It reuses audit
    events, `WorkflowHistory` and the `/metrics` snapshot without recomputing them
  - **`GET /analytics`** (`ADMIN_AUDIT`): per-agent executions, success rate and durations
    from audit; workflow success rate; traffic and search counters; source coverage
  - **An absent source returns `null`, never `0`** — zero reads as "no agent ran" when the
    truth is "nothing was measured"
  - **Four of the seven data sources** in chapter 04 are wired; memory, system logs and
    external integrations feed nothing, and `source_coverage()` says so at runtime
  - **Trends, anomaly detection and dashboards are named unavailable with their reason**:
    no time series survives a restart (ADR-009), so there is no baseline to compare against
  - No user request, subject or key fingerprint enters a report
  - 8 new tests; full suite 1 742 passing, 7 skipped

### Fixed
- **VOLET 08 — Workflow Engine: nothing validated a workflow.** Measured state →
  `docs/architecture/workflows.md`
  - A workflow citing **an agent that does not exist** loaded silently and failed halfway
    through; one with **no steps at all** returned `success` having executed nothing.
    `workflow_validator.py` separates blocking errors from warnings, and the engine now
    refuses to run a workflow that would produce a misleading result
  - **Three declarations configured nothing**: the root `execution:` block (the planner
    reads `execution` *inside* a workflow), the root `failure:` block (the code reads it
    from `config/settings.yaml`, where the key did not exist, so `max_attempts` and
    `rollback` always fell back to code defaults), and no workflow carried `version` or
    `owner`. The failure settings now live where they are read, the dead blocks are gone,
    and the metadata is in place
  - **Added `WorkflowHistory`**: execution history and the success rate chapter 09 asks
    for. Failures are recorded too — a rate that only observes successes is always 100 %.
    `success_rate` is `None` with no runs, never 0.0; the user's request is not stored;
    the history is bounded at 500 runs and says it dies with the process (ADR-009)
  - 19 new tests; full suite 1 734 passing, 7 skipped
- **VOLET 07 — Memory Engine: four declared rules that nothing applied.** Measured state →
  `docs/architecture/memory.md`
  - **"Forgetting" deleted permanently**: `forget_memory()` called `delete_memory()`, and
    the `ARCHIVED` status was never set by anything. It now archives; `delete_memory()`
    still erases
  - **Archiving would have changed nothing**: the retriever passed `status=None`, so an
    archived memory kept appearing in every search. It now considers `ACTIVE` only
  - **Expiry only applied if someone ran the cleaner**, and nothing runs it on a schedule.
    It is now honoured at read time
  - **`cleanup_expired()` reported deletions the cache undid** — it returned an exact count
    while the memory stayed readable from `item:{id}`
  - **`consolidate_memory()` returned 0**, indistinguishable from "nothing to consolidate".
    It now raises `NotImplementedError` naming the rules that do not exist
  - **Added** `quality_report()` and `list_inactive()`: freshness, per-owner duplicate rate,
    metadata completeness and status breakdown; retrieval accuracy and user satisfaction
    are named unavailable with their reason
  - 15 new tests
- **The `tester` agent reported suites it never ran.** It executed `python <suite>`, which
  only runs a file's `__main__` block — **20 of 92 suites have one**; the other 72 imported
  themselves, ran no test, exited 0 and were counted as passing. It now runs
  `python -m pytest`, and a suite collecting zero tests is no longer green
- **The `tester` agent is 2.5× faster**: one process per suite paid the platform's import
  92 times. A single batched pytest invocation pays it once — **97.4 s → 38.6 s** for 91
  suites — while keeping a per-suite verdict, since pytest names the file of each failure.
  A batch that fails or times out falls back to per-suite execution
- **The router announced parallel execution it never performed.** Its docstring claimed
  "supports parallel execution", the log printed a parallel plan, and no concurrency
  primitive exists in `src/router/` — the "parallel" agents were appended to the sequential
  list. The claims are corrected (`parallel_supported: False`); the behaviour is unchanged
  and the decision is now backed by measurement: `tester` is 97.4 s of a 99 s pipeline and
  the eight other agents total 1.66 s, so parallelism would buy ~1.5 s

### Added
- **VOLET 03 — Development Manual, 10 chapters in 12 phases.** Measured state →
  `docs/architecture/development.md`
  - **Performance targets** (`docs/standards/performance.md`): the oldest P1 in the
    backlog. Derived from same-day measurements, not round numbers — ≤ 50 ms for liveness,
    ≤ 200 ms for reads and search, ≤ 500 ms for writes, at p95. End-to-end latency is
    deliberately **not** targeted while nothing is deployed
  - **The fifth testing level** (`tests/test_performance_targets.py`), which was absent
    for a legitimate reason: without a declared target, a timing assertion is a number
    chosen to pass. It also asserts that search does not degrade with base size
  - **`release_check.py`** gains a ninth automated check and no longer leaves
    "performance targets verified" to a human
  - **Startup configuration validation** (`src/config/environment.py`): 11 variables that
    are present and unusable are reported with the consequence of ignoring each.
    `GALSEN_STORAGE_BACKEND=sqllite` used to fall back to in-memory storage silently
  - **Eight environment variables** read by the code and documented nowhere are now in
    `.env.example`, with a test that fails if another one goes missing
  - **Backward-compatible storage proved both ways** (`tests/test_storage_rollback.py`):
    an older reader on a newer base, a newer reader on an older base, and a full
    roll-back cycle that loses nothing
  - **Six of eighteen packages documented**: three had no docstring at all, three repeated
    their own name. Rewritten to the chapter's structure, known limitations included
  - 32 new tests; full suite 1 687 passing, 7 skipped

- **VOLET 14 — Search Engine, 10 chapters in 12 phases.** Full measured state →
  `docs/architecture/search.md`
  - **`POST /search` could not return a result**: no class implemented `SearchProvider`
    and nothing called `register_provider()`, so the route answered `total: 0` to every
    query — indistinguishable from an empty base. It now answers 503 with a reason while
    nothing is wired, and `KnowledgeSearchProvider` wires the knowledge source for real
  - **Searching does not grant reading**: `SearchQuery` carries the caller's role through
    the merge down to each provider
  - **Search analytics** (`record_search`): volume, per-source latency and empty-result
    rate in `/metrics`. Query *contents* are never recorded
  - **`GET /search/status`**: declared versus wired sources, their owner
    (`GALSEN_SEARCH_OWNERS`), index integrity and search counters. Precision, recall and
    user satisfaction are named as unmeasurable with their reason
  - **Index integrity** (`check_integrity`): missing, orphaned and stale documents, each
    with a test that provokes it
  - 33 new tests; full suite 1655 passing, 7 skipped

- **VOLET 05 — Knowledge Engine, 10 chapters in 12 phases.** The engine was built and the
  base was empty (0 items, 0 indexed terms, 0 graph nodes); the VOLET added the discipline
  around the content. Full measured state → `docs/architecture/knowledge.md`
  - **Organisation**: `KnowledgeDomain` (the chapter's 7 domains, closed), plus
    `KnowledgeSensitivity` and `KnowledgeStatus`. Both stores filter and persist them, and
    SQLite migrates an older base additively — pre-existing rows read as unclassified
    rather than guessed
  - **Lifecycle** (`knowledge_lifecycle.py`): review cannot be skipped, retirement is
    terminal, and every transition is a revision recorded with actor, reason and time.
    Rewriting content returns an item to `DRAFT`
  - **Retrieval policy**: archived and deprecated knowledge never feeds a reasoning path;
    `search_knowledge()` stays exhaustive for operators
  - **Query cache**: repeated searches went from 0.50 ms to 0.234 ms; every write drops
    the cached results, so nothing outlives the data it describes
  - **Security**: reads are gated by role against sensitivity — no role, empty role or
    unknown role reads public only, and filtering is silent
  - **Reports**: `GET /knowledge/governance` (owners per domain, orphan domains) and
    `GET /knowledge/quality` (completeness, freshness, duplicates, validation coverage).
    Accuracy rate and user feedback carry **no number** and are named as unavailable with
    their reason
  - 78 new tests; full suite 1622 passing, 7 skipped

### Changed
- **The 27 root `test_*.py` files now live in `tests/`**, as `.claude/rules/testing.md`
  requires. The move broke 20 path expressions that computed the repository root as
  `dirname(__file__)`; all were rewritten, and `tests/test_project_structure.py` now fails
  if a test file reappears at the root or points `sys.path` at its own directory
- **The debt register in `docs/roadmap/roadmap.md` was re-measured**: four of nine debts
  are paid, three were missing, and the orchestration suite grew from 97 s to 105 s
### Fixed
- **Two silent truncations at 10 000 items.** `count()` returned the length of
  `list_items(limit=10000)` in both knowledge stores, so a store holding 10 050 items
  reported 10 000 with nothing able to detect it; `_rebuild_index()` read the same bound,
  leaving every document past it **unindexed and unfindable without any signal**. Counting
  is now real (`len`, `SELECT COUNT(*)`), the index bound is a named constant shared with
  the integrity check, and reaching it is logged and reported as `truncated`
- **OpenAI-compatible provider** (`src/model_engine/providers/openai_compatible_provider.py`)
  — one provider for every service speaking `/v1/models` and
  `/v1/chat/completions`: vLLM, LM Studio, llama.cpp, LocalAI, OpenRouter, Groq,
  Together, or a rented GPU server. Moving a model from a laptop to a server to
  a host costs **no code**: only `GALSEN_OPENAI_COMPATIBLE_URL` changes
  - the key is optional — a local server asks for none, and `HostedProvider`
    refuses to work without credentials, which is why this is a distinct class
  - the catalogue is **discovered**, not declared: a hard-coded list would lie
    the moment the operator swaps models
  - inactive until the URL is declared; it never guesses an address
  - HTTP codes become distinct reasons — 401 asks for a key, 429 asks to wait,
    and confusing them leaves the operator without a lead
  - `tests/test_openai_compatible_provider.py`: 20 tests against a real HTTP
    server speaking the protocol
- **Exit criterion C3 met — a second workflow, executed**. `workflows/workflows.yaml`
  declares `revue` (`reviewer` then `security`), which runs the full pipeline in
  0.2 s and produces real output: 40 files reviewed, 26 findings, 0 security
  issues. It carries its own `execution` block, which is what lets two workflows
  use different strategies. `tests/test_workflow_revue.py`: 12 tests, and they
  never execute `standard` — it contains `tester`, which would run the suite
  inside the suite
- **Exit criterion C5 met — the log is bounded.** `RotatingFileHandler` replaces
  `logging.FileHandler`: 5 MB × 3 archives, so 20 MB maximum instead of the
  6.7 MB and 43 638 lines it had reached with nothing capping it.
  `GALSEN_LOG_MAX_BYTES` and `GALSEN_LOG_BACKUP_COUNT` adjust it; an unreadable
  value falls back to the default rather than reopening unbounded growth.
  `tests/test_log_rotation.py`: 18 tests, which write enough to trigger several
  rotations rather than inspecting the handler's type
- **Identity (VOLET 16, ADR-010)** — a key belongs to a subject
  - `GALSEN_API_KEYS` gains an optional third field: `secret:role:subject`.
    `RBACContext` carries `subject`; a key without one is anonymous, so no
    existing deployment breaks
  - `GET /auth/whoami` tells a caller who they are — a misattributed key was
    otherwise discovered by reading audit traces, too late
  - `GET /metrics` reports the authentication success rate (`auth.attempts`,
    `succeeded`, `failed`, `success_rate`), the metric VOLET 16 ch. 06 and 09
    both ask for. The counters name no subject: per-person counting would turn
    an operational measurement into individual tracking
  - `docs/architecture/identity.md`: what the manual asks, what exists, and what
    is deliberately absent with the trigger for each
  - No credential store, and none planned before self-service signup. The
    platform still holds no secret of its own

### Security
- **Exit criterion C2 met — data belongs to its subject.** Three stores leaked
  the same way and now enforce ownership:
  - `/memory/store` and `/file/upload` took their owner from the request body,
    so any key holder could write in someone else's name. The owner is now the
    authenticated subject; an administrator may still name another
  - `/memory/retrieve`, `/file/{id}`: another subject's data answers **404, not
    403** — a 403 confirms an id exists and belongs to somebody, which is enough
    to enumerate it. A test asserts refusal and absence are indistinguishable
  - `/memory/search`, `/file/list`, `/notification/list` filter by subject, and
    an explicit filter naming someone else is not honoured
  - `/notification/mark-all-read` accepted an arbitrary recipient: any key
    holder could empty another subject's inbox
  - Notifications are constrained on **reading**, not writing — `recipient` is
    the addressee, and sending to someone else stays legitimate, which is what
    the approval engine does when it asks an operator to decide
- **Proof for exit criterion C1** (`tests/test_generation_end_to_end.py`) — the
  end-to-end generation tests skip with an actionable reason while no provider
  answers, and run unchanged the moment one does. The "runs" path is covered too:
  a stub HTTP server speaking Ollama's protocol drives tool → manager → selector
  → provider → HTTP, so the file cannot silently become vacuous
- **`GET /metrics` (VOLET 04 ch. 09, half of exit criterion C5)** — request count,
  error rate and per-route latency. `/health` answers what is configured; this
  answers what is happening. It feeds the `metrics` tool that already existed and
  that nothing had ever called, rather than adding a second mechanism
  - series are named by route template, so a URL scan cannot grow the collector
  - a failed measurement never fails the measured request
  - requires a key (read-only is enough); `/health` stays open
  - the reading does not count itself, and the response states `scope: "instance"`
  - `tests/test_api_metrics.py`: 12 tests
- **Versioning and release procedure (VOLET 04 ch. 03)**
  - `src/version.py` is the single source for the version and the release type.
    The application imports it; the Dockerfile redeclares it as
    `ARG GALSEN_VERSION` and `tests/test_version.py` fails if the two drift
  - `scripts/release_check.py`: eight executable checks (version, git tag,
    working tree, tracked secrets, changelog, documentation, startup, test
    suite), non-zero exit when one blocks. The two requirements needing
    judgement — features complete, performance targets verified — are printed
    and never ticked automatically
  - The release type is recorded as `prototype`; the series stays `0.x` while it
    is prototype, alpha or beta, and a stable label is refused while `/health`
    does not report healthy
- **Scaling posture made explicit (VOLET 02 ch. 10, ADR-009)** — closes VOLET 02
  - `src/api/scaling.py`: inventory of every subsystem holding state, with where
    it lives, what a second instance would do to it, and whether that is a loss
    of correctness or harmless duplication. Recomputed on each call so a change
    of `GALSEN_STORAGE_BACKEND` is reflected instead of frozen at import
  - `/health` carries a `scaling` section: instance identity,
    `multi_instance_ready` verdict and the names of the blocking subsystems
  - `POST /auth/keys/{fingerprint}/revoke`, `/restore` and `GET /auth/keys` now
    state `scope: "instance"` — a revoked key keeps opening any other instance,
    and an operator responding to a compromise must not learn that afterwards
  - `GALSEN_INSTANCE_ID` names an instance; unset, `<host>:<pid>` is used
  - `tests/test_scaling.py`: 20 tests, including a demonstration that a key
    revoked on one manager still authenticates on another

- **Conseil Agricole page on `/ui`** (ADR-008) — `api.agri.conseil()` in the API
  client, a full-width section rendered with `textContent`, line breaks
  preserved. `tests/test_web_agri.py` (18 tests) replaces the removed
  `tests/test_dashboard_agri.py`
- `tests/test_import_convention.py` — walks every module under `src/` and fails
  on the first internal import written without the `src.` prefix, and on any
  logic in `src/__init__.py`. The convention had been broken twice, both times
  invisibly, because the tests imported by the bare name too

### Changed
- Two development lines reconciled. `src/frontend/` (Jinja2, mounted on
  `/admin`) is removed: ADR-008 stands, and its page was rebuilt on `/ui`
- `src/api/scaling.py` derives the scope of files and notifications from
  `GALSEN_STORAGE_BACKEND` instead of declaring them process-local. Under
  `sqlite`, only key revocations and rate-limit counters still block a second
  instance
- `data/` is no longer tracked; five `*.sqlite` databases and
  `.claude/settings.json.bak` were removed from version control

### Fixed
- **A reachable provider with a too-small model gave a dead-end message.** With
  Ollama running and a 4096-context model, `/agri/advice` answered 503 with
  "Aucun modèle sélectionnable" — the real reason (minimum context 8192) was
  logged by `select_model_for_task()` and thrown away, and
  `unavailability_reason()` only knew how to report "no provider at all". The
  manager now keeps the selector's reason and returns it, clearing it on every
  new selection so a stale explanation cannot outlive the configuration that
  fixed it. This is the most likely local failure and it said nothing useful
- **`POST /agri/advice` answered 200 with an empty answer** when no model
  provider is configured: only exceptions were translated to 503, and the tool
  reports unavailability as a status. Any non-`ready` status now yields 503
  carrying the tool's own detail
- **The `src.` import convention was broken again** by the five services merged
  from the parallel branch, and hidden by `src/__init__.py` inserting `src/`
  into `sys.path`. The same file was importable under two names, so Python
  built two distinct classes and `isinstance` failed. Ten modules and six test
  files converted; `src/__init__.py` emptied of logic
- Three dashboard rendering defects, all found by driving a real browser and
  invisible to HTTP tests: identifiers broken mid-word, a table column silently
  cut off, and overlapping column headers
- `tests/test_api_startup.py`: seven integration tests that actually boot the
  application (`with TestClient(app)`), covering the lifespan, the late binding
  of the tool engine into the health checker, resilience to a broken tool engine
  and a real end-to-end tool execution. No test booted the app before, which is
  why the two startup defects above went unnoticed
- **Backend services test coverage (VOLET 02 Phase 2)**
  - `tests/test_services.py` extended from 93 to 135 unit tests: notification
    serialization edge cases (`read_at`, omitted optional fields, enum instances
    in `from_mapping`), advanced store filters (`min_priority`, role, tags,
    content type), search source weighting, offset pagination, `DATE_ASC` sort,
    provider-query construction and single-source failures, file base64
    round-trip and best-effort failure handling of `FileManagerImpl`
  - `src/services/` statement coverage raised from 92% to 99%

### Fixed
- **The API could not start.** `uvicorn src.api.server:app` — the command the
  Dockerfile runs — failed with `ModuleNotFoundError: No module named 'storage'`
  because `memory_manager.py`, the three `src/storage/sqlite_*_store.py` modules
  and the deferred imports in `knowledge_manager.py` / `model_manager.py` used
  top-level absolute imports assuming `src/` was on `sys.path`. Every import
  inside `src/` now uses the single `src.<module>` convention, which also fixes
  the duplicate-module identity bug (two distinct `MemoryPriority` classes)
- **The startup handler was dead code.** `startup_event()` called
  `tool_loader.load_tools()`, `ToolEngine(tools)` and
  `tool_engine.set_executor()` — none of which exist. It now builds the engine
  from the registry path and logs a failure instead of taking the API down
- **`/tool/execute` never worked**: it called `tool_engine.execute()` (absent —
  the method is `execute_tool()`) and passed `config` as a positional dict, so
  the tool never received its options
- `ToolLoader.get_tool_class()` no longer swallows `ImportError` /
  `AttributeError` silently; the cause is logged. All 20 tools in
  `tools/tools.yaml` now load
- `test_embeddings_tool.py`: the three tests that patch `sentence_transformers`
  are now skipped when that optional dependency is absent, so the suite is green
  out of the box. The behaviour without the dependency stays covered by
  `test_embeddings_tool_missing_sentence_transformer`
- `requirements.txt` now declares two dependencies the code already required:
  `opencv-python-headless` (imported at module level by four
  `src/vision_intelligence_engine/` modules — without it the `vision` engine is
  unavailable in the registry) and `httpx` (required by
  `starlette.testclient.TestClient`, without which four API test files cannot be
  collected)
- Three pre-existing `NameError` failures that prevented the full pytest suite
  from being collected: missing `Optional` import in
  `src/memory_engine/memory_summarizer.py` and
  `src/vision_intelligence_engine/vision_analyzer.py`, and a forward reference to
  `ColorAnalyzer` in `src/vision_intelligence_engine/interfaces.py` (now a string
  annotation)

### Added
- **Priorité #7 — Conseil Agricole (première feature réelle)** : outil
  `AgriAdviceTool` réparé (passage à l'API synchrone `select_model_for_task()` +
  `generate()`, corrigeait un bug d'appel de coroutine asynchrone et une méthode
  inexistante), endpoint `POST /agri/advice` dans `src/api/server.py` (question
  agricole en fr/wo, options model_id/max_tokens, protégé par RBAC
  `model:generate`), 17 tests unitaires dans `tests/test_agri_advice.py` — tous
  verts. Génération réelle vérifiée via Ollama (qwen2.5-coder:14b).
- **Credentials providers (ADR-004)** : `_call_api` implémenté pour OpenAI,
  Anthropic et Google (stdlib urllib, zéro dépendance). Lecture des clés via
  `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`. Correctifs : imports
  manquants dans `openai_provider.py` et `google_provider.py`, enum `UNAUTHORIZED`,
  commentaires arabes → français. 24 tests unitaires — tous verts.
- **Stockage persistant complet (ADR-005)** : 8 stores SQLite pour Memory, Model,
  Knowledge, Notification, Calendar, Email, Cloud, File. 92 tests — tous verts.
  Backend sélectionnable via `GALSEN_STORAGE_BACKEND=sqlite` ou injection. Correctif
  `:memory:` mode sur `SQLiteFileStore` (connexion persistante).
- **Connecteur S3/Minio + FileSystem pour le service Cloud** : `S3CloudStore` (`src/services/cloud/store_s3.py`) avec upload/download via boto3 (lazy import, configuration par variables d'environnement `CLOUD_S3_*`). `FileSystemCloudStore` (`src/services/cloud/store_fs.py`) pour un stockage persistant local zéro dépendance (index JSON + fichiers binaires). 19 nouveaux tests. **185 tests pour les 3 services externes — tous verts**.
- **Connecteur SMTP pour le service Email** : `SmtpTransport` (`src/services/email/transport.py`) avec support STARTTLS et SSL, configuration par variables d'environnement, construction MIME complète. `ConsoleTransport` et `NoopTransport`. 18 nouveaux tests.
- **Dashboard web (`src/frontend/`)** : 5 templates Jinja2 (base, accueil, santé, services, modèles, mémoire), monté comme sous-application FastAPI sur `/admin` dans `src/api/server.py`. Interface sombre avec sidebar et badges de statut.
- **SDK Client Python (`src/client/`)** : Client REST sans dépendances externes (stdlib `urllib`), couvrant tous les endpoints (santé, mémoire, modèles, notifications, fichiers, cloud, calendrier, email). Retourne des objets Pydantic, pattern best-effort (pas d'exception levée). **48 tests — tous verts**.
- **VOLET 02 Phase 2 — Services Backend (Ch. 03, 07, 09)**
  - **Notification Service** (`src/services/notification/`): types.py, interfaces.py, store.py, manager.py. 8 types de notification (info, warning, error, approval_request, approval_decided, system, task_completed, task_failed), 4 niveaux de priorité, stockage en mémoire thread-safe avec filtres (type, destinataire, rôle, priorité minimale), marquage de lecture individuel et groupé, statistiques agrégées
  - **Search Service** (`src/services/search/`): types.py, interfaces.py, manager.py. Recherche unifiée multi-source (knowledge, memory, document, vision) avec fusion pondérée par source, tri par pertinence/date, filtrage par score minimum. Architecture extensible : tout moteur implémentant `SearchProvider` peut être branché
  - **File Service** (`src/services/file/`): types.py, interfaces.py, store.py, manager.py. Upload avec validation (taille max 10 Mo, nom requis, contenu non vide), mapping automatique type MIME → catégorie (12 catégories), stockage mémoire thread-safe, mise à jour des métadonnées, statistiques par catégorie/type
  - **Integration EngineRegistry** : 3 nouveaux moteurs (notification, search, file) dans ENGINE_NAMES avec builders lazy, propriétés et availability()
  - **API REST** : 14 nouveaux endpoints — notification (POST /notification/send, POST /notification/list, POST /notification/mark-read, POST /notification/mark-all-read, GET /notification/stats, DELETE /notification/{id}), search (POST /search), file (POST /file/upload, GET /file/{id}, POST /file/list, GET /file/stats, DELETE /file/{id})
  - **Tests** : 93 tests unitaires dans `tests/test_services.py` couvrant les 3 services (types, store, manager, cas d'échec, résilience aux pannes store)
- **Phase 4 — Generalized Persistence (VOLET_01, chapitre 03, PERSISTENCE; ADR-005)**
  - `SQLiteModelStore` (`src/storage/sqlite_model_store.py`): replicates the
    `InMemoryModelStore` semantics (same filters, same `updated_at` descending
    sort, same limit) with a verbatim Python filter loop over `list_items`
    (`rowid` order = insertion order); serialization through
    `ModelItem.to_dict()/from_dict()`; `RLock` + `PRAGMA busy_timeout = 5000`;
    `cleanup_expired()` removes DEPRECATED models
  - `SQLiteKnowledgeStore` (`src/storage/sqlite_knowledge_store.py`): 26 columns
    covering the Phase 1 reliability hierarchy (source_category, priority,
    confidence, citation, retrieved_at…); enums serialized as `.value`, datetimes
    as `isoformat()`, lists/dicts as JSON; `list_items` faithfully replicates the
    in-memory filter loop; `cleanup_old_versions()` returns 0 (one version per ID)
  - Configurable data directory: `GALSEN_DATA_DIR` (default `"data"`) resolved by
    `src/storage/paths.py` → `default_sqlite_path(filename)`; backend selected by
    `GALSEN_STORAGE_BACKEND` ("in-memory" by default, "sqlite" for durability)
  - Engine wiring via environment-variable dependency injection in
    `ModelManagerImpl` and `KnowledgeManagerImpl`: injected store wins → else
    sqlite env var → else in-memory store. Deferred **absolute** imports
    (`from storage.sqlite_*_store import ...`) inside `__init__` (avoids the
    circular import AND stays compatible with the project's top-level package
    convention)
  - Fixed `InMemoryKnowledgeIndexer._rebuild_index()`: it accessed the in-memory
    store's private `_data` dict (crashed with `AttributeError` on a SQLite
    store) → now uses the public `list_items()` interface. The index (a derived
    structure) is still rebuilt in memory at manager construction
  - Concurrency: per-instance `RLock` + `PRAGMA busy_timeout = 5000`; shared
    `:memory:` base via `cache=shared` for test isolation
  - `tests/test_storage_engines.py`: 43 unit tests covering CRUD, version
    semantics, filters, cleanup, persistence across reopen, `:memory:`,
    serialization round-trips (enums, dates, JSON, priority) and engine backend
    selection (env var + explicit injection + `GALSEN_DATA_DIR`)
  - Aligned `src/memory_engine/memory_manager.py` with the project convention:
    the module-level relative import `from ..storage.sqlite_store import
    SQLiteMemoryStore` became the absolute `from storage.sqlite_store import
    SQLiteMemoryStore` — the last remaining `..storage` relative import in an
    engine manager (same bug class fixed in Model/Knowledge managers); memory
    and storage tests still pass (96 tests)
- **Phase 3 — Human Approval Gate (VOLET_01, chapitre 06, GOVERNANCE; ADR-006)**
  - `src/approval_engine/` package: `types.py`, `interfaces.py`,
    `approval_store.py`, `approval_manager.py`, `__init__.py`
  - `ApprovalStatus` enum (pending, approved, rejected) and `ApprovalRequest`
    dataclass (id, agent_id, action, description, reason, confidence, timestamps,
    decided_by, status) with serialization
  - `generate_approval_request_id()` producing unique `appr_<hex>` identifiers
  - `InMemoryApprovalStore`: thread-safe store (RLock), unique submission,
    idempotent approve/reject, filtered and ordered listing, pending-queue
    (oldest first), aggregated stats, clear
  - `ApprovalManagerImpl`: best-effort manager that never raises (every method is
    guarded and returns an empty default)
  - Registered as the `approval` engine in `EngineRegistry` (purely in-memory,
    always available — satisfies the dynamic registry test comparison)
  - `AgentContext`: `approval` property plus `submit_approval()`,
    `approve_approval()` and `reject_approval()` delegating best-effort to the
    registry
  - `BaseAgent`: `approval_required`, `approval_description` and
    `approval_confidence` attributes; execution returns status
    `requires_approval` when the gate is required, and a controlled error when
    the approval engine is unavailable
  - `RetryManager`: terminal statuses extended with `requires_approval`
    (never re-executed); only genuine errors are retried
  - `ResultAggregator`: priority `errors > requires_approval > success`;
    `failed_agents = len - successful - pending`; `requires_approval` re-evaluated
    to `partial_success` once all actions eventually succeed
  - `AgentRuntime.execute_task()` and `RouterEngine.process_request()`: global
    status `requires_approval`, collected `approval_request_ids`, aggregation
    consistent with the router
  - API: 5 approval endpoints in `src/api/server.py` — `GET /approval/pending`,
    `GET /approval/stats`, `GET /approval/{request_id}`,
    `POST /approval/{request_id}/approve`, `POST /approval/{request_id}/reject`
    (404/409 handled)
  - `test_approval_engine.py`: 33 unit tests covering types, store, manager,
    registry, context, BaseAgent, RetryManager and ResultAggregator
- **Phase 2 — Structured Audit System (VOLET_01, chapitre 03, AUDITABILITY)**
  - `src/audit_engine/` package: `types.py`, `interfaces.py`, `audit_store.py`,
    `audit_manager.py`, `__init__.py`
  - `AuditEventType` enum (request, agent, tool, generation, knowledge) and
    `AuditStatus` enum (success, partial_success, failure, unavailable, skipped,
    running)
  - `AuditEvent` dataclass logging timestamp, request_id, agent_id, user_request,
    model_id, confidence, knowledge_sources, execution status and execution time
    — the nine fields required by the AUDITABILITY spec
  - `KnowledgeSourceRef` for provenance/citation of knowledge sources used
  - `generate_request_id()` producing unique `req_<hex>` identifiers
  - `InMemoryAuditStore`: thread-safe store (RLock), event_type/status/agent_id/
    request_id/since/until filters, case-insensitive full-text search, aggregated
    stats (by status/type/agent, average execution time)
  - `AuditManagerImpl`: best-effort manager that never raises (every method is
    guarded and returns an empty default), JSON export with accents preserved
    (`ensure_ascii=False`)
  - Registered as the `audit` engine in `EngineRegistry` (purely in-memory, always
    available — satisfies the dynamic registry test comparison)
  - `AgentContext.record_audit()` plus automatic audit tracing of `search_knowledge`,
    `add_knowledge`, `use_tool` and `generate` (SUCCESS/FAILURE/SKIPPED/UNAVAILABLE
    statuses, confidence and knowledge sources recorded, sensitive arguments
    redacted as `key=***`)
  - `BaseAgent`: every agent execution (success and failure) is audited with
    `action=agent:<id>`, engines used and duration
  - `AgentRuntime.execute_task()` and `RouterEngine.process_request()`: request_id
    generated up front, a summarizing REQUEST event on success and failure, and
    request_id present in both success and error responses
  - `test_audit_engine.py`: 35 unit tests covering types, store, manager, context
    integration and registry integration
- Architecture manual consolidation
  - `scripts/merge_architecture_volets.py`: merges the chapter files of all 26 manual
    folders in `docs/architecture/` into 25 single Markdown documents
    (`VOLET_01.md` → `VOLET_25.md`, 10 chapters each), preserving the original
    content byte-for-byte and the original chapter order. Source folders and
    chapter files are left untouched. Integrity is verified per file (each source
    present in the merge + exact byte count).
- Embassions Tool for generating text embeddings using sentence-transformers models
  - `EmbeddingsTool` (`src/tools/embeddings/tool.py`): provides interface for generating embeddings for one or more texts
  - Supports lazy loading of models, configurable model name, device, and normalization
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- OCR Tool for optical character recognition
  - `OCRTool` (`src/tools/ocr/tool.py`): provides interface for extracting text from images using Tesseract OCR
  - Supports lazy loading of dependencies (Pillow, pytesseract), configurable language and Tesseract command path
  - Returns extracted text, confidence scores, and optional bounding boxes
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Database Tool for SQLite database operations
  - `DatabaseTool` (`src/tools/database/tool.py`): provides simple SQL execution, table listing, and schema inspection
  - Supports executing raw SQL with parameters, fetching results, listing tables, retrieving table schema
  - Includes proper connection handling, autocommit mode, and foreign key enforcement
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Memory Tool for GalSen IA memory engine
  - `MemoryTool` (`src/tools/memory/tool.py`): provides interface for memory operations (store, retrieve, search, update, delete, list)
  - Supports short-term, long-term, user, agent shared, conversation, session, workspace/project, and knowledge memories
  - Integrates with the Memory Engine via the MemoryManager
  - Integrated with the Tool Engine via the tools registry
- Browser Tool for web browsing capabilities
  - `BrowserTool` (`src/tools/browser/tool.py`): provides web browsing capabilities to fetch and interact with web pages
  - Supports visiting URLs, extracting text content, extracting links, and getting page titles
  - Includes error handling, retry mechanisms, and proper HTTP headers
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
  - This is one of the remaining tools declared in `tools/tools.yaml` to be implemented.
- PDF Tool for PDF text extraction
  - `PDFTool` (`src/tools/pdf/tool.py`): provides interface for extracting text from PDF files using PyPDF2
  - Supports lazy loading of PyPDF2 dependency, configurable page selection (specific pages or all pages)
  - Returns extracted text, total page count, and list of pages that were processed
  - Includes proper error handling for missing files, invalid paths, and missing dependencies
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Email Tool for sending emails via SMTP
- Calendar Tool for managing calendar events
  - `CalendarTool` (`src/tools/calendar/tool.py`): provides interface for managing calendar events (list, add, delete)
  - Supports listing events, adding new events with validation, deleting events by ID
  - Includes proper error handling for invalid parameters and missing data
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Docker Tool for Docker container management
  - `DockerTool` (`src/tools/docker/tool.py`): provides interface for managing Docker containers (list, run, stop, remove)
  - Supports listing containers, running containers with options, stopping containers, and removing containers
  - Includes proper error handling for Docker daemon unavailability and API errors
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Logging Tool for managing application logs
  - `LoggingTool` (`src/tools/logging/tool.py`): provides interface for managing application logs (list, add, clear)
  - Supports listing logs, adding log entries with levels, clearing logs
  - Includes proper error handling for invalid parameters
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- Metrics Tool for collecting and retrieving metrics
  - `MetricsTool` (`src/tools/metrics/tool.py`): provides interface for collecting and retrieving metrics (counters, gauges, histograms)
  - Supports incrementing counters, setting gauges, recording histogram values, retrieving all metrics, resetting
  - Includes proper error handling for invalid parameters
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)

- Model Engine provider layer, making providers interchangeable (see ADR-003)
  - `ModelProvider` (`src/model_engine/providers/base.py`): the single contract —
    declared catalogue, availability check, generation. No code above this file
    refers to a specific vendor.
  - `ProviderRegistry`: which providers exist and which can answer right now
  - `ModelRegistry` (`src/model_engine/model_registry.py`): catalogue of every known
    model with context window, capabilities and price. Readable with no provider
    configured, so the platform can explain what a task would need.
  - `CapabilityDetector`: asks the provider that serves the model, falling back to
    the pre-existing `StaticCapabilityDiscoverer` for hand-registered models
  - `ProviderSelector`: derives requirements from the task type and complexity,
    then picks the cheapest capable model among available providers
  - Providers: `OpenAIProvider`, `AnthropicProvider`, `GoogleProvider` (catalogues
    declared, generation unavailable until credits are decided) and
    `LocalProvider` (Ollama, fully implemented and generating today when a server runs)
  - `GenerationResponse` carries a status, an empty text on failure, a machine
    readable `reason` and an actionable `detail`
  - `ModelManagerImpl.generate()`: structured generation API; `get_provider_status()`,
    `list_catalogue()`, `select_provider_for_task()`, `explain_selection()`,
    `register_provider()`, `sync_catalogue_to_store()`
- `model` tool exposing the Model Engine through the Tool Engine
- `tail` operation on the filesystem tool, reading the end of a file without a
  size limit
- ADR-003 recording the model provider architecture
- Nine provider tests in `test_model_engine.py` covering the registry, provider
  interchangeability, unavailability reporting, the catalogue, capability
  detection, automatic selection, cost preference, the local probe and the
  cross-engine integrations
- Engine integration layer connecting the engines to the agents and orchestrators
  - `EngineRegistry` (`src/integration/engine_registry.py`): builds each engine once,
    lazily, and shares the instance across the platform. An engine that cannot be
    built is reported unavailable rather than raising into unrelated code.
  - `AgentContext` (`src/agent/context.py`): the object handed to every agent,
    carrying the request, the results of earlier agents, and shortcuts to memory,
    knowledge, documents, vision, tools and models
  - `BaseAgent` / `AgentResult` (`src/agent/base_agent.py`): result shape, error
    containment, timing and memory tracing, so agents only implement `perform`
  - `src/agent/legacy.py`: preserves the historical `execute(input_data)` contract
- Nine agents rewritten to call real engines instead of returning formatted strings
  - `planner`, `researcher`, `coder`, `reviewer`, `tester`, `security`,
    `documentation`, `deployment`, `monitor`
  - Agents that would act outside the process (deploy, push, rewrite docs) report
    what should be done instead of doing it
- Four Tool Engine connectors, previously declared in `tools/tools.yaml` but missing
  - `filesystem`: 13 operations, confined to the project root including through
    symbolic links, writing disabled by default
  - `terminal`: executes without a shell, with an executable allowlist and a timeout
  - `git`: read-only by default; pushing to a protected branch and force pushing are
    refused in code, per `.claude/rules/git-workflow.md`
  - `github`: read-only REST client reading its token from `GITHUB_TOKEN` at call time
- `test_integration.py`: 18 tests covering the registry, the context, the four tool
  connectors, all nine agents, error containment and both orchestrators
- Knowledge Engine for unified knowledge management and RAG capabilities
  - KnowledgeManagerImpl: Main orchestrator with dependency injection for all components
  - KnowledgeStore: In-memory storage with thread-safe operations
  - KnowledgeLoaderFactory: Automatic loader selection by file extension/source type
    - TextFileLoader, JSONFileLoader, CSVFileLoader, WebPageLoader, APIDatasourceLoader
    - PDFLoader, DocxLoader (with graceful degradation if dependencies missing)
  - KnowledgeIndexer: In-memory inverted index for fast keyword search with TF-like scoring
  - KnowledgeRetriever: Semantic retrieval using TF-IDF cosine similarity
  - KnowledgeValidator: Input validation (content length, confidence, date consistency, spam detection)
  - KnowledgeGraph: In-memory directed graph for knowledge relationships with BFS path finding
  - KnowledgeCache: LRU cache with TTL support for frequently accessed knowledge
  - KnowledgeRanker: Configurable weighted ranking algorithm (confidence, recency, length, popularity, custom functions)
- Support for multiple input formats: TXT, JSON, CSV, PDF, DOCX, HTML, Markdown, web pages, APIs, databases
- Features: CRUD operations, full-text search, knowledge graph relationships, validation, caching, ranking, versioning, multi-language support (English, French, Spanish, etc.)
- Comprehensive test suite covering all components and integration scenarios
- Model Engine (unified AI model management system)
  - Model Manager, Model Store (in-memory), Model Loader, Model Selector, Model Router
  - Model Context Manager, Prompt Optimizer, Response Validator, Token Tracker
  - Rate Limiter, Retry Manager, Stream Handler, Parallel Executor, Response Ranker
  - Health Monitor, Capability Discoverer
- Support for multiple providers (OpenAI, Anthropic, Google, etc.)
- Intelligent model selection based on task requirements
- Fallback mechanisms, load balancing, and health monitoring
- Prompt optimization per model type, response validation, hallucination detection
- Token usage tracking, cost tracking, rate limiting, retry mechanisms
- Streaming support, parallel execution, and response ranking
- Web Search Tool for intelligent web search
  - WebSearchTool: Multi‑provider search engine with caching, rate limiting, retry, parallel execution
  - Supports web, news, image, video search; suggestions; filters; language/country selection; safe search
  - Features: duplicate removal, ranking, metadata/snippet extraction, citation generation
  - Integrates with Tool Engine, Memory Engine, Model Engine, Knowledge Engine
- Document Intelligence Engine for unified document processing and understanding
  - DocumentManagerImpl: Main orchestrator with dependency injection for all components
  - DocumentStore: In‑memory storage with thread‑safe operations
  - DocumentLoaderFactory: Automatic loader selection by file extension/source type
  - Features: document loading, chunking, indexing, search, retrieval, summarization, question answering, comparison, duplicate detection, metadata/table/image extraction, versioning, caching, validation
- Vision Intelligence Engine for image understanding and analysis
  - Supports image formats: JPG, JPEG, PNG, WEBP, BMP, TIFF
  - Features: metadata extraction, quality analysis, object detection via provider interface, scene description, face detection without identification
  - Integrated with Router Engine, Agent Runtime, Tool Engine, Memory Engine, Model Engine, Knowledge Engine
- Embeddings Tool for generating text embeddings using sentence-transformers models
  - `EmbeddingsTool` (`src/tools/embeddings/tool.py`): provides interface for generating embeddings for one or more texts
  - Supports lazy loading of models, configurable model name, device, and normalization
  - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- ADR-005: Select SQLite as persistent storage backend
  - Added SQLite memory store (`src/storage/sqlite_store.py`) implementing the `MemoryStore` interface for persistent storage.
  - Modified `MemoryManager` to accept an optional `MemoryStore` dependency, enabling persistence while maintaining backward compatibility with in-memory storage. The storage backend can be selected via the `GALSEN_STORAGE_BACKEND` environment variable (values: "in-memory" or "sqlite", default: "in-memory").
- API Layer for exposing platform functionality via RESTful API
  - Created `src/api/server.py`: FastAPI-based server exposing memory, model, knowledge, and tool endpoints.
  - Provides endpoints for memory storage/retrieval/search, model generation, tool execution, and knowledge search.
  - Integrates with existing engines: MemoryManager, ModelManagerImpl, KnowledgeManagerImpl, ToolEngine.
  - Includes Pydantic models for request/response validation.
  - Updated requirements.txt with fastapi, uvicorn, pydantic.
  - Verified basic functionality with manual tests.
- Agricultural Advisory Tool for providing crop advice in Wolof/French
    - `AgriAdviceTool` (`src/tools/agri_advice/tool.py`): provides interface for generating agricultural advice using AI models.
    - Supports generating advice in French or Wolof based on user query.
    - Integrated with the Tool Engine via the tools registry (`tools/tools.yaml`)
- API Authentication via API Key
    - Added API key authentication middleware (dependency) loaded from environment variable GALSEN_API_KEYS.
    - Protected all sensitive endpoints (memory, model, tool, knowledge) while keeping /health public.
    - Returns 401 for missing/invalid keys.
    - Created unit tests in tests/test_api_auth.py.
- Production-Grade API Rate Limiting
    - `src/api/rate_limiter.py`: Token bucket algorithm (InMemoryRateLimiter) with abstract
      `APIRateLimiter` interface enabling future migration to Redis without code changes.
    - `src/api/__init__.py`: Public API exports for all rate limiting components.
    - Configurable via environment variables: `GALSEN_RATE_LIMIT_ENABLED`, `GALSEN_RATE_LIMIT_AUTHENTICATED_RPM`
      (default 60), `GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM` (default 30),
      `GALSEN_RATE_LIMIT_BURST_MULTIPLIER` (default 2.0).
    - Different limits for authenticated (API key) and unauthenticated (IP) clients.
    - Burst multiplier allows short traffic bursts above the RPM average.
    - Thread-safe implementation with `threading.RLock()`.
    - FastAPI dependency `rate_limit_dependency` applied to all protected endpoints;
      rate limiting runs before authentication (429 before 401).
    - HTTP 429 responses include standard headers: `Retry-After`, `X-RateLimit-Limit`,
      `X-RateLimit-Remaining`, `X-RateLimit-Reset`.
    - Client identification: API key for authenticated clients, IP address
      (including `X-Forwarded-For` for reverse proxies) for unauthenticated clients.
    - Singleton pattern with double-checked locking ensures one rate limiter instance per process.
    - Integrated with existing API key authentication in `src/api/server.py`.
    - 34 comprehensive unit tests in `tests/test_api_rate_limiter.py` — all passing.
- Production-Grade Health & Monitoring Endpoints
    - `src/api/health.py`: Abstract `HealthChecker` interface and `ComponentHealthChecker` implementation
      for monitoring all platform components.
    - Three Kubernetes-compatible endpoints in `src/api/server.py`:
      - `GET /health` — Detailed health report of all components (API, memory engine, model engine,
        knowledge engine, tool engine, storage) with metadata (version, uptime, storage backend,
        configured providers). Always returns HTTP 200; overall status in response body.
      - `GET /ready` — Readiness probe verifying required components (API, tool engine) are available.
        Returns 200 when ready, 503 otherwise.
      - `GET /live` — Liveness probe (minimal check that the process is alive). Always returns 200.
    - `ComponentHealth` and `HealthReport` dataclasses with `to_dict()` for clean JSON serialization.
    - Per-component health checks: memory engine (write → read → delete test item), model engine
      (provider availability counts), knowledge engine (get_stats()), tool engine (list_tools()),
      storage (GALSEN_STORAGE_BACKEND env var).
    - Proper HTTP status codes: 200 for healthy, 503 when required dependencies unavailable.
    - Abstract `HealthChecker` interface designed for future Prometheus/Grafana integration without
      modifying calling code.
    - Singleton pattern with `threading.RLock()` and double-checked locking, identical to rate limiter.
    - Late binding via `set_tool_engine()` for tool engine initialized during FastAPI startup event.
    - Overall status computation: any unhealthy → unhealthy, else any degraded → degraded, else healthy.
    - `src/api/__init__.py` updated to export all health module components.
    - Integrated with existing rate limiting dependency on all health endpoints.
    - 58 comprehensive unit tests in `tests/test_api_health.py` — all passing.
- Production-Grade Docker & Deployment Foundation
    - `Dockerfile` — Image de production multi-stage avec `python:3.11-slim`, utilisateur
      non-root `galsen`, healthcheck Docker intégré via `/health`, et couche de
      dépendances séparée pour minimiser la taille de l'image.
    - `docker-compose.yml` — Deux services : `api` (production, port 8000) et `api-dev`
      (développement avec rechargement automatique, port 8001). Volumes nommés pour la
      persistance des données SQLite et des logs. Healthcheck Docker Compose intégré.
      Limites de ressources CPU/mémoire configurables. Réseau bridge dédié `galsen-network`.
    - `.env.example` — Documentation complète de toutes les variables d'environnement :
      stockage, sécurité, limiteur de taux, ports, fournisseurs de modèles IA,
      dépendances optionnelles.
    - `.dockerignore` — Exclusion du contexte Docker : secrets, caches, tests, docs,
      IDE files, virtualenvs, Git.
    - `docs/deployment/docker.md` — Guide complet de déploiement Docker : démarrage
      rapide, construction d'image, exécution avec et sans Compose, variables
      d'environnement, persistance des données, optimisation de taille, compatibilité
      Kubernetes avec exemple de Deployment, troubleshooting.
    - Compatibilité Kubernetes : endpoints `/health`/`/ready`/`/live` pour les probes,
      configuration entièrement par variables d'environnement, utilisateur non-root,
      signal handling via uvicorn.
- Persistent Storage Package (ADR-005) — `src/storage/`
    - `BaseRepository[T]` — Interface abstraite générique définissant le contrat CRUD
      (save, get, update, delete, list_items, clear, count, exists) pour tout backend
      de stockage, permettant de remplacer SQLite par PostgreSQL sans modifier le code
      appelant.
    - `SQLiteMemoryStore` — Implémentation concrète de `MemoryStore` avec persistance
      SQLite. Supporte les bases fichier et `:memory:` (cache partagé avec connexion
      persistante). Gère la sérialisation JSON pour le contenu, les tags et les
      métadonnées.
    - `cleanup_expired()` — Suppression des mémoires expirées basée sur `time.time()`.
    - `src/storage/__init__.py` — Package exportant `BaseRepository` et `SQLiteMemoryStore`.
    - `tests/test_storage.py` — 50 tests unitaires (8 classes) : BaseRepository, CRUD,
      filtrage, pagination, clear, cleanup_expired, cas limites (Unicode, contenu long,
      concurrence), persistance fichier et exports du package.
- **Phase 1 — Verifiable Knowledge Hierarchy (VOLET_01, chapitre 04)**
  - `KnowledgePriority` (IntEnum) : hiérarchie de fiabilité P1 → P4 (P1 = textes
    officiels, publications gouvernementales, normes et documentation officielles ;
    P2 = recherche évaluée par les pairs, documentation technique de confiance,
    institutions réputées ; P3 = références industrielles fiables, consensus d'experts ;
    P4 = estimations ou opinions clairement étiquetées). Classe utilitaire
    `KnowledgePriority.from_source_category()` qui dérive la priorité par défaut
    depuis la catégorie de source.
  - `SourceCategory` (Enum) : 12 catégories de sources (OFFICIAL, GOVERNMENT,
    STANDARD, OFFICIAL_DOCUMENTATION, PEER_REVIEWED, TRUSTED_DOCUMENTATION,
    INSTITUTIONAL, INDUSTRY, EXPERT_CONSENSUS, ESTIMATE, OPINION, UNKNOWN).
  - `KnowledgeSource` enrichi : `source_category`, `title`, `author`, `url`,
    `citation`, `retrieved_at` — traçabilité et citation complètes.
  - `KnowledgeItem.priority` : champ avec valeur par défaut P3 ; préservé par
    `update_content()`.
  - Validation renforcée (`knowledge_validator.py`) : type de source obligatoire
    pour P1/P2 (source traçable avec `id` et `location` définis), vérification des
    types de `source_category`/`retrieved_at`, priorité doit être un
    `KnowledgePriority`, avertissement de cohérence priorité/source.
  - Classement par priorité (`knowledge_ranker.py`) : critère `priority`
    (score `1.0 - (priority-1)/3.0`), méthode `rank_by_priority()`, poids
    équilibrés mis à jour (confidence 0.35, priority 0.25, recency 0.2, ...).
  - Filtres de priorité dans le store (`knowledge_store.py`) : `priority`,
    `min_priority`, `max_priority`, `source_category`.
  - `KnowledgeManager.retrieve_reliable()` : récupération fiable uniquement,
    retourne `{items, reliable, best_priority, best_confidence, reason}` ; renforce
    le comportement « Je ne sais pas » quand aucune connaissance fiable n'est
    disponible.
  - Outil RAG mis à jour (`src/tools/rag/tool.py`) : conversion P1–P4, provenance
    et citation sérialisées, option `require_reliable`/`min_priority` sur
    `retrieve_for_prompt`.
  - Nouveaux tests : 4 tests knowledge engine (hiérarchie P1–P4, provenance,
    filtrage de fiabilité, validation priorité) + 1 test RAG
    (round-trip priorité/provenance).

### Fixed
- Suite de tests stabilisée — 213 tests passent, 0 échecs
  - `test_vision_engine.py::test_image_classification` : `np.float32` n'est pas une sous-classe de `float` Python — corrigé avec `isinstance(score, (float, np.floating))`
  - `test_integration.py::test_terminal_tool` : `echo` n'existe pas comme exécutable standalone sur Windows — remplacé par `python -c "print(...)"`
  - `test_model_engine.py::test_model_engine` : fonction async sans décorateur `@pytest.mark.asyncio` — ajouté
  - `test_rag_tool.py::test_add_and_retrieve` : variable `update_data` non définie après mise à jour + échec de mise à jour car la version n'était pas incrémentée — corrigé
  - `src/tools/rag/tool.py::_op_update` : `KnowledgeItem` créé sans incrémenter la version, causant le rejet de la mise à jour par le store — corrigé
  - `src/knowledge_engine/knowledge_manager.py` : méthode `get_store()` manquante, appelée par `_op_list` du RAGTool — ajoutée
- Infinite recursion in the agent pipeline: `test_router.py` runs every agent,
  including `tester`, which ran `test_router.py` again. Nested execution is now
  detected through an inherited environment flag, and orchestration suites are
  excluded from agent-driven runs because running them there is circular.
- Orchestration suites went from 222s to 34s once the circular runs were removed
  and the web search timeout was shortened
- Reviewer agent reported declarations found inside docstrings as undocumented code
- Missing docstrings on the three `_HTMLTextExtractor` callbacks
- Dead `pass` block in `csv_loader.py` header handling
- Fourteen over-long lines in the document engine loaders and interfaces
- Document Intelligence Engine could not be imported at all: 9 loaders used `from ..types import`,
  which raised `ImportError: attempted relative import beyond top-level package`
- `html_loader` imported `html.parser.Parser`, which does not exist (correct name is `HTMLParser`)
- `ocr_loader` referenced an undefined variable `st` and shadowed the `format` builtin
- `DocumentLoaderFactory()` instances registered no loader; only the module-level singleton did,
  so a directly constructed factory silently failed to recognise most formats
- `DocumentManagerImpl.load_document()` called `DocumentItem.from_dict()` on an object that was
  already a `DocumentItem`
- `CompositeMetadataExtractor` raised `NameError` on an undefined `me`
- `DocumentMetadata` was missing the `line_count` field that its own extractor wrote to
- Document IDs derived from `time.time()` collided when several documents were saved within the
  same millisecond; they now use UUIDs
- `SimpleChunker` could emit chunks up to 100 characters larger than requested and could loop
  forever when the overlap left no progress
- `LRUDocumentCache` accepted a TTL argument and ignored it
- New document versions were built but never stored, so they could not be retrieved by ID
- `unregister_document` deleted the document but left it in the search index
- `json_loader` used the JSON `name` field as document title, which is an entity name, not a title
- Removed `text_loader.py`, an unregistered duplicate of `txt_loader.py`
- Document engine test suite crashed on Windows before running any assertion, because its own
  ✓ output characters are not encodable in cp1252
- KnowledgeIndexer.search() now returns List[tuple[KnowledgeItem, float]] instead of List[str]
- KnowledgeManagerImpl.search_knowledge() and retrieve_for_prompt() updated to correctly unpack search results
- KnowledgeManagerImpl stats output format changed to match test expectations ("store" instead of "knowledge_store")
- KnowledgeManagerImpl now exposes ranking methods: rank_by_confidence, rank_by_recency, rank
- Fixed date handling in tests to use timezone-aware datetime objects
- Fixed knowledge item setup in tests to properly set both created_at and updated_at for age simulation
- KnowledgeValidator date comparison now works with timezone-aware datetime objects
- Fixed missing imports and updated credential detail message in hosted providers to enable environment‑based credential handling (ADR-004)

## Pre-release history — never tagged

The two sections below were written while the version number lived in two places at once
(`0.1.0` in the application, `0.2.0` in the Docker image). **No tag was ever created for
either**, so neither was a release in any sense a user could act on. They are kept
because they are history, and moved under this heading so that `v0.1.0` above is
unambiguously the first release.

### 0.2.0 — 2026-07-31 (development)
#### Added
- Project foundation structure
- Root `CLAUDE.md` with permanent memory system
- Core memory files (`vision`, `current-objectives`, `completed-work`, `pending-work`, `priorities`, `knowledge-index`)
- Complete folder structure for long-term development
- Router Engine (core orchestration component)
- Agent Loader, Workflow Loader, Config Loader, Execution Planner, Result Aggregator, Retry Manager, Logger, Agent Dispatcher
- Agent Runtime (parallel/sequential execution engine with retry handling)
- Placeholder agents for all agent types (Planner, Researcher, Coder, Reviewer, Tester, Security, Documentation, Deployment, Monitor)
- Updated agent registry with module paths for dynamic loading
- Tool Engine architecture (dynamic tool loading and execution)
- Tool Loader, Tool Executor, Tool Engine, and BaseTool interface
- Updated tools registry with module and class information for each tool
- Memory Engine (unified memory management system)
  - Memory Manager, Memory Store (in-memory), Memory Retriever, Memory Indexer, Memory Cache (LRU), Memory Summarizer, Memory Ranking
  - Designed for future storage backends (vector databases, SQL, local, cloud)

#### Changed
- Nothing yet

#### Fixed
- Nothing yet

### 0.1.0 — 2026-07-28 (development)
- Initial project foundation created