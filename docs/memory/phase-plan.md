# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 22 terminé
**Phase courante** : —
**Terminées** : toutes (5 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 22 — Decision Engine : terminé   → docs/architecture/decisions.md
  Sujet neuf : aucun moteur de décision n'existe, et aucun n'a été fabriqué.
  Onze composants et quatorze étapes : c'est un projet, pas une phase.
  Ce qui a été mesuré : la plateforme prend **une** décision — le planificateur
  déduit les agents nécessaires d'une demande — et elle est jetée. Sur
  « surveille les logs de production » : 3 agents recommandés, 9 exécutés.
  `decision_trace.py` enregistre l'écart avec un `applied: false` explicite.
  Suivre la recommandation changerait toutes les exécutions : c'est le P1 déjà
  inscrit après le VOLET 19, pas le travail d'une phase de mesure.
```

**Restants** : 23 à 25 — soit 3 VOLETs, dont 1 porte un sujet déjà traité avec un
contenu différent (24). Le VOLET 01 n'a jamais eu de plan de phases formel.

**Prochaine action** : par ordre numérique, **VOLET 23 — Learning Engine**.
