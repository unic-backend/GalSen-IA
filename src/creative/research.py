"""
The provider research record, and the rule that keeps it from drifting into
optimism.

Directive §37–§40 asks for an ecosystem survey, a provider comparison and a
licence audit. Written as prose, all three go stale in a month and nobody
notices — and the way they go stale is always the same direction. A field that
was `UNKNOWN` in October gets quoted in November as "Apache-2.0", because the
repository was Apache-2.0 and the distinction between a repository licence and
a weight licence is exactly the kind of thing that survives in a document for
about one reading.

So the record is **data with provenance per field**, and this module refuses it
at load time when the discipline is broken. Four rules, each of which exists
because breaking it produces a specific wrong decision:

1. **A verified field must name where it was verified.** `AUTHORITATIVE`
   without a source URL is a claim, not evidence.
2. **A secondary source can never make a field authoritative.** An article
   summarising a licence is not the licence. §67 says so, and this is where it
   is enforced rather than remembered.
3. **`UNKNOWN` must carry its reason.** "We do not know" and "we did not look"
   lead to different next actions, and only the reason distinguishes them.
4. **Commercial permission is never inferred.** `commercial_status: ALLOWED`
   requires *both* the repository licence and the weight licence verified from
   authoritative sources. Popularity, permissive code, and downloadable weights
   are three things that are not permission.

Nothing here selects a provider. Selection is C04's decision and belongs in an
ADR; this module only makes the evidence checkable.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

import yaml

#: Le fichier de recherche, à la racine du dépôt.
CHEMIN_PAR_DEFAUT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "corpus", "creative", "providers.yaml",
)

#: Niveaux de preuve. Ils sont ordonnés : `SECONDARY` ne vaut jamais
#: `AUTHORITATIVE`, et une lecture d'article ne devient pas une lecture de
#: licence parce qu'elle est confiante.
AUTORITATIF = "AUTHORITATIVE"
SECONDAIRE = "SECONDARY"
AUCUNE = "NONE"
NIVEAUX_DE_PREUVE = (AUTORITATIF, SECONDAIRE, AUCUNE)

#: L'absence, déclarée. `UNKNOWN` n'est pas « non », et `NOT_MEASURED` n'est pas
#: « mauvais » : ce sont deux façons différentes de ne pas savoir.
INCONNU = "UNKNOWN"
NON_MESURE = "NOT_MEASURED"
SANS_OBJET = "NOT_APPLICABLE"
ABSENCES = (INCONNU, NON_MESURE, SANS_OBJET)

#: Les états commerciaux déclarables.
COMMERCIAL_AUTORISE = "ALLOWED"
COMMERCIAL_RESTREINT = "RESTRICTED"
COMMERCIAL_PARTIEL = "PARTIAL"
ETATS_COMMERCIAUX = (COMMERCIAL_AUTORISE, COMMERCIAL_RESTREINT,
                     COMMERCIAL_PARTIEL, INCONNU)

#: Les champs qui ne peuvent **jamais** porter une valeur sans mesure. Une
#: qualité ou une latence recopiée d'un README est la revendication d'un
#: projet, pas un résultat : les confondre fait choisir un fournisseur sur la
#: promesse d'un autre.
CHAMPS_A_MESURER = ("quality", "latency", "identity_consistency")


class ResearchRefused(ValueError):
    """Un enregistrement de recherche qui se contredit. Levé au chargement."""


def _exiger_raison(entree: Dict[str, Any], champ: str) -> None:
    """Un champ inconnu doit dire pourquoi il l'est."""
    valeur = entree.get(champ)
    if valeur != INCONNU:
        return
    for cle in (f"{champ}_reason", f"{champ}_note"):
        if str(entree.get(cle, "")).strip():
            return
    raise ResearchRefused(
        f"« {entree.get('id')} » : {champ} vaut UNKNOWN sans raison. "
        "« On ne sait pas » et « on n'a pas regardé » appellent des actions "
        "différentes, et seule la raison les distingue."
    )


