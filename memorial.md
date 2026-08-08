# Mémorial GalSen IA

Ce fichier décrit l'état complet du projet pour un agent IA (Cerveau) qui arrive froid.

## Arborescence

```
C:\GalSen IA
├── agents/              # Agents spécialisés (planner, coder, reviewer, etc.)
│   ├── registry.yaml    # Registre des 10 agents
│   └── */agent.py       # Chaque agent dans son dossier
├── config/
│   └── settings.yaml    # Configuration générale
├── docs/
│   ├── memory/          # Mémoire persistante du projet (À LIRE avant toute action)
│   │   ├── vision.md
│   │   ├── priorities.md
│   │   ├── current-objectives.md
│   │   ├── pending-work.md
│   │   ├── completed-work.md
│   │   ├── session-state.md
│   │   └── knowledge-index.md
│   ├── architecture/    # Overview + ADRs (décisions d'architecture)
│   └── standards/       # Standards de code
├── prompts/
│   └── systeme.md       # Instruction système pour le Cerveau
├── src/
│   ├── router/          # Routeur — aiguille les requêtes
│   ├── agent/           # Runtime des agents
│   ├── tool/            # Moteur d'outils
│   ├── memory_engine/   # Mémoire court/long terme
│   ├── model_engine/    # Moteur de modèles IA (Ollama + providers)
│   ├── knowledge_engine/# Base de connaissances RAG
│   ├── document_intelligence_engine/  # Documents
│   └── vision_intelligence_engine/    # Vision
├── models/models.yaml   # Catalogue des modèles
├── tools/tools.yaml     # Déclaration des 18 outils
├── serveur_cerveau.py   # SERVEUR LOCAL — point d'entrée API REST
├── Lancer_GalSen_IA.bat # LANCEUR — démarre serveur + Claude Code
└── test_*.py            # Tests unitaires (~300 tests)
```

## État actuel

- **Foundation terminée :** mémoire, standards, ADR-001 à ADR-006
- **8 engines implémentés :** routeur, runtime, outils, mémoire, modèles, connaissances, documents, vision
- **10 agents déclarés :** planner, researcher, coder, reviewer, tester, security, documentation, deployment, monitor + router
- **18 outils déclarés, 5 implémentés :** filesystem, terminal, git, github, web_search, model
- **Tests :** ~300 tests passent, 0 échec
- **Stockage :** tout est in-memory — pas de persistance
- **Providers :** Ollama est le seul provider qui génère réellement (localhost:11434)
  Les providers OpenAI/Anthropic/Google sont déclarés mais pas de credentials

## Modèle local disponible

- **Ollama** : qwen2.5-coder:14b (9 Go, bon pour code et raisonnement)
- **API Ollama** : `http://localhost:11434/api/generate`
- **Port API** : 11434 (configurable dans .env)

## Pour démarrer

1. Lancer `Lancer_GalSen_IA.bat` — démarre le serveur GalSen IA + Claude Code
2. Accéder à `http://localhost:8000/docs` pour l'API REST
3. Le serveur expose : `/health`, `/chat`, `/engines`, `/models`