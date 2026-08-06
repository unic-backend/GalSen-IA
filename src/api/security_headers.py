"""
En-têtes de sécurité HTTP et politique d'origines croisées.

Le chapitre 08 du VOLET 02 demande de « réduire les surfaces d'attaque » et
d'appliquer des « valeurs par défaut sûres ». Ce module tient les trois réglages
qui décidaient de la posture de l'API :

- les **en-têtes de sécurité**, absents de toutes les réponses ;
- les **origines croisées**, qui acceptaient n'importe quel site avec les
  identifiants du visiteur ;
- la **documentation interactive**, publique quel que soit le déploiement.

Aucun de ces réglages n'est laissé à la discipline : ils sont appliqués par un
intergiciel et lus depuis l'environnement.
"""

import logging
import os
from typing import List

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

CORS_ORIGINS_VARIABLE = "GALSEN_CORS_ORIGINS"
API_DOCS_VARIABLE = "GALSEN_API_DOCS"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Ajoute les en-têtes de sécurité à chaque réponse.

    Les valeurs sont celles d'une API qui ne sert que du JSON : rien à afficher,
    rien à encadrer, rien à mettre en cache. Une API plus permissive qu'un site
    web n'aurait aucune raison de l'être.
    """

    # `frame-ancestors 'none'` double `X-Frame-Options` pour les navigateurs
    # récents ; les deux sont conservés car le parc n'est pas homogène.
    # `sandbox` sans valeur interdit jusqu'à l'exécution de scripts : c'est juste
    # pour une API qui ne sert que du JSON.
    CONTENT_SECURITY_POLICY = "default-src 'none'; frame-ancestors 'none'; sandbox"

    # L'interface web, elle, doit charger sa feuille de style et ses modules.
    # La politique de l'API l'aurait rendue muette dans un navigateur — sans
    # qu'aucun test HTTP ne s'en aperçoive, un client de test n'appliquant pas
    # les CSP. Tout reste limité à la même origine : aucun script tiers, aucune
    # ressource distante, et rien d'incorporé dans la page (pas d'`unsafe-inline`).
    UI_CONTENT_SECURITY_POLICY = (
        "default-src 'none'; "
        "style-src 'self'; "
        "script-src 'self'; "
        "connect-src 'self'; "
        "img-src 'self' data:; "
        "base-uri 'none'; "
        "form-action 'none'; "
        "frame-ancestors 'none'"
    )

    # Préfixe sous lequel l'interface est servie.
    UI_PATH_PREFIX = "/ui"

    # Deux ans, la valeur attendue pour une éventuelle inscription en liste de
    # préchargement. Envoyé uniquement sur HTTPS : en clair, l'en-tête ne
    # protège rien et casserait un accès local en http://.
    STRICT_TRANSPORT_SECURITY = "max-age=63072000; includeSubDomains"

    async def dispatch(self, request: Request, call_next) -> Response:
        """Traite la requête puis complète la réponse."""
        response = await call_next(request)

        # nosniff : empêche un navigateur de deviner un type et d'exécuter
        # comme script une réponse qui n'en est pas un.
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        politique = (
            self.UI_CONTENT_SECURITY_POLICY
            if request.url.path.startswith(self.UI_PATH_PREFIX)
            else self.CONTENT_SECURITY_POLICY
        )
        response.headers.setdefault("Content-Security-Policy", politique)
        # Toute réponse d'API est authentifiée : aucun intermédiaire ne doit la
        # garder. Les fichiers de l'interface, eux, ne contiennent aucun secret.
        response.headers.setdefault("Cache-Control", "no-store")

        if self._is_https(request):
            response.headers.setdefault(
                "Strict-Transport-Security", self.STRICT_TRANSPORT_SECURITY
            )

        return response

    @staticmethod
    def _is_https(request: Request) -> bool:
        """
        Indique si la requête est arrivée en HTTPS.

        Derrière un répartiteur de charge, le schéma vu par l'application est
        `http` : c'est l'en-tête `X-Forwarded-Proto` qui porte l'information.
        """
        if request.url.scheme == "https":
            return True
        return request.headers.get("x-forwarded-proto", "").lower() == "https"


def allowed_origins() -> List[str]:
    """
    Retourne les origines autorisées à appeler l'API depuis un navigateur.

    Par défaut : **aucune**. `allow_origins=["*"]` combiné à
    `allow_credentials=True` faisait renvoyer l'origine de l'appelant quelle
    qu'elle soit, ce qui autorisait n'importe quel site à appeler l'API avec les
    identifiants du visiteur. Une liste vide interdit tout appel croisé ; les
    appels serveur à serveur, eux, ne sont pas concernés.

    Returns:
        Les origines déclarées dans `GALSEN_CORS_ORIGINS`, séparées par des
        virgules.
    """
    brut = os.environ.get(CORS_ORIGINS_VARIABLE, "").strip()
    if not brut:
        return []
    return [origine.strip() for origine in brut.split(",") if origine.strip()]


def docs_enabled() -> bool:
    """
    Indique si la documentation interactive doit être servie.

    Règle : **la documentation n'est publique qu'aussi longtemps que l'API
    l'est.** Sans clé configurée, la plateforme est ouverte et cacher son schéma
    ne protégerait rien tout en gênant le développement. Dès qu'une clé existe,
    quelqu'un a décidé de contrôler l'accès : le schéma complet des routes
    cesse d'être offert à qui passe.

    `GALSEN_API_DOCS` (`enabled` / `disabled`) tranche explicitement quand ce
    choix automatique ne convient pas.

    Returns:
        True si `/docs`, `/redoc` et `/openapi.json` doivent être servis.
    """
    demande = os.environ.get(API_DOCS_VARIABLE, "").strip().lower()
    if demande in ("enabled", "true", "1", "yes"):
        return True
    if demande in ("disabled", "false", "0", "no"):
        return False

    return not os.environ.get("GALSEN_API_KEYS", "").strip()
