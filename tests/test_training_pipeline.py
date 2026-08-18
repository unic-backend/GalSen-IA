"""
Ce qu'il faut avant d'entraîner SamP et ToP (VOLET 33).

Le brief demandait de l'entraînement distribué et du RLHF. La mesure a renversé
l'ordre : en QLoRA un modèle de 7–8 milliards de paramètres tient sur un seul
GPU, et n'a besoin d'aucune distribution. Les vrais obstacles sont l'absence de
données, l'absence de mesure, et le signal que personne ne capture — le seul dont
le coût augmente chaque jour, parce qu'une correction non enregistrée est perdue.

Ces tests portent sur les trois choses vérifiables sans GPU : la capture, la
mesure et la lignée.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.training.evaluation import (  # noqa: E402
    EvalCase,
    EvalResult,
    compare,
    evaluate_retrieval,
    load_cases,
)
from src.training.feedback import (  # noqa: E402
    Feedback,
    FeedbackKind,
    SQLiteFeedbackStore,
    scrub,
)
from src.training.lineage import LineageRegistry, ModelVersion  # noqa: E402


@pytest.fixture
def magasin(tmp_path):
    """Magasin de retours isolé."""
    return SQLiteFeedbackStore(str(tmp_path / "feedback.sqlite"))


# ----------------------------------------------------------------------
# Capture du signal
# ----------------------------------------------------------------------

def test_une_correction_est_conservee(magasin):
    """Le signal qui vaut le plus : l'utilisateur a réécrit la réponse."""
    identifiant = magasin.record(Feedback(
        prompt="Quand semer le mil ?", response="En décembre.",
        kind=FeedbackKind.CORRECTION, correction="À l'arrivée des pluies.",
        consent_to_train=True, subject="moussa",
    ))

    retours = magasin.list_feedback()
    assert len(retours) == 1
    assert retours[0].id == identifiant
    assert retours[0].correction == "À l'arrivée des pluies."


def test_les_donnees_personnelles_sont_retirees_a_l_ecriture(magasin):
    """
    Filtrer à l'export voudrait dire que le numéro a été écrit sur le disque,
    sauvegardé, et copié hors site.
    """
    magasin.record(Feedback(
        prompt="Mon numéro est 77 123 45 67 et mon mail awa@exemple.sn",
        response="Noté.", consent_to_train=True,
    ))

    conserve = magasin.list_feedback()[0].prompt

    assert "77 123 45 67" not in conserve
    assert "awa@exemple.sn" not in conserve
    assert "[téléphone]" in conserve and "[courriel]" in conserve


def test_le_nettoyage_ne_detruit_pas_le_texte_utile():
    """Un filtre trop large rendrait la correction inutilisable."""
    texte = scrub("Le mil se sème à l'arrivée des pluies, vers juin.")

    assert texte == "Le mil se sème à l'arrivée des pluies, vers juin."


def test_sans_consentement_le_retour_reste_hors_du_jeu(magasin):
    """Un retour appartient à qui l'a écrit (ADR-010)."""
    magasin.record(Feedback(prompt="q1", response="r1", consent_to_train=False))
    magasin.record(Feedback(prompt="q2", response="r2", consent_to_train=True))

    assert len(magasin.list_feedback()) == 2
    assert len(magasin.list_feedback(consent_only=True)) == 1


def test_l_export_exige_une_approbation(magasin):
    """
    Sortir le texte de vraies personnes vers un jeu de données est une décision
    humaine (ADR-006), pas un effet de bord.
    """
    magasin.record(Feedback(
        prompt="q", response="mauvaise", correction="bonne", consent_to_train=True,
    ))

    with pytest.raises(PermissionError, match="approbation"):
        magasin.export_pairs()

    paires = magasin.export_pairs(approval_request_id="req_accorde")
    assert paires == [{"prompt": "q", "chosen": "bonne", "rejected": "mauvaise"}]


