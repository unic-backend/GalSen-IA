"""
Nommer une langue sans prétendre la comprendre (C13, directive §24, §64).

## Le défaut que ce module corrige, mesuré

Avant lui, `src/creative/voice/scene.py` validait la langue d'un segment contre
`LANGUES` (`src/media/subtitles/cues.py`), qui déclare **quatre** langues :
`fr`, `en`, `wo`, `ar`. Conséquence directe et vérifiable : un segment en sérère
ou en lingala était **refusé** — or les tests d'or 5 et 6 de §63 sont exactement
un enregistrement sérère et un enregistrement lingala. La couche vocale ne
pouvait pas exprimer les scénarios que la directive lui demande de valider.

## Pourquoi une table de données, et non une énumération de plus

Ce dépôt porte déjà **deux** tables de langues, chacune pour une bonne raison :

| Table | Où | Ce qu'elle sert |
|-------|----|--------------|
| `Language` | `src/knowledge_engine/types.py` | étiqueter, stocker, filtrer un document |
| `LANGUES` | `src/media/subtitles/cues.py` | rendre un sous-titre (sens d'écriture) |

En ajouter une troisième en Python serait la duplication que §2 interdit — et
« deux vocabulaires pour un geste dérivent », ce que ce dépôt a déjà payé
plusieurs fois. Ce module n'est donc **pas** une table : c'est un registre
chargé depuis `corpus/creative/languages.yaml` qui *pointe* vers les deux
autres. Ajouter le bambara est une ligne de données, pas un commit de code —
ce que §24 et §64 demandent en propres termes.

## Ce qu'une ligne du registre autorise

Elle autorise à **nommer** la langue. Rien d'autre. Comprendre, transcrire et
parler sont trois capacités distinctes, mesurées ailleurs et reprises telles
quelles par `language_matrix()` : aujourd'hui, sur cette machine, la
transcription est indisponible et **aucune synthèse vocale n'existe dans ce
dépôt**. Déclarer vingt langues ne rend aucune de ces cases vraie, et la
confusion entre « déclarée » et « supportée » est le mensonge le moins cher
qu'une plateforme d'IA puisse écrire.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import yaml

from ...integration.degradation import DISPONIBLE
from ...knowledge_engine.types import Language
from ...media.core.capabilities import probe
from ...media.subtitles.cues import LANGUES as LANGUES_SOUS_TITRES

#: Le registre, à la racine du dépôt.
CHEMIN_PAR_DEFAUT = os.path.join(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    ),
    "corpus", "creative", "languages.yaml",
)

#: Les deux registres ISO. Les mélanger est nécessaire : le sérère et le
#: jola-fonyi n'ont pas de code à deux lettres, et l'absence est celle de la
#: liste ISO, pas celle des langues.
ISO_1 = "iso-639-1"
ISO_3 = "iso-639-3"
REGISTRES = (ISO_1, ISO_3)

#: Sens d'écriture admis. Un troisième n'est pas refusé par principe mais par
#: prudence : un sens inventé affiche une langue à l'envers.
SENS = ("ltr", "rtl")

#: L'absence déclarée, reprise du vocabulaire du programme.
INCONNU = "UNKNOWN"


class LanguageRegistryError(ValueError):
    """Un registre de langues qu'on ne peut pas croire."""


@dataclass(frozen=True)
class LanguageRecord:
    """
    Une langue que la plateforme sait nommer.

    Attributes:
        code: L'identifiant utilisé partout ailleurs.
        register: `iso-639-1` ou `iso-639-3`.
        name: Le nom anglais, pour les journaux et les rapports.
        script: Le système d'écriture, ou `UNKNOWN`.
        direction: `ltr` ou `rtl`.
        orthography: La norme orthographique, quand ce dépôt en nomme une.
        note: Ce qu'un lecteur doit savoir pour ne pas mal lire la ligne.
    """

    code: str
    register: str
    name: str
    script: str = INCONNU
    direction: str = "ltr"
    orthography: str = ""
    note: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "code": self.code, "register": self.register, "name": self.name,
            "script": self.script, "direction": self.direction,
            "orthography": self.orthography or None, "note": self.note,
        }


