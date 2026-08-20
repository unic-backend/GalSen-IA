# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-20

> ### ⚠ REPRISE : lire `docs/oss-ecosystem/handover.md` AVANT toute autre chose.
> Il contient le passage de relais complet — état exact, règles, mesures déjà
> faites, et ce que chacune des 8 phases restantes doit produire.
> **Ne pose aucune question à l'utilisateur : tout y est.**

**En cours** : **VOLET OPEN-SOURCE ECOSYSTEM AUDIT** — audit de 12 projets
open-source (Transformers, SGLang, llama.cpp, LangGraph, OpenHands, vLLM,
LiteLLM, LlamaIndex, Qdrant, Open WebUI, Unsloth, whisper.cpp).
**14 phases sur 22 terminées.** La suivante est **E06.2**, en attente de
confirmation. Cadence : **deux phases par tour**.

**Terminé cette session** : PR #31 et PR #32 fusionnées sur `main` (Live Context
ADR-033, audits ADR-034/035, **ADR-036 Apache-2.0**, test de souveraineté des
runtimes subordonnés, mémoire réalignée, `completed-work.md` 1 170 → 83 lignes).
Puis les Ch. 01 à 05 et la moitié du Ch. 06 du VOLET en cours — 14 documents
dans `docs/oss-ecosystem/`. **Zéro ligne de `src/`, zéro dépendance, zéro test
touché** : le §12 de la directive interdit d'implémenter pendant l'audit.

**Prochaine étape** : `git fetch origin && git reset --hard origin/claude/unit-tests-notification-search-file-4z0ok1`,
puis **E06.2** (licences des six derniers) et **E07** (audit de sécurité, §9).

**Résultat du VOLET à ce stade** : **zéro `INTEGRATE` sur douze**. Trois constats
sur GalSen IA elle-même, aucun corrigé, tous destinés au Ch. 07 :
`SQLiteVectorStore.search()` est **3 388 × plus lent** que le design qu'ADR-015
décrivait ; `Role.USER` atteint `POST /coding/task` avec n'importe quel dossier
de l'hôte (exposition **latente** — aucun moteur n'est disponible) ; et
`litellm==1.81.10` est installé sans être déclaré ni importé.

**Repère de non-régression, à chaque phase** : `1 failed, 6967 passed,
12 skipped`. L'unique échec est l'étiquette `v0.1.0`, **identique sur `main` et
en CI** — ce n'est pas une régression, ne pas la « corriger ».

**Piège de l'environnement, vu trois fois** : le conteneur est recyclé et le
clone retombe sur `8879e8b`. Un `docs/oss-ecosystem/` absent = clone périmé,
**jamais un programme perdu**. Faire le `git fetch` avant de conclure.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- `git push origin v0.1.0` sur `383fcf7` → seul test rouge. **Publie une release
  GitHub.** Refusé d'ici : `HTTP 403`, mesuré deux fois. Ne pas réessayer.
- `ollama serve` (critère C1) ; les 3 conditions d'ADR-035 ; un nom légal dans
  `LICENSE`/`NOTICE` à la place de « GalSen IA ».
- Cet hôte : **aucun GPU**, **`ffmpeg` absent**, Hugging Face et
  `api.github.com` en **403**. `raw.githubusercontent.com` et `pypi.org`
  répondent — c'est par là que les licences ont été lues.

---

### Sessions précédentes

**2026-08-20 — Finalisation, PR #32** : ADR-036 (Apache-2.0, choisie pour la
concession de brevet du §3), `tests/test_sovereignty_subordinate_runtimes.py`,
trois mensonges de la mémoire corrigés.

**2026-08-19/20 — OpenClaw (19 phases, ADR-034 : ne pas intégrer)** et
**DeepSeek Harness (14 phases, ADR-035 : quatrième back-end de codage,
implémentation non autorisée)**. Même méthode, réponses différentes.

**2026-08-19 — Live Context Engine / Call.md**, 27 phases, **ADR-033**.
`REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE`. **PR #31.**

**2026-08-19 — Creative Canvas (ADR-031) et Research Orchestration (ADR-032)**,
PR #29. *Il n'y avait rien à importer.* Puis PR #30 : gouvernance spec-driven.

**2026-08-18/19 — Universal Creative Intelligence (44 phases) et
MoneyPrinterTurbo (15 phases, ADR-030)**, PR #28. **MPT ne génère pas de
vidéo** : il assemble des rushes Pexels/Pixabay.

**2026-08-18 — ADR-029 (option C) : la plateforme a des comptes.** PR #26.
**2026-08-17 — Coding Engine et interopérabilité** (ADR-028, ADR-023). PR #25.
**2026-08-16 — Moteur média universel**, 32 phases. Aucune synthèse vocale ici.

**Hérité, toujours vrai**
- Ni `/dev/snd`, ni `/dev/video*`, `DISPLAY` vide — mesuré par `capture.py`.
- Mandataire : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
