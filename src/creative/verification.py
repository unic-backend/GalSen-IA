"""
Verification that says what it could not check.

Directive §48 asks for identity verification and then forbids the thing that
would make it easy: *do NOT invent scientific meaning for a score.* ADR-026
turns that into structure, and the structure is the whole module — a composite
identity score has **no field here**, deliberately, because a field that exists
gets filled.

Measured on this machine: no face detection at all
(`HaarCascadeFaceDetector.is_available()` is `False`, headless OpenCV ships no
cascade files). So every visual dimension reports `NOT_MEASURABLE` and every
verdict is `INCOMPLETE`. That output looks empty. It should: the alternative is
a number computed from colour histograms, presented beside someone's likeness,
that means nothing and will be believed.

The same three outcomes carry continuity (§50). "Could not check" and "checked
and fine" must be impossible to confuse — the rule `src/media/qc/checks.py`
already holds with `PASS` / `FAIL` / `NOT_CHECKED`, restated here because the
subject is different and the confusion is the same.

Drift (§49) inherits it too. Shot 2 deviating from shot 1 is measurable only if
the dimension was measurable in both; drift on an unmeasured dimension is
`UNKNOWN`, never `0.0`. Zero is a finding — it says "no deviation" — and it is
the finding a broken pipeline produces most often.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Ce qu'une dimension peut rendre. Trois issues, jamais deux : « pas pu
#: vérifier » et « vérifié, conforme » doivent rester impossibles à confondre.
MESUREE = "MEASURED"
NON_MESURABLE = "NOT_MEASURABLE"
ECHOUEE = "FAILED"
ISSUES = (MESUREE, NON_MESURABLE, ECHOUEE)

#: Le verdict d'ensemble. `VERIFIED` exige que **tout** l'applicable ait été
#: mesuré : une seule dimension non mesurable rend `INCOMPLETE`, jamais
#: « conforme avec réserves ».
VERIFIE = "VERIFIED"
INCOMPLET = "INCOMPLETE"
EN_ECHEC = "FAILED"

#: Les dimensions d'identité déclarées (§48). Aucune n'est agrégée : une note
#: unique cacherait la dimension qui compte derrière la moyenne de celles qui
#: ne comptent pas — la raison pour laquelle `src/security/posture.py` refuse
#: déjà une note globale.
DIMENSIONS_D_IDENTITE = (
    "facial_similarity", "appearance_similarity", "proportion_consistency",
    "clothing_consistency", "distinctive_features", "colour_consistency",
    "motion_characteristics",
)

#: Les dimensions de continuité déclarées (§50).
DIMENSIONS_DE_CONTINUITE = (
    "identity", "appearance", "clothing", "objects", "environment",
    "lighting", "weather", "time_of_day", "spatial_relations",
    "screen_direction", "dialogue", "audio_timing", "voice", "camera",
    "references",
)

#: La gravité d'un écart constaté. Déclarée pour que « à corriger » et « à
#: refaire » ne se décident pas au jugé.
MINEURE = "MINOR"
MAJEURE = "MAJOR"
BLOQUANTE = "BLOCKING"
GRAVITES = (MINEURE, MAJEURE, BLOQUANTE)

#: Les étapes de la boucle qualité (§51).
BOUCLE = ("PLAN", "GENERATE", "ANALYZE", "VERIFY", "CORRECT", "REGENERATE",
          "FINALIZE")


class VerificationRefused(ValueError):
    """Une vérification impossible à déclarer telle quelle."""


@dataclass(frozen=True)
class DimensionResult:
    """
    Ce qu'une dimension a donné — ou pourquoi elle n'a rien pu donner.

    Attributes:
        dimension: La dimension examinée.
        outcome: `MEASURED`, `NOT_MEASURABLE` ou `FAILED`.
        value: La valeur, **seulement** pour `MEASURED`.
        method: Ce qui a été comparé et comment. **Obligatoire** pour
            `MEASURED` : un nombre dont la dérivation n'est pas consignée est
            exactement la fabrication que §48 interdit.
        scale: Ce que le nombre veut dire.
        missing_capability: Ce qui manque, **obligatoire** pour
            `NOT_MEASURABLE`.
        confidence: De 0 à 1, quand elle a un sens.
        severity: La gravité, pour un écart constaté.
    """

    dimension: str
    outcome: str
    value: Optional[float] = None
    method: str = ""
    scale: str = ""
    missing_capability: str = ""
    confidence: Optional[float] = None
    severity: str = ""

    def __post_init__(self) -> None:
        if self.outcome not in ISSUES:
            raise VerificationRefused(
                f"Issue « {self.outcome} » non déclarée. Déclarées : "
                f"{list(ISSUES)}."
            )
        if self.outcome == MESUREE:
            if not str(self.method or "").strip():
                raise VerificationRefused(
                    f"« {self.dimension} » est déclarée MEASURED sans méthode. "
                    "Un nombre dont personne ne sait comment il a été obtenu "
                    "est une invention habillée en mesure (§48)."
                )
            if not str(self.scale or "").strip():
                raise VerificationRefused(
                    f"« {self.dimension} » est mesurée sans échelle : personne "
                    "ne peut dire ce que le nombre signifie."
                )
        if self.outcome == NON_MESURABLE:
            if self.value is not None:
                raise VerificationRefused(
                    f"« {self.dimension} » porte une valeur et se dit non "
                    "mesurable. L'un des deux est faux."
                )
            if not str(self.missing_capability or "").strip():
                raise VerificationRefused(
                    f"« {self.dimension} » est non mesurable sans nommer la "
                    "capacité manquante. Le rapport doit servir de liste "
                    "d'installation, pas de haussement d'épaules."
                )
        if self.severity and self.severity not in GRAVITES:
            raise VerificationRefused(
                f"Gravité « {self.severity} » non déclarée. Déclarées : "
                f"{list(GRAVITES)}."
            )
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise VerificationRefused(
                f"Confiance {self.confidence} hors de [0, 1]."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "dimension": self.dimension, "outcome": self.outcome,
            "value": self.value, "method": self.method, "scale": self.scale,
            "missing_capability": self.missing_capability,
            "confidence": self.confidence, "severity": self.severity,
        }


def not_measurable(dimension: str, capability: str,
                   reason: str = "") -> DimensionResult:
    """
    Déclare une dimension non mesurable, en nommant ce qui manque.

    Args:
        dimension: La dimension.
        capability: La capacité qui la rendrait mesurable.
        reason: Le détail, quand il aide.
    """
    return DimensionResult(
        dimension=dimension, outcome=NON_MESURABLE,
        missing_capability=capability,
        method=reason,
    )


def identity_dimensions_here() -> List[DimensionResult]:
    """
    L'état réel des dimensions d'identité sur cette machine.

    Returns:
        Sept dimensions, toutes `NOT_MEASURABLE`, chacune nommant la capacité
        absente. C'est la sortie honnête ici : aucune détection de visage n'est
        disponible, donc rien de facial n'est calculable, et rien qui en dérive
        non plus.
    """
    from ..vision_intelligence_engine.face_detector import HaarCascadeFaceDetector

    visage_disponible = HaarCascadeFaceDetector().is_available()
    manquantes = {
        "facial_similarity": (
            "face_detection",
            "Aucune cascade de détection de visages (OpenCV sans interface "
            "n'en livre plus)." if not visage_disponible else "",
        ),
        "appearance_similarity": (
            "appearance_embedding",
            "Aucun modèle d'apparence : un écart de couleurs n'est pas une "
            "similarité d'apparence.",
        ),
        "proportion_consistency": (
            "pose_estimation",
            "Aucun estimateur de pose : les proportions ne sont pas mesurées.",
        ),
        "clothing_consistency": (
            "segmentation",
            "Aucune segmentation de vêtement.",
        ),
        "distinctive_features": (
            "face_detection",
            "Dépend de la détection de traits, indisponible.",
        ),
        "colour_consistency": (
            "video_decode",
            "Le décodage vidéo est dégradé : aucune trame de rendu n'est "
            "comparable ici.",
        ),
        "motion_characteristics": (
            "video_decode",
            "Aucun mouvement n'est observable sans décodage.",
        ),
    }
    return [not_measurable(dimension, capacite, raison)
            for dimension, (capacite, raison) in manquantes.items()]


def verdict(results: Sequence[DimensionResult]) -> Dict[str, Any]:
    """
    Le verdict d'ensemble, difficile à atteindre exprès.

    Args:
        results: Les dimensions examinées.

    Returns:
        `VERIFIED` seulement si **toutes** les dimensions applicables sont
        mesurées et qu'aucune n'a échoué. Une seule non mesurable rend
        `INCOMPLETE` — jamais « conforme avec réserves ». Un rapport vert sur
        des dimensions non mesurées serait cru plutôt que regardé, et il porte
        ici sur le visage de quelqu'un.

        **Aucune note composite n'est rendue**, et aucune clé n'existe pour en
        recevoir une.
    """
    if not results:
        return {
            "verdict": INCOMPLET,
            "reason": (
                "Aucune dimension examinée. Un rapport vide n'est pas une "
                "conformité : c'est l'absence de vérification."
            ),
            "counts": {issue: 0 for issue in ISSUES},
            "measured": [], "not_measurable": [], "failed": [],
        }

    comptes = {issue: sum(1 for r in results if r.outcome == issue)
               for issue in ISSUES}
    echecs = [r.dimension for r in results if r.outcome == ECHOUEE]
    non_mesurables = [r.dimension for r in results
                      if r.outcome == NON_MESURABLE]
    mesurees = [r.dimension for r in results if r.outcome == MESUREE]

    if echecs:
        etat, raison = EN_ECHEC, (
            f"{len(echecs)} dimension(s) en écart : {', '.join(echecs[:5])}."
        )
    elif non_mesurables:
        etat, raison = INCOMPLET, (
            f"{len(non_mesurables)} dimension(s) **non mesurables** : "
            f"{', '.join(non_mesurables[:5])}. Une identité dont on n'a pas pu "
            "vérifier la moitié n'a pas été vérifiée."
        )
    else:
        etat, raison = VERIFIE, (
            "Toutes les dimensions applicables ont été mesurées, et aucune "
            "n'est en écart."
        )

    return {
        "verdict": etat,
        "counts": comptes,
        "measured": mesurees,
        "not_measurable": non_mesurables,
        "failed": echecs,
        "missing_capabilities": sorted({
            r.missing_capability for r in results
            if r.outcome == NON_MESURABLE and r.missing_capability
        }),
        "reason": raison,
        "note": (
            "Aucune note composite n'est produite : une note unique cacherait "
            "la dimension qui compte derrière la moyenne de celles qui ne "
            "comptent pas."
        ),
    }


@dataclass(frozen=True)
class ShotVerification:
    """
    La vérification d'un plan : ses dimensions et son verdict.

    Attributes:
        shot_id: Le plan vérifié.
        dimensions: Les résultats, un par dimension.
        entity_id: L'entité concernée, quand la vérification la vise.
    """

    shot_id: str
    dimensions: Tuple[DimensionResult, ...] = ()
    entity_id: str = ""

    def verdict(self) -> Dict[str, Any]:
        """Le verdict de ce plan."""
        return verdict(self.dimensions)

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "shot_id": self.shot_id, "entity_id": self.entity_id,
            "dimensions": [d.as_dict() for d in self.dimensions],
            "verdict": self.verdict(),
        }


def drift(previous: DimensionResult, current: DimensionResult) -> Dict[str, Any]:
    """
    L'écart d'une dimension entre deux plans (§49).

    Args:
        previous: Le résultat du plan précédent.
        current: Le résultat du plan courant.

    Returns:
        L'écart quand les **deux** côtés sont mesurés, `UNKNOWN` sinon. Un
        écart de `0.0` sur une dimension non mesurée serait une constatation —
        « aucune dérive » — et c'est celle qu'une chaîne cassée produit le plus
        souvent.

    Raises:
        VerificationRefused: Si les deux résultats ne portent pas sur la même
            dimension : comparer une similarité faciale à une cohérence de
            vêtement produirait un nombre qui ne veut rien dire.
    """
    if previous.dimension != current.dimension:
        raise VerificationRefused(
            f"« {previous.dimension} » et « {current.dimension} » ne sont pas "
            "la même dimension : leur écart n'aurait aucun sens."
        )

    if previous.outcome != MESUREE or current.outcome != MESUREE:
        indisponible = (previous if previous.outcome != MESUREE else current)
        return {
            "dimension": current.dimension,
            "drift": None,
            "state": "UNKNOWN",
            "reason": (
                f"Dimension non mesurée des deux côtés "
                f"({indisponible.outcome}). Rendre `0.0` affirmerait l'absence "
                "de dérive, ce qu'une chaîne cassée produit le plus souvent."
            ),
            "missing_capability": indisponible.missing_capability,
        }

    ecart = round(abs((current.value or 0.0) - (previous.value or 0.0)), 6)
    return {
        "dimension": current.dimension,
        "drift": ecart,
        "state": "MEASURED",
        "method": current.method,
        "scale": current.scale,
        "reason": f"Écart mesuré entre deux valeurs comparables : {ecart}.",
    }


def drift_across(verifications: Sequence[ShotVerification]) -> Dict[str, Any]:
    """
    La dérive plan par plan, et les plans qu'elle désigne.

    Args:
        verifications: Les vérifications, dans l'ordre des plans.

    Returns:
        Les écarts par dimension et les plans concernés. Les dimensions non
        mesurables restent `UNKNOWN` : elles ne comptent ni comme stables ni
        comme dérivantes.
    """
    if len(verifications) < 2:
        return {
            "comparisons": [],
            "affected_shots": [],
            "unknown_dimensions": [],
            "reason": (
                "Moins de deux plans : une dérive se constate entre deux "
                "états, pas sur un seul."
            ),
        }

    comparaisons, concernes, inconnues = [], set(), set()
    for precedent, courant in zip(verifications, verifications[1:]):
        par_dimension = {d.dimension: d for d in precedent.dimensions}
        for resultat in courant.dimensions:
            reference = par_dimension.get(resultat.dimension)
            if reference is None:
                continue
            ecart = drift(reference, resultat)
            ecart["from_shot"] = precedent.shot_id
            ecart["to_shot"] = courant.shot_id
            comparaisons.append(ecart)
            if ecart["state"] == "UNKNOWN":
                inconnues.add(resultat.dimension)
            elif ecart["drift"]:
                concernes.add(courant.shot_id)

    return {
        "comparisons": comparaisons,
        "affected_shots": sorted(concernes),
        "unknown_dimensions": sorted(inconnues),
        "note": (
            "Les dimensions inconnues ne comptent ni comme stables ni comme "
            "dérivantes. Les ranger d'un côté ou de l'autre inventerait une "
            "constatation."
        ),
    }


def continuity_check(
    results: Sequence[DimensionResult], applicable: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Le contrôle de continuité (§50), avec la même discipline à trois issues.

    Args:
        results: Les dimensions examinées.
        applicable: Les dimensions qui devaient l'être. Toutes celles de
            `DIMENSIONS_DE_CONTINUITE` par défaut.

    Returns:
        Le verdict, les dimensions **jamais examinées**, et la confiance.
        Une dimension applicable qu'on a oublié d'examiner est signalée : un
        contrôle qui ne liste que ce qu'il a regardé se lit comme un contrôle
        complet.

        Aucune continuité parfaite n'est jamais affirmée — §19 l'interdit et
        rien ici ne peut la constater.
    """
    attendues = list(applicable or DIMENSIONS_DE_CONTINUITE)
    examinees = {r.dimension for r in results}
    jamais = [d for d in attendues if d not in examinees]

    resume = verdict(results)
    resume["never_examined"] = jamais
    if jamais and resume["verdict"] == VERIFIE:
        resume["verdict"] = INCOMPLET
        resume["reason"] = (
            f"{len(jamais)} dimension(s) applicables n'ont jamais été "
            f"examinées : {', '.join(jamais[:5])}. Un contrôle qui ne liste "
            "que ce qu'il a regardé se lit comme un contrôle complet."
        )
    resume["claims_perfect_continuity"] = False
    return resume


