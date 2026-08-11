# GalSen IA — Docker Deployment Guide

## Quick Start

```bash
# 1. Configurer l'environnement
cp .env.example .env
# Éditer .env et définir au moins :
#   GALSEN_API_KEYS   — les clés d'accès
#   GALSEN_DOMAIN     — le domaine servi, qui doit pointer sur cette machine
#   GALSEN_TLS_EMAIL  — l'adresse de contact Let's Encrypt

# 2. Construire et démarrer (api + caddy)
docker compose up -d

# 3. Vérifier que l'API répond, en HTTPS, à travers le proxy
curl https://$GALSEN_DOMAIN/health

# 4. Vérifier que la redirection HTTP fonctionne
curl -I http://$GALSEN_DOMAIN/health   # attendu : 308 vers https://
```

L'application **ne publie aucun port sur l'hôte**. `curl http://localhost:8000/health`
ne répond plus depuis l'extérieur du réseau Docker, et c'est voulu (ADR-012) : un
port 8000 publié serait une route en clair contournant TLS et le journal du proxy.
Pour interroger l'API sans passer par le proxy :

```bash
docker compose exec api curl -sf http://localhost:8000/health
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
# Sur une machine locale, sans proxy devant (essai, développement)
docker run -d \
  --name galsen-ia \
  -p 127.0.0.1:8000:8000 \
  -v galsen_data:/app/data \
  --env-file .env \
  galsen-ia:latest
```

Le port est lié à `127.0.0.1` : sans proxy devant, la publier sur toutes les
interfaces exposerait l'API en clair. **Un déploiement joignable depuis Internet
passe par Compose**, qui démarre Caddy — voir *HTTPS / TLS* plus bas.

## HTTPS / TLS

Le chemin d'une requête est : `Internet → HTTPS → Caddy → api:8000` sur le
réseau Docker interne. Le raisonnement complet est dans
`docs/architecture/decisions/012-tls-termination.md` ; l'essentiel pour opérer :

**Ce que Caddy fait sans configuration** : obtenir le certificat, le renouveler,
rediriger HTTP vers HTTPS en 308, et poser `X-Forwarded-For` / `X-Forwarded-Proto`.

**Ce que l'opérateur doit faire** :

1. Faire pointer `GALSEN_DOMAIN` sur l'adresse publique de la machine (enregistrement A/AAAA).
2. Ouvrir les ports **80 et 443** dans le pare-feu. Le 80 n'est pas facultatif :
   c'est par lui que passe le défi ACME. Sans lui, aucun certificat.
3. Renseigner `GALSEN_TLS_EMAIL` — Let's Encrypt y envoie les avertissements d'expiration.
4. Déclarer le réseau du proxy dans `GALSEN_TRUSTED_PROXIES` (voir ci-dessous).

**`GALSEN_TRUSTED_PROXIES` n'est pas optionnel derrière un proxy.** L'application
ne croit les en-têtes `X-Forwarded-*` que s'ils viennent d'une source déclarée.
Les deux erreurs possibles, et ce qu'elles coûtent :

| Réglage | Conséquence |
|---|---|
| Non déclaré | Toutes les requêtes semblent venir de Caddy : la limite par adresse devient globale, et le détecteur de menaces ne distingue plus les sources. Restrictif, donc sûr, mais faux. |
| Déclaré trop large (`0.0.0.0/0`) | N'importe quel appelant peut forger son adresse : quota illimité et invisibilité du détecteur. **À ne jamais faire.** |

La valeur par défaut de Compose, `172.16.0.0/12`, couvre le réseau bridge de
Docker. Un `docker network inspect galsen-network` donne le sous-réseau réel si
l'installation en utilise un autre.

Le certificat vit dans le volume `caddy_data`. **Ne le supprimez pas** : chaque
repartance à zéro redemande un certificat et se heurte aux limites de Let's
Encrypt (cinq échecs par heure et par domaine).

```bash
# Essai local, sans domaine public : Caddy émet un certificat interne
GALSEN_DOMAIN=localhost docker compose up -d
curl -k https://localhost/health

# Journal du proxy (JSON) — c'est là qu'apparaît un échec ACME
docker compose logs -f caddy
```

## Docker Compose Services

### `api` (Production)

