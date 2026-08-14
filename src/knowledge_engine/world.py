"""
World reference knowledge, derived from acquired datasets — never written from memory.

The Senegalese knowledge in this repository was **derived**: fourteen regions and
forty-five departments read out of published administrative boundaries, not out
of a model's general knowledge. This module does the same thing for the world,
using datasets that were already acquired for Senegal and happen to cover every
country.

Four rules, and none of them is negotiable here.

**Nothing is written from memory.** Every value comes from a row of an acquired
dataset. A field the dataset does not carry is `UNKNOWN` — never a plausible
value. This is the whole difference between a knowledge base and a confident
guess, and it is the reason the Senegalese layer is trustworthy today.

**`global` is the taxonomy, not the countries.** A fact about France holds in
France: its scope is `country:fr`. What is genuinely worldwide is the *reference*
— the code space, the UN M49 regions, the currency list. Populating `global` with
country facts would be the exact error `scope.py` exists to prevent, dressed up
as progress.

**Two sources that disagree are reported, never reconciled.** When the country
code list and the country profile give a different capital, both are kept and the
disagreement is named. Picking one silently would make the platform authoritative
about something it cannot settle.

**A country without an ISO 3166-1 alpha-3 code does not enter, and is counted.**
Dropping rows in silence is how a base ends up with a size nobody can explain.
"""

from __future__ import annotations

import csv
import io
import json
import os
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Valeur d'un champ que la source ne porte pas. `unknown` n'est pas `no`.
INCONNU = "UNKNOWN"

#: Les jeux acquis dont ce module dérive. Les mêmes fichiers que la couche
#: sénégalaise : ils sont mondiaux, et seul le nom de leur dossier dit « Sénégal »
#: parce qu'ils ont été acquis pour elle. `tier` est celui de **ce qui est
#: récupéré**, jamais celui de l'institution en amont.
JEUX_MONDIAUX: Dict[str, Dict[str, Any]] = {
    "country_codes": {
        "url": "https://raw.githubusercontent.com/datasets/country-codes/main/data/country-codes.csv",
        "file": "datasets-country-codes.csv",
        "publisher": "datasets (Frictionless Data / Datahub)",
        "upstream_source": "ISO 3166 ; Nations unies (M49) ; CLDR",
        "upstream_tier": "TIER_B_INTERNATIONAL",
        "tier": "TIER_C_SECONDARY",
        "licence": "ODC-PDDL (redistribution)",
    },
    "country_profile": {
        "url": "https://raw.githubusercontent.com/mledoze/countries/master/countries.json",
        "file": "mledoze-countries.json",
        "publisher": "mledoze/countries (base communautaire)",
        "upstream_source": "ISO 3166 ; sources ouvertes agrégées, non individuellement tracées",
        "upstream_tier": INCONNU,
        "tier": "TIER_C_SECONDARY",
        "licence": "ODbL (redistribution)",
    },
}

#: Colonnes du code list retenues, et le nom qu'elles portent dans la sortie.
#: Une colonne absente du fichier ne devient pas une clé absente de l'objet : elle
#: devient `UNKNOWN`, pour qu'un champ manquant se distingue d'un champ oublié.
CHAMPS_CODE_LIST: Dict[str, str] = {
    "iso3": "ISO3166-1-Alpha-3",
    "iso2": "ISO3166-1-Alpha-2",
    "m49": "M49",
    "official_name_en": "official_name_en",
    "official_name_fr": "official_name_fr",
    "capital": "Capital",
    "continent": "Continent",
    "region": "Region Name",
    "sub_region": "Sub-region Name",
    "currency_code": "ISO4217-currency_alphabetic_code",
    "currency_name": "ISO4217-currency_name",
    "tld": "TLD",
    "languages": "Languages",
    "is_independent": "is_independent",
}


class WorldDerivationError(ValueError):
    """Une dérivation impossible, avec sa raison."""


def _valeur(ligne: Dict[str, Any], colonne: str) -> str:
    """Retourne une valeur de colonne, ou `UNKNOWN` si elle est vide ou absente."""
    brut = str(ligne.get(colonne, "") or "").strip()
    return brut if brut else INCONNU


