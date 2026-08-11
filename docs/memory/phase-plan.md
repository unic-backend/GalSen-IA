# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 07 — Memory Engine
**Phases** : 12
**Phase courante** : 5.1
**Terminées** : 1.1, 2.1, 2.2, 3.1, 4.1
**Cadence** : **deux VOLETs d'affilée en autonomie** (07 puis 08), autorisés
explicitement par l'utilisateur le 2026-08-11 : il dort, ne sera pas réveillé, et
m'a donné son feu vert pour décider seul. Retour au défaut d'une phase par tour
dès qu'il le redemande.

```
VOLET 07 — Memory Engine
10 chapitres → 12 phases

Ch. 01  Vision           → 1 phase   1.1  état mesuré du moteur
Ch. 02  Architecture     → 2 phases  2.1  les 7 composants ; 2.2  le flux en 7 étapes
Ch. 03  Cycle de vie     → 1 phase   3.1  les 8 étapes : archivage et expiration
Ch. 04  Classification   → 1 phase   4.1  types, priorités, statuts réellement utilisés
Ch. 05  Récupération     → 2 phases  5.1  pipeline ; 5.2  pertinence et cache mesurés
Ch. 06  Synchronisation  → 1 phase   6.1  ce qui est partagé entre services
Ch. 07  Sécurité         → 1 phase   7.1  isolation par utilisateur, vie privée
Ch. 08  Gouvernance      → 1 phase   8.1  rétention, propriété des mémoires
Ch. 09  Qualité          → 1 phase   9.1  métriques réellement calculables
Ch. 10  Gouvernance moteur → 1 phase 10.1 clôture, mémoire et CHANGELOG

Total : 12 phases.
```

**Puis VOLET 08 — Workflow Engine**, même méthode.
