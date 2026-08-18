"""
Normalisation orthographique du wolof selon le standard CLAD.

Le wolof s'écrit officiellement avec l'alphabet arrêté par le décret n° 2005-992
et porté par le CLAD (Université Cheikh Anta Diop) : **27 lettres**, dont trois
que le français ne connaît pas — `ë`, `ñ`, `ŋ`. Ce module est la seule autorité
orthographique du dépôt pour cette langue.

## Ce que ce module fait

1. **Compose l'Unicode** (NFC) : `n` + `~` combinant et `ñ` précomposé sont la
   même lettre pour un lecteur et deux chaînes différentes pour une machine.
2. **Uniformise ce qui n'est pas une lettre** : apostrophes typographiques,
   espaces insécables, caractères de largeur nulle, espaces multiples.
3. **Signale** ce qui sort de l'alphabet, sans le réécrire.

## Ce qu'il ne fait pas, et pourquoi c'est le point important

- **Il ne plie pas les accents.** `ë` n'est pas `e` et `ñ` n'est pas `n` : ce
  sont des lettres distinctes de l'alphabet. Les fondre est une habitude
  française qui détruit le mot.
- **Il n'applique aucune règle de pluriel.** Le wolof ne marque pas le pluriel
  par un `s` final ; retirer ce `s` produit une forme que personne n'a écrite.
- **Il ne convertit pas `ng` en `ŋ`.** La tentation est grande — `ŋ` est
  pénible à taper — mais `ng` est une suite légitime en wolof (`nguur`).
  Convertir corromprait des mots corrects. Même raisonnement pour `gn` → `ñ`,
  qui est une habitude orthographique française.
- **Il n'invente aucun mot.** Un caractère hors alphabet est **rapporté**, pas
  remplacé par le plus ressemblant.

## Orthographique n'est pas indexation

`src/text_normalization.py` plie les accents pour que la recherche fonctionne au
clavier sans accents ; c'est une opération de **recherche**, symétrique et sans
perte de correspondance. Ce module-ci travaille sur le **texte**, qui est
conservé tel qu'il s'écrit. Les deux ne se remplacent pas.
"""

import re
import unicodedata
from typing import Any, Dict, List

#: Version des règles. Elle voyage avec chaque texte normalisé : deux corpus
#: normalisés par deux versions différentes ne se comparent pas à l'aveugle.
VERSION = "1.0"

#: Le standard invoqué. Autorité orthographique, pas source du corpus.
STANDARD = "CLAD"

#: L'alphabet officiel, 27 lettres (décret n° 2005-992).
ALPHABET = (
    "a", "e", "ë", "i", "o", "u",
    "b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", "ñ", "ŋ",
    "p", "q", "r", "s", "t", "w", "x", "y",
)

#: Les trois lettres que le français ne connaît pas, et que toute la chaîne doit
#: transporter intactes.
LETTRES_PROPRES = ("ë", "ñ", "ŋ")

#: Voyelles longues : le wolof les écrit en doublant la lettre (`aa`, `ëë`).
#: Elles ne sont donc pas des caractères de plus.
VOYELLES = ("a", "e", "ë", "i", "o", "u")

#: Substitutions **sûres** : elles ne changent aucune lettre, seulement des
#: caractères de ponctuation ou d'espacement qui varient selon la source.
SUBSTITUTIONS = {
    "’": "'",   # apostrophe typographique
    "‘": "'",
    "ʼ": "'",   # apostrophe modificative
    "“": '"',
    "”": '"',
    " ": " ",   # espace insécable
    " ": " ",   # espace fine insécable
    "–": "-",   # tiret demi-cadratin
    "—": "-",
    "​": "",    # largeur nulle
    "‌": "",
    "‍": "",
    "﻿": "",
}

#: Ce qui **ne sera jamais** converti automatiquement, avec la raison. Écrit
#: plutôt que sous-entendu : c'est la première chose qu'on voudra ajouter.
CONVERSIONS_REFUSEES = {
    "ng → ŋ": (
        "`ng` est une suite légitime en wolof (`nguur`) : convertir corromprait "
        "des mots corrects, et l'erreur serait invisible."
    ),
    "gn → ñ": (
        "`gn` est une habitude orthographique française ; l'accepter ferait "
        "entrer une graphie que le standard écarte, sous couvert de correction."
    ),
    "ë → e, ñ → n, ŋ → n": (
        "Ce sont des lettres distinctes de l'alphabet, pas des variantes "
        "accentuées. Les fondre détruit le mot."
    ),
}

