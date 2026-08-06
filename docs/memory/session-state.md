# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-06

**En cours** : Rien. `main` = `0ec16b3`, 10 PR fusionnées, rien en attente.

**Terminé dans cette session**
- La plateforme démarre, CI verte (~85 s), docs d'entrée et backlog remis au vrai.
- **VOLET 02 ch. 09 bouclé** — couche de connecteurs (ADR-007) : contrat + registre,
  connecteur SMTP, connecteur stockage disque, 4 routes `/connectors` avec deux
  permissions RBAC (décrire ≠ vérifier).
- **Quatre inventions supprimées** : calendrier (rendez-vous fabriqués), RAG (scores
  déduits du rang), détection de visages (« aucun visage » systématique), routeur de
  modèles (« Réponse simulée »). Ce dernier est branché sur la vraie génération et
  apporte `generate_with_fallback()`.
- Tests : 93 → **899 passants**, 5 ignorés, zéro avertissement.

**Prochaine étape** (au choix, aucune n'est bloquée)
Santé des connecteurs dans `/health` · connecteur calendrier (CalDAV) · service de
fichiers adossé au connecteur stockage · tests du chemin de génération hébergé.

**Bloqué / à surveiller**
- `/model/generate` répond 503 : aucune clé dans l'environnement. ADR-004 appliquée,
  `_call_api` implémentée pour les 3 fournisseurs — il ne manque que la clé.
- Une invention peut se cacher derrière un test vert : les quatre trouvées étaient
  couvertes par des tests qui affirmaient la fiction ou ne la voyaient pas.
