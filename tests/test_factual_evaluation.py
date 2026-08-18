"""
Mesurer une réponse contre ses passages, sans modèle (VOLET 36, ch. C).

Deux mesures existaient et aucune ne disait si une **réponse** est vraie : la
couverture de citations compte les éléments qui portent une source, le taux de
rappel mesure la recherche. Une réponse pouvait afficher 100 % de couverture en
affirmant ce qu'aucun passage cité ne dit.

Le piège de ce chapitre est le contraire du défaut qu'il répare : une mesure
lexicale qui se prendrait pour une mesure de vérité. Ces tests épinglent les
deux — ce qui est réellement mesuré, et ce que le module refuse de conclure.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.factual_evaluation import (  # noqa: E402
    MESURES_INDISPONIBLES,
    TO_SOURCE,
    VERIFIED,
    BenchmarkEntry,
    BenchmarkRefused,
    ClaimVerdict,
    assess_claim,
    benchmark_report,
    citation_correctness,
    evaluate_answer,
    load_benchmark,
    score_entry,
    split_claims,
)

# Un passage tel qu'il sortirait de la base : du texte, rien de plus.
PASSAGE = (
    "La culture du mil dans le bassin arachidier commence avec les premières "
    "pluies de l'hivernage, entre juin et juillet selon les régions."
)


# ----------------------------------------------------------------------
# Les trois cas d'une citation : portée, absente, contredite
# ----------------------------------------------------------------------

def test_une_affirmation_portee_par_le_passage_est_etayee():
    """Le cas nominal : les termes de l'affirmation sont dans le passage."""
    verdict = assess_claim(
        "La culture du mil commence avec les premières pluies de l'hivernage.", [PASSAGE]
    )

    assert verdict.verdict is ClaimVerdict.SUPPORTED
    assert verdict.score >= 0.6


def test_une_affirmation_absente_du_passage_est_comptee_non_etayee():
    """
    Le défaut que le chapitre existe pour mesurer.

    Une réponse peut citer une source impeccable et affirmer à côté. Sans cette
    mesure, la citation suffisait à faire passer l'affirmation.
    """
    verdict = assess_claim(
        "Le rendement moyen atteint quatre tonnes par hectare.", [PASSAGE]
    )

    assert verdict.verdict is ClaimVerdict.UNSUPPORTED


def test_une_affirmation_qui_contredit_son_passage_n_est_jamais_dite_etayee():
    """
    Le cas dangereux, et la raison d'être de la comparaison de polarité.

    Une contradiction partage presque tous ses mots avec le passage qu'elle
    contredit : un score de recouvrement seul la déclarerait étayée à 100 %.
    `DISPUTED` n'est pas non plus `UNSUPPORTED` — « un passage en parle et dit
    le contraire » n'est pas « aucun passage n'en parle ».
    """
    verdict = assess_claim(
        "La culture du mil ne commence pas avec les pluies de l'hivernage.", [PASSAGE]
    )

    assert verdict.verdict is ClaimVerdict.DISPUTED
    assert verdict.verdict is not ClaimVerdict.SUPPORTED


def test_une_affirmation_trop_courte_ne_recoit_pas_de_verdict():
    """Un verdict sur « C'est exact. » serait un chiffre là où il n'y a rien à comparer."""
    assert assess_claim("C'est exact.", [PASSAGE]).verdict is ClaimVerdict.NOT_ASSESSABLE


# ----------------------------------------------------------------------
# Le rapport d'une réponse entière
# ----------------------------------------------------------------------

def test_les_affirmations_non_etayees_sont_comptees_et_nommees():
    """Comptées **et** listées : un chiffre seul n'aide personne à corriger."""
    rapport = evaluate_answer(
        "La culture du mil commence avec les premières pluies de l'hivernage. "
        "Le rendement moyen atteint quatre tonnes par hectare.",
        [PASSAGE],
    )

    assert rapport["claims"] == 2
    assert rapport["supported"] == 1
    assert len(rapport["unsupported"]) == 1
    assert "rendement" in rapport["unsupported"][0]["claim"]


def test_repondre_sans_aucun_passage_est_signale_a_part():
    """
    Le cas où une réponse fluide est le plus trompeuse : aucune source retenue,
    et une réponse quand même. Le taux vide vaut 0, jamais 1 — un sans-faute
    par absence de mesure serait le pire des chiffres.
    """
    rapport = evaluate_answer("Le prix du kilogramme est fixé chaque campagne.", [])

    assert rapport["answered_without_sources"] is True
    assert rapport["support_rate"] == 0.0


