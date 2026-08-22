# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **SUPERPOWERS — IMPLÉMENTATION DES 6 CANDIDATS**
                   Autorisé par le propriétaire le 2026-08-22 (« autorisation de
                   tout »), sur la base de `docs/research/superpowers-audit.md`
Chapitres        : **7**
Phases           : **11**
Phase courante   : **3.1 — en attente de confirmation**
Terminées        : **1 (C3, clause de fraîcheur)**, **2 (C4, format de
                   décision)** — `verification.md`, `memory.md`, `phase-protocol.md`
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète.

**Ce qui reste exclu, malgré l'autorisation de tout.** L'audit a exclu cinq
choses *nommément*, et « tout » désigne les six candidats, pas les exclusions :

- la **cadence sans arrêt** (« ne pas s'arrêter entre les tâches ») — elle
  contredit `.claude/rules/phase-protocol.md`, que tu as rendu permanent ;
- **l'installation du plugin** — elle importerait cette cadence, un flux
  d'instructions auto-mis-à-jour et 9 skills inutiles ;
- `dispatching-parallel-agents` — `parallel_supported` vaut `False` ;
- `brainstorming` — seule surface de télémétrie du dépôt ;
- **la boucle de correction de sous-agents** — elle touche `workflows.yaml` et le
  comportement des agents, son coût-modèle est `UNKNOWN`, et l'audit a conclu
  qu'elle mérite son propre audit.

Si tu veux l'une de ces cinq, dis-le : ce sera un autre VOLET, pas celui-ci.

---

## Le plan

```
Ch. 01  C3  Clause de fraîcheur                          → 1 phase (indivisible)
            Une phrase dans `.claude/rules/verification.md` :
            la preuve se produit dans CE message, pas « cette session ».

Ch. 02  C4  Format de décision                           → 1 phase (indivisible)
            `Décision : <quoi> — <pourquoi> — <ce que ça coûte si c'est faux>`
            dans `.claude/rules/memory.md` et le protocole de phases.

Ch. 03  C2  Débogage systématique                        → 2 phases
            3.1 `.claude/skills/systematic-debugging/SKILL.md`, quatre phases
            3.2 pointeur depuis `verification.md` + vérification

Ch. 04  C5  Fin d'une branche de développement           → 1 phase (indivisible)
            Section dans `.claude/rules/git-workflow.md`.

Ch. 05  C1  Tester les instructions                      → 3 phases
            5.1 `.claude/skills/testing-instructions/SKILL.md`
            5.2 **ligne de base ROUGE** sur `verification.md`
            5.3 **VERT** + rapport de ce qui a été mesuré

Ch. 06  C6  `find-polluter.sh`                           → 2 phases
            6.1 lecture ligne à ligne, portage vers pytest, notice MIT
            6.2 **preuve** : introduire un vrai test pollueur et le faire trouver

Ch. 07      Clôture                                      → 1 phase (indivisible)
            ADR-038, CHANGELOG, `completed-work.md`, mémoire.
```

**Total : 11 phases.** Je commence par la phase 1 et je m'arrête après.

---

## Le point à voir avant de confirmer

**C1 exige de dépêcher des sous-agents.** C'est sa méthode : faire tourner un
scénario *sans* la règle pour observer l'échec, puis *avec*. Sans ça, C1 est un
skill de plus dont personne ne sait s'il marche — exactement le défaut qu'il est
censé corriger.

L'audit avait classé son coût par exécution en `UNKNOWN` parce qu'aucun modèle ne
répond sur cette machine (critère C1, `ollama serve`). **Cette mesure visait le
runtime de GalSen IA.** Pour éprouver `.claude/rules/`, l'agent concerné est
l'agent de codage lui-même, qui a un modèle — donc C1 **est** faisable ici.

Je ne dépêcherai aucun sous-agent sans que tu aies confirmé ce plan. Si tu
préfères que C1 s'arrête à l'écriture du skill sans exécution, dis-le : le skill
sera écrit et **marqué non éprouvé**, ce qui est honnête mais vide la moitié de
sa valeur.

---

## Ce qui a été décidé, pour ne pas le re-déduire

`docs/research/superpowers-audit.md` — 24 phases, `PARTIAL-GO`.
Source auditée : `obra/superpowers` à `b36e0829`, **v6.3.0**, MIT.

- **19 sous-systèmes sur 37 : `KEEP GALSEN`. `REPLACE` : zéro.**
- Superpowers est **de la prose** : 29 322 lignes contre 4 012 de code, zéro
  dépendance, **aucune surface d'import**.
- Le constat qui porte tout : **les 15 fichiers de règles n'ont aucune preuve de
  changer le comportement d'un agent.** C'est C1 qui répond à ça.
- **Une seule vraie copie** dans tout le programme : `find-polluter.sh`. La
  notice MIT et l'origine (`b36e0829`) voyagent avec.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **SUPERPOWERS AUDIT** — 24 phases, `PARTIAL-GO`.
2. **Les quatre constats de l'audit OSS** — 4 phases. PR #34 et #35 fusionnées.
3. **OPEN-SOURCE ECOSYSTEM AUDIT** — 22 phases. ADR-037 : zéro `INTEGRATE`.
4. **Universal Creative Intelligence** — 44 phases.
5. **MoneyPrinterTurbo** — 15 phases. ADR-030.
6. **Creative Canvas** (ADR-031) et **Research Orchestration** (ADR-032).
7. **Live Context Engine / Call.md** — 27 phases. ADR-033.
8. **OpenClaw** — ADR-034 : **ne pas intégrer**.
9. **DeepSeek Harness** — ADR-035 : implémentation non autorisée.
10. **Finalisation** — ADR-036 (Apache-2.0).
