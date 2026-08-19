# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **OPENCLAW COMPATIBILITY & SAFE INTEGRATION**
Plan complet     : `docs/openclaw/phase-plan.md`
Phases           : 19
Phase courante   : **O00.1 — en attente de confirmation** (audit du dépôt,
                   première moitié des 27 sous-systèmes du §2)
Terminées        : aucune
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente en vigueur depuis le 2026-08-19** :
`.claude/rules/post-integration-validation.md` — toute phase se termine par une
validation de non-régression complète, jamais par une compilation.

---

## Ce que ce programme est, et ce qu'il n'est pas

**§20 énumère dix livrables et finit par « THEN STOP ».** C'est un programme
d'**audit avec une décision au bout**, pas une intégration. Trois choses sont
interdites sur tout le plan : installer OpenClaw, modifier l'orchestrateur / les
agents / la mémoire / le routage de fournisseurs, et écrire du code d'adaptateur.

Le §21 — l'adaptateur — est **conditionnel à la décision** et n'est pas planifié
ici. Il le sera séparément si l'audit conclut oui et que le propriétaire confirme.

**Ce plan ne dit pas ce qu'est OpenClaw.** §3 exige des sources officielles lues
**à l'exécution** et §4 interdit de confondre un runtime d'agent avec un modèle.
Les données d'entraînement de cette session ne sont pas une source. Chaque
affirmation portera sa date et son URL, ou vaudra `UNKNOWN`.

**Le risque nommé d'avance** : quatre programmes ont mesuré que le mandataire de
cet environnement répond `CONNECT → 403` sur une longue liste de domaines. Si
les sources officielles sont injoignables, O01 consigne `UNKNOWN` **avec le
refus exact mesuré**, et les douze portes du §19 sont tranchées sur ce qui a pu
être lu — jamais sur un souvenir.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases.
   `docs/providers/final-report.md`, ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases.
   `docs/canvas/final-report.md`, ADR-031.
4. **Research Orchestration Integration** — 18 phases.
   `docs/research/final-report.md`, ADR-032.
5. **Live Context Engine / Call.md** — 27 phases.
   `docs/live-context/final-report.md`, ADR-033. **PR #31 ouverte**, CI en cours.

## Ce que le dernier programme a mesuré, et qu'il ne faut pas re-déduire

**L'état de la chaîne live est calculé par `readiness()`**, jamais écrit :
`REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE, 5 STAGE(S) NOT
IMPLEMENTED, 2 BLOCKED`. Neuf `READY`, deux `BLOCKED`, cinq `ABSENT` — toutes
les étapes de représentation tournent, aucune étape de perception.

**La diarisation est `ABSENT` et non `BLOCKED`** : installer `pyannote`
fournirait la capacité et laisserait toujours rien pour l'appeler.

**Six des neuf items « ne pas dupliquer » du §41 de la directive Live Context
existaient déjà**, et le `NudgeEngine` demandé était `src/proactive/`. C'est le
précédent qui compte pour OpenClaw : la question utile n'est pas « que fait ce
projet », c'est « qu'ajoute-t-il à ce que ce dépôt a déjà ».