def test_un_retour_sans_deux_cotes_ne_fait_pas_une_paire(magasin):
    """Sans réponse rejetée, il n'y a pas de préférence — seulement une réponse."""
    magasin.record(Feedback(
        prompt="q", response="r", kind=FeedbackKind.RATING, rating=5, consent_to_train=True,
    ))

    assert magasin.export_pairs(approval_request_id="req") == []


def test_le_compte_utile_est_distingue_du_total(magasin):
    """
    Un total qui mélange consentis et non consentis ferait croire à un jeu de
    données qui n'existe pas.
    """
    magasin.record(Feedback(prompt="a", response="b", consent_to_train=False))
    magasin.record(Feedback(prompt="c", response="d", consent_to_train=True))
    magasin.record(Feedback(
        prompt="e", response="f", correction="g", consent_to_train=True,
    ))

    etat = magasin.stats()

    assert etat["total"] == 3
    assert etat["with_consent"] == 2
    assert etat["trainable_pairs"] == 1


# ----------------------------------------------------------------------
# Mesurer avant d'entraîner
# ----------------------------------------------------------------------

def test_le_jeu_d_evaluation_du_depot_est_lisible():
    """Le jeu par défaut porte sur la documentation, vérifiable ligne à ligne."""
    cas = load_cases()

    assert len(cas) >= 10
    assert all(element.expected_source for element in cas)


def test_le_taux_de_recuperation_se_mesure_sans_jugement_humain():
    """
    La propriété qui rend cette mesure utilisable aujourd'hui : le passage
    attendu est retrouvé, ou il ne l'est pas. Aucun humain, aucun modèle.
    """
    cas = [
        EvalCase(question="q1", expected_source="a.md"),
        EvalCase(question="q2", expected_source="b.md"),
    ]

    resultat = evaluate_retrieval(
        lambda question: [{"location": "a.md"}] if question == "q1" else [{"location": "z.md"}],
        cases=cas, method="factice",
    )

    assert resultat.cases == 2
    assert resultat.hit_rate == 0.5
    assert resultat.misses[0]["expected"] == "b.md"


def test_un_jeu_vide_ne_vaut_pas_un_sans_faute():
    """Zéro sur zéro n'est pas 100 % — ce serait le pire des faux positifs."""
    assert evaluate_retrieval(lambda q: [], cases=[]).hit_rate == 0.0


def test_une_recherche_qui_leve_compte_comme_un_echec():
    """Une panne ne doit pas disparaître de la mesure."""
    resultat = evaluate_retrieval(
        lambda question: (_ for _ in ()).throw(RuntimeError("indisponible")),
        cases=[EvalCase(question="q", expected_source="a.md")],
    )

    assert resultat.hit_rate == 0.0
    assert "indisponible" in resultat.misses[0]["error"]


def test_une_regression_par_langue_annule_le_gain_global():
    """
    Un modèle qui progresse en français en régressant en wolof n'a pas progressé
    pour ce projet. Une moyenne le cacherait.
    """
    avant = EvalResult(cases=20, hits=10, by_language={
        "fr": {"cases": 10, "hits": 4}, "wo": {"cases": 10, "hits": 6},
    })
    apres = EvalResult(cases=20, hits=12, by_language={
        "fr": {"cases": 10, "hits": 9}, "wo": {"cases": 10, "hits": 3},
    })

    verdict = compare(avant, apres)

    assert verdict["delta"] > 0
    assert verdict["regressions"] == ["wo"]
    assert verdict["keep"] is False


def test_un_gain_sans_regression_est_gardable():
    """Le contre-test : la règle ne doit pas tout refuser."""
    avant = EvalResult(cases=10, hits=4, by_language={"fr": {"cases": 10, "hits": 4}})
    apres = EvalResult(cases=10, hits=7, by_language={"fr": {"cases": 10, "hits": 7}})

    assert compare(avant, apres)["keep"] is True


# ----------------------------------------------------------------------
# Lignée
# ----------------------------------------------------------------------

