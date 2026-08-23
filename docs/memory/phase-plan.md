# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **CHAT — RÉPONSE FINALE RÉELLE**
                   Brief du propriétaire, 2026-08-23
Chapitres        : **11**
Phases           : **19** (18 + la 5.3 annoncée au ch. 03)
Phase courante   : AUCUNE — VOLET TERMINÉ
Terminées        : **1.1 · 1.2 · 2.1 · 2.2 · 3.1 · 3.2 · 4.1 · 4.2 · 5.1 · 5.2 · 5.3 · 6 · 7.1 · 7.2 · 7.3 · 8 · 9 · 10 · 11** — les 19
Branche          : `claude/galsen-ia-phases-ukwz7p`, **repartie de `main`**
                   (`dc09303`) — la PR #36 est fusionnée, on n'empile pas
                   sur de l'historique déjà intégré.
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Ce que le brief interdit** : reconstruire l'architecture, créer une seconde
sélection de modèle, contourner l'orchestration, l'ancrage, la vérification, la
mémoire, la sécurité, les permissions d'outils, le repli de fournisseur ou
l'observabilité. Et : **aucune mesure inventée**.

---

## Ce qui a été mesuré avant d'écrire ce plan

Le brief dit lui-même : *« DO NOT assume this diagnosis is automatically
correct. VERIFY IT against the actual current code. »* Trois vérifications ont
déjà corrigé sa prémisse.

**1. `ModelManager` est une classe abstraite.** L'implémentation est
`ModelManagerImpl` (`src/model_engine/model_manager.py:37`), et l'API l'obtient
par `_moteur_partage("model", ModelManagerImpl)` (`server.py:518`). Instancier
`ModelManager` lève `TypeError`. Le brief nomme la bonne classe pour la mauvaise
raison — c'est l'implémentation qu'il faut réutiliser, pas l'interface.

**2. `generate_text` et `generate_text_with_fallback` sont `async`**
(`:254`, `:283`). L'orchestrateur, lui, est **synchrone**. La couche de réponse
finale se tient donc exactement sur une frontière async/sync, et c'est un point
de conception, pas un détail.

**3. Et le plus important — il n'y a AUCUN modèle enregistré ici.**

```
modèles après démarrage complet de l'application : 0
modèles actifs                                    : 0
```

Mesuré à travers `TestClient(app)`, donc après le `lifespan`. Ce n'est pas
« Ollama est éteint » : c'est qu'aucun modèle n'est déclaré dans cet
environnement.

### Ce que cela impose au plan, et qu'il faut dire maintenant

**L'objectif final — « une vraie réponse en langue naturelle » — ne sera pas
vérifiable de bout en bout sur cette machine.** Ce qui est vérifiable ici :

- le câblage complet `/chat → contexte → ModelManagerImpl → ChatResponse` ;
- la construction du contexte de réponse ;
- la sémantique d'ancrage préservée ;
- le chemin d'erreur quand aucun fournisseur ne répond ;
- **toute la chaîne avec un fournisseur simulé** — ce que le §17 du brief
  demande explicitement.

Ce qui restera `UNKNOWN` jusqu'à ce que **tu** lances un modèle : la qualité
réelle des réponses, la latence réelle, et le comportement du repli entre
fournisseurs.

### Un risque à signaler avant de commencer

L'audit Linux a mesuré que `/health` passe de **3,5 ms à 1 149 ms** pendant un
`/chat`, parce que le travail bloquant tourne sur la boucle d'événements
(144 routes `async`, zéro délégation à un fil). **Ajouter une génération de
modèle allonge le tour**, donc aggrave ce blocage — d'une seconde aujourd'hui à
potentiellement dix.

