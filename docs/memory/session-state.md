# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session
**2026-08-18 — VOLET créatif repris : C13 et C14 livrés (35 phases sur 38).**
Programme en cours : **Universal Creative Intelligence, directive V4** →
`docs/creative/phase-plan.md`. Il était à l'arrêt après C12, non par blocage
mais par fin de quota du compte précédent.

C13 (§24–§26) : registre de langues **en données** (`corpus/creative/languages.yaml`,
19 langues), alternance codique par segment. Défaut corrigé : la couche vocale
validait contre les 4 langues des sous-titres — sérère et lingala, qui sont les
tests d'or 5 et 6 de §63, étaient **refusés**.
C14 (§27–§33) : échelle observation → validation, base de connaissance avec
frontière privé/global, boucle d'acquisition. La fréquence plafonne à
`CORROBORATED` ; `VALIDATED` exige un humain nommé, `OFFICIAL` une autorité
extérieure. Aucun entraînement sur les conversations, et c'est vérifiable.

**Prochaine étape** : **C15 — ModelRouter, appariement par capacités (§36, §43)**,
2 phases. Puis C16 (GPU/jobs/cache), C17 (API + tests d'or + MVP), C18 (rapport).

**Bloqué** : rien côté code. Sur cette machine : pas de GPU, pas de `torch`,
`huggingface.co` injoignable → génération, diarisation, ASR et lip-sync restent
`BLOCKED`, 8 licences de poids `UNKNOWN` (`docs/creative/feasibility.md`).
Et `git push origin v0.1.0`, seul échec de CI, qui appartient au mainteneur.

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
