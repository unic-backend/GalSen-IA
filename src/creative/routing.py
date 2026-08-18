"""
Router par capacités, et refuser de classer sur des chiffres absents (C15, §36).

## Ce que C04 a laissé ouvert, et que cette phase ferme

`ProviderRegistry.select()` choisit **le premier éligible dans l'ordre
d'inscription**, et son commentaire dit pourquoi : *« un classement par coût ou
latence exigerait des chiffres mesurés ; aucun n'existe »*. C'était honnête et
insuffisant : l'ordre d'inscription est un ordre arbitraire, et servir le
premier venu est une décision déguisée en absence de décision.

Ce module ajoute les deux moitiés manquantes de §36 :

**L'appariement** — une demande porte maintenant ses exigences réelles
(résolution, durée, audio, conditionnement par référence, contrôle de caméra,
mémoire disponible, palier d'utilisateur), et chacune est confrontée à ce que le
fournisseur **déclare**. Chaque dimension rend un verdict séparé, jamais un
score agrégé : `MET`, `UNMET` ou `UNKNOWN`.

**Le classement, quand il est possible** — et le refus de classer quand il ne
l'est pas. C'est la règle centrale de ce module.

## `UNKNOWN` n'est pas `UNMET`, et cette distinction est tout

Un fournisseur qui **déclare ne pas** savoir contrôler la caméra est écarté. Un
fournisseur qui n'a **rien déclaré** ne l'est pas : on ne sait pas. Les fondre
ferait deux erreurs opposées selon le sens du pli — écarter ce qui marche, ou
retenir ce qui ne marche pas. Une exigence marquée `strict` transforme
`UNKNOWN` en refus ; c'est au demandeur de le décider, pas au routeur.

## Pourquoi il n'y a pas de score global

§36 énumère quatorze dimensions. Les additionner produirait un nombre qui a
l'air d'une mesure et n'en est pas : il faudrait des poids, et aucun poids n'est
mesurable ici. Pire, il rendrait comparables des dimensions qui ne le sont pas —
une licence inconnue ne se compense pas par une latence faible.

Le classement ne porte donc que sur **une** dimension à la fois, et seulement si
**tous** les candidats en portent une valeur mesurée. Sinon le résultat est
`UNRANKED` avec la liste de ceux qui ne l'ont pas déclarée. Aujourd'hui, sur les
fournisseurs du dossier de recherche, c'est le cas de tous : le routeur le dit
plutôt que d'inventer un ordre.

## Ce que ce module ne fait pas

Il ne code en dur aucune association tâche → modèle (§36 le nomme comme le
défaut à éviter), ne se replie sur aucun fournisseur voisin, et ne relit pas les
licences : `evaluate()` les applique déjà, et les redoubler ici créerait la
seconde vérité que §2 interdit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .providers import (
    AUCUN,
    CHOISI,
    DESACTIVE,
    CreativeProvider,
    CreativeRequest,
    ProviderRegistry,
    evaluate,
)

#: Le verdict d'une dimension. Trois valeurs, jamais deux : « il ne sait pas
#: faire » et « personne n'a regardé » ne se remplacent pas.
SATISFAIT = "MET"
NON_SATISFAIT = "UNMET"
INDETERMINE = "UNKNOWN"
VERDICTS = (SATISFAIT, NON_SATISFAIT, INDETERMINE)

#: Ce qu'un fournisseur déclare d'une capacité, dans `capability_status`.
DECLARE_OUI = "SUPPORTED"
DECLARE_PARTIEL = "PARTIAL"
DECLARE_NON = "UNSUPPORTED"
DECLARE_INCONNU = "UNKNOWN"

#: Les dimensions de §36 exprimées comme capacités déclarables. Elles sont des
#: **clés**, pas du code : un fournisseur qui en déclare une nouvelle n'oblige
#: à rien réécrire ici.
CAPACITES = (
    "audio_output",
    "lip_sync",
    "reference_conditioning",
    "camera_control",
    "multi_entity",
    "identity_consistency",
)

#: Les dimensions sur lesquelles un classement a un sens, quand les chiffres
#: existent. Le sens du tri est explicite : moins cher et plus rapide gagnent.
CLASSABLES = {"cost_per_second": "asc", "typical_latency_s": "asc",
              "min_vram_gb": "asc"}

#: L'état d'un classement impossible. Ce n'est pas un échec : c'est le résultat.
NON_CLASSE = "UNRANKED"


class RoutingRefused(ValueError):
    """Une demande de routage impossible à interpréter telle qu'elle est posée."""


