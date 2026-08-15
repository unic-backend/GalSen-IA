# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-14

**En cours** : **programme d'expansion VOLETs 37→76** (directive du 2026-08-14).
**VAGUES I à IV CLOSES** — 46 phases sur 73. **58.1 attend confirmation** (greffons).
Plan complet → `docs/memory/phase-plan.md`. **Cadence : deux phases par tour.**

**Terminé dans cette session**
- **Vague III** : routines (budget, arrêt d'urgence), workflows longs à points de
  reprise, notifications des événements que personne ne verrait, canaux honnêtes.
- **Vague IV — la connaissance** : registre de sources mondial, **249 pays
  dérivés** de jeux déjà acquis, séries mesurées, fraîcheur à deux échelles
  (années et jours), recherche documentaire corrigée, domaines `construction` et
  `sports` **déclarés vides avec leur raison**, routage des deux couches.
- **Deux corrections d'audit** : « recherche documentaire » et « notifications »
  étaient annoncés absents dans le plan ; les deux existaient entièrement.
- **Défauts trouvés en construisant** : FAO/OMS dans le mauvais registre ;
  `delete()` de l'index qui recalculait au lieu de relire ; l'Estonie rendue pour
  le mot « est » ; « base vide » là où il fallait lire « personne n'a compté ».
- Suite : **4066 tests passent**, 8 ignorés ; `ruff` propre.

**Prochaine étape**
Phase **58.1** — système de greffons (chargement, bac à sable, refus). Ouvre la
vague V (l'extension par des tiers, 12 phases).

**Bloqué / à surveiller**
- **Aucun identifiant OAuth Google** — arrête l'activation des VOLETs 43 à 45.
- **Aucune source de connaissance activée** : inscrire n'est pas activer (ADR-021).
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO,
  la FAO, l'OMS répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
