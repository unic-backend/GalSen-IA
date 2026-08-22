# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-22

**En cours** : rien. **AUDIT #01 `codebase-memory-mcp` terminé**, 16 phases.

**Terminé** : `DeusData/codebase-memory-mcp` à `010569fa` audité →
**`KEEP FOR RESEARCH`**. Rapport : `docs/research/codebase-memory-mcp-audit.md`.
**Rien installé, rien intégré, rien adapté. Zéro fichier hors `docs/`.**

À savoir sans relire :
- **Projet en C, 1,3 Go** (842 `.c`, 160 grammaires tree-sitter), **MIT**, aucun
  copyleft, **30 Mo de poids `nomic` embarqués** (Apache-2.0).
- **Réellement indépendant des fournisseurs** — vérifié dans le C : aucun client
  d'API, aucun appel sortant, la seule socket `AF_INET` vise `127.0.0.1`.
- **16 lignes sur 24 sont `KEEP`** parce que **`code-review-graph`, déjà branché
  ici, les couvre**. Ce n'est pas une capacité qui manque : c'est un **second
  fournisseur** d'une capacité existante.
- **Le risque** : il écrit des **fichiers d'instructions** dans `$HOME`
  (`global_rules.md`, `AGENTS.md`). Même classe de surface qu'ADR-038 a écartée.
  **Le retrait n'est pas propre** : désinstaller ne les efface pas.
- **`NOT_MEASURED`** sur la performance : la mesure qui déciderait est contre
  `code-review-graph`, et son serveur MCP s'est déconnecté deux fois ici.
- **Deux faux positifs écartés en lisant les correspondances** : « 7 MPL » était
  *simplecpp*, et `getaddrinfo` était une table générée de symboles Python.

**Prochaine étape** : rien d'autorisé. Le déclencheur nommé, si tu le veux :
mesurer tokens et appels contre `code-review-graph` sur les 5 questions de la
phase 8. Suggestion optionnelle non implémentée : arêtes `CALLS` et incrémental
par hachage dans `src/agent/`, le jour où `self_healer.py` en aura besoin.

**Ce qui a servi à chaque fois** : *sabotez la garde avant de la croire.* Une
sabotage a elle-même été fautive — la ligne ajoutée s'est collée à la
précédente, le fichier n'ayant pas de saut de ligne final ; le test était juste,
pas la sabotage.

**Repère de non-régression, mesuré sur `main` après la fusion** (run 32555510451) :
`1 failed, 7020 passed, 15 skipped, 3 deselected`. Avant la fusion, `main` à
`c88b555` donnait `1 failed, 6964 passed, 15 skipped` : **+56 verts, le même
unique échec**. Cet échec est l'étiquette `v0.1.0` — **jamais une régression, ne
pas la « corriger »**. En local sur un conteneur où l'étiquette existe, la suite
est entièrement verte : `7027 passed, 9 skipped, 3 deselected, 0 failed`. L'écart
de 6 ignorés vient de tests dépendants de l'environnement ; le total collecté est
le même des deux côtés.

**Piège d'environnement, mesuré** : un conteneur peut être provisionné **avant**
une dépendance déclarée. `bcrypt==5.0.0` était dans `requirements.txt` et pas
installé : **40 échecs et 16 erreurs**, tous d'auth. Mesurer la base **intacte**
sur la même machine avant de conclure à une régression.

**Piège de l'environnement, vu trois fois** : le conteneur est recyclé et le
clone retombe en arrière. Un dossier attendu absent = clone périmé, **jamais un
programme perdu**. `git fetch` avant de conclure.

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
