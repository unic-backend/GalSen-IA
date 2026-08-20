# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-20

**En cours** : rien. Aucun VOLET ouvert, aucune phase en attente.

**Terminé** : **VOLET OPEN-SOURCE ECOSYSTEM AUDIT — 22 phases sur 22, ADR-037.**
Douze projets audités (Transformers, SGLang, llama.cpp, LangGraph, OpenHands,
vLLM, LiteLLM, LlamaIndex, Qdrant, Open WebUI, Unsloth, whisper.cpp) →
**zéro `INTEGRATE`**. 16 documents dans `docs/oss-ecosystem/`, rapport final
inclus. **Zéro ligne de `src/`, zéro dépendance, zéro test touché.**
Avant cela : **PR #31 et PR #32 fusionnées** (ADR-033, ADR-034, ADR-035,
**ADR-036 Apache-2.0**, test de souveraineté des runtimes subordonnés).

**Quatre constats sur GalSen IA, aucun corrigé — suggestions, pas tâches**
1. `SQLiteVectorStore.search()` est **3 388 × plus lent** que le design
   qu'ADR-015 décrivait : il relit et reparse chaque ligne à chaque requête.
   13 132 ms → **3,88 ms** à 100 000 vecteurs (153,6 Mo). La moitié p95 de la
   condition de renversement d'ADR-015 est atteinte **dès 271 vecteurs**.
   *C'est le point le plus utile trouvé par ce programme.*
2. `Role.USER` atteint `POST /coding/task` avec n'importe quel dossier de
   l'hôte. **Latent** : aucun des trois moteurs n'est disponible.
3. L'entraînement exige une approbation ADR-006 pour *l'exécution*, jamais pour
   *le contenu* du jeu de données.
4. `litellm==1.81.10` installé, déclaré par rien, importé par rien.

**Prochaine étape** : attendre le prochain VOLET du propriétaire. Tout est
poussé sur `claude/unit-tests-notification-search-file-4z0ok1` ; **rien n'est
fusionné sur `main` depuis la PR #32** — ouvrir une PR quand tu le décides.

**Repère de non-régression** : `1 failed, 6967 passed, 12 skipped`. L'unique
échec est l'étiquette `v0.1.0`, **identique sur `main` et en CI** — jamais une
régression, ne pas la « corriger ».

**Piège de l'environnement, vu trois fois** : le conteneur est recyclé et le
clone retombe sur `8879e8b`. Un dossier attendu absent = clone périmé, **jamais
un programme perdu**. `git fetch` avant de conclure.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- `git push origin v0.1.0` sur `383fcf7` → seul test rouge. **Publie une release
  GitHub.** Refusé d'ici : `HTTP 403`, mesuré deux fois. Ne pas réessayer.
- `ollama serve` (critère C1) ; les 3 conditions d'ADR-035 ; un nom légal dans
  `LICENSE`/`NOTICE` à la place de « GalSen IA ».
- Cet hôte : **aucun GPU**, **`ffmpeg` absent**, Hugging Face et
  `api.github.com` en **403**. `raw.githubusercontent.com` et `pypi.org`
  répondent — c'est par là que les 12 licences ont été lues.

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
