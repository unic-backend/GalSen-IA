# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — **VOLET 25 terminé, série close**
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **une phase par tour** (défaut).

```
VOLET 25 — Enterprise Governance & Global Architecture : terminé
                                   → docs/architecture/enterprise.md
  Défaut le plus grave de la série : **chaque moteur existait en deux
  exemplaires**. `server.py` construisait les siens, `EngineRegistry` ceux des
  agents — une alerte levée par un agent n'apparaissait pas sur la route que
  l'utilisateur consulte, et une mémoire écrite par l'API restait invisible aux
  agents. Invisible avec SQLite (fichier partagé), le défaut ne mordait que sur
  la configuration **par défaut**, celle que tout le monde lance en premier.
  Corrigé : l'API prend ses moteurs du registre partagé ; le secours reste
  possible mais il est journalisé.
```

**Restant** : le VOLET 01 (Master Constitution) n'a jamais eu de plan de phases
formel. C'est le seul reliquat de la série.

**Prochaine action** : proposer le VOLET 01, ou reprendre le backlog — les deux
P1 les plus hauts (`tester` dans le pipeline, base de connaissances vide) ne
dépendent plus du code.