def test_une_version_est_inscrite_avec_sa_base_et_sa_licence(tmp_path):
    """Le jour où SamP dit une bêtise, la question sera « il a appris quoi ? »."""
    registre = LineageRegistry(str(tmp_path / "lineage.jsonl"))
    registre.record(ModelVersion(
        name="samp-1", family="samp", base_model="qwen2.5-7b",
        base_license="apache-2.0", data_hash="abc123",
        metrics={"hit_rate": 0.62}, kept=True,
    ))

    versions = registre.versions("samp")

    assert len(versions) == 1
    assert versions[0].base_model == "qwen2.5-7b"


def test_une_licence_non_permissive_empeche_la_publication(tmp_path):
    """
    ADR-014 écarte Llama parce que sa licence impose de porter « Llama » dans le
    nom. Ne pas noter la licence, c'est le découvrir le jour de la publication.
    """
    version = ModelVersion(
        name="samp-1", family="samp", base_model="llama-3-8b",
        base_license="llama-3-community", data_hash="abc", metrics={"hit_rate": 0.7},
    )

    problemes = version.issues()

    assert any("licence" in probleme for probleme in problemes)
    assert version.license_is_permissive() is False


def test_une_version_non_mesuree_est_signalee(tmp_path):
    """Un modèle non évalué ne peut pas être gardé pour une bonne raison."""
    version = ModelVersion(
        name="top-1", family="top", base_model="qwen2.5-coder-7b",
        base_license="apache-2.0", data_hash="def",
    )

    assert any("aucune mesure" in probleme for probleme in version.issues())


def test_un_entrainement_rate_reste_au_journal(tmp_path):
    """
    Un journal qui ne contient que des succès n'est pas un journal : l'essai
    raté serait refait.
    """
    registre = LineageRegistry(str(tmp_path / "lineage.jsonl"))
    registre.record(ModelVersion(
        name="samp-0", family="samp", base_model="qwen2.5-7b",
        base_license="apache-2.0", data_hash="a", metrics={"hit_rate": 0.3},
        kept=False, notes="pire que la base",
    ))
    registre.record(ModelVersion(
        name="samp-1", family="samp", base_model="qwen2.5-7b",
        base_license="apache-2.0", data_hash="b", metrics={"hit_rate": 0.62}, kept=True,
    ))

    assert len(registre.versions("samp")) == 2
    # Mais la version courante est la dernière **gardée**, jamais la dernière écrite.
    assert registre.latest("samp").name == "samp-1"


def test_sans_version_gardee_il_n_y_a_pas_de_version_courante(tmp_path):
    """Rendre un modèle rejeté comme courant serait le servir par accident."""
    registre = LineageRegistry(str(tmp_path / "lineage.jsonl"))
    registre.record(ModelVersion(
        name="samp-0", family="samp", base_model="q", base_license="apache-2.0",
        metrics={"hit_rate": 0.1}, kept=False,
    ))

    assert registre.latest("samp") is None


def test_mesurer_ne_deplace_pas_ce_qu_on_mesure(monkeypatch):
    """
    Chercher incrémente le compteur de consultations, qui alimente le critère de
    popularité du classement : une même base mesurée deux fois ne rendait pas le
    même score. Constaté sur le corpus du dépôt — 0,4 sur une base neuve, 0,5
    après quelques passages, sans qu'une ligne de code ait changé.

    Un barème qui dérive à l'usage ne peut arbitrer aucun entraînement.
    """
    from src.knowledge_engine.knowledge_manager import TRACK_ACCESS_VARIABLE

    monkeypatch.setenv(TRACK_ACCESS_VARIABLE, "true")
    vu = []

    def rechercher(question):
        vu.append(os.environ.get(TRACK_ACCESS_VARIABLE))
        return [{"location": "a.md"}]

    evaluate_retrieval(rechercher, cases=[EvalCase(question="q", expected_source="a.md")])

    assert vu == ["false"], "Le compteur doit être coupé pendant la mesure"
    # Et l'environnement est rendu tel qu'il était : une mesure ne reconfigure
    # pas la plateforme derrière elle.
    assert os.environ[TRACK_ACCESS_VARIABLE] == "true"
