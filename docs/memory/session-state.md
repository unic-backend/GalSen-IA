# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-16

**En cours** : **Universal Media & Video Intelligence Engine** (directive
propriétaire, 42 sections) — **29 phases sur 32**, M01 à M18 terminés.
Plan et constats par volet → `docs/media/phase-plan.md`.

**Terminé dans cette session**
- **M15-M16** : adaptation multi-format (les positions sont relatives et
  **reposées**, le coût du recadrage centré refusé par §22 est *mesuré* à côté)
  et file de rendu (avancement **compté**, `None` quand le total est inconnu,
  annulation terminale, `RunStatus` réutilisé).
- **M17** : les seize outils de §24 avec `consumes`/`produces`, donc un
  enchaînement impossible refusé **avant** tout encodage ; deux déclarations au
  registre (`media` local et sans témoin, `media_generation` externe et
  approuvé). §25 : une demande non dite reste `UNSPECIFIED` et devient une
  **question** — aucune chaîne tant qu'une question est ouverte.
- **M18** : huit routes `/media`, et une frontière qui **donne la racine média**
  au résolveur existant au lieu de réécrire la règle de traversée.
- **Chiffres publiés re-mesurés, jamais assouplis** : 22 → 24 outils déclarés,
  123 → 131 routes, après que les gardes du dépôt ont attrapé la dérive.
- Suite : **5323 tests**, 8 ignorés, `ruff` propre. HEAD = `f56ad6c`.

**Prochaine étape**
**VOLET M19** (2 phases) : tests, mesures et rapport d'aptitude — puis **M20**
(1 phase, conditionnel à `src/web/`). Ensuite le rapport final en 13 points (§42).

**Bloqué / à surveiller**
- **`ffmpeg`, `ffprobe`, `torch`, GPU et `whisper` absents** de cet
  environnement (mesuré). Le moteur média est donc en adaptateurs à sondes :
  une capacité absente rapporte son état, jamais un résultat plausible.
- **Aucun curriculum `TIER_A` publié** — seule condition pour que Darra J quitte
  `ARCHITECTURE READY`. N'appartient pas à ce dépôt.
- **Mandataire réseau** : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS
  répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
