# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **LIVE CONTEXT ENGINE / CALL.MD INTEGRATION**
Plan complet     : `docs/live-context/phase-plan.md`
Phases           : 27
Phase courante   : **L13.2 — en attente de confirmation** (readiness.py :
                   l'état calculé de la chaîne live — §31 à §34)
Terminées        : L00 à L12, et L13.1 — quatre audits, ADR-033, et `src/live_context/` :
                   `state.py`, `capture.py`, `fusion.py`, `speakers.py`,
                   `languages.py`, `assistance.py`, `intent.py`,
                   `screen.py`, `retention.py`, `memory.py`,
                   `creative.py`, `providers.py` (331 tests)
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente en vigueur depuis le 2026-08-19** :
`.claude/rules/post-integration-validation.md` — toute phase se termine par une
validation de non-régression complète, jamais par une compilation. La nouvelle
directive la redit mot pour mot à la fin ; elle s'appliquait déjà.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases.
   `docs/providers/final-report.md`, ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases.
   `docs/canvas/final-report.md`, ADR-031.
4. **Research Orchestration Integration** — 18 phases.
   `docs/research/final-report.md`, ADR-032.

## Ce que les sondes ont déjà établi

**Call.md est une application Electron/TypeScript, et sa licence est déclarée
sans être déposée.**

| Lu | Valeur |
|---|---|
| `package.json` | `call-md` **1.0.4**, `"license": "MIT"` |
| Fichier `LICENSE` | **absent** — 404 sur cinq noms × deux branches |
| Pile | Electron 42, React 19, tRPC, Drizzle + SQLite, **`videodb`**, SDK MCP |
| Python | **aucun** |

Un champ de manifeste est une déclaration, pas une concession : consigné **MIT
`DECLARED`**, jamais `AUTHORITATIVE`.

**Call.md n'enregistre pas sous Linux** — sa propre table le dit : l'application
refuse d'enregistrer avant de démarrer, faute de binaire de capture. GalSen IA
tourne sous Linux.

**Cet environnement n'a aucune entrée live** : ni `/dev/snd`, ni `/dev/video*`,
`DISPLAY` vide, `ffmpeg` hors `PATH`. Les latences de capture et de
transcription rendront `NOT_MEASURED`, et la tranche de L05 devra le **rapporter**
plutôt que le simuler.

## La contrainte qui décide du programme

**Deux ADR acceptées tranchent déjà ce que §12 et §26 proposent d'évaluer.**

- **ADR-014** — la plateforme ne dépend d'aucun modèle externe à l'exécution.
- **ADR-018** — la dérogation est une configuration, jamais un paramètre de
  requête, et trois catégories sont refusées **quoi que dise la configuration** :
  mémoires/fichiers/connaissances de l'utilisateur, **captures d'écran**, export
  de données d'entraînement.

Or L01 a mesuré que **VideoDB porte la capture, la transcription et l'inférence**
dans Call.md. L'option A du §26 heurte donc ADR-014 et ADR-018 ; l'option B est
compatible. **C'est documenté, pas tranché** : amender une ADR appartient au
propriétaire.

## Ce qui ne doit pas être reconstruit

**Six des neuf items du §41 existent déjà** : transcription, mémoire,
orchestration MCP, boucle d'agent, base de données, moteur de résumé. Trois
manquent : diarisation, gestionnaire de contexte, et un bus d'événements dont
L04 décidera la nécessité.

Et **deux exigences présentées comme neuves sont déjà implémentées** :
`creative/language/switching.py` (alternance de langues, structurée et jamais
devinée) et `creative/voice/scene.py` (l'audio d'origine reste l'artefact
source). Le `NudgeEngine` du §20 serait `src/proactive/` écrit deux fois.
