# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 17 terminé
**Phase courante** : —
**Terminées** : toutes (8 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 17 — Notification Engine (second manuel) : terminé
                                   → docs/architecture/notifications.md
  `VOLET_17.md` est un second manuel Notification, pas le « Agent Framework »
  annoncé par le nom du dossier. Seul ce qu'il demande en plus du VOLET 13 a
  été traité.
  Gabarits de message : absents, maintenant un registre + send_from_template().
  Un paramètre manquant n'envoie rien — un message à trous a l'air d'une vraie
  alerte et ne dit rien. Registre livré vide.
  Analytique : les trois métriques du manuel (taux de livraison, latence de
  file, échecs) ne s'appliquent pas à une boîte interne et sont nommées ;
  ce qui est mesuré est ce qui arrive après — taux d'accusé de réception, âge
  de la plus vieille non lue, incidents les plus répétés.
  Reprises : rien à reprendre sans canal externe.
```

**Restants** : 18 à 25 — soit 8 VOLETs, dont 5 portent un sujet déjà traité avec
un contenu différent (18, 19, 20, 21, 24). Le VOLET 01 n'a jamais eu de plan de
phases formel.

**Prochaine action** : par ordre numérique, **VOLET 18 — Infrastructure & DevOps**.
