"""
Les dix contrôles, et ce que chacun peut faire (ADR-021, étape 8).

Entre `PARSED` et `VERIFIED`, dix questions. Chacune rend un verdict, et surtout
chacune a un **pouvoir borné** : certaines peuvent refuser, la plupart ne peuvent
que mettre en quarantaine.

## La distinction qui porte tout

- **Refuser** est mécanique et sans appel : le rang interdit la collecte, le
  document est vide, c'est un doublon exact. Aucun jugement n'est en jeu.
- **Mettre en quarantaine** dit : *la mesure ne tranche pas*. Une personne le
  fera. C'est le verdict par défaut de tout ce qui est incertain, et
  **`unknown` y va toujours** — une lacune n'est pas un feu vert.

Donner à la pertinence le pouvoir de refuser, par exemple, viderait la base des
documents que le registre n'a pas su décrire. Elle ne peut que signaler.

## Ce que les contrôles ne font pas

Ils ne disent pas si un document est **vrai**. Aucun composant de ce dépôt ne le
peut, et prétendre le contraire serait le mensonge le plus coûteux qu'il puisse
faire. Ils disent d'où il vient, s'il est complet, s'il est déjà là, et s'il
contredit ce qui est déjà détenu.
"""

from typing import Any, Callable, Dict, List, Optional

from ..knowledge_engine.contradictions import detect_contradictions
from ..knowledge_engine.markers import sujets_reperes
from ..knowledge_engine.source_registry import RANGS_ACQUERABLES, SourceTier
from .dedup import SEUIL_DE_PROXIMITE, find_duplicates
from .record import PROVENANCE_MINIMALE, AcquiredDocument, AcquisitionStatus

#: Ce qui n'a pas été établi.
INCONNU = "unknown"

#: Verdicts d'un contrôle, du plus faible au plus fort. L'ordre compte : le
#: verdict du lot est le maximum de ses contrôles.
OK, QUARANTAINE, REFUS = "ok", "quarantine", "reject"

_FORCE = {OK: 0, QUARANTAINE: 1, REFUS: 2}

#: Caractères en dessous desquels l'extraction n'a rien rendu d'exploitable.
TEXTE_MINIMUM = 200


def _verdict(nom: str, verdict: str, raison: str, **details) -> Dict[str, Any]:
    """Assemble le résultat d'un contrôle."""
    return {"check": nom, "verdict": verdict, "reason": raison, **details}


# ----------------------------------------------------------------------
# Les dix contrôles
# ----------------------------------------------------------------------

def check_authority(document: AcquiredDocument, tier_defaulted: bool = False) -> Dict[str, Any]:
    """Le rang de la source — le seul contrôle qui parle d'autorité."""
    rang = document.source_tier
    try:
        valeur = SourceTier(rang)
    except ValueError:
        return _verdict("authority", REFUS, f"Rang « {rang} » inconnu du registre.")

    if valeur not in RANGS_ACQUERABLES:
        return _verdict(
            "authority", REFUS,
            f"{valeur.value} est une piste, jamais une source : elle peut faire "
            "chercher un document ailleurs, elle n'entre pas.",
        )
    if tier_defaulted:
        return _verdict(
            "authority", QUARANTAINE,
            "Le rang a été replié depuis la catégorie : personne ne l'a relu. Un "
            "rang non relu ne doit pas donner d'autorité en silence.",
        )
    return _verdict("authority", OK, f"Rang {valeur.value}, déclaré au registre.")


def check_integrity(document: AcquiredDocument, texte: str) -> Dict[str, Any]:
    """Le document a des octets, une empreinte, et du texte."""
    if document.content_hash == INCONNU:
        return _verdict("integrity", REFUS, "Aucune empreinte de contenu : rien n'a été reçu.")
    if len(texte or "") < TEXTE_MINIMUM:
        return _verdict(
            "integrity", QUARANTAINE,
            f"{len(texte or '')} caractères extraits (minimum {TEXTE_MINIMUM}). Un PDF "
            "scanné, une page vide et une extraction ratée se ressemblent ici.",
        )
    return _verdict("integrity", OK, f"{len(texte)} caractères extraits.")


def check_provenance(document: AcquiredDocument) -> Dict[str, Any]:
    """La provenance minimale, sans laquelle rien n'entre dans la couche de confiance."""
    manquants = document.missing_for_trusted_layer()
    if manquants:
        return _verdict(
            "provenance", QUARANTAINE,
            "Provenance incomplète : " + ", ".join(manquants) + ".",
            missing=manquants,
        )
    return _verdict(
        "provenance", OK,
        f"Les {len(PROVENANCE_MINIMALE)} champs minimaux sont établis.",
    )


