# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 05 — Knowledge Engine
**Phases** : 12
**Phase courante** : 8.1 — en attente de confirmation
**Terminées** : 1.1 (→ `docs/architecture/knowledge.md`), 2.1 (`KnowledgeDomain`),
2.2 (`KnowledgeSensitivity`, `KnowledgeStatus`), 3.1 (`knowledge_lifecycle.py`, `set_status`),
4.1 (revalidation périodique), 5.1 (filtrage par politique à la récupération), 5.2 (cache de requêtes, mesuré), 6.1 (propriétaires de domaine, rapport de gouvernance),
7.1 (lecture par rôle selon la sensibilité)
**Cadence** : une phase par tour (défaut)

```
VOLET 05 — Knowledge Engine
10 chapitres → 12 phases

Ch. 01  Vision            → 1 phase   1.1  inventaire mesuré du moteur face à la vision
Ch. 02  Organisation      → 2 phases  2.1  structure (domaines → versions) vs `types.py`
                                      2.2  classification (source, fiabilité, sensibilité, statut)
Ch. 03  Cycle de vie      → 1 phase   3.1  les 8 étapes : lesquelles existent, laquelle manque
Ch. 04  Validation        → 1 phase   4.1  niveaux Draft → Deprecated vs `knowledge_validator.py`
Ch. 05  Récupération      → 2 phases  5.1  pipeline en 6 étapes (intention, index, filtre)
                                      5.2  classement et cache, mesurés et non supposés
Ch. 06  Gouvernance       → 1 phase   6.1  propriétaire par domaine, rôles = mécanismes
Ch. 07  Sécurité          → 1 phase   7.1  permissions et sensibilité à la lecture
Ch. 08  Intégration       → 1 phase   8.1  qui consomme réellement le moteur (RAG, search, mémoire)
Ch. 09  Qualité           → 1 phase   9.1  métriques de qualité réellement calculables
Ch. 10  Gouvernance moteur→ 1 phase  10.1  clôture du VOLET, mémoire et CHANGELOG

Total : 12 phases.
```

**Pourquoi ce VOLET** : le P1 le plus haut de `pending-work.md` — la base de
connaissances contient 0 élément, 0 document indexé, 0 nœud de graphe, et
`docs/knowledge/` n'existe pas. Le moteur (12 modules, 2372 lignes) et la
recherche récupèrent dans le vide.

**Garde-fou** : chaque phase part de l'état réel du dépôt, chaque chiffre est
mesuré et non rappelé. Une capacité inachevée rapporte un statut, jamais une
réponse plausible (`.claude/rules/verification.md`).
