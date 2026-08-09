# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-09

**En cours** : rien. **VOLET 16 terminé** (10 chapitres, 12 phases).

**Terminé dans cette session**
- **VOLET 02, VOLET 04 et VOLET 16 clos.**
- **ADR-010** : une clé appartient à un sujet, sans magasin de secrets.
- **Critère C2 atteint** sur les trois magasins — l'écriture prenait son
  propriétaire dans le corps de la requête, la lecture ne filtrait rien.
- **Preuve de C1** écrite : s'ignore sans fournisseur, s'exécute dès qu'il y en a un.
- `GET /metrics` (trafic + taux d'authentification), `GET /auth/whoami`,
  `scripts/release_check.py`, `src/version.py` source unique.
- **C3 et C5 fermés** : workflow `revue` exécuté de bout en bout, journal borné.
- Tests : **1524 passants**, 7 ignorés.

**Prochaine étape**
Choisir le prochain VOLET et publier son plan de phases. Critères de sortie de
Phase 2 : **C2, C3, C5 et C6 atteints** ; restent C1 et C4, qui ne dépendent
plus du code.

**Bloqué / à surveiller**
- **C1 dépend de toi** : `ollama serve` avec un modèle de contexte ≥ 8192.
- **C4 dépend de toi** : rien n'est déployé, personne n'a joint l'API par le réseau.
- Rien ne vérifie une identité : celui qui écrit `GALSEN_API_KEYS` est cru sur parole.
- Base de connaissances toujours vide ; log à 6,7 Mo sans rotation.
