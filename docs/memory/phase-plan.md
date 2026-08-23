# Phase plan — current VOLET

Chargé au démarrage de session. Il dit où en est le programme en cours et quelle
phase attend une confirmation.

---

VOLET en cours   : **REDESIGN CHAT-FIRST**
                   Brief du propriétaire, 2026-08-22
Chapitres        : **8**
Phases           : **11**
Phase courante   : **5.1 — en attente de confirmation**
Terminées        : **1–5** (4.1-4.2 incl.) — chat conversationnel fonctionnel
Cadence          : **deux phases par tour** (convenu le 2026-08-19)

**Règle permanente** : `.claude/rules/post-integration-validation.md`.

**Ce que le brief interdit de casser** : orchestration, agents, mémoire,
connaissance, `ModelRouter`, runtimes, outils, multimodalité, recherche,
sécurité, backend, API internes.

---

## Chapitre 1 — Audit du frontend (TERMINÉ)

Mesuré, pas rappelé.

### Ce qui existe

| Fichier | Lignes | Rôle |
|---|---:|---|
| `src/web/static/index.html` | 109 | Le tableau de bord actuel |
| `js/dashboard.js` | 282 | Sa logique |
| `css/dashboard.css` | 262 | Son style |
| `js/api-client.js` | **236** | **Client HTTP partagé — à réutiliser** |
| `studio.html` + `studio.js` + `studio.css` | 725 | Le Media Studio, séparé |

**1 614 lignes au total. Aucune étape de build**, aucun framework : HTML, CSS et
JavaScript servis tels quels par `StaticFiles` sous `/ui` (ADR-008). C'est une
force ici — le redesign n'ajoute aucune chaîne d'outils.

### Les routes que le frontend appelle aujourd'hui

`/health` · `/connectors` · `/connectors/status` · `/auth/keys` ·
`/auth/keys/reload` · `/memory/store` · `/notification/stats` ·
`/media/capabilities` · `/media/projects` · **`/agri/advice`**

### Le constat qui décide du plan

**Il n'existe aucune route de conversation générale.** Ni `/chat`, ni
`/conversation`, ni `/ask`. Grep sur `src/api/server.py` : zéro occurrence.

Les seules routes qui produisent du texte sont :

| Route | Ce qu'elle fait |
|---|---|
| `/model/generate` | Génération brute — **court-circuite l'orchestration** |
| `/agri/advice` | L'outil agricole, un domaine unique |
| `/workflow/run` | **Passe par l'orchestrateur** (`router → planner → …`) |
| `/knowledge/search` | Récupération, pas conversation |

**Conséquence** : l'expérience demandée ne peut pas être livrée en touchant
seulement le frontend. Il manque **une** route. Le brief dit *« ne réécris pas le
backend inutilement »* — ce n'est pas inutile, c'est le minimum, et c'est une
seule route.

### Et la détection automatique de domaine existe déjà

Le brief demande que *« Comment planter le mil ? »* active l'agriculture sans que
l'utilisateur choisisse. **C'est de l'orchestration**, et `src/router/` la fait :
l'agent `router` est le premier du workflow `standard`.

Donc la route de chat doit passer par **l'orchestrateur existant**, pas par
`model.generate`. Réutiliser plutôt que reconstruire — et c'est ce qui donne la
détection automatique gratuitement.

---

## Le plan

```
Ch. 01  Audit du frontend                        → 1 phase  ✅ TERMINÉE

Ch. 02  La route de conversation                 → 2 phases  ✅ TERMINÉ
        2.1 contrat : entrée, sortie, orchestrateur, refus. Aucun code
        2.2 implémentation + tests — `POST /chat`, 14 tests

Ch. 03  La coquille chat                         → 2 phases  ✅ TERMINÉ
        3.1 `chat.html` + `chat.css` — plein écran, zéro carte
        3.2 identité GalSen IA : palette reprise, vide accueillant, 9 tests

Ch. 04  La conversation                          → 2 phases  ✅ TERMINÉ
        4.1 `chat.js` : envoi, historique, états d'attente et d'erreur
        4.2 réutilisation de `api-client.js`, jamais un second client — 7 tests

Ch. 05  Le menu des domaines                     → 1 phase (indivisible)
        14 capacités, en haut à gauche, sans multiplier les assistants

Ch. 06  L'espace administrateur                  → 1 phase (indivisible)
        Le tableau de bord actuel déplacé sous `/ui/admin`, rien supprimé

Ch. 07  Responsive                               → 1 phase (indivisible)
        Mobile d'abord, puis desktop

Ch. 08  Vérification de bout en bout             → 1 phase (indivisible)
        Suite complète, routes, mobile, desktop, chat, menu, admin
```