def check_duplicate(
    texte: str, corpus: List[Dict[str, str]], seuil: float = SEUIL_DE_PROXIMITE
) -> Dict[str, Any]:
    """Déjà là à l'identique, ou presque."""
    doublons = find_duplicates(texte, corpus, seuil)
    if doublons["identical"]:
        return _verdict(
            "duplicate", REFUS,
            "Document déjà détenu à l'identique : "
            + ", ".join(entree["id"] for entree in doublons["identical"]) + ".",
            matches=doublons["identical"],
        )
    if doublons["near"]:
        meilleur = doublons["near"][0]
        return _verdict(
            "duplicate", QUARANTAINE,
            f"Quasi-doublon de « {meilleur['id']} » ({meilleur['similarity']:.0%}). "
            "Une version corrigée et une republication paresseuse se ressemblent ici.",
            matches=doublons["near"],
        )
    return _verdict("duplicate", OK, "Aucun doublon dans le corpus comparé.")


def check_date(document: AcquiredDocument) -> Dict[str, Any]:
    """La date de publication — absente n'est pas fausse."""
    if document.publication_date == INCONNU:
        return _verdict(
            "date", QUARANTAINE,
            "Date de publication inconnue. Un document officiel non daté reste un "
            "document officiel : c'est une lacune à confirmer, pas un refus.",
        )
    return _verdict("date", OK, f"Publié le {document.publication_date}.")


def check_language(document: AcquiredDocument) -> Dict[str, Any]:
    """La langue détectée contre la langue déclarée."""
    accord = document.provenance.get("language_agreement", "undetected")
    if accord == "disagree":
        return _verdict(
            "language", QUARANTAINE,
            f"Déclaré « {document.language_declared} », détecté « {document.language} ».",
        )
    if document.language == INCONNU:
        return _verdict(
            "language", QUARANTAINE,
            "Langue non détectée. Le sérère n'a aucune liste de marqueurs, "
            "délibérément — `unknown` est ici le résultat correct, et il demande "
            "une confirmation, pas un refus.",
        )
    return _verdict("language", OK, f"Langue « {document.language} » ({accord}).")


def check_relevance(texte: str, sujets_declares: List[str]) -> Dict[str, Any]:
    """
    Le sujet repéré contre les sujets déclarés par la source.

    **Ce contrôle ne peut jamais refuser.** Les marqueurs de sujet sont un signal
    faible ; leur donner le pouvoir de refuser viderait la base des documents que
    le registre n'a pas su décrire.
    """
    if not sujets_declares:
        return _verdict("relevance", OK, "La source ne déclare aucun sujet : rien à confronter.")

    reperes = sujets_reperes(texte or "")
    if not reperes:
        return _verdict(
            "relevance", QUARANTAINE,
            "Aucun sujet repéré dans le texte. Signal faible : ce contrôle ne "
            "refuse jamais.",
        )
    communs = sorted(set(reperes) & set(sujets_declares))
    if not communs:
        return _verdict(
            "relevance", QUARANTAINE,
            f"Sujets repérés {reperes} hors de ce que la source déclare "
            f"({sujets_declares}). Signal faible : à confirmer, pas à refuser.",
        )
    return _verdict("relevance", OK, f"Sujets communs : {communs}.")


def check_extraction(document: AcquiredDocument) -> Dict[str, Any]:
    """L'extraction a-t-elle réellement rendu quelque chose."""
    if not document.provenance.get("text_extracted", False):
        return _verdict(
            "extraction", QUARANTAINE,
            "Le texte n'a pas pu être extrait. Un extracteur absent et un document "
            "sans texte demandent deux actions différentes.",
        )
    return _verdict("extraction", OK, "Texte extrait.")


