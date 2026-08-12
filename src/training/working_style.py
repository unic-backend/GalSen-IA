"""
Apprendre le style de travail de quelqu'un (VOLET 34, ch. 12, phase 1).

Le VOLET 33 a construit la capture du signal, et l'état des lieux du chapitre 01
a mesuré ce qu'il en reste : *« feedback is captured, nothing turns it into
preferences »*. Le fichier grossit, la plateforme répond exactement comme au
premier jour.

Ce module fait le pas manquant : il **dérive** des préférences de ce qui a été
observé, et rien d'autre.

## Les trois règles qui tiennent ce module

1. **Une préférence est dérivée, jamais demandée ni supposée.** Chacune porte le
   nombre d'observations qui la soutiennent et les identifiants des retours dont
   elle vient. Une préférence sans preuve est une invention à laquelle la
   plateforme obéirait.

2. **En dessous de trois observations, rien n'est affirmé.** Une correction plus
   courte ne veut rien dire ; trois corrections plus courtes sur quatre en
   veulent quelque chose. Le seuil est bas parce que le signal est rare — mais
   il existe, et l'absence de préférence est rendue comme telle plutôt que
   comblée par une valeur par défaut qui aurait l'air d'un choix.

3. **Seul le signal consenti entre ici.** `feedback.py` pose la règle : sans
   consentement, un retour sert à corriger *cette* réponse **et rien d'autre**.
   Un profil durable est « autre chose ». Le consentement se demande, il ne se
   déduit pas du fait que quelqu'un a pris la peine d'écrire.

## Et par sujet, jamais globalement

Le style de quelqu'un n'est pas celui de son voisin (ADR-010). Fondre les
retours de tout le monde produirait un « style moyen » que personne n'a demandé,
et ferait fuir le style d'une personne vers les réponses d'une autre.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .feedback import Feedback, FeedbackKind, FeedbackStore, shared_feedback_store

logger = logging.getLogger(__name__)

#: Observations minimales avant qu'une préférence soit affirmée.
MINIMUM_OBSERVATIONS = 3

#: Part des observations qui doivent aller dans le même sens. À 0,6, deux
#: signaux sur trois suffisent ; en dessous, ce n'est pas une préférence, c'est
#: une hésitation, et la rendre comme une préférence serait un mensonge poli.
MAJORITE = 0.6

#: Écart de longueur en deçà duquel une correction ne dit rien sur la longueur.
#: Réécrire une phrase change le nombre de caractères sans être un avis.
ECART_LONGUEUR = 0.2

#: Marqueurs de langue. Ce n'est **pas** un détecteur de langue : c'est un compte
#: de mots courants, et il ne tranche que lorsque le signal est net.
MARQUEURS = {
    "fr": (" le ", " la ", " les ", " des ", " une ", " est ", " pour ", " avec ",
           " pas ", " que ", " qui ", " dans "),
    "en": (" the ", " and ", " is ", " for ", " with ", " that ", " this ",
           " you ", " are ", " not "),
}

#: Motifs de mise en forme cherchés dans une correction.
FORMATS = {
    "code_blocks": re.compile(r"```"),
    "bullet_lists": re.compile(r"^\s*[-*•]\s+", re.MULTILINE),
    "numbered_steps": re.compile(r"^\s*\d+[.)]\s+", re.MULTILINE),
}


@dataclass(frozen=True)
class Preference:
    """
    Une préférence observée, avec ce qui la soutient.

    Attributes:
        trait: Ce sur quoi porte la préférence (`length`, `format`, `language`…).
        value: La valeur observée (`shorter`, `code_blocks`, `fr`…).
        observations: Nombre de retours qui vont dans ce sens.
        considered: Nombre de retours examinés pour ce trait.
        evidence: Identifiants des retours — une préférence doit pouvoir être
            remontée jusqu'aux textes qui l'ont produite.
    """

    trait: str
    value: str
    observations: int
    considered: int
    evidence: Tuple[str, ...] = ()

    @property
    def ratio(self) -> float:
        """Part des observations allant dans ce sens."""
        return self.observations / self.considered if self.considered else 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la préférence, preuve comprise."""
        return {
            "trait": self.trait,
            "value": self.value,
            "observations": self.observations,
            "considered": self.considered,
            "ratio": round(self.ratio, 3),
            "evidence": list(self.evidence),
        }


