# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-11

**En cours** : rien. **Les quatre chantiers de `docs/deployment/audit-2026-08-11.md`
sont terminés et poussés** (branche `claude/galsen-ia-phases-ukwz7p`). `v0.1.0` est
étiquetée localement sur `383fcf7` — **pas encore poussée** : le proxy git de
l'environnement refuse les étiquettes (403). Un `git push origin v0.1.0` depuis un
clone normal publie la version et déclenche `release.yml`.

**Terminé dans cette session**
- Les 25 VOLETs (série close) puis le backlog : le planificateur pilote le pipeline.
- **Chantier 1** — persistance : `src/storage/paths.py` point de décision unique (WAL,
  0600), sauvegarde à chaud par `VACUUM INTO`. Deux défauts trouvés : l'image sans
  `config/`, `agents/`, `workflows/` ; `SQLiteMemoryStore` ignorant `GALSEN_DATA_DIR`.
- **Chantier 2** (ADR-012) — Caddy termine TLS, `api` ne publie plus de port, et
  `X-Forwarded-*` n'est cru que d'un proxy déclaré : sans cela un en-tête forgé donnait
  un quota illimité et l'invisibilité du détecteur de menaces.
- **Chantier 3** (ADR-013) — verrou `flock` sur le répertoire de données : une deuxième
  instance refuse de démarrer. **Redis écarté**, avec le déclencheur écrit.
- Tests : **2164 passants**, 7 ignorés.

**Prochaine étape**
Pousser l'étiquette (`git push origin v0.1.0`) : `release.yml` construit alors l'image,
vérifie qu'elle répond sur `/live` et publie les notes. Puis la liste de
`docs/deployment/production-readiness.md` — DNS, ports 80/443, `.env`, TEST 2, TEST 6.

**Bloqué / à surveiller**
- **TEST 2 et TEST 6 non exécutés** : ils demandent un hôte Docker, absent de
  l'environnement de travail. À la charge de l'opérateur avant publication.
- **Chantier 4** : `release.yml`, `docs/deployment/rollback.md`,
  `docs/deployment/production-readiness.md`, versions figées, outils de test sortis de
  l'image de production.
- **Une révocation de clé ne survit pas à un redémarrage** (`persistent: false`). Le
  verrou ferme le cas « autre instance », pas le cas « redémarrage ». Suite naturelle :
  persister la liste de révocation dans le répertoire de données.
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **La base de connaissances est toujours vide** : P1, ne dépend pas du code.