@dataclass(frozen=True)
class RoutingNeed:
    """
    Ce que la demande exige, au-delà de la tâche.

    Attributes:
        capabilities: Les capacités attendues, parmi `CAPACITES`.
        strict: Les capacités pour lesquelles `UNKNOWN` vaut refus. Le
            demandeur décide de sa propre tolérance ; le routeur n'a pas à la
            deviner pour lui.
        resolution: La résolution voulue, en pixels de hauteur.
        duration_s: La durée voulue, en secondes.
        available_vram_gb: La mémoire réellement disponible. `None` veut dire
            « non mesurée » — et un besoin de VRAM confronté à une mesure
            absente est `UNKNOWN`, jamais `MET`.
        user_tier: Le palier du demandeur, quand la plateforme en a un.
    """

    capabilities: Tuple[str, ...] = ()
    strict: Tuple[str, ...] = ()
    resolution: Optional[int] = None
    duration_s: Optional[float] = None
    available_vram_gb: Optional[float] = None
    user_tier: str = ""

    def __post_init__(self) -> None:
        inconnues = sorted(set(self.capabilities) - set(CAPACITES))
        if inconnues:
            raise RoutingRefused(
                f"Capacités non déclarées : {inconnues}. Déclarées : "
                f"{list(CAPACITES)}. En router une qu'aucun fournisseur ne "
                "peut décrire ferait choisir au hasard."
            )
        hors_besoin = sorted(set(self.strict) - set(self.capabilities))
        if hors_besoin:
            raise RoutingRefused(
                f"Capacités marquées strictes sans être demandées : "
                f"{hors_besoin}."
            )
        if self.duration_s is not None and self.duration_s <= 0:
            raise RoutingRefused("Une durée nulle ou négative n'est pas une durée.")


@dataclass(frozen=True)
class DimensionVerdict:
    """
    Ce qu'une dimension a donné pour un fournisseur.

    Attributes:
        dimension: Ce qui a été confronté.
        verdict: `MET`, `UNMET` ou `UNKNOWN`.
        declared: Ce que le fournisseur en dit, tel quel.
        reason: Pourquoi, quand ce n'est pas `MET`.
    """

    dimension: str
    verdict: str
    declared: str = ""
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {"dimension": self.dimension, "verdict": self.verdict,
                "declared": self.declared or None, "reason": self.reason}


@dataclass(frozen=True)
class MatchResult:
    """
    L'appariement complet d'un fournisseur avec une demande.

    Attributes:
        provider_id: Le fournisseur.
        dimensions: Le verdict de chaque dimension, séparément.
        eligible: Vrai si aucune dimension n'est `UNMET`, et si aucune
            dimension stricte n'est `UNKNOWN`.
    """

    provider_id: str
    dimensions: Tuple[DimensionVerdict, ...] = field(default_factory=tuple)
    eligible: bool = False

    @property
    def unmet(self) -> List[str]:
        """Les dimensions refusées."""
        return [d.dimension for d in self.dimensions
                if d.verdict == NON_SATISFAIT]

    @property
    def unknown(self) -> List[str]:
        """Les dimensions que personne n'a renseignées."""
        return [d.dimension for d in self.dimensions if d.verdict == INDETERMINE]

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "provider_id": self.provider_id, "eligible": self.eligible,
            "dimensions": [d.as_dict() for d in self.dimensions],
            "unmet": self.unmet, "unknown": self.unknown,
        }


def _verdict_capacite(
    provider: CreativeProvider, capacite: str, strict: bool,
) -> DimensionVerdict:
    """Confronte une capacité demandée à ce que le fournisseur en déclare."""
    declare = provider.capability_status.get(capacite, DECLARE_INCONNU)
    if declare == DECLARE_OUI:
        return DimensionVerdict(capacite, SATISFAIT, declare)
    if declare == DECLARE_NON:
        return DimensionVerdict(
            capacite, NON_SATISFAIT, declare,
            "Le fournisseur déclare ne pas le faire.",
        )
    if declare == DECLARE_PARTIEL:
        return DimensionVerdict(
            capacite, INDETERMINE if not strict else NON_SATISFAIT, declare,
            "Déclaré partiel : ce qui marche et ce qui ne marche pas n'est pas "
            "décrit, donc la demande n'est pas tranchée.",
        )
    return DimensionVerdict(
        capacite, NON_SATISFAIT if strict else INDETERMINE, declare,
        "Rien n'est déclaré. Ce n'est pas un refus du fournisseur, c'est une "
        "absence d'information — les confondre écarterait ce qui marche.",
    )


