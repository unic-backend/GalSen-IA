"""
La connaissance sénégalaise, servie au RAG existant.

Ce module lit `data/processed_senegal/senegal_master_knowledge.json` et rend des
fragments que la chaîne de récupération existante sait traiter. Il **n'ajoute
aucune architecture** : pas d'index, pas de base vectorielle, pas de dépendance
tierce. Le score est lexical et déterministe, calculé avec la normalisation du
dépôt (`src/text_normalization.py`), celle qui sait déjà qu'une règle française
ne s'applique pas au wolof.

## Trois refus

1. **Aucun fragment sans provenance.** Un fait sur un pays réel qu'on ne peut
   pas rattacher à une source est un fait qu'il ne faut pas servir.
2. **Aucune réponse inventée.** Une requête sans correspondance rend une liste
   vide **avec sa raison**, jamais le fragment le moins mauvais.
3. **Le corpus wolof n'est pas recopié.** `get_wolof_corpus()` renvoie vers
   `src/services/wolof/`, qui reste la seule source de vérité pour le wolof.

## Ce que « peuplé » veut dire

Trois domaines sur seize portent des données : géographie, administration,
langues. Les treize autres sont **déclarés vides avec leur raison**. Les lire
comme « le Sénégal n'a pas d'agriculture » serait un contresens ; les remplir de
mémoire serait pire.
"""

import json
import math
import os
import re
import time
from typing import Any, Dict, Iterator, List, Optional

from ...text_normalization import token_variants, tokenize
from .multilingual_aliases import expand_terms

#: Emplacement de la connaissance construite, relatif à la racine du dépôt.
CONNAISSANCE = os.path.join("data", "processed_senegal", "senegal_master_knowledge.json")

#: Connaissance sectorielle, acquise séparément (économie, institutions,
#: transport). Deux fichiers parce que deux acquisitions : les fondre ferait
#: perdre quelle source a produit quoi.
DOMAINES = os.path.join("data", "processed_senegal", "senegal_domain_knowledge.json")

#: Valeur d'un champ que personne n'a pu établir.
INCONNU = "UNKNOWN"

#: Découpage en mots, avant toute normalisation.
_MOT = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)

#: Nombre de fragments rendus par défaut.
TOP_K = 5

#: Score en dessous duquel aucun fragment n'est rendu. Sans ce plancher, une
#: question dont seuls les mots banals correspondent — « Sénégal », « est »,
#: « quelle » — rendait le premier département venu : mesuré sur « Quelle est
#: l'histoire du royaume du Cayor ? », qui renvoyait Bakel avec l'air de
#: répondre alors que le domaine HISTORY est vide.
SCORE_MINIMUM = 0.15

#: Part maximale de fragments qu'un terme peut toucher pour compter. Au-delà, il
#: ne distingue rien : « Sénégal » est dans 100 % des fragments, « est » dans
#: presque autant. Un terme non distinctif ne doit ni porter un score, ni
#: entrer dans le dénominateur — sinon deux mots vides suffisent à faire remonter
#: n'importe quoi.
PART_MAXIMALE = 0.5

#: Mots vides écartés du score, en français et en anglais. Ils ne sont pas
#: écartés par pure convention : les fragments administratifs sont rédigés en
#: français et les fragments sectoriels en anglais, si bien que « est » ou « du »
#: n'apparaissent que dans un quart des fragments et **passaient pour
#: distinctifs**. « Quelle est l'histoire du royaume du Cayor ? » remontait alors
#: un département, alors que le domaine HISTORY est vide.
MOTS_VIDES = frozenset({
    "le", "la", "les", "un", "une", "des", "du", "de", "au", "aux", "et", "ou",
    "est", "sont", "quel", "quelle", "quels", "quelles", "qui", "que", "quoi",
    "dans", "pour", "par", "sur", "avec", "sans", "ce", "cette", "ces", "son",
    "sa", "ses", "leur", "leurs", "il", "elle", "ils", "elles", "on", "nous",
    "vous", "en", "y", "a", "as", "ont", "etre", "avoir", "plus", "moins",
    "the", "of", "in", "at", "to", "for", "and", "or", "is", "are", "was",
    "were", "what", "which", "who", "with", "from", "by", "its", "their",
    "senegal", "senegaal",
})


