"""
Une observation linguistique et l'échelle qu'elle doit gravir (C14, §28–§33).

## La règle centrale, et pourquoi elle est structurelle

§28 : *ne jamais convertir « fréquemment observé » en « vérité officielle »
sans validation.* ADR-027 en fait un invariant plutôt qu'une consigne :

```
OBSERVED → CANDIDATE → CORROBORATED   ← la fréquence s'arrête ici
                     → VALIDATED      ← exige un humain nommé
                     → OFFICIAL       ← exige une autorité qui n'est pas nous
```

La fréquence fait monter jusqu'à `CORROBORATED` et **pas un cran de plus**. Ce
n'est pas de la prudence : une plateforme qui promeut par répétition encode dans
le registre d'une langue les erreurs de ses utilisateurs les plus bavards. Pour
une langue peu dotée, dont le corpus écrit est mince, cette plateforme
deviendrait vite l'une des rares références en ligne — et publierait des fautes
avec l'autorité d'un dictionnaire.

`promote_by_frequency()` ne peut donc pas produire `VALIDATED`. Ce n'est pas un
oubli à corriger : c'est le mécanisme.

## Ce que « valider » veut dire

`VALIDATED` exige un **humain nommé**. Pas « un utilisateur », pas « la
communauté », pas un score : quelqu'un dont le nom est écrit dans l'entrée et
qui reste attaché à elle. `OFFICIAL` exige en plus une autorité extérieure —
et la plateforme ne peut pas être cette autorité pour elle-même. Le refus
réutilise `IDENTITES_DE_PLATEFORME` de `src/creative/reference/consent.py`,
qui portait déjà exactement ce refus pour le consentement.

## Plusieurs hypothèses valent mieux qu'une fausse certitude

§32 : le contexte visuel est une **preuve**, pas une vérité. Un geste peut
soutenir une hypothèse sur un mot inconnu ; il ne la tranche pas. Deux
observations concurrentes sur la même expression coexistent donc, et rien ici ne
choisit entre elles.

## Ceci n'est pas de l'entraînement

§27, §31, §45 : accumuler des observations validées **n'est pas** entraîner un
modèle. Les deux actes restent séparés, et `src/creative/language/loop.py` le
dit explicitement plutôt que de le laisser supposer.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Dict, Optional, Tuple

from ..reference.consent import IDENTITES_DE_PLATEFORME
from ..reference.memory import PRIVEE
from .registry import LanguageRegistryError, is_declared

#: L'échelle de §28, du moins établi au plus établi.
OBSERVE = "OBSERVED"
CANDIDAT = "CANDIDATE"
CORROBORE = "CORROBORATED"
VALIDE = "VALIDATED"
OFFICIEL = "OFFICIAL"
INCONNU = "UNKNOWN"
ETATS = (OBSERVE, CANDIDAT, CORROBORE, VALIDE, OFFICIEL, INCONNU)

#: Les états que la seule répétition peut atteindre. La borne est ici, en une
#: ligne, et c'est tout l'ADR-027 point 6.
ETATS_PAR_FREQUENCE = (OBSERVE, CANDIDAT, CORROBORE)

#: Combien d'observations indépendantes font monter d'un cran. Déclarés, donc
#: discutables — un seuil caché se discute mal. Ils ne mènent nulle part
#: au-delà de `CORROBORATED`.
SEUIL_CANDIDAT = 2
SEUIL_CORROBORE = 4

#: La confidentialité d'une observation. Reprise de la mémoire de références :
#: deux vocabulaires pour une même frontière dériveraient.
PRIVE = PRIVEE
GLOBAL = "GLOBAL"
CONFIDENTIALITES = (PRIVE, GLOBAL)


class ObservationRefused(ValueError):
    """Une observation linguistique impossible à tenir telle qu'elle est posée."""


@dataclass(frozen=True)
class ObservationEvent:
    """
    Un événement de l'histoire d'une observation.

    Attributes:
        action: Ce qui a eu lieu.
        by: Qui l'a fait. Jamais vide.
        at: Quand, en temps epoch.
        detail: Ce qu'il faut pour relire l'événement plus tard.
    """

    action: str
    by: str
    at: float
    detail: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"action": self.action, "by": self.by, "at": self.at,
                "detail": self.detail}


