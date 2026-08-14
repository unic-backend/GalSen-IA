# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-14

**En cours** : **programme d'expansion VOLETs 37→76** (directive du 2026-08-14).
Phase **37.1 terminée** (audit d'intégration) ; **38.1 attend confirmation**.
Plan complet → `docs/memory/phase-plan.md`.

**Terminé dans cette session**
- **Audit d'intégration des 40 domaines de la directive** contre le dépôt réel :
  **19 existent déjà**, **12 sont à étendre**, **9 sont absents** (recherche, BTP,
  sports, greffons, routines, isolation utilisateur, écosystème développeur, sûreté
  des routines, démonstration). Les 39 chemins affirmés existants ont été vérifiés
  un par un ; l'absence de `routine`, `plugin` et `oauth` dans `src/` aussi.
  **72 phases en 6 vagues**, ordonnées par dépendance.
- **ADR-021 accepté et implémenté** : le report de `automated_acquisition` reposait sur un
  déclencheur **circulaire** (il mesurait le corpus que seule l'acquisition pouvait
  produire). Corrigé dans le code le 2026-08-14 — il mesure désormais **une source activée
  au registre**, ce qui peut bouger sans que la capacité existe. Un test garde la
  non-circularité.
- **Chaîne d'acquisition complète** (`src/acquisition/`, étapes 1→10) : registre étendu,
  enregistrement candidat et machine à états, récupérateur poli (agent véridique,
  `robots.txt`, débit par hôte, redirections hors domaine refusées), portillon par lot avec
  empreinte, découverte profondeur 1, métadonnées, détection de langue, barrière de
  confiance obligatoire (A8 passé), dix contrôles, proposition de manifeste, script de
  pilote. **Rien n'ingère tout seul ; aucune source n'est activée.**
- **Wolof** : `src/wolof/clad.py` (alphabet 27 lettres, normalisation déterministe),
  corpus **2105 phrases** acquis réellement, `src/services/wolof/`. Marqueurs de langue
  **mesurés sur le corpus** — 0 faux positif sur 2105 phrases.
- **Connaissance sénégalaise** : 14 régions et 45 départements **dérivés** de geoBoundaries
  (rattachement calculé par géométrie), 8 jeux acquis, **212 objets**, 271 fragments, 100 %
  avec provenance. **6 domaines peuplés sur 16.**
- **RAG multilingue** : `corpus/languages/aliases.yaml` (16 concepts, 115 termes fr/wo/en),
  expansion qui **ajoute et ne retire jamais**, latence **0,1–0,5 ms**.
- **Refus tenus** : 45 départements et non 46 (la source prime sur la directive) ;
  « Keur Massar » cherché dans les 8 sources et **introuvable** → `UNVERIFIED_CLAIM` ;
  histoire, culture, agriculture répondent `UNKNOWN`.
- Suite complète : **3239 tests passent**, 8 ignorés ; `ruff` propre.

**Prochaine étape**
Rien n'est en cours. Ce qui reste dépend du propriétaire — voir
`docs/deployment/etat-du-projet.md` §4.

**Bloqué / à surveiller**
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO, la FAO, l'OMS
  répondent `CONNECT → 403`. Mesuré, non contourné. C'est ce qui laisse 10 domaines vides.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
