# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-20

**En cours** : rien. Aucun VOLET ouvert, aucune phase en attente.

**Terminé** : deux programmes d'audit, **par la même méthode et avec des
réponses différentes** — ce qui est la seule preuve que la méthode travaille.
- **OpenClaw** — 19 phases, **ADR-034** : **ne pas intégrer**. 3 portes sur 12 à
  `NON` (bac à sable désactivé par défaut, isolation multi-utilisateurs absente,
  13 des 14 capacités déjà ici). 13 documents → `docs/openclaw/`.
- **DeepSeek Harness** — 14 phases, **ADR-035** : **quatrième back-end de
  codage, et pas encore**. Aucune porte n'échoue franchement ; tout ce qui est
  structurel passe, tout ce qui est empirique est `UNKNOWN`. `BENCHMARK.md` ne
  publie **aucun score**. 11 documents → `docs/deepseek-harness/`.

**Zéro ligne de `src/` modifiée, zéro dépendance, zéro test touché** sur les deux.
**PR #31 fusionnée** — `1e09f6d` sur `main`, CI vérifiée avant fusion
(`1 failed, 6955 passed`, l'étiquette et rien d'autre).

Puis la finalisation, **fusionnée par la PR #32** (`f08a4ff` sur `main`) :
- **Trois mensonges de la mémoire corrigés** — `current-objectives.md` et
  `priorities.md` annonçaient C6 seul tenu (la feuille de route en compte
  **quatre**), gardaient ouverte la question tranchée par **ADR-029**, et
  disaient la base de connaissances vide (**212 objets secteur, 14 régions,
  45 départements**, mesurés).
- **`completed-work.md` : 1 170 → 83 lignes**, tout l'avant-19-août versé dans
  `archive/completed-work-2026.md`. Rien supprimé.
- **Le trou de souveraineté relevé deux fois est fermé** :
  `tests/test_sovereignty_subordinate_runtimes.py`, 9 tests, aucune ligne de
  `src/`. Le seul canal vers un runtime subordonné est `ModelSpec.api_key_env`,
  et aucun modèle joignable n'en déclare.
- **La plateforme a une licence — ADR-036, Apache-2.0.** Elle n'en avait
  **aucune**. Choisie pour la concession de brevet du §3, que MIT n'offre pas ;
  pas d'AGPL, qui gênerait les déploiements institutionnels que la vision vise.
  19 dépendances d'exécution lues avant de choisir, **zéro copyleft**. Texte
  récupéré depuis `apache.org`. `LICENSE` et `NOTICE` nomment « GalSen IA » —
  **y mettre un nom légal est la décision du propriétaire**.

Vérifié : **6 968 passent, 12 ignorés, 0 échec**, `ruff check .` propre.
**Attention au zéro** : il tient à l'étiquette `v0.1.0` créée dans ce clone —
rien n'a été réparé, et la CI échouera à l'identique tant qu'elle n'est pas
poussée.

**Prochaine étape** : attendre le prochain VOLET du propriétaire. Rien n'est en
attente sur `main` ; **PR #31 et PR #32 sont fusionnées**.

**Piège de l'environnement, vu deux fois** : le conteneur est recyclé et le clone
retombe sur un vieux commit (`8879e8b`). Rien n'est perdu — `git fetch origin` +
`git reset --hard origin/main` réaligne. Ne pas conclure qu'un programme a
disparu avant d'avoir fait ce fetch.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- `git push origin v0.1.0` → seul test rouge, en sept programmes. Cible correcte
  `383fcf7`. **Pousser l'étiquette publie une release GitHub** (`release.yml`).
  Refusé depuis cet environnement : `HTTP 403`, mesuré.
- Les 3 conditions d'ADR-035 : mesurer la qualité sur une machine autorisée à
  installer, lire la licence de `@anthropic-ai/claude-agent-sdk`, établir ce que
  persiste `dsh-headless`.
- `ollama serve`, un `ffmpeg` réel, un périphérique de capture.

---

### Sessions précédentes

**2026-08-19 — Live Context Engine / Call.md**, 27 phases, **ADR-033**.
`REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE`. **PR #31.**

**2026-08-19 — Creative Canvas (17 phases, ADR-031) et Research Orchestration
(18 phases, ADR-032)**, fusionnés par la **PR #29**. *Il n'y avait rien à
importer* : 0 KEEP, 0 ADAPT, et deux dépôts sur cinq n'ont aucune licence.
Puis la **PR #30** : couche de gouvernance spec-driven et Spec Kit installé.

**2026-08-18/19 — Universal Creative Intelligence (44 phases) et
MoneyPrinterTurbo (15 phases, ADR-030)**, PR #28. **MPT ne génère pas de
vidéo** : il assemble des rushes Pexels/Pixabay.

**2026-08-18 — ADR-029 (option C) : la plateforme a des comptes.** Trois défauts
corrigés avant montage, dont un secret de signature en dur. PR #26.

**2026-08-17 — Coding Engine et interopérabilité** (ADR-028, ADR-023). PR #25.

**2026-08-16 — Moteur média universel**, 32 phases. État calculé : 10 `READY`,
6 `BLOCKED`, 1 `ABSENT` — aucune synthèse vocale n'existe dans ce dépôt.

**Hérité, toujours vrai**
- `ffmpeg` complet, `ffprobe`, `torch`, GPU et `whisper` absents.
- Ni `/dev/snd`, ni `/dev/video*`, `DISPLAY` vide — mesuré par `capture.py`.
- Mandataire : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
