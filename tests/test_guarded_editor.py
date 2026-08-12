"""
Écrire du code sous portillon (VOLET 31 — ch. 02 et 03, ADR-006).

C'est la capacité la plus dangereuse de la plateforme, donc celle où le défaut
doit être le refus. Le VOLET 01 avait mesuré le risque et l'avait laissé ouvert :
`approval_required` vaut `False` par défaut, donc « le premier agent qui écrira
le fera sans portillon ». `submit_approval()` reste consultatif — il dépose une
demande et rend un identifiant, sans empêcher qui que ce soit d'écrire ensuite.

Ces tests vérifient qu'aucun chemin ne mène à une écriture non approuvée.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.context import AgentContext  # noqa: E402
from src.agent.guarded_editor import (  # noqa: E402
    MAX_OCTETS,
    ApprovalRequired,
    GuardedEditor,
)
from src.agent.repo_map import RepoMap  # noqa: E402


@pytest.fixture
def depot(tmp_path):
    """Un dépôt jouet : un module, son test, et de quoi les faire échouer."""
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "src" / "calcul.py").write_text(
        "def additionner(a, b):\n    return a + b\n", encoding="utf-8"
    )
    (tmp_path / "tests" / "test_calcul.py").write_text(
        "import sys, os\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))\n"
        "from src.calcul import additionner\n\n"
        "def test_addition():\n    assert additionner(2, 2) == 4\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture
def editeur(depot):
    """Éditeur branché sur un contexte réel, avec son moteur d'approbation."""
    contexte = AgentContext(request="corriger le calcul", agent_id="coder")
    return GuardedEditor(contexte, root=str(depot)), contexte


def _approuver(contexte, demande: str) -> None:
    """Joue la décision humaine."""
    contexte.approval.approve(demande, reason="revu", decided_by="operateur")


# ----------------------------------------------------------------------
# Rien ne s'écrit sans approbation
# ----------------------------------------------------------------------

def test_proposer_n_ecrit_rien(editeur, depot):
    """Une proposition est une demande, pas une écriture."""
    editeur_, _ = editeur
    avant = (depot / "src" / "calcul.py").read_text(encoding="utf-8")

    resultat = editeur_.propose("src/calcul.py", "def additionner(a, b):\n    return 0\n", "essai")

    assert resultat.status == "pending_approval"
    assert resultat.approval_request_id
    assert (depot / "src" / "calcul.py").read_text(encoding="utf-8") == avant


def test_appliquer_sans_approbation_leve(editeur):
    """
    Le cœur du chapitre.

    Appliquer sans décision humaine est la faute que ce module existe pour
    rendre impossible : elle lève, elle n'échoue pas en silence.
    """
    editeur_, _ = editeur
    demande = editeur_.propose("src/calcul.py", "x = 1\n", "essai").approval_request_id

    with pytest.raises(ApprovalRequired, match="approved"):
        editeur_.apply(demande)


def test_une_demande_inconnue_est_refusee(editeur):
    """On ne peut pas appliquer une modification qui n'a jamais été proposée."""
    editeur_, _ = editeur

    with pytest.raises(ApprovalRequired):
        editeur_.apply("req_inexistant")


def test_une_modification_approuvee_est_ecrite(editeur, depot):
    """Le contre-test : le portillon ne doit pas bloquer ce qui est accordé."""
    editeur_, contexte = editeur
    nouveau = "def additionner(a, b):\n    return a + b\n\n\ndef doubler(x):\n    return x * 2\n"
    demande = editeur_.propose("src/calcul.py", nouveau, "ajoute doubler").approval_request_id

    _approuver(contexte, demande)
    resultat = editeur_.apply(demande)

    assert resultat.status == "applied"
    assert resultat.tests_passed is True
    assert "doubler" in (depot / "src" / "calcul.py").read_text(encoding="utf-8")


def test_sans_moteur_d_approbation_rien_ne_s_ecrit(depot, monkeypatch):
    """
    Ailleurs un moteur absent dégrade proprement ; ici il **ferme**.

    Un portillon qu'on peut faire disparaître en éteignant un service n'est pas
    un portillon.
    """
    contexte = AgentContext(request="x", agent_id="coder")
    monkeypatch.setattr(type(contexte), "approval", property(lambda self: None))

    resultat = GuardedEditor(contexte, root=str(depot)).propose("src/calcul.py", "x = 1\n", "essai")

    assert resultat.status == "refused"
    assert "approbation" in resultat.detail.lower()


