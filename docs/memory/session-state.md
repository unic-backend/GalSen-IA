# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-06

**En cours** : Rien. `main` = `a2c596f`, 15 PR fusionnées, rien en attente.

**Terminé dans cette session**
- La plateforme démarre, CI verte (~90 s). Tests : 93 → **967 passants**, 5 ignorés.
- **VOLET 02 ch. 09 bouclé** — connecteurs (ADR-007) : contrat, registre, SMTP,
  stockage disque, 4 routes `/connectors`.
- **VOLET 02 ch. 08 bouclé** — clés jamais en clair (condensés + `compare_digest`),
  CORS refermé (il reflétait toute origine avec identifiants), en-têtes de sécurité,
  doc privée, révocation et rotation à chaud, chiffrement au repos.
- **Quatre inventions supprimées** : calendrier, scores RAG, détection de visages,
  « Réponse simulée » du routeur de modèles.

**Prochaine étape**
VOLET 02, il reste **2 chapitres sur 10** : ch. 02 (frontend, rien n'existe) et
ch. 10 (montée en charge : files d'attente, réplicas, cache distribué).

**Bloqué / à surveiller**
- `/model/generate` répond 503 : il ne manque qu'une clé dans l'environnement.
- `GALSEN_API_DOCS=enabled` est nécessaire pour voir `/docs` maintenant que des
  clés sont configurées.
- Perdre `GALSEN_ENCRYPTION_KEY` = perdre les données chiffrées, sans recours.
