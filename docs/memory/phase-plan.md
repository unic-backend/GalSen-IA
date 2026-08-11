# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 13 terminé
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **une phase par tour** (défaut).

```
VOLET 13 — Notification Engine : terminé   → docs/architecture/notifications.md
  La même alerte cinq fois produisait cinq notifications : aucune prévention des
  doublons, alors que le chapitre 03 la range dans ses contrôles qualité.
  Regroupement d'une notification identique et non lue dans une fenêtre de 300 s
  (le même identifiant est retourné, `created_at` ne recule pas), et rétention
  des notifications lues au-delà de 90 jours — l'étape 9 du cycle n'existait pas.
  Un désaccord entre les deux magasins sur le sens de `save()` a été corrigé par
  un `update()` explicite, vérifié sur les deux backends.
  Absents : moteur de règles, connecteurs de canaux, file de livraison,
  préférences utilisateur.
```

**Restants** : 15, 17 à 25 — soit 10 VOLETs, dont 5 portent un sujet déjà traité
avec un contenu différent (18, 19, 20, 21, 24) et 17 qui recoupe 13 à 46 %. Le
VOLET 01 n'a jamais eu de plan de phases formel.

**Prochaine action** : par ordre numérique, **VOLET 15 — API Gateway Engine**.
