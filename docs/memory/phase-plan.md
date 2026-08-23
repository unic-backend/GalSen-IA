# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **Interface conversationnelle « chat-first »**
                   Brief du propriétaire, 2026-08-22 : à l'ouverture, GalSen IA doit
                   ressembler à un assistant IA généraliste, pas à un tableau de bord.
                   Arrivée directe sur le chat ; un menu discret liste les domaines
                   (modes d'un même assistant, pas des assistants séparés) ; par défaut
                   l'orchestration détecte elle-même le domaine. Le contenu du tableau
                   de bord actuel (santé, connecteurs, clés, moteurs) n'est **pas
                   supprimé** : il est déplacé vers ADMIN → DIAGNOSTICS, caché des
                   utilisateurs normaux. Aucune réécriture du backend ; orchestration,
                   agents, mémoire, connaissance, ModelRouter, outils et sécurité
                   restent intacts.
Chapitres        : **5**
Phases           : **8**
Phase courante   : 2.1 — en cours
Terminées        : 1.1, 1.2
Cadence          : **continu automatique** (décision du propriétaire 2026-08-22 :
                   « ne me demande pas de confirmation entre les phases sauf si une
                   décision réellement bloquante ou irréversible est nécessaire »).
                   Arrêt uniquement pour une décision bloquante/irréversible.

**Règle permanente** : `.claude/rules/post-integration-validation.md`.

**Condition d'arrêt** : landing sur le chat, menu domaines + auto-détection branchés
sur l'orchestration existante, espace admin séparé et fonctionnel, backend intact,
tests verts.

---

## Le plan

```
Ch. 01  La page d'accueil devient un chat      → 2 phases
        Ph1.1  index.html → structure du chat : en-tête minimal, menu domaines,
               zone de conversation, barre de saisie (🎙 / ➤).
        Ph1.2  chat.js → logique d'affichage : bulles utilisateur/assistant,
               état « en cours », erreurs, saisie vocale Web Speech avec repli.

Ch. 02  Câblage sur l'orchestration existante  → 2 phases
        Ph2.1  api-client.js → ajouter workflow.run (et knowledge.ask), sans
               casser les routes existantes.
        Ph2.2  Brancher la boîte de chat sur POST /workflow/run (auto-détection) ;
               gérer les appels longs et la réponse.

Ch. 03  L'espace admin (diagnostics)           → 2 phases
        Ph3.1  admin.html + admin.js → déplacer santé / connecteurs / clés hors
               du chat.
        Ph3.2  Retirer ces panneaux du chat ; lien discret vers l'admin ; clé API
               déplacée dans l'admin ; Media Studio conservé tel quel.

Ch. 04  Design et responsive                   → 1 phase (indivisible)
        Ph4.1  chat.css → identité GalSen IA, mobile-first, thème clair/sombre,
               plus de look « dashboard SaaS ».

Ch. 05  Vérification complète                  → 1 phase (indivisible)
        Ph5.1  pytest + vérifier les routes (/ui/, /ui/admin.html, /ui/studio.html),
               responsive mobile/desktop, fonctions existantes, non-régression.
```

**Total : 8 phases.**

---

## Programmes précédents, terminés — ne pas rouvrir

1. **SUPERPOWERS** — audit 24 phases + implémentation 11 phases. **ADR-038** :
   6 concepts adoptés comme prose, **rien installé**.
2. **Les quatre constats de l'audit OSS** — PR #34 et #35 fusionnées.
3. **OPEN-SOURCE ECOSYSTEM AUDIT** — 22 phases. **ADR-037** : zéro `INTEGRATE`.
4. **OpenClaw** — ADR-034 : ne pas intégrer.
5. **DeepSeek Harness** — ADR-035 : implémentation non autorisée.
6. **Live Context** (ADR-033), **Creative Canvas** (ADR-031), **Research
   Orchestration** (ADR-032), **MoneyPrinterTurbo** (ADR-030),
   **Apache-2.0** (ADR-036).
7. **AUDIT #01 codebase-memory-mcp** — 16 phases sur 16. **`KEEP FOR RESEARCH`**.
   Rapport : `docs/research/codebase-memory-mcp-audit.md`. Rien installé, rien
   intégré, rien adapté.

## Programme interrompu (pas terminé — changements non commités, à reprendre ou trancher)

8. **Ancrage de /agri/advice sur le moteur de connaissance** — interrompu après
   les phases 1.1 et 2.1 (phase 3.1 non faite). Changements non commités dans
   `src/api/server.py`, `src/tools/agri_advice/tool.py`, `tests/test_agri_advice.py`,
   `tests/test_agri_advice_tool.py`. Reprendre ou trancher explicitement.
