"""
Détecter une langue, et ne jamais confondre cela avec la comprendre (ADR-021, étape 6).

`languages.py` répond depuis le VOLET 36 à « que sait faire la plateforme dans
cette langue ? », capacité par capacité. Sa réponse pour la détection était
`no` : *« Aucun détecteur de langue n'existe, pour aucune langue. La langue est
déclarée à l'ingestion, jamais inférée. »*

Ce module ferme cette capacité — **elle seule**. Détecter reste la plus pauvre
des neuf capacités de cette liste : savoir qu'un texte est en wolof n'apprend
rien sur la façon de le récupérer, de le normaliser ou d'y répondre.

## Ce qui rend ce détecteur honnête plutôt que confiant

1. **Il ne connaît que les langues qui ont une liste relue.** Les marqueurs sont
   dans `corpus/languages/markers.yaml`, une donnée relue, pas un modèle.
2. **Le sérère n'a aucune liste**, et le détecteur rend `unknown` pour lui
   plutôt qu'un voisin plausible. Un sérère détecté comme du wolof serait pire
   qu'une absence de réponse.
3. **Les listes wolof et pulaar sont marquées non relues**, et chaque verdict
   qu'elles produisent porte cette mention. Un résultat aussi affirmatif que
   pour le français ferait croire à une capacité qui n'existe pas.
4. **Un texte trop court, un score trop faible ou deux langues au coude à coude
   rendent `unknown`.** `unknown` n'est pas un échec : c'est le résultat correct
   quand la mesure ne tranche pas.

## Détecté contre déclaré

La langue déclarée au manifeste et la langue détectée sont **deux faits
différents**. Quand ils divergent, ce module ne choisit pas : il le signale, et
le document part en quarantaine — c'est une personne qui tranche.
"""

import os
import re
from typing import Any, Dict, List, Optional

#: Fichier de marqueurs, relatif à la racine du dépôt.
MARQUEURS_PAR_DEFAUT = os.path.join("corpus", "languages", "markers.yaml")

#: Ce que rend le détecteur quand il ne tranche pas. Ce n'est pas un échec.
INCONNU = "unknown"

#: En dessous de ce nombre de mots, aucun verdict n'est rendu. Un texte de dix
#: mots peut être n'importe quoi, et une langue « détectée » dessus est un
#: tirage au sort présenté comme une mesure.
MOTS_MINIMUM = 25

#: Part minimale de mots outils reconnus pour qu'un verdict soit rendu.
SEUIL = 0.02

#: Écart minimal entre les deux meilleurs scores. En dessous, les deux langues
#: sont au coude à coude et choisir serait arbitraire.
ECART_MINIMUM = 1.25

_MOT = re.compile(r"[^\W\d_]+", re.UNICODE)

_CACHE: Dict[str, Dict[str, Any]] = {}


def _racine() -> str:
    """Retourne la racine du dépôt."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_markers(chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge les listes de marqueurs déclarées.

    Un fichier absent rend un détecteur **sans aucune langue**, qui répondra
    `unknown` à tout : perdre la donnée ne doit pas produire des verdicts
    inventés.
    """
    import yaml

    cible = chemin or os.path.join(_racine(), MARQUEURS_PAR_DEFAUT)
    if cible in _CACHE:
        return _CACHE[cible]

    if not os.path.isfile(cible):
        resultat = {"languages": {}, "loaded": False, "path": cible}
        _CACHE[cible] = resultat
        return resultat

    with open(cible, "r", encoding="utf-8") as fichier:
        donnees = yaml.safe_load(fichier) or {}

    langues = {}
    for code, entree in (donnees.get("languages") or {}).items():
        marqueurs = {str(mot).strip().lower() for mot in (entree.get("markers") or [])}
        if not marqueurs:
            continue
        langues[str(code)] = {
            "markers": marqueurs,
            "reviewed": bool(entree.get("reviewed", False)),
            "reviewed_by": str(entree.get("reviewed_by") or ""),
            "note": str(entree.get("note") or ""),
        }

    resultat = {"languages": langues, "loaded": True, "path": cible}
    _CACHE[cible] = resultat
    return resultat


def known_detectable_languages(chemin: Optional[str] = None) -> List[str]:
    """Retourne les langues que ce détecteur peut nommer."""
    return sorted(load_markers(chemin)["languages"])


