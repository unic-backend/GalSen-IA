# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-22

**En cours** : rien. VOLET SUPERPOWERS AUDIT **terminé, 24 phases sur 24**.

**Terminé** : audit de compatibilité Superpowers (`obra/superpowers` à
`b36e0829`, v6.3.0) → **`PARTIAL-GO`**, rapport dans
`docs/research/superpowers-audit.md` (1 836 lignes, 18 points de §25 + bloc §26).
**Zéro fichier hors `docs/` touché, rien installé, rien implémenté.**

Ce qu'il faut savoir sans relire le rapport :
- Superpowers est **de la prose** : 29 322 lignes de markdown contre 4 012 de
  code, **MIT**, **zéro dépendance**, aucune surface d'import. Ce n'est ni un
  modèle, ni un runtime, ni une bibliothèque.
- **19 sous-systèmes sur 37 : `KEEP GALSEN`. `REPLACE` : zéro.**
- **Le constat qui porte la décision** : les 15 fichiers de `.claude/rules/`, les
  14 skills et `CLAUDE.md` n'ont **aucune preuve** de changer le comportement d'un
  agent. Ce dépôt sabote ses gardes avant d'y croire — jamais sa prose.
- **Un conflit direct** : « ne pas s'arrêter entre les tâches » contre
  `phase-protocol.md`. Exclu nommément de tous les candidats.
- **Un constat de sécurité** : un flux d'instructions auto-mis-à-jour injecté à
  chaque session. Vise **la voie plugin uniquement**, jamais la prose.
- **6 candidats C1–C6**, tous en réimplémentation native sauf `find-polluter.sh`
  (seule vraie copie, la notice MIT doit voyager avec).

**Prochaine étape** : **attendre une autorisation explicite** (§21, §27). Aucun
candidat n'est autorisé. Ordre suggéré si autorisé : C3 → C4 → C2 → C5 → C1 → C6.

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
