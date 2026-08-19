"""
Le style, nommé — et tenu hors du monde (C19, §46).

## Le trou que ce module comble

L'audit de PHASE 0 avait classé le StyleEngine `EXTENSION_REQUIRED` et le plan
des 43 phases ne lui a jamais alloué de phase : il est passé entre les mailles.
Résultat mesuré avant d'écrire ce module — la représentation créative suivait
`domain`, `duration_seconds` et `aspect`, et **rien d'autre**. « Une scène en
style anime » perdait le mot « anime » entre la demande et le rendu.

La moitié négative de §46, elle, était déjà tenue : `WorldState` **exclut**
délibérément le style depuis C09. Ce module apporte la moitié positive.

## Pourquoi le style ne peut pas vivre dans le monde

La même rue de Dakar, les deux mêmes personnes, la même boutique, peuvent être
rendues en photoréaliste ou en dessin animé. Si le style était une propriété du
monde, le premier contrôle de continuité comparerait un documentaire à un
dessin et signalerait une rupture qui n'existe pas.

Le style voyage donc **à côté** du monde, sur la représentation créative : c'est
une entrée du rendu, jamais un fait du monde. `world_is_style_free()` le vérifie
plutôt que de le laisser à la discipline de celui qui écrira le module suivant.

## Ce que le module refuse

**Il ne choisit pas de style par défaut.** Une demande sans style nommé reste
sans style, et `resolve_style()` rend `None`. Poser « photoréaliste » parce que
c'est le plus courant produirait une vidéo dans un style que personne n'a
demandé — exactement ce que la représentation créative existe pour empêcher, et
la raison pour laquelle le style **n'est pas** dans `CHAMPS_REQUIS` : son
absence est légitime, ce n'est pas un manque à combler.

**Il ne devine pas non plus.** Un mot proche mais non déclaré n'est pas rattaché
au style le plus ressemblant : « rétro » n'est pas « fantastique ».
"""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml

#: Le registre, à la racine du dépôt.
CHEMIN_PAR_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "corpus", "creative", "styles.yaml",
)

#: Le nom du champ posé sur la représentation. Un seul endroit le déclare.
CHAMP = "style"


class StyleRegistryError(ValueError):
    """Un registre de styles auquel on ne peut pas se fier."""


@dataclass(frozen=True)
class StyleRecord:
    """
    Un style que la plateforme sait nommer.

    Attributes:
        style_id: L'identifiant utilisé partout ailleurs.
        name: Le nom anglais, pour les journaux.
        family: Le regroupement — jamais un classement de qualité.
        aliases: Ce qu'une personne écrit réellement, français compris.
        note: Ce qu'un lecteur doit savoir pour ne pas mal lire la ligne.
    """

    style_id: str
    name: str
    family: str
    aliases: Tuple[str, ...] = ()
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"style_id": self.style_id, "name": self.name,
                "family": self.family, "aliases": list(self.aliases),
                "note": self.note}


def _plier(texte: str) -> str:
    """
    Réduit un texte à une forme comparable : minuscules, accents pliés.

    Les accents sont pliés **des deux côtés** de la comparaison, donc elle reste
    symétrique : « animé » et « anime » se rejoignent, et aucune écriture n'est
    privilégiée. C'est le même geste que `src/text_normalization.py` applique
    déjà aux alias multilingues.
    """
    sans_accent = unicodedata.normalize("NFD", str(texte or "").lower())
    sans_accent = "".join(c for c in sans_accent
                          if unicodedata.category(c) != "Mn")
    return re.sub(r"[\s\-_]+", " ", sans_accent).strip()


