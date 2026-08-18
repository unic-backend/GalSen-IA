"""
Excerpts: the words that actually matched, quoted, never rewritten.

A search result that shows only a title and a score asks the reader to trust it.
An excerpt shows *where* the match is, and lets them judge in one glance whether
the document is the one they wanted.

The whole difficulty is what an excerpt must not become.

**An excerpt is verbatim.** It is a slice of the document, copied. It is not a
summary, not a paraphrase, and nothing is reflowed inside it. The document
provider already refuses to fabricate summaries — `summary=None` is deliberate —
and an excerpt written in the platform's own words would be that fabrication
under another name.

**Truncation is marked at the edges, never inside.** A cut shown by an ellipsis
at the boundary is honest: the reader knows text continues. A cut in the middle,
silently joined, would produce a sentence the document does not contain.

**When no term is found, the excerpt says it is the beginning.** Returning the
first characters and letting them look like a match would be the quiet kind of
lie this repository keeps refusing.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

#: Largeur d'un extrait, en caractères. Assez pour une phrase et son contexte,
#: assez peu pour qu'une page de résultats reste lisible.
LARGEUR_EXTRAIT = 240

#: Marque de coupure, aux bords seulement.
COUPURE = "…"


def _replie(texte: str) -> str:
    """La forme sans accent d'un texte, pour la recherche de position."""
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _position(texte: str, terme: str) -> Optional[int]:
    """
    Où un terme apparaît dans un texte, en mot entier.

    La comparaison ignore les accents — « senegal » doit situer « Sénégal » —
    mais l'extrait rendu reste **le texte d'origine**, accents compris : replier
    sert à trouver, jamais à réécrire.

    Args:
        texte: Le texte du document.
        terme: Le terme cherché.

    Returns:
        L'indice du début du mot, ou `None`.
    """
    if not texte or not terme:
        return None
    # Le repli conserve la longueur caractère par caractère (NFKD retire des
    # marques combinantes, jamais des lettres de base), donc l'indice trouvé sur
    # la forme repliée est valable sur le texte d'origine.
    trouve = re.search(
        rf"\b{re.escape(_replie(terme).lower())}\b", _replie(texte).lower()
    )
    return trouve.start() if trouve else None


def excerpt_around(
    texte: str, termes: Iterable[str], largeur: int = LARGEUR_EXTRAIT,
) -> Dict[str, Any]:
    """
    Un extrait verbatim autour du premier terme trouvé.

    Args:
        texte: Le texte du document.
        termes: Les termes ayant fait correspondre, dans l'ordre de préférence.
        largeur: Largeur voulue de l'extrait.

    Returns:
        L'extrait, sa position, ce qui a été coupé, et le terme sur lequel il
        est centré — `None` s'il n'a été trouvé nulle part, auquel cas l'extrait
        est **le début du document** et le dit.
    """
    contenu = str(texte or "")
    if not contenu:
        return {
            "text": "", "start": 0, "truncated_left": False,
            "truncated_right": False, "centered_on": None,
            "is_beginning": True,
            "note": "Document sans texte : aucun extrait à montrer.",
        }

    centre_sur = None
    position = None
    for terme in termes or []:
        position = _position(contenu, terme)
        if position is not None:
            centre_sur = terme
            break

    if position is None:
        debut = 0
    else:
        debut = max(0, position - largeur // 3)

    fin = min(len(contenu), debut + largeur)
    extrait = contenu[debut:fin]

    return {
        # Verbatim : ni reformulé, ni recomposé.
        "text": (COUPURE if debut > 0 else "") + extrait + (
            COUPURE if fin < len(contenu) else ""
        ),
        "start": debut,
        "truncated_left": debut > 0,
        "truncated_right": fin < len(contenu),
        "centered_on": centre_sur,
        # Dit explicitement : sans cela, un début de document se lirait comme
        # une correspondance.
        "is_beginning": centre_sur is None,
        "note": (
            f"Extrait verbatim autour de « {centre_sur} »."
            if centre_sur else
            "Aucun terme de la requête n'apparaît dans le texte : ceci est le "
            "**début** du document, pas une correspondance."
        ),
    }


def excerpt_report(extraits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Ce que les extraits d'une page de résultats montrent.

    Args:
        extraits: Les extraits produits.

    Returns:
        Combien sont centrés sur un terme, combien sont des débuts de document,
        et les règles tenues.
    """
    debuts = sum(1 for extrait in extraits if extrait.get("is_beginning"))
    return {
        "excerpts": len(extraits),
        "centered_on_a_term": len(extraits) - debuts,
        "beginnings": debuts,
        "width": LARGEUR_EXTRAIT,
        "rules": [
            "Un extrait est **verbatim** : une tranche copiée du document, "
            "jamais un résumé ni une reformulation.",
            "La coupure est marquée aux bords, jamais à l'intérieur : un "
            "recollement silencieux produirait une phrase que le document ne "
            "contient pas.",
            "Sans terme trouvé, l'extrait dit qu'il est le **début** du "
            "document et non une correspondance.",
        ],
    }
