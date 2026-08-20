# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **aucun**
Dernier terminé  : **DEEPSEEK HARNESS — GALSEN-IA COMPATIBILITY AUDIT**
                   14 phases sur 14, plan complet
                   `docs/deepseek-harness/phase-plan.md`,
                   rapport `docs/deepseek-harness/final-report.md`
Phase courante   : aucune — le VOLET est clos, en attente du suivant
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md` — toute
phase se termine par une validation de non-régression complète, jamais par une
compilation.

---

## La décision à ne pas re-déduire — ADR-035

**DeepSeek Harness entrerait comme quatrième back-end de codage, et pas encore.**
`0.1.0-rc.8`, MIT déposé, ~130 dépendances lues. **Aucune des onze portes
n'échoue franchement** : tout ce qui est structurel passe, tout ce qui est
empirique est `UNKNOWN`.

- **OPTION C** — un quatrième `CodingEngineAdapter` à côté d'`aider`,
  `openhands`, `swe_agent`. Ni orchestrateur, ni routeur de modèles, ni mémoire,
  ni hôte de greffons.
- **Implémentation non autorisée.** Trois conditions, toutes hors de cet
  environnement : **1)** mesurer la qualité (même jeu de tâches par un moteur
  existant et par DSH, sur une machine autorisée à installer) ; **2)** lire le
  fichier de licence de `@anthropic-ai/claude-agent-sdk` ; **3)** établir ce que
  persiste `dsh-headless`.
- **Une seule configuration viable** : `dsh-llm-pi-ai` pointé sur notre propre
  point d'entrée compatible OpenAI. **Rejetée** : DSH portant ses propres
  identifiants.
- **Son bac à sable ne peut pas tourner sur cet hôte** — `bwrap` absent,
  Landlock `ENOSYS`, stub faible, aucun LSM. Contrainte d'hôte, pas défaut du
  projet.

**Zéro ligne de `src/` modifiée, zéro dépendance, zéro test ajouté ou touché**
sur tout le programme.

## Trouvé sur GalSen IA par ces deux audits — rien n'est corrigé

1. **Aucun fichier `LICENSE`** dans ce dépôt (`ls LICENSE*` ne rend rien).
2. **Le test de souveraineté ne couvre pas les runtimes subordonnés** —
   deuxième occurrence après ADR-034 : deux projets, le même trou, donc le trou
   est ici.
3. **`load_capabilities()` non mise en cache, ~22 ms** — latent.

## Ce qui reste à l'opérateur, et à personne d'autre ici

- **`git push origin v0.1.0`** — l'étiquette n'a jamais été poussée
  (`git ls-remote --tags origin` ne rend rien). C'est l'unique test rouge de la
  CI, identique sur `main`, et c'est une décision du propriétaire.
- Les trois conditions d'ADR-035 ci-dessus.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases. ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases. ADR-031.
4. **Research Orchestration Integration** — 18 phases. ADR-032.
5. **Live Context Engine / Call.md** — 27 phases. ADR-033. **PR #31 ouverte.**
6. **OpenClaw Compatibility & Safe Integration** — 19 phases. ADR-034.
   **Décision : ne pas intégrer** (3 portes sur 12 à `NON` ; bac à sable
   désactivé par défaut, isolation multi-utilisateurs absente, treize des
   quatorze capacités déjà présentes ici). Le seul manque réel est un **canal**
   conversationnel bidirectionnel — un programme séparé, non autorisé par
   ADR-034.
7. **DeepSeek Harness Compatibility Audit** — 14 phases. ADR-035.
