# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 14 — Search Engine
**Phases** : 12
**Phase courante** : 1.1 — en attente de confirmation
**Terminées** : aucune
**Cadence** : une phase par tour (défaut)

```
VOLET 14 — Search Engine
10 chapitres → 12 phases

Ch. 01  Vision         → 1 phase   1.1  inventaire mesuré : ce que la plateforme cherche déjà
Ch. 02  Architecture   → 2 phases  2.1  les 7 composants du manuel face au code réel
                                   2.2  flux en 6 étapes, de la collecte aux analytiques
Ch. 03  Cycle de vie   → 1 phase   3.1  les 9 étapes : lesquelles existent, laquelle manque
Ch. 04  Gestion        → 1 phase   4.1  enregistrement des sources et politiques d'indexation
Ch. 05  Indexation     → 2 phases  5.1  les 5 types d'index face à l'index par mots-clés
                                   5.2  intégrité et fraîcheur de l'index, mesurées
Ch. 06  Supervision    → 1 phase   6.1  métriques de recherche réellement observables
Ch. 07  Sécurité       → 1 phase   7.1  accès indexé : ce qui est cherché n'est pas ce qui est lu
Ch. 08  Gouvernance    → 1 phase   8.1  propriété des sources, journal des changements
Ch. 09  Qualité        → 1 phase   9.1  pertinence : ce qui se mesure sans jury humain
Ch. 10  Gouvernance moteur → 1 phase 10.1  clôture du VOLET, mémoire et CHANGELOG

Total : 12 phases.
```

**Pourquoi ce VOLET** : le VOLET 05 a laissé deux manques nommés au backlog qui
appartiennent tous deux à celui-ci — **la recherche sémantique n'existe pas** et
**rien n'analyse l'intention** ; le score de pertinence est un recouvrement de
termes. Deux implémentations coexistent déjà sans que rien ne dise laquelle
sert : `InMemoryKnowledgeIndexer` et `src/services/search/`.

**Garde-fou** : chaque phase part de l'état réel du dépôt, chaque chiffre est
mesuré et non rappelé. Une capacité inachevée rapporte un statut, jamais un
score plausible (`.claude/rules/verification.md`) — la pertinence est
précisément l'endroit où un chiffre inventé passe inaperçu.
