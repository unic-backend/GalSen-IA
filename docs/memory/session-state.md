# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-24 (Phase 3)

**En cours** : rien. Mission « PHASE 3 — REAL LOCAL BRAIN + SERVER » : routage
par rôle, reconnaissance de Qwen3.5, infrastructure serveur et banc de modèles
faits. **Aucun modèle n'a tourné** — c'est le fait principal de cette session.
Branche `claude/galsen-ia-phases-ukwz7p`, PR #37 ouverte.

**Terminé** : **la préférence tranche entre égaux, et un grand modèle est une
URL.** Décision → **ADR-042**. Déploiement → `docs/models/deployment.md`.

À savoir sans relire :
- **Cet hôte ne peut atteindre aucun poids.** Mesuré : `registry.ollama.ai`,
  `ollama.com`, `huggingface.co`, `cdn-lfs.huggingface.co` → `000`. Pas de GPU,
  pas d'Ollama. `pypi.org` et `raw.githubusercontent.com` répondent.
- **Les commandes vLLM sont recopiées, pas reconstruites** — recettes
  officielles `vllm-project/recipes`, lues cette session. Un drapeau inventé
  pour un modèle de 400 milliards coûte une heure de GPU loué à découvrir.
- **`role_preferences` n'agit qu'à égalité.** Elle ne remonte jamais un modèle
  moins capable, sinon elle deviendrait un routage en dur.
- **La vision de Qwen3.5 n'est pas déclarée.** Annoncée par des sources
  secondaires, elle sera mesurée par `/api/show`.
- **`bench.py` ne rend aucun chiffre sans modèle**, jamais un zéro : un taux nul
  se compare, une absence non. Et un écart < 1,5 tâche est `ÉGALITÉ`.
- **L'entraînement n'a pas été refait** : `scripts/training/train_adapter.py`
  est déjà une recette QLoRA réelle.

**Prochaine étape, sur ta machine** : `ollama serve`, puis
`ollama pull qwen3.5:9b` et `ollama pull qwen2.5:14b`, puis
`python scripts/models/preflight.py --generer`, puis
`python scripts/models/bench.py --modele qwen3.5:9b --contre qwen2.5:14b`.
C'est la seule séquence qui transforme `PREPARED` en `TESTED`.

**Décisions en attente du propriétaire** (aucune faite)
1. **Déclarer `coder` dans le workflow `question`** — l'agent n'est pas atteint
   depuis le chat, donc la boucle de compétences ne tourne pas depuis `/chat`.
2. **P10 de l'audit Linux** : la boucle d'événements se bloque pendant un
   `/chat` (`/health` : 3,5 ms → 1 149 ms).
3. **Base de `train_adapter.py`** : elle vise Qwen2.5-7B ; Qwen3.5 serait une
   autre base — une ligne, plus un entraînement réel qui demande un GPU.

**Repère mesuré le 2026-08-24** : `pytest -q` → **7345 passés, 9 ignorés,
3 désélectionnés, 0 échec**. `ruff check src tests scripts agents` → tout passe.
**36 tests ajoutés, 0 supprimé, 0 affaibli.**

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- **`ollama serve` + `ollama pull`** : sans eux, aucun chiffre de modèle
  n'existe et les profils restent `declared` au lieu de `measured`.
- **Un serveur GPU loué** pour Kimi K2.5, Qwen3.5-397B, DeepSeek-R1, GLM-5.1 :
  huit H200 chacun, et **aucun ne tient sur 12 Go**.
- `git push origin v0.1.0` → seul test rouge en CI, rouge sur `main` aussi.
  Refusé d'ici : `HTTP 403`, mesuré. **Ne pas réessayer, ne pas « corriger ».**
- `GALSEN_CODING_WORKSPACE_ROOTS` non renseignée → le moteur de codage refuse tout.

---

### Sessions précédentes

**2026-08-24 — P3, le chat critique sa réponse (ADR-041)** et `src/skills/`
branchée. Banc des critiques : 66,7 % de détection, 0 % de fausse alerte.

**2026-08-24 — Routage des modèles (ADR-040)** : il ne sélectionnait pas, il
prenait le premier de la liste. Six causes mesurées. Dix types de tâche et huit
intentions atteignent cinq modèles distincts.

**2026-08-23 — `/chat` rédige (ADR-039)**, 19 phases. `src/chat/` compose une
réponse et appelle `ModelManagerImpl`. « bonjour » : 1 092 ms → 77 ms.
Puis bibliothèque de compétences (`src/skills/`, idée d'Odyssey, MIT) — **non
branchée**.

**2026-08-22 — AUDIT #01 `codebase-memory-mcp`**, 16 phases → `KEEP FOR RESEARCH`.
Rapport : `docs/research/codebase-memory-mcp-audit.md`. Rien installé, rien intégré.

**2026-08-20 — Audit OSS (22 phases, ADR-037)**, PR #33 : douze projets, **zéro
`INTEGRATE`**, 16 documents, zéro ligne de `src/` touchée. *Le troisième audit
externe d'affilée à trouver le défaut ici plutôt que chez son sujet.*

**2026-08-20 — Branche parallèle abandonnée** : `claude/galsen-ia-phases-ukwz7p`
avait **refait** le programme Creative Intelligence déjà fusionné en PR #28.

**2026-08-20 — Finalisation, PR #32** : ADR-036 (Apache-2.0).
**2026-08-19/20 — OpenClaw (ADR-034 : ne pas intégrer)** et **DeepSeek Harness
(ADR-035 : implémentation non autorisée)**.
**2026-08-19 — Live Context (ADR-033)**, 27 phases, PR #31.
**2026-08-19 — Creative Canvas (ADR-031), Research Orchestration (ADR-032)**, PR #29.
**2026-08-18/19 — Universal Creative Intelligence, MoneyPrinterTurbo (ADR-030)**,
PR #28. **MPT ne génère pas de vidéo.**
**2026-08-18 — ADR-029 : la plateforme a des comptes.** PR #26.
**2026-08-17 — Coding Engine et interopérabilité** (ADR-028, ADR-023). PR #25.
**2026-08-16 — Moteur média universel**, 32 phases. Aucune synthèse vocale ici.

**Hérité, toujours vrai**
- Ni `/dev/snd`, ni `/dev/video*`, `DISPLAY` vide — mesuré par `capture.py`.
- Mandataire : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
