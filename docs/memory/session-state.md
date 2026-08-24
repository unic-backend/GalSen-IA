# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-24 (P3)

**En cours** : rien. Mission « PHASE 2 — DEEP REASONING » : P3 (raisonnement),
vérification, auto-correction et branchement de `src/skills/` faits. Bancs de
modèles, serveurs d'inférence et infrastructure d'entraînement **non entamés**.
Branche `claude/galsen-ia-phases-ukwz7p`, PR #37 ouverte.

**Terminé** : **le chat critique sa propre réponse et peut la réécrire une
fois.** Décision → **ADR-041**. Et **`src/skills/` est enfin branchée** —
elle existait sans que rien n'y écrive.

À savoir sans relire :
- **Deux modules, et la frontière est la conception.** `critics.py` constate et
  ne corrige rien ; `deliberation.py` décide quoi en faire. **Aucun critique
  n'interroge un modèle** : `agents/verifier/agent.py` explique pourquoi.
- **Budget épuisé ⇒ la réponse est servie AVEC ses constats.** Une boucle qui
  rend en silence une réponse qu'elle sait douteuse ajoute une garantie qui
  n'existe pas. `GALSEN_CHAT_MAX_RETRIES`, une reprise par défaut ; `0` garde
  la critique et n'arrête que la reprise.
- **Le banc se donne 66,7 %, et c'est voulu.** Sa première version faisait 8/8 :
  cas et contrôles sortaient de la même main. Quatre cas réellement ratés y ont
  été ajoutés. Un banc dont le score ne peut que monter est une décoration.
- **Le `tester` range, pas le `coder`.** C'est le seul endroit du dépôt où
  existe une preuve. Un verdict vert **sans exécution** est refusé : le
  `tester` rend `passed: True` quand il s'exclut par ré-entrance.
- **Défaut trouvé en construisant** : `empty_answer` exigeait trois mots et
  signalait « 42 ». **Vide veut dire vide.**

**Prochaine étape** : bancs de modèles réels et serveurs d'inférence
(vLLM/SGLang via `OpenAICompatibleProvider`, déjà présent) — tout cela attend
un GPU. Puis l'infrastructure d'entraînement (SFT/LoRA/QLoRA).

**Décisions en attente du propriétaire** (aucune faite)
1. **Déclarer `coder` dans le workflow `question`** — l'agent n'est pas atteint
   depuis le chat, donc la boucle de compétences ne tourne pas depuis `/chat`.
2. **P10 de l'audit Linux** : la boucle d'événements se bloque pendant un
   `/chat` (`/health` : 3,5 ms → 1 149 ms). Une reprise allonge encore le tour.
3. **Portée régionale dans `KnowledgeScope`**, ou expansion pays par pays.

**Repère mesuré le 2026-08-24** : `pytest -q` → **7309 passés, 9 ignorés,
3 désélectionnés, 0 échec**. `ruff check src tests scripts agents` → tout passe.
**62 tests ajoutés, 0 supprimé, 0 affaibli.**

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- **`ollama serve`** : sans serveur, les profils de modèles restent `declared`
  au lieu de `measured`, et aucune reprise réelle n'a jamais tourné.
- `git push origin v0.1.0` → seul test rouge en CI, rouge sur `main` aussi.
  Refusé d'ici : `HTTP 403`, mesuré. **Ne pas réessayer, ne pas « corriger ».**
- `GALSEN_CODING_WORKSPACE_ROOTS` non renseignée → le moteur de codage refuse tout.
- Cet hôte : **aucun GPU**, `ffmpeg` absent, Hugging Face, `qwenlm.github.io` et
  `api.github.com` en 403. `raw.githubusercontent.com` et `pypi.org` répondent.

---

### Sessions précédentes

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
