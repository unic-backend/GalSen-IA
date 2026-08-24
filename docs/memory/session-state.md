# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-24

**En cours** : rien. Mission « STRICT AUTONOMOUS AI ENGINE UPGRADE » —
priorités P0 à P2 traitées (couche modèle et routage). P3 à P8 non entamées.
Branche `claude/galsen-ia-phases-ukwz7p`, PR #37 ouverte.

**Terminé** : **le routage de modèles sélectionne enfin.** Il ne sélectionnait
pas : il prenait le premier de la liste. Décision → **ADR-040**. Candidats par
rôle → `docs/models/local-model-selection.md`.

À savoir sans relire :
- **Six causes, toutes mesurées, aucune supposée.** La plus grave était la
  cinquième : `generate_text_with_fallback` — le chemin que le chat appelle —
  **n'appelait jamais `ProviderSelector`**. Tout le routage vivait dans un
  composant que la génération ne consultait pas.
- **`/api/tags` ne porte pas de `context_length`.** La clé lue n'a jamais
  existé : tout modèle valait 8192, donc `summarization` (32k) et
  `document_analysis` (100k) étaient irroutables **par construction**.
- **Trois origines, jamais confondues** : `measured` (`/api/show`) >
  `declared` (`config/model_routing.yaml`) > `default`. `capability_sources`
  dit laquelle a fixé chaque champ. **Une mesure muette n'efface rien** —
  « non mesuré » n'est pas « mesuré faux ».
- **Sept des huit intentions du planner n'avaient aucune règle de routage.**
  « Écris une fonction Python » se faisait écrire par le plus petit modèle.
  Ajoutées à la politique, **pas renommées** dans le planner : elles désignent
  aussi les agents.
- **Aucun modèle téléchargé, chargé ni évalué.** Aucune revendication de
  qualité ne dépasse `OBSERVED` — `huggingface.co` et `qwenlm.github.io` sont
  en `EGRESS_BLOCKED`, mesuré.

**Prochaine étape** : P3 de la mission — raisonnement, vérification, outils.
La bibliothèque de compétences (`src/skills/`, ADR d'Odyssey) **n'est branchée
à aucun agent** : rien n'y écrit encore.

**Décisions en attente du propriétaire** (aucune faite)
1. **Déclarer `coder` dans le workflow `question`** — l'intention est corrigée,
   l'agent n'est pas atteint.
2. **P10 de l'audit Linux** : la boucle d'événements se bloque pendant un
   `/chat` (`/health` : 3,5 ms → 1 149 ms). Trois sites d'appel.
3. **Portée régionale dans `KnowledgeScope`**, ou expansion pays par pays.

**Repère mesuré le 2026-08-24** : voir le rapport de fin de session pour le
chiffre exact de `pytest -q` ; `ruff check src tests scripts agents` → tout
passe. **47 tests ajoutés, 0 supprimé, 0 affaibli.**

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- **`ollama serve`** : sans serveur, les profils restent `declared` au lieu
  d'être `measured`. C'est le geste qui active le plus de choses d'un coup.
- `git push origin v0.1.0` → seul test rouge en CI, rouge sur `main` aussi.
  Refusé d'ici : `HTTP 403`, mesuré. **Ne pas réessayer, ne pas « corriger ».**
- `GALSEN_CODING_WORKSPACE_ROOTS` non renseignée → le moteur de codage refuse tout.
- Cet hôte : **aucun GPU**, `ffmpeg` absent, Hugging Face et `api.github.com`
  en 403. `raw.githubusercontent.com` et `pypi.org` répondent.

---

### Sessions précédentes

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
