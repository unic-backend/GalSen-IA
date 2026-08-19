# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-18/19

**Deux programmes terminés**, tous deux poussés sur
`claude/unit-tests-notification-search-file-4z0ok1` (`36de732`), arbre propre.

1. **Universal Creative Intelligence** — 44 phases sur 44, dont **C19 (§46, le
   registre de styles)** qui comblait un trou que le plan avait perdu.
   Rapport → `docs/creative/final-report.md`.
2. **Master Update Directive V4 — MoneyPrinterTurbo** — 15 phases sur 15.
   Rapport → `docs/providers/final-report.md`. ADR-030.
   **Il ne génère pas de vidéo** : il assemble des rushes de Pexels/Pixabay.
   L'avoir vérifié dans la source *avant* d'écrire l'adaptateur a évité de le
   déclarer `text_to_video` — un routeur aurait servi les rushes d'un inconnu.

Vérifié : `pytest -q` → **6 233 passent, 1 échec** (`v0.1.0`). `ruff` propre.

**En attente d'une décision** : **PR #28** (les deux programmes), ouverte, CI
relancée sur `36de732`. Elle ne sera jamais verte tant que `v0.1.0` n'est pas
poussée — l'échec est antérieur et identique sur `main`.

**Gestes qui appartiennent à l'exploitant**
- `git push origin v0.1.0` depuis un clone normal → seul test rouge de la CI.
- Un `ffmpeg` réel → débloque **cinq** choses d'un coup (4 étapes média + MPT).
- Supprimer `feature/service-unit-tests` (obsolète) — cet environnement refuse
  la suppression de références distantes (403).

**Dette nommée, non oubliée** : décision TTS à part entière (`kokoro-tts` MIT et
local contre `edge-tts` LGPL-3.0), `whisperx` pour la séparation de locuteurs,
l'écart de sens de `None` entre couches média et créative, et la lecture des
conditions Pexels/Pixabay qui sortirait le commercial de `UNKNOWN`.

---

### Sessions précédentes

**2026-08-18 — ADR-029 tranchée (option C) : la plateforme a des comptes, avec mots de passe.**
Routes `/auth/register|login|refresh` montées, `/auth/me` accepte jeton **ou** clé.
Trois défauts corrigés avant montage, dont un **secret de signature en dur dans le dépôt**
qui laissait forger un jeton d'administrateur. ADR-010 amendée, pas contredite.
Fusionnée dans `main` par la PR #26.

**2026-08-17 — Coding Engine et interopérabilité portés depuis la seconde ligne de développement.**
`src/coding_engine/` (OpenHands, Aider, SWE-agent derrière une abstraction native, ADR-028),
`src/code_edit/` (blocs d'édition) et `src/interop/` (OpenGAP, ADR-023). Aucun code des
projets externes recopié, aucune dépendance ajoutée, exécution passée par `src/sandbox`.
Fusionnée dans `main` par la PR #25.

**2026-08-16 — Le moteur média universel est terminé** — 20 VOLETs, 32 phases sur 32.
Rapport final → `docs/media/final-report.md`. `src/media/` : 26 modules, 483 tests.
État calculé : 10 `READY`, 6 `BLOCKED`, 1 `ABSENT` (aucune synthèse vocale n'existe
dans ce dépôt — trouvé en parcourant la chaîne, jamais rangé parmi les dépendances
manquantes).

**Bloqué / à surveiller (hérité)**
- `ffmpeg` complet, `ffprobe`, `torch`, GPU et `whisper` absents de cet environnement.
- Licence de WanGP non inspectée.
- Mandataire réseau : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
