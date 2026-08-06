"""
Limiteur de taux pour l'API GalSen IA.

Fournit un limiteur de taux configurable pour les endpoints de l'API REST,
avec des limites différentes pour les requêtes authentifiées et non authentifiées.
Utilise l'algorithme du seau à jetons (token bucket) pour un contrôle précis.

Conçu pour une migration future vers Redis : l'interface APIRateLimiter permet
de remplacer l'implémentation en mémoire par une version distribuée sans
modifier le code appelant.

Variables d'environnement :
    GALSEN_RATE_LIMIT_ENABLED : Active/désactive le limiteur ("true"/"false", défaut "true")
    GALSEN_RATE_LIMIT_AUTHENTICATED_RPM : Requêtes/min pour clients authentifiés (défaut 60)
    GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM : Requêtes/min pour clients non authentifiés (défaut 30)
    GALSEN_RATE_LIMIT_BURST_MULTIPLIER : Multiplicateur de rafale (défaut 2.0)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import os
import threading
import time

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security.api_key import APIKeyHeader

from src.api.rbac import hash_api_key, key_fingerprint

# ---------------------------------------------------------------------------
# Modèles de données
# ---------------------------------------------------------------------------


@dataclass
class RateLimitConfig:
    """Configuration du limiteur de taux.

    Tous les champs peuvent être surchargés via les variables d'environnement.
    """

    enabled: bool = True
    authenticated_rpm: int = 60
    unauthenticated_rpm: int = 30
    burst_multiplier: float = 2.0

    @classmethod
    def from_env(cls) -> "RateLimitConfig":
        """Crée une configuration à partir des variables d'environnement.

        Returns:
            Instance de RateLimitConfig configurée.
        """
        return cls(
            enabled=_env_bool("GALSEN_RATE_LIMIT_ENABLED", True),
            authenticated_rpm=_env_int("GALSEN_RATE_LIMIT_AUTHENTICATED_RPM", 60),
            unauthenticated_rpm=_env_int("GALSEN_RATE_LIMIT_UNAUTHENTICATED_RPM", 30),
            burst_multiplier=_env_float("GALSEN_RATE_LIMIT_BURST_MULTIPLIER", 2.0),
        )


@dataclass
class RateLimitInfo:
    """Informations sur l'état actuel du limiteur de taux pour un client.

    Ces informations sont incluses dans les en-têtes HTTP de la réponse.
    """

    limit: int
    remaining: int
    reset_at: float
    retry_after: float


# ---------------------------------------------------------------------------
# Interface abstraite (pour migration future vers Redis)
# ---------------------------------------------------------------------------


class APIRateLimiter(ABC):
    """Interface abstraite pour le limiteur de taux de l'API.

    Cette abstraction permet de remplacer l'implémentation en mémoire
    par une version distribuée (Redis, etc.) sans modifier le code
    des endpoints ou des dépendances FastAPI.
    """

    @abstractmethod
    def is_allowed(
        self, client_id: str, is_authenticated: bool
    ) -> Tuple[bool, RateLimitInfo]:
        """Vérifie si une requête est autorisée selon les limites de taux.

        Args:
            client_id: Identifiant unique du client (clé API ou adresse IP).
            is_authenticated: True si le client est authentifié par clé API valide.

        Returns:
            Tuple (autorisé, informations sur la limite).
        """
        ...

    @abstractmethod
    def reset(self, client_id: str) -> None:
        """Réinitialise le compteur de taux pour un client spécifique.

        Utile pour les tests ou lors de la rotation des clés API.

        Args:
            client_id: Identifiant du client à réinitialiser.
        """
        ...


# ---------------------------------------------------------------------------
# Implémentation en mémoire (token bucket)
# ---------------------------------------------------------------------------


class InMemoryRateLimiter(APIRateLimiter):
    """Implémentation en mémoire du limiteur de taux.

    Utilise l'algorithme du seau à jetons (token bucket) :
    - Chaque client possède un seau avec une capacité maximale (rafale).
    - Les jetons sont ajoutés à un taux constant (RPM / 60 par seconde).
    - Chaque requête consomme 1 jeton.
    - Si le seau est vide, la requête est refusée (HTTP 429).

    Thread-safe grâce à un verrou réentrant.
    """

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialise le limiteur de taux en mémoire.

        Args:
            config: Configuration des limites de taux.
        """
        self._config = config
        self._buckets: Dict[str, Dict[str, float]] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Méthodes privées
    # ------------------------------------------------------------------

    def _ensure_bucket(
        self, client_id: str, capacity: float, fill_rate: float
    ) -> Dict[str, float]:
        """Obtient ou crée le seau à jetons pour un client.

        Args:
            client_id: Identifiant du client.
            capacity: Capacité maximale du seau (en jetons).
            fill_rate: Taux de remplissage (jetons par seconde).

        Returns:
            Le dictionnaire représentant le seau à jetons.
        """
        if client_id not in self._buckets:
            self._buckets[client_id] = {
                "tokens": capacity,
                "last_update": time.time(),
                "capacity": capacity,
                "fill_rate": fill_rate,
            }
        return self._buckets[client_id]

    # ------------------------------------------------------------------
    # Interface publique
    # ------------------------------------------------------------------

    def is_allowed(
        self, client_id: str, is_authenticated: bool
    ) -> Tuple[bool, RateLimitInfo]:
        """Vérifie si une requête est autorisée selon les limites de taux.

        Args:
            client_id: Identifiant unique du client.
            is_authenticated: True si le client est authentifié.

        Returns:
            Tuple (autorisé, informations sur la limite).
        """
        # Si le limiteur est désactivé, tout est autorisé
        if not self._config.enabled:
            return True, RateLimitInfo(
                limit=0,
                remaining=0,
                reset_at=0.0,
                retry_after=0.0,
            )

        # Sélectionner la limite selon le niveau d'authentification
        rpm = (
            self._config.authenticated_rpm
            if is_authenticated
            else self._config.unauthenticated_rpm
        )

        # Calculer les paramètres du seau
        capacity = float(rpm) * self._config.burst_multiplier
        fill_rate = rpm / 60.0

        with self._lock:
            bucket = self._ensure_bucket(client_id, capacity, fill_rate)
            now = time.time()

            # Mettre à jour les paramètres si la configuration a changé
            bucket["capacity"] = capacity
            bucket["fill_rate"] = fill_rate

            # Ajouter les jetons accumulés depuis la dernière requête
            elapsed = now - bucket["last_update"]
            bucket["tokens"] = min(capacity, bucket["tokens"] + elapsed * fill_rate)
            bucket["last_update"] = now

            # Une requête coûte 1 jeton
            cost = 1.0

            if bucket["tokens"] >= cost:
                bucket["tokens"] -= cost
                remaining = max(0, int(bucket["tokens"]))
                reset_at = now + (cost / fill_rate)
                return True, RateLimitInfo(
                    limit=rpm,
                    remaining=remaining,
                    reset_at=reset_at,
                    retry_after=0.0,
                )
            else:
                # Calculer le temps d'attente estimé avant de pouvoir émettre
                retry_after = (cost - bucket["tokens"]) / fill_rate
                return False, RateLimitInfo(
                    limit=rpm,
                    remaining=0,
                    reset_at=now + retry_after,
                    retry_after=retry_after,
                )

    def reset(self, client_id: str) -> None:
        """Réinitialise le compteur de taux pour un client spécifique.

        Args:
            client_id: Identifiant du client à réinitialiser.
        """
        with self._lock:
            self._buckets.pop(client_id, None)


