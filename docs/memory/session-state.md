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
Vérifié après chaque phase : **6 958 passent, 12 ignorés, 1 échec** (`v0.1.0`),
`ruff check .` propre. Tout est poussé sur
`claude/unit-tests-notification-search-file-4z0ok1`.

**Prochaine étape** : attendre le prochain VOLET du propriétaire. **PR #31 reste
ouverte**, rouge uniquement sur `test_release_check`.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- `git push origin v0.1.0` → seul test rouge, en sept programmes.
- Les 3 conditions d'ADR-035 : mesurer la qualité sur une machine autorisée à
  installer, lire la licence de `@anthropic-ai/claude-agent-sdk`, établir ce que
  persiste `dsh-headless`.
- `ollama serve`, un `ffmpeg` réel, un périphérique de capture.

**Dette nommée** : **ce dépôt n'a aucun fichier `LICENSE`** (trouvé par les deux
audits). Le **test de souveraineté ne couvre pas les runtimes subordonnés** —
même trou relevé deux fois, donc il est ici. `completed-work.md` dépasse 1 150
lignes contre 200 autorisées.

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
