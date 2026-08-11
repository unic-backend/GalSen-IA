# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-11

**En cours** : rien. **Vingt-trois VOLETs terminés** dans cette session : 01, 03, 05, 06,
07, 08, 09, 10, 11, 12, 13, 14, 15, 17, 18, 19, 20, 21, 22, 23, 24, 25. **Les 25 VOLETs
sont traités ; la série est close.**

**Terminé dans cette session**
- Un document mesuré par moteur dans `docs/architecture/` : knowledge, search, development,
  orchestration, memory, workflows, analytics, integration, security, communication,
  notifications, gateway, decisions, learning, enterprise, constitution.
  **ADR-011** (versionnement d'API).
- **Le motif dominant** : des règles déclarées que rien n'appliquait, et des capacités qui
  rapportaient un succès sans travail. Les plus graves, par ordre de gravité :
  **chaque moteur existait en deux exemplaires** (une alerte d'agent invisible sur
  `/notification/list`) ; `tester` consomme 96 % de chaque requête ; « envoyé » désignait
  des e-mails que personne n'a reçus ; douze échecs d'authentification ne déclenchaient
  aucun signal ; quatre routes rendaient l'hôte interne dans leur 500.
- **Trois fois** deux implémentations d'une même interface trouvées en désaccord :
  `save()` des notifications (13), `get()` des connaissances (21), le compteur d'accès (23).
- Tests : **2092 passants**, 7 ignorés (**398 ajoutés** dans la session).
- **P1 le plus haut retiré** : la décision du planificateur pilote le pipeline.
  « bonjour » passe de 45,2 s à 1,5 s ; la suite de tests de 183 s à 81 s.
  Branche `claude/galsen-ia-phases-ukwz7p`, tout est poussé.

**Prochaine étape**
Reprendre `docs/memory/pending-work.md`. Le P1 restant le plus haut est la **base de
connaissances vide** — il ne dépend pas du code. Les deux P0 dépendent de l'opérateur
(vérifier les identités, configurer un fournisseur de modèle).

**Bloqué / à surveiller**
- **`AgentRuntime` fait double emploi avec `RouterEngine`** et reste sans route : seul
  `RouterEngine` est exposé (`POST /workflow/run`). Quatrième duplication de la série,
  non traitée.
- **Recherche** : mémoire branchée comme deuxième source, poids arbitraires retirés.
  Restent document et vision sans fournisseur — leurs moteurs ne produisent pas encore de
  texte cherchable.
- **La base de connaissances est toujours vide** : P1, ne dépend plus du code.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **C4 dépend de toi** : rien n'est déployé ; aucun tag de version n'existe.