def match(provider: CreativeProvider, need: RoutingNeed) -> MatchResult:
    """
    Confronte un fournisseur aux exigences d'une demande, dimension par dimension.

    Args:
        provider: Le fournisseur déclaré.
        need: Ce que la demande exige.

    Returns:
        Un verdict par dimension, et l'éligibilité qui en découle. Aucun score
        agrégé : additionner une licence inconnue et une latence faible
        produirait un nombre qui a l'air d'une mesure.
    """
    stricts = set(need.strict)
    verdicts = [
        _verdict_capacite(provider, capacite, capacite in stricts)
        for capacite in need.capabilities
    ]

    if need.available_vram_gb is not None and provider.min_vram_gb is not None:
        assez = provider.min_vram_gb <= need.available_vram_gb
        verdicts.append(DimensionVerdict(
            "vram",
            SATISFAIT if assez else NON_SATISFAIT,
            f"{provider.min_vram_gb} Gio requis",
            "" if assez else (
                f"{provider.min_vram_gb} Gio requis, "
                f"{need.available_vram_gb} Gio disponibles."
            ),
        ))
    elif need.available_vram_gb is not None or provider.min_vram_gb is not None:
        verdicts.append(DimensionVerdict(
            "vram", INDETERMINE,
            "" if provider.min_vram_gb is None else f"{provider.min_vram_gb} Gio",
            "Besoin ou disponibilité non mesuré : la comparaison n'a pas eu lieu.",
        ))

    eligible = all(verdict.verdict != NON_SATISFAIT for verdict in verdicts)
    return MatchResult(provider.provider_id, tuple(verdicts), eligible)


def rank(
    providers: List[CreativeProvider], by: str,
) -> Dict[str, Any]:
    """
    Classe des fournisseurs sur **une** dimension, ou refuse de classer.

    Args:
        providers: Les candidats.
        by: La dimension, parmi `CLASSABLES`.

    Returns:
        L'ordre, ou `UNRANKED` avec la liste de ceux qui n'ont pas déclaré de
        valeur. Le refus est le point : classer sur une dimension que la moitié
        des candidats ne renseigne pas revient à les ranger derrière les autres
        sans les avoir mesurés, et l'ordre obtenu se lit ensuite comme un
        résultat.

    Raises:
        RoutingRefused: Dimension non classable — la qualité, par exemple, n'a
            pas de mesure ici, et lui en inventer une est précisément ce que la
            directive interdit.
    """
    if by not in CLASSABLES:
        raise RoutingRefused(
            f"Dimension « {by} » non classable. Classables : "
            f"{sorted(CLASSABLES)}. Une dimension sans chiffre mesuré — la "
            "qualité, la cohérence d'identité — ne se classe pas : lui "
            "inventer une échelle en ferait une mesure."
        )
    if not providers:
        raise RoutingRefused("Aucun candidat à classer.")

    manquants = [p.provider_id for p in providers
                 if getattr(p, by, None) is None]
    if manquants:
        return {
            "status": NON_CLASSE,
            "dimension": by,
            "missing": manquants,
            "reason": (
                f"{len(manquants)} candidat(s) sur {len(providers)} ne "
                f"déclarent pas « {by} ». Les classer quand même les rangerait "
                "derrière les autres sans les avoir mesurés, et l'ordre se "
                "lirait ensuite comme un résultat."
            ),
        }

    ordonnes = sorted(providers, key=lambda p: getattr(p, by))
    return {
        "status": "RANKED",
        "dimension": by,
        "order": [p.provider_id for p in ordonnes],
        "values": {p.provider_id: getattr(p, by) for p in ordonnes},
    }


