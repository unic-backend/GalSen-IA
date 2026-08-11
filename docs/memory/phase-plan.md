# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 15 — API Gateway
**Phases** : 12
**Phase courante** : 3.1 — en attente de confirmation
**Terminées** : 1.1, 2.1
**Cadence** : **une phase par tour** (demandée explicitement pour ce VOLET).

```
VOLET 15 — API Gateway
10 chapitres → 12 phases

Ch. 01  Vision                  → 1 phase   (1.1 ce qu'est réellement la passerelle)  ✔
Ch. 02  Architecture            → 1 phase   (2.1 les 7 composants, le flux de requête)  ✔
Ch. 03  Cycle de vie            → 1 phase   (3.1 les 9 étapes, une par une)
Ch. 04  Gestion                 → 2 phases  (4.1 versionnement, 4.2 retrait d'une API)
Ch. 05  Routage et trafic       → 2 phases  (5.1 limitation mesurée, 5.2 coupe-circuit et reprises)
Ch. 06  Supervision             → 1 phase   (6.1 métriques clés manquantes)
Ch. 07  Sécurité                → 1 phase   (7.1 indivisible — recoupe le VOLET 11)
Ch. 08  Gouvernance             → 1 phase   (8.1 indivisible)
Ch. 09  Qualité et optimisation → 1 phase   (9.1 indivisible)
Ch. 10  Gouvernance d'entreprise→ 1 phase   (10.1 indivisible — redit le ch. 08)

Total : 12 phases.
```

Phase 1.1 a livré `docs/architecture/gateway.md` (tête du document) et
`tests/test_gateway_surface.py` : 63 routes énumérées, 59 exigent une
authentification, 62 passent par le limiteur, 4 exceptions nommées et
verrouillées.

Phase 2.1 a verrouillé le flux de requête (`tests/test_gateway_request_flow.py`) :
en-têtes de sécurité présents sur une réponse d'erreur, statut réellement
renvoyé vu par les compteurs, et limiteur qui tranche **avant**
l'authentification (401, 401, puis 429).

**Restants après le 15** : 17 à 25 — soit 9 VOLETs, dont 5 portent un sujet déjà
traité avec un contenu différent (18, 19, 20, 21, 24). Le VOLET 01 n'a jamais eu
de plan de phases formel.
