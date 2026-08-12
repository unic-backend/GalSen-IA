# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : **34 — Agent d'ordinateur personnel** (`docs/roadmap/VOLET_34.md`)
**Phases**         : 24, réparties sur 14 chapitres
**Phase courante** : **aucune.** VOLET 34 terminé (14/14), puis la **découverte proactive**
(`src/proactive/`) livrée hors chapitre le 2026-08-12 : le brief n'a plus de capacité absente.
**Cadence** : **un chapitre par tour** — demandé par l'utilisateur le 2026-08-12
(auparavant : un VOLET, puis une phase).
**ADR-018 : accepté en option B** le 2026-08-12, décidé par le propriétaire et **implémenté**
(`src/model_engine/providers/derogations.py`, `GALSEN_SOVEREIGN_DEROGATIONS`).
**Terminées dans le VOLET 34** : 1.1 état des lieux (`personal-agent-assessment.md`),
2.1 agents de code et multi-agents (`agent-foundations-comparison.md`),
2.2 computer-use, bureau et MCP (`computer-use-comparison.md`),
3.1 **ADR-017** — les capacités manquantes arrivent comme outils, pas comme une seconde architecture,
4.1 **ADR-018 (accepté, option B)** — souverain par défaut, avec une dérogation cadrée,
**chapitre 05** — la vue (`src/tools/screen/`),
**chapitre 06** — la main sous portillon (`src/tools/gui/`) — 21 outils au catalogue,
**chapitre 07** — plusieurs racines et des opérations annulables (`src/storage/`),
**chapitre 08** — le bac à sable et ses tests d'évasion (`src/sandbox/`),
**chapitre 09** — MCP : serveur en liste blanche, client épinglé (`src/mcp/`),
**chapitre 10** — graphe d'imports et index des symboles (`src/agent/repo_graph.py`, `symbol_index.py`),
**chapitre 11** — les trois agents manquants (`agents/organizer/`, `project_manager/`, `opportunity/`) — 13 agents au registre,
**chapitre 12** — style de travail dérivé et appliqué, amélioration mesurée ou refusée (`src/training/`),
**chapitre 13** — posture de sécurité mesurée et points de reprise (`src/security/`),
**chapitre 14** — matériel, pile et chemins de mise à niveau (`docs/architecture/hardware-and-stack.md`)
**Bloqué**         : rien du côté des décisions. Reste ce qui dépend de l'opérateur —
`ollama serve` (critère C1), `git push origin v0.1.0`, le corpus sénégalais, TEST 2 / TEST 6.
**Terminées** : VOLETs 01 à 25, 4 chantiers de mise en ligne, **VOLET 26 sauf 26.1**, **VOLETs 27 à 33**,
puis le backlog : persistance audit/approbation, validation des sorties d'agents, ADR-016, le linter
**Cadence** : **un VOLET par tour** — demandé par l'utilisateur le 2026-08-12.
La limite des 25 minutes de `.claude/rules/work-cadence.md` continue de s'appliquer.

Base du plan : `docs/architecture/assessment-2026-08-11.md`.

---

## La série 26–33

Huit VOLETs, dérivés des phases du brief mais **réordonnés** : chaque VOLET rend
le suivant vérifiable. Construire les agents avant qu'un modèle réponde
produirait du code que rien ne peut tester, ce que les règles du projet
interdisent.

Ce qui est déjà fait n'est pas refait : la « Phase 1 — Production Engineering »
du brief a été livrée par les quatre chantiers de mise en ligne (CI, tests,
sécurité, journalisation, Docker, publication). Il n'en reste que deux manques
réels, placés en VOLET 26.