def check_contradiction(
    document: AcquiredDocument, texte: str, corpus: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Le document contre ce qui est déjà détenu — **rapporté, jamais résolu**.

    Aucun gagnant n'est désigné : le plus récent n'est pas automatiquement le
    bon, et écraser un fait validé en silence est la façon dont une base pourrit.
    """
    candidat = {
        "id": document.source_url,
        "content": texte,
        "scope": document.provenance.get("scope", "global"),
        "subject": document.provenance.get("subject", "unspecified"),
    }
    rapport = detect_contradictions([candidat] + list(corpus))
    if rapport["contradictions"]:
        return _verdict(
            "contradiction", QUARANTAINE,
            f"{len(rapport['contradictions'])} désaccord(s) avec la base. Rapporté, "
            "jamais résolu : la décision revient à une personne.",
            conflicts=rapport["contradictions"],
        )
    return _verdict("contradiction", OK, "Aucun désaccord repéré avec la base.")


def check_licence(document: AcquiredDocument) -> Dict[str, Any]:
    """
    La licence — inconnue **dégrade**, elle ne bloque pas.

    Sinon les meilleures sources seraient les premières écartées : une
    institution publie rarement une licence lisible par une machine.
    """
    usage = document.license_or_usage_status
    if usage == INCONNU:
        return _verdict(
            "licence", QUARANTAINE,
            "Statut d'usage inconnu : à établir avant de citer le document.",
        )
    if usage == "reference_only":
        return _verdict(
            "licence", OK,
            "Licence inconnue ou non reproductible : citable par son URL et par "
            "fragments, pas reproductible en entier. Une licence absente dégrade, "
            "elle ne bloque pas.",
        )
    return _verdict("licence", OK, f"Usage autorisé : {usage}.")


# ----------------------------------------------------------------------
# L'agrégation
# ----------------------------------------------------------------------

def evaluate(
    document: AcquiredDocument,
    texte: str,
    *,
    corpus: Optional[List[Dict[str, Any]]] = None,
    declared_subjects: Optional[List[str]] = None,
    tier_defaulted: bool = False,
    seuil_de_proximite: float = SEUIL_DE_PROXIMITE,
    now: Optional[Callable] = None,
) -> Dict[str, Any]:
    """
    Passe les dix contrôles et mène le document de `PARSED` à son verdict.

    Args:
        document: Le document, au statut `PARSED`.
        texte: Le texte extrait.
        corpus: Ce qui est déjà détenu, pour les doublons et les contradictions.
        declared_subjects: Sujets déclarés par la source au registre.
        tier_defaulted: Vrai si le rang a été replié depuis la catégorie.
        seuil_de_proximite: Seuil du quasi-doublon.
        now: Injectable, réservé aux mesures de fraîcheur.

    Returns:
        Les dix verdicts, le verdict d'ensemble, et **les raisons qui l'ont
        produit**. Un document arrêté sans raison lisible obligerait à relire le
        code pour savoir quoi corriger.
    """
    if document.status is not AcquisitionStatus.PARSED:
        return {
            "evaluated": False,
            "reason": (
                f"Un document au statut {document.status.value} n'est pas prêt : les "
                "contrôles se placent entre l'extraction et le verdict."
            ),
        }

    corpus = list(corpus or [])
    textes = [{"id": e.get("id", ""), "text": e.get("content", e.get("text", ""))} for e in corpus]

    controles = [
        check_authority(document, tier_defaulted),
        check_integrity(document, texte),
        check_provenance(document),
        check_duplicate(texte, textes, seuil_de_proximite),
        check_date(document),
        check_language(document),
        check_relevance(texte, list(declared_subjects or [])),
        check_extraction(document),
        check_contradiction(document, texte, corpus),
        check_licence(document),
    ]

    pire = max(controles, key=lambda c: _FORCE[c["verdict"]])
    bloquants = [c for c in controles if c["verdict"] == pire["verdict"] != OK]

    if pire["verdict"] == REFUS:
        raison = "Refusé — " + " ; ".join(c["reason"] for c in bloquants)
        document.transition(AcquisitionStatus.REJECTED, raison)
    elif pire["verdict"] == QUARANTAINE:
        raison = "En quarantaine — " + " ; ".join(c["reason"] for c in bloquants)
        document.transition(AcquisitionStatus.QUARANTINED, raison)
    else:
        raison = "Les dix contrôles passent."
        document.transition(AcquisitionStatus.VERIFIED, raison)

    return {
        "evaluated": True,
        "checks": controles,
        "verdict": pire["verdict"],
        "status": document.status.value,
        "reasons": [c["reason"] for c in bloquants],
        "passed": [c["check"] for c in controles if c["verdict"] == OK],
        "note": (
            "Refuser est mécanique ; mettre en quarantaine dit que la mesure ne "
            "tranche pas. `unknown` va toujours en quarantaine — une lacune n'est "
            "pas un feu vert."
        ),
    }


def quality_report() -> Dict[str, Any]:
    """Décrit les dix contrôles et le pouvoir de chacun."""
    return {
        "checks": {
            "authority": "peut refuser (TIER_D, rang inconnu) ou mettre en quarantaine (rang replié)",
            "integrity": "peut refuser (aucune empreinte)",
            "provenance": "quarantaine seulement",
            "duplicate": "peut refuser (identique) ou mettre en quarantaine (proche)",
            "date": "quarantaine seulement — absente n'est pas fausse",
            "language": "quarantaine seulement",
            "relevance": "quarantaine seulement — signal faible, ne refuse jamais",
            "extraction": "quarantaine seulement",
            "contradiction": "quarantaine seulement — rapporté, jamais résolu",
            "licence": "quarantaine seulement — inconnue dégrade, ne bloque pas",
        },
        "can_reject": ["authority", "integrity", "duplicate"],
        "unknown_goes_to": "quarantine",
        "does_not_answer": (
            "si le document est vrai — aucun composant de ce dépôt ne le peut, et "
            "prétendre le contraire serait son mensonge le plus coûteux"
        ),
    }
