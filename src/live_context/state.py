"""
Ce qui est observé pendant une session, et à quel point on en est sûr
(L05.1, ADR-033, §6 et §13 de la directive Live Context).

## La phrase du §6 qui gouverne ce module

*« Ne pas supposer que tous les champs sont toujours disponibles. Chaque
observation doit porter une confiance ou un statut appropriés. »*

C'est toute la conception. Il n'existe pas de valeur nue dans un état live :
chaque valeur est une `Observation` qui dit **d'où elle vient, comment elle a
été obtenue, et ce qu'on n'en sait pas**.

## `ABSENT` n'est pas `UNKNOWN`, et c'est la distinction qui coûte le plus cher

Quatre statuts, et deux d'entre eux se ressemblent assez pour être confondus par
quelqu'un de pressé :

- `MEASURED` — quelque chose a été mesuré.
- `DECLARED` — quelqu'un l'affirme ; ce n'est pas une mesure.
- `UNKNOWN` — **personne ne sait encore**. Attendre peut changer cela.
- `ABSENT` — **la chose n'existe pas ici**, et c'est mesuré. Attendre n'y
  changera rien.

Pas de micro sur cette machine, c'est `ABSENT` : `/dev/snd` a été cherché et
n'existe pas. Une langue non identifiée, c'est `UNKNOWN` : le fichier est là, la
mesure manque.

Les fondre ferait deux erreurs opposées selon le sens du pli — envoyer un
opérateur installer ce qui ne peut pas aider, ou masquer ce qu'une installation
réglerait.

## Une confiance sans base est refusée

`research/sources.py` a déjà imposé la règle et ce module la tient à l'identique :
un chiffre dont personne ne dit comment il a été obtenu se comporte comme une
mesure sans en être une. `confidence` et `confidence_basis` vont ensemble ou pas
du tout.

## Ce que l'état ne fait pas

**Il ne promeut rien.** Une observation ajoutée dix fois reste ce qu'elle est.
L'échelle qui plafonne à `CORROBORATED` vit dans
`creative/language/observation.py`, et cet état n'y touche pas.

**Il ne résout pas les désaccords.** Deux fournisseurs qui se contredisent sur
un locuteur produisent **deux observations et un conflit enregistré**, jamais
une moyenne. Une moyenne effacerait précisément l'information qui compte : que
quelque chose ne colle pas.

**Il n'est pas une mémoire.** Écrire en mémoire est une décision de permission
et de consentement, et elle appartient à un autre volet.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: Les statuts déclarés d'une observation.
MESURE = "MEASURED"
DECLARE = "DECLARED"
INCONNU = "UNKNOWN"
ABSENT = "ABSENT"
STATUTS = (MESURE, DECLARE, INCONNU, ABSENT)

#: Les statuts qui n'accompagnent **aucune** valeur. Une valeur avec l'un de ces
#: statuts serait une contradiction : on ne connaît pas une chose absente.
STATUTS_SANS_VALEUR = (INCONNU, ABSENT)

#: Les modalités d'où une observation peut venir. Une modalité inconnue est
#: refusée pour être **ajoutée ici** : elle décide de la façon dont
#: l'observation sera fusionnée et de la frontière de confiance qui s'applique.
MODALITES = ("audio", "screen", "video", "text", "event")


class ObservationRefused(ValueError):
    """Une observation impossible telle quelle."""


@dataclass(frozen=True)
class Observation:
    """
    Une chose observée pendant une session, avec ce qu'on en sait.

    Attributes:
        subject: Sur quoi porte l'observation — `speaker`, `language`,
            `transcript`, `screen_app`… Requis : une observation sans sujet ne
            se recoupe avec rien.
        value: Ce qui a été observé. **`None` obligatoire** quand le statut est
            `UNKNOWN` ou `ABSENT`.
        status: Un statut de `STATUTS`.
        modality: D'où cela vient, parmi `MODALITES`.
        confidence: `None` = **jamais établie**. Une valeur exige une base.
        confidence_basis: Comment la confiance a été obtenue. Vide seulement si
            `confidence` est `None`.
        provider: Qui l'a produite, quand c'est un fournisseur.
        provider_version: Sa version déclarée.
        at: L'instant de l'observation, en temps epoch.
        detail: Une précision libre — par exemple pourquoi c'est `ABSENT`.
    """

    subject: str
    status: str
    modality: str
    value: Any = None
    confidence: Optional[float] = None
    confidence_basis: str = ""
    provider: str = ""
    provider_version: str = "UNKNOWN"
    at: float = field(default_factory=time.time)
    detail: str = ""

    def __post_init__(self) -> None:
        if not str(self.subject).strip():
            raise ObservationRefused(
                "Une observation sans sujet ne se recoupe avec rien."
            )
        if self.status not in STATUTS:
            raise ObservationRefused(
                f"Statut « {self.status} » non déclaré. Déclarés : "
                f"{list(STATUTS)}."
            )
        if self.modality not in MODALITES:
            raise ObservationRefused(
                f"Modalité « {self.modality} » non déclarée. Déclarées : "
                f"{list(MODALITES)}."
            )
        if self.status in STATUTS_SANS_VALEUR and self.value is not None:
            raise ObservationRefused(
                f"Statut « {self.status} » avec une valeur : on ne connaît pas "
                "une chose qu'on déclare inconnue ou absente."
            )
        if self.status == MESURE and self.value is None:
            raise ObservationRefused(
                "Une observation `MEASURED` sans valeur ne mesure rien. "
                f"Utiliser `{INCONNU}` ou `{ABSENT}` selon ce qui est vrai."
            )
        if self.confidence is not None:
            if not 0.0 <= float(self.confidence) <= 1.0:
                raise ObservationRefused(
                    f"Confiance {self.confidence} hors de [0, 1]."
                )
            if not self.confidence_basis.strip():
                raise ObservationRefused(
                    f"Confiance {self.confidence} sans base. Un chiffre dont "
                    "personne ne dit comment il a été obtenu se comporte comme "
                    "une mesure sans en être une."
                )
        elif self.confidence_basis.strip():
            raise ObservationRefused(
                "Une base de confiance sans confiance ne dit rien : soit les "
                "deux, soit aucune."
            )

    @property
    def is_known(self) -> bool:
        """Vrai quand l'observation porte quelque chose de connu."""
        return self.status in (MESURE, DECLARE)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "subject": self.subject, "status": self.status,
            "modality": self.modality, "value": self.value,
            "confidence": self.confidence,
            "confidence_basis": self.confidence_basis,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "at": self.at, "detail": self.detail,
        }