# ----------------------------------------------------------------------
# Ce qu'aucune approbation ne permet
# ----------------------------------------------------------------------

def test_ecrire_hors_du_depot_est_refuse(editeur):
    """Une approbation ne donne pas accès à la machine."""
    editeur_, _ = editeur

    resultat = editeur_.propose("../../etc/passwd", "compromis", "essai")

    assert resultat.status == "refused"
    assert "sort du dépôt" in resultat.detail


@pytest.mark.parametrize("chemin", [".env", "config/secrets.yaml", "data/memory.sqlite", ".git/config"])
def test_les_fichiers_proteges_restent_hors_de_portee(editeur, chemin):
    """Ces fichiers ne peuvent pas être une intention légitime d'un agent."""
    editeur_, _ = editeur

    resultat = editeur_.propose(chemin, "peu importe", "essai")

    assert resultat.status == "refused"
    assert "protégé" in resultat.detail


def test_une_raison_est_exigee(editeur):
    """Un humain doit pouvoir décider sans lire le diff entier."""
    editeur_, _ = editeur

    assert editeur_.propose("src/calcul.py", "x = 1\n", "   ").status == "refused"


def test_une_reecriture_massive_est_refusee(editeur):
    """Au-delà d'une certaine taille, ce n'est plus une correction ciblée."""
    editeur_, _ = editeur

    resultat = editeur_.propose("src/calcul.py", "x = 1\n" * (MAX_OCTETS // 2), "gros")

    assert resultat.status == "refused"
    assert "trop grande" in resultat.detail


# ----------------------------------------------------------------------
# Une modification qui casse ses tests est annulée
# ----------------------------------------------------------------------

def test_une_modification_qui_casse_les_tests_est_annulee(editeur, depot):
    """Laisser un dépôt cassé serait pire que refuser la modification."""
    editeur_, contexte = editeur
    avant = (depot / "src" / "calcul.py").read_text(encoding="utf-8")

    demande = editeur_.propose(
        "src/calcul.py", "def additionner(a, b):\n    return 0\n", "casse tout"
    ).approval_request_id
    _approuver(contexte, demande)
    resultat = editeur_.apply(demande)

    assert resultat.status == "reverted"
    assert resultat.tests_passed is False
    assert resultat.output, "L'agent doit recevoir la sortie réelle de l'échec"
    assert (depot / "src" / "calcul.py").read_text(encoding="utf-8") == avant


def test_un_fichier_sans_test_est_ecrit_mais_annonce_non_verifie(editeur, depot):
    """
    Appliquer sans pouvoir vérifier doit se dire.

    Un « appliqué » silencieux laisserait croire que la modification est bonne.
    """
    editeur_, contexte = editeur
    demande = editeur_.propose("src/sans_test.py", "VALEUR = 1\n", "nouveau module").approval_request_id
    _approuver(contexte, demande)

    resultat = editeur_.apply(demande)

    assert resultat.status == "applied"
    assert resultat.tests_passed is None
    assert "non vérifié" in resultat.detail


# ----------------------------------------------------------------------
# La boucle éditer → tester → corriger
# ----------------------------------------------------------------------

def test_la_boucle_ne_s_auto_approuve_jamais(editeur):
    """Sans décision humaine, la boucle s'arrête — elle ne se donne pas le droit."""
    editeur_, _ = editeur

    rapport = editeur_.edit_test_fix(
        "src/calcul.py", lambda echec: "x = 1\n", "essai",
    )

    assert rapport.succeeded is False
    assert "humaine" in rapport.detail


def test_la_boucle_corrige_avec_le_retour_de_l_echec(editeur, depot):
    """
    Le déroulé complet : une première tentative casse, la seconde répare.

    La boucle ne fabrique aucun code — c'est `proposer` qui le produit, et c'est
    là qu'un modèle interviendra quand il y en aura un.
    """
    editeur_, contexte = editeur
    tentatives = {"n": 0}

    def proposer(echec_precedent):
        tentatives["n"] += 1
        if tentatives["n"] == 1:
            return "def additionner(a, b):\n    return 0\n"
        # Le second essai voit l'échec du premier.
        assert echec_precedent, "La correction doit recevoir le retour de l'échec"
        return "def additionner(a, b):\n    return a + b\n"

    rapport = editeur_.edit_test_fix(
        "src/calcul.py", proposer, "corrige l'addition",
        approuver=lambda demande: bool(_approuver(contexte, demande) or True),
    )

    assert rapport.succeeded is True
    assert tentatives["n"] == 2
    assert "additionner(2, 2)" not in rapport.detail  # le détail parle, il ne recopie pas


def test_la_boucle_est_bornee(editeur, depot):
    """Sans borne, un agent qui ne sait pas réparer consomme toute la requête."""
    editeur_, contexte = editeur
    essais = {"n": 0}

    def proposer(_echec):
        essais["n"] += 1
        return "def additionner(a, b):\n    return 0\n"

    rapport = editeur_.edit_test_fix(
        "src/calcul.py", proposer, "ne répare jamais",
        approuver=lambda demande: bool(_approuver(contexte, demande) or True),
        max_tentatives=2,
    )

    assert rapport.succeeded is False
    assert essais["n"] == 2
    # Et le dépôt est intact : chaque tentative ratée a été annulée.
    assert "a + b" in (depot / "src" / "calcul.py").read_text(encoding="utf-8")


# ----------------------------------------------------------------------
# La carte du dépôt
# ----------------------------------------------------------------------

def test_la_carte_relie_un_module_a_son_test(depot):
    """Une modification sans son test est une modification invérifiable."""
    carte = RepoMap(str(depot)).build(["src"])

    assert carte.tests_for("src/calcul.py") == "tests/test_calcul.py"


def test_la_carte_trouve_ou_regarder(depot):
    """Un agent doit viser un fichier sans lire le dépôt entier."""
    carte = RepoMap(str(depot)).build(["src"])

    trouves = [entree.path for entree in carte.find("additionner")]

    assert "src/calcul.py" in trouves


def test_la_carte_mesure_ce_qui_n_est_pas_couvert(depot):
    """
    Le taux de fichiers sans test nommé est la mesure la plus utile de la carte :
    c'est là qu'une modification ne peut pas être vérifiée.
    """
    (depot / "src" / "orphelin.py").write_text("VALEUR = 1\n", encoding="utf-8")

    resume = RepoMap(str(depot)).build(["src"]).summary()

    assert resume["files"] == 2
    assert resume["with_named_test"] == 1
    assert resume["coverage_by_convention"] == 0.5


# ----------------------------------------------------------------------
# Le graphe d'imports choisit les suites (VOLET 34, ch. 10)
# ----------------------------------------------------------------------

def _depot_avec_dependance(depot):
    """Ajoute un module qu'aucun test ne nomme, mais que la chaîne d'imports atteint."""
    (depot / "src" / "noyau.py").write_text(
        "def doubler(valeur):\n    return valeur * 2\n", encoding="utf-8"
    )
    (depot / "src" / "calcul.py").write_text(
        "from src.noyau import doubler\n\n\n"
        "def additionner(a, b):\n    return doubler(a + b) // 2\n",
        encoding="utf-8",
    )
    return depot


def test_un_fichier_sans_test_nomme_est_quand_meme_verifie(editeur, depot):
    """
    Le gain mesurable du chapitre 10.

    Aucun fichier ne s'appelle `test_noyau.py` : la convention de nom rendait
    « appliqué mais **non vérifié** », et la modification restait en place. Le
    graphe voit que `tests/test_calcul.py` atteint `src/noyau.py` par la chaîne
    d'imports, lance ce test, et **annule** parce qu'il échoue.
    """
    _depot_avec_dependance(depot)
    editeur_, contexte = editeur
    assert RepoMap(str(depot)).build(["src"]).tests_for("src/noyau.py") is None

    resultat = editeur_.propose(
        "src/noyau.py", "def doubler(valeur):\n    return valeur * 3\n", "casser"
    )
    _approuver(contexte, resultat.approval_request_id)
    applique = editeur_.apply(resultat.approval_request_id)

    assert applique.tests_run == "tests/test_calcul.py"
    assert applique.status == "reverted"
    assert "valeur * 2" in (depot / "src" / "noyau.py").read_text(encoding="utf-8")


def test_les_suites_lancees_sont_plafonnees(editeur, depot):
    """
    Un fichier central est importé par des dizaines de tests ; les lancer tous
    reviendrait à passer la suite complète à chaque édition.
    """
    _depot_avec_dependance(depot)
    for numero in range(5):
        (depot / "tests" / f"test_appel_{numero}.py").write_text(
            "import sys, os\n"
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))\n"
            "from src.noyau import doubler\n\n"
            "def test_double():\n    assert doubler(2) == 4\n",
            encoding="utf-8",
        )
    editeur_, _ = editeur

    suites = editeur_._tests_de("src/noyau.py")

    assert len(suites) == 3
    assert all(suite.startswith("tests/") for suite in suites)