def test_le_rapport_nomme_ce_qu_il_ne_sait_pas_mesurer():
    """
    Une mesure lexicale n'est pas une mesure de vérité, et le rapport le porte
    avec lui : justesse factuelle, contradiction entre sources, pertinence
    sémantique.
    """
    rapport = evaluate_answer("La culture du mil commence en juin.", [PASSAGE])

    assert set(rapport["unavailable"]) == set(MESURES_INDISPONIBLES)
    assert "factual_correctness" in rapport["unavailable"]


def test_le_decoupage_en_affirmations_est_approximatif_mais_compte():
    """Une phrase n'est pas une affirmation ; le nombre trouvé reste visible."""
    assert len(split_claims("Une phrase. Une autre ! Une troisième ?")) == 3
    assert split_claims("   ") == []


# ----------------------------------------------------------------------
# Justesse des citations
# ----------------------------------------------------------------------

def test_une_source_citee_qui_ne_porte_pas_l_affirmation_est_une_erreur():
    """
    « Chaque source citée contient-elle ce qu'on lui fait dire » — la question
    que la couverture de citations ne posait pas.
    """
    rapport = citation_correctness({
        "La culture du mil commence avec les premières pluies.": [PASSAGE],
        "Le rendement moyen atteint quatre tonnes par hectare.": [PASSAGE],
    })

    assert rapport["citations"] == 2
    assert rapport["correct"] == 1
    assert rapport["rate"] == 0.5
    assert rapport["errors"][0]["verdict"] == ClaimVerdict.UNSUPPORTED.value


def test_une_citation_qui_dit_le_contraire_est_distinguee_d_une_citation_absente():
    """Citer une source qui vous contredit n'est pas la même faute que citer à côté."""
    rapport = citation_correctness({
        "La culture du mil ne commence pas avec les pluies.": [PASSAGE],
    })

    assert rapport["errors"][0]["verdict"] == ClaimVerdict.DISPUTED.value


# ----------------------------------------------------------------------
# Le jeu de référence : vide, et le disant
# ----------------------------------------------------------------------

def test_le_jeu_de_reference_publie_zero_entree_verifiee():
    """
    L'état vide est l'état honnête.

    Le dépôt ne détient aucun document sénégalais ; le nombre d'entrées
    vérifiées est publié quand même, parce que le cacher ferait croire qu'une
    mesure existe.
    """
    rapport = benchmark_report()

    assert rapport["entries"] > 0, "Le jeu de référence est vide de toute question"
    assert rapport["verified"] == 0
    assert rapport["scorable"] == 0
    assert rapport["to_source"] == rapport["entries"]


def test_aucune_entree_du_depot_ne_porte_de_reponse_ecrite_de_memoire():
    """
    Ce que le fichier ne doit **pas** contenir.

    Une entrée « to_source » nomme la question et le type de source qui la
    trancherait. Si l'une d'elles portait des affirmations attendues, elles
    auraient été écrites de mémoire — et toute mesure future mesurerait cette
    mémoire.
    """
    for entree in load_benchmark():
        assert entree.status == TO_SOURCE
        assert entree.expected_claims == ()
        assert entree.source_type, f"« {entree.question} » ne dit pas qui la trancherait"


def test_l_evaluateur_refuse_de_noter_une_entree_a_sourcer():
    """Le cœur du chapitre : une entrée sans document derrière ne note rien."""
    entree = BenchmarkEntry(
        question="Combien d'habitants compte le Sénégal ?",
        status=TO_SOURCE,
        source_type="ANSD",
    )

    with pytest.raises(BenchmarkRefused):
        score_entry(entree, "Le Sénégal compte des habitants.", [PASSAGE])


def test_une_entree_verifiee_note_ce_que_la_reponse_contient():
    """
    Le jour où un document sénégalais entre dans la base, la notation marche.

    L'entrée est construite ici, pas lue du dépôt : y écrire une entrée
    « vérifiée » pour faire passer un test serait exactement la fabrication que
    ce chapitre refuse.
    """
    entree = BenchmarkEntry(
        question="Quand commence la culture du mil ?",
        status=VERIFIED,
        expected_claims=("La culture du mil commence avec les premières pluies",),
        source="Passage de test, construit dans ce test",
    )

    rapport = score_entry(
        entree,
        "La culture du mil commence avec les premières pluies de l'hivernage.",
        [PASSAGE],
    )

    assert rapport["expected_claims"] == 1
    assert rapport["expected_claims_found"] == 1
    assert rapport["source"] == entree.source