def absent(subject: str, modality: str, detail: str,
           provider: str = "") -> Observation:
    """
    Construit une observation `ABSENT` — la chose n'existe pas ici, et on l'a vu.

    Args:
        subject: Sur quoi porte l'absence.
        modality: La modalité concernée.
        detail: **Comment l'absence a été constatée.** Requis : « absent » sans
            constat est une supposition.
        provider: Le fournisseur concerné, s'il y en a un.

    Returns:
        L'observation.

    Raises:
        ObservationRefused: Si le constat n'est pas donné.
    """
    if not str(detail).strip():
        raise ObservationRefused(
            "Une absence sans constat est une supposition. Dire *comment* elle "
            "a été établie — un chemin cherché, une variable vide, une sonde."
        )
    return Observation(subject=subject, status=ABSENT, modality=modality,
                       detail=detail, provider=provider)


def unknown(subject: str, modality: str, detail: str = "",
            provider: str = "") -> Observation:
    """
    Construit une observation `UNKNOWN` — personne ne sait encore.

    Args:
        subject: Sur quoi porte l'inconnue.
        modality: La modalité concernée.
        detail: Ce qui manque pour savoir, quand c'est nommable.
        provider: Le fournisseur concerné.

    Returns:
        L'observation.
    """
    return Observation(subject=subject, status=INCONNU, modality=modality,
                       detail=detail, provider=provider)


