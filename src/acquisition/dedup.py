"""
Le même document, deux fois — et presque le même (ADR-021, étape 8).

L'égalité stricte existait déjà (`knowledge_quality.py` compare des empreintes
de contenu). Elle attrape la ré-acquisition à l'identique et rien d'autre : un
communiqué republié avec une date de mise à jour, un PDF régénéré, une page avec
un fil d'Ariane différent produisent une empreinte différente et entrent une
seconde fois.

Trente circulaires quasi identiques dans une base de trente documents ne font
pas une base de trente documents.

## Comment le « presque » est mesuré

Fragments de mots (*shingles*) de longueur fixe, comparés par indice de Jaccard.
C'est mécanique, sans modèle, et **symétrique** : `A` proche de `B` implique `B`
proche de `A`. Ce qu'il ne voit pas est nommé, pas sous-entendu.

## Ce que ce module ne fait pas

Il ne supprime rien et ne fusionne rien. Un doublon exact est un refus motivé ;
un quasi-doublon part en **quarantaine**, parce qu'une version corrigée d'un
texte de loi et une republication paresseuse se ressemblent exactement ici, et
que seule une personne les distingue.
"""

import hashlib
import re
from typing import Any, Dict, Iterable

#: Longueur d'un fragment, en mots. Trop court, deux textes du même domaine se
#: ressemblent tous ; trop long, une virgule déplacée casse la correspondance.
LONGUEUR_DE_FRAGMENT = 5

#: Au-dessus, deux textes sont « presque le même document ». Choisi haut à
#: dessein : mieux vaut laisser passer un quasi-doublon — un humain le verra —
#: que mettre en quarantaine deux rapports annuels légitimes d'affilée.
SEUIL_DE_PROXIMITE = 0.8

_ESPACES = re.compile(r"\s+")
_PONCTUATION = re.compile(r"[^\w\s]", re.UNICODE)


def normalize(texte: str) -> str:
    """
    Ramène un texte à ce qui doit être comparé.

    La casse, la ponctuation et les espaces multiples ne distinguent pas deux
    documents ; les laisser ferait passer pour différents deux fichiers issus du
    même contenu par deux moulinettes.
    """
    sans_ponctuation = _PONCTUATION.sub(" ", (texte or "").lower())
    return _ESPACES.sub(" ", sans_ponctuation).strip()


def text_hash(texte: str) -> str:
    """Retourne l'empreinte du texte normalisé — l'égalité stricte."""
    return hashlib.sha256(normalize(texte).encode("utf-8")).hexdigest()


def shingles(texte: str, longueur: int = LONGUEUR_DE_FRAGMENT) -> set:
    """
    Découpe un texte en fragments de `longueur` mots.

    Un texte plus court qu'un fragment rend un seul fragment : sans cela, deux
    textes courts identiques auraient une similarité nulle.
    """
    mots = normalize(texte).split()
    if not mots:
        return set()
    if len(mots) <= longueur:
        return {" ".join(mots)}
    return {
        " ".join(mots[debut:debut + longueur])
        for debut in range(len(mots) - longueur + 1)
    }


def similarity(gauche: str, droite: str, longueur: int = LONGUEUR_DE_FRAGMENT) -> float:
    """
    Retourne l'indice de Jaccard entre deux textes, entre 0 et 1.

    Symétrique par construction : `similarity(a, b) == similarity(b, a)`. Une
    mesure asymétrique ferait dépendre le verdict de l'ordre d'arrivée.
    """
    a, b = shingles(gauche, longueur), shingles(droite, longueur)
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    return intersection / len(a | b) if intersection else 0.0


def compare(texte: str, autre: str, seuil: float = SEUIL_DE_PROXIMITE) -> Dict[str, Any]:
    """
    Compare deux textes et dit **quel genre** de doublon ils forment.

    Returns:
        `verdict` — `identical`, `near`, ou `distinct` — avec la mesure qui l'a
        produit. Les trois demandent des actions différentes : refuser, faire
        trancher, laisser passer.
    """
    if text_hash(texte) == text_hash(autre):
        return {
            "verdict": "identical",
            "similarity": 1.0,
            "reason": "Empreintes de texte normalisé identiques.",
        }

    score = similarity(texte, autre)
    if score >= seuil:
        return {
            "verdict": "near",
            "similarity": round(score, 4),
            "reason": (
                f"{score:.1%} de fragments communs (seuil {seuil:.0%}). Une version "
                "corrigée et une republication paresseuse se ressemblent ici : une "
                "personne tranche."
            ),
        }
    return {
        "verdict": "distinct",
        "similarity": round(score, 4),
        "reason": f"{score:.1%} de fragments communs, sous le seuil de {seuil:.0%}.",
    }


def find_duplicates(
    texte: str, corpus: Iterable[Dict[str, str]], seuil: float = SEUIL_DE_PROXIMITE
) -> Dict[str, Any]:
    """
    Cherche des doublons d'un texte dans un corpus déjà détenu.

    Args:
        texte: Le texte du document candidat.
        corpus: Éléments `{"id": …, "text": …}` déjà en base.
        seuil: Seuil de proximité.

    Returns:
        `identical` et `near`, chacun avec l'identifiant et la mesure. Un
        candidat peut être proche de plusieurs éléments : tous sont rendus, pas
        seulement le premier — un seuil franchi trois fois n'est pas la même
        information qu'une fois.
    """
    identiques, proches = [], []
    for element in corpus:
        verdict = compare(texte, element.get("text", ""), seuil)
        entree = {
            "id": element.get("id", ""),
            "similarity": verdict["similarity"],
            "reason": verdict["reason"],
        }
        if verdict["verdict"] == "identical":
            identiques.append(entree)
        elif verdict["verdict"] == "near":
            proches.append(entree)

    return {
        "identical": identiques,
        "near": sorted(proches, key=lambda e: e["similarity"], reverse=True),
        "compared": len(list(corpus)) if isinstance(corpus, list) else None,
        "method": f"jaccard sur fragments de {LONGUEUR_DE_FRAGMENT} mots",
        "threshold": seuil,
    }


def dedup_report() -> Dict[str, Any]:
    """Décrit la mesure, et ce qu'elle ne voit pas."""
    return {
        "method": f"jaccard sur fragments de {LONGUEUR_DE_FRAGMENT} mots",
        "threshold": SEUIL_DE_PROXIMITE,
        "symmetric": True,
        "identical": "refusé, avec sa raison",
        "near": "quarantaine — jamais une fusion automatique",
        "not_detected": [
            "un mot remplacé partout dans un texte court : mesuré à 0,79 sur un "
            "rapport de trois paragraphes, donc **sous** le seuil — deux rapports "
            "régionaux distincts restent distincts, mais un document simplement "
            "relocalisé passe aussi",
            "une traduction du même document : aucun fragment commun, similarité nulle",
            "un résumé fidèle d'un document déjà détenu",
            "le même contenu dans deux mises en page très différentes, si "
            "l'extraction produit des mots dans un autre ordre",
            "une reprise partielle : un chapitre extrait d'un rapport détenu en "
            "entier a peu de fragments communs **rapportés à l'union**",
        ],
        "note": (
            "Rien n'est supprimé ni fusionné. Un doublon exact est un refus motivé ; "
            "un quasi-doublon attend une personne."
        ),
    }
