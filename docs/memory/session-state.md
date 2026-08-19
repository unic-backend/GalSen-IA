# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-19

**En cours** : rien. Le VOLET Live Context est terminé, aucune phase en attente.

**Terminé** : **Live Context Engine / Call.md**, 16 volets, **27 phases**,
**ADR-033**. `src/live_context/` : 16 modules, **376 tests**, aucune dépendance
ajoutée. Rapport → `docs/live-context/final-report.md`.
L'état est **calculé** : `REPRESENTATION READY — NO LIVE PERCEPTION ON THIS
MACHINE, 5 STAGE(S) NOT IMPLEMENTED, 2 BLOCKED` (9 `READY`, 2 `BLOCKED`,
5 `ABSENT`). Toutes les étapes de représentation tournent, **aucune** étape de
perception. Les quatre audits ont **réduit** le programme : Call.md n'enregistre
pas sous Linux, VideoDB y porte capture *et* inférence, six des neuf items du
§41 existaient déjà, et la licence n'était pas l'obstacle.
Vérifié : suite complète **6 958 passent, 12 ignorés, 1 échec** (`v0.1.0`),
`ruff check .` propre, 30 scénarios `golden` → 24 `VERIFIED`, 6 `BLOCKED`.

**Prochaine étape** : la branche `claude/unit-tests-notification-search-file-4z0ok1`
porte tout le programme et **aucune PR n'est ouverte**. L'ouvrir, attendre la CI,
fusionner.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- `git push origin v0.1.0` → seul test rouge, en cinq programmes.
- Un périphérique de capture + un `LiveCaptureProvider` implémenté.
- `pip install faster-whisper` → débloque l'étape de transcription.
- `ollama serve`, un `ffmpeg` réel, supprimer `feature/service-unit-tests` (403).

**Dette nommée** : `docs/memory/completed-work.md` dépasse 1 150 lignes — la
règle demande d'archiver au-delà de 200. Signalé, non fait : hors périmètre de
ce programme. Plus l'écart de sens `invocation`/`min_vram_gb` (ADR-031), la
décision TTS, et les conditions Pexels/Pixabay/Exa/DuckDuckGo non lues.

---

### Sessions précédentes

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