def _lire(path: Optional[str] = None) -> Dict[str, Any]:
    """Lit le fichier de registre, sans rien interpréter."""
    chemin = path or CHEMIN_PAR_DEFAUT
    if not os.path.isfile(chemin):
        raise LanguageRegistryError(
            f"Registre de langues introuvable : {chemin}. Sans lui, la couche "
            "créative ne peut nommer aucune langue — et en inventer une liste "
            "de secours ferait accepter des codes que personne n'a déclarés."
        )
    with open(chemin, encoding="utf-8") as fichier:
        return yaml.safe_load(fichier) or {}


def load_registry(
    path: Optional[str] = None,
) -> Tuple[Dict[str, LanguageRecord], Tuple[str, ...]]:
    """
    Charge le registre et refuse un fichier auquel on ne peut pas se fier.

    Args:
        path: Le fichier. Le registre du dépôt par défaut.

    Returns:
        Les langues par code, et les langues de validation de §24 / §64.

    Raises:
        LanguageRegistryError: Code vide ou dupliqué, registre ISO inconnu,
            sens d'écriture non déclaré, ou langue de validation absente des
            lignes. Chacun de ces cas produirait un registre qui ment
            silencieusement : un doublon fait dépendre le sens de l'ordre de
            lecture, un sens inventé affiche l'arabe à l'envers, et une langue
            de validation absente laisserait un test d'or de §63 inexécutable
            sans que rien ne le signale.
    """
    donnees = _lire(path)
    lignes = donnees.get("languages") or []
    if not lignes:
        raise LanguageRegistryError(
            "Registre vide : aucune langue déclarée. Une plateforme qui ne "
            "nomme aucune langue ne peut pas étiqueter un segment."
        )

    registre: Dict[str, LanguageRecord] = {}
    for ligne in lignes:
        code = str(ligne.get("code") or "").strip()
        if not code:
            raise LanguageRegistryError("Une ligne du registre n'a pas de code.")
        if code in registre:
            raise LanguageRegistryError(
                f"Code « {code} » déclaré deux fois. Le sens de la ligne "
                "dépendrait de l'ordre de lecture du fichier."
            )
        registre_iso = str(ligne.get("register") or "").strip()
        if registre_iso not in REGISTRES:
            raise LanguageRegistryError(
                f"Langue « {code} » : registre ISO « {registre_iso} » inconnu. "
                f"Attendu : {list(REGISTRES)}."
            )
        direction = str(ligne.get("direction") or "").strip()
        if direction not in SENS:
            raise LanguageRegistryError(
                f"Langue « {code} » : sens d'écriture « {direction} » non "
                f"déclaré. Attendu : {list(SENS)}. Un sens deviné afficherait "
                "la langue à l'envers."
            )
        registre[code] = LanguageRecord(
            code=code,
            register=registre_iso,
            name=str(ligne.get("name") or code),
            script=str(ligne.get("script") or INCONNU),
            direction=direction,
            orthography=str(ligne.get("orthography") or ""),
            note=str(ligne.get("note") or "").strip(),
        )

    validation = tuple(str(c).strip() for c in (donnees.get("validation_languages") or []))
    manquantes = [c for c in validation if c not in registre]
    if manquantes:
        raise LanguageRegistryError(
            f"Langues de validation absentes des lignes : {manquantes}. §64 "
            "les nomme comme scénarios à valider ; déclarées ici et absentes "
            "du registre, elles seraient inexécutables sans que rien ne le dise."
        )
    return registre, validation


def known_codes(path: Optional[str] = None) -> List[str]:
    """Les codes déclarés, triés."""
    registre, _ = load_registry(path)
    return sorted(registre)


def language_record(code: str, path: Optional[str] = None) -> LanguageRecord:
    """
    La ligne d'une langue.

    Args:
        code: Le code cherché.
        path: Le registre à lire.

    Returns:
        La ligne déclarée.

    Raises:
        LanguageRegistryError: Code non déclaré. Le registre ne devine pas :
            accepter un code inconnu ferait entrer une langue que rien ne sait
            afficher, et l'erreur n'apparaîtrait qu'au rendu.
    """
    registre, _ = load_registry(path)
    if code not in registre:
        raise LanguageRegistryError(
            f"Langue « {code} » non déclarée. Déclarées : {sorted(registre)}. "
            "Pour en ajouter une, ajouter une ligne à "
            "`corpus/creative/languages.yaml` — c'est une donnée, pas du code "
            "(§24, §64)."
        )
    return registre[code]


def is_declared(code: str, path: Optional[str] = None) -> bool:
    """Si une langue est nommable ici. Ne dit rien de ce qu'on peut en faire."""
    registre, _ = load_registry(path)
    return code in registre