```
VOLET 26 — Fondations mesurables                            → 6 phases
  Ce qui empêche tout le reste d'être vérifiable.
  Ch. 26.0  Souveraineté appliquée (ADR-014)                → 1 phase — **terminée**
  Ch. 26.1  Un modèle **local** qui répond (critère C1)     → 1 phase — **bloquée : `ollama serve`**
  Ch. 26.2  Résoudre AgentRuntime vs RouterEngine (C4)      → 2 phases — **terminées**
  Ch. 26.3  Traçage bout en bout router→agent→outil→modèle  → 1 phase — **terminée**
  Ch. 26.4  Le garde de dépendances rate les paquets absents → 1 phase — **terminée**

VOLET 27 — Récupération sémantique                          → 4 phases — **terminé**
  Ch. 27.1  ADR-015 : embeddings locaux, et leur prix réel  → **terminée**
  Ch. 27.2  Fournisseur d'embeddings + magasin de vecteurs  → **terminées**
  Ch. 27.3  Mémoire au sémantique, méthode rapportée        → **terminée**
  Ch. 27.4  Service de recherche au sémantique (backlog, 2026-08-12) → **terminée**

VOLET 28 — Base de connaissances                            → 4 phases — **terminé**
  Ch. 28.1  Ingestion : découpage + provenance par bloc     → **terminées**
  Ch. 28.2  Corpus de départ : 250 passages, tous vérifiables → **terminée**
  Ch. 28.3  Citation des sources + couverture mesurée       → **terminée**
  **Le corpus sénégalais dépend de toi** : il s'ingère depuis de vrais documents
  déclarés dans un manifeste (`docs/knowledge/README.md`). Rien n'a été écrit de
  mémoire — servir des affirmations inventées à un agriculteur serait le pire
  usage possible de ce dépôt.

VOLET 29 — Gestionnaire d'agents                            → 5 phases — **terminé**
  Ch. 29.1  Décomposition lue, et plus seulement produite   → **terminées**
  Ch. 29.2  Délégation bornée + tableau noir partagé        → **terminées**
  Ch. 29.3  Les agents suivent leurs tâches assignées       → **terminée**
  **Limite dite** : « raisonner » au sens d'un modèle qui délibère dépend de
  26.1. La décomposition, l'assignation et la délégation sont déterministes et
  vérifiées ; l'affinage par modèle rapporte son indisponibilité.

VOLET 30 — Routage de modèles par coût et par tâche         → 3 phases — **terminé**
  Ch. 30.1  Politique en configuration + familles SamP/ToP  → **terminées**
  Ch. 30.2  Coût ventilé par route                          → **terminée**
  **Correction de mon évaluation** : la politique existait, en dur dans
  `ProviderSelector`. Ce qui manquait : la configuration, les familles, le coût
  qui filtre vraiment — et une règle morte pointant vers des fournisseurs
  qu'ADR-014 n'inscrit plus.

VOLET 31 — Agent de développement autonome                  → 4 phases — **terminé**
  Ch. 31.1  Carte du dépôt : 278 fichiers, symboles, tests   → **terminées**
  Ch. 31.2  Boucle bornée éditer → tester → annuler          → **terminée**
  Ch. 31.3  Portillon obligatoire **par construction**       → **terminée**
  **Limite dite** : l'étape « proposer le code » appelle un modèle et dépend
  de 26.1. La boucle ne fabrique aucun code — elle applique, vérifie, annule.

VOLET 32 — Multimodal                                       → 3 phases — **terminé**
  Ch. 32.1  Transcription locale : interface + Whisper       → **terminées**
  Ch. 32.2  Image et audio branchés sur l'ingestion          → **terminée**
  **Non vérifié ici** : la transcription réelle. Les poids viennent de Hugging
  Face, qui répond 403 à travers ce mandataire. Ce qui est vérifié : le refus
  propre, le rapport, et l'ingestion d'image de bout en bout.

VOLET 33 — Infrastructure d'entraînement : SamP et ToP      → 6 phases — **terminé**
  Ch. 33.1  Capture du signal : consentement, nettoyage, export sous portillon → **terminée**
  Ch. 33.2  Barème d'évaluation + **référence mesurée : lexical = 0,40** → **terminée**
  Ch. 33.3  Décisions consignées dans `training-infrastructure.md` → **terminée**
  Ch. 33.4  Recette QLoRA+DPO — **écrite, jamais exécutée** (pas de GPU ici) → **terminée**
  Ch. 33.5  Registre de lignée : base, licence, condensat, mesures → **terminée**
  Ch. 33.6  Retour en service GGUF → **reste à faire quand un modèle existera**
```

**Total : 35 phases.**

### Le VOLET 33 et les sept piliers

| Pilier | Où il est traité |
|---|---|
| Modèles | 26 (un modèle répond), 30 (routage par coût et par tâche) |
| **Entraînement** | **33** |
| Mémoire | 27 (récupération sémantique) |
| RAG | 28 (corpus, ingestion, citation) |
| Agents | 26.2 (fusion des orchestrateurs), 29 (gestionnaire d'agents) |
| Multimodal | 32 |
| Optimisation / performance | 26.3 (traçage), 30.2 (coût mesuré par route) |

### Une recommandation d'ordre, et sa raison

**`33.1` (capture du signal) est le seul chapitre de la série dont le coût augmente chaque
jour où il n'est pas fait.** Une correction d'utilisateur non enregistrée est perdue pour
toujours ; tout le reste peut être construit plus tard sans rien perdre. Il ne dépend
d'aucun autre VOLET.

Proposition : l'exécuter **juste après le VOLET 26**, avant 27, et laisser 33.2 à 33.5 à
leur place. La série reste à une phase par tour ; seul l'ordre change. À toi de trancher.

**Un point de conception qui s'écarte du brief** : le premier modèle entraîné n'est pas un
LLM mais **le modèle d'embeddings** du VOLET 27, adapté au français et au wolof. Il
s'entraîne sur CPU ou petit GPU, son effet se mesure **sans jugement humain** (le taux de
récupération monte ou non), et il améliore recherche, mémoire et RAG d'un coup. Il prouve
la chaîne complète pour une fraction du coût d'un entraînement de LLM.

