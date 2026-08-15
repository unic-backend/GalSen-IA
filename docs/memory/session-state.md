# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-15

**En cours** : **programme d'expansion VOLETs 37→76** (directive du 2026-08-14).
**PROGRAMME TERMINÉ — 73 phases sur 73**, vagues I à VI closes. Aucune phase en
attente. Plan → `docs/memory/phase-plan.md`. Les VOLETs 72 à 76 restent réservés :
ils ne s'ouvrent que si un manque réel est mesuré.

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
- **Vague VI, V65** : l'isolement des pannes ne couvrait que les 14 moteurs du
  registre ; les **9 sous-systèmes** des VOLETs 47→64 n'étaient dans aucun
  rapport, et `/health` ne connaissait que des composants d'avant la vague III.
  `src/integration/degradation.py` les sonde isolément — une sonde qui lève est
  rapportée, pas propagée. **Dégradé n'est pas en panne** : pas de bascule du
  statut global, pas de perte de readiness. Mesuré : 9 disponibles, 0 dégradé.
- **Vague VI, V66** : `request_id` n'existait dans aucun sous-système récent.
  Un tour de routine porte désormais un `correlation_id` que l'exécution
  **reprend**, et `/observability/trail/{id}` assemble les sources autour de lui
  — en **appelant** la trace d'audit du VOLET 19 plutôt qu'en la refaisant.
  Vide ≠ illisible ; rien n'est rapproché par l'heure.
- **Vague VI, V67** : le budget des routines comptait des tours ; depuis qu'un
  tour peut déclencher un workflow entier, il ne dit plus ce qu'une routine
  coûte. Le travail est plafonné à part, en **agents exécutés**, décompté après
  l'exécution et même quand le tour échoue.
- **Vague VI, V68** : le barème comptait ses entrées sans dire **ce qui n'est
  pas évalué**. Chaque entrée déclare son domaine, un domaine inconnu est nommé,
  et sept questions couvrent construction, sport, géographie, langues, santé et
  entreprise — toutes `to_source`, **aucune réponse écrite**. Défaut corrigé en
  écrivant : « non mesuré » était rangé avec « rien à évaluer ».
- **Vague VI, V69** : démonstration de bout en bout (`scripts/demonstration.py`).
  **Elle a attrapé un défaut réel au premier tour** : le routage passait la
  question entière à `answer_country()`, qui attend un nom de pays — la couche
  mondiale était muette dès qu'on lui posait une vraie question. `find_country()`
  corrige. Verdict mesuré : **PARTIAL** (5 OK, 2 non configurés, 0 échec).
- **Vague VI, V70–V71** : les chiffres publiés étaient périmés (76 routes / 3238
  tests annoncés, **123 / 4334** mesurés) — corrigés et **tenus par une suite**.
  **ADR-022** rassemble les décisions du travail sans témoin ; changelog,
  `completed-work.md` et vue d'ensemble à jour.
- Suite : **4334 tests passent** ; 8 ignorés ; `ruff` propre.

**Prochaine étape**
Aucune : le programme d'expansion est terminé. Ce qui reste dépend de quelqu'un
d'autre (voir « Bloqué »). Un VOLET 72 ne s'ouvre que sur un manque **mesuré**.

**Bloqué / à surveiller**
- **Aucun identifiant OAuth Google** — arrête l'activation des VOLETs 43 à 45.
- **Aucune source de connaissance activée** : inscrire n'est pas activer (ADR-021).
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO,
  la FAO, l'OMS répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
