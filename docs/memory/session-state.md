# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-10

**En cours** : rien. **VOLETs 05, 14 et 03 terminés** dans cette session.

**Terminé dans cette session**
- **VOLET 05 — Knowledge Engine** → `docs/architecture/knowledge.md`
- **VOLET 14 — Search Engine** → `docs/architecture/search.md`
- **VOLET 03 — Development Manual** → `docs/architecture/development.md`
- **Une cible de performance existe enfin** (`docs/standards/performance.md`), dérivée de
  mesures : le P1 le plus ancien du backlog est payé, et `release_check.py` ne laisse
  plus ce point à un humain.
- **Cinq défauts silencieux corrigés** : aller-retour RAG qui détruisait une connaissance,
  `count()` plafonné à 10 000, index tronqué à 10 000, `/search` qui répondait « aucun
  résultat » sans aucune source branchée, `GALSEN_STORAGE_BACKEND` mal écrit qui repartait
  en mémoire sans le dire.
- Tests : **1687 passants**, 7 ignorés (143 ajoutés dans la session), couverture 81 %.
  Branche `claude/galsen-ia-phases-ukwz7p`.

**Prochaine étape**
Ouvrir le **VOLET 06 — AI Orchestration** (ordre numérique) et publier son plan de
phases. Restent ensuite : 07 à 13, 15, 17 à 25. Cadence : **2 à 3 phases par tour**.

**Bloqué / à surveiller**
- **La base de connaissances est toujours vide** : P1 le plus haut, ne dépend plus du code.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **C4 dépend de toi** : rien n'est déployé ; aucun tag de version n'existe.
- Recherche sémantique absente ; aucun linter ni vérificateur de types.
