# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 18 — Workflow Engine (second manuel)
**Phases** : 7
**Phase courante** : 2.1 — en attente de confirmation
**Terminées** : 1.1
**Cadence** : **une phase par tour** (défaut).

```
VOLET 18 — Workflow Engine (second manuel, distinct du VOLET 08)
10 chapitres → 7 phases

Ch. 01  Vision                  → 1 phase   (1.1 ce que ce manuel demande en plus du 08)  ✔
Ch. 02  Architecture            → 1 phase   (2.1 les 7 composants du chapitre)
Ch. 03  Cycle de vie            → 2 phases  (3.1 gestion des versions, 3.2 retrait et archivage)
Ch. 04  Gestion + Ch. 06 Supervision → 1 phase (4.1 métriques réelles d'exécution)
Ch. 05  Sécurité + Ch. 07 Conformité → 1 phase (5.1 recoupe VOLET 11 et 08)
Ch. 08  Gouvernance + Ch. 09/10       → 1 phase (8.1 indivisible)

Total : 7 phases.
```

Le fichier `VOLET_18.md` est un **second manuel Workflow**, pas
l'« Infrastructure & DevOps » annoncé par le nom du dossier. Comme pour le
VOLET 17, seul ce qu'il demande en plus est traité.

Phase 1.1 a mesuré le défaut central : chaque workflow **déclare** une version
(`workflows.yaml`), le validateur exige qu'elle soit présente, et **rien ne la
lit**. L'historique d'exécution enregistre l'identifiant du workflow mais pas la
version qui a tourné — deux définitions différentes se confondent dans le même
taux d'échec.

**Restants après le 18** : 19 à 25 — soit 7 VOLETs, dont 4 portent un sujet déjà
traité avec un contenu différent (19, 20, 21, 24). Le VOLET 01 n'a jamais eu de
plan de phases formel.
