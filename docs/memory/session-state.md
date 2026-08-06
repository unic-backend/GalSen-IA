# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-06

**En cours** : Rien. **VOLET 02 terminé, 10 chapitres sur 10.**

**Terminé dans cette session**
- **ch. 10 (montée en charge) — ADR-009** : la plateforme tourne en **une seule
  instance** et le dit à l'exécution (`/health` → `scaling`, `scope: "instance"`
  sur les routes de clés). Quatre sous-systèmes cassent avec une 2ᵉ instance ;
  ordre de réparation fixé : révocations → limiteur → fichiers → notifications.
  Aucune infrastructure (Redis, files d'attente, réplicas) n'a été ajoutée.
- **ch. 02 (frontend) — ADR-008** : tableau de bord sans étape de construction
  sous `/ui`, vérifié dans un vrai navigateur.
- Tests : **1008 passants**, 5 ignorés.

**Prochaine étape**
Choisir le prochain VOLET. VOLET 03 (Development Manual) ou VOLET 04 (Roadmap)
sont les suites naturelles ; VOLET 01 (Master Constitution) sert d'arbitrage.

**Bloqué / à surveiller**
- `/model/generate` répond 503 : il ne manque qu'une clé dans l'environnement.
- Une clé révoquée n'est coupée que sur l'instance jointe (ADR-009).
- Perdre `GALSEN_ENCRYPTION_KEY` = perdre les données chiffrées, sans recours.
