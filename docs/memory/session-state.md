# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-08

**En cours** : réconciliation des deux branches — phase R.1 terminée, R.2 à faire.

**Terminé dans cette session**
- **VOLET 02 clos** (10/10) : ADR-008 (tableau de bord `/ui` sans build) et
  ADR-009 (une seule instance, dite à l'exécution via `/health`).
- **Protocole de phases** installé : une phase par tour, plan avant chaque VOLET
  (`.claude/rules/phase-protocol.md`, chargé au démarrage).
- **Merge de `feature/service-unit-tests`** : 12 conflits résolus. Arrivent les
  services calendar/cloud/email, 5 stores SQLite de service, le SDK client,
  `POST /agri/advice` et le serveur local Ollama (`serveur_cerveau.py`).
- **Décision** : `src/frontend/` (Jinja2) est abandonné, `/ui` (ADR-008) reste.
  La page « Conseil Agricole » sera portée dans `src/web/`.

**Prochaine étape**
Phase R.2 : faire passer la suite complète après le merge — les tests des deux
côtés n'ont jamais tourné ensemble. Puis R.3 (page agricole), R.4 (mémoire, PR).

**Bloqué / à surveiller**
- `tests/test_agri_advice.py` attend peut-être des exceptions là où l'outil
  retourne un statut : c'est la version « statut » qui a été gardée.
- Perdre `GALSEN_ENCRYPTION_KEY` = perdre les données chiffrées, sans recours.
