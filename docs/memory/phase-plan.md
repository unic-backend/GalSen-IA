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

## La série 26–32

Sept VOLETs, dérivés des sept phases du brief mais **réordonnés** : chaque VOLET
rend le suivant vérifiable. Construire les agents avant qu'un modèle réponde
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
```

**Total : 28 phases.**

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

**Retenus** : Sentence Transformers (VOLET 27, avec ADR pour le prix réel :
~90 Mo de poids et PyTorch) et Whisper (VOLET 32, en dernier).

---

## Règle de conduite pour cette série

Chaque phase commence par **mesurer l'existant** avant d'écrire quoi que ce soit :
le dépôt fait 387 fichiers Python et la moitié du travail de la série 01–25 a
consisté à découvrir que ce qui était déclaré n'était pas branché. Une phase qui
ajoute un module là où un module existait déjà est une régression, pas un progrès.