#: Caractères qui, dans un texte wolof, sont presque sûrement un `ŋ` mal encodé
#: — un eta grec ou un `n` à jambe longue n'a rien à faire ici. Ils sont
#: **signalés, jamais remplacés** : la correction change une lettre, et changer
#: une lettre sans qu'une personne l'ait vu est exactement ce que ce module
#: refuse. Mesurés sur UD_Wolof-WTB : 7 « η » et 1 « ƞ ».
MISENCODAGES_SUSPECTS = {
    "η": "ŋ",   # eta grec (U+03B7)
    "ƞ": "ŋ",   # n à jambe longue (U+019E)
    "ŋ": "ŋ",   # déjà correct, gardé pour que la table se lise
}

_ESPACES = re.compile(r"[ \t]+")
_LIGNES = re.compile(r"\n{3,}")
_LETTRE = re.compile(r"[^\W\d_]", re.UNICODE)


def compose(texte: str) -> str:
    """
    Compose le texte en NFC.

    `n` suivi d'un tilde combinant et `ñ` précomposé sont la même lettre pour un
    lecteur et deux chaînes pour une machine : sans cette étape, deux documents
    corrects ne se comparent pas.
    """
    return unicodedata.normalize("NFC", texte or "")


def normalize_text(texte: str) -> str:
    """
    Normalise un texte wolof selon le standard CLAD.

    Déterministe : le même texte rend toujours la même sortie, et normaliser
    deux fois donne le même résultat qu'une fois.

    Args:
        texte: Le texte brut, tel qu'il a été écrit.

    Returns:
        Le texte normalisé. **Les lettres ne sont pas touchées** — seuls
        l'encodage, la ponctuation variable et les espaces le sont.
    """
    resultat = compose(texte)
    for source, cible in SUBSTITUTIONS.items():
        resultat = resultat.replace(source, cible)
    resultat = _ESPACES.sub(" ", resultat)
    resultat = _LIGNES.sub("\n\n", resultat)
    return "\n".join(ligne.strip() for ligne in resultat.split("\n")).strip()


def is_in_alphabet(caractere: str) -> bool:
    """Indique si une lettre appartient à l'alphabet officiel."""
    return caractere.lower() in ALPHABET


def letters_outside_alphabet(texte: str) -> List[str]:
    """
    Retourne les lettres du texte qui ne sont pas dans l'alphabet officiel.

    Elles sont **rapportées, jamais remplacées** : `v` dans un nom propre
    étranger est légitime, et le remplacer par la lettre la plus ressemblante
    inventerait un mot.
    """
    trouvees = []
    for caractere in compose(texte):
        if _LETTRE.match(caractere) and not is_in_alphabet(caractere):
            if caractere.lower() not in trouvees:
                trouvees.append(caractere.lower())
    return sorted(trouvees)


def suspected_miscodings(texte: str) -> Dict[str, str]:
    """
    Retourne les caractères qui sont vraisemblablement un `ŋ` mal encodé.

    **Rien n'est corrigé.** Un eta grec dans un texte wolof est presque
    certainement une erreur d'encodage, mais « presque certainement » n'autorise
    pas une machine à changer une lettre.
    """
    present = compose(texte or "")
    return {
        caractere: cible
        for caractere, cible in MISENCODAGES_SUSPECTS.items()
        if caractere != cible and caractere in present
    }


def normalize(texte: str) -> Dict[str, Any]:
    """
    Normalise un texte et rend ce qui a été fait.

    Returns:
        `raw`, `normalized`, les lettres hors alphabet, la présence des trois
        lettres propres au wolof, et la version des règles. Le texte brut est
        **conservé** : une normalisation qui écrase l'original est irréversible.
    """
    normalise = normalize_text(texte)
    hors_alphabet = letters_outside_alphabet(normalise)
    return {
        "raw": texte,
        "normalized": normalise,
        "changed": normalise != (texte or ""),
        "letters_outside_alphabet": hors_alphabet,
        "special_letters": [
            lettre for lettre in LETTRES_PROPRES if lettre in normalise.lower()
        ],
        "suspected_miscodings": suspected_miscodings(normalise),
        "normalization_standard": STANDARD,
        "normalization_version": VERSION,
    }


def alphabet_report() -> Dict[str, Any]:
    """Décrit l'alphabet et les règles, pour qui veut vérifier sans lire le code."""
    return {
        "standard": STANDARD,
        "version": VERSION,
        "reference": "décret n° 2005-992 ; CLAD, Université Cheikh Anta Diop",
        "letters": list(ALPHABET),
        "letter_count": len(ALPHABET),
        "vowels": list(VOYELLES),
        "not_in_french": list(LETTRES_PROPRES),
        "long_vowels": "écrites en doublant la voyelle (aa, ëë) — pas de lettre de plus",
        "deterministic": True,
        "applies_french_rules": False,
        "refused_conversions": dict(CONVERSIONS_REFUSEES),
        "reported_not_fixed": dict(MISENCODAGES_SUSPECTS),
        "note": (
            "Autorité orthographique. Le corpus de travail (UD_Wolof-WTB) est une "
            "ressource distincte : il n'a pas été produit par le CLAD."
        ),
    }
