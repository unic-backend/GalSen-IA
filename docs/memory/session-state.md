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

**Quatre constats — le n°1 est corrigé, les trois autres restent ouverts**
1. ~~`SQLiteVectorStore.search()` reconstruisait la matrice à chaque requête.~~
   **CORRIGÉ le 2026-08-20.** Matrice mise en cache par (collection, modèle),
   validée par un compteur de version écrit **dans la transaction de chaque
   écriture** — pas un drapeau en mémoire : un cache que seul son processus
   sait invalider ment dès qu'un autre écrit, et un test l'écrit depuis une
   seconde instance pour le prouver. Mesuré ici : **49,4 → 0,463 ms** à 271
   vecteurs, **1 856,8 → 0,830 ms** à 10 000. 11 tests ; les 5 gardes
   anti-péremption vérifiées **en sabotant la validation** (elles passent au
   rouge, dont une qui ne discriminait pas et a été refaite). Amendement dans
   ADR-015, avec deux nuances sur le constat d'origine : 94,93 ms est **sous**
   le seuil de 100 ms, et la correction **ne déplace pas** le déclencheur —
   elle retire un surcoût qui n'en faisait pas partie.
2. `Role.USER` atteint `POST /coding/task` avec n'importe quel dossier de
   l'hôte. **Latent** : aucun des trois moteurs n'est disponible.
3. L'entraînement exige une approbation ADR-006 pour *l'exécution*, jamais pour
   *le contenu* du jeu de données.
4. `litellm==1.81.10` installé, déclaré par rien, importé par rien.

**Prochaine étape** : les constats 2, 3 et 4 restent ouverts (permission
`Role.USER` sur `/coding/task`, approbation du *contenu* d'entraînement,
`litellm` non déclaré). Puis attendre le prochain VOLET du propriétaire.

**Reprise du 2026-08-20** : la PR #33 a été fusionnée depuis la note ci-dessus.
Une branche parallèle (`claude/galsen-ia-phases-ukwz7p`) avait **refait** le
programme Creative Intelligence déjà fusionné en PR #28 — 21 modules contre 38,
rien d'unique — elle a été remise sur `main` et ses commits en double
abandonnés. Deux couches créatives concurrentes auraient divergé.

**Repère de non-régression** : `1 failed, 6967 passed, 12 skipped`. L'unique
échec est l'étiquette `v0.1.0`, **identique sur `main` et en CI** — jamais une
régression, ne pas la « corriger ». *Sur un conteneur où l'étiquette existe en
local, ce test passe et la suite est entièrement verte : mesuré le 2026-08-20,*
`6982 passed, 9 skipped, 3 deselected, 0 failed`.

**Piège d'environnement de plus, mesuré** : un conteneur peut être provisionné
**avant** une dépendance déclarée. Ici `bcrypt==5.0.0` est dans
`requirements.txt` et n'était pas installé : **40 échecs et 16 erreurs**, tous
d'auth, tous disparus après `pip install`. Avant de conclure à une régression,
mesurer la base **intacte** sur la même machine — c'est ce qui a montré que ces
40 échecs préexistaient.

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