@dataclass
class WorkingStyle:
    """
    Le style de travail d'un sujet, tel qu'il a été observé.

    Exemple:
        style = derive("awa")
        style.prompt_hints()   # « Réponses plus courtes. Blocs de code. »
    """

    subject: str
    preferences: List[Preference] = field(default_factory=list)
    feedback_considered: int = 0
    consented_only: bool = True

    @property
    def known(self) -> bool:
        """Vraie si au moins une préférence est soutenue par des observations."""
        return bool(self.preferences)

    def preference(self, trait: str) -> Optional[Preference]:
        """Retourne la préférence portant sur un trait, ou None."""
        for preference in self.preferences:
            if preference.trait == trait:
                return preference
        return None

    def prompt_hints(self) -> str:
        """
        Rend les préférences sous forme d'instructions pour un modèle.

        Vide quand rien n'est établi — et c'est le comportement voulu : une
        invite enrichie d'un style inventé produirait des réponses adaptées à
        une personne qui n'existe pas.
        """
        phrases = []
        for preference in self.preferences:
            phrase = _EN_PHRASE.get((preference.trait, preference.value))
            if phrase:
                phrases.append(phrase)
        if not phrases:
            return ""
        return "Préférences observées de la personne : " + " ".join(phrases)

    def to_dict(self) -> Dict[str, Any]:
        """Décrit le style, et ce sur quoi il repose."""
        return {
            "subject": self.subject,
            "known": self.known,
            "preferences": [preference.to_dict() for preference in self.preferences],
            "feedback_considered": self.feedback_considered,
            "consented_only": self.consented_only,
            "minimum_observations": MINIMUM_OBSERVATIONS,
            # Dit pourquoi le style est vide, plutôt que de laisser croire que
            # la personne n'a aucune préférence.
            "reason": None if self.known else _raison_du_vide(self.feedback_considered),
        }


#: Traduction d'une préférence en instruction. Écrite ici plutôt que produite
#: par concaténation : une consigne envoyée à un modèle est du texte que
#: quelqu'un doit avoir relu.
_EN_PHRASE = {
    ("length", "shorter"): "Répondre plus brièvement que par défaut.",
    ("length", "longer"): "Développer davantage que par défaut.",
    ("format", "code_blocks"): "Donner les exemples en blocs de code.",
    ("format", "bullet_lists"): "Structurer en listes à puces.",
    ("format", "numbered_steps"): "Structurer en étapes numérotées.",
    ("language", "fr"): "Répondre en français.",
    ("language", "en"): "Répondre en anglais.",
}


def _raison_du_vide(examines: int) -> str:
    """Explique pourquoi aucun style n'a pu être dérivé."""
    if examines == 0:
        return (
            "Aucun retour consenti pour ce sujet : sans consentement, un retour "
            "corrige la réponse concernée et rien d'autre."
        )
    return (
        f"{examines} retour(s) consenti(s) examiné(s), aucun trait n'atteint "
        f"{MINIMUM_OBSERVATIONS} observations concordantes."
    )


def derive(
    subject: str,
    store: Optional[FeedbackStore] = None,
    limit: int = 500,
) -> WorkingStyle:
    """
    Dérive le style de travail d'un sujet à partir de ses retours.

    Args:
        subject: Sujet propriétaire des retours (ADR-010).
        store: Magasin de retours ; le magasin partagé sinon.
        limit: Nombre maximal de retours examinés.

    Returns:
        Le style observé. **Vide plutôt qu'inventé** quand le signal manque.
    """
    magasin = store or shared_feedback_store()
    try:
        retours = magasin.list_feedback(subject=subject, consent_only=True, limit=limit)
    except Exception as erreur:  # noqa: BLE001 - un magasin en panne ne crée pas de style
        logger.warning("Style de travail indérivable pour « %s » : %s", subject, erreur)
        return WorkingStyle(subject=subject)

    preferences = []
    for deducteur in (_longueur, _format, _langue):
        preference = deducteur(retours)
        if preference is not None:
            preferences.append(preference)

    return WorkingStyle(
        subject=subject, preferences=preferences, feedback_considered=len(retours),
    )