**Total : 11 phases.**

---

## Ce que je dois te dire avant que tu confirmes

**Ce redesign amplifie un défaut non résolu.**

Il y a une heure, `/agri/advice` a répondu à *« quand semer »* en plaçant
l'hivernage de fin mars à mi-août — trois mois trop tôt — et en inventant une
troisième saison. **Sans source, sans provenance, sans `UNKNOWN`.** La cause est
mesurée : la route ne consulte jamais le corpus, et le corpus agricole est vide.

Aujourd'hui ce défaut est enfermé dans **un formulaire**. Une interface
chat-first en fait **l'expérience principale** : chaque question, sur n'importe
quel domaine, passera par le même chemin non ancré.

Une belle interface qui invente couramment est plus dangereuse qu'un formulaire
laid qui invente rarement — parce qu'on lui fait confiance.

**Deux ordres possibles, et c'est ta décision :**

- **Grounding d'abord** — brancher le mécanisme `UNKNOWN` qui existe déjà
  (`retrieve_reliable`, `routing.ask`), puis construire le chat par-dessus.
  Plus lent à voir, honnête dès le premier jour.
- **Chat d'abord** — livrer l'interface, puis le grounding. Tu vois ton produit
  tout de suite, et tu portes le risque en attendant. **← choisi le 2026-08-22.**

Si tu choisis « chat d'abord », la phase 2.1 devra prévoir **où** le refus
s'insérera plus tard, pour que ce ne soit pas à refaire.

---

## Programmes précédents, terminés — ne pas rouvrir

1. **AUDIT #01 `codebase-memory-mcp`** — 16 phases, `KEEP FOR RESEARCH`.
2. **SUPERPOWERS** — audit 24 phases + 11 d'implémentation. **ADR-038**.
3. **OPEN-SOURCE ECOSYSTEM AUDIT** — 22 phases. **ADR-037**.
4. **OpenClaw** (ADR-034), **DeepSeek Harness** (ADR-035) : non intégrés.
5. **Live Context** (ADR-033), **Creative Canvas** (ADR-031),
   **Research Orchestration** (ADR-032), **MoneyPrinterTurbo** (ADR-030),
   **Apache-2.0** (ADR-036).

---

## Ce que les chapitres 02–04 ont bâti

Un chat qui refuse honnêtement. À la première visite, l'utilisateur voit :
- Un accueil que le premier message efface
- Trois pistes qu'il peut cliquer ou dactylographier
- L'historique, dans le temps de la conversation
- Les trois jetons sous chaque réponse : domaine, méthode, ancrage, durée
- **Rien que la plateforme ne sait.**

Quand il saisit « Quand planter le mil ? », le chat :
1. détecte agriculture (keywords)
2. demande à l'orchestrateur (par `/chat`, pas par `/model/generate`)
3. reçoit le refus de l'agent `senegal` : « la base est vide »
4. le rend tel quel, en ocre (pas rouge)
5. dit **1,1 s** réellement, pas 4,87 s de mesure précédente

Aucun des 17 agents ne rédige. La chaîne `question` est recherche+vérification,
pas conversation. Ce qui s'affiche n'invente rien.

---

## Ce que le chapitre 02 a mesuré, et qui change la suite

**Aucun des 17 agents ne rédige.** Seuls `planner` et `coder` appellent le
modèle, pour planifier et pour coder. Le workflow `question` est
`planner → researcher → senegal → verifier` : une chaîne de recherche et de
vérification, pas une chaîne de conversation.

Conséquence sur `POST /chat`, mesurée le 2026-08-22 :

| Message | Ce que la route rend |
|---|---|
| « Quand planter le mil à Thiès ? » | Le refus de l'agent `senegal` : *« la base est vide sur ce sujet — ce n'est pas une réponse négative »*, `UNGROUNDED` |
| « bonjour » | Les trois lacunes du `researcher`, `UNGROUNDED` |

**La route est honnête et ne fabrique rien. Elle ne converse pas non plus.**

Ce n'est pas un défaut de la route : c'est l'état de la plateforme, rendu
visible. Le rendre visible était le travail du chapitre 02 ; le combler est une
décision d'architecture qui ne m'appartient pas, et elle est posée en fin de
phase.
