# =============================================================================
# GalSen IA — Image Docker de production
# =============================================================================
# Construction :
#   docker build -t galsen-ia:latest .
#
# Exécution :
#   docker run -p 8000:8000 --env-file .env galsen-ia:latest
#
# L'image est construite en deux étapes pour minimiser la taille finale.
# =============================================================================

# ---------------------------------------------------------------------------
# Étape 1 : Construction des dépendances
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS builder

# Empêcher la création de fichiers .pyc et le buffering des logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Installer les outils de compilation nécessaires pour certaines dépendances
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Créer un environnement virtuel pour isoler les dépendances
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copier et installer les dépendances Python.
# `requirements.txt` ne contient que l'exécution : pytest et le client HTTP de
# test vivent dans `requirements-dev.txt` et n'ont rien à faire dans une image
# exposée au réseau.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ---------------------------------------------------------------------------
# Étape 2 : Image de production
# ---------------------------------------------------------------------------
FROM python:3.11-slim AS production

# Version de l'image. Docker ne peut pas importer src/version.py : la valeur est
# donc redéclarée ici, et tests/test_version.py échoue si les deux s'écartent.
ARG GALSEN_VERSION=0.1.0

# Métadonnées de l'image
LABEL org.opencontainers.image.title="GalSen IA" \
      org.opencontainers.image.description="Plateforme IA modulaire pour le Sénégal et l'Afrique" \
      org.opencontainers.image.version="${GALSEN_VERSION}" \
      org.opencontainers.image.vendor="GalSen IA"

# Empêcher la création de fichiers .pyc et le buffering des logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Créer un utilisateur non-root pour l'exécution
RUN groupadd --system galsen && \
    useradd --system --no-log-init --gid galsen --home /app galsen

# Installer uniquement les dépendances d'exécution légères
# curl est nécessaire pour le healthcheck Docker
# `curl` sert au healthcheck ; `tesseract-ocr` et ses données françaises servent
# à l'OCR. Beaucoup de documents officiels de la région sont des numérisations :
# sans le binaire, `pytesseract` n'est qu'une enveloppe vide et l'ingestion
# accepte une image sans en tirer une ligne de texte (VOLET 28, VOLET 32).
# `tesseract-ocr-fra` pèse quelques mégaoctets et évite de reconnaître le
# français avec un modèle anglais, qui rend un texte lisible et faux.
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copier l'environnement virtuel depuis l'étape de construction
COPY --from=builder /opt/venv /opt/venv

# Définir le répertoire de travail
WORKDIR /app

# Copier le code source (dans l'ordre : fichiers les moins changeants en premier)
COPY requirements.txt .
COPY src/ src/
COPY tools/ tools/

# Registres lus à l'exécution, à la racine du projet.
#
# Ils manquaient : l'image ne contenait que `src/` et `tools/`, si bien que
# `RouterEngine` — qui lit config/settings.yaml, agents/registry.yaml et
# workflows/workflows.yaml — échouait dans le conteneur alors qu'il passait en
# local. Les routes /workflow/* étaient donc en panne dès la mise en image, et
# rien ne le montrait parce que la CI ne construit pas l'image.
#
# `agents/` porte aussi les modules Python des agents : le répartiteur les
# importe par leur chemin de module (`agents.planner.agent`), pas seulement
# leur déclaration YAML.
#
# `tests/test_docker_image_contents.py` échoue si un nouveau répertoire lu à
# l'exécution n'est pas ajouté ici.
COPY config/ config/
COPY agents/ agents/
COPY workflows/ workflows/

# Créer le répertoire de données pour le stockage persistant
RUN mkdir -p /app/data && \
    chown -R galsen:galsen /app

# Basculer vers l'utilisateur non-root
USER galsen

# Exposer le port de l'API
EXPOSE 8000

# Healthcheck utilisant l'endpoint /health existant
# Vérifie que l'API répond avec un statut valide (healthy, degraded ou unhealthy)
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -sf http://localhost:8000/health || exit 1

# Commande de démarrage
# uvicorn écoute sur 0.0.0.0 pour accepter les connexions depuis l'extérieur du conteneur
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000"]
