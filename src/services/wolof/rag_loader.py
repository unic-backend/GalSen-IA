"""
Le corpus wolof, prêt pour le RAG existant — sans second RAG.

GalSen a déjà une chaîne de récupération complète : `KnowledgeItem` avec sa
provenance, un magasin, un récupérateur, une normalisation par langue, une
barrière de confiance et un outil `rag`. Ce module ne fait **que** l'adaptation :
il lit `data/processed_wolof/official_wolof_corpus.json` et rend des documents
que cette chaîne sait déjà traiter.

Aucun second index, aucune base vectorielle, aucune bibliothèque tierce.

## Ce que chaque fragment transporte

Une phrase sans sa source ne peut pas être citée, et une citation qu'on ne peut
pas rouvrir ne vaut rien. Chaque fragment porte donc son `sent_id` amont, son
URL, son empreinte, sa licence, son découpage et la version de normalisation qui
l'a produit.

## Ce que ce module ne fait pas

Il **n'écrit rien** dans la base de connaissances. Ingérer est un geste séparé,
qui passe par `DocumentIngestor` et par une relecture — la même règle que pour
tout autre corpus.
"""

import json
import os
from typing import Any, Dict, Iterator, List, Optional

#: Emplacement du corpus traité, relatif à la racine du dépôt.
CORPUS = os.path.join("data", "processed_wolof", "official_wolof_corpus.json")

#: Taille d'un fragment, en caractères. Les phrases du corpus sont courtes ;
#: le découpage sert surtout aux textes wolof qui viendront ensuite.
TAILLE_DE_FRAGMENT = 1200

#: Recouvrement entre deux fragments, pour qu'une phrase coupée reste lisible
#: des deux côtés.
RECOUVREMENT = 150


class CorpusUnavailable(FileNotFoundError):
    """Le corpus traité n'existe pas encore, et le message dit comment le produire."""


def _racine() -> str:
    """Retourne la racine du dépôt."""
    ici = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(ici)))


