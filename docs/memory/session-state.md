# Session State

Où en est le travail, à la fin de la dernière session.
Ce fichier est injecté automatiquement au démarrage de chaque session Claude Code
(hook `SessionStart`). Il doit rester court : 20 lignes maximum.

Mise à jour : à la fin de chaque session, et à chaque point de contrôle des 25 minutes.

---

## Dernière session

**Date** : 2026-08-08

**En cours** : rien. Réconciliation terminée (4 phases), VOLET 02 clos (10/10).

**Terminé dans cette session**
- **VOLET 02 clos** : ADR-008 (`/ui` sans build) et ADR-009 (une seule instance,
  dite à l'exécution par `/health`).
- **Protocole de phases** installé : une phase par tour, plan avant chaque VOLET.
- **Deux branches réconciliées** : arrivent les services calendar/cloud/email,
  5 magasins SQLite, le SDK client, `POST /agri/advice`. `src/frontend/` (Jinja2)
  écarté ; la page « Conseil agricole » vit dans `/ui`.
- **Trois défauts corrigés** : `/agri/advice` répondait 200 avec un conseil vide ;
  la convention `src.` était de nouveau enfreinte et masquée par un `sys.path` ;
  le rapport `scaling` ne suivait pas le backend de stockage.
- Tests : **1405 passants**, 5 ignorés.

**Prochaine étape**
Choisir le prochain VOLET (03 Development Manual ou 04 Roadmap), publier son plan
de phases, puis s'arrêter — protocole `.claude/rules/phase-protocol.md`.

**Bloqué / à surveiller**
- `/model/generate` et `/agri/advice` répondent 503 : il ne manque qu'une clé.
- Trois façons d'écrire un fichier sur disque cohabitent (connecteur, magasin
  SQLite, magasin fichier) — à arbitrer, c'est dans `pending-work.md`.