---

## Ce qui a été écarté, et pourquoi

Décidé dans `docs/architecture/assessment-2026-08-11.md`, section D. Résumé :

| Écarté | Raison en une ligne |
|---|---|
| LangGraph | Le dépôt a déjà planificateur, reprises, validation, trace et historique — 1 815 lignes. On garde l'idée d'état explicite, pas la dépendance. |
| AutoGen | Agents qui discutent jusqu'à consensus : coûteux en jetons, mal borné, contraire à la contrainte de coût du projet. |
| Haystack | Duplique le moteur de connaissances, le moteur documentaire et le service de recherche : 7 000 lignes orphelines. |
| Qdrant | Juste — quand il y aura un corpus. Sur 0 élément, c'est un service à opérer pour rien. Déclencheur : ~100 000 vecteurs. |
| PostgreSQL, Redis | Même déclencheur qu'ADR-013 : une deuxième instance. |
| OpenHands, Aider | Motifs à étudier (carte du dépôt, boucle éditer/tester), pas des dépendances : ils supposent être l'application. |
| DeepSpeed | Résout « le modèle ne tient pas en mémoire ». En QLoRA sur 7–8B, il tient. Déclencheur écrit : entraînement complet au-dessus de ~13B, ou un pas qui ne passe pas à taille de lot 1. Accelerate l'activera alors par configuration. |
| Entraînement distribué multi-nœuds | Zéro donnée d'entraînement aujourd'hui. Construire un cluster avant d'avoir 5 000 exemples serait le travail le plus spéculatif du dépôt. |
| RLHF classique (PPO + modèle de récompense) | Trois modèles en mémoire, instable, cher à régler. **DPO** entraîne directement sur des paires de préférences et répond au même besoin. |
| Axolotl, Weights & Biases | Une seconde culture de configuration, et un service hébergé pour quelques dizaines d'exécutions. Un manifeste à côté du point de reprise répond à la même question. |

**Retenus** : Sentence Transformers (VOLET 27, avec ADR pour le prix réel :
~90 Mo de poids et PyTorch), Whisper (VOLET 32, en dernier), et pour le VOLET 33
**Accelerate + PEFT (QLoRA) + TRL (DPO) + conversion GGUF** — l'efficacité à
petite échelle, jamais l'échelle elle-même.

---

## Souveraineté — ce que la direction change au plan

Décidé dans **ADR-014** : la plateforme ne dépend d'aucun modèle tiers à l'exécution.
Ses modèles sont les familles **SamP** et **ToP**.

Trois conséquences concrètes sur ce plan :

1. **`26.1` n'a plus qu'un seul chemin.** « Ollama **ou** une clé fournisseur » devient
   « un modèle local ». Le critère C1 se ferme avec `ollama serve`, pas avec une clé.
2. **`26.0` est ajouté** : les trois fournisseurs hébergés ne doivent plus être
   seulement inertes faute de clé, ils ne doivent plus être **inscrits**. Un fournisseur
   absent du registre ne peut être choisi par aucun chemin. Le test qui compte : mode
   souverain actif, toutes les clés hébergées présentes, et aucun point d'accès externe
   joignable depuis le chemin des modèles.
3. **Le VOLET 33 produit SamP et ToP**, par adaptation d'une base **Apache-2.0**
   (Qwen 2.5, Mistral 7B v0.3). La licence Llama impose « Built with Llama » dans le nom
   et l'affichage : incompatible avec l'identité SamP/ToP, donc écartée pour cette raison
   seule.

**Ce que la souveraineté d'exécution donne dès l'étape S1/S2 d'ADR-014** : aucun serveur
tiers, aucune clé, aucune donnée qui sort de la machine. **Ce qu'elle ne donne pas encore** :
des poids qui ne doivent rien à personne — c'est l'étape S3 (préentraînement continu sur
le corpus du VOLET 28), et elle se chiffre en milliers d'heures de GPU. Les deux axes sont
tenus séparés dans l'ADR pour que le premier ne soit pas retardé par le second.

---

## Règle de conduite pour cette série

Chaque phase commence par **mesurer l'existant** avant d'écrire quoi que ce soit :
le dépôt fait 387 fichiers Python et la moitié du travail de la série 01–25 a
consisté à découvrir que ce qui était déclaré n'était pas branché. Une phase qui
ajoute un module là où un module existait déjà est une régression, pas un progrès.
