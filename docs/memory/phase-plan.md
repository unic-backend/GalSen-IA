# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 18 terminé
**Phase courante** : —
**Terminées** : toutes (7 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 18 — Workflow Engine (second manuel) : terminé
                                   → docs/architecture/workflows.md
  `VOLET_18.md` est un second manuel Workflow, pas l'« Infrastructure & DevOps »
  annoncé par le nom du dossier. Seul ce qu'il demande en plus du VOLET 08 a été
  traité.
  Défaut central : chaque workflow déclarait une version que rien ne lisait, si
  bien que deux définitions se confondaient dans le même taux d'échec. La
  version est désormais enregistrée à chaque exécution et le rapport la ventile.
  L'analyse des défaillances nomme l'agent en cause au lieu de le compter.
  Absents et assumés : ordonnanceur, bus d'événements, dépôt de définitions,
  file d'attente, et les instances de gouvernance que le projet n'a pas.
```

**Restants** : 19 à 25 — soit 7 VOLETs, dont 4 portent un sujet déjà traité avec
un contenu différent (19, 20, 21, 24). Le VOLET 01 n'a jamais eu de plan de
phases formel.

**Prochaine action** : par ordre numérique, **VOLET 19**.