def load_styles(path: Optional[str] = None) -> Dict[str, StyleRecord]:
    """
    Charge le registre et refuse un fichier qui mentirait en silence.

    Args:
        path: Le fichier. Le registre du dépôt par défaut.

    Returns:
        Les styles par identifiant.

    Raises:
        StyleRegistryError: Fichier absent, registre vide, identifiant vide ou
            dupliqué, famille non déclarée, ou **alias partagé par deux
            styles**. Ce dernier cas est le plus vicieux : « manga » rattaché à
            deux styles ferait dépendre le rendu de l'ordre de lecture du
            fichier, et personne ne remonterait jusque-là.
    """
    chemin = path or CHEMIN_PAR_DEFAUT
    if not os.path.isfile(chemin):
        raise StyleRegistryError(
            f"Registre de styles introuvable : {chemin}. En inventer une liste "
            "de secours ferait accepter des styles que personne n'a déclarés."
        )
    with open(chemin, encoding="utf-8") as fichier:
        donnees = yaml.safe_load(fichier) or {}

    familles = set(donnees.get("families") or [])
    if not familles:
        raise StyleRegistryError("Aucune famille déclarée.")

    lignes = donnees.get("styles") or []
    if not lignes:
        raise StyleRegistryError(
            "Registre vide : la plateforme ne pourrait nommer aucun style, et "
            "une demande de style se perdrait en silence."
        )

    registre: Dict[str, StyleRecord] = {}
    vus: Dict[str, str] = {}
    for ligne in lignes:
        identifiant = str(ligne.get("id") or "").strip()
        if not identifiant:
            raise StyleRegistryError("Une ligne du registre n'a pas d'identifiant.")
        if identifiant in registre:
            raise StyleRegistryError(
                f"Style « {identifiant} » déclaré deux fois."
            )
        famille = str(ligne.get("family") or "").strip()
        if famille not in familles:
            raise StyleRegistryError(
                f"Style « {identifiant} » : famille « {famille} » non "
                f"déclarée. Déclarées : {sorted(familles)}."
            )

        alias = tuple(str(a) for a in (ligne.get("aliases") or []))
        for terme in (identifiant, str(ligne.get("name") or ""), *alias):
            plie = _plier(terme)
            if not plie:
                continue
            if plie in vus and vus[plie] != identifiant:
                raise StyleRegistryError(
                    f"L'alias « {terme} » désigne à la fois "
                    f"« {vus[plie]} » et « {identifiant} ». Le rendu "
                    "dépendrait de l'ordre de lecture du fichier."
                )
            vus[plie] = identifiant

        registre[identifiant] = StyleRecord(
            style_id=identifiant, name=str(ligne.get("name") or identifiant),
            family=famille, aliases=alias,
            note=str(ligne.get("note") or "").strip(),
        )
    return registre


def known_styles(path: Optional[str] = None) -> List[str]:
    """Les identifiants déclarés, triés."""
    return sorted(load_styles(path))


def style_record(style_id: str, path: Optional[str] = None) -> StyleRecord:
    """
    La ligne d'un style.

    Raises:
        StyleRegistryError: Style non déclaré. Le registre ne devine pas : un
            mot proche n'est pas rattaché au style le plus ressemblant, parce
            que « rétro » n'est pas « fantastique ».
    """
    registre = load_styles(path)
    if style_id not in registre:
        raise StyleRegistryError(
            f"Style « {style_id} » non déclaré. Déclarés : {sorted(registre)}. "
            "Pour en ajouter un, c'est une ligne dans "
            "`corpus/creative/styles.yaml` — une donnée, pas du code (§46)."
        )
    return registre[style_id]


def resolve_style(
    text: str, path: Optional[str] = None,
) -> Optional[StyleRecord]:
    """
    Trouve le style **nommé** dans une demande, ou rien.

    Args:
        text: La demande, en langage naturel.
        path: Le registre à lire.

    Returns:
        Le style si la demande en nomme un, `None` sinon. **`None` est une
        réponse**, pas un échec : une production sans style demandé reste sans
        style, et poser « photoréaliste » parce que c'est le plus courant
        rendrait une vidéo dans un style que personne n'a choisi.

        Quand plusieurs styles sont nommés, **aucun n'est retenu** : « en anime
        ou en dessin animé, je ne sais pas » est une hésitation de l'auteur, et
        en trancher une au hasard revient à décider à sa place.
    """
    registre = load_styles(path)
    plie = _plier(text)

    # Toutes les occurrences, avec leur étendue dans le texte.
    occurrences: List[Tuple[int, int, str]] = []
    for record in registre.values():
        for terme in (record.style_id, record.name, *record.aliases):
            forme = _plier(terme)
            if not forme:
                continue
            # Frontières de mot : « bd » ne doit pas s'allumer dans « abdomen ».
            for trouve in re.finditer(rf"(?<!\w){re.escape(forme)}(?!\w)", plie):
                occurrences.append((trouve.start(), trouve.end(), record.style_id))

    # Une occurrence contenue dans une autre est écartée : « dessin animé »
    # contient « animé », et les compter toutes deux ferait passer une demande
    # parfaitement claire pour une hésitation entre deux styles. L'énoncé le
    # plus long est le plus précis, et c'est celui de l'auteur.
    retenues = [
        (debut, fin, style) for debut, fin, style in occurrences
        if not any(autre_debut <= debut and fin <= autre_fin
                   and (autre_fin - autre_debut) > (fin - debut)
                   for autre_debut, autre_fin, _ in occurrences)
    ]

    uniques = sorted({style for _, _, style in retenues})
    if len(uniques) != 1:
        return None
    return registre[uniques[0]]


