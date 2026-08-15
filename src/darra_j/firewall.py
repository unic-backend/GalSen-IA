"""
The gate a curriculum answer passes before anyone reads it.

Everything before this module produces records. This module decides whether a
record may be spoken, and in what capacity — because the dangerous moment in an
educational system is not retrieval, it is the sentence a student reads and
believes.

The chain is fixed and every step can stop it:

    parse → resolve → retrieve → verify version → verify authority
         → verify status → generate → attach provenance → validate → answer

Three rules give it its shape.

**Generation never happens without a canonical record.** Not "generation is
discouraged", not "generation is labelled" — it does not run. A model asked to
explain week 10 with nothing in the register would produce a fluent, teachable,
entirely invented lesson, and a label under it would not save the student who
read it.

**The canonical fields are returned verbatim, beside the explanation, never
merged into it.** The explanation may be simplified, translated, rephrased; the
official title, objectives and competencies are copied unchanged. A response
where the two are indistinguishable is a response where nobody can tell what the
ministry said.

**A refusal is a real answer.** `UNKNOWN` and `AMBIGUOUS` come back with their
reason and no substitute. Directive XXIII says it plainly: never fill the gap
using model knowledge — and the system should be proud of `UNKNOWN`.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from .registry import AMBIGU, INCONNU, TROUVE, CurriculumRegistry
from .resolution import CLARIFICATION, CurriculumQuery, resolve

#: Les types de réponse (directive XXIV). Ils disent **ce qu'une phrase est**,
#: et c'est l'information qu'une interface doit pouvoir montrer.
CANONIQUE = "CANONICAL_OFFICIAL"
SUPPLEMENT_VERIFIE = "VERIFIED_SUPPLEMENTARY"
DERIVE_IA = "AI_DERIVED"
GENERE_IA = "AI_GENERATED"
NON_VERIFIE = "NOT_VERIFIED"
CONFLIT = "CONFLICTING_SOURCE"

#: Les vérifications obligatoires. Chacune peut arrêter la chaîne, et celle qui
#: l'arrête est **nommée** : « non vérifié » sans cause fait chercher partout.
VERIFICATIONS = ("resolution", "version", "authority", "status", "provenance")


class FirewallRefused(RuntimeError):
    """Une réponse que le pare-feu refuse de laisser sortir."""


def _etape(nom: str, ok: bool, detail: str) -> Dict[str, Any]:
    """Le résultat d'une vérification."""
    return {"check": nom, "passed": ok, "detail": detail}


def answer(
    query: CurriculumQuery,
    registry: CurriculumRegistry,
    explain: Optional[Callable[[Dict[str, Any]], str]] = None,
    level: int = 2,
) -> Dict[str, Any]:
    """
    Répond à une question de curriculum, ou refuse en disant pourquoi.

    Args:
        query: La question, avec ses coordonnées.
        registry: Le registre des versions officielles.
        explain: L'explication pédagogique, injectée. Elle reçoit **le fait
            canonique** et rend du texte. Elle n'est appelée que si un fait
            existe : c'est là toute la garantie de ce module.
        level: Le niveau d'explication demandé (1 à 5). Ne change que la
            présentation, jamais le fait.

    Returns:
        La réponse, son type, les vérifications franchies, et la provenance.
        Une réponse refusée porte `NOT_VERIFIED` ou `UNKNOWN` avec sa cause et
        **aucun substitut**.
    """
    debut = time.perf_counter()
    verifications: List[Dict[str, Any]] = []

    resolution = resolve(query, registry)
    verifications.append(_etape(
        "resolution", resolution["status"] == TROUVE, resolution.get("reason", ""),
    ))

    if resolution["status"] == CLARIFICATION:
        return _refus(
            CLARIFICATION, resolution["reason"], verifications, debut,
            missing=resolution["missing"],
        )
    if resolution["status"] == AMBIGU:
        return _refus(
            CONFLIT, resolution["reason"], verifications, debut,
            candidates=resolution.get("candidates", []),
        )
    if resolution["status"] != TROUVE:
        return _refus(INCONNU, resolution["reason"], verifications, debut)

    version = registry.get_version(resolution["version_id"])
    verifications.append(_etape(
        "version", version is not None,
        f"Version « {resolution['version_id']} »." if version else "Version absente.",
    ))
    if version is None:
        return _refus(
            NON_VERIFIE,
            "L'unité désigne une version que le registre ne contient pas.",
            verifications, debut,
        )

    verifications.append(_etape(
        "authority", version.provenance.source_tier.startswith("TIER_A"),
        f"Rang « {version.provenance.source_tier} ».",
    ))
    verifications.append(_etape(
        "status", version.is_official,
        f"État « {version.status.value} », officiel : {version.is_official}.",
    ))

    provenance = resolution["provenance"]
    verifications.append(_etape(
        "provenance", provenance["status"] == TROUVE and bool(provenance.get("authority")),
        f"Autorité : {provenance.get('authority', '—')}.",
    ))

    echouees = [v["check"] for v in verifications if not v["passed"]]
    if echouees:
        return _refus(
            NON_VERIFIE,
            "Vérifications non franchies : " + ", ".join(echouees)
            + ". Combler avec ce qu'un modèle croit savoir remplacerait un fait "
            "institutionnel par une vraisemblance.",
            verifications, debut,
        )

    unite = resolution["unit"]
    canonique = {
        "official_title": unite["official_title"],
        "official_description": unite["official_description"],
        "competencies": unite["competencies"],
        "objectives": unite["objectives"],
        "prerequisites": unite["prerequisites"],
        "activities": unite["activities"],
        "evaluation_requirements": unite["evaluation_requirements"],
        "content_hash": unite["content_hash"],
    }

    # L'explication n'est produite **qu'ici**, une fois le fait établi. Une
    # génération lancée avant aurait déjà écrit une leçon inventée, et une
    # étiquette posée dessous ne sauverait pas l'élève qui l'a lue.
    explication = None
    if explain is not None:
        explication = str(explain({"canonical": canonique, "level": level}) or "")

    return {
        "answer_type": CANONIQUE,
        "status": TROUVE,
        "canonical": canonique,
        "explanation": explication,
        "explanation_type": DERIVE_IA if explication else None,
        "explanation_level": level if explication else None,
        "unit_id": resolution["unit_id"],
        "version_id": resolution["version_id"],
        "provenance": provenance,
        "checks": verifications,
        "dimensions": resolution["dimensions"],
        "elapsed_ms": round((time.perf_counter() - debut) * 1000, 2),
        "note": (
            "Le fait officiel est rendu **tel quel**, à côté de l'explication et "
            "jamais fondu dedans : une réponse où l'on ne distingue pas les deux "
            "est une réponse où personne ne sait ce que le ministère a dit."
        ),
    }


