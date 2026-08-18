"""
Citer ce qui a servi à répondre (VOLET 28, ch. 03).

`KnowledgeSource` porte depuis longtemps un titre, un auteur, une URL et une
citation. **Rien ne les assemblait.** `retrieve_reliable()` rendait des éléments
et un verdict de fiabilité, sans jamais dire d'où venait le contenu : une réponse
enrichie par la base ressemblait donc exactement à une réponse inventée par le
modèle.

C'est le point où une plateforme de connaissances se distingue d'un générateur de
texte plausible. Une affirmation sourcée peut être vérifiée, contestée, corrigée
à sa source ; la même affirmation sans source ne peut qu'être crue.

Deux règles :

1. **Une source non exploitable est signalée, jamais maquillée.** Un élément dont
   la provenance est inconnue apparaît comme tel, avec son identifiant, plutôt
   que sous un titre inventé ou un « source interne » qui ne renvoie nulle part.
2. **Les passages d'un même document sont regroupés.** Cinq blocs d'un même
   rapport font une citation avec cinq passages, pas cinq citations : une liste
   qui répète le même titre est illisible et fait croire à cinq sources.
"""

from typing import Any, Dict, Iterable, List

# Emplacement rendu quand la provenance est inconnue. Nommé, pour qu'un rapport
# de qualité puisse compter ces cas au lieu de les confondre avec des sources.
PROVENANCE_INCONNUE = "provenance inconnue"


# Valeurs que le constructeur par défaut de `KnowledgeSource` met en place quand
# personne n'a déclaré de source. Elles ressemblent à une provenance et n'en sont
# pas : citer « unknown » comme emplacement renverrait le lecteur nulle part en
# lui donnant l'impression d'une référence.
PLACEHOLDERS = {"", "unknown", "inconnu", "none", "n/a"}


def _valeur(source, champ: str):
    """Retourne un champ de source, ou None s'il n'est qu'un remplissage."""
    valeur = getattr(source, champ, None)
    if valeur is None:
        return None
    texte = str(valeur).strip()
    return None if texte.lower() in PLACEHOLDERS else texte


def _cle(item) -> str:
    """Identifie le document dont un élément est issu."""
    source = getattr(item, "source", None)
    if source is None:
        return PROVENANCE_INCONNUE
    for champ in ("hash", "url", "location", "title"):
        valeur = _valeur(source, champ)
        if valeur:
            return valeur
    return PROVENANCE_INCONNUE


def build_citations(items: Iterable[Any]) -> List[Dict[str, Any]]:
    """
    Construit la liste des sources ayant servi à une réponse.

    Args:
        items: Connaissances retenues pour répondre.

    Returns:
        Une citation par document, avec les passages utilisés. Une source
        inconnue est rendue avec `known: False` et l'identifiant de l'élément —
        elle n'est ni cachée ni déguisée.
    """
    groupes: Dict[str, Dict[str, Any]] = {}

    for item in items:
        cle = _cle(item)
        source = getattr(item, "source", None)
        citation = groupes.setdefault(cle, {
            "title": _valeur(source, "title"),
            "author": _valeur(source, "author"),
            "url": _valeur(source, "url"),
            "location": _valeur(source, "location"),
            "source_category": (
                source.source_category.value
                if source is not None and getattr(source, "source_category", None) is not None
                else None
            ),
            "passages": [],
            "knowledge_ids": [],
            "known": cle != PROVENANCE_INCONNUE,
        })

        citation["knowledge_ids"].append(getattr(item, "id", None))
        reference = getattr(source, "citation", None)
        if reference and reference not in citation["passages"]:
            citation["passages"].append(reference)

    # Une citation sans titre ni emplacement ne renvoie nulle part : le dire est
    # plus utile que de rendre une entrée vide qui aura l'air d'une source.
    for citation in groupes.values():
        if not citation["title"] and not citation["location"] and not citation["url"]:
            citation["known"] = False
            citation["detail"] = (
                "Cet élément n'a pas de provenance exploitable : il a été ajouté "
                "sans source. Il ne peut pas être vérifié."
            )

    return list(groupes.values())


def citation_coverage(items: Iterable[Any]) -> Dict[str, Any]:
    """
    Mesure la part de la réponse qui est réellement sourçable.

    C'est le chiffre qui rend la règle exécutable plutôt que déclarative : une
    base dont la moitié des éléments ne peuvent pas être cités est une base dont
    la moitié des réponses ne peuvent pas être vérifiées, et il vaut mieux le
    savoir que le découvrir.

    Returns:
        Le nombre d'éléments, combien portent une provenance exploitable, et la
        proportion. Une base vide rend une couverture nulle, pas une division
        par zéro déguisée en 100 %.
    """
    elements = list(items)
    if not elements:
        return {"items": 0, "with_source": 0, "coverage": 0.0}

    sourcables = sum(1 for item in elements if _cle(item) != PROVENANCE_INCONNUE)
    return {
        "items": len(elements),
        "with_source": sourcables,
        "coverage": round(sourcables / len(elements), 4),
    }