@dataclass(frozen=True)
class LanguageObservation:
    """
    Ce que quelqu'un a observé d'une langue, avec d'où ça vient.

    Attributes:
        observation_id: Son identité.
        language: Le code de langue, déclaré au registre.
        expression: L'expression observée.
        meaning: Le sens proposé. `None` tant que personne n'en propose —
            et c'est un état normal, pas un trou à combler.
        dialect: La variété, quand elle est connue.
        region: Où elle a été entendue.
        context: Dans quelle situation. Un sens hors contexte se transporte mal.
        examples: Des emplois observés.
        pronunciation: Ce qui a été relevé, jamais une norme inventée.
        status: Où en est l'observation sur l'échelle.
        observed_count: Combien de fois observée indépendamment.
        validated_by: L'humain nommé qui a validé, quand il y en a un.
        authority: L'autorité extérieure, pour `OFFICIAL` seulement.
        privacy: `PRIVATE` par défaut. Le rester est une décision.
        source: D'où vient l'observation.
        history: Tout ce qui lui est arrivé, dans l'ordre.
    """

    observation_id: str
    language: str
    expression: str
    meaning: Optional[str] = None
    dialect: Optional[str] = None
    region: Optional[str] = None
    context: str = ""
    examples: Tuple[str, ...] = ()
    pronunciation: Optional[str] = None
    status: str = OBSERVE
    observed_count: int = 1
    validated_by: str = ""
    authority: str = ""
    privacy: str = PRIVE
    source: str = ""
    history: Tuple[ObservationEvent, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not str(self.expression or "").strip():
            raise ObservationRefused(
                "Observation sans expression : il n'y a rien à observer."
            )
        try:
            declaree = is_declared(self.language)
        except LanguageRegistryError as erreur:  # registre illisible
            raise ObservationRefused(str(erreur)) from erreur
        if not declaree:
            raise ObservationRefused(
                f"Langue « {self.language} » non déclarée au registre. Une "
                "observation rangée sous une langue que la plateforme ne "
                "nomme pas serait introuvable, et personne ne saurait de quelle "
                "langue elle parle."
            )
        if self.status not in ETATS:
            raise ObservationRefused(
                f"État « {self.status} » inconnu. Attendus : {list(ETATS)}."
            )
        if self.observed_count < 1:
            raise ObservationRefused(
                "Une observation existe au moins une fois."
            )
        if self.privacy not in CONFIDENTIALITES:
            raise ObservationRefused(
                f"Confidentialité « {self.privacy} » inconnue. Attendues : "
                f"{list(CONFIDENTIALITES)}."
            )
        if self.status == VALIDE and not self.validated_by.strip():
            raise ObservationRefused(
                "`VALIDATED` sans humain nommé. §28 : la validation est un "
                "acte de quelqu'un, pas un seuil franchi."
            )
        if self.status == OFFICIEL and not self.authority.strip():
            raise ObservationRefused(
                "`OFFICIAL` sans autorité nommée. L'officialité vient d'une "
                "institution, jamais de la plateforme qui la constate."
            )

    @property
    def frequency_ceiling_reached(self) -> bool:
        """Vrai quand la répétition ne peut plus rien apporter à cette entrée."""
        return self.status in ETATS_PAR_FREQUENCE and self.status == CORROBORE

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, y compris l'histoire."""
        return {
            "observation_id": self.observation_id, "language": self.language,
            "expression": self.expression, "meaning": self.meaning,
            "dialect": self.dialect, "region": self.region,
            "context": self.context, "examples": list(self.examples),
            "pronunciation": self.pronunciation, "status": self.status,
            "observed_count": self.observed_count,
            "validated_by": self.validated_by or None,
            "authority": self.authority or None,
            "privacy": self.privacy, "source": self.source,
            "history": [evenement.as_dict() for evenement in self.history],
        }


def new_observation(
    language: str, expression: str, by: str, **champs: Any,
) -> LanguageObservation:
    """
    Crée une observation à son premier échelon.

    Args:
        language: Le code de langue, déclaré au registre.
        expression: Ce qui a été observé.
        by: Qui l'a observé. Jamais vide — une observation sans observateur ne
            peut plus être recontactée ni pondérée.
        **champs: Les autres champs de `LanguageObservation`.

    Returns:
        L'observation, à l'état `OBSERVED` et `PRIVATE`.

    Raises:
        ObservationRefused: Observateur absent, ou champ invalide.
    """
    if not str(by or "").strip():
        raise ObservationRefused(
            "Observation sans observateur. Sans nom, elle ne peut être ni "
            "recontactée, ni pondérée, ni retirée si son auteur se rétracte."
        )
    champs.pop("status", None)
    return LanguageObservation(
        observation_id=champs.pop("observation_id", None) or str(uuid.uuid4()),
        language=language,
        expression=expression.strip(),
        status=OBSERVE,
        history=(ObservationEvent("observed", by, time.time(),
                                  champs.get("context", "")),),
        source=champs.pop("source", by),
        **champs,
    )


def corroborate(
    observation: LanguageObservation, by: str, detail: str = "",
) -> LanguageObservation:
    """
    Enregistre une observation indépendante de la même expression.

    Args:
        observation: L'entrée à renforcer.
        by: Qui l'observe cette fois.
        detail: Le contexte de cette observation-ci.

    Returns:
        L'entrée avec un compte de plus, et l'état que la fréquence permet —
        `CORROBORATED` au maximum. Une entrée déjà `VALIDATED` ou `OFFICIAL`
        n'est **pas** rétrogradée ; elle compte, sans changer d'état.

    Raises:
        ObservationRefused: Observateur absent.
    """
    if not str(by or "").strip():
        raise ObservationRefused("Corroboration sans observateur.")

    compte = observation.observed_count + 1
    if observation.status in ETATS_PAR_FREQUENCE:
        etat = promote_by_frequency(compte)
    else:
        etat = observation.status

    return replace(
        observation,
        observed_count=compte,
        status=etat,
        history=observation.history + (
            ObservationEvent("corroborated", by, time.time(), detail),
        ),
    )


def promote_by_frequency(count: int) -> str:
    """
    L'état que la seule répétition autorise.

    Args:
        count: Le nombre d'observations indépendantes.

    Returns:
        `OBSERVED`, `CANDIDATE` ou `CORROBORATED`. **Jamais au-delà**, quel que
        soit le compte : mille observations d'une erreur restent une erreur
        observée mille fois. C'est l'invariant d'ADR-027 point 6, et le fait
        qu'aucune valeur de `count` ne puisse produire `VALIDATED` est le
        mécanisme lui-même, pas une limite de cette fonction.
    """
    if count >= SEUIL_CORROBORE:
        return CORROBORE
    if count >= SEUIL_CANDIDAT:
        return CANDIDAT
    return OBSERVE


def validate(
    observation: LanguageObservation, by: str, meaning: Optional[str] = None,
) -> LanguageObservation:
    """
    Fait valider une observation par un humain nommé.

    Args:
        observation: L'entrée à valider.
        by: L'humain qui valide. Ni la plateforme, ni un agent.
        meaning: Le sens retenu, s'il précise ou corrige celui qui était noté.

    Returns:
        L'entrée à `VALIDATED`, portant le nom du valideur.

    Raises:
        ObservationRefused: Valideur absent, ou valideur qui est la plateforme.
            Une plateforme qui se valide elle-même transforme sa propre
            supposition en fait, ce qui est exactement le glissement que §28
            interdit.
    """
    nom = str(by or "").strip()
    if not nom:
        raise ObservationRefused(
            "Validation sans valideur. §28 exige un humain nommé : « validé » "
            "sans nom est un état que personne ne peut défendre."
        )
    if nom.lower() in IDENTITES_DE_PLATEFORME:
        raise ObservationRefused(
            f"« {nom} » est la plateforme. Elle ne valide pas ses propres "
            "observations : ce serait promouvoir une supposition en fait par "
            "le seul fait de l'avoir énoncée."
        )
    return replace(
        observation,
        status=VALIDE,
        validated_by=nom,
        meaning=meaning if meaning is not None else observation.meaning,
        history=observation.history + (
            ObservationEvent("validated", nom, time.time(), meaning or ""),
        ),
    )


def mark_official(
    observation: LanguageObservation, authority: str, reference: str,
) -> LanguageObservation:
    """
    Enregistre qu'une autorité extérieure a établi ce sens.

    Args:
        observation: L'entrée concernée.
        authority: L'institution. Jamais la plateforme.
        reference: Ce qu'on peut aller relire — décret, dictionnaire, norme.

    Returns:
        L'entrée à `OFFICIAL`, avec sa référence.

    Raises:
        ObservationRefused: Autorité absente, autorité qui est la plateforme,
            ou référence absente. Une officialité sans source à relire est
            invérifiable, donc indistinguable d'une affirmation.
    """
    nom = str(authority or "").strip()
    if not nom:
        raise ObservationRefused("`OFFICIAL` sans autorité nommée.")
    if nom.lower() in IDENTITES_DE_PLATEFORME:
        raise ObservationRefused(
            f"« {nom} » est la plateforme. L'officialité d'un sens vient d'une "
            "institution — le CLAD pour l'orthographe du wolof, par exemple —, "
            "jamais du système qui l'observe."
        )
    if not str(reference or "").strip():
        raise ObservationRefused(
            "`OFFICIAL` sans référence à relire : invérifiable, donc "
            "indistinguable d'une affirmation."
        )
    return replace(
        observation,
        status=OFFICIEL,
        authority=nom,
        history=observation.history + (
            ObservationEvent("made_official", nom, time.time(), reference),
        ),
    )


def ladder_report() -> Dict[str, Any]:
    """
    L'échelle, ses seuils et sa borne — lisible sans lire le code.

    Returns:
        Les états, ce que la fréquence atteint, et ce qu'elle n'atteindra
        jamais.
    """
    return {
        "states": list(ETATS),
        "reachable_by_frequency": list(ETATS_PAR_FREQUENCE),
        "thresholds": {"CANDIDATE": SEUIL_CANDIDAT,
                       "CORROBORATED": SEUIL_CORROBORE},
        "requires_named_human": [VALIDE],
        "requires_external_authority": [OFFICIEL],
        "rules": [
            "La fréquence monte jusqu'à `CORROBORATED` et s'arrête là : mille "
            "observations d'une erreur restent une erreur.",
            "`VALIDATED` exige un humain **nommé**, attaché à l'entrée.",
            "`OFFICIAL` exige une autorité qui n'est pas la plateforme, et une "
            "référence qu'on peut aller relire.",
            "`PRIVATE` est le défaut ; passer en `GLOBAL` demande un "
            "consentement enregistré (§58).",
            "Deux hypothèses concurrentes coexistent : §32 fait du contexte "
            "une preuve, pas un arbitre.",
        ],
    }