Ce n'est pas une raison de ne pas faire le travail. C'est une raison de le
savoir : la correction P10 (trois sites d'appel) devient nettement plus urgente
après ce VOLET qu'avant. Je ne la fais pas ici — elle n'est pas dans le brief.

---

## Chapitre 01 — Cause racine confirmée (mesurée, pas lue)

### Le chemin réel, tracé en instrumentant `RouterEngine._dispatch_agent`

| Message | Agents réellement exécutés |
|---|---|
| « bonjour » | `planner` 114 ms · `researcher` **1 095 ms** |
| « Qui était Albert Einstein ? » | `planner` 3 ms · `researcher` **1 071 ms** |

**`senegal` et `verifier` ne tournent jamais**, alors qu'ils sont déclarés dans
le pipeline. Et le `researcher` consomme ~97 % du tour.

### Deux corrections au diagnostic du brief

**1. Le routage généraliste que le §9 demande existe déjà.** Le workflow porte
`agent_selection: planner`, et son propre commentaire l'explique : *« une
question sénégalaise fait entrer `senegal`, un sujet à risque fait entrer
`verifier`, et une question ordinaire n'en retient aucun des deux »*. Mesuré sur
« Einstein » : `agents_required: ['researcher']`, `geographic_scope: 'global'`.

**Le Sénégal n'est donc pas forcé aujourd'hui.** Le §10 du brief demande de le
rendre spécialisé — il l'est déjà. Ce qui reste à faire est ailleurs.

**2. Le planner appelle déjà le modèle, et échoue honnêtement.**
`model_assisted: {'status': 'unavailable', 'reason': 'Aucun modèle enregistré ne
correspond à la tâche'}`. Le motif d'intégration existe donc déjà dans un agent.

### La cause racine, elle, est confirmée — et plus étroite que le brief

**Rien dans la chaîne ne rédige.** Entre les résultats structurés des agents et
`ChatResponse.answer` il n'y a que `_texte_de_reponse()`, qui **rend des données**
et n'en produit pas. Aucun agent, aucun workflow, aucun module ne transforme un
contexte en phrase.

### Le symptôme que le brief n'avait pas nommé

`_texte_de_reponse()` rend les **lacunes du chercheur** dès qu'il n'a rien trouvé.
Sur cette machine — sans réseau, corpus vide — c'est le cas de *toutes* les
questions. D'où le fait mesuré que **« bonjour » et « Qui était Albert Einstein ? »
reçoivent la réponse identique**, mot pour mot.

### Ce qui existe déjà et sera réutilisé plutôt que réécrit

| Besoin | Ce qui existe |
|---|---|
| Pont sync → async | **`AgentContext._run_async()`** (`src/agent/context.py:1233`), qui gère déjà le cas « une boucle tourne déjà » |
| Génération avec repli | `ModelManagerImpl.generate_text_with_fallback()` |
| Validation de réponse | `src/model_engine/response_validator.py`, `response_ranker.py` |
| Axes de routage | `domain`, `task_type`, `complexity`, `risk`, `freshness`, `language`, `geographic_scope` — déjà calculés par le planner |

**Aucun composant de rédaction conversationnelle n'existe** : le §7 autorise donc
d'en créer un.

---

## Le plan

```
Ch. 01  Confirmer la cause racine (§3)            → 2 phases
        1.1 tracer le chemin d'exécution réel de /chat, bout en bout ✅
        1.2 confirmer ou réfuter le diagnostic du brief, avec les preuves ✅

Ch. 02  Contrat de la couche de réponse (§6,7,8)  → 2 phases
        2.1 chercher un composant existant avant d'en créer un ; lire les ADR ✅
        2.2 le contrat : entrées, sortie, frontière async, échecs. Aucun code ✅
        → `docs/architecture/chat-final-response.md`

Ch. 03  Routage généraliste (§9,10)               → 2 phases
        3.1 ce que le routage fait aujourd'hui, mesuré sur 8 messages types ✅
        3.2 le Sénégal EST déjà une spécialité (5/5 et 3/3) ; deux vrais ✅
            manques : « bonjour » lance une recherche, « écris du code »
            est classé recherche. Corrigés dans le planner, au ch. 05

Ch. 04  Implémentation de la couche (§7,11)       → 2 phases
        4.1 le composant et sa consigne de génération ✅ → `src/chat/`
        4.2 branchement sur `ModelManagerImpl`, repli compris ✅

Ch. 05  /chat, ancrage et constats (§12,13)       → 3 phases
        5.1 le contexte de réponse construit depuis les résultats d'agents ✅
        5.2 ancrage préservé : la génération ne rend jamais `GROUNDED` ✅
        5.3 les deux intentions du planner ✅ — « bonjour » : 1 092 → 77 ms.
            « écris du code » : intention corrigée (`coder`), mais le
            workflow `question` ne déclare pas `coder`, donc il ne tourne
            pas. **Décision d'exploitant, pas de détail** — voir ci-dessous.

Ch. 06  Erreurs et mémoire (§14,15)               → 1 phase (indivisible) ✅
        Fuite d'infrastructure corrigée ; historique vérifié jusqu'à l'invite

Ch. 07  Tests A à J (§16,17)                      → 3 phases
        7.1 A, B, D — général, conversation, technique ✅
        7.2 C, E, F — Sénégal, code, historique multi-tours ✅
        → `tests/test_chat_general_purpose.py`, 18 tests
        7.3 G, H, I, J — pas de modèle, non vérifié, vérifié, échec ✅

Ch. 08  Sécurité, observabilité, coût (§18,19,20) → 1 phase (indivisible) ✅
        34 tests au total dans `tests/test_chat_general_purpose.py`
Ch. 09  Vérification complète (§23)               → 1 phase (indivisible) ✅
        7 148 passent, 0 échec · 44 tests ajoutés, 0 supprimé · lint vert
Ch. 10  Documentation et décision d'ADR (§21)     → 1 phase (indivisible) ✅
        **ADR-039** · contrat marqué implémenté · mémoire et CHANGELOG à jour
Ch. 11  Rapport final, 12 points (§24)            → 1 phase (indivisible) ✅
        → `docs/chat/final-response-report.md`
```

**Total : 18 phases.**

---

## Ce que je dois te dire avant que tu confirmes

**Je suis d'accord avec le brief sur le fond**, et l'audit précédent disait déjà
la même chose dans ses propres termes : *« aucun des 17 agents ne rédige ; seuls
`planner` et `coder` appellent le modèle »*. Le brief ajoute ce que l'audit
n'avait pas le droit de décider — **que la couche de rédaction doit exister**.

**Deux points où je demanderai ton arbitrage en cours de route**, parce qu'ils
changent le produit et pas seulement le code :

1. **« Bonjour » doit-il traverser le pipeline complet ?** Le §9 dit non. Cela
   veut dire un chemin court qui saute planner, researcher, senegal et verifier.
   C'est la bonne conception — et c'est aussi la première fois que `/chat`
   contournera l'orchestration. Je le ferai *dans* l'orchestrateur, pas à côté.

2. **`NOT_CHECKED` autorise-t-il le modèle à répondre de sa propre
   connaissance ?** Le §12 dit oui. C'est un changement réel de posture pour
   cette plateforme, qui refusait jusqu'ici de répondre sans source. Je le
   respecterai, et l'interface devra distinguer clairement « fondé sur nos
   sources » de « connaissance du modèle, non vérifiée ».

Une phase à la fois, deux par tour, chacune vérifiée avant la suivante.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **AUDIT ARCHITECTURE NOYAU LINUX** — 13 chapitres, 18 phases →
   `docs/research/linux-kernel-architecture-audit.md`.
   `SELECTIVE ARCHITECTURAL IMPROVEMENTS RECOMMENDED` : 5 recommandations, aucune
   autorisée, aucune implémentée. **P10 (3 sites d'appel) devient plus urgente
   après ce VOLET.**
2. **REDESIGN CHAT-FIRST** — 8 chapitres, 11 phases. `POST /chat`, `/ui/` sert la
   conversation, `/ui/admin/` le tableau de bord, menu de 14 domaines.
3. **AUDIT #01 `codebase-memory-mcp`** — 16 phases, `KEEP FOR RESEARCH`.
4. **SUPERPOWERS** — **ADR-038**. **OPEN-SOURCE ECOSYSTEM** — **ADR-037**.
5. **OpenClaw** (ADR-034), **DeepSeek Harness** (ADR-035) : non intégrés.
6. **Live Context** (ADR-033), **Creative Canvas** (ADR-031),
   **Research Orchestration** (ADR-032), **MoneyPrinterTurbo** (ADR-030),
   **Apache-2.0** (ADR-036).
