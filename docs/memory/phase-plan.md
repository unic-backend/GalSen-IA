# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**Travail en cours** : réconciliation des deux lignes de développement
**Phases** : 4
**Phase courante** : R.4 — en attente de confirmation
**Terminées** : R.1, R.2, R.3

```
R.1  Merge mécanique       ✅ 12 conflits résolus, src/frontend/ retiré, l'app démarre
R.2  Suite verte           ✅ 1376 passent, 5 ignorés (6 échecs corrigés)
R.3  Page Conseil Agricole ✅ portée dans src/web/, 18 tests, vérifiée au navigateur
R.4  Mémoire, ADR, PR      ⏳ trace de la réconciliation
```

**Dette de R.1 soldée** : `tests/test_dashboard_agri.py`, retiré avec
`src/frontend/`, est remplacé par `tests/test_web_agri.py` (18 tests).
