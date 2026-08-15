# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-15

**En cours** : **programme d'expansion VOLETs 37→76** (directive du 2026-08-14).
**VAGUES I à V CLOSES, vague VI en cours** — 62 phases sur 73. **65.1 attend
confirmation**. Plan → `docs/memory/phase-plan.md`. **Cadence : deux phases par tour.**

**Terminé dans cette session**
- **Vague V — l'extension par des tiers** : greffons (manifeste jugé avant le
  code, `privé + externe` et `system` refusés, exécution dans le bac à sable du
  VOLET 34), contrats développeur vérifiés par la suite, couches de mémoire
  (une couche **est** une durée de vie), documents venus d'un connecteur
  (propriétaire pris au contrat), **modifier un greffon le désactive**.
- **Vague VI, V63** : la connaissance des vagues III–IV n'était joignable que par
  HTTP — un agent du même processus devait sortir par le réseau pour interroger
  son propre dépôt. `AgentContext.ask_knowledge()` referme l'écart ;
  `agent_reach()` le **mesure par recherche d'attribut** (13 atteintes, 0
  manquante) et nomme ce qui est hors de portée par décision.
- **Vague VI, V64** : une routine ne pouvait appeler que des **outils**, donc
  n'empruntait jamais l'orchestrateur (ni reprise, ni historique, ni audit).
  Elle peut désormais déclencher un **workflow** par le même moteur.
  Règle du travail sans témoin : **une approbation n'est jamais accordée par
  l'absence de quelqu'un pour la refuser** — `suspended`, avec le `run_id`.
- Suite : **4203 tests passent** avant V64 ; 8 ignorés ; `ruff` propre.

**Prochaine étape**
Phase **65.1** — sûreté intégrée : un moteur absent ne fait rien tomber
(vague VI, 11 phases restantes).

**Bloqué / à surveiller**
- **Aucun identifiant OAuth Google** — arrête l'activation des VOLETs 43 à 45.
- **Aucune source de connaissance activée** : inscrire n'est pas activer (ADR-021).
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO,
  la FAO, l'OMS répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
