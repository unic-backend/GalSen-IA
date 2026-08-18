"""
Perishable facts: what expires in days, and what never expires at all.

Sport is the domain that breaks the freshness model built in VOLET 53, and it
breaks it in a way worth naming.

That model measures age **in years**, because it was built for statistics: a
population figure published annually is fresh at two years old. A league table
is stale on Sunday evening. A cadence expressed in years cannot say that — the
smallest thing it can express is "one year", and calling a table fresh for a
year would be the most confidently wrong answer this platform could give.

So this module measures in **days**. It does not replace `freshness.py`; the
year scale is right for what it was written for, and both are needed.

The second distinction is the one sport makes obvious and every domain shares:

**A result is dated and permanent.** The final played on 18 December 2022 will
still have been played, with the same score, in 2050. It does not age. Marking
it `STALE` because it is old would be nonsense, and marking it `FRESH` would be
a different nonsense — it is neither. It is **`PERMANENT`**, which is a third
thing.

**A standing is dated and expires.** A table, a squad, a ranking: each is a
photograph of an instant. Serving one without its date is not "slightly out of
date", it is a claim about today that nobody made.

Nothing here classifies a text. The kind of a fact is **declared** by whoever
records it, never guessed from words — a guessed kind would put a permanent
label on something that expires, which is the failure this module exists to
prevent.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from .freshness import Freshness

INCONNU = "UNKNOWN"

#: Verdict d'un fait qui ne vieillit pas. Ce n'est ni « frais » ni « périmé » :
#: c'est une troisième chose, et les deux autres seraient fausses.
PERMANENT = "PERMANENT"

#: Les genres de faits périssables, et leur durée de validité **en jours**.
#: Déclarés, jamais devinés d'un texte : un genre deviné poserait une étiquette
#: « permanent » sur ce qui périme, ce que ce module existe pour empêcher.
GENRES: Dict[str, Dict[str, Any]] = {
    "result": {
        "perishable": False,
        "what": "Un match joué, un score final, une médaille remise.",
        "why": (
            "La finale du 18 décembre 2022 aura toujours été jouée, avec le "
            "même score, en 2050. Elle ne vieillit pas."
        ),
    },
    "record": {
        "perishable": False,
        "what": "Un record établi.",
        "why": (
            "Un record est un fait daté : il reste vrai même battu. Ce qui "
            "change alors, c'est qu'un **autre** fait daté existe."
        ),
    },
    "standing": {
        "perishable": True,
        "valid_days": 7,
        "what": "Un classement, une table, un rang.",
        "why": (
            "Photographie d'un instant. La servir sans sa date n'est pas « un "
            "peu dépassé », c'est une affirmation sur aujourd'hui que personne "
            "n'a faite."
        ),
    },
    "squad": {
        "perishable": True,
        "valid_days": 30,
        "what": "Un effectif, une sélection, un transfert en cours.",
        "why": "Un effectif change à chaque fenêtre de transfert.",
    },
    "fixture": {
        "perishable": True,
        "valid_days": 1,
        "what": "Un calendrier, une rencontre à venir.",
        "why": (
            "Une rencontre à venir se reporte, se déplace et se joue : passé "
            "sa date, l'annoncer encore serait faux."
        ),
    },
}

#: Marge, en jours, au-delà de la validité déclarée avant de dire `STALE`
#: plutôt que `AGING`. Volontairement courte : ce qui périme en jours n'a pas de
#: longue zone grise.
MARGE_JOURS = 3


def _instant(now: Optional[datetime] = None) -> datetime:
    """L'instant de référence, en UTC. Le temps vient de l'appelant."""
    return now if now is not None else datetime.now(timezone.utc)


def _lire_date(valeur: Any) -> Optional[datetime]:
    """
    Lit une date ISO, ou `None`.

    Rien n'est deviné : une date mal écrite ne devient pas aujourd'hui.
    """
    texte = str(valeur or "").strip()
    if not texte:
        return None
    try:
        lue = datetime.fromisoformat(texte.replace("Z", "+00:00"))
    except ValueError:
        return None
    return lue if lue.tzinfo else lue.replace(tzinfo=timezone.utc)


def kind_of(fact_kind: str) -> Optional[Dict[str, Any]]:
    """
    La déclaration d'un genre de fait, ou `None` s'il n'est pas déclaré.

    Args:
        fact_kind: Le genre.

    Returns:
        Sa déclaration.
    """
    return GENRES.get(str(fact_kind or "").strip().lower())


def freshness_of_date(
    date: Any, fact_kind: str = "", now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    L'âge d'un fait daté au jour près, selon son genre.

    Args:
        date: La date du fait, en ISO 8601.
        fact_kind: Le genre déclaré (`result`, `standing`, …).
        now: L'instant de référence, pour les tests.

    Returns:
        L'âge en jours, le verdict, et la raison en clair.
    """
    genre = kind_of(fact_kind)
    quand = _lire_date(date)

    if quand is None:
        return {
            "status": Freshness.UNKNOWN.value,
            "age_days": INCONNU,
            "fact_kind": fact_kind or INCONNU,
            "reason": (
                "Fait sans date lisible : son âge est inconnu. Une donnée non "
                "datée n'est pas récente — elle en a seulement l'air."
            ),
        }

    age = (_instant(now) - quand).days

    if genre is None:
        return {
            "status": Freshness.UNKNOWN.value,
            "age_days": age,
            "fact_kind": fact_kind or INCONNU,
            "date": quand.date().isoformat(),
            "reason": (
                f"Genre « {fact_kind or '—'} » non déclaré : impossible de dire "
                "s'il périme. Le deviner poserait une étiquette « permanent » "
                f"sur ce qui expire. Genres connus : {', '.join(sorted(GENRES))}."
            ),
        }

    if not genre["perishable"]:
        return {
            "status": PERMANENT,
            "age_days": age,
            "fact_kind": fact_kind,
            "date": quand.date().isoformat(),
            "reason": f"{genre['what']} {genre['why']}",
        }

    validite = int(genre["valid_days"])
    if age <= validite:
        verdict = Freshness.FRESH.value
        raison = f"Valable {validite} jour(s) ; celui-ci en a {age}."
    elif age <= validite + MARGE_JOURS:
        verdict = Freshness.AGING.value
        raison = (
            f"Au-delà des {validite} jour(s) de validité ({age} jours). Servi "
            "tel quel, avec sa date."
        )
    else:
        verdict = Freshness.STALE.value
        raison = (
            f"{age} jours pour un fait valable {validite} : périmé. Il reste "
            "rendu **avec sa date** — le remplacer par une valeur d'apparence "
            "plus récente serait une fabrication."
        )

    return {
        "status": verdict,
        "age_days": age,
        "fact_kind": fact_kind,
        "date": quand.date().isoformat(),
        "valid_days": validite,
        "reason": f"{genre['what']} {raison}",
    }


