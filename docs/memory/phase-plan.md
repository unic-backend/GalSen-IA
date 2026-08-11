# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 12 terminé
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **une phase par tour** (défaut).

```
VOLET 12 — Communication Engine : terminé   → docs/architecture/communication.md
  « Envoyé » désignait des messages que personne n'a reçus : sans SMTP, l'envoi
  retournait un succès et le statut `sent`, sans contacter aucun serveur.
  Six tests verrouillaient ce mensonge — tous réécrits.
  Le message reste stocké, le statut devient `failed`, la route répond 503.
  Absents : gestionnaire de conversation, file de messages, accusé de réception.
```

**Restants** : 13, 15, 17 à 25 — soit 11 VOLETs, dont 5 portent un sujet déjà
traité avec un contenu différent (18, 19, 20, 21, 24) et 17 qui recoupe 13 à
46 %. Le VOLET 01 n'a jamais eu de plan de phases formel.

**Prochaine action** : par ordre numérique, **VOLET 13 — Notification Engine**.
