# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-12

**En cours** : rien. Le backlog est la file de travail courante (les VOLETs 26–33 sont
clos). Prochain P2 à prendre : **valider les sorties d'agents**.

**Terminé dans cette session**
- **VOLETs 26 à 33** : souveraineté des modèles (ADR-014, SamP/ToP), embeddings et
  recherche sémantique (ADR-015), ingestion documentaire, agent de code sous portillon
  d'approbation (`src/agent/guarded_editor.py`), infrastructure d'entraînement
  (`src/training/` — capture consentie, barème, lignée).
- **Backlog** : les huit dépendances optionnelles tranchées une par une (`scipy` retiré,
  `docker` désactivé pour raison de sécurité, six déclarées) ; le chemin de lecture de la
  base de connaissances ne réécrit plus à chaque recherche ; la mesure ne dérive plus.
- **P2 — l'audit et les approbations persistent** : `src/storage/sqlite_audit_store.py`,
  `src/storage/sqlite_approval_store.py`, choisis par `GALSEN_STORAGE_BACKEND=sqlite`.
- Suite complète : **2339 tests passent**, 7 ignorés.

**Prochaine étape**
P2 « valider les sorties d'agents » : aucun schéma ne se tient entre le dictionnaire d'un
agent et la réponse agrégée, et un pipeline vide rend `success` sans avoir rien exécuté.

**Bloqué / à surveiller**
- **`git push origin v0.1.0`** : le proxy git de l'environnement refuse les étiquettes
  (403). L'étiquette existe localement sur `383fcf7` ; à pousser depuis un clone normal.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **La base de connaissances n'a que le corpus du dépôt** (250 passages de documentation).
  Le corpus sénégalais demande de vrais documents déclarés — il ne s'invente pas.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
