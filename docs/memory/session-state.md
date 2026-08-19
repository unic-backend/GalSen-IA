# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

---

## Dernière session — 2026-08-19

**En cours** : rien. Aucun VOLET ouvert, aucune phase en attente.

**Terminé** : deux programmes, **35 phases**, fusionnés dans `main` par la
**PR #29** (merge `e099d9c`).

1. **Creative Canvas & Cinema Orchestration** — 17 phases, **ADR-031**.
   `docs/canvas/final-report.md`. *Il n'y avait rien à importer* : §4 rend
   **0 KEEP, 0 ADAPT**, et deux des cinq dépôts n'ont **aucune licence** —
   la directive les annonçait MIT, c'est faux, mesuré.
2. **Research Orchestration Integration** — 18 phases, **ADR-032**.
   `docs/research/final-report.md`. *Un seul candidat est une bibliothèque, et
   aucun ne tourne ici.* Agent-Reach route vers des CLI tiers dont **trois n'ont
   aucune licence**, et son README conseille un compte jetable.

Vérifié : `pytest -q` → **6 582 passent, 12 ignorés, 1 échec** (`v0.1.0`).
CI de la PR : 6 579 passés, 15 ignorés — trois tests s'ignorent en CI. `ruff` propre.

**Prochaine étape** : aucune imposée. `docs/memory/pending-work.md` et
`priorities.md` disent ce qui reste ; le mémorial (`memorial.md`, réécrit cette
session depuis des mesures) oriente un agent froid.

**Bloqué — gestes de l'exploitant, aucun faisable ici**
- `git push origin v0.1.0` → seul test rouge, en quatre programmes.
- Un `ffmpeg` réel → débloque cinq choses d'un coup.
- `pip install web-search-mcp` → cinq mesures `NOT_MEASURED` deviendraient des chiffres.
- Supprimer `feature/service-unit-tests` (403 sur les références distantes).

**Dette nommée, non oubliée** : l'écart de sens de `invocation` et de
`min_vram_gb` entre couches média et créative (ADR-031 acte que le prochain
changement qui touche l'un des deux le résout) ; une décision TTS à part entière
(`kokoro-tts` MIT et local contre `edge-tts` LGPL-3.0) ; les conditions de
Pexels, Pixabay, Exa et DuckDuckGo, non lues, qui sortiraient le commercial de
`UNKNOWN`.

---

### Sessions précédentes

**2026-08-18/19 — Universal Creative Intelligence (44 phases) et MoneyPrinterTurbo
(15 phases, ADR-030)**, fusionnés par la PR #28. **MPT ne génère pas de vidéo** :
il assemble des rushes Pexels/Pixabay. L'avoir lu dans la source *avant* d'écrire
l'adaptateur a évité de le déclarer `text_to_video` — un routeur aurait fini par
servir les rushes d'un inconnu à qui demandait son ami.

**2026-08-18 — ADR-029 tranchée (option C) : la plateforme a des comptes.**
Routes `/auth/register|login|refresh`, `/auth/me` accepte jeton **ou** clé. Trois
défauts corrigés avant montage, dont un **secret de signature en dur** qui
laissait forger un jeton d'administrateur. PR #26.

**2026-08-17 — Coding Engine et interopérabilité** (`src/coding_engine/`,
`src/code_edit/`, `src/interop/`, ADR-028 et ADR-023). Aucun code externe
recopié, aucune dépendance ajoutée. PR #25.

**2026-08-16 — Moteur média universel terminé**, 32 phases.
`docs/media/final-report.md`. État calculé : 10 `READY`, 6 `BLOCKED`, 1 `ABSENT`
— aucune synthèse vocale n'existe dans ce dépôt.

**Hérité, toujours vrai**
- `ffmpeg` complet, `ffprobe`, `torch`, GPU et `whisper` absents.
- Licence de WanGP non inspectée.
- Mandataire : 9 domaines `.sn`, Banque mondiale, UNESCO, FAO, OMS → `CONNECT 403`.
- `ollama serve` : génération et récupération sémantique non mesurées.
