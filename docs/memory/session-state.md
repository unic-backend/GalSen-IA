# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-16

**En cours** : rien. **DARRA J est terminé — 20 VOLETs, 28 phases sur 28.**
Rapport final → `docs/darra-j/final-report.md`. Détail des phases et des défauts
trouvés → `docs/darra-j/phase-plan.md`.

**Terminé dans cette session**
- **`src/darra_j/`** : 21 modules, 19 fichiers de tests, **377 tests**.
  Modèle canonique, registre de versions, résolution déterministe, ingestion,
  pare-feu, cohérence entre usagers, pédagogie, évaluation, modes enseignant /
  élève / parent, confidentialité, graphe éducatif, maîtrise, multilingue,
  laboratoire, résilience, auditabilité, aptitude à la production.
- **État atteint, et c'est celui que la directive demande** :
  `ARCHITECTURE READY — OFFICIAL CURRICULUM DATA PENDING`. **Aucun curriculum
  sénégalais n'a été intégré** — aucun n'était disponible, aucun n'a été écrit
  de mémoire. `readiness()` **mesure** le registre ; un registre ne contenant
  que des fixtures rapporte zéro version officielle.
- **Six rôles éducatifs dans `src/api/rbac.py`**, avec
  `PERMISSIONS_HORS_PLATEFORME` : sans cette soustraction, déclarer
  `curriculum:publish` aurait rendu GalSen IA capable de publier un curriculum
  officiel. `test_admin_has_all_permissions` a été **resserré**, pas assoupli.
- **Défaut corrigé dans du code existant** : la table d'alias ne gardait que la
  forme repliée — `translate()` rendait `mbey` pour `mbéy`, du wolof mal
  orthographié alors que `ë ñ ŋ` sont des lettres CLAD. Elle garde désormais
  `written` (affichage) et `terms` (recherche).
- **Onze défauts trouvés en exécutant**, chacun pinné par un test (tableau dans
  le rapport final). Suite : **4864 tests**, 8 ignorés, `ruff` propre.

**Prochaine étape**
Aucune en attente. Ce qui reste dépend de quelqu'un d'autre (voir « Bloqué »).

**Bloqué / à surveiller**
- **Aucune version de curriculum publiée par une autorité `TIER_A`** — seule
  condition pour quitter `ARCHITECTURE READY`. Elle n'appartient pas à ce dépôt.
- **Aucun identifiant OAuth Google** — arrête l'activation des VOLETs 43 à 45.
- **Aucune source de connaissance activée** : inscrire n'est pas activer (ADR-021).
- **Mandataire réseau** : les 9 domaines `.sn`, la Banque mondiale, l'UNESCO,
  la FAO, l'OMS répondent `CONNECT → 403`. Mesuré, non contourné.
- **C1** : `ollama serve` — génération et récupération sémantique non mesurées.
- **`git push origin v0.1.0`** : seul échec de CI restant.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement : décisions en attente.
