# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 20 terminé
**Phase courante** : —
**Terminées** : toutes (5 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 20 — Memory Engine (second manuel) : terminé
                                   → docs/architecture/memory.md
  Le fichier n'a pas de chapitre 02 : il enchaîne 01, 01, puis 03. L'inventaire
  des composants du VOLET 07 tient, rien n'a été inventé pour combler le trou.
  Défaut central : les doublons étaient détectés et rien ne pouvait les
  retirer — trois enregistrements du même contenu donnaient trois mémoires et
  la recherche rendait les trois. `deduplicate()` garde la plus ancienne et
  archive les autres, avec un essai à blanc.
  Second défaut trouvé en construisant : `quality_report()` comptait les
  doublons tous statuts confondus, donc il en annonçait encore après
  déduplication. Il ne compte plus que les actives — le rapport et l'action
  doivent parler du même ensemble.
```

**Restants** : 21 à 25 — soit 5 VOLETs, dont 2 portent un sujet déjà traité avec
un contenu différent (21, 24). Le VOLET 01 n'a jamais eu de plan de phases
formel.

**Prochaine action** : par ordre numérique, **VOLET 21** — vérifier son titre
réel dans le fichier avant de planifier.