def _verifier_preuve(entree: Dict[str, Any], champ: str) -> None:
    """Une preuve autoritative doit nommer sa source."""
    niveau = entree.get(f"{champ}_evidence")
    if niveau is None:
        return
    if niveau not in NIVEAUX_DE_PREUVE:
        raise ResearchRefused(
            f"« {entree.get('id')} » : niveau de preuve « {niveau} » non "
            f"déclaré. Déclarés : {list(NIVEAUX_DE_PREUVE)}."
        )
    if niveau != AUTORITATIF:
        return
    source = entree.get(f"{champ}_source") or entree.get(f"{champ}_reason")
    if not str(source or "").strip():
        raise ResearchRefused(
            f"« {entree.get('id')} » : {champ} est déclaré AUTHORITATIVE sans "
            "source. Sans l'URL lue, c'est une affirmation, pas une preuve."
        )


def _verifier_commercial(entree: Dict[str, Any]) -> None:
    """
    Le droit commercial ne se déduit pas.

    `ALLOWED` exige que la licence du dépôt **et** celle des poids aient été
    lues à leur source. Un dépôt permissif dont les poids sont sous une licence
    à restrictions d'usage est le cas normal, pas l'exception.
    """
    etat = entree.get("commercial_status", INCONNU)
    if etat not in ETATS_COMMERCIAUX:
        raise ResearchRefused(
            f"« {entree.get('id')} » : commercial_status « {etat} » non "
            f"déclaré. Déclarés : {list(ETATS_COMMERCIAUX)}."
        )
    if etat != COMMERCIAL_AUTORISE:
        return
    depot = entree.get("repository_license_evidence")
    poids = entree.get("weight_license_evidence")
    if depot != AUTORITATIF or poids != AUTORITATIF:
        raise ResearchRefused(
            f"« {entree.get('id')} » : commercial_status ALLOWED alors que la "
            f"licence du dépôt est {depot} et celle des poids {poids}. Un dépôt "
            "permissif n'est pas une permission d'usage des poids — c'est la "
            "confusion que §40 existe pour empêcher."
        )


def _verifier_mesures(entree: Dict[str, Any]) -> None:
    """
    Qualité, latence et cohérence d'identité sont mesurées ou absentes.

    Recopier le chiffre d'un README ferait comparer la promesse d'un projet à
    la mesure d'un autre.
    """
    for champ in CHAMPS_A_MESURER:
        valeur = entree.get(champ)
        if valeur is None or valeur in ABSENCES:
            continue
        if not str(entree.get(f"{champ}_measured_by", "")).strip():
            raise ResearchRefused(
                f"« {entree.get('id')} » : {champ}={valeur} sans "
                f"`{champ}_measured_by`. Un chiffre repris d'un README est la "
                "revendication d'un projet, pas un résultat."
            )


