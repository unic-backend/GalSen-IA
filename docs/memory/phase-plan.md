# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 06 — AI Orchestration
**Phases** : 12
**Phase courante** : 5.1 — en attente de confirmation
**Terminées** : 1.1, 2.1, 2.2, 3.1, 4.1 (→ `docs/architecture/orchestration.md`)
**Cadence** : **jusqu'à 5 phases par tour**, demandé par l'utilisateur le 2026-08-11
(2 à 3 auparavant). Revenir au défaut d'une phase par tour dès qu'il le dit.

```
VOLET 06 — AI Orchestration
10 chapitres → 12 phases

Ch. 01  Vision            → 1 phase   1.1  ce que l'orchestrateur fait vraiment, mesuré
Ch. 02  Architecture      → 2 phases  2.1  les 7 composants du manuel face au code
                                      2.2  le flux en 8 étapes, de la requête au résultat
Ch. 03  Intention & plan  → 1 phase   3.1  détection d'intention : règles ou modèle ?
Ch. 04  Sélection d'agent → 1 phase   4.1  correspondance capacité/tâche, 10 agents déclarés
Ch. 05  Multi-agents      → 2 phases  5.1  ce que les agents se transmettent réellement
                                      5.2  exécution parallèle vs séquentielle, mesurée
Ch. 06  Exécution         → 1 phase   6.1  reprise sur échec et retour arrière
Ch. 07  Réponse           → 1 phase   7.1  agrégation et validation des sorties
Ch. 08  Supervision       → 1 phase   8.1  ce qu'on voit d'une exécution en cours
Ch. 09  Performance       → 1 phase   9.1  la suite d'orchestration à 105 s (dette P2)
Ch. 10  Gouvernance       → 1 phase  10.1  clôture du VOLET, mémoire et CHANGELOG

Total : 12 phases.
```

**Pourquoi ce VOLET** : l'ordre numérique. Il porte le cœur du produit — 10 agents
déclarés, 2 710 lignes dans `src/router/` et `src/agent/` — et une dette P2 mesurée
la veille : la suite d'orchestration prend **105 s**, dont trois tests à ~34 s
parce que l'agent `tester` lance de vraies suites à l'intérieur du pipeline.

**Deux garde-fous pour ce VOLET** :
1. **Ne pas exécuter le workflow `standard` dans les tests** — il contient l'agent
   `tester`, qui relancerait la suite à l'intérieur d'elle-même.
2. L'analyse d'intention est le point où l'invention est la plus tentante : si la
   détection est faite par règles, le dire, et ne jamais présenter un score de
   confiance qu'aucun modèle n'a produit (`.claude/rules/verification.md`).
