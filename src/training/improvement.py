"""
Est-ce que la plateforme s'améliore ? (VOLET 34, ch. 12, phase 2)

Le brief demande « l'amélioration continue ». Le mot est facile à honorer de la
mauvaise façon : afficher une courbe qui monte. Ce module fait l'inverse — il
rend une mesure, ou il refuse de conclure.

## Ce qui est mesuré, et sur quoi

Sur le signal réellement recueilli (`feedback.py`), deux fenêtres de même durée
qui se suivent, et trois taux comparés :

| Taux | Ce qu'il dit |
|---|---|
| corrections | on a dû réécrire la réponse |
| signalements | la réponse était fausse ou nuisible |
| note moyenne | ce que les gens en ont pensé, quand ils ont noté |

## Ce qui est refusé

**Un écart calculé sur trois retours n'est pas une tendance.** En dessous d'un
minimum par fenêtre, la réponse est `insufficient_data` — pas « stable », pas
« légère amélioration ». Les deux dernières formulations sont des conclusions
tirées de rien, et elles seraient citées comme des mesures.

**Aucune fenêtre n'est comparée à une fenêtre vide.** Sans période antérieure,
il n'y a pas de référence : il y a un premier point.

Le seuil est explicite plutôt que caché dans un test de significativité que
personne n'aurait relu : trente retours par fenêtre, écrits ici, modifiables par
argument, et rendus dans la réponse.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from .feedback import Feedback, FeedbackKind, FeedbackStore, shared_feedback_store

logger = logging.getLogger(__name__)

#: Retours minimaux **par fenêtre** avant qu'un écart soit rapporté comme une
#: tendance. Trente n'est pas une valeur statistique : c'est le nombre en dessous
#: duquel un écart de quelques points s'explique par deux personnes de mauvaise
#: humeur le même jour.
MINIMUM_PAR_FENETRE = 30

#: Durée d'une fenêtre, en jours.
FENETRE_JOURS = 30

#: Écart en deçà duquel un taux est dit inchangé. Sans lui, « 12,0 % contre
#: 12,1 % » serait rapporté comme une dégradation.
BRUIT = 0.02

SECONDES_PAR_JOUR = 86400


def measure(
    store: Optional[FeedbackStore] = None,
    window_days: int = FENETRE_JOURS,
    minimum: int = MINIMUM_PAR_FENETRE,
    now: Optional[float] = None,
    limit: int = 5000,
) -> Dict[str, Any]:
    """
    Compare la fenêtre courante à la précédente, ou refuse de conclure.

    Args:
        store: Magasin de retours ; le magasin partagé sinon.
        window_days: Durée de chaque fenêtre, en jours.
        minimum: Retours minimaux par fenêtre pour qu'une tendance soit rendue.
        now: Instant de référence ; l'heure courante sinon.
        limit: Nombre maximal de retours lus.

    Returns:
        Les deux fenêtres mesurées et, seulement si le volume le permet, le sens
        de l'évolution.
    """
    magasin = store or shared_feedback_store()
    instant = now if now is not None else time.time()
    duree = window_days * SECONDES_PAR_JOUR

    try:
        retours = magasin.list_feedback(limit=limit)
    except Exception as erreur:  # noqa: BLE001 - un magasin en panne ne produit pas de tendance
        logger.warning("Mesure d'amélioration impossible : %s", erreur)
        return {"status": "unavailable", "reason": str(erreur)}

    courante = [f for f in retours if instant - duree <= f.created_at <= instant]
    precedente = [f for f in retours if instant - 2 * duree <= f.created_at < instant - duree]

    mesure_courante = _mesurer(courante)
    mesure_precedente = _mesurer(precedente)
    base = {
        "window_days": window_days,
        "minimum_per_window": minimum,
        "current": mesure_courante,
        "previous": mesure_precedente,
    }

    if not precedente:
        return {
            **base,
            "status": "no_baseline",
            "reason": (
                "Aucun retour sur la période antérieure : il n'y a pas de "
                "référence à comparer, seulement un premier point."
            ),
        }

    if len(courante) < minimum or len(precedente) < minimum:
        return {
            **base,
            "status": "insufficient_data",
            "reason": (
                f"{len(precedente)} puis {len(courante)} retours : en dessous de "
                f"{minimum} par fenêtre, un écart ne se distingue pas du hasard. "
                "Aucune tendance n'est rendue — ni « stable », ni « en progrès »."
            ),
        }

    return {
        **base,
        "status": "measured",
        "deltas": {
            "correction_rate": _ecart(
                mesure_precedente["correction_rate"], mesure_courante["correction_rate"]
            ),
            "report_rate": _ecart(
                mesure_precedente["report_rate"], mesure_courante["report_rate"]
            ),
            "mean_rating": _ecart(
                mesure_precedente["mean_rating"], mesure_courante["mean_rating"],
                plus_haut_est_mieux=True, bruit=0.1,
            ),
        },
    }


def _mesurer(retours: List[Feedback]) -> Dict[str, Any]:
    """Calcule les taux d'une fenêtre."""
    total = len(retours)
    if not total:
        return {
            "feedback": 0, "correction_rate": None, "report_rate": None,
            "mean_rating": None, "rated": 0,
        }

    corrections = sum(1 for f in retours if f.kind == FeedbackKind.CORRECTION)
    signalements = sum(1 for f in retours if f.kind == FeedbackKind.REPORT)
    notes = [f.rating for f in retours if f.rating is not None]

    return {
        "feedback": total,
        "correction_rate": round(corrections / total, 4),
        "report_rate": round(signalements / total, 4),
        # La note moyenne porte sur les retours **notés**, pas sur tous : diviser
        # par le total ferait baisser la moyenne à chaque retour sans note.
        "mean_rating": round(sum(notes) / len(notes), 3) if notes else None,
        "rated": len(notes),
    }


def _ecart(
    avant: Optional[float],
    apres: Optional[float],
    plus_haut_est_mieux: bool = False,
    bruit: float = BRUIT,
) -> Dict[str, Any]:
    """
    Décrit l'écart entre deux valeurs, en disant dans quel sens il va.

    Un écart plus petit que le bruit déclaré est rendu `unchanged` : sans cela,
    « 12,0 % contre 12,1 % » serait rapporté comme une dégradation.
    """
    if avant is None or apres is None:
        return {
            "before": avant, "after": apres, "direction": "unknown",
            "reason": "Une des deux fenêtres ne porte pas cette mesure.",
        }

    variation = apres - avant
    if abs(variation) < bruit:
        sens = "unchanged"
    elif (variation > 0) == plus_haut_est_mieux:
        sens = "better"
    else:
        sens = "worse"

    return {
        "before": avant, "after": apres,
        "change": round(variation, 4), "direction": sens,
    }
