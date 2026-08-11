# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — **les 25 VOLETs sont traités**
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **une phase par tour** (défaut).

```
VOLET 01 — Master Constitution : terminé   → docs/architecture/constitution.md
  Le seul VOLET qui n'avait jamais eu de plan de phases, et celui dont le
  reste de la série était l'audit sans le dire.
  Mesuré : le portillon d'approbation humaine existe (ADR-006) et **aucun agent
  ne l'active** — ce qui est aujourd'hui correct, les neuf agents ne faisant
  que lire. Ce qui manquait, c'est ce qui maintient cet état :
  `approval_required` vaut `False` par défaut, donc le premier agent qui
  écrira le fera sans portillon. Un test rend la règle finale du chapitre 03
  exécutable, et un second verrouille la mesure pour qu'elle ne passe pas au
  vert pour une mauvaise raison.
```

**Restant** : plus aucun manuel. Le travail revient au backlog
(`docs/memory/pending-work.md`), dont les deux P1 les plus hauts ne dépendent
plus du code : `tester` dans le pipeline, et la base de connaissances vide.