def route(
    registry: ProviderRegistry,
    request: CreativeRequest,
    need: Optional[RoutingNeed] = None,
    prefer: str = "",
) -> Dict[str, Any]:
    """
    Choisit un fournisseur en appariant les capacités, sans jamais coder en dur.

    Args:
        registry: Le registre des fournisseurs déclarés.
        request: La tâche et ses contraintes non techniques (licence, coût,
            invocation) — appliquées par `evaluate()`, pas redoublées ici.
        need: Les exigences de capacité. Aucune par défaut.
        prefer: La dimension de départage, parmi `CLASSABLES`. Vide, l'ordre
            d'inscription est conservé **et le retour le dit**.

    Returns:
        Le fournisseur retenu et la matrice complète, ou `NO_PROVIDER` avec ce
        qui a écarté chacun. Aucun repli sur un fournisseur voisin : servir
        autre chose que ce qui est demandé est une substitution silencieuse.

    Raises:
        RoutingRefused: Dimension de départage inconnue.
        ProviderRefused: Tâche non déclarée (levée par `CreativeRequest`).
    """
    exigences = need or RoutingNeed()
    if prefer and prefer not in CLASSABLES:
        raise RoutingRefused(
            f"Départage « {prefer} » non classable. Classables : "
            f"{sorted(CLASSABLES)}."
        )

    matrice: List[Dict[str, Any]] = []
    candidats: List[CreativeProvider] = []
    for fournisseur in registry.providers():
        if registry.state_of(fournisseur.provider_id) == DESACTIVE:
            matrice.append({"provider_id": fournisseur.provider_id,
                            "eligible": False,
                            "obstacles": ["désactivé par déclaration"]})
            continue

        verdict = evaluate(fournisseur, request)
        appariement = match(fournisseur, exigences)
        entree = {**verdict, **appariement.as_dict()}
        entree["eligible"] = bool(verdict["eligible"]) and appariement.eligible
        matrice.append(entree)
        if entree["eligible"]:
            candidats.append(fournisseur)

    if not candidats:
        return {
            "status": AUCUN,
            "task": request.task,
            "matrix": matrice,
            "reason": (
                "Aucun fournisseur déclaré ne satisfait à la fois les "
                "contraintes de la demande et les capacités exigées. Aucun "
                "repli n'est proposé : servir autre chose que ce qui est "
                "demandé est une substitution silencieuse, et le demandeur "
                "n'a aucun moyen de s'en apercevoir."
            ),
        }

    classement = rank(candidats, prefer) if prefer else {
        "status": NON_CLASSE,
        "dimension": None,
        "reason": (
            "Aucune dimension de départage demandée : l'ordre d'inscription "
            "est conservé, et ce n'est pas un classement."
        ),
    }
    if classement["status"] == "RANKED":
        retenu = classement["order"][0]
    else:
        retenu = candidats[0].provider_id

    return {
        "status": CHOISI,
        "provider_id": retenu,
        "task": request.task,
        "candidates": [p.provider_id for p in candidats],
        "ranking": classement,
        "matrix": matrice,
        "note": (
            "Aucune association tâche → modèle n'est codée en dur (§36) : le "
            "choix sort de l'appariement des capacités déclarées. Quand le "
            "classement est `UNRANKED`, le retenu est le premier candidat et "
            "cela se lit dans `ranking`, au lieu de passer pour un choix."
        ),
    }


def routing_report() -> Dict[str, Any]:
    """
    Ce que le routeur apparie, ce qu'il classe, et ce qu'il refuse de classer.

    Returns:
        Les dimensions et les règles, lisibles sans lire le code.
    """
    return {
        "capabilities": list(CAPACITES),
        "verdicts": list(VERDICTS),
        "rankable": sorted(CLASSABLES),
        "not_rankable": [
            "quality", "identity_consistency", "continuity",
            "reference_fidelity",
        ],
        "rules": [
            "`UNKNOWN` n'est pas `UNMET` : « il déclare ne pas savoir » et "
            "« personne n'a regardé » écartent des fournisseurs différents.",
            "Une exigence `strict` transforme `UNKNOWN` en refus — c'est la "
            "tolérance du demandeur, pas une règle du routeur.",
            "Aucun score global : additionner une licence inconnue et une "
            "latence faible produirait un nombre qui a l'air d'une mesure.",
            "Un classement n'a lieu que si **tous** les candidats portent la "
            "valeur ; sinon `UNRANKED`, avec ceux qui manquent.",
            "Aucune association tâche → modèle en dur, aucun repli sur le "
            "fournisseur le plus proche.",
        ],
        "why_quality_is_not_rankable": (
            "Aucune mesure de qualité, de cohérence d'identité ou de "
            "continuité n'existe sur cette machine (ADR-026, "
            "`docs/creative/feasibility.md`). Leur donner un rang inventerait "
            "l'échelle avant la mesure."
        ),
    }
