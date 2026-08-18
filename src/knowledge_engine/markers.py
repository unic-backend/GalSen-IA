"""
Marqueurs textuels partagés : sujet, pays, risque, fraîcheur (VOLET 36).

Ces listes servaient d'abord aux axes du planificateur (ch. F). Le chapitre G
leur donne un second lecteur — l'agent qui propose une entrée de manifeste — et
c'est le moment où elles doivent cesser de vivre dans un agent : deux copies
d'une même liste divergent, et ce dépôt a déjà payé quatre fois ce mode de
défaillance.

**Ce que ces marqueurs ne sont pas** : un classifieur. Ils repèrent des mots au
début d'un mot, rien de plus. Tout ce qui les consomme doit rendre la méthode
(`keywords`) avec la valeur, et proposer `unspecified` quand rien ne ressort —
jamais deviner.
"""

import re
from typing import Dict, Iterable, List, Tuple

from src.text_normalization import strip_accents

from .scope import KnowledgeSubject

#: Marqueurs qui rattachent un texte au Sénégal. Villes et régions, pas
#: seulement le nom du pays : « les prix à Kaolack » est une question
#: sénégalaise qui ne prononce jamais « Sénégal ».
MARQUEURS_SENEGAL: Tuple[str, ...] = (
    "senegal", "senegalais", "dakar", "thies", "kaolack", "saint-louis",
    "ziguinchor", "casamance", "touba", "diourbel", "matam", "tambacounda",
    "louga", "fatick", "kolda", "kedougou", "sedhiou", "wolof", "pulaar",
    "serere", "cfa",
)

#: Sujets où une réponse fausse coûte plus qu'ailleurs, et leurs marqueurs.
MARQUEURS_DE_RISQUE: Dict[str, Tuple[str, ...]] = {
    KnowledgeSubject.HEALTH.value: (
        "sante", "maladie", "traitement", "medicament", "symptome", "grossesse",
        "vaccin", "dosage", "paludisme", "diabete",
    ),
    KnowledgeSubject.LAW.value: (
        "droit", "loi", "legal", "juridique", "contrat", "tribunal", "foncier",
        "heritage", "succession", "licenciement", "amende",
    ),
    KnowledgeSubject.ECONOMICS.value: (
        "impot", "taxe", "credit", "pret", "investir", "salaire", "fiscal",
        "banque", "assurance",
    ),
}

#: Marqueurs qui exigent de l'information à jour.
MARQUEURS_DE_FRAICHEUR: Tuple[str, ...] = (
    "actuel", "actuellement", "aujourd", "recent", "dernier", "derniere",
    "en vigueur", "maintenant", "2025", "2026", "cette annee",
)

#: Marqueurs de sujet, rattachés aux valeurs de `KnowledgeSubject`.
#: Volontairement courts : une liste longue donnerait l'illusion d'un classement
#: fiable, alors que ce sont des mots-clés.
MARQUEURS_DE_SUJET: Dict[str, Tuple[str, ...]] = {
    KnowledgeSubject.AGRICULTURE.value: ("mil", "arachide", "culture", "semis", "recolte",
                                         "agricole", "agriculture", "elevage"),
    KnowledgeSubject.HEALTH.value: MARQUEURS_DE_RISQUE[KnowledgeSubject.HEALTH.value],
    KnowledgeSubject.LAW.value: MARQUEURS_DE_RISQUE[KnowledgeSubject.LAW.value],
    KnowledgeSubject.ECONOMICS.value: MARQUEURS_DE_RISQUE[KnowledgeSubject.ECONOMICS.value],
    KnowledgeSubject.ADMINISTRATION.value: ("carte nationale", "passeport", "prefecture",
                                            "demarche", "administratif", "etat civil"),
    KnowledgeSubject.TECHNOLOGY.value: ("logiciel", "application", "api", "serveur",
                                        "code", "base de donnees"),
    KnowledgeSubject.EDUCATION.value: ("ecole", "universite", "scolaire", "eleve",
                                       "etudiant", "formation"),
    KnowledgeSubject.FISHERIES.value: ("peche", "pecheur", "piroque", "poisson"),
}

# Motif par marqueur : début de mot exigé, fin libre — « application » reconnaît
# « applications ». Construits au premier usage, la détection tourne souvent.
_MOTIFS: Dict[str, "re.Pattern"] = {}


def motif(marqueur: str) -> "re.Pattern":
    """Retourne le motif d'un marqueur, construit une seule fois."""
    compile_ = _MOTIFS.get(marqueur)
    if compile_ is None:
        compile_ = re.compile(r"\b" + re.escape(strip_accents(marqueur)))
        _MOTIFS[marqueur] = compile_
    return compile_


def contient(texte: str, marqueurs: Iterable[str]) -> bool:
    """Indique si l'un des marqueurs commence un mot du texte."""
    normalise = strip_accents((texte or "").lower())
    return any(motif(marqueur).search(normalise) for marqueur in marqueurs)


def sujets_reperes(texte: str) -> List[str]:
    """
    Retourne les sujets dont un marqueur apparaît dans le texte.

    Une liste vide veut dire « rien repéré », pas « rien à repérer » : c'est à
    l'appelant de rendre `unspecified` et de le dire.
    """
    return [
        sujet for sujet, marqueurs in MARQUEURS_DE_SUJET.items()
        if contient(texte, marqueurs)
    ]


def sujets_a_risque(texte: str) -> List[str]:
    """Retourne les sujets à risque repérés dans le texte."""
    return [
        sujet for sujet, marqueurs in MARQUEURS_DE_RISQUE.items()
        if contient(texte, marqueurs)
    ]


def est_senegalais(texte: str) -> bool:
    """Indique si le texte porte un marqueur sénégalais."""
    return contient(texte, MARQUEURS_SENEGAL)