def load_research(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Charge le dossier de recherche et refuse ce qui se contredit.

    Args:
        path: Le fichier YAML. Celui du dépôt par défaut.

    Returns:
        Les candidats, les jeux de données notés, et la date de la recherche.

    Raises:
        ResearchRefused: Sur un identifiant dupliqué, une preuve sans source, un
            `UNKNOWN` sans raison, un droit commercial déduit ou une mesure
            recopiée.
    """
    chemin = path or CHEMIN_PAR_DEFAUT
    with open(chemin, encoding="utf-8") as fichier:
        donnees = yaml.safe_load(fichier) or {}

    candidats = donnees.get("candidates") or []
    vus = set()
    for entree in candidats:
        identite = entree.get("id")
        if not identite:
            raise ResearchRefused("Un candidat sans identifiant ne peut être cité.")
        if identite in vus:
            raise ResearchRefused(f"Identifiant « {identite} » en double.")
        vus.add(identite)

        for champ in ("repository_license", "weight_license", "dataset_license"):
            _exiger_raison(entree, champ)
            _verifier_preuve(entree, champ)
        _verifier_preuve(entree, "commercial_status")
        _verifier_commercial(entree)
        _verifier_mesures(entree)

    return {
        "researched_on": donnees.get("researched_on"),
        "candidates": candidats,
        "datasets": donnees.get("datasets") or [],
        "path": chemin,
    }


def license_matrix(path: Optional[str] = None) -> Dict[str, Any]:
    """
    La matrice de licences demandée par §40, avec ses trous nommés.

    Returns:
        Une ligne par candidat, chaque licence accompagnée de son niveau de
        preuve, plus le compte de ce qui reste inconnu. Le compte est le
        résultat utile : il dit combien de décisions ne peuvent pas encore
        être prises.
    """
    dossier = load_research(path)
    lignes = []
    for entree in dossier["candidates"]:
        lignes.append({
            "id": entree["id"],
            "repository": entree.get("repository", INCONNU),
            "repository_license": entree.get("repository_license", INCONNU),
            "repository_license_evidence": entree.get(
                "repository_license_evidence", AUCUNE),
            "weight_license": entree.get("weight_license", INCONNU),
            "weight_license_evidence": entree.get("weight_license_evidence", AUCUNE),
            "dataset_license": entree.get("dataset_license", INCONNU),
            "commercial_status": entree.get("commercial_status", INCONNU),
            "restrictions": entree.get("repository_license_note", ""),
        })

    inconnues = {
        champ: [ligne["id"] for ligne in lignes if ligne[champ] == INCONNU]
        for champ in ("weight_license", "dataset_license", "commercial_status")
    }

    return {
        "rows": lignes,
        "count": len(lignes),
        "unknown": inconnues,
        "authoritative_repository_licenses": sum(
            1 for ligne in lignes
            if ligne["repository_license_evidence"] == AUTORITATIF),
        "note": (
            "Aucune ligne ne porte `ALLOWED` sans deux licences lues à leur "
            "source. Les `UNKNOWN` de la colonne poids viennent d'un fait "
            "mesuré : `huggingface.co` n'a aucune route depuis ce conteneur."
        ),
    }


def executable_here(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce que cette machine pourrait exécuter, mesuré et non supposé.

    Returns:
        La liste — vide ici — et la raison. Elle est calculée sur les sondes du
        moteur média : un candidat exigeant un GPU sur une machine sans GPU
        n'est pas « peut-être lent », il est inexécutable.
    """
    from ..media.core.capabilities import probe

    gpu = probe("gpu_compute")
    dossier = load_research(path)
    exigeant_gpu = [entree["id"] for entree in dossier["candidates"]
                    if entree.get("vram_gb_min") or entree.get("integration_complexity")
                    in ("HIGH", "MEDIUM")]

    return {
        "gpu_state": gpu["state"],
        "gpu_reason": gpu["reason"],
        "executable": [],
        "requires_gpu": sorted(exigeant_gpu),
        "note": (
            "Aucun candidat n'est exécutable ici : ni GPU, ni `torch`, ni "
            "`transformers`. Toute qualité, latence ou fidélité d'identité "
            "reste donc `NOT_MEASURED` — et le rester est la seule réponse "
            "honnête tant qu'aucun modèle n'a tourné."
        ),
    }


def research_report(path: Optional[str] = None) -> Dict[str, Any]:
    """
    Ce que le dossier de recherche garantit, et ce qu'il refuse.

    Returns:
        Le résumé, la matrice et les règles tenues.
    """
    dossier = load_research(path)
    matrice = license_matrix(path)
    return {
        "researched_on": dossier["researched_on"],
        "candidates": [entree["id"] for entree in dossier["candidates"]],
        "datasets": [entree["id"] for entree in dossier["datasets"]],
        "license_matrix": matrice,
        "execution": executable_here(path),
        "rules": [
            "Une preuve `AUTHORITATIVE` **nomme sa source** ; sans URL lue, "
            "c'est une affirmation.",
            "Un article résumant une licence n'est pas la licence (§67).",
            "`UNKNOWN` porte sa raison : « on ne sait pas » et « on n'a pas "
            "regardé » appellent des actions différentes.",
            "Le droit commercial ne se **déduit** pas : `ALLOWED` exige la "
            "licence du dépôt **et** celle des poids, lues à leur source.",
            "Qualité, latence et cohérence d'identité sont mesurées ou "
            "absentes — jamais recopiées d'un README.",
        ],
        "does_not": [
            "Choisir un fournisseur : c'est une décision d'ADR.",
            "Déduire une permission d'usage d'une licence de dépôt.",
            "Traiter la popularité comme une preuve.",
            "Présenter la revendication d'un projet comme une mesure.",
        ],
    }
