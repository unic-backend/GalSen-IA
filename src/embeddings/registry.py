"""
Le point unique où l'on demande un encodeur (ADR-015).

Chaque appelant — mémoire, connaissances, recherche — passe par ici. Sans ce
point unique, chacun construirait son fournisseur et l'un d'eux finirait par
diverger : un modèle différent, donc un espace vectoriel différent, donc des
scores qui n'ont plus de sens entre eux. La plateforme a déjà connu trois fois
deux implémentations d'une même interface en désaccord.

`active_embedder()` retourne **None** quand aucun fournisseur ne peut encoder.
C'est la valeur normale d'une installation sans `sentence-transformers`, et
l'appelant doit alors retomber sur la récupération lexicale **en le disant**.
"""

import os
import threading
from typing import Any, Dict, Optional

from .interfaces import EmbeddingProvider
from .sentence_transformers_provider import (  # noqa: F401  (réexport public)
    MODEL_VARIABLE as EMBEDDING_MODEL_VARIABLE,
    SentenceTransformersEmbedder,
)

ENABLED_VARIABLE = "GALSEN_EMBEDDINGS_ENABLED"

_verrou = threading.RLock()
_fournisseur: Optional[EmbeddingProvider] = None
_force: bool = False


def _desactive() -> bool:
    """Indique si l'exploitant a coupé les embeddings explicitement."""
    return os.getenv(ENABLED_VARIABLE, "").strip().lower() in ("false", "0", "no")


def set_embedder(fournisseur: Optional[EmbeddingProvider]) -> None:
    """
    Impose un fournisseur, ou rend la main au choix par défaut avec `None`.

    Sert à un déploiement qui sert son propre encodeur, et aux tests, qui
    peuvent ainsi exercer tout le chemin vectoriel — magasin, cosinus, repli —
    avec un encodeur déterministe, sans télécharger 90 Mo de poids.
    """
    global _fournisseur, _force
    with _verrou:
        _fournisseur = fournisseur
        _force = fournisseur is not None


def reset_embedder() -> None:
    """Oublie le fournisseur retenu ; le prochain appel le redécouvrira."""
    global _fournisseur, _force
    with _verrou:
        _fournisseur = None
        _force = False


def active_embedder() -> Optional[EmbeddingProvider]:
    """
    Retourne l'encodeur utilisable, ou None s'il n'y en a pas.

    Returns:
        Le fournisseur, ou None — ce qui est l'état normal d'une installation
        sans `sentence-transformers`. Un `None` n'est pas une panne : c'est
        l'information dont l'appelant a besoin pour dire quel chemin il a pris.
    """
    global _fournisseur
    # L'interrupteur de l'exploitant passe **avant** le fournisseur imposé :
    # sinon `GALSEN_EMBEDDINGS_ENABLED=false` ne couperait rien dans un
    # déploiement qui a injecté son propre encodeur, et un interrupteur qui
    # n'interrompt pas toujours ne vaut rien.
    if _desactive():
        return None
    with _verrou:
        if _force and _fournisseur is not None:
            return _fournisseur
        if _fournisseur is None:
            candidat = SentenceTransformersEmbedder()
            if not candidat.is_available():
                return None
            _fournisseur = candidat
        return _fournisseur


def embedding_status() -> Dict[str, Any]:
    """
    Décrit l'état de l'encodage, pour `/health` et les rapports de recherche.

    Returns:
        L'état du fournisseur retenu, ou le motif pour lequel il n'y en a pas.
        Jamais un état vide : « pas d'embeddings » est une réponse, et elle doit
        dire pourquoi.
    """
    if _desactive():
        return {
            "available": False,
            "reason": "disabled",
            "detail": f"{ENABLED_VARIABLE} est à false : la recherche reste lexicale.",
        }

    with _verrou:
        fournisseur = _fournisseur if _force else None
    if fournisseur is None:
        fournisseur = SentenceTransformersEmbedder()

    etat = fournisseur.check_availability().to_dict()
    etat["reference"] = "ADR-015"
    return etat