- **Image** : Construite depuis `Dockerfile` (étape `production`)
- **Port** : `expose: 8000`, **non publié sur l'hôte** — joignable seulement par Caddy
- **Volumes** : `galsen_data` (stockage SQLite), `galsen_logs`
- **Healthcheck** : `curl -sf http://localhost:8000/health` toutes les 30s
- **Restart** : `unless-stopped`

### `caddy` (TLS)

- **Image** : `caddy:2-alpine`
- **Ports** : `80`, `443`, `443/udp` (QUIC)
- **Configuration** : `./Caddyfile` monté en lecture seule
- **Volumes** : `caddy_data` (certificats et clés privées), `caddy_config`
- **Démarrage** : après que `api` soit `healthy`

### `api-dev` (Development)

Sous profil : **ne démarre pas** avec `docker compose up`. Il tournait auparavant
à côté de `api` — une deuxième instance de la plateforme, ce que ADR-009 interdit.

```bash
docker compose --profile dev up api-dev
```

- **Port** : `8001` (configurable via `GALSEN_DEV_PORT`)
- **Volumes** : Code source monté en lecture seule (`./src:/app/src:ro`)
- **Rechargement automatique** : `--reload` activé
- **Rate limiting** : Désactivé par défaut

## Environment Variables

| Variable | Défaut | Description |
|---|---|---|
| `GALSEN_STORAGE_BACKEND` | `sqlite` | `sqlite` (persistant) ou `in-memory` |
| `GALSEN_API_KEYS` | *(requis)* | Clés API séparées par des virgules |
| `GALSEN_DOMAIN` | `localhost` | Domaine servi par Caddy, pour le certificat |
| `GALSEN_TLS_EMAIL` | *(vide)* | Contact Let's Encrypt (avertissements d'expiration) |
| `GALSEN_TRUSTED_PROXIES` | `172.16.0.0/12` | Sources dont les en-têtes `X-Forwarded-*` sont crus |
| `GALSEN_BACKUP_DIR` | `data/backups` | Destination des sauvegardes `VACUUM INTO` |
| `GALSEN_RATE_LIMIT_ENABLED` | `true` | Active/désactive le limiteur de taux |
| `GALSEN_RATE_LIMIT_AUTHENTICATED_RPM` | `60` | Requêtes/min (clients authentifiés) |
| `GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM` | `30` | Requêtes/min (clients non authentifiés) |
| `GALSEN_RATE_LIMIT_BURST_MULTIPLIER` | `2.0` | Multiplicateur de pics |
| `GALSEN_PORT` | `8000` | Port du Cerveau local (`serveur_cerveau.py`) — l'API en Compose ne publie plus de port |
| `GALSEN_DEV_PORT` | `8001` | Port HTTP du service de développement (profil `dev`) |
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

**Ne copiez pas le volume avec `cp`.** Copier un fichier SQLite ouvert peut
produire une base corrompue — l'écriture en cours n'est pas atomique du point de
vue du copieur — et depuis que les bases tournent en mode WAL, les écritures
récentes vivent dans un fichier `-wal` séparé qu'une copie du seul `.sqlite`
laisserait derrière. La procédure `cp -r` qui figurait ici était fausse.

`scripts/backup.py` passe par `VACUUM INTO`, qui écrit une copie **cohérente**
pendant que l'application continue d'écrire.

```bash
# Sauvegarde à chaud, sans arrêter le service
docker compose exec api python scripts/backup.py sauvegarder

# Lister les sauvegardes existantes
docker compose exec api python scripts/backup.py lister

# Restauration — le service doit être arrêté
docker compose stop api
docker compose run --rm api python scripts/backup.py restaurer 2026-08-11T18-30-00
docker compose start api
```

Les sauvegardes vivent dans `GALSEN_BACKUP_DIR` (défaut `data/backups`), donc
dans le volume `galsen_data`. **Pour survivre à la perte du volume, elles doivent
en sortir** : montez un second volume ou copiez le répertoire de sauvegardes
ailleurs — lui peut se copier avec `cp`, puisque `VACUUM INTO` a déjà produit des
fichiers fermés et cohérents.

```bash
docker run --rm -v galsen_data:/data -v $(pwd):/hors-site alpine \
  cp -r /data/backups /hors-site/galsen-sauvegardes
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
  # Une seule instance. ADR-009 : les compteurs de débit, les révocations de clés
  # et le magasin SQLite vivent dans le processus et son volume ; deux répliques
  # donneraient deux vérités, dont une clé révoquée qui reste valide sur l'autre.
  replicas: 1
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