def quality_loop(
    verifications: Sequence[ShotVerification],
) -> Dict[str, Any]:
    """
    Ce que la boucle qualité (§51) demande de refaire — et rien de plus.

    Args:
        verifications: Les vérifications des plans générés.

    Returns:
        Les plans à refaire, ceux à laisser, et l'étape suivante. **Seuls les
        plans en écart sont désignés** : refaire une production entière pour
        corriger un plan en coûte le prix entier, et §51 demande explicitement
        de ne régénérer que le nécessaire.

        Un plan dont la vérification est `INCOMPLETE` n'est **pas** à refaire :
        il est à *vérifier*. Le confondre avec un échec ferait régénérer sans
        fin sur une machine qui ne peut rien mesurer.
    """
    a_refaire, a_verifier, conformes = [], [], []
    for verification in verifications:
        etat = verification.verdict()["verdict"]
        if etat == EN_ECHEC:
            a_refaire.append(verification.shot_id)
        elif etat == INCOMPLET:
            a_verifier.append(verification.shot_id)
        else:
            conformes.append(verification.shot_id)

    if a_refaire:
        suivante = "REGENERATE"
    elif a_verifier:
        suivante = "VERIFY"
    else:
        suivante = "FINALIZE"

    return {
        "stages": list(BOUCLE),
        "regenerate": a_refaire,
        "needs_verification": a_verifier,
        "passed": conformes,
        "next_stage": suivante,
        "note": (
            "Seuls les plans en écart sont régénérés (§51). Un plan "
            "`INCOMPLETE` est à **vérifier**, pas à refaire : les confondre "
            "ferait régénérer sans fin sur une machine incapable de mesurer."
        ),
    }