def detect_language(texte: str, chemin: Optional[str] = None) -> Dict[str, Any]:
    """
    Nomme la langue d'un texte, ou dit qu'il ne la nomme pas.

    Args:
        texte: Le texte extrait du document.
        chemin: Fichier de marqueurs, pour les tests.

    Returns:
        `language` (code ou `unknown`), `confidence`, `scores` par langue,
        `reviewed` — faux quand la liste qui a tranché n'a pas été relue par un
        locuteur — et `why`, qui dit pourquoi le verdict est celui-là.
    """
    registre = load_markers(chemin)
    mots = [mot.lower() for mot in _MOT.findall(texte or "")]

    if len(mots) < MOTS_MINIMUM:
        return _verdict(
            INCONNU, 0.0, {},
            f"Texte trop court ({len(mots)} mots, minimum {MOTS_MINIMUM}). "
            "Une langue « détectée » sur dix mots est un tirage au sort.",
        )
    if not registre["languages"]:
        return _verdict(
            INCONNU, 0.0, {},
            "Aucune liste de marqueurs chargée : le détecteur ne connaît aucune langue.",
        )

    total = len(mots)
    scores = {
        code: sum(1 for mot in mots if mot in entree["markers"]) / total
        for code, entree in registre["languages"].items()
    }
    classement = sorted(scores.items(), key=lambda couple: couple[1], reverse=True)
    meilleur, score = classement[0]

    if score < SEUIL:
        return _verdict(
            INCONNU, round(score, 4), scores,
            f"Aucune langue au-dessus du seuil ({SEUIL}). Le texte peut être dans une "
            "langue sans liste — le sérère n'en a aucune, délibérément.",
        )

    second = classement[1][1] if len(classement) > 1 else 0.0
    if second > 0 and score < second * ECART_MINIMUM:
        return _verdict(
            INCONNU, round(score, 4), scores,
            f"« {meilleur} » et « {classement[1][0]} » sont au coude à coude "
            f"({score:.3f} contre {second:.3f}) : choisir serait arbitraire.",
        )

    entree = registre["languages"][meilleur]
    return _verdict(
        meilleur, round(score, 4), scores,
        f"{score:.1%} des mots sont des mots outils du « {meilleur} ».",
        reviewed=entree["reviewed"],
        note=entree["note"],
    )


def _verdict(
    langue: str,
    confiance: float,
    scores: Dict[str, float],
    pourquoi: str,
    reviewed: bool = True,
    note: str = "",
) -> Dict[str, Any]:
    """Assemble un verdict de détection, avec ce qui le nuance."""
    resultat = {
        "language": langue,
        "confidence": confiance,
        "scores": {code: round(valeur, 4) for code, valeur in sorted(scores.items())},
        "method": "function-word markers",
        "reviewed": reviewed,
        "why": pourquoi,
    }
    if not reviewed and langue != INCONNU:
        resultat["caveat"] = (
            f"La liste « {langue} » n'a pas été relue par un locuteur : ce verdict "
            "vaut un signalement, pas une certitude. " + note
        ).strip()
    return resultat


def reconcile(detected: Dict[str, Any], declared: str = "") -> Dict[str, Any]:
    """
    Confronte la langue détectée et la langue déclarée, **sans choisir**.

    Args:
        detected: Le verdict de `detect_language()`.
        declared: La langue déclarée au manifeste ou par le registre.

    Returns:
        `agreement` — `agree`, `undetected`, `undeclared`, `disagree` — et
        `quarantine`, vrai quand une personne doit trancher. Choisir
        automatiquement entre les deux effacerait l'information qui compte : que
        deux sources de vérité se contredisent.
    """
    declaree = (declared or "").strip().lower()
    trouvee = detected.get("language", INCONNU)

    if trouvee == INCONNU:
        accord, quarantaine, raison = "undetected", False, (
            "La détection n'a pas tranché ; la langue déclarée reste la seule "
            "information, et elle n'est pas contredite."
        )
    elif not declaree:
        accord, quarantaine, raison = "undeclared", False, (
            "Rien n'était déclaré ; la détection remplit une case vide, elle n'en "
            "contredit aucune."
        )
    elif declaree == trouvee:
        accord, quarantaine, raison = "agree", False, "Détecté et déclaré concordent."
    else:
        accord, quarantaine, raison = "disagree", True, (
            f"Déclaré « {declaree} », détecté « {trouvee} ». Ce module ne choisit "
            "pas : un document bilingue, une déclaration erronée et un détecteur "
            "trompé se ressemblent, et seule une personne les distingue."
        )

    return {
        "declared": declaree or INCONNU,
        "detected": trouvee,
        "agreement": accord,
        "quarantine": quarantaine,
        "reason": raison,
        "reviewed": detected.get("reviewed", True),
    }


def detection_report(chemin: Optional[str] = None) -> Dict[str, Any]:
    """Décrit ce que la détection sait et ne sait pas, langue par langue."""
    registre = load_markers(chemin)
    return {
        "loaded": registre["loaded"],
        "file": MARQUEURS_PAR_DEFAUT,
        "detectable": sorted(registre["languages"]),
        "reviewed": sorted(
            code for code, entree in registre["languages"].items() if entree["reviewed"]
        ),
        "unreviewed": sorted(
            code for code, entree in registre["languages"].items()
            if not entree["reviewed"]
        ),
        "not_detectable": ["srr"],
        "method": "function-word markers",
        "minimum_words": MOTS_MINIMUM,
        "not_detected": [
            "le sérère : aucune liste de marqueurs n'existe, et en inventer une "
            "produirait un détecteur qui se trompe avec assurance",
            "un document bilingue : le score le plus haut gagne, et le second n'est "
            "pas rapporté comme une seconde langue",
            "une langue absente du fichier : elle rend `unknown`, jamais le voisin "
            "le plus proche",
        ],
        "note": (
            "Détecter n'est pas comprendre. Ce module ne ferme que la capacité "
            "`detection` de `languages.py` — la plus pauvre des neuf."
        ),
    }
