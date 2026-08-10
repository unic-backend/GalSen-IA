# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 14 terminé (10 chapitres, 12 phases)
**Phase courante** : —
**Terminées** : toutes
**Cadence** : **2 à 3 phases par tour**, demandé par l'utilisateur le 2026-08-10.
Revenir au défaut d'une phase par tour dès qu'il le dit.

```
VOLET 14 — Search Engine : terminé
  Ch. 01  vision       : 3 mécanismes de recherche qui s'ignorent, 2 capacités sur 6
  Ch. 02  architecture : `/search` ne pouvait rien rendre — 503 puis branchement réel
  Ch. 03  cycle de vie : 6 étapes sur 9 ; suppression non « sécurisée », dit comme tel
  Ch. 04  gestion      : `KnowledgeSearchProvider`, rôle propagé jusqu'aux fournisseurs
  Ch. 05  indexation   : 1 type d'index sur 5 ; `check_integrity()` ; 2 troncatures muettes
  Ch. 06  supervision  : analytique de recherche dans `/metrics`, sans le contenu des requêtes
  Ch. 07  sécurité     : l'index contient tout, le filtrage tient sur chaque sortie
  Ch. 08  gouvernance  : sources déclarées vs branchées, responsable par source
  Ch. 09  qualité      : taux de vides et intégrité ; précision et rappel non mesurables
  Ch. 10  gouvernance moteur : `GET /search/status`
```

**Ce que le VOLET n'a pas fait, et le dit** : sémantique et vectoriel absents
(`EmbeddingsTool` produit des vecteurs que rien n'indexe), pas d'analyse
d'intention, pas de gestion des accents ni de racinisation, 3 sources sur 4 sans
fournisseur, aucune reconstruction d'index planifiée. Aucun de ces manques n'a
reçu de valeur de remplacement.

**Prochaine action** : choisir le prochain VOLET, lire ses chapitres, publier le
plan de phases, puis s'arrêter. Restent ouverts : VOLET 03, 06 à 13, 15, 17 à 25.
