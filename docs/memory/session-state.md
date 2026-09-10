# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-09-10 (la branche `claude/arena-personal-ai-qh66ix` redémarrée après fusion, et la suite n'est plus verte)

**En cours** : rien. Le travail de la session précédente (abroger les règles qui
arrêtaient le travail demandé — `09a1a70`, `d8d97bf`) était déjà commité mais
**jamais poussé**, et le PR #38 de cette même branche avait entre-temps été
fusionné dans `main`. Rebasé sur `origin/main` (aucun conflit — même contenu),
vérifié, poussé en force-with-lease : `40b234f`.

**Terminé** :
- Rebase + push de la branche (règle « après un PR fusionné, redémarrer la
  branche, garder les commits non fusionnés » de `.claude/rules/git-workflow.md`).
- `ruff check scripts src tests agents` propre ; hook `session_bootstrap.py`
  reconfirmé sans trace de « PROTOCOLE DE PHASES »/« Je continue »/« ATTENDRE ».
- **Suite complète mesurée deux fois, à neuf** : `bcrypt` déclaré dans
  `requirements.txt` mais absent de ce conteneur → 56 échecs/erreurs
  (`test_auth_oauth.py`, `test_auth_hybrid.py`, `test_auth_reset_lockout.py`).
  Installé (`pip install bcrypt==5.0.0`) — **corrige tout**, confirmé par un
  second run complet. Le `Dockerfile` installe déjà correctement
  `requirements.txt` ; l'écart vient de ce bac à sable précis, pas du dépôt.
- **Après ce correctif : 7349 passés, 24 échoués, 6 erreurs, 11 ignorés, 3
  désélectionnés.** Aucun rapport avec la branche — diff contre `main` limité
  à 9 fichiers de règles/doc + `scripts/session_bootstrap.py`, zéro `src/`
  zéro `tests/`. Cause réelle : ce bac à sable a maintenant `faster-whisper`
  et un OpenCV complet **installés**, alors que `tests/test_multimodal_ingestion.py`,
  `tests/creative/test_golden.py`, `tests/creative/test_representation_voice.py`,
  `tests/creative/test_creative_providers.py`, `tests/media/test_media_*.py`,
  `tests/media/test_moneyprinterturbo.py` supposent ces outils **absents** en
  s'appuyant sur l'environnement réel plutôt que sur un double contrôlé — la
  moindre montée en capacité du bac à sable les casse. `test_requirements.py`
  le confirme : `faster-whisper` est importé par `src/agents/tools` et n'est
  déclaré nulle part.

**Prochaine étape** : ouvrir un VOLET séparé — « rendre les tests de capacité
absente déterministes (mock, pas environnement réel) + déclarer
`faster-whisper` » — voir `docs/memory/pending-work.md`. Ce n'est pas la
même mission que le repeal de règles, ne pas les mélanger.

**Bloqué** : rien sur la branche actuelle. Le repeal des règles est fait et
poussé ; aucun PR ouvert pour lui (non demandé).

---

### Sessions précédentes

**2026-08-24 — les dix épreuves** : mission « RUN THE FIRST REAL MODEL TEST »,
harnais câblé sur le **vrai** `/chat` (`src/model_engine/evaluation_suite.py`,
`scripts/models/evaluate.py`), branche `claude/galsen-ia-phases-ukwz7p`, PR #37.
**Aucun modèle n'a répondu ici** : `llama-cpp-python` s'installe, mais
`ollama.com`, `huggingface.co`, `hf-mirror.com`, `modelscope.cn`, `gpt4all.io`
→ `000`, `github.com/…/releases` → `403`. Aucun paquet pypi n'embarque de
poids utilisables (tinyllama, smollm, llm-gguf, minillm testés : code seul).
Prochaine étape restée sur la machine du propriétaire : `ollama serve` +
`ollama pull qwen3.5:9b` + `scripts/models/evaluate.py`. Mesuré alors :
7371 passés, 9 ignorés, 3 désélectionnés, 0 échec.

**2026-08-24 — Phase 3 (ADR-042)** : `role_preferences` tranche entre égaux,
Qwen3.5 reconnu, quatre familles serveur préparées avec les commandes vLLM
officielles recopiées.

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
- **2026-08-29 — PR #38** : plan de phase ARENA → GalSen IA (VOLET 65),
  fusionné dans `main` le 2026-09-02. GalSen IA absorbe ARENA sous
  `src/arena/`, licence Apache-2.0 commune, transfert fichier par fichier
  (sans historique Git — 6 secrets dans l'historique d'ARENA), rotation de
  clés préalable et séparée.