@dataclass(frozen=True)
class LiveContextState:
    """
    L'état d'une session — en ajout seul, et qui ne conclut rien.

    Attributes:
        session_id: L'identifiant de session.
        observations: Ce qui a été observé, dans l'ordre d'arrivée.
        started_at: Le début de la session, en temps epoch.
    """

    session_id: str
    observations: Tuple[Observation, ...] = ()
    started_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if not str(self.session_id).strip():
            raise ObservationRefused(
                "Un état sans session ne se rattache à rien."
            )

    def add(self, *observations: Observation) -> "LiveContextState":
        """
        Ajoute des observations et rend un **nouvel** état.

        Args:
            *observations: Ce qui vient d'être observé.

        Returns:
            Un nouvel état. L'ancien n'est pas modifié : un état live doit
            pouvoir être comparé à ce qu'il était il y a une minute, et un
            objet muté ne le permet pas.
        """
        return LiveContextState(
            session_id=self.session_id,
            observations=self.observations + tuple(observations),
            started_at=self.started_at,
        )

    def subjects(self) -> List[str]:
        """Les sujets observés, triés."""
        return sorted({o.subject for o in self.observations})

    def by_subject(self, subject: str) -> List[Observation]:
        """
        Toutes les observations d'un sujet, dans l'ordre d'arrivée.

        Args:
            subject: Le sujet cherché.

        Returns:
            La liste — **entière**. Rendre seulement la dernière ferait
            disparaître le désaccord au moment où il apparaît.
        """
        return [o for o in self.observations if o.subject == subject]

    def latest(self, subject: str) -> Optional[Observation]:
        """
        La dernière observation d'un sujet, ou `None`.

        Args:
            subject: Le sujet cherché.

        Returns:
            La plus récente par `at`, ou `None` si le sujet n'a rien.

        Note:
            « La plus récente » n'est pas « la bonne ». Quand un sujet porte un
            conflit, `conflicts()` le dit, et l'appelant décide.
        """
        connues = self.by_subject(subject)
        return max(connues, key=lambda o: o.at) if connues else None

    def conflicts(self) -> List[Dict[str, Any]]:
        """
        Les sujets sur lesquels deux observations connues se contredisent.

        Returns:
            Un conflit par sujet, avec les valeurs distinctes et les
            fournisseurs qui les portent.

        Note:
            **Aucune moyenne, aucun arbitrage.** Une moyenne effacerait
            exactement l'information qui compte : que quelque chose ne colle
            pas. Le conflit est rendu pour qu'un humain ou un volet ultérieur en
            décide.
        """
        trouves: List[Dict[str, Any]] = []
        for sujet in self.subjects():
            connues = [o for o in self.by_subject(sujet) if o.is_known]
            valeurs = {repr(o.value) for o in connues}
            if len(valeurs) > 1:
                trouves.append({
                    "subject": sujet,
                    "values": sorted(valeurs),
                    "providers": sorted({o.provider for o in connues if o.provider}),
                    "observations": len(connues),
                    "resolved": False,
                    "note": ("Aucun arbitrage : une moyenne effacerait le fait "
                             "que quelque chose ne colle pas."),
                })
        return trouves

    def counts(self) -> Dict[str, int]:
        """Le nombre d'observations par statut."""
        return {statut: sum(1 for o in self.observations if o.status == statut)
                for statut in STATUTS}

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable de l'état."""
        return {
            "session_id": self.session_id,
            "started_at": self.started_at,
            "observations": [o.as_dict() for o in self.observations],
            "subjects": self.subjects(),
            "counts": self.counts(),
            "conflicts": self.conflicts(),
            "promoted": False,
        }


def state_report() -> Dict[str, Any]:
    """
    Ce que l'état garantit, et ce qu'il refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "statuses": list(STATUTS),
        "statuses_without_value": list(STATUTS_SANS_VALEUR),
        "modalities": list(MODALITES),
        "rules": [
            "ABSENT n'est pas UNKNOWN : l'un est mesuré et ne changera pas, "
            "l'autre attend une mesure.",
            "Une absence sans constat est refusée : dire comment elle a été "
            "établie.",
            "Une confiance sans base est refusée, et l'inverse aussi.",
            "MEASURED sans valeur est refusé ; UNKNOWN ou ABSENT avec valeur "
            "aussi.",
            "L'état est en ajout seul : `add()` rend un nouvel état.",
            "Aucune promotion : une observation répétée reste ce qu'elle est.",
            "Aucun arbitrage : un désaccord est rendu comme conflit, jamais "
            "moyenné.",
        ],
    }
