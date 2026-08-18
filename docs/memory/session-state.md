# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session
**2026-08-17 — Coding Engine et interopérabilité portés depuis la seconde ligne de développement.**
`src/coding_engine/` (OpenHands, Aider, SWE-agent derrière une abstraction native, ADR-028),
`src/code_edit/` (blocs d'édition) et `src/interop/` (OpenGAP, ADR-023). Aucun code des
projets externes recopié, aucune dépendance ajoutée, exécution passée par `src/sandbox`.
Branche : `claude/coding-engine-on-phases`, issue de `claude/galsen-ia-phases-ukwz7p`,
qui n'a **pas** été modifiée.

Puis les **8 échecs préexistants** ont été traités : 7 corrigés à la source (dont
l'agent testeur qui rapportait une suite en échec comme réussie), 1 laissé rouge —
`v0.1.0` doit être poussée, ce qui est une décision de mainteneur.

Vérifié : **5761 tests passent**, 11 ignorés, 1 échec. `ruff` propre.

**Prochaine étape** : fusionner cette branche, puis les deux gestes qui débloquent le reste —
`ollama serve` (génération + recherche sémantique) et un `ffmpeg` réel (cinq étapes média).

---

### Sessions précédentes
**Date** : 2026-08-16

**En cours** : rien. **Le moteur média universel est terminé — 20 VOLETs,
32 phases sur 32.** Rapport final → `docs/media/final-report.md`.

**Terminé dans cette session**
- **`src/media/`** : 26 modules, 21 fichiers de tests, **483 tests**. Capacités
  sondées, ingestion, scènes, transcription, montage déterministe, récit, motion
  design, fournisseurs + WanGP, audio, sous-titres, ressources, compétences,
  contrôle qualité, multi-format, file d'attente, outils d'agent, langage
  naturel, API, frontière de sécurité, mesures, aptitude, studio.
- **L'état est calculé** : `ENGINE READY — MEDIA RUNTIME DEPENDENCIES PENDING,
  1 STAGE(S) NOT IMPLEMENTED (VOICE)` — 10 `READY`, 6 `BLOCKED`, 1 `ABSENT`.
- **Aucune synthèse vocale n'existe dans ce dépôt** : trouvé en parcourant la
  chaîne. Rapporté `ABSENT`, jamais rangé parmi les dépendances manquantes.
- **Chiffres publiés re-mesurés, jamais assouplis** : 22 → 24 outils déclarés,
  123 → 131 routes. Quatre gardes du dépôt ont attrapé le travail ; toutes
  honorées.
- Suite : **5369 tests**, 8 ignorés, `ruff` propre.

**Prochaine étape**
Aucune en attente. Le prochain gain le plus élevé ne dépend pas de ce dépôt :
installer un vrai `ffmpeg` et `ffprobe` fait passer **cinq étapes** de `BLOCKED`
à `READY` sans une ligne de code — c'est l'intérêt des adaptateurs à sondes.
Ensuite : un adaptateur de synthèse vocale (la seule étape que rien n'implémente).

**Bloqué / à surveiller**
- **`ffmpeg` complet, `ffprobe`, `torch`, GPU et `whisper` absents** de cet
  environnement (mesuré). `frame_encode` et `image_analysis` sont disponibles.
- **Licence de WanGP non inspectée** : c'est une lecture, pas de l'ingénierie,
  et elle bloque la génération plus fermement que l'absence de GPU.
- **Aucun curriculum `TIER_A` publié** — seule condition pour que Darra J quitte
  `ARCHITECTURE READY`. N'appartient pas à ce dépôt.
- **Mandataire réseau** : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS
  répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