#: Fichiers déjà lus, par chemin. Sans ce cache, chaque question relisait deux
#: fichiers JSON et reconstruisait 246 fragments : la latence tenait au disque,
#: pas au classement.
_CACHE: Dict[str, Any] = {}


def clear_cache() -> None:
    """Vide le cache des fichiers lus — utile après une nouvelle acquisition."""
    _CACHE.clear()


class KnowledgeUnavailable(FileNotFoundError):
    """La connaissance n'a pas encore été construite, et le message dit comment."""


def _racine() -> str:
    """Retourne la racine du dépôt."""
    ici = os.path.dirname(os.path.abspath(__file__))
    return os.path.dirname(os.path.dirname(os.path.dirname(ici)))


def load_all_knowledge(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge la connaissance sénégalaise construite.

    Raises:
        KnowledgeUnavailable: Si le fichier n'existe pas. Rendre un objet vide
            ferait croire à un Sénégal sans entités, alors que rien n'a encore
            été acquis.
    """
    cible = chemin or os.path.join(_racine(), CONNAISSANCE)
    if not os.path.isfile(cible):
        raise KnowledgeUnavailable(
            f"Connaissance absente : {cible}. La construire avec "
            "`python scripts/ingest_all_senegal.py`. Un objet vide serait pris "
            "pour un pays sans entités."
        )
    if cible not in _CACHE:
        with open(cible, "r", encoding="utf-8") as fichier:
            _CACHE[cible] = json.load(fichier)
    return _CACHE[cible]


def load_domain_knowledge(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge la connaissance sectorielle, ou rend une structure vide **qui le dit**.

    Son absence n'est pas une erreur : les domaines sectoriels sont acquis par un
    second script, et le moteur doit fonctionner sans eux. Mais elle ne doit pas
    passer pour « ces domaines sont vides » — la distinction est dans `available`.
    """
    cible = chemin or os.path.join(_racine(), DOMAINES)
    if not os.path.isfile(cible):
        return {
            "available": False,
            "domains": {},
            "reason": (
                f"Connaissance sectorielle absente : {cible}. La construire avec "
                "`python scripts/ingest_senegal_domains.py`."
            ),
        }
    if cible not in _CACHE:
        with open(cible, "r", encoding="utf-8") as fichier:
            donnees = json.load(fichier)
        donnees["available"] = True
        _CACHE[cible] = donnees
    return _CACHE[cible]


def _domaines_fusionnes(
    connaissance: Dict[str, Any], sectorielle: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Rend les seize domaines, ceux du second fichier venant compléter les vides.

    Un domaine peuplé par les deux fichiers n'existe pas aujourd'hui ; s'il
    arrivait, la version sectorielle serait ajoutée, jamais substituée — écraser
    perdrait la source du premier.
    """
    fusionnes = {nom: dict(domaine) for nom, domaine in connaissance["domains"].items()}
    for nom, domaine in (sectorielle or {}).get("domains", {}).items():
        if not domaine.get("items"):
            continue
        existant = fusionnes.setdefault(nom, {"populated": False, "items": [], "reason": ""})
        existant["items"] = list(existant.get("items", [])) + list(domaine["items"])
        existant["populated"] = True
        existant["reason"] = ""
    return fusionnes


def query_by_region(
    region_name: str,
    chemin: Optional[str] = None,
    connaissance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retourne une région et ses départements, avec la provenance de chacun.

    Args:
        region_name: Nom de la région, à la casse et aux accents près.

    Returns:
        La région, ses départements, et `found: False` **avec la liste des noms
        connus** quand elle n'existe pas — deviner la région la plus proche
        ferait répondre sur un autre territoire.
    """
    donnees = connaissance or load_all_knowledge(chemin)
    cible = _normalise(region_name)
    region = next(
        (r for r in donnees["regions"] if _normalise(r["name"]) == cible), None
    )
    if region is None:
        return {
            "found": False,
            "query": region_name,
            "reason": "Aucune région de ce nom dans la connaissance construite.",
            "known_regions": sorted(r["name"] for r in donnees["regions"]),
        }

    departements = [
        d for d in donnees["departments"] if d["parent"] == region["name"]
    ]
    return {
        "found": True,
        "region": region,
        "departments": departements,
        "department_count": len(departements),
        "provenance": region["provenance"],
        "unknown_fields": [
            champ for champ in ("chief_lieu", "population", "area_km2")
            if region.get(champ) == INCONNU
        ],
    }


def query_by_sector(
    sector_name: str,
    chemin: Optional[str] = None,
    connaissance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retourne un domaine de connaissance, peuplé ou non.

    Un domaine vide rend `populated: False` **et sa raison**. C'est la réponse
    utile : « rien n'a été acquis sur ce sujet » et « le Sénégal n'a pas ce
    secteur » sont deux phrases très différentes.
    """
    donnees = connaissance or load_all_knowledge(chemin)
    domaines = _domaines_fusionnes(donnees, load_domain_knowledge())
    cle = str(sector_name or "").strip().upper().replace(" ", "_")
    domaine = domaines.get(cle)
    if domaine is None:
        return {
            "found": False,
            "query": sector_name,
            "reason": "Domaine inconnu de ce modèle de connaissance.",
            "known_sectors": sorted(domaines),
        }
    return {
        "found": True,
        "sector": cle,
        "populated": domaine["populated"],
        "items": domaine["items"],
        "count": len(domaine["items"]),
        "reason": domaine["reason"],
    }


def get_wolof_corpus() -> Dict[str, Any]:
    """
    Retourne l'état du corpus wolof **existant**, sans le recopier.

    Un second corpus wolof donnerait deux vérités et deux versions de
    normalisation, sans moyen de dire laquelle a servi à une réponse.
    """
    from ..wolof.rag_loader import corpus_report

    rapport = corpus_report()
    rapport["owner"] = "src/services/wolof/ — source de vérité unique pour le wolof"
    return rapport


def iterate_chunks(
    chemin: Optional[str] = None, connaissance: Optional[Dict[str, Any]] = None
) -> Iterator[Dict[str, Any]]:
    """
    Parcourt les fragments récupérables, **chacun avec sa provenance**.

    Un fragment orphelin ne peut pas être cité ; il ne devrait donc pas exister.
    """
    donnees = connaissance or load_all_knowledge(chemin)
    for region in donnees["regions"]:
        yield _fragment(region, donnees)
    for departement in donnees["departments"]:
        yield _fragment(departement, donnees)

    sectorielle = load_domain_knowledge()
    for nom, domaine in (sectorielle.get("domains") or {}).items():
        for index, objet in enumerate(domaine.get("items", [])):
            yield _fragment_sectoriel(nom, index, objet)


def _fragment(entite: Dict[str, Any], donnees: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit un fragment textuel pour une entité administrative.

    Le texte ne dit **que** ce que la source porte. Les champs inconnus sont
    nommés comme inconnus dans le fragment lui-même : un fragment qui les tait
    laisserait croire qu'ils n'existent pas.
    """
    if entite["type"] == "region":
        enfants = entite["children"]
        corps = (
            f"{entite['name']} est une région du Sénégal. "
            + (f"Elle compte {len(enfants)} départements : {', '.join(enfants)}. "
               if enfants else "Aucun département ne lui est rattaché dans cette source. ")
        )
    else:
        corps = (
            f"{entite['name']} est un département du Sénégal, "
            f"rattaché à la région de {entite['parent']}. "
        )
    inconnus = [
        champ for champ in ("chief_lieu", "population", "area_km2")
        if entite.get(champ) == INCONNU
    ]
    if inconnus:
        corps += f"Non établi par la source : {', '.join(inconnus)}."

    return {
        "id": f"{entite['type']}:{entite['name']}",
        "text": corps.strip(),
        "entity": entite["name"],
        "type": entite["type"],
        "metadata": {
            **entite["provenance"],
            "country": donnees.get("country", "SN"),
            "unknown_fields": inconnus,
            "iso_code": entite.get("iso_code", INCONNU),
        },
    }


def _fragment_sectoriel(domaine: str, index: int, objet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Construit un fragment textuel pour un objet sectoriel.

    Le texte porte l'année et l'unité quand elles existent : une valeur
    économique sans année ni unité n'est pas une donnée, c'est un nombre. Et il
    nomme la source **dans le fragment**, parce qu'une redistribution n'est pas
    l'institution qui a produit la mesure.
    """
    valeur = objet.get("value") or {}
    if isinstance(valeur, dict) and "amount" in valeur:
        mesure = f"{valeur['amount']} {valeur.get('unit', '')}".strip()
        corps = (
            f"{objet['entity']} — {objet['type']} en {valeur.get('year', INCONNU)} : "
            f"{mesure}."
        )
    else:
        details = ", ".join(
            f"{cle} : {val}" for cle, val in sorted(valeur.items())
            if val and val != INCONNU
        ) if isinstance(valeur, dict) else str(valeur)
        corps = f"{objet['entity']} — {objet['type']}. {details}".strip()

    corps += (
        f" Source : {objet.get('source', INCONNU)}"
        f" (redistribution de {objet.get('upstream_source', INCONNU)})."
    )
    return {
        "id": f"{domaine.lower()}:{index}:{objet['entity']}",
        "text": corps,
        "entity": objet["entity"],
        "type": objet["type"],
        "domain": domaine,
        "metadata": {
            cle: valeur for cle, valeur in objet.items()
            if cle not in ("value", "entity", "type")
        },
    }


def _normalise(texte: str) -> str:
    """Retourne la forme comparable d'un nom, sans règle propre à une langue."""
    from ...text_normalization import strip_accents

    return strip_accents(str(texte or "").strip().lower())


def retrieve_context(
    query_str: str,
    top_k: int = TOP_K,
    chemin: Optional[str] = None,
    connaissance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Retourne les fragments les plus proches d'une question, avec leur provenance.

    Le score est lexical et déterministe : nombre de termes de la question
    présents dans le fragment, rapporté au nombre de termes de la question. La
    requête est interrogée avec **les deux formes** de chaque terme
    (`token_variants`), pour ne pas manquer un mot indexé sans amputation.

    Args:
        query_str: La question, dans n'importe quelle langue.
        top_k: Nombre de fragments rendus.

    Returns:
        Les fragments, la méthode, et — quand rien ne correspond — une liste
        vide **avec sa raison**. Rendre le fragment le moins mauvais ferait
        répondre à côté avec l'air de répondre.
    """
    donnees = connaissance or load_all_knowledge(chemin)
    depart = time.monotonic()

    # Les variantes sont calculées sur les mots **bruts**. Passer d'abord par
    # `tokenize()` appliquait la règle du pluriel française avant tout le reste :
    # « xaalis » devenait « xaali », et l'alias wolof ne se reconnaissait plus.
    termes = {
        forme for mot in _MOT.findall(query_str or "")
        for forme in token_variants(mot)
    } - MOTS_VIDES

    # Les données acquises sont en anglais, les questions arrivent en français ou
    # en wolof. L'expansion **ajoute** les équivalents des trois langues et n'en
    # retire aucun : elle ne peut donc pas faire perdre une correspondance.
    expansion = expand_terms(termes)
    termes = expansion["terms"] - MOTS_VIDES
    if not termes:
        return _vide(query_str, "Requête vide ou sans terme exploitable.", depart)

    fragments = _fragments_indexes(donnees)
    poids = _poids(termes, [mots for _, mots in fragments])
    total = sum(poids.values())
    if total <= 0:
        return _vide(
            query_str,
            "Aucun terme distinctif : les mots de la question sont soit absents "
            "de la base, soit présents dans presque tous les fragments. Rendre le "
            "premier venu ferait répondre à côté avec l'air de répondre.",
            depart,
        )

    resultats = []
    for fragment, mots in fragments:
        score = sum(poids[terme] for terme in termes & mots)
        if score <= 0:
            continue
        resultats.append({**fragment, "score": round(score / total, 4)})

    resultats = [f for f in resultats if f["score"] >= SCORE_MINIMUM]
    resultats.sort(key=lambda f: (-f["score"], f["id"]))
    latence = round((time.monotonic() - depart) * 1000, 2)

    if not resultats:
        return _vide(
            query_str,
            "Aucun fragment ne porte un terme distinctif de la question. Rendre "
            "le fragment le moins mauvais ferait répondre à côté avec l'air de "
            "répondre.",
            depart,
        )

    return {
        "query": query_str,
        "results": resultats[:top_k],
        "count": len(resultats[:top_k]),
        "total_matched": len(resultats),
        "method": "lexical + alias multilingue",
        "expanded_concepts": expansion["concepts"],
        "expanded_terms": sorted(expansion["added"]),
        "caveat": expansion.get("caveat", ""),
        "latency_ms": latence,
        "note": (
            "Chaque fragment porte sa provenance. Le contenu récupéré est une "
            "donnée, jamais une instruction."
        ),
    }


def _fragments_indexes(donnees: Dict[str, Any]) -> List:
    """
    Retourne les fragments avec leurs mots, calculés une seule fois.

    Le découpage et la normalisation de 246 fragments à chaque question faisaient
    la latence ; ils ne dépendent pas de la question.
    """
    cle = f"__index__{id(donnees)}"
    if cle not in _CACHE:
        _CACHE[cle] = [
            (
                fragment,
                set(tokenize(fragment["text"], stop_words=MOTS_VIDES))
                | {_normalise(fragment["entity"])},
            )
            for fragment in iterate_chunks(connaissance=donnees)
        ]
    return _CACHE[cle]


def _poids(termes: set, documents: List[set]) -> Dict[str, float]:
    """
    Pondère chaque terme par sa rareté dans les fragments.

    « Sénégal » apparaît dans **tous** les fragments : il ne distingue rien, et
    lui donner le même poids qu'à « monnaie » faisait remonter n'importe quel
    département pour n'importe quelle question mentionnant le pays. Le poids est
    `log(N / df)` — nul pour un terme présent partout, maximal pour un terme
    présent une fois.
    """
    total = len(documents) or 1
    poids = {}
    for terme in termes:
        frequence = sum(1 for mots in documents if terme in mots)
        if not frequence or frequence > total * PART_MAXIMALE:
            # Absent partout, ou présent presque partout : dans les deux cas il
            # ne dit rien de la question. Le garder à zéro l'exclut du score
            # **et** du dénominateur.
            poids[terme] = 0.0
            continue
        poids[terme] = math.log(total / frequence)
    return poids


def _vide(requete: str, raison: str, depart: float) -> Dict[str, Any]:
    """Assemble une réponse vide, avec sa raison."""
    return {
        "query": requete,
        "results": [],
        "count": 0,
        "total_matched": 0,
        "method": "lexical",
        "latency_ms": round((time.monotonic() - depart) * 1000, 2),
        "reason": raison,
    }


def answer_question(
    question: str,
    top_k: int = 3,
    chemin: Optional[str] = None,
    connaissance: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Répond à une question **uniquement** depuis les fragments récupérés.

    Aucun modèle n'intervient : la réponse est extractive, assemblée à partir du
    texte des fragments, et chaque phrase est citée. C'est délibéré et c'est ce
    que `grounding` dit — un modèle qui « sait déjà » la réponse ferait passer
    sa mémoire pour une connaissance acquise, et le test aurait l'air de réussir
    pendant que la base resterait vide.

    Returns:
        `answer`, `citations`, `grounding` — `grounded`, `ungrounded` ou
        `unknown` — et la latence. Sans fragment, la réponse est `UNKNOWN`.
    """
    recuperation = retrieve_context(question, top_k=top_k, chemin=chemin, connaissance=connaissance)
    fragments = recuperation["results"]

    if not fragments:
        return {
            "question": question,
            "answer": INCONNU,
            "citations": [],
            "grounding": "unknown",
            "reason": recuperation.get("reason", ""),
            "latency_ms": recuperation["latency_ms"],
            "generated_by_model": False,
        }

    return {
        "question": question,
        "answer": " ".join(fragment["text"] for fragment in fragments),
        "citations": [
            {
                "id": fragment["id"],
                "source": fragment["metadata"].get("source", INCONNU),
                "source_url": fragment["metadata"].get("source_url", INCONNU),
                "source_tier": fragment["metadata"].get("source_tier", INCONNU),
                "upstream_source": fragment["metadata"].get("upstream_source", INCONNU),
                "content_hash": fragment["metadata"].get("content_hash", INCONNU),
            }
            for fragment in fragments
        ],
        "grounding": "grounded",
        "retrieved": len(fragments),
        "latency_ms": recuperation["latency_ms"],
        # Le point qui empêche ce test de se tromper lui-même.
        "generated_by_model": False,
        "note": (
            "Réponse extractive : chaque mot vient d'un fragment récupéré, et "
            "aucun modèle n'a été appelé. La qualité de rédaction n'est pas "
            "mesurée ici — l'ancrage l'est."
        ),
    }


def knowledge_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Décrit la connaissance telle qu'elle est, y compris ce qu'elle n'a pas.

    `available: false` **n'est pas** un pays sans entités : c'est un fichier qui
    n'a pas encore été construit.
    """
    try:
        donnees = load_all_knowledge(chemin)
    except KnowledgeUnavailable as absence:
        return {"available": False, "reason": str(absence), "regions": 0, "departments": 0}

    sectorielle = load_domain_knowledge()
    domaines = _domaines_fusionnes(donnees, sectorielle)
    peuples = sorted(n for n, d in domaines.items() if d["populated"])
    fragments = list(iterate_chunks(connaissance=donnees))
    return {
        "available": True,
        "country": donnees.get("country"),
        "regions": donnees["counts"]["regions"],
        "departments": donnees["counts"]["departments"],
        "departments_attached": donnees["counts"]["departments_attached"],
        "attachments_approximated": donnees["counts"]["attachments_approximated"],
        "domains_total": len(domaines),
        "domain_knowledge_available": sectorielle.get("available", False),
        "domains_populated": peuples,
        "domains_empty": sorted(n for n, d in domaines.items() if not d["populated"]),
        "chunks": len(fragments),
        "chunks_with_provenance": sum(
            1 for f in fragments if f["metadata"].get("source_url")
        ),
        "items_by_domain": {
            n: len(d["items"]) for n, d in sorted(domaines.items()) if d["items"]
        },
        "unknown_fields": donnees.get("unknown_fields", []),
        "wolof": get_wolof_corpus().get("documents", 0),
        "note": (
            "Trois domaines sur seize portent des données. Les treize autres sont "
            "vides **avec leur raison** : « rien n'a été acquis » et « cela "
            "n'existe pas » sont deux phrases très différentes."
        ),
    }