def apply_style(
    representation: Any, text: Optional[str] = None,
    path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Pose le style sur une représentation, quand la demande en nomme un.

    Args:
        representation: La `CreativeRepresentation` à compléter.
        text: La demande. L'intention de la représentation par défaut.
        path: Le registre à lire.

    Returns:
        Ce qui a été posé, ou la raison de ne rien poser. Le champ est posé par
        `state()` avec la provenance **`STATED`** : le style vient de la
        personne, il n'est pas déduit. Le poser en `INFERRED` laisserait croire
        qu'un module l'a choisi, et c'est précisément la confusion que la
        représentation créative existe pour empêcher.

        Rien n'est posé quand aucun style n'est nommé — et l'absence de style
        n'est **pas** un manque : elle n'apparaît pas dans les questions de
        clarification, parce qu'une production sans style demandé est
        parfaitement légitime.
    """
    demande = text if text is not None else getattr(representation, "intent", "")
    record = resolve_style(demande, path)
    if record is None:
        return {
            "applied": False, "style_id": None,
            "reason": (
                "Aucun style déclaré n'est nommé dans la demande — ou plusieurs "
                "le sont. Rien n'est posé : choisir à la place de l'auteur "
                "rendrait une vidéo dans un style que personne n'a demandé, et "
                "l'absence de style est un état légitime, pas un manque."
            ),
        }
    representation.state(CHAMP, record.style_id, source="style registry")
    return {"applied": True, "style_id": record.style_id,
            "family": record.family,
            "reason": "Le style est nommé dans la demande, donc **déclaré**."}


def world_is_style_free(world: Any) -> Dict[str, Any]:
    """
    Vérifie que le style n'a pas fui dans le monde (§46).

    Args:
        world: Un `WorldState`.

    Returns:
        Le constat. C'est une vérification et non une convention : la règle est
        facile à respecter tant qu'on y pense, et le module suivant qui ajoutera
        « juste un champ » au monde n'y pensera pas.

        Ce qu'un style dans le monde casserait : le premier contrôle de
        continuité comparerait un documentaire à un dessin animé et signalerait
        une rupture qui n'existe pas.
    """
    suspects = sorted(
        nom for nom in dir(world)
        if "style" in nom.lower() and not nom.startswith("__")
    )
    faits = []
    lister = getattr(world, "facts", None)
    if callable(lister):
        try:
            faits = [f for f in lister() if "style" in str(f).lower()]
        except TypeError:  # signature différente : rien à conclure
            faits = []

    return {
        "style_free": not suspects and not faits,
        "attributes": suspects,
        "facts": [str(f) for f in faits],
        "reason": (
            "Le monde ne porte aucun style."
            if not suspects and not faits else
            "Le monde porte du style : un contrôle de continuité comparerait "
            "un documentaire à un dessin animé et signalerait une rupture qui "
            "n'existe pas."
        ),
    }


def style_report(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Les styles déclarés et les règles qui les gouvernent.

    Returns:
        De quoi juger sans lire le code — y compris ce que nommer un style
        **ne** dit **pas** : qu'un fournisseur sache le produire.
    """
    registre = load_styles(path)
    par_famille: Dict[str, List[str]] = {}
    for record in registre.values():
        par_famille.setdefault(record.family, []).append(record.style_id)

    return {
        "styles": [record.as_dict() for record in
                   sorted(registre.values(), key=lambda r: r.style_id)],
        "count": len(registre),
        "by_family": {famille: sorted(ids)
                      for famille, ids in sorted(par_famille.items())},
        "field": CHAMP,
        "required": False,
        "rules": [
            "Un style est une **ligne de données** : en ajouter un ne demande "
            "aucun changement de code (§46, « future styles »).",
            "Le style n'est **pas** dans `WorldState` : le même monde peut "
            "être rendu photoréaliste ou animé, et l'y ranger ferait comparer "
            "un documentaire à un dessin au premier contrôle de continuité.",
            "Aucun style par défaut. Une demande sans style reste sans style, "
            "et cette absence n'est pas un manque à combler.",
            "Plusieurs styles nommés : aucun n'est retenu. Trancher "
            "l'hésitation de l'auteur revient à décider à sa place.",
            "Un alias partagé par deux styles est refusé au chargement : le "
            "rendu dépendrait de l'ordre de lecture du fichier.",
            "Une famille regroupe, elle ne classe pas : « graphic » n'est pas "
            "au-dessous de « photoreal », c'est une intention différente.",
        ],
        "does_not": [
            "Dire qu'un fournisseur sait produire ce style — c'est une "
            "capacité, sondée et rapportée ailleurs.",
            "Rattacher un mot proche au style le plus ressemblant : « rétro » "
            "n'est pas « fantastique ».",
        ],
    }
