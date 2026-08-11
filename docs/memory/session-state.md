# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-11

**En cours** : rien. **VOLETs 05, 14, 03 et 06 terminés** dans cette session.

**Terminé dans cette session**
- **VOLET 05** → `docs/architecture/knowledge.md` · **VOLET 14** → `search.md`
  **VOLET 03** → `development.md` · **VOLET 06** → `orchestration.md`
- **Une cible de performance existe** (`docs/standards/performance.md`), dérivée de
  mesures : le P1 le plus ancien est payé.
- **Sept défauts silencieux corrigés**, dont trois graves : l'aller-retour RAG qui
  détruisait une connaissance, `count()` et l'index plafonnés à 10 000 sans le dire, et
  **l'agent `tester` qui comptait comme réussies 72 suites qu'il n'exécutait pas**
  (`python <fichier>` ne joue que le bloc `__main__`). Corrigé puis **accéléré de
  97,4 s à 38,6 s** en un seul lot pytest.
- Tests : **1700 passants**, 7 ignorés (156 ajoutés dans la session).
  Branche `claude/galsen-ia-phases-ukwz7p`.

**Prochaine étape**
Ouvrir le **VOLET 07 — Memory Engine** (ordre numérique) et publier son plan de phases.
Restent ensuite : 08 à 13, 15, 17 à 25. Cadence : **jusqu'à 5 phases par tour**.

**Bloqué / à surveiller**
- **La base de connaissances est toujours vide** : P1 le plus haut, ne dépend plus du code.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **C4 dépend de toi** : rien n'est déployé ; aucun tag de version n'existe.
- L'orchestrateur ne lit pas la requête pour planifier, et `rollback` ne restaure rien.
