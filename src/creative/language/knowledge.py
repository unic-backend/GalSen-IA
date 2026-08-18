"""
La base de connaissance linguistique, et sa frontière (C14, §30, §32, §58).

## Deux espaces, une frontière, aucun passage automatique

§58 : *les conversations privées restent séparées de la connaissance
linguistique globale.* Ici, cela veut dire deux espaces dans un même magasin,
et **un seul passage** entre eux — `publish()`, qui exige un consentement
enregistré et nommé.

Il n'y a pas de chemin inverse automatique, pas de promotion « parce que
l'observation est bonne », pas de tâche de fond qui ferait remonter le privé
vers le global. Une plateforme qui apprend d'une conversation privée sans que
personne l'ait décidé est exactement ce que §58 interdit, et c'est le genre de
glissement qui s'écrit en trois lignes distraites.

## Deux sens concurrents ne sont pas un conflit à résoudre

§32 : le contexte est une **preuve**, pas un arbitre. Deux personnes peuvent
observer la même expression avec deux sens différents, et les deux peuvent avoir
raison — selon la région, la génération, la situation. `hypotheses()` les rend
toutes ; rien ici ne choisit, ne moyenne, ni ne classe par fréquence.

Choisir serait la tentation utile : un appelant préférerait une réponse unique.
C'est précisément pour ça que la fonction n'existe pas.

## Pourquoi le consentement n'est pas `ConsentScope`

`src/creative/reference/consent.py` porte le consentement d'une **personne sur
son image et sa voix** : usage, portée, conservation, révocation. Une observation
linguistique n'est pas cela — c'est un énoncé sur une langue, pas un média
d'une personne. Plier l'un dans l'autre aurait donné un objet aux deux tiers
vides. Ce qui est repris, en revanche, c'est le refus qui compte :
`IDENTITES_DE_PLATEFORME`, parce que la plateforme ne consent pour personne.

## L'histoire ne se réécrit pas

Chaque entrée porte ce qui lui est arrivé, dans l'ordre, et les événements ne
sont qu'ajoutés. Une base dont on peut effacer le passé ne peut pas être
auditée, et ADR-027 promet qu'elle peut l'être.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any, Dict, List, Optional

from ..reference.consent import IDENTITES_DE_PLATEFORME
from .observation import (
    GLOBAL,
    PRIVE,
    LanguageObservation,
    ObservationEvent,
    ObservationRefused,
    corroborate,
)


class KnowledgeRefused(ValueError):
    """Une opération refusée par la base de connaissance, avec sa raison."""


class LanguageKnowledgeBase:
    """
    Ce que la plateforme sait des langues, et de qui elle le tient.

    Le magasin est en mémoire. C'est un choix assumé et borné : §72 refuse
    d'ajouter une couche de persistance avant qu'un usage la demande, et
    `src/storage/` fournira le magasin SQLite le jour où elle sera demandée,
    sans changer cette interface. Ce qui compte ici est la **frontière**, et
    elle ne dépend pas du support.
    """

    def __init__(self) -> None:
        """Ouvre une base vide."""
        self._entrees: Dict[str, LanguageObservation] = {}

    # -- écriture ---------------------------------------------------------

    def add(self, observation: LanguageObservation) -> LanguageObservation:
        """
        Ajoute une observation, ou renforce celle qui dit déjà la même chose.

        Args:
            observation: L'observation à ranger.

        Returns:
            L'entrée telle qu'elle est après l'ajout. Une observation identique
            en langue, expression **et sens**, faite par quelqu'un d'autre,
            corrobore l'entrée existante au lieu d'en créer une deuxième. Un
            sens différent crée une entrée distincte : c'est une hypothèse
            concurrente (§32), pas un doublon.

        Raises:
            KnowledgeRefused: Identifiant déjà présent avec un autre contenu.
        """
        existante = self._entrees.get(observation.observation_id)
        if existante is not None and existante != observation:
            raise KnowledgeRefused(
                f"L'observation « {observation.observation_id} » existe déjà "
                "avec un autre contenu. Écraser une entrée effacerait son "
                "histoire, et la base ne serait plus auditable."
            )

        jumelle = self._meme_sens(observation)
        if jumelle is not None:
            auteur = observation.source or "inconnu"
            renforcee = corroborate(jumelle, by=auteur,
                                    detail=observation.context)
            self._entrees[renforcee.observation_id] = renforcee
            return renforcee

        self._entrees[observation.observation_id] = observation
        return observation

    def _meme_sens(
        self, observation: LanguageObservation,
    ) -> Optional[LanguageObservation]:
        """L'entrée qui dit déjà la même chose, si elle existe."""
        for entree in self._entrees.values():
            if (entree.language == observation.language
                    and entree.expression == observation.expression
                    and entree.meaning == observation.meaning
                    and entree.privacy == observation.privacy
                    and entree.observation_id != observation.observation_id):
                return entree
        return None

    def publish(
        self, observation_id: str, by: str, consent: str,
    ) -> LanguageObservation:
        """
        Fait passer une observation de l'espace privé à l'espace global.

        Args:
            observation_id: L'observation concernée.
            by: La personne qui consent. Ni la plateforme, ni un agent.
            consent: Ce qui a été consenti, en toutes lettres. C'est la trace
                qu'un audit relira ; « true » n'en est pas une.

        Returns:
            L'entrée, désormais `GLOBAL`, avec le consentement dans son
            histoire.

        Raises:
            KnowledgeRefused: Observation inconnue, consentant absent,
                consentant qui est la plateforme, ou consentement vide. Chacun
                de ces refus empêche le même geste : faire entrer dans la
                connaissance globale ce que personne n'a accepté d'y mettre.
        """
        entree = self._entrees.get(observation_id)
        if entree is None:
            raise KnowledgeRefused(
                f"Observation « {observation_id} » inconnue."
            )
        nom = str(by or "").strip()
        if not nom:
            raise KnowledgeRefused(
                "Publication sans consentant. §58 : le passage du privé au "
                "global est une décision de quelqu'un, et ce quelqu'un se nomme."
            )
        if nom.lower() in IDENTITES_DE_PLATEFORME:
            raise KnowledgeRefused(
                f"« {nom} » est la plateforme. Elle ne consent pour personne, "
                "et surtout pas à publier ce qu'elle a entendu."
            )
        if not str(consent or "").strip():
            raise KnowledgeRefused(
                "Publication sans consentement écrit. Un audit doit pouvoir "
                "relire ce qui a été accepté ; un booléen ne se relit pas."
            )
        if entree.privacy == GLOBAL:
            return entree

        publiee = replace(
            entree,
            privacy=GLOBAL,
            history=entree.history + (
                ObservationEvent("published", nom, time.time(), consent),
            ),
        )
        self._entrees[observation_id] = publiee
        return publiee

    # -- lecture ----------------------------------------------------------

    def get(self, observation_id: str) -> Optional[LanguageObservation]:
        """L'entrée demandée, ou `None`."""
        return self._entrees.get(observation_id)

    def hypotheses(
        self, language: str, expression: str, include_private: bool = False,
    ) -> List[LanguageObservation]:
        """
        Tous les sens observés pour une expression.

        Args:
            language: La langue.
            expression: L'expression cherchée.
            include_private: Inclure l'espace privé. **Faux par défaut** : une
                lecture qui remonterait le privé sans le demander est la fuite
                que §58 interdit, et un défaut permissif finit toujours par
                être utilisé sans y penser.

        Returns:
            Les hypothèses, de la mieux établie à la moins établie, **sans
            qu'aucune ne soit désignée**. §32 fait du contexte une preuve, pas
            un arbitre : deux sens concurrents peuvent être justes tous les
            deux selon la région ou la situation.
        """
        rang = {"OFFICIAL": 0, "VALIDATED": 1, "CORROBORATED": 2,
                "CANDIDATE": 3, "OBSERVED": 4, "UNKNOWN": 5}
        trouvees = [
            entree for entree in self._entrees.values()
            if entree.language == language
            and entree.expression == expression
            and (include_private or entree.privacy == GLOBAL)
        ]
        return sorted(
            trouvees,
            key=lambda e: (rang.get(e.status, 9), -e.observed_count),
        )

    def for_language(
        self, language: str, include_private: bool = False,
    ) -> List[LanguageObservation]:
        """Toutes les entrées d'une langue, l'espace privé exclu par défaut."""
        return sorted(
            (entree for entree in self._entrees.values()
             if entree.language == language
             and (include_private or entree.privacy == GLOBAL)),
            key=lambda e: e.expression,
        )

    def entries(self) -> List[LanguageObservation]:
        """
        Toutes les entrées, les deux espaces confondus.

        Réservé aux usages qui doivent voir la base entière — un rapport, un
        audit, la file de validation. Ce n'est **pas** la lecture ordinaire :
        `hypotheses()` et `for_language()` excluent le privé par défaut, et
        c'est par elles qu'on interroge la connaissance.
        """
        return list(self._entrees.values())

    def private_entries(self) -> List[LanguageObservation]:
        """Ce qui n'a pas été publié. Nommer l'espace privé le rend auditable."""
        return [entree for entree in self._entrees.values()
                if entree.privacy == PRIVE]

    def report(self) -> Dict[str, Any]:
        """
        L'état de la base, et la frontière qu'elle tient.

        Returns:
            Les comptes par espace et par état, les langues couvertes, et les
            expressions portant plusieurs hypothèses — celles-là sont
            intéressantes, pas défectueuses.
        """
        entrees = list(self._entrees.values())
        par_etat: Dict[str, int] = {}
        for entree in entrees:
            par_etat[entree.status] = par_etat.get(entree.status, 0) + 1

        concurrentes: Dict[str, int] = {}
        for entree in entrees:
            cle = f"{entree.language}:{entree.expression}"
            concurrentes[cle] = concurrentes.get(cle, 0) + 1

        return {
            "total": len(entrees),
            "private": len([e for e in entrees if e.privacy == PRIVE]),
            "global": len([e for e in entrees if e.privacy == GLOBAL]),
            "by_status": par_etat,
            "languages": sorted({e.language for e in entrees}),
            "competing_hypotheses": sorted(
                cle for cle, compte in concurrentes.items() if compte > 1
            ),
            "note": (
                "Le passage du privé au global se fait par `publish()` et par "
                "rien d'autre : consentant nommé, consentement écrit, trace "
                "dans l'histoire. Plusieurs hypothèses sur une même expression "
                "sont un état normal (§32), pas un conflit à trancher."
            ),
        }


