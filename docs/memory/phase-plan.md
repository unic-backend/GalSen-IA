# Phase Plan

Où en est le découpage en phases du travail en cours.
Protocole complet → `.claude/rules/phase-protocol.md`.

Ce fichier est chargé au démarrage de chaque session : il dit quelle phase
exécuter, et une seule.

---

**VOLET en cours** : **26 — Fondations mesurables**
**Phase courante** : 26.1 — en attente de confirmation
**Terminées** : VOLETs 01 à 25 (série des manuels), 4 chantiers de mise en ligne
**Cadence** : **une phase par tour** (défaut).

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
VOLET 26 — Fondations mesurables                            → 5 phases
  Ce qui empêche tout le reste d'être vérifiable.
  Ch. 26.1  Un modèle qui répond (critère C1)               → 1 phase (indivisible)
  Ch. 26.2  Résoudre AgentRuntime vs RouterEngine (C4)      → 2 phases (26.2 mesure, 26.3 fusion)
  Ch. 26.3  Traçage bout en bout router→agent→outil→modèle  → 1 phase
  Ch. 26.4  Le garde de dépendances rate les paquets absents → 1 phase

VOLET 27 — Récupération sémantique                          → 4 phases
  Aujourd'hui tout est du Jaccard sur des jetons.
  Ch. 27.1  ADR : embeddings locaux, et leur prix réel      → 1 phase (indivisible)
  Ch. 27.2  Fournisseur d'embeddings + magasin de vecteurs  → 2 phases
  Ch. 27.3  Mémoire et recherche passent au sémantique      → 1 phase

VOLET 28 — Une base de connaissances qui contient quelque chose → 4 phases
  Le RAG sur 0 élément ne prouve rien.
  Ch. 28.1  Ingestion de documents (le moteur existe)       → 2 phases
  Ch. 28.2  Un corpus de départ : Sénégal, agriculture, santé → 1 phase
  Ch. 28.3  Citation des sources, mesurée                   → 1 phase

VOLET 29 — Gestionnaire d'agents                            → 5 phases
  Ch. 29.1  Décomposition d'objectif                        → 2 phases
  Ch. 29.2  Délégation et état partagé entre agents         → 2 phases
  Ch. 29.3  Les neuf agents raisonnent au lieu d'exécuter   → 1 phase

VOLET 30 — Routage de modèles par coût et par tâche         → 3 phases
  Le moteur existe (6 423 lignes) ; la politique n'existe pas.
  Ch. 30.1  Politique : question simple → petit modèle      → 2 phases
  Ch. 30.2  Mesure du coût et de la qualité par route       → 1 phase

VOLET 31 — Agent de développement autonome                  → 4 phases
  Ch. 31.1  Carte du dépôt (motif OpenHands/Aider, pas leur code) → 2 phases
  Ch. 31.2  Boucle éditer → tester → corriger               → 1 phase
  Ch. 31.3  Passage obligatoire par le portillon (ADR-006)  → 1 phase

VOLET 32 — Multimodal                                       → 3 phases
  Ch. 32.1  Parole vers texte (Whisper local)               → 2 phases
  Ch. 32.2  Le moteur vision branché sur l'ingestion        → 1 phase

VOLET 33 — Infrastructure d'entraînement                    → 5 phases
  Conception → `docs/architecture/training-infrastructure.md`.
  Ch. 33.1  Capture du signal (corrections, préférences)    → 1 phase  ← à exécuter tôt
  Ch. 33.2  Jeu d'évaluation français/wolof, avant tout entraînement → 1 phase
  Ch. 33.3  ADR : LoRA/QLoRA + DPO, ce qui est écarté       → 1 phase (indivisible)
  Ch. 33.4  Recette d'entraînement (accelerate + peft + trl) → 1 phase
  Ch. 33.5  Retour en service : fusion, GGUF, Ollama, mesure → 1 phase
```

**Total : 33 phases.**

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

## Règle de conduite pour cette série

Chaque phase commence par **mesurer l'existant** avant d'écrire quoi que ce soit :
le dépôt fait 387 fichiers Python et la moitié du travail de la série 01–25 a
consisté à découvrir que ce qui était déclaré n'était pas branché. Une phase qui
ajoute un module là où un module existait déjà est une régression, pas un progrès.
