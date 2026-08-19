# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **aucun**
Dernier terminé  : **LIVE CONTEXT ENGINE / CALL.MD INTEGRATION** — 27 phases,
                   **ADR-033**. Rapport → `docs/live-context/final-report.md`
Phase courante   : **aucune** — le programme est fini, il reste à ouvrir la PR
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente en vigueur depuis le 2026-08-19** :
`.claude/rules/post-integration-validation.md` — toute phase se termine par une
validation de non-régression complète, jamais par une compilation. Quatorze
régressions complètes ont tourné pendant ce programme, toutes `PASS` avec le
même échec unique (`v0.1.0`).

---

## Programmes précédents, terminés — ne pas rouvrir

1. **Universal Creative Intelligence** — 44 phases. `docs/creative/final-report.md`
2. **Master Update Directive V4 (MoneyPrinterTurbo)** — 15 phases.
   `docs/providers/final-report.md`, ADR-030.
3. **Creative Canvas & Cinema Orchestration** — 17 phases.
   `docs/canvas/final-report.md`, ADR-031.
4. **Research Orchestration Integration** — 18 phases.
   `docs/research/final-report.md`, ADR-032.
5. **Live Context Engine / Call.md** — 27 phases.
   `docs/live-context/final-report.md`, ADR-033.

## Ce que ce dernier programme a mesuré, et qu'il ne faut pas re-déduire

**L'état de la chaîne live est calculé par `readiness()`**, jamais écrit :
`REPRESENTATION READY — NO LIVE PERCEPTION ON THIS MACHINE, 5 STAGE(S) NOT
IMPLEMENTED, 2 BLOCKED`. Neuf étapes `READY`, deux `BLOCKED`, cinq `ABSENT`, et
la coupure est totale : **toutes** les étapes de représentation tournent,
**aucune** étape de perception.

**La diarisation est `ABSENT` et non `BLOCKED`** : installer `pyannote`
fournirait la capacité et laisserait toujours rien pour l'appeler. La ranger
sous `BLOCKED` enverrait un opérateur chercher un paquet qui n'a jamais été le
problème.

**Call.md n'enregistre pas sous Linux** — sa propre table le dit — et **VideoDB
y porte la capture, la transcription et l'inférence**. Son « Local-First »
couvre le **stockage**, pas le traitement. L'option A du §26 heurtait donc
ADR-014 et ADR-018 avant même d'être évaluée ; **aucune ADR n'a été amendée**.

**Six des neuf items « ne pas dupliquer » du §41 existaient déjà**, et le
`NudgeEngine` du §20 est `src/proactive/` : sa suppression des répétitions par
empreinte des preuves est plus précise qu'un minuteur de deux minutes, parce
qu'une suggestion revient quand la situation a changé et non quand le temps a
passé.

**La licence n'était pas l'obstacle** : 48 MIT sur 54 paquets, l'arbre le plus
propre des cinq dépôts audités en quatre programmes. Ce qui bloque est
l'architecture, la plateforme et la souveraineté. À noter tout de même :
`package.json` déclare MIT et **aucun fichier `LICENSE` n'existe** — consigné
`MIT DECLARED`, jamais `AUTHORITATIVE`.
