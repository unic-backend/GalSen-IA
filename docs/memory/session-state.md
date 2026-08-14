# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-14

**En cours** : **programme d'expansion VOLETs 37→76** (directive du 2026-08-14).
**VAGUES I, II et III CLOSES** — 30 phases sur 73. **51.1 attend confirmation.**
Plan complet → `docs/memory/phase-plan.md`. **Cadence demandée : deux phases par tour.**

**Terminé dans cette session**
- **Vague II — connecteurs Google** : OAuth 2.0 + PKCE S256, jetons chiffrés ou
  refusés, Gmail/Drive/Agenda en lecture seule. `NOT_CONFIGURED` : aucun
  identifiant n'existe, aucun n'a été fabriqué. Étanchéité vérifiée en attaquant.
- **Vague III — le temps et l'exécution longue** : routines (déclaration,
  planification, journal, budget, arrêt d'urgence), workflows longs avec points de
  reprise (une étape aboutie n'est jamais refaite), notifications des événements
  que personne ne verrait, canaux de livraison déclarés et honnêtes.
- **Défauts trouvés en câblant** : l'arrêt d'urgence disparaissait à la
  reconstruction du planificateur ; la reprise d'un workflow pouvait changer la
  question posée. Les deux refermés, avec un test chacun.
- **Correction d'audit** : la ligne « Notifications — pas de moteur » était fausse.
  Le service existait ; ce sont ses **événements** et ses **canaux** qui manquaient.
- Suite : **3866 tests passent**, 8 ignorés ; `ruff` propre.

**Prochaine étape**
Phase **51.1** — registre de sources mondial, généralisant `corpus/sources/senegal.yaml`.
Ouvre la vague IV (la connaissance, 16 phases).

**Bloqué / à surveiller**
- **Aucun identifiant OAuth Google** — arrête l'activation des VOLETs 43 à 45.
- **Aucun identifiant de canal externe** — courriel et webhook `NOT_CONFIGURED`.
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO,
  la FAO, l'OMS répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
