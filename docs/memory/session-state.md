# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-22

**En cours** : rien. Aucun VOLET ouvert, aucune phase en attente.

**Terminé** : **les quatre constats de l'audit OSS sont fermés et sur `main`** —
**PR #34 fusionnée**, `main` à `5ce708a`. Le n°1 (matrice vectorielle) datait du
2026-08-20 ; les n°2, 3 et 4 ont été faits en quatre phases le 2026-08-21/22.
La branche `claude/galsen-ia-phases-ukwz7p` a été **repartie de `main`** après la
fusion : ne jamais empiler sur de l'historique déjà fusionné.

1. ~~`SQLiteVectorStore.search()` reconstruisait la matrice.~~ **CORRIGÉ** —
   **49,4 → 0,463 ms** à 271 vecteurs, **1 856,8 → 0,830 ms** à 10 000. Cache
   validé par un compteur de version écrit **dans la transaction de chaque
   écriture** (ADR-015 amendé).
2. ~~`Role.USER` atteignait `POST /coding/task` avec n'importe quel dossier.~~
   **CORRIGÉ** — deux moitiés. Les routes passent par le **plafond de rôle
   existant** (`src/tool/authorization.py`, aucune permission nouvelle), et
   `GALSEN_CODING_WORKSPACE_ROOTS` borne l'espace lui-même : **variable absente
   = refus total**, jamais « tout l'hôte ».
3. ~~L'approbation d'entraînement portait sur l'acte, jamais sur le contenu.~~
   **CORRIGÉ** — empreinte SHA-256 du texte inscrite dans la demande et
   recalculée à l'export. `export_pairs("oui")` ne passe plus.
4. ~~`litellm` installé, déclaré par rien.~~ **CORRIGÉ EN GARDE** — trois tests
   refusent qu'un paquet de moteur soit atteignable, déclaré ou importé. Ici il
   est **absent** ; numpy 2.4.6, cv2 5.0.0.

**Prochaine étape** : **rien — au repos**, décidé par le propriétaire le
2026-08-22 après que quatre candidats mesurés lui ont été proposés (ADR-020,
seul ADR encore `proposed` ; la quatrième source de recherche ; la vérification
d'identité ; ou un brief). Ils restent dans `pending-work.md`. **Ne pas ouvrir
de VOLET de sa propre initiative** : aucun fichier VOLET suivant n'existe, et
les quatre derniers programmes sont tous nés d'un brief du propriétaire.

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
