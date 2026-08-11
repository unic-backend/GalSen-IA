# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLETs 07 et 08 terminés
**Phase courante** : —
**Terminées** : toutes
**Cadence** : retour au **défaut d'une phase par tour**. L'autorisation de deux
VOLETs d'affilée en autonomie (2026-08-11, utilisateur endormi) est **consommée**.

```
VOLET 07 — Memory Engine : terminé          → docs/architecture/memory.md
  Quatre règles déclarées que rien n'appliquait : « oublier » supprimait,
  l'archivage n'aurait rien changé, l'expiration attendait un nettoyage manuel,
  et le nettoyage comptait des suppressions que le cache annulait.
  `consolidate_memory()` retournait 0 : elle lève désormais NotImplementedError.
  Ajouté : `quality_report()` et `list_inactive()`.

VOLET 08 — Workflow Engine : terminé        → docs/architecture/workflows.md
  Rien ne validait un workflow : agent inexistant accepté, workflow vide
  rapportant `success`. Trois déclarations ne configuraient rien, dont la
  configuration d'échec lue dans un fichier où elle n'existait pas.
  Ajouté : `workflow_validator.py` et `WorkflowHistory` (taux de succès).
```

**Ce que ces deux VOLETs n'ont pas fait, et le disent** : la consolidation de
mémoire (aucune règle n'existe pour ce qui passe du court au long terme), le
gestionnaire d'état et le répartiteur d'événements du chapitre 02 du VOLET 08,
et la précision de récupération (aucun jeu de référence).

**Prochaine action** : choisir le prochain VOLET, publier son plan de phases,
puis s'arrêter. Par ordre numérique : **VOLET 09 — Analytics Engine**.
Restent ensuite : 10 à 13, 15, 17 à 25.
