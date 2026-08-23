# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-23

**En cours** : rien. **VOLET « CHAT — RÉPONSE FINALE RÉELLE » : 17 phases sur
19 faites**, il reste la 10 (docs, en cours) et la 11 (rapport final).
Branche `claude/galsen-ia-phases-ukwz7p`, repartie de `main` après la fusion
de la PR #36.

**Terminé** : **`/chat` rédige enfin.** `src/chat/` compose une réponse à
partir de ce que l'orchestration a trouvé et appelle `ModelManagerImpl`.
Décision → **ADR-039**. Contrat et flux réel →
`docs/architecture/chat-final-response.md`.

À savoir sans relire :
- **Le brief se trompait deux fois, et la mesure l'a corrigé.** Le routage
  généraliste existait déjà (5 questions globales sur 5 n'appellent pas
  `senegal`), et le planner appelait déjà le modèle. La vraie cause était plus
  étroite : **rien ne rédigeait**.
- **Écrire n'ancre jamais.** L'ancrage est calculé avant la génération.
  `ChatResponse.generated` vaut vrai seulement si un modèle a écrit — sans ce
  champ, un refus composé serait indiscernable d'une réponse.
- **« bonjour » : 1 092 ms → 77 ms.** Une intention `conversation` ne mobilise
  aucun agent, et `selection_appliquee()` distingue enfin les trois cas.
  `recommended_agents()` faisait déjà cette distinction dans sa docstring ;
  elle a été **rétablie, pas inventée**.
- **Deux défauts trouvés en relisant mon propre travail** : `/chat` livrait
  `http://localhost:11434` dans son message d'erreur, et `_build_tasks`
  levait `IndexError` sur une intention sans agent.
- **Zéro modèle enregistré ici**, mesuré après le démarrage complet. Toute la
  chaîne est vérifiée avec un fournisseur simulé ; qualité, latence réelle et
  repli entre fournisseurs restent `UNKNOWN`.

**Prochaine étape** : phase 11 — rapport final en 12 points (§24 du brief).

**Décisions en attente du propriétaire** (ni l'une ni l'autre faite) :
1. **Déclarer `coder` dans le workflow `question`** — l'intention est corrigée
   mais l'agent n'est pas atteint. Brancher un chat sur un agent qui écrit des
   fichiers est une décision d'exploitant (§19). Un test épingle l'état réel.
2. **P10 de l'audit Linux devient urgente** : ajouter une génération allonge le
   tour, donc aggrave le blocage de la boucle d'événements (`/health` :
   3,5 ms → 1 149 ms pendant un `/chat`). Trois sites d'appel.

**Ce qui a servi** : *sabotez la garde avant de la croire* — cinq fois
aujourd'hui, dont une qui a montré qu'un test cassé avait raison contre moi.

**Repère mesuré le 2026-08-23** : `pytest -q` → **7 148 passent, 9 ignorés,
3 désélectionnés, 0 échec**. `ruff check src tests scripts agents` → tout passe.
44 tests ajoutés, **0 supprimé**.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- **`GALSEN_CODING_WORKSPACE_ROOTS` doit être renseignée** ou le moteur de codage
  refuse tout. C'est la correction du constat n°2 qui fonctionne comme prévu —
  avant, il acceptait l'hôte entier — mais ça se découvre mal en production.
- `git push origin v0.1.0` sur `383fcf7` → seul test rouge. **Publie une release
  GitHub.** Refusé d'ici : `HTTP 403`, mesuré deux fois. Ne pas réessayer.
- `ollama serve` (critère C1) ; les 3 conditions d'ADR-035 ; un nom légal dans
  `LICENSE`/`NOTICE` à la place de « GalSen IA ».
- Cet hôte : **aucun GPU**, **`ffmpeg` absent**, Hugging Face et
  `api.github.com` en **403**. `raw.githubusercontent.com` et `pypi.org`
  répondent.

---

### Sessions précédentes

**2026-08-22 — AUDIT #01 `codebase-memory-mcp`**, 16 phases → `KEEP FOR RESEARCH`.
Rapport : `docs/research/codebase-memory-mcp-audit.md`. Rien installé, rien intégré.

**2026-08-20 — Audit OSS (22 phases, ADR-037)**, PR #33 : douze projets, **zéro
`INTEGRATE`**, 16 documents, zéro ligne de `src/` touchée. C'est cet audit qui a
produit les quatre constats ci-dessus — *le troisième audit externe d'affilée à
trouver le défaut ici plutôt que chez son sujet.*

**2026-08-20 — Branche parallèle abandonnée** : `claude/galsen-ia-phases-ukwz7p`
avait **refait** le programme Creative Intelligence déjà fusionné en PR #28 — 21
modules contre 38, rien d'unique. Remise sur `main`, doublons abandonnés.

**2026-08-20 — Finalisation, PR #32** : ADR-036 (Apache-2.0, pour la concession
de brevet du §3), `tests/test_sovereignty_subordinate_runtimes.py`.

**2026-08-19/20 — OpenClaw (ADR-034 : ne pas intégrer)** et **DeepSeek Harness
(ADR-035 : quatrième back-end, implémentation non autorisée)**.

**2026-08-19 — Live Context / Call.md**, 27 phases, **ADR-033**, PR #31.
**2026-08-19 — Creative Canvas (ADR-031) et Research Orchestration (ADR-032)**,
PR #29. Puis PR #30 : gouvernance spec-driven.
**2026-08-18/19 — Universal Creative Intelligence (44 phases) et
MoneyPrinterTurbo (ADR-030)**, PR #28. **MPT ne génère pas de vidéo.**
**2026-08-18 — ADR-029 : la plateforme a des comptes.** PR #26.
**2026-08-17 — Coding Engine et interopérabilité** (ADR-028, ADR-023). PR #25.
**2026-08-16 — Moteur média universel**, 32 phases. Aucune synthèse vocale ici.

**Hérité, toujours vrai**
- Ni `/dev/snd`, ni `/dev/video*`, `DISPLAY` vide — mesuré par `capture.py`.
- Mandataire : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
