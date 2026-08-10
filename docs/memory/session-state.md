# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-10

**En cours** : rien. **VOLET 05 et VOLET 14 terminés** dans cette session.

**Terminé dans cette session**
- **VOLET 05 — Knowledge Engine** : domaines, sensibilité, statut, cycle de vie tracé,
  filtrage par politique et par rôle, cache de requêtes, rapports de gouvernance et
  de qualité. Détail → `docs/architecture/knowledge.md`.
- **VOLET 14 — Search Engine** : `POST /search` **ne pouvait rien rendre** (aucun
  `SearchProvider` dans le dépôt) — 503 explicite puis source connaissance branchée,
  rôle propagé, analytique de recherche, `GET /search/status`.
  Détail → `docs/architecture/search.md`.
- **Trois défauts silencieux corrigés** : aller-retour RAG qui détruisait une
  connaissance ; `count()` plafonné à 10 000 (magasin qui ment sur sa taille) ;
  index tronqué à 10 000 rendant des documents introuvables sans signal.
- Tests : **1655 passants**, 7 ignorés (111 ajoutés dans la session).
  Branche `claude/galsen-ia-phases-ukwz7p`.

**Prochaine étape**
Choisir le prochain VOLET et publier son plan de phases. Restent : 03, 06 à 13, 15,
17 à 25. Cadence convenue : **2 à 3 phases par tour**.

**Bloqué / à surveiller**
- **La base de connaissances est toujours vide** : tout ce qui a été bâti dans les
  deux VOLETs décrit 0 élément. P1 le plus haut, ne dépend plus du code.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **C4 dépend de toi** : rien n'est déployé, personne n'a joint l'API par le réseau.
- Recherche sémantique absente : `EmbeddingsTool` produit des vecteurs que rien n'indexe.
