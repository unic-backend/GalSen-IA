# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-23

**En cours** : rien. **VOLET REDESIGN CHAT-FIRST terminé**, 8 chapitres, 11 phases,
branche `claude/galsen-ia-phases-ukwz7p`.

**Terminé** : la plateforme a une conversation. `POST /chat` (143 routes), le chat
sert `/ui/`, le tableau de bord passe sous `/ui/admin/`, menu de 14 domaines,
responsive mobile d'abord.

À savoir sans relire :
- **Aucun des 17 agents ne rédige.** Seuls `planner` et `coder` appellent le
  modèle, pour planifier et pour coder. Le workflow `question` est
  `planner → researcher → senegal → verifier` : recherche et vérification, pas
  conversation. **`/chat` rend donc le refus des agents, jamais une phrase
  fabriquée** — c'est honnête, et ça ne converse pas encore. Rendre le chat
  *conversant* demande une étape de rédaction : **non autorisée, non faite.**
- L'orchestrateur a l'honnêteté que `/agri/advice` n'a pas : l'agent `senegal`
  répond `empty_base` avec « la base est vide sur ce sujet — ce n'est pas une
  réponse négative ». **1,1 s** par tour, mesuré.
- **Trois défauts trouvés en relisant du travail déjà déclaré terminé** :
  le jeton d'ancrage fabriquait sa classe par interpolation (`jeton.grounded`,
  invalide) et **n'a jamais eu sa couleur** ; `grounding.reason` était jeté ;
  le déplacement du tableau de bord avait rendu le formulaire agricole et le
  Media Studio **inatteignables en cliquant**. `tests/test_ui_chat.py`
  (`TestJetonAncrage`) tient le premier, sabotage vérifiée.

**Prochaine étape** : rien d'autorisé. La branche n'est pas fusionnée et aucune PR
n'a été demandée pour ce volet. Décision en attente du propriétaire : ouvrir ou
non l'étape de rédaction qui ferait vraiment converser le chat.

**Ce qui a servi** : *une suite lancée avec `| tail -4` cache ses échecs.* Un run
a rapporté « 25 failed » dont **3 seulement étaient visibles**, et les 22 autres
ont été déclarés verts. Rediriger la sortie vers un fichier, jamais la tronquer.

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
