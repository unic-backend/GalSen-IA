# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 16 — Authentication & Identity Engine
**Phases** : 12
**Phase courante** : 3.1 — en cours
**Terminées** : 1.1, 2.1, 2.2
**Cadence** : VOLET entier demandé par l'utilisateur

```
Ch. 01  Vision           → 1 phase
  1.1  ✅ 5 composants sur 7 existaient déjà ; seul l'annuaire manquait

Ch. 02  Architecture     → 2 phases
  2.1  ✅ tableau composant → code réel
  2.2  ✅ ADR-010 acceptée : une clé appartient à un sujet, sans magasin de secrets

Ch. 03  Lifecycle        → 2 phases
  3.1  Enregistrement et stockage d'une identité
  3.2  Suspension, révocation, retrait — en réutilisant la révocation existante

Ch. 04  Management       → 1 phase (indivisible)
  4.1  Les routes : créer, lister, modifier une identité

Ch. 05  Security         → 1 phase (indivisible)
  5.1  Comment une identité prouve qui elle est, sans secret stocké en clair

Ch. 06  Monitoring       → 1 phase (indivisible)
  6.1  Les événements d'authentification dans le moteur d'audit et /metrics

Ch. 07  Compliance       → 1 phase (indivisible)
  7.1  Quelles données personnelles sont détenues, combien de temps, pourquoi

Ch. 08  Governance       → 1 phase (indivisible)
  8.1  Qui crée et retire une identité

Ch. 09  Quality          → 1 phase (indivisible)
  9.1  Ce qui est mesuré sur l'authentification

Ch. 10  Governance (bis) → 1 phase (indivisible)
  10.1 Le chapitre 10 porte le même titre que le 08 — à lire avant de décider
       s'il ajoute quelque chose ou s'il faut le signaler comme doublon
```

**Total : 12 phases.**

**Ce VOLET n'est pas une construction à partir de rien.** La plateforme a déjà la
moitié de ce chapitre : clés API hachées, 4 rôles, permissions, révocation,
rotation à chaud, `hmac.compare_digest`. Ce qui manque est l'**identité** — une
clé désigne un rôle, pas une personne. Le plan sert autant à éviter de
reconstruire ce que `src/api/rbac.py` et l'ADR-004 font déjà qu'à ajouter ce qui
manque.

**Les phases 3.1 et suivantes dépendent de l'ADR-010 (phase 2.2).** Elles seront
re-découpées si la décision les invalide — annoncer aujourd'hui le détail d'une
implémentation dont la forme n'est pas décidée serait une prévision, pas un plan.

**Prochaine action** : exécuter la phase 1.1, puis s'arrêter.