def perishability_report() -> Dict[str, Any]:
    """
    Ce que ce module distingue, et ce qu'il ne fait pas.

    Returns:
        Les genres déclarés et les règles tenues.
    """
    return {
        "kinds": {
            nom: {
                "perishable": genre["perishable"],
                "valid_days": genre.get("valid_days"),
                "what": genre["what"],
            }
            for nom, genre in sorted(GENRES.items())
        },
        "scale": "jours",
        "why_days": (
            "Le modèle de fraîcheur du VOLET 53 mesure en **années**, ce qui est "
            "juste pour une statistique annuelle. Un classement est périmé le "
            "dimanche soir : une cadence en années ne peut pas le dire, et le "
            "déclarer frais pendant un an serait la réponse la plus "
            "confortablement fausse possible."
        ),
        "rules": [
            "Un résultat est daté et **permanent** : ni frais, ni périmé — une "
            "troisième chose.",
            "Un classement est daté et **périme** : le servir sans sa date est "
            "une affirmation sur aujourd'hui que personne n'a faite.",
            "Le genre d'un fait est **déclaré**, jamais deviné d'un texte : un "
            "genre deviné poserait « permanent » sur ce qui expire.",
            "Un fait périmé est rendu avec sa date, jamais remplacé.",
        ],
        "does_not": [
            "Classer un texte : ce module ne lit aucun contenu.",
            "Rafraîchir un fait : aucune source de sport n'est joignable ici.",
        ],
    }


def valid_until(date: Any, fact_kind: str) -> Optional[str]:
    """
    Jusqu'à quand un fait périssable reste valable.

    Args:
        date: La date du fait.
        fact_kind: Son genre.

    Returns:
        La date limite en ISO, ou `None` si le fait ne périme pas ou n'est pas
        datable.
    """
    genre = kind_of(fact_kind)
    quand = _lire_date(date)
    if genre is None or quand is None or not genre["perishable"]:
        return None
    return (quand + timedelta(days=int(genre["valid_days"]))).date().isoformat()
