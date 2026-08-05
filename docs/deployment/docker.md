# GalSen IA — Docker Deployment Guide

## Quick Start

```bash
# 1. Configurer l'environnement
cp .env.example .env
# Éditer .env et définir au moins GALSEN_API_KEYS

# 2. Construire et démarrer
docker-compose up -d

# 3. Vérifier que l'API répond
curl http://localhost:8000/health
```

## Build the Docker Image

```bash
# Construction standard
docker build -t galsen-ia:latest .

# Construction sans cache (build propre)
docker build --no-cache -t galsen-ia:latest .
```

## Run with Docker (without Compose)

```bash
# Mode production (stockage SQLite persistant)
docker run -d \
  --name galsen-ia \
  -p 8000:8000 \
  -v galsen_data:/app/data \
  --env-file .env \
  galsen-ia:latest

# Mode développement (rechargement automatique)
docker run -d \
  --name galsen-ia-dev \
  -p 8001:8000 \
  -v $(pwd)/src:/app/src:ro \
  -v galsen_data_dev:/app/data \
  -e GALSEN_API_KEYS=dev-key \
  -e GALSEN_RATE_LIMIT_ENABLED=false \
  galsen-ia:latest \
  uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
```

## Docker Compose Services

### `api` (Production)

- **Image** : Construite depuis `Dockerfile` (étape `production`)
- **Port** : `8000` (configurable via `GALSEN_PORT`)
- **Volumes** : `galsen_data` (stockage SQLite), `galsen_logs`
- **Healthcheck** : `curl -sf http://localhost:8000/health` toutes les 30s
- **Restart** : `unless-stopped`

### `api-dev` (Development)

- **Port** : `8001` (configurable via `GALSEN_DEV_PORT`)
- **Volumes** : Code source monté en lecture seule (`./src:/app/src:ro`)
- **Rechargement automatique** : `--reload` activé
- **Rate limiting** : Désactivé par défaut

## Environment Variables

| Variable | Défaut | Description |
|---|---|---|
| `GALSEN_STORAGE_BACKEND` | `sqlite` | `sqlite` (persistant) ou `in-memory` |
| `GALSEN_API_KEYS` | *(requis)* | Clés API séparées par des virgules |
| `GALSEN_RATE_LIMIT_ENABLED` | `true` | Active/désactive le limiteur de taux |
| `GALSEN_RATE_LIMIT_AUTHENTICATED_RPM` | `60` | Requêtes/min (clients authentifiés) |
| `GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM` | `30` | Requêtes/min (clients non authentifiés) |
| `GALSEN_RATE_LIMIT_BURST_MULTIPLIER` | `2.0` | Multiplicateur de pics |
| `GALSEN_PORT` | `8000` | Port HTTP du service principal |
| `GALSEN_DEV_PORT` | `8001` | Port HTTP du service de développement |
| `OPENAI_API_KEY` | *(optionnel)* | Clé API OpenAI |
| `ANTHROPIC_API_KEY` | *(optionnel)* | Clé API Anthropic |
| `GOOGLE_API_KEY` | *(optionnel)* | Clé API Google |
| `OLLAMA_HOST` | *(optionnel)* | URL du serveur Ollama local |

See `.env.example` for the complete list with descriptions.

## Health Endpoints

| Endpoint | Description | Code |
|---|---|---|
| `GET /health` | Rapport de santé détaillé | 200 |
| `GET /ready` | Readiness probe | 200 / 503 |
| `GET /live` | Liveness probe | 200 |

## Data Persistence

Le stockage SQLite (`GALSEN_STORAGE_BACKEND=sqlite`) utilise le répertoire `/app/data`
dans le conteneur, monté sur le volume nommé `galsen_data`.

```bash
# Sauvegarde des données
docker run --rm -v galsen_data:/data -v $(pwd):/backup alpine \
  cp -r /data /backup/galsen-backup

# Restauration
docker run --rm -v galsen_data:/data -v $(pwd):/backup alpine \
  cp -r /backup/galsen-backup/* /data/
```

## Image Size Optimization

- **Base** : `python:3.11-slim` (~125 MB)
- **Multi-stage build** : Les dépendances de compilation ne sont pas incluses
- **No-cache pip** : `pip install --no-cache-dir`
- **.dockerignore** : Exclut tests, docs, caches, IDE files

## Kubernetes Compatibility

L'image est compatible Kubernetes :
- Endpoints `/health`, `/ready`, `/live` pour les probes
- Utilisateur non-root (`galsen`)
- Variables d'environnement pour toute la configuration
- Stateless (les données sont dans un volume externe)
- Signal handling : uvicorn gère SIGTERM/SIGINT proprement

### Exemple de Deployment Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: galsen-ia
spec:
  replicas: 2
  selector:
    matchLabels:
      app: galsen-ia
  template:
    metadata:
      labels:
        app: galsen-ia
    spec:
      containers:
        - name: api
          image: galsen-ia:latest
          ports:
            - containerPort: 8000
          env:
            - name: GALSEN_STORAGE_BACKEND
              value: "sqlite"
            - name: GALSEN_API_KEYS
              valueFrom:
                secretKeyRef:
                  name: galsen-secrets
                  key: api-keys
          livenessProbe:
            httpGet:
              path: /live
              port: 8000
            initialDelaySeconds: 15
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              memory: "256Mi"
              cpu: "500m"
            limits:
              memory: "2Gi"
              cpu: "2"
```

## Troubleshooting

```bash
# Voir les logs
docker-compose logs -f api

# Vérifier le healthcheck
docker inspect galsen-ia-api --format='{{json .State.Health}}' | python -m json.tool

# Entrer dans le conteneur
docker exec -it galsen-ia-api bash

# Redémarrer après modification de .env
docker-compose down && docker-compose up -d

# Reconstruire l'image après modification du code
docker-compose build --no-cache && docker-compose up -d
```
