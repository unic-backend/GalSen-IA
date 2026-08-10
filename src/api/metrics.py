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

# Issues d'authentification (VOLET_16 ch. 06 et 09). Le taux de succès est la
# métrique que les deux chapitres demandent, et elle ne coûte que deux
# compteurs. Aucun sujet n'y figure : compter par personne transformerait une
# mesure d'exploitation en suivi individuel.
AUTH_SUCCES = "auth.success"
AUTH_ECHEC = "auth.failure"

# Recherche (VOLET 14, ch. 02 étape 6 et ch. 06). Le manuel réclame deux fois un
# module d'analytique et rien n'enregistrait la moindre requête. Ce qui est
# compté est le *comportement* de la recherche, jamais son contenu : une requête
# est ce qu'un utilisateur cherche, et le stocker changerait une mesure
# d'exploitation en journal de ce que chacun veut savoir.
RECHERCHE_TOTAL = "search.queries.total"
RECHERCHE_VIDE = "search.queries.empty"
RECHERCHE_LATENCE = "search.latency.{source}"

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


def record_authentication(reussie: bool) -> None:
    """
    Compte une tentative d'authentification.

    Args:
        reussie: True si la clé a été reconnue et n'était pas révoquée.

    Une mesure ratée ne doit pas empêcher une authentification : l'erreur est
    journalisée et avalée, comme dans l'intergiciel.
    """
    try:
        get_shared_metrics().execute("increment", AUTH_SUCCES if reussie else AUTH_ECHEC)
    except Exception as erreur:
        logger.warning("Métrique d'authentification non enregistrée : %s", erreur)


def record_search(sources: Any, results_count: int, duration_ms: float) -> None:
    """
    Compte une recherche : son volume, sa latence, et si elle n'a rien rendu.

    Args:
        sources: sources réellement interrogées (noms ou énumérations)
        results_count: nombre de résultats rendus
        duration_ms: durée mesurée de la recherche

    Le taux de recherches vides est la métrique de qualité que le chapitre 09
    demande et la seule qui se mesure sans jury humain : elle dit combien de fois
    la plateforme n'a rien su répondre. La requête elle-même n'est jamais écrite.
    """
    try:
        collecteur = get_shared_metrics()
        collecteur.execute("increment", RECHERCHE_TOTAL)
        if results_count == 0:
            collecteur.execute("increment", RECHERCHE_VIDE)
        noms = [getattr(s, "value", s) for s in (sources or ["none"])]
        for nom in noms:
            collecteur.execute("record_histogram", RECHERCHE_LATENCE.format(source=nom), duration_ms)
    except Exception as erreur:
        logger.warning("Métrique de recherche non enregistrée : %s", erreur)


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

    succes = compteurs.get(AUTH_SUCCES, 0)
    echecs = compteurs.get(AUTH_ECHEC, 0)
    tentatives = succes + echecs

    recherches = compteurs.get(RECHERCHE_TOTAL, 0)
    vides = compteurs.get(RECHERCHE_VIDE, 0)

    return {
        "requests_total": total,
        # Ce que la recherche a fait, sans dire ce qui a été cherché.
        "search": {
            "queries": recherches,
            "empty": vides,
            "empty_rate": round(vides / recherches, 4) if recherches else None,
        },
        # Le chapitre 06 du VOLET_16 demande « taux de succès » et « taux
        # d'échec » : le second se déduit du premier, une seule valeur suffit.
        "auth": {
            "attempts": tentatives,
            "succeeded": succes,
            "failed": echecs,
            "success_rate": round(succes / tentatives, 4) if tentatives else None,
        },
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