def verification_report() -> Dict[str, Any]:
    """
    Ce que la vérification garantit, et ce qu'elle refuse.

    Returns:
        Les vocabulaires déclarés, l'état réel des dimensions ici, et les
        règles tenues.
    """
    dimensions = identity_dimensions_here()
    return {
        "outcomes": list(ISSUES),
        "verdicts": [VERIFIE, INCOMPLET, EN_ECHEC],
        "identity_dimensions": list(DIMENSIONS_D_IDENTITE),
        "continuity_dimensions": list(DIMENSIONS_DE_CONTINUITE),
        "severities": list(GRAVITES),
        "loop": list(BOUCLE),
        "here": verdict(dimensions),
        "composite_score": None,
        "rules": [
            "**Aucune note composite d'identité n'existe**, et aucun champ ne "
            "peut en recevoir une : une note unique cacherait la dimension qui "
            "compte derrière la moyenne des autres (§48).",
            "Trois issues, jamais deux : « pas pu vérifier » et « vérifié, "
            "conforme » doivent rester impossibles à confondre.",
            "Une dimension `MEASURED` **nomme sa méthode et son échelle** ; "
            "sans elles, le nombre est une invention habillée en mesure.",
            "Une dimension `NOT_MEASURABLE` **nomme la capacité manquante** : "
            "le rapport doit servir de liste d'installation.",
            "Une seule dimension non mesurable rend le verdict `INCOMPLETE`, "
            "jamais « conforme avec réserves ».",
            "Une dérive sur une dimension non mesurée est `UNKNOWN` : `0.0` "
            "affirmerait l'absence de dérive, ce qu'une chaîne cassée produit "
            "le plus souvent.",
            "Un plan `INCOMPLETE` est à vérifier, pas à refaire.",
        ],
        "does_not": [
            "Produire un score d'identité composite.",
            "Rendre `0.0` pour une dimension non mesurée.",
            "Affirmer une continuité parfaite.",
            "Régénérer des plans que rien ne concerne.",
        ],
    }
