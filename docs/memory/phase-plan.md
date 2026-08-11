# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : aucun — VOLET 23 terminé
**Phase courante** : —
**Terminées** : toutes (5 phases)
**Cadence** : **une phase par tour** (défaut).

```
VOLET 23 — Learning Engine : terminé   → docs/architecture/learning.md
  Sujet neuf : aucun moteur d'apprentissage n'existe, aucun n'a été fabriqué.
  L'étape 6 est l'entraînement de modèle et le critère C1 n'est pas atteint.
  La plateforme recueille **un** signal d'usage — le compteur de consultations
  d'une connaissance, qui alimente le critère `popularity` du classement — et
  il ne fonctionnait pas : `update()` refusait l'écriture faute de version
  avancée. Jamais sur SQLite ; en mémoire il ne survivait que par aliasing,
  **que mon correctif du VOLET 21 a supprimé** — régression que j'ai
  introduite et corrigée ici.
  `record_access()` écrit le compteur sans toucher à la version. Les deux
  magasins concordent enfin — troisième divergence de ce type de la série.
```

**Restants** : 24 et 25. Le VOLET 01 n'a jamais eu de plan de phases formel.

**Prochaine action** : **VOLET 24** — vérifier son titre réel dans le fichier.
