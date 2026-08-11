# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 19 terminé
**Phase courante** : —
**Terminées** : toutes (6 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 19 — AI Agent Orchestration : terminé
                                   → docs/architecture/orchestration.md
  Troisième manuel sur ce sous-système, après les VOLETs 06 et 08/18.
  Défaut central mesuré : sur le pipeline livré, l'agent `tester` consomme
  43,5 s d'une requête de 45,2 s — 96 % — parce qu'il exécute toute la suite
  pytest avant que la plateforme réponde, à chaque requête. « bonjour » coûte
  45 secondes. Rien ne mesurait la durée par agent : le coût était invisible.
  La durée de chaque agent est désormais enregistrée et ventilée (`agent_time`).
  Le correctif est une décision sur le pipeline, pas une mesure → P1 du backlog.
  Aucun délai d'attente inventé : Python ne peut pas tuer un fil, un
  `future.result(timeout=…)` libérerait l'appelant pendant que l'agent continue.
  Absents et assumés : bus de communication, ordonnanceur, gestionnaire de
  ressources.
```

**Restants** : 20 à 25 — soit 6 VOLETs, dont 3 portent un sujet déjà traité avec
un contenu différent (20, 21, 24). Le VOLET 01 n'a jamais eu de plan de phases
formel.

**Prochaine action** : par ordre numérique, **VOLET 20** — vérifier son titre
réel dans le fichier avant de planifier.
