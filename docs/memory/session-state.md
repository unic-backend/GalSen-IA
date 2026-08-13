# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-13

**En cours** : **acquisition de connaissance sénégalaise** — conception écrite et
**approuvée par le propriétaire** (`docs/architecture/senegal-knowledge-acquisition.md`,
13 sections). Aucun code de production modifié. **Prochaine action = ADR-021** (étape 0).
Contexte : VOLET 36 terminé (8/8), VOLET 35 à 10/12 — les chapitres 11 et 12 sont
précisément ce que ce pipeline débloque.

**Terminé dans cette session**
- VOLET 36 complet (A→H) : barrière de confiance sur les **9 chemins externes**, trois
  langues nationales, évaluation factuelle mécanique, agents `verifier` et `senegal`,
  entités et relations avec provenance obligatoire, dix axes de plan, `knowledge_architect`
  et `data_engineer`, capacités différées **mesurées**.
- VOLET 35, tours 2 à 4 (ch. 03–10) : registre des sources, récupération par portée, la
  réponse dit d'où elle vient, manques mesurés, découverte de sources, contradictions
  rapportées, collecte sous portillon, politique santé.
- Trois workflows ajoutés (`question`, `ingestion`, `series`) : quatre agents étaient au
  registre sans qu'aucun pipeline ne les cite — donc inatteignables.
- `DocumentSearchProvider` branché ; le branchement a révélé une **fuite** entre
  utilisateurs, réparée par une règle de propriété, pas par un test affaibli.
- Relecture : `contradictions.py` comptait les **années** comme des valeurs mesurées
  (2022 vs 2023 = faux conflit sur chaque série) ; `source_registry.py` lisait
  `//ansd.sn/x` comme « aucune URL », la porte exacte d'une autorité usurpée. Les deux
  corrigés, avec leurs tests dans les deux sens.
- **Rapport au propriétaire écrit** : `docs/deployment/etat-du-projet.md` — où en est le
  projet, ce qui bloque, et les cinq actions humaines dans l'ordre.
- Suite complète : **2925 tests passent**, 8 ignorés ; `ruff` propre.

**Prochaine étape**
**ADR-021** — rouvrir `automated_acquisition`, corriger son déclencheur (l'actuel est
circulaire : il mesure le résultat de la capacité manquante), inscrire la limite de portée
et ce qui reste différé. Ensuite seulement les étapes 1→12 de l'ordre d'implémentation.
Le reste dépend toujours du propriétaire — voir
`docs/deployment/etat-du-projet.md` §4 : `ollama serve`, `git push origin v0.1.0`, les
premiers vrais documents sénégalais, ADR-020, la cible de déploiement.

**Bloqué / à surveiller**
- **C1** : `ollama serve` avec un modèle de contexte ≥ 8192 — bloque génération et
  récupération sémantique.
- **`git push origin v0.1.0`** : seul échec de CI restant (403 depuis cet environnement).
- **0 document sénégalais** dans la base : le corpus ne s'invente pas.
- **ADR-020**, fin de vie de `/cloud/*`, cible de déploiement (C4) : décisions en attente.
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker.
