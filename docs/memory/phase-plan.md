# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 21 terminé
**Phase courante** : —
**Terminées** : toutes (5 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 21 — Knowledge Engine (second manuel) : terminé
                                   → docs/architecture/knowledge.md
  La déduplication qu'il réclame était déjà acquise, structurellement :
  l'identifiant d'une connaissance est l'empreinte de son contenu. Rien
  n'a été ajouté — du code sans défaut dessous.
  Défaut trouvé : trois vues d'une même connaissance, deux réponses. Le cache
  gardait l'objet soumis sans vérifier que le magasin l'avait accepté, alors
  que `save()` refuse silencieusement une version pas plus récente.
  Second défaut, exposé par le test du premier : lire → corriger → enregistrer
  ne marchait pas en mémoire, `get()` rendant la référence interne. Les deux
  magasins divergeaient — même classe de bug qu'au VOLET 13.
```

**Restants** : 22 à 25 — soit 4 VOLETs, dont 1 porte un sujet déjà traité avec
un contenu différent (24). Le VOLET 01 n'a jamais eu de plan de phases formel.

**Prochaine action** : par ordre numérique, **VOLET 22 — Decision Engine**.
