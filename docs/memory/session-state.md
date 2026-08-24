# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-24 (les dix épreuves)

**En cours** : rien. Mission « RUN THE FIRST REAL MODEL TEST » : le harnais est
fait et **tourne**, mais **aucun modèle n'a répondu** — c'est le résultat, pas
un contretemps. Branche `claude/galsen-ia-phases-ukwz7p`, PR #37 ouverte.

**Terminé** : les dix épreuves du propriétaire, câblées sur le **vrai** `/chat`
(`src/model_engine/evaluation_suite.py`, `scripts/models/evaluate.py`).

À savoir sans relire :
- **Le moteur s'installe, les poids non.** `llama-cpp-python 0.3.35` installé
  depuis pypi et importable. Mais `registry.ollama.ai`, `ollama.com`,
  `huggingface.co`, `hf-mirror.com`, `modelscope.cn`, `gpt4all.io` → `000`, et
  `github.com/…/releases` → `403`. La liste `noProxy` du mandataire dit ce qui
  passe : npm, jsr, pypi, crates.io, proxy.golang.org. **Aucun paquet pypi
  n'embarque de poids utilisables** (vérifié : tinyllama, smollm, llm-gguf,
  minillm — code seul, ≤ 30 Ko).
- **Les dix épreuves passent par `/chat`**, pas par un fournisseur direct :
  elles mesurent ce qu'un utilisateur reçoit, donc un calcul faux est jugé
  **après** la boucle de délibération.
- **Trois issues, jamais deux** : `PASS`, `FAIL`, `NOT_CHECKED`. Quatre épreuves
  n'ont aucune vérité vérifiable par machine ; leur réponse entière est gardée
  pour lecture humaine.
- **Une réponse non générée n'est jamais notée** — sinon on mesurerait le repli
  composé par la plateforme.
- **La clé jetable n'est pas un contournement** : mécanisme documenté
  `GALSEN_API_KEYS`, jamais écrite ni affichée.

**Prochaine étape, sur ta machine — c'est la seule qui produise des chiffres** :
```
ollama serve
ollama pull qwen3.5:9b && ollama pull qwen2.5:14b
python scripts/models/evaluate.py --modele qwen3.5:9b --contre qwen2.5:14b --json rapport.json
```

**Décisions en attente du propriétaire** (aucune faite)
1. **Déclarer `coder` dans le workflow `question`** — l'agent n'est pas atteint
   depuis le chat, donc TEST-05 mesure la rédaction, pas le moteur de codage.
2. **P10 de l'audit Linux** : la boucle d'événements se bloque pendant un
   `/chat` (`/health` : 3,5 ms → 1 149 ms).
3. **Base de `train_adapter.py`** : elle vise Qwen2.5-7B.

**Repère mesuré le 2026-08-24** : `pytest -q` → **7371 passés, 9 ignorés,
3 désélectionnés, 0 échec**. `ruff check src tests scripts agents` → tout passe.
**26 tests ajoutés, 0 supprimé, 0 affaibli.**

**Bloqué — aucun faisable ici**
- **Les poids.** Tous les hôtes refusés par la passerelle, mesuré deux fois.
- **`ollama serve` + `ollama pull`** sur ta machine : le seul geste qui
  transforme `NOT_EXECUTED` en résultat.
- **Un serveur GPU loué** pour Kimi K2.5, Qwen3.5-397B, DeepSeek-R1, GLM-5.1.
- `git push origin v0.1.0` → seul test rouge en CI, rouge sur `main` aussi.
  **Ne pas réessayer, ne pas « corriger ».**

---

### Sessions précédentes

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
