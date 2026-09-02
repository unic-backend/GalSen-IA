"""
La boucle qui fait vivre la bibliothèque de compétences.

`src/skills/library.py` existait depuis le 2026-08-23 et **rien n'y écrivait**.
Ce qui est éprouvé ici est la boucle qui lui manquait, et surtout sa règle
centrale : **on ne range que ce dont l'exécution a prouvé le fonctionnement.**

Les refus comptent autant que les rangements. Une bibliothèque qui accepte le
code d'une suite rouge le ressortira comme antériorité, et propagera l'erreur
qu'elle était censée éviter.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.skills import BibliothequeCompetences  # noqa: E402
from src.skills.loop import (  # noqa: E402
    _nom_de,
    antecedents,
    ranger_depuis_le_tester,
    ranger_si_prouve,
    rendre_anterioroites,
    resume,
)

#: Assez long pour dépasser `CONTENU_MINIMAL` : un fragment n'est pas une
#: procédure réutilisable.
CODE = (
    "def normaliser_le_texte(texte: str) -> str:\n"
    "    # Retire les espaces superflus et met en minuscules\n"
    "    return ' '.join(texte.lower().split())\n"
)


@pytest.fixture
def depot(tmp_path):
    """Une bibliothèque sur disque jetable, sans fournisseur d'embeddings."""
    return BibliothequeCompetences(chemin=str(tmp_path / "competences.json"))


class TestCeQuiEstRange:
    """La règle centrale : la preuve, ou rien."""

    def test_une_procedure_prouvee_est_rangee(self, depot):
        competence = ranger_si_prouve(
            demande="normaliser un texte",
            contenu=CODE,
            preuve="tester: 3 suite(s) vertes",
            origine="agent:coder",
            bibliotheque=depot,
        )
        assert competence is not None
        assert competence.verifiee is True
        assert depot.compter() == 1

    def test_sans_preuve_rien_n_est_range(self, depot):
        """
        Le refus qui tient tout le reste. Sans lui, la bibliothèque archiverait
        tout ce qu'un modèle produit — le tas que `library.py` refuse d'être.
        """
        assert ranger_si_prouve(
            demande="normaliser un texte", contenu=CODE, preuve="",
            origine="agent:coder", bibliotheque=depot,
        ) is None
        assert depot.compter() == 0

    def test_un_fragment_trop_court_n_est_pas_range(self, depot):
        """Le retrouver ferait perdre du temps : ce n'est pas une procédure."""
        assert ranger_si_prouve(
            demande="x", contenu="return 1", preuve="tester: vert",
            origine="agent:coder", bibliotheque=depot,
        ) is None

    def test_deux_formulations_voisines_ne_creent_qu_une_entree(self, depot):
        """
        Un nom instable ferait grossir la bibliothèque sans qu'elle apprenne
        quoi que ce soit : `ajouter()` remplace par nom.
        """
        for _ in range(2):
            ranger_si_prouve(
                demande="normaliser un texte en python",
                contenu=CODE, preuve="tester: vert",
                origine="agent:coder", bibliotheque=depot,
            )
        assert depot.compter() == 1

    def test_le_nom_ignore_les_mots_vides_et_la_ponctuation(self):
        assert _nom_de("Normaliser  un TEXTE, en Python !") == "normaliser_texte_python"

    def test_une_demande_vide_recoit_un_nom_quand_meme(self):
        """Un nom vide ferait lever `CompetenceRefusee` au lieu de refuser proprement."""
        assert _nom_de("") == "competence_sans_nom"


class TestLeTesterRangeCeQuiAMarche:
    """Le point d'intégration : c'est le `tester` qui détient la preuve."""

    @staticmethod
    def _coder(status: str = "generated", code: str = CODE):
        """Un résultat d'agent `coder`, à la forme réelle."""
        return {
            "request": "normaliser un texte",
            "implementation": {"status": status, "code": code},
        }

    def test_des_suites_vertes_rangent_le_code_du_coder(self, depot):
        competence = ranger_depuis_le_tester(
            resultat_coder=self._coder(),
            verdict={"passed": True, "reason": "tout passe", "suites_executed": 3},
            demande="normaliser un texte",
            bibliotheque=depot,
        )
        assert competence is not None
        assert "3 suite(s) vertes" in competence.preuve
        assert competence.origine == "agent:coder"

    def test_des_suites_rouges_ne_rangent_rien(self, depot):
        """Précisément ce que la bibliothèque ne doit jamais contenir."""
        assert ranger_depuis_le_tester(
            resultat_coder=self._coder(),
            verdict={"passed": False, "reason": "2 échecs", "suites_executed": 3},
            demande="normaliser un texte",
            bibliotheque=depot,
        ) is None
        assert depot.compter() == 0

    def test_un_verdict_vert_sans_execution_ne_prouve_rien(self, depot):
        """
        Le `tester` rend `passed: True` quand il s'exclut lui-même par
        ré-entrance. Accepter ce cas rangerait du code que personne n'a
        éprouvé, sous une preuve qui n'a pas eu lieu.
        """
        assert ranger_depuis_le_tester(
            resultat_coder=self._coder(),
            verdict={"passed": True, "reason": "Tests délégués", "suites_executed": 0},
            demande="normaliser un texte",
            bibliotheque=depot,
        ) is None

    def test_sans_code_genere_il_n_y_a_rien_a_ranger(self, depot):
        assert ranger_depuis_le_tester(
            resultat_coder=self._coder(status="not_generated", code=""),
            verdict={"passed": True, "reason": "vert", "suites_executed": 2},
            demande="normaliser un texte",
            bibliotheque=depot,
        ) is None

    def test_sans_coder_dans_le_tour_rien_ne_se_passe(self, depot):
        assert ranger_depuis_le_tester(
            resultat_coder=None,
            verdict={"passed": True, "reason": "vert", "suites_executed": 2},
            demande="peu importe",
            bibliotheque=depot,
        ) is None


