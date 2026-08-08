# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**Travail en cours** : réconciliation des deux lignes de développement
**Phases** : 4
**Phase courante** : R.3 — en attente de confirmation
**Terminées** : R.1, R.2

```
R.1  Merge mécanique       ✅ 12 conflits résolus, src/frontend/ retiré, l'app démarre
R.2  Suite verte           ✅ 1376 passent, 5 ignorés (6 échecs corrigés)
R.3  Page Conseil Agricole ⏳ portée dans src/web/ (ADR-008) + ses tests
R.4  Mémoire, ADR, PR         trace de la réconciliation
```

**Note pour R.3** : `tests/test_dashboard_agri.py` a été retiré avec
`src/frontend/`. La page portée dans `src/web/` doit retrouver une couverture
équivalente — sinon la décision aura coûté des tests sans les remplacer.
