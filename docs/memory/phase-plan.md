# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 11 terminé
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **une phase par tour** (défaut).

```
VOLET 11 — Security Engine : terminé        → docs/architecture/security.md
  Compter n'est pas détecter : 12 échecs avec 12 clés différentes ne levaient
  aucun signal. Ajouté : fenêtre glissante d'échecs par source, sévérité,
  `GET /security/threats`. Méthodes non fournies nommées dans la réponse.
  Un contournement trouvé et corrigé en construisant : un succès effaçait les
  échecs de la source — l'attaquant effaçait sa trace, l'opérateur effaçait ce
  qu'il observait.
  Confinement et reprise (ch. 06) absents et non simulés : bloquer une adresse
  demande un ADR.
```

**Restants** : 12, 13, 15, 17 à 25 — soit 12 VOLETs, dont 5 portent un sujet
déjà traité avec un contenu différent (18, 19, 20, 21, 24) et 17 qui recoupe 13
à 46 %. Le VOLET 01 (Master Constitution) n'a jamais eu de plan de phases formel.

**Prochaine action** : choisir le prochain VOLET, publier son plan de phases,
puis s'arrêter. Par ordre numérique : **VOLET 12 — Communication Engine**.
