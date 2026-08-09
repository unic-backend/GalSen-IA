# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : 04 — Roadmap
**Phases** : 13
**Phase courante** : 9.1 et 9.2 — en attente de confirmation
**Terminées** : 1.1, 2.1, 2.2, 3.1, 3.2, 4.1, 5.1, 6.1, 7.1, 8.1
**Cadence** : 2 phases par tour (demandé par l'utilisateur ; le défaut de
`.claude/rules/phase-protocol.md` reste une phase)

```
Ch. 01  Product Vision          → 1 phase
  1.1  ✅ vision.md réconciliée — et corrigée : elle annonçait encore « no application code yet »

Ch. 02  Development Phases      → 2 phases
  2.1  ✅ roadmap.md réécrite sur les 4 macro-phases — Phase 2 au tiers, 3 items de Phase 3 déjà faits
  2.2  ✅ 6 critères de sortie vérifiables — C6 tenu, C1 à C5 ouverts

Ch. 03  Milestones & Releases   → 2 phases
  3.1  ✅ src/version.py source unique, type « prototype », garde-fou anti-divergence
  3.2  ✅ scripts/release_check.py — 8 contrôles exécutables, 2 points laissés à l'humain

Ch. 04  Feature Prioritization  → 1 phase (indivisible)
  4.1  ✅ backlog rangé P0–P3, chaque entrée nomme le critère qui l'a décidée

Ch. 05  Strategic Objectives    → 1 phase (indivisible)
  5.1  ✅ 6 piliers confrontés au réel — base de connaissances vide, 2 objectifs sur 5 impossibles

Ch. 06  Innovation Roadmap      → 1 phase (indivisible)
  6.1  ✅ mode d'échec nommé (fabrication, 4 cas), 3 conditions d'entrée, étape « pilote » manquante

Ch. 07  Global Expansion        → 1 phase (indivisible)
  7.1  ✅ expansion : 2 propriétés déjà acquises ; 2 numérotations contradictoires découvertes

Ch. 08  Long-Term Sustainability → 1 phase (indivisible)
  8.1  ✅ registre de 9 dettes mesurées, chacune avec son déclencheur

Ch. 09  Success Metrics & KPIs  → 2 phases
  9.1  ⏳ Choisir les métriques mesurables aujourd'hui, écarter les autres
  9.2  Les rendre mesurables : un script ou une route qui les rapporte

Ch. 10  Roadmap Governance      → 1 phase (indivisible)
  10.1 Qui décide, comment une révision est enregistrée
```

**Total : 13 phases.** Ce VOLET ne produit du code qu'en 9.2. Partout ailleurs,
la sortie est un document — le seul garde-fou contre les généralités est que
chaque phase parte de l'état réel du dépôt et non du texte du manuel.

**Prochaine action** : exécuter les phases 9.1 et 9.2, puis s'arrêter.