def _refus(
    type_reponse: str, raison: str, verifications: List[Dict[str, Any]],
    debut: float, **extra: Any,
) -> Dict[str, Any]:
    """
    Construit un refus : une réponse à part entière, sans substitut.

    Aucune explication n'est produite ici, et c'est délibéré : le seul moment où
    un modèle pourrait « aider » est précisément celui où il inventerait.
    """
    return {
        "answer_type": type_reponse,
        "status": INCONNU if type_reponse in (INCONNU, NON_VERIFIE) else type_reponse,
        "canonical": None,
        "explanation": None,
        "reason": raison,
        "checks": verifications,
        "elapsed_ms": round((time.perf_counter() - debut) * 1000, 2),
        "note": (
            "Aucun substitut n'est proposé. `UNKNOWN` est plus sûr qu'une "
            "réponse fausse, et le système en est fier."
        ),
        **extra,
    }


def classify_supplement(
    source_tier: str, verified: bool = False,
) -> str:
    """
    Dit ce qu'un contenu **non canonique** est.

    Args:
        source_tier: Le rang de sa source.
        verified: S'il a été vérifié par quelqu'un.

    Returns:
        `VERIFIED_SUPPLEMENTARY` pour un complément vérifié, `AI_GENERATED`
        sinon. Un complément ne devient jamais `CANONICAL_OFFICIAL` : le rang
        d'une source décide de ce qu'on peut en faire, pas de ce qu'elle vaut.
    """
    if verified and source_tier.startswith(("TIER_A", "TIER_B")):
        return SUPPLEMENT_VERIFIE
    return GENERE_IA


def firewall_report() -> Dict[str, Any]:
    """
    Ce que le pare-feu garantit, et ce qu'il refuse.

    Returns:
        Les types de réponse, les vérifications, et les règles tenues.
    """
    return {
        "answer_types": [
            CANONIQUE, SUPPLEMENT_VERIFIE, DERIVE_IA, GENERE_IA,
            INCONNU, CLARIFICATION, CONFLIT, NON_VERIFIE,
        ],
        "mandatory_checks": list(VERIFICATIONS),
        "rules": [
            "Aucune génération sans fait canonique : le modèle n'est pas "
            "appelé, pas seulement étiqueté. Une leçon inventée reste lisible "
            "et enseignable — l'étiquette ne sauve pas l'élève qui l'a lue.",
            "Le fait officiel est rendu **tel quel**, à côté de l'explication : "
            "les fondre rendrait indistinguable ce que le ministère a dit.",
            "Une vérification non franchie **nomme** laquelle : « non vérifié » "
            "sans cause fait chercher partout.",
            "Un refus est une réponse : `UNKNOWN`, `AMBIGUOUS` et "
            "`CLARIFICATION_REQUIRED` reviennent avec leur raison et aucun "
            "substitut.",
            "Un complément ne devient jamais canonique, quel que soit son "
            "intérêt pédagogique.",
        ],
        "does_not": [
            "Compléter un curriculum absent depuis la mémoire d'un modèle.",
            "Choisir entre deux enregistrements officiels contradictoires.",
            "Modifier un champ officiel pour le rendre plus clair : la clarté "
            "est le travail de l'explication, à côté.",
        ],
    }