class TestLeCoderRetrouveAvantDEcrire:
    """L'autre moitié : ce qui a servi revient comme antériorité."""

    def test_une_competence_rangee_est_retrouvee(self, depot):
        ranger_si_prouve(
            demande="normaliser un texte en python", contenu=CODE,
            preuve="tester: vert", origine="agent:coder", bibliotheque=depot,
        )
        trouve = antecedents("normaliser du texte python", bibliotheque=depot)
        assert [c["name"] for c in trouve["skills"]] == ["normaliser_texte_python"]

    def test_le_chemin_de_recuperation_est_toujours_dit(self, depot):
        """
        Sans encodeur, le classement est lexical. Un appelant qui l'ignore
        présenterait un classement par mots comme une compréhension du sens.
        """
        ranger_si_prouve(
            demande="normaliser un texte", contenu=CODE, preuve="t",
            origine="agent:coder", bibliotheque=depot,
        )
        assert antecedents("normaliser", bibliotheque=depot)["method"] == "lexical"

    def test_une_bibliotheque_vide_ne_produit_aucun_bloc(self, depot):
        trouve = antecedents("n'importe quoi", bibliotheque=depot)
        assert trouve["skills"] == []
        assert rendre_anterioroites(trouve) == ""

    def test_le_bloc_dit_au_modele_de_relire_avant_de_reutiliser(self, depot):
        """
        Sans cette phrase, une procédure rangée devient une réponse toute faite
        et la bibliothèque propage ses propres erreurs.
        """
        ranger_si_prouve(
            demande="normaliser un texte", contenu=CODE, preuve="tester: vert",
            origine="agent:coder", bibliotheque=depot,
        )
        bloc = rendre_anterioroites(antecedents("normaliser un texte", bibliotheque=depot))
        assert "Read them before writing" in bloc
        assert "Do not copy one because it is here" in bloc
        assert CODE.strip().splitlines()[0] in bloc

    def test_seules_les_competences_prouvees_reviennent(self, depot):
        """
        `antecedents()` ne demande que les vérifiées. Une antériorité non
        prouvée influencerait le code écrit sans que rien ne la soutienne.
        """
        from src.skills import Competence

        depot.ajouter(Competence(
            nom="jamais_eprouvee", description="normaliser un texte",
            contenu=CODE, origine="agent:coder",
        ))
        trouve = antecedents("normaliser un texte", bibliotheque=depot)
        assert trouve["skills"] == []


class TestLaBibliothequeNeBloqueJamais:
    """Une bibliothèque en panne ne doit jamais empêcher le travail."""

    def test_une_bibliotheque_illisible_rend_une_liste_vide(self, tmp_path):
        chemin = tmp_path / "interdit"
        chemin.mkdir()
        # Un répertoire à la place du fichier : toute lecture ou écriture échoue.
        casse = BibliothequeCompetences(chemin=str(chemin))
        trouve = antecedents("peu importe", bibliotheque=casse)
        assert trouve["skills"] == []

    def test_un_rangement_impossible_ne_leve_pas(self, tmp_path):
        chemin = tmp_path / "interdit"
        chemin.mkdir()
        casse = BibliothequeCompetences(chemin=str(chemin))
        assert ranger_si_prouve(
            demande="normaliser un texte", contenu=CODE, preuve="tester: vert",
            origine="agent:coder", bibliotheque=casse,
        ) is None

    def test_le_resume_dit_l_etat(self, depot):
        assert resume(depot)["total"] == 0
        assert resume(depot)["semantique"] is False


class TestLesAgentsSontBranches:
    """
    Le test qui empêche le débranchement silencieux. La boucle a existé une
    session entière sans qu'aucun agent ne l'appelle : c'est exactement ce
    qu'un test d'existence de module ne détecte pas.
    """

    def test_le_coder_consulte_la_bibliotheque(self):
        source = open("agents/coder/agent.py", encoding="utf-8").read()
        assert "antecedents(" in source
        assert "rendre_anterioroites(" in source

    def test_le_tester_range_ce_qui_a_marche(self):
        source = open("agents/tester/agent.py", encoding="utf-8").read()
        assert "ranger_depuis_le_tester(" in source
        assert "skill_recorded" in source