def load_corpus(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge le corpus wolof traité.

    Args:
        chemin: Fichier à lire ; celui du dépôt par défaut.

    Returns:
        Le corpus complet, avec ses statistiques et ses enregistrements.

    Raises:
        CorpusUnavailable: Si le fichier n'existe pas. Rendre un corpus vide
            ferait croire à un wolof sans documents, alors que le corpus n'a
            simplement pas encore été construit.
    """
    cible = chemin or os.path.join(_racine(), CORPUS)
    if not os.path.isfile(cible):
        raise CorpusUnavailable(
            f"Corpus absent : {cible}. Le construire avec "
            "`python scripts/ingest_wolof.py`. Un corpus vide serait pris pour "
            "un wolof sans documents."
        )
    with open(cible, "r", encoding="utf-8") as fichier:
        return json.load(fichier)


def iterate_documents(
    chemin: Optional[str] = None,
    split: str = "",
    corpus: Optional[Dict[str, Any]] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Parcourt les documents du corpus, un par phrase.

    Args:
        chemin: Fichier à lire.
        split: `train`, `dev`, `test` — vide pour tout.
        corpus: Corpus déjà chargé, pour éviter de relire le fichier.

    Yields:
        Un document par phrase : son texte brut, son texte normalisé, et sa
        provenance complète. Le texte brut est **toujours** présent : le
        normalisé ne le remplace pas.
    """
    donnees = corpus or load_corpus(chemin)
    for enregistrement in donnees.get("records", []):
        if split and enregistrement.get("split") != split:
            continue
        yield {
            "id": f"{enregistrement['source']}:{enregistrement['sent_id']}",
            "text": enregistrement["text"],
            "normalized_text": enregistrement["normalized_text"],
            "language": enregistrement.get("language", "wo"),
            "metadata": get_metadata(enregistrement, donnees),
        }


def chunk_text(
    texte: str, taille: int = TAILLE_DE_FRAGMENT, recouvrement: int = RECOUVREMENT
) -> List[str]:
    """
    Découpe un texte en fragments, sur les frontières de mots.

    Couper au milieu d'un mot wolof produirait des formes qui n'existent pas ;
    le découpage recule jusqu'à la dernière espace plutôt que de trancher.

    Args:
        texte: Le texte à découper.
        taille: Taille visée d'un fragment, en caractères.
        recouvrement: Caractères repris du fragment précédent.

    Returns:
        Les fragments, dans l'ordre. Un texte plus court que `taille` rend un
        seul fragment — jamais une liste vide pour un texte non vide.
    """
    contenu = (texte or "").strip()
    if not contenu:
        return []
    if len(contenu) <= taille:
        return [contenu]
    if recouvrement >= taille:
        raise ValueError("Le recouvrement doit rester inférieur à la taille du fragment.")

    fragments, debut = [], 0
    while debut < len(contenu):
        fin = min(debut + taille, len(contenu))
        if fin < len(contenu):
            espace = contenu.rfind(" ", debut, fin)
            if espace > debut:
                fin = espace
        fragments.append(contenu[debut:fin].strip())
        if fin >= len(contenu):
            break
        # Le recouvrement doit lui aussi commencer sur un mot : reculer de N
        # caractères tombe au milieu d'un mot une fois sur deux, et le fragment
        # suivant s'ouvrait sur « ari » au lieu de « ñaari ».
        suivant = max(fin - recouvrement, debut + 1)
        espace = contenu.rfind(" ", debut, suivant)
        debut = espace + 1 if espace > debut else suivant
    return [fragment for fragment in fragments if fragment]


def get_metadata(
    enregistrement: Dict[str, Any], corpus: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Retourne la provenance d'un enregistrement, complète.

    Une phrase sans sa source ne peut pas être citée, et une citation qu'on ne
    peut pas rouvrir ne vaut rien.
    """
    corpus = corpus or {}
    return {
        "language": enregistrement.get("language", "wo"),
        "source": enregistrement.get("source", corpus.get("source", "unknown")),
        "sent_id": enregistrement.get("sent_id", ""),
        "split": enregistrement.get("split", ""),
        "source_url": enregistrement.get("source_url", ""),
        "licence": enregistrement.get("licence", corpus.get("licence", "unknown")),
        "content_hash": enregistrement.get("content_hash", ""),
        "normalization_standard": enregistrement.get("normalization_standard", ""),
        "normalization_version": enregistrement.get("normalization_version", ""),
        "letters_outside_alphabet": enregistrement.get("letters_outside_alphabet", []),
    }


def iterate_chunks(
    chemin: Optional[str] = None,
    split: str = "",
    taille: int = TAILLE_DE_FRAGMENT,
    corpus: Optional[Dict[str, Any]] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Parcourt les fragments prêts pour la récupération.

    **Chaque fragment garde sa provenance** : un fragment orphelin ne peut pas
    être cité, donc il ne devrait jamais exister.
    """
    for document in iterate_documents(chemin, split, corpus):
        fragments = chunk_text(document["text"], taille)
        for index, fragment in enumerate(fragments):
            metadonnees = dict(document["metadata"])
            metadonnees.update({"chunk": index, "chunks": len(fragments)})
            yield {
                "id": f"{document['id']}#{index}",
                "text": fragment,
                "language": document["language"],
                "metadata": metadonnees,
            }


def corpus_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Décrit le corpus tel qu'il est réellement, ou son absence.

    `available: false` **n'est pas** un corpus vide : c'est un fichier qui n'a
    pas encore été construit, et la distinction change ce qu'il faut faire.
    """
    try:
        corpus = load_corpus(chemin)
    except CorpusUnavailable as absence:
        return {
            "available": False,
            "reason": str(absence),
            "documents": 0,
            "note": "Corpus non construit — ce n'est pas un wolof sans documents.",
        }

    documents = list(iterate_documents(corpus=corpus))
    return {
        "available": True,
        "corpus": corpus.get("corpus"),
        "source": corpus.get("source"),
        "licence": corpus.get("licence"),
        "normalization_standard": corpus.get("normalization_standard"),
        "normalization_version": corpus.get("normalization_version"),
        "documents": len(documents),
        "by_split": corpus.get("statistics", {}).get("by_split", {}),
        "duplicates_removed": corpus.get("duplicates", 0),
        "statistics": corpus.get("statistics", {}),
        "ingested": 0,
        "note": (
            "Ce module n'écrit rien dans la base : ingérer est un geste séparé, "
            "par `DocumentIngestor`, après relecture."
        ),
    }