def merge_correction(
    base: LanguageKnowledgeBase,
    observation_id: str,
    by: str,
    meaning: str,
    context: str = "",
) -> LanguageObservation:
    """
    Enregistre la correction d'un utilisateur — comme observation, pas comme fait.

    Args:
        base: La base concernée.
        observation_id: L'entrée corrigée.
        by: Qui corrige.
        meaning: Le sens qu'il propose.
        context: Où sa correction s'applique.

    Returns:
        Une **nouvelle** entrée portant le sens corrigé, à l'état `OBSERVED` et
        `PRIVATE`, liée à l'originale par son histoire. L'entrée d'origine
        n'est ni modifiée ni supprimée.

        C'est ADR-027 point 7 : *une correction d'utilisateur est une
        observation, pas un fait global.* Écraser l'ancien sens ferait de la
        dernière personne à parler l'autorité sur la langue.

    Raises:
        KnowledgeRefused: Entrée inconnue.
        ObservationRefused: Correcteur absent.
    """
    entree = base.get(observation_id)
    if entree is None:
        raise KnowledgeRefused(f"Observation « {observation_id} » inconnue.")
    nom = str(by or "").strip()
    if not nom:
        raise ObservationRefused("Correction sans auteur.")

    from .observation import new_observation  # import local : évite un cycle

    correction = new_observation(
        language=entree.language,
        expression=entree.expression,
        by=nom,
        meaning=meaning,
        dialect=entree.dialect,
        region=entree.region,
        context=context or entree.context,
    )
    correction = replace(
        correction,
        history=correction.history + (
            ObservationEvent(
                "corrects", nom, time.time(),
                f"corrige « {observation_id} » : « {entree.meaning} » → "
                f"« {meaning} »",
            ),
        ),
    )
    return base.add(correction)
