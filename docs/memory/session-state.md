# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-14

**En cours** : **programme d'expansion VOLETs 37→76** (directive du 2026-08-14).
**VAGUE I CLOSE** — 12 phases sur 12. **43.1 attend confirmation** (OAuth 2.0).
Plan complet → `docs/memory/phase-plan.md`.

**Terminé dans cette session**
- **Audit d'intégration des 40 domaines** : 19 existent, 12 à étendre, 9 absents.
  Le programme n'est pas 40 constructions. **73 phases en 6 vagues.**
- **Vague I — le socle d'extension, six frontières tenues par du code** :
  capacités des 22 outils, pré-approbation étroite (`python -m pytest` oui,
  `python -c` non), plafonds de rôle à trois verdicts, isolation des données
  utilisateur, base de connaissance étanche, contrat + cycle de vie + sûreté des
  connecteurs, masquage des secrets avec garde AST.
- **Défauts trouvés en construisant, tous corrigés** : `model` déclaré `system`
  refusait la génération à tout utilisateur ; `/workflow/run` contournait le
  plafond de `/tool/execute` (phase 39.3 ajoutée au plan pour le refermer) ;
  `contract_of` faisait dire « aucun contrat » à un contrat mal typé ;
  `is_sensitive("key")` accusait le connecteur de stockage à tort.
- Suite : **3452 tests passent**, 8 ignorés (3241 au début) ; `ruff` propre.

**Prochaine étape**
Phase **43.1** — OAuth 2.0 : flux, jetons chiffrés, révocation. Elle finira en
`IMPLEMENTED` + `NOT_CONFIGURED` : **aucun identifiant Google n'existe ici, et
aucun ne sera fabriqué.**

**Bloqué / à surveiller**
- **Aucun identifiant OAuth Google** — arrête l'activation des VOLETs 43 à 45.
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO,
  la FAO, l'OMS répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