# ---------------------------------------------------------------------------
# Fonctions utilitaires d'environnement
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool) -> bool:
    """Lit une variable d'environnement comme booléen.

    Args:
        name: Nom de la variable d'environnement.
        default: Valeur par défaut si absente.

    Returns:
        La valeur booléenne.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes", "on")


def _env_int(name: str, default: int) -> int:
    """Lit une variable d'environnement comme entier.

    Args:
        name: Nom de la variable d'environnement.
        default: Valeur par défaut si absente ou invalide.

    Returns:
        La valeur entière.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except (ValueError, TypeError):
        return default


def _env_float(name: str, default: float) -> float:
    """Lit une variable d'environnement comme flottant.

    Args:
        name: Nom de la variable d'environnement.
        default: Valeur par défaut si absente ou invalide.

    Returns:
        La valeur flottante.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw.strip())
    except (ValueError, TypeError):
        return default


def _get_client_ip(request: Request) -> str:
    """Extrait l'adresse IP du client depuis la requête.

    Gère les proxys inverses en vérifiant les en-têtes standards.

    Args:
        request: La requête FastAPI.

    Returns:
        L'adresse IP du client sous forme de chaîne.
    """
    # Vérifier les en-têtes de proxy pour l'IP réelle
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # Prendre la première IP de la liste (celle du client d'origine)
        return forwarded.split(",")[0].strip()

    # Fallback sur l'IP directe
    if request.client and request.client.host:
        return request.client.host

    # Dernier recours
    return "unknown"


# ---------------------------------------------------------------------------
# Singleton et dépendance FastAPI
# ---------------------------------------------------------------------------

# Singleton du limiteur de taux, initialisé une seule fois par processus
_rate_limiter: Optional[APIRateLimiter] = None
_rate_limiter_lock = threading.Lock()

# Référence au header API Key (doit correspondre à celui de server.py)
API_KEY_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Condensés des clés API valides (surchargés par server.py au démarrage).
# Le limiteur reconnaît un client authentifié sans jamais détenir sa clé.
_valid_key_digests: set = set()


def get_rate_limiter() -> APIRateLimiter:
    """Retourne l'instance singleton du limiteur de taux.

    Crée l'instance à la première demande en utilisant la configuration
    issue des variables d'environnement.

    Returns:
        L'instance du limiteur de taux.
    """
    global _rate_limiter
    if _rate_limiter is None:
        with _rate_limiter_lock:
            if _rate_limiter is None:
                config = RateLimitConfig.from_env()
                _rate_limiter = InMemoryRateLimiter(config)
    return _rate_limiter


def set_valid_api_key_digests(digests: set) -> None:
    """Enregistre les condensés des clés API valides pour le limiteur.

    Appelée par server.py après le chargement des clés depuis l'environnement.
    Le limiteur ne reçoit que des condensés : une fuite de sa mémoire ne
    donnerait aucune clé rejouable.

    Args:
        digests: Ensemble des condensés SHA-256 des clés valides.
    """
    global _valid_key_digests
    _valid_key_digests = digests


# ---------------------------------------------------------------------------
# Dépendance FastAPI
# ---------------------------------------------------------------------------


async def rate_limit_dependency(
    request: Request,
    api_key: Optional[str] = Security(_api_key_header),
) -> None:
    """Dépendance FastAPI pour appliquer le rate limiting aux endpoints.

    S'utilise avec Depends() dans les décorateurs de route.
    Compatible avec l'authentification API Key existante.

    Comportement :
    - Client authentifié (clé API valide) → limite authentifiée (RPM élevé)
    - Client non authentifié (sans clé ou clé invalide) → limite non authentifiée
    - Si le limiteur est désactivé → aucune vérification

    En-têtes HTTP ajoutés en cas de succès (via middleware) :
        X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset

    En cas de dépassement, lève HTTPException 429 avec :
        Retry-After : secondes avant de pouvoir réessayer
        X-RateLimit-Limit : limite applicable
        X-RateLimit-Remaining : toujours 0
        X-RateLimit-Reset : timestamp Unix de réinitialisation

    Args:
        request: La requête FastAPI (injectée automatiquement).
        api_key: La clé API depuis l'en-tête (injectée automatiquement).

    Raises:
        HTTPException: 429 si la limite de taux est dépassée.
    """
    limiter = get_rate_limiter()

    # Déterminer l'identité et le statut d'authentification du client.
    # Le compteur est indexé sur l'empreinte, jamais sur la clé : un seau de
    # limitation finit dans les journaux et les métriques.
    digest = hash_api_key(api_key) if api_key else None
    is_authenticated = digest is not None and digest in _valid_key_digests
    client_id = key_fingerprint(digest) if is_authenticated else _get_client_ip(request)

    allowed, info = limiter.is_allowed(client_id, is_authenticated)

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Trop de requêtes. Veuillez réessayer plus tard.",
            headers={
                "Retry-After": str(int(info.retry_after) + 1),
                "X-RateLimit-Limit": str(info.limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(info.reset_at)),
            },
        )