def language_matrix(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce que la plateforme sait réellement faire de chaque langue déclarée.

    Returns:
        Par langue, cinq capacités **distinctes**, chacune reprise de la source
        qui la mesure déjà — aucune n'est réaffirmée ici :

        - `nameable` : le registre la déclare. Toujours vrai dans cette table.
        - `documentable` : `Language` (`src/knowledge_engine/types.py`) la
          connaît, donc un document peut être étiqueté et retrouvé lexicalement.
        - `subtitleable` : `LANGUES` (`src/media/subtitles/cues.py`) porte son
          sens d'écriture, donc un sous-titre se rend correctement.
        - `understood` : la sonde `transcription` est disponible.
        - `speakable` : faux partout, et pas faute de dépendance — **aucune
          synthèse vocale n'existe dans ce dépôt** (§26).

        Les cinq sont séparées parce que les confondre est précisément
        l'erreur : vingt lignes déclarées ne font pas vingt langues comprises.
    """
    registre, validation = load_registry(path)
    codes_documents = {langue.value for langue in Language}
    transcription = probe("transcription")
    comprend = transcription["state"] == DISPONIBLE

    langues = []
    for code in sorted(registre):
        ligne = registre[code]
        langues.append({
            **ligne.as_dict(),
            "nameable": True,
            "documentable": code in codes_documents,
            "subtitleable": code in LANGUES_SOUS_TITRES,
            "understood": comprend,
            "speakable": False,
            "understanding_reason": (
                "" if comprend
                else f"Transcription {transcription['state']} : "
                     f"{transcription['reason']}"
            ),
            "speaking_reason": (
                "Aucune synthèse vocale n'existe dans ce dépôt. Ce n'est pas "
                "une dépendance absente mais un module qui n'a pas été écrit "
                "— et pour une langue peu dotée, §26 rappelle que "
                "l'enregistrement d'origine reste la meilleure réponse."
            ),
        })

    return {
        "languages": langues,
        "declared": len(langues),
        "documentable": [entree["code"] for entree in langues if entree["documentable"]],
        "subtitleable": [entree["code"] for entree in langues if entree["subtitleable"]],
        "understood": [entree["code"] for entree in langues if entree["understood"]],
        "speakable": [],
        "validation_languages": list(validation),
        "note": (
            "« Déclarée » veut dire nommable. Les quatre autres colonnes sont "
            "mesurées ailleurs et reprises ici sans être réaffirmées : une "
            "seule table qui prétendrait les tenir toutes deviendrait la "
            "cinquième vérité sur les langues de ce dépôt."
        ),
    }


def coverage_report(path: Optional[str] = None) -> Dict[str, Any]:
    """
    L'écart entre les langues que §24 nomme et celles que la plateforme porte.

    Returns:
        Pour chaque langue de validation, ce qui manque — et le constat que la
        couche créative ne pouvait, avant C13, exprimer qu'un quart d'entre
        elles. C'est le genre d'écart qui reste invisible tant que personne ne
        le compte.
    """
    matrice = language_matrix(path)
    par_code = {entree["code"]: entree for entree in matrice["languages"]}
    validation = matrice["validation_languages"]

    lignes = []
    for code in validation:
        entree = par_code[code]
        lacunes = []
        if not entree["documentable"]:
            lacunes.append(
                "aucune valeur dans `Language` : un document dans cette langue "
                "ne peut pas être étiqueté ni retrouvé lexicalement"
            )
        if not entree["subtitleable"]:
            lacunes.append(
                "aucun sens d'écriture dans `LANGUES` : un sous-titre se "
                "rendrait sans direction déclarée"
            )
        lignes.append({
            "code": code, "name": entree["name"],
            "nameable": True,
            "documentable": entree["documentable"],
            "subtitleable": entree["subtitleable"],
            "gaps": lacunes,
        })

    return {
        "validation_languages": lignes,
        "count": len(lignes),
        "fully_carried": [ligne["code"] for ligne in lignes if not ligne["gaps"]],
        "partially_carried": [ligne["code"] for ligne in lignes if ligne["gaps"]],
        "note": (
            "Nommable partout : c'est ce que C13 apporte, et c'est la "
            "condition pour que les tests d'or 4, 5 et 6 de §63 — wolof, "
            "sérère, lingala — soient seulement exprimables. Les lacunes "
            "restantes sont réelles et nommées : elles appartiennent aux "
            "tables d'origine, et les combler ici en créerait une de plus."
        ),
    }
