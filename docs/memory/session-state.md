# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-11

**En cours** : rien. **Dix-sept VOLETs terminés** dans cette session : 05, 14, 03, 06, 07, 08, 09, 10, 11, 12, 13, 15, 17, 18, 19, 20.

**Terminé dans cette session**
- Documents mesurés dans `docs/architecture/` : `knowledge.md`, `search.md`,
  `development.md`, `orchestration.md`, `memory.md`, `workflows.md`, `analytics.md`,
  `integration.md`, `security.md`, `communication.md`, `notifications.md`,
  `gateway.md`. **ADR-011** : pas de préfixe `/v1`, dépréciation par en-têtes RFC 8594.
- **Une cible de performance existe** (`docs/standards/performance.md`) : le P1 le
  plus ancien du backlog est payé.
- **Le motif dominant de la session** : des règles déclarées que rien n'appliquait, et
  des capacités qui rapportaient un succès sans travail. Les plus graves :
  l'agent `tester` comptait 72 suites qu'il n'exécutait pas ; `POST /search` répondait
  « aucun résultat » sans aucune source branchée ; « envoyé » désignait des e-mails que
  personne n'a reçus ; douze échecs d'authentification ne déclenchaient aucun signal ;
  un aller-retour RAG détruisait une connaissance ; quatre routes rendaient l'hôte
  interne et un chemin de fichier dans leur 500.
- Tests : **1982 passants**, 7 ignorés (**288 ajoutés** dans la session).
  Branche `claude/galsen-ia-phases-ukwz7p`, tout est poussé.

**Prochaine étape**
Ouvrir le **VOLET 21** et publier son plan de phases.
Restent ensuite : 22 à 25. **Cadence revenue à une phase par tour.**
Attention : les noms de dossier des VOLETs 17 et 18 ne correspondaient pas à
leur contenu — vérifier le titre dans le fichier avant de planifier.

**Bloqué / à surveiller**
- **`tester` coûte 96 % de chaque requête** (43,5 s sur 45,2 s) : nouveau P1, c'est une
  décision sur le pipeline, mesure faite.
- **La base de connaissances est toujours vide** : P1, ne dépend plus du code.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **C4 dépend de toi** : rien n'est déployé ; aucun tag de version n'existe.
