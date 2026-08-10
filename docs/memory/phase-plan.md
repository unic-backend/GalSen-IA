# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 03 — Development Manual
**Phases** : 12
**Phase courante** : 4.1 — en attente de confirmation
**Terminées** : 1.1, 2.1 (→ `docs/architecture/development.md`), 3.1 (27 tests déplacés
dans `tests/`, chemins corrigés, garde-fou `test_project_structure.py`)
**Cadence** : **2 à 3 phases par tour**, demandé par l'utilisateur le 2026-08-10.
Revenir au défaut d'une phase par tour dès qu'il le dit.

```
VOLET 03 — Development Manual
10 chapitres → 12 phases

Ch. 01  Standards de dév.  → 1 phase   1.1  ce que le dépôt impose vraiment vs ce qu'il déclare
Ch. 02  Conventions        → 1 phase   2.1  type hints, docstrings, commentaires FR : mesurés
Ch. 03  Structure projet   → 1 phase   3.1  les 27 `test_*.py` à la racine (P3 du backlog)
Ch. 04  Tests              → 2 phases  4.1  les 5 niveaux de test : lesquels existent
                                       4.2  couverture réelle, mesurée et non estimée
Ch. 05  Déploiement        → 2 phases  5.1  environnements et validation des variables au démarrage
                                       5.2  retour arrière : procédure et intégrité des données
Ch. 06  Contrôle de version→ 1 phase   6.1  stratégie de branches vs ce que fait le dépôt
Ch. 07  Documentation      → 1 phase   7.1  les 6 champs exigés par module : lesquels manquent
Ch. 08  Performance        → 1 phase   8.1  **déclarer une cible de performance** (P1 du backlog)
Ch. 09  Maintenance        → 1 phase   9.1  dette : registre existant vs dette réelle
Ch. 10  Cycle de dév.      → 1 phase  10.1  clôture du VOLET, mémoire et CHANGELOG

Total : 12 phases.
```

**Pourquoi ce VOLET** : l'ordre numérique, et il porte deux entrées du backlog —
**déclarer une cible de performance** (P1 : `/metrics` mesure la latence, rien ne
dit ce qui est acceptable, donc `release_check.py` refuse de cocher la case) et
les **27 fichiers de test à la racine** (P3).

**Risque propre à ce VOLET, à tenir** : c'est un volet de standards, et
`.claude/rules/` en couvre déjà une partie. Le piège est d'écrire dix documents
qui répètent des règles existantes. Chaque phase part donc du **dépôt mesuré**,
pas du manuel : ce qui est déjà écrit ailleurs est cité, jamais recopié
(`.claude/rules/documentation.md` : ne jamais dupliquer, mettre à jour l'existant).
