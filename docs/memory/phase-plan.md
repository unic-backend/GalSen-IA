# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 09 terminé
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **une phase par tour** (défaut). Les autorisations d'enchaînement
données le 2026-08-11 (VOLETs 07, 08 puis 09) sont consommées.

```
VOLET 09 — Analytics Engine : terminé       → docs/architecture/analytics.md
  Il n'existait aucun moteur analytique : de la collecte sans agrégation.
  4 composants sur 7 existent désormais, bâtis comme une couche d'agrégation
  au-dessus de l'audit, de l'historique des workflows et de /metrics — jamais
  comme un second collecteur.
  Ajouté : `src/analytics/` et `GET /analytics`.
  Déclaré absent avec sa raison : tendances, détection d'anomalies, tableaux de
  bord — aucune série temporelle ne survit à un redémarrage (ADR-009).
```

**Ce qui rendrait l'analytique réelle** : la rétention des données analytiques.
C'est une décision de stockage (un ADR), à prendre **après** le critère C4 —
avant un déploiement, il n'y a pas d'historique d'exploitation qui vaille d'être
conservé. Entré au backlog.

**Prochaine action** : choisir le prochain VOLET, publier son plan de phases,
puis s'arrêter. Par ordre numérique : **VOLET 10 — Integration Engine**.
Restent ensuite : 11 à 13, 15, 17 à 25.