# ----------------------------------------------------------------------
# Déductions
# ----------------------------------------------------------------------


def _corrections(retours: List[Feedback]) -> List[Feedback]:
    """Retient les retours qui portent une réécriture — le seul signal exploitable ici."""
    return [
        retour for retour in retours
        if retour.kind == FeedbackKind.CORRECTION and retour.correction and retour.response
    ]


def _longueur(retours: List[Feedback]) -> Optional[Preference]:
    """
    Déduit si la personne raccourcit ou allonge les réponses.

    Les réécritures de longueur voisine sont **écartées du décompte** : réécrire
    une phrase change le nombre de caractères sans exprimer un avis, et les
    compter diluerait le signal des deux côtés.
    """
    plus_court, plus_long = [], []
    for retour in _corrections(retours):
        origine, corrige = len(retour.response), len(retour.correction or "")
        if not origine:
            continue
        variation = (corrige - origine) / origine
        if variation <= -ECART_LONGUEUR:
            plus_court.append(retour.id)
        elif variation >= ECART_LONGUEUR:
            plus_long.append(retour.id)

    return _trancher("length", {"shorter": plus_court, "longer": plus_long})


def _format(retours: List[Feedback]) -> Optional[Preference]:
    """
    Déduit une mise en forme que la personne ajoute quand elle corrige.

    Le motif doit apparaître dans la correction **et pas dans la réponse** :
    sinon il était déjà là, et le compter mesurerait ce que la plateforme fait
    déjà plutôt que ce que la personne veut.
    """
    ajouts: Dict[str, List[str]] = {nom: [] for nom in FORMATS}
    for retour in _corrections(retours):
        for nom, motif in FORMATS.items():
            if motif.search(retour.correction or "") and not motif.search(retour.response):
                ajouts[nom].append(retour.id)
    return _trancher("format", ajouts)


def _langue(retours: List[Feedback]) -> Optional[Preference]:
    """
    Déduit la langue dans laquelle la personne écrit ses corrections.

    Ce n'est pas un détecteur de langue, et le module le dit : c'est un compte
    de mots courants qui ne tranche que lorsqu'un seul jeu de marqueurs
    apparaît. Un texte trop court, ou mêlant les deux, ne compte pour aucune.
    """
    par_langue: Dict[str, List[str]] = {code: [] for code in MARQUEURS}
    for retour in _corrections(retours):
        texte = f" {(retour.correction or '').lower()} "
        comptes = {
            code: sum(texte.count(marqueur) for marqueur in marqueurs)
            for code, marqueurs in MARQUEURS.items()
        }
        gagnante = max(comptes, key=comptes.get)
        autres = max(valeur for code, valeur in comptes.items() if code != gagnante)
        if comptes[gagnante] >= 2 and comptes[gagnante] > autres:
            par_langue[gagnante].append(retour.id)
    return _trancher("language", par_langue)


def _trancher(trait: str, candidats: Dict[str, List[str]]) -> Optional[Preference]:
    """
    Retient la valeur majoritaire d'un trait, si elle est assez soutenue.

    Args:
        trait: Trait examiné.
        candidats: Valeur possible → identifiants des retours qui la soutiennent.

    Returns:
        La préférence, ou None si le seuil ou la majorité ne sont pas atteints.
    """
    examines = sum(len(preuves) for preuves in candidats.values())
    if not examines:
        return None

    valeur, preuves = max(candidats.items(), key=lambda paire: len(paire[1]))
    if len(preuves) < MINIMUM_OBSERVATIONS:
        return None
    if len(preuves) / examines < MAJORITE:
        return None

    return Preference(
        trait=trait, value=valeur, observations=len(preuves),
        considered=examines, evidence=tuple(preuves),
    )
