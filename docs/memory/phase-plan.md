# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 03 terminé (10 chapitres, 12 phases)
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **2 à 3 phases par tour**, demandé par l'utilisateur le 2026-08-10.
Revenir au défaut d'une phase par tour dès qu'il le dit.

```
VOLET 03 — Development Manual : terminé
  Ch. 01  standards     : 13 fichiers de règles, 4 mécanismes seulement s'exécutent
  Ch. 02  conventions   : 98 % docstrings, 88 % de types de retour, 100 % snake_case
  Ch. 03  structure     : 27 tests déplacés dans tests/, 20 chemins réparés
  Ch. 04  tests         : 4 niveaux sur 5 ; couverture réelle 81 %
  Ch. 05  déploiement   : validation des variables au démarrage ; retour arrière prouvé
  Ch. 06  version       : 73/100 commits conformes ; aucun tag
  Ch. 07  documentation : 6 paquets sur 18 ne documentaient rien
  Ch. 08  performance   : cibles déclarées et vérifiées — le P1 le plus ancien
  Ch. 09  maintenance   : registre de dette re-mesuré, 4 payées sur 9
  Ch. 10  cycle de dév. : clôture, mémoire et CHANGELOG
```

**Ce que le VOLET n'a pas fait, et le dit** : aucun linter ni vérificateur de
types n'a été ajouté (entré au backlog, P3 tant qu'il y a un contributeur) ;
aucun tag de version n'a été posé ; la latence de bout en bout n'est pas ciblée
tant que rien n'est déployé.

**Prochaine action** : choisir le prochain VOLET, lire ses chapitres, publier le
plan de phases, puis s'arrêter. Par ordre numérique, le suivant est le **VOLET
06 — AI Orchestration Manual**. Restent ensuite : 07 à 13, 15, 17 à 25.