def _provenance(cle: str) -> Dict[str, Any]:
    """
    Assemble la provenance d'un jeu, au format du dépôt.

    Args:
        cle: L'identifiant du jeu dans `JEUX_MONDIAUX`.

    Returns:
        De quoi rouvrir la source **et** savoir jusqu'où elle fait autorité.
    """
    jeu = JEUX_MONDIAUX[cle]
    return {
        "source": jeu["publisher"],
        "source_url": jeu["url"],
        "upstream_source": jeu["upstream_source"],
        "upstream_tier": jeu["upstream_tier"],
        "source_tier": jeu["tier"],
        "licence": jeu["licence"],
        "verification_status": "derived_from_source",
        "confidence": "derived",
    }


def read_country_codes(contenu: str) -> List[Dict[str, str]]:
    """
    Lit le fichier des codes pays.

    Args:
        contenu: Le CSV, tel qu'acquis.

    Returns:
        Une ligne par pays, colonnes brutes.
    """
    return list(csv.DictReader(io.StringIO(contenu)))


def _profils_par_code(profils: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Indexe les profils pays par code alpha-3."""
    index = {}
    for profil in profils or []:
        code = str(profil.get("cca3", "") or "").strip().upper()
        if code:
            index[code] = profil
    return index


def _capitale_du_profil(profil: Dict[str, Any]) -> str:
    """La capitale déclarée par le profil, ou `UNKNOWN`."""
    capitales = profil.get("capital") or []
    return str(capitales[0]).strip() if capitales else INCONNU


def _comparable(texte: str) -> str:
    """
    Ramène un libellé à ce qui, en lui, constituerait un vrai désaccord.

    Accents et ponctuation retirés, casse ignorée : « Brasília » et « Brasilia »
    sont le même nom écrit deux fois. Rapporter cet écart comme un désaccord
    noierait les vrais — une liste où presque tout est du bruit n'est plus lue,
    et c'est aussi grave que d'en cacher un.
    """
    decompose = unicodedata.normalize("NFKD", str(texte or ""))
    sans_accent = "".join(c for c in decompose if not unicodedata.combining(c))
    return "".join(c for c in sans_accent if c.isalnum()).casefold()


def _codes_monnaie(valeur: str) -> set:
    """Les codes d'une liste de monnaies, comme ensemble : l'ordre n'est pas un écart."""
    return {
        morceau.strip().upper()
        for morceau in str(valeur or "").split(",")
        if morceau.strip()
    }


def _desaccords(ligne: Dict[str, str], profil: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Compare les deux sources et **rapporte** ce sur quoi elles divergent.

    Ne tranche rien : choisir en silence rendrait la plateforme catégorique sur
    ce qu'elle ne peut pas établir. Le plus récent n'est pas automatiquement le
    bon, et le plus détaillé non plus.

    Args:
        ligne: La ligne du code list.
        profil: Le profil correspondant, s'il existe.

    Returns:
        Un désaccord par champ divergent.
    """
    if not profil:
        return []

    ecarts = []
    capitale_liste = _valeur(ligne, CHAMPS_CODE_LIST["capital"])
    capitale_profil = _capitale_du_profil(profil)
    if (
        capitale_liste != INCONNU and capitale_profil != INCONNU
        and _comparable(capitale_liste) != _comparable(capitale_profil)
    ):
        ecarts.append({
            "field": "capital",
            "country_codes": capitale_liste,
            "country_profile": capitale_profil,
            "resolved": "no",
            "note": "Les deux sources divergent. Aucune n'est retenue contre l'autre.",
        })

    monnaie_liste = _valeur(ligne, CHAMPS_CODE_LIST["currency_code"])
    monnaies_profil = sorted((profil.get("currencies") or {}).keys())
    if (
        monnaie_liste != INCONNU and monnaies_profil
        and _codes_monnaie(monnaie_liste) != {m.upper() for m in monnaies_profil}
    ):
        ecarts.append({
            "field": "currency_code",
            "country_codes": monnaie_liste,
            "country_profile": ", ".join(monnaies_profil),
            "resolved": "no",
            "note": "Les deux sources divergent. Aucune n'est retenue contre l'autre.",
        })
    return ecarts


def derive_countries(
    lignes: Iterable[Dict[str, str]],
    profils: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Dérive un objet par pays depuis les jeux acquis.

    Chaque pays reçoit **sa propre portée** (`country:xx`) : un fait sur la
    France vaut en France. Ce qui est mondial est la référence, pas les pays.

    Args:
        lignes: Les lignes du code list.
        profils: Les profils pays, pour les champs complémentaires et la
            confrontation.

    Returns:
        Les pays dérivés, les lignes refusées avec leur raison, et les
        désaccords entre sources.
    """
    index = _profils_par_code(profils or [])
    pays: List[Dict[str, Any]] = []
    refusees: List[Dict[str, str]] = []
    desaccords: List[Dict[str, Any]] = []

    for ligne in lignes:
        code = _valeur(ligne, CHAMPS_CODE_LIST["iso3"]).upper()
        if code == INCONNU or len(code) != 3:
            # Compté, jamais écarté en silence : une base dont la taille
            # s'explique par des lignes disparues n'est pas vérifiable.
            refusees.append({
                "row": _valeur(ligne, CHAMPS_CODE_LIST["official_name_en"]),
                "reason": "Aucun code ISO 3166-1 alpha-3 : le pays n'a pas d'identité stable.",
            })
            continue

        profil = index.get(code)
        champs = {
            nom: _valeur(ligne, colonne)
            for nom, colonne in CHAMPS_CODE_LIST.items()
        }
        iso2 = champs["iso2"]
        ecarts = _desaccords(ligne, profil)
        desaccords.extend({"iso3": code, **ecart} for ecart in ecarts)

        pays.append({
            **champs,
            # Un fait sur un pays vaut dans ce pays. Le ranger en `global`
            # ferait passer une connaissance locale pour universelle.
            "scope": f"country:{iso2.lower()}" if iso2 != INCONNU else INCONNU,
            "area_km2": (profil or {}).get("area", INCONNU),
            "borders": list((profil or {}).get("borders") or []),
            "un_member": (profil or {}).get("unMember", INCONNU),
            "capital_from_profile": _capitale_du_profil(profil) if profil else INCONNU,
            "has_profile": profil is not None,
            "disagreements": ecarts,
            "provenance": _provenance("country_codes"),
        })

    return {
        "countries": sorted(pays, key=lambda entree: entree["iso3"]),
        "refused_rows": refusees,
        "disagreements": desaccords,
    }


def derive_reference(pays: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Dérive la référence mondiale — ce qui est réellement de portée `global`.

    Les continents, les régions et sous-régions M49, l'espace des monnaies : ces
    taxonomies ne valent pas « dans un pays », elles valent partout. Ce sont les
    seuls objets que ce module range en `global`.

    Args:
        pays: Les pays dérivés.

    Returns:
        La taxonomie, avec le nombre de pays qui l'attestent.
    """
    def _compter(champ: str) -> Dict[str, int]:
        compte: Dict[str, int] = {}
        for entree in pays:
            valeur = entree.get(champ, INCONNU)
            if valeur and valeur != INCONNU:
                compte[valeur] = compte.get(valeur, 0) + 1
        return dict(sorted(compte.items()))

    return {
        "scope": "global",
        "continents": _compter("continent"),
        "regions": _compter("region"),
        "sub_regions": _compter("sub_region"),
        "currencies": _compter("currency_code"),
        "provenance": _provenance("country_codes"),
        "note": (
            "Taxonomies de portée mondiale. Les faits par pays ne sont **pas** "
            "ici : ils portent la portée de leur pays."
        ),
    }


def build_world_knowledge(
    contenu_codes: str, profils: Optional[Iterable[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Construit l'objet de connaissance mondiale complet.

    Args:
        contenu_codes: Le CSV des codes pays, tel qu'acquis.
        profils: Les profils pays.

    Returns:
        La référence mondiale, les pays, et tout ce qui n'a pas pu être établi.

    Raises:
        WorldDerivationError: Si aucun pays ne peut être dérivé. Rendre un objet
            vide laisserait croire que le monde est vide.
    """
    derive = derive_countries(read_country_codes(contenu_codes), profils)
    if not derive["countries"]:
        raise WorldDerivationError(
            "Aucun pays dérivé : la source est absente ou n'a pas la forme "
            "attendue. Un objet vide laisserait croire que le monde l'est."
        )

    pays = derive["countries"]
    sans_profil = [entree["iso3"] for entree in pays if not entree["has_profile"]]
    return {
        "built_from": {cle: jeu["file"] for cle, jeu in JEUX_MONDIAUX.items()},
        "reference": derive_reference(pays),
        "countries": pays,
        "counts": {
            "countries": len(pays),
            "with_profile": len(pays) - len(sans_profil),
            "refused_rows": len(derive["refused_rows"]),
            "disagreements": len(derive["disagreements"]),
        },
        "refused_rows": derive["refused_rows"],
        # Rapportés, jamais résolus.
        "disagreements": derive["disagreements"],
        "without_profile": sans_profil,
        "rules": [
            "Rien n'est écrit de mémoire : chaque valeur vient d'une ligne d'un "
            "jeu acquis, et un champ absent vaut UNKNOWN.",
            "`global` porte la taxonomie, pas les pays : un fait sur un pays "
            "porte la portée de ce pays.",
            "Deux sources qui divergent sont rapportées, jamais réconciliées.",
            "Une ligne sans code ISO 3166-1 alpha-3 n'entre pas, et elle est "
            "comptée.",
        ],
    }


def country_lookup(
    monde: Dict[str, Any], code: str,
) -> Tuple[Optional[Dict[str, Any]], str]:
    """
    Cherche un pays par code alpha-2 ou alpha-3.

    Args:
        monde: L'objet construit.
        code: Le code cherché.

    Returns:
        Le pays et un motif ; `(None, …)` si le code est inconnu — jamais le
        pays le plus proche.
    """
    cherche = str(code or "").strip().upper()
    if not cherche:
        return None, "Aucun code demandé."
    for entree in monde.get("countries", []):
        if cherche in (entree["iso3"], entree["iso2"]):
            return entree, f"Pays trouvé : {entree['official_name_en']}."
    return None, (
        f"Aucun pays sous le code « {cherche} ». Le plus proche n'est pas rendu : "
        "un code voisin désigne un autre pays."
    )


#: Là où la connaissance dérivée est écrite par `scripts/build_world_knowledge.py`.
FICHIER_DERIVE = os.path.join("data", "processed_global", "world_countries.json")

#: Cache du fichier dérivé. Il est lu une fois : 280 ko relus à chaque question
#: coûteraient plus cher que la question elle-même.
_CACHE: Dict[str, Any] = {}


def load_world(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge la connaissance mondiale dérivée.

    Args:
        chemin: Le fichier. Celui du dépôt par défaut.

    Returns:
        L'objet dérivé, ou un objet **vide qui se déclare tel** si le fichier
        n'a jamais été construit. Un monde absent n'est pas un monde vide, et la
        différence doit se voir avant la première question.
    """
    cible = chemin or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        FICHIER_DERIVE,
    )
    if cible in _CACHE:
        return _CACHE[cible]

    if not os.path.isfile(cible):
        vide = {
            "countries": [], "reference": {}, "counts": {"countries": 0},
            "built": False,
            "reason": (
                "La connaissance mondiale n'a jamais été construite. "
                "`python scripts/build_world_knowledge.py` la dérive des jeux "
                "acquis. Absente n'est pas vide."
            ),
        }
        _CACHE[cible] = vide
        return vide

    with open(cible, "r", encoding="utf-8") as flux:
        monde = json.load(flux)
    monde["built"] = True
    _CACHE[cible] = monde
    return monde


def _noms_comparables(pays: Dict[str, Any]) -> set:
    """Les formes sous lesquelles un pays peut être nommé."""
    return {
        _comparable(pays.get(champ, ""))
        for champ in ("official_name_en", "official_name_fr", "iso2", "iso3")
        if pays.get(champ, INCONNU) != INCONNU
    }


def answer_country(question: str, monde: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Répond sur un pays, ou dit `UNKNOWN`.

    **Aucune approximation.** Un nom qui ne correspond exactement à aucun pays
    ne rend pas le plus proche : « Niger » et « Nigeria » sont deux pays, et
    rendre l'un pour l'autre serait la pire réponse possible — plausible et
    fausse.

    Args:
        question: Un code ou un nom de pays, en français ou en anglais.
        monde: La connaissance chargée, pour éviter une relecture.

    Returns:
        Le verdict, le pays s'il est trouvé, et ce qui trancherait sinon.
    """
    monde = monde if monde is not None else load_world()
    if not monde.get("countries"):
        return {
            "status": "UNKNOWN",
            "country": None,
            "reason": monde.get("reason", "Aucune connaissance mondiale chargée."),
        }

    cherche = _comparable(question)
    if not cherche:
        return {"status": "UNKNOWN", "country": None,
                "reason": "Aucun pays demandé."}

    for pays in monde["countries"]:
        if cherche in _noms_comparables(pays):
            return {
                "status": "FOUND",
                "country": pays,
                "reason": f"Pays trouvé : {pays['official_name_en']}.",
                "scope": pays["scope"],
                "provenance": pays.get("provenance", {}),
            }

    return {
        "status": "UNKNOWN",
        "country": None,
        "reason": (
            f"Aucun pays nommé « {question} » dans la connaissance dérivée. Le "
            "plus proche n'est pas rendu : deux pays voisins par le nom sont "
            "deux pays."
        ),
        "what_would_settle_it": [
            "Vérifier le code ISO 3166-1 (alpha-2 ou alpha-3) du pays.",
            "Le nom officiel anglais ou français, tel que publié par la source.",
        ],
    }


def answer_field(
    question: str, field: str, monde: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Répond sur un champ d'un pays, avec sa provenance et ses désaccords.

    Un champ que la source ne porte pas rend `UNKNOWN` : la plateforme ne
    complète pas une source par ce qu'un modèle croit savoir.

    Args:
        question: Le pays.
        field: Le champ demandé.
        monde: La connaissance chargée.

    Returns:
        La valeur, sa provenance, et les désaccords qui la concernent.
    """
    trouve = answer_country(question, monde)
    if trouve["status"] != "FOUND":
        return trouve

    pays = trouve["country"]
    if field not in pays:
        return {
            "status": "UNKNOWN", "country": pays["iso3"], "field": field,
            "reason": (
                f"Le champ « {field} » n'existe pas dans la connaissance "
                f"dérivée. Champs disponibles : {', '.join(sorted(CHAMPS_CODE_LIST))}."
            ),
        }

    valeur = pays[field]
    if valeur == INCONNU or valeur == "" or valeur == []:
        return {
            "status": "UNKNOWN", "country": pays["iso3"], "field": field,
            "reason": (
                f"La source ne porte pas « {field} » pour "
                f"{pays['official_name_en']}. La plateforme ne le complète pas "
                "par ce qu'un modèle croit savoir."
            ),
        }

    return {
        "status": "FOUND",
        "country": pays["iso3"],
        "field": field,
        "value": valeur,
        "scope": pays["scope"],
        "provenance": pays.get("provenance", {}),
        # Le désaccord voyage avec la valeur : une réponse qui le tairait serait
        # plus nette et moins vraie.
        "disagreements": [
            ecart for ecart in pays.get("disagreements", [])
            if ecart.get("field") == field
        ],
    }


def world_report(monde: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Ce que la connaissance mondiale contient, et ce qu'elle ne fait pas.

    Returns:
        Les comptes, la taxonomie et les règles tenues.
    """
    monde = monde if monde is not None else load_world()
    reference = monde.get("reference") or {}
    return {
        "built": monde.get("built", False),
        "counts": monde.get("counts", {}),
        "regions": reference.get("regions", {}),
        "continents": reference.get("continents", {}),
        "currencies_declared": len(reference.get("currencies", {})),
        "built_from": monde.get("built_from", {}),
        "rules": monde.get("rules", []),
        "does_not": [
            "Répondre par approximation : un nom inconnu rend UNKNOWN, jamais "
            "le pays le plus proche.",
            "Compléter une source manquante par ce qu'un modèle croit savoir.",
            "Trancher un désaccord entre deux sources : il voyage avec la "
            "valeur.",
            "Servir le droit, l'administration ou les langues d'un pays : ces "
            "sujets ne se transportent pas, et rien ici ne les porte.",
        ],
    }
