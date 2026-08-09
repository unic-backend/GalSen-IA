"""
Mesure du trafic réel de l'API (VOLET_04 ch. 09, critère de sortie C5).

`/health`, `/ready` et `/live` répondent à « qu'est-ce qui est configuré ». Aucune
route ne répondait à « qu'est-ce qui se passe » : combien de requêtes, combien
d'erreurs, en combien de temps. Un opérateur devait ouvrir les journaux, ce que
le chapitre 09 exclut explicitement.

Ce module ne crée pas de mécanisme : il **alimente** l'outil `metrics` déjà
livré (`src/tools/metrics/tool.py`), qui savait compter mais que personne
n'appelait. L'outil garde son rôle de magasin ; ce module lui donne des chiffres
et les rend lisibles.

Portée : la mémoire du processus, comme le reste de l'état (ADR-009). Redémarrer
remet les compteurs à zéro, et `/metrics` le dit plutôt que de le laisser
deviner.
"""

import logging
import threading
import time
from typing import Any, Dict, Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.tools.metrics.tool import MetricsTool

logger = logging.getLogger(__name__)

# Noms des métriques. Centralisés : une faute de frappe dans un nom crée
# silencieusement un second compteur au lieu d'incrémenter le premier.
TOTAL = "http.requests.total"
PAR_CLASSE = "http.requests.{classe}"
LATENCE = "http.latency.{methode}.{route}"

# Chemin retenu quand aucune route ne correspond. Utiliser l'URL brute ferait
# exploser le nombre de compteurs : un scan d'URL en créerait un par tentative.
ROUTE_INCONNUE = "unmatched"

_metriques: Optional[MetricsTool] = None
_verrou = threading.Lock()


def get_shared_metrics() -> MetricsTool:
    """
    Retourne le collecteur partagé du processus.

    Même forme que les autres registres partagés de la plateforme : construit une
    fois, à la première utilisation. Sans partage, l'intergiciel et la route
    compteraient chacun dans leur coin.
    """
    global _metriques
    if _metriques is None:
        with _verrou:
            if _metriques is None:
                _metriques = MetricsTool()
    return _metriques


def reset_metrics() -> None:
    """Vide les compteurs. Réservé aux tests, qui doivent partir d'un état connu."""
    get_shared_metrics().execute("reset")


def _nom_de_route(request: Request) -> str:
    """
    Retourne le gabarit de route plutôt que l'URL demandée.

    `/memory/{item_id}` compte comme une seule série ; l'URL brute en créerait
    une par identifiant, et la mémoire du collecteur suivrait le trafic.
    """
    route = request.scope.get("route")
    chemin = getattr(route, "path", None)
    if not chemin:
        return ROUTE_INCONNUE
    # Les points séparent déjà les segments du nom de métrique.
    return chemin.strip("/").replace("/", ".").replace("{", "").replace("}", "") or "racine"


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """
    Compte chaque requête, son issue et sa durée.

    Une exception non rattrapée est comptée comme une erreur avant d'être
    relancée : sans cela, la seule catégorie de panne qui compte vraiment serait
    la seule à ne pas apparaître dans les chiffres.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """Mesure la requête, quelle que soit son issue."""
        collecteur = get_shared_metrics()
        debut = time.perf_counter()

        try:
            reponse = await call_next(request)
        except Exception:
            duree = (time.perf_counter() - debut) * 1000
            self._enregistrer(collecteur, request, 500, duree)
            raise

        duree = (time.perf_counter() - debut) * 1000
        self._enregistrer(collecteur, request, reponse.status_code, duree)
        return reponse

    @staticmethod
    def _enregistrer(collecteur: MetricsTool, request: Request, code: int, duree_ms: float) -> None:
        """Écrit les trois mesures d'une requête dans le collecteur."""
        try:
            collecteur.execute("increment", TOTAL)
            collecteur.execute("increment", PAR_CLASSE.format(classe=f"{code // 100}xx"))
            collecteur.execute(
                "record_histogram",
                LATENCE.format(methode=request.method.lower(), route=_nom_de_route(request)),
                duree_ms,
            )
        except Exception as erreur:
            # Une mesure ratée ne doit jamais faire échouer la requête mesurée.
            logger.warning("Métrique non enregistrée : %s", erreur)


def metrics_snapshot() -> Dict[str, Any]:
    """
    Retourne l'état des compteurs, avec le taux d'erreur déjà calculé.

    Le taux est dérivé ici plutôt que laissé à l'appelant : deux consommateurs
    qui le calculent chacun de leur côté finissent par ne pas être d'accord.

    Returns:
        Les compteurs, les histogrammes de latence, le total, le taux d'erreur
        et la portée de la mesure.
    """
    donnees = get_shared_metrics().execute("get_metrics")
    compteurs = donnees.get("counters", {})

    total = compteurs.get(TOTAL, 0)
    erreurs = sum(
        valeur
        for nom, valeur in compteurs.items()
        if nom in (PAR_CLASSE.format(classe="4xx"), PAR_CLASSE.format(classe="5xx"))
    )

    return {
        "requests_total": total,
        # Arrondi à quatre décimales : au-delà, le chiffre suggère une précision
        # que quelques centaines de requêtes ne portent pas.
        "error_rate": round(erreurs / total, 4) if total else 0.0,
        "counters": compteurs,
        "latency_ms": donnees.get("histograms", {}),
        "scope": "instance",
        "detail": (
            "Compteurs tenus en mémoire du processus : un redémarrage les remet "
            "à zéro et une autre instance a les siens (ADR-009)."
        ),
    }
