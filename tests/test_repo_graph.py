"""
Le graphe d'imports et l'index des symboles (VOLET 34, ch. 10).

Deux moitiés, comme le chapitre :

1. **`RepoGraph`** — qui importe quoi, et donc qui casse si je change ceci.
2. **`SymbolIndex`** — où un nom est défini, et qui s'en sert.

Les tests structurels tournent sur un **dépôt jouet** construit dans un
répertoire temporaire : y affirmer « `a.py` importe `b.py` » est vérifiable,
alors que la même affirmation sur le vrai dépôt deviendrait fausse au prochain
import déplacé. Une poignée de tests portent quand même sur le dépôt réel — ceux
dont la valeur *est* qu'ils cassent quand le dépôt change (aucun cycle bloquant,
par exemple).
"""

import os
import sys
import textwrap

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.repo_graph import RepoGraph  # noqa: E402
from src.agent.symbol_index import SymbolIndex  # noqa: E402


# ----------------------------------------------------------------------
# Dépôt jouet
# ----------------------------------------------------------------------

FICHIERS = {
    "src/__init__.py": "",
    "src/base.py": textwrap.dedent(
        '''
        """Socle dont tout le reste dépend."""

        VALEUR = 1


        class Socle:
            """Une base."""

            def calculer(self, entree, facteur=2):
                """Calcule."""
                return entree * facteur

            def _interne(self):
                """Détail."""
                return None


        def aider(quoi, *args, **kwargs):
            """Aide."""
            return quoi
        '''
    ),
    "src/service.py": textwrap.dedent(
        '''
        """Service bâti sur le socle."""

        import json

        from .base import Socle, aider


        class Service:
            """Un service."""

            def servir(self, requete):
                """Sert."""
                return json.dumps(aider(Socle().calculer(requete)))
        '''
    ),
    "src/api.py": textwrap.dedent(
        '''
        """Façade publique."""

        from src.service import Service


        def point_entree(requete):
            """Point d'entrée."""
            return Service().servir(requete)
        '''
    ),
    "src/solitaire.py": textwrap.dedent(
        '''
        """Personne ne l'importe."""

        def seul():
            """Seul."""
            return 0
        '''
    ),
    "src/boucle_a.py": textwrap.dedent(
        '''
        """Moitié d'un cycle différé."""

        def utiliser():
            """Import différé, dans le corps."""
            from src.boucle_b import autre
            return autre()
        '''
    ),
    "src/boucle_b.py": textwrap.dedent(
        '''
        """Moitié d'un cycle, au chargement."""

        from src.boucle_a import utiliser


        def autre():
            """Autre."""
            return utiliser
        '''
    ),
    "tests/test_api.py": textwrap.dedent(
        '''
        """Test qui importe la façade."""

        from src.api import point_entree


        def test_point_entree():
            assert point_entree(2)
        '''
    ),
}


@pytest.fixture
def depot(tmp_path):
    """Écrit le dépôt jouet et retourne sa racine."""
    for chemin, contenu in FICHIERS.items():
        cible = tmp_path / chemin
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(contenu, encoding="utf-8")
    return str(tmp_path)


@pytest.fixture
def graphe(depot):
    """Graphe construit sur le dépôt jouet."""
    return RepoGraph(root=depot, packages=("src",)).build()


@pytest.fixture
def index(depot):
    """Index construit sur le dépôt jouet."""
    return SymbolIndex(root=depot, packages=("src",)).build()


# ----------------------------------------------------------------------
# 1. Le graphe d'imports
# ----------------------------------------------------------------------


def test_un_import_relatif_est_resolu(graphe):
    """`from .base import Socle` dans `src/service.py` désigne `src/base.py`."""
    assert graphe.imports_of("src/service.py") == ["src/base.py"]


def test_un_import_absolu_est_resolu(graphe):
    """`from src.service import Service` désigne le fichier, pas un symbole."""
    assert graphe.imports_of("src/api.py") == ["src/service.py"]


def test_un_paquet_etranger_n_entre_pas_dans_le_graphe(graphe):
    """`json` n'est pas un fichier du dépôt : il sort, en étant nommé."""
    assert "json" in graphe.external_imports("src/service.py")
    assert all("json" not in cible for cible in graphe.imports_of("src/service.py"))


def test_imported_by_est_l_inverse_d_imports_of(graphe):
    assert graphe.imported_by("src/base.py") == ["src/service.py"]


def test_l_impact_est_transitif(graphe):
    """
    Le cœur du chapitre : `base.py` n'est importé que par `service.py`, mais le
    modifier touche aussi `api.py` et le test. C'est ce qu'un `grep` sur le nom
    du fichier ne dit pas.
    """
    assert graphe.impact_of("src/base.py") == [
        "src/api.py", "src/service.py", "tests/test_api.py",
    ]


def test_l_impact_exclut_le_fichier_lui_meme(graphe):
    assert "src/base.py" not in graphe.impact_of("src/base.py")


def test_l_impact_peut_etre_borne_en_profondeur(graphe):
    """Le voisinage direct suffit parfois, et coûte moins à lire."""
    assert graphe.impact_of("src/base.py", depth=1) == ["src/service.py"]


def test_un_fichier_que_personne_n_importe_n_a_aucun_impact(graphe):
    assert graphe.impact_of("src/solitaire.py") == []


def test_les_tests_a_relancer_viennent_des_imports_pas_des_noms(graphe):
    """
    Aucun fichier ne s'appelle `test_base.py`, et pourtant `tests/test_api.py`
    couvre `src/base.py` — par la chaîne d'imports. C'est précisément ce que la
    convention de nom ratait pour 241 fichiers sur 308.
    """
    assert graphe.tests_to_run("src/base.py") == ["tests/test_api.py"]


def test_un_fichier_hors_de_portee_des_tests_est_signale(graphe):
    """Le cas où une modification passe inaperçue jusqu'à la production."""
    description = graphe.describe("src/solitaire.py")
    assert description["tests_to_run"] == []
    assert description["untested"] is True


def test_describe_dit_si_le_fichier_est_connu(graphe):
    """Un chemin inconnu rend une description vide, pas une exception."""
    description = graphe.describe("src/inexistant.py")
    assert description["known"] is False
    assert description["imports"] == []


def test_un_cycle_est_detecte(graphe):
    """`boucle_a` et `boucle_b` s'importent mutuellement."""
    cycles = graphe.cycles()
    assert ["src/boucle_a.py", "src/boucle_b.py"] in cycles


def test_un_cycle_differe_n_est_pas_un_cycle_bloquant(graphe):
    """
    La distinction qui compte : `boucle_a` importe `boucle_b` **dans une
    fonction**. Le cycle existe, mais rien ne casse au chargement. Les confondre
    ferait signaler une panne qui n'a pas lieu.
    """
    assert graphe.cycles(blocking=True) == []


def test_un_import_differe_reste_une_dependance(graphe):
    """Différé ne veut pas dire absent : le rayon d'impact doit le contenir."""
    assert "src/boucle_b.py" in graphe.imports_of("src/boucle_a.py")


def test_le_resume_compte_le_code_et_les_tests_separement(graphe):
    resume = graphe.summary()
    assert resume["code_files"] == 7
    assert resume["files"] == 8
    assert resume["blocking_cycles"] == 0


def test_un_fichier_illisible_ne_vide_pas_le_graphe(depot):
    """Une erreur de syntaxe sort un fichier du graphe, sans emporter le reste."""
    with open(os.path.join(depot, "src", "casse.py"), "w", encoding="utf-8") as fichier:
        fichier.write("def ( pas du python\n")
    construit = RepoGraph(root=depot, packages=("src",)).build()
    assert construit.imports_of("src/casse.py") == []
    assert construit.imports_of("src/service.py") == ["src/base.py"]


# ----------------------------------------------------------------------
# 2. L'index des symboles
# ----------------------------------------------------------------------


def test_les_methodes_sont_indexees(index):
    """
    Ce que `RepoMap` ne donnait pas : il n'indexe que le premier niveau. Un
    agent qui doit changer `calculer()` cherche `calculer`, pas `Socle`.
    """
    definitions = index.definitions("calculer")
    assert len(definitions) == 1
    assert definitions[0].qualified == "Socle.calculer"
    assert definitions[0].kind == "method"


def test_un_symbole_porte_son_emplacement(index):
    """Un symbole sans sa ligne oblige à relire le fichier pour le trouver."""
    definition = index.definitions("Socle")[0]
    assert definition.location() == "src/base.py:7"


def test_la_signature_retenue_est_l_ordre_des_parametres(index):
    """C'est cela qu'un changement casse chez les appelants."""
    assert index.definitions("calculer")[0].signature == "(self, entree, facteur)"
    assert index.definitions("aider")[0].signature == "(quoi, *args, **kwargs)"


def test_un_nom_qualifie_peut_etre_cherche_directement(index):
    assert index.definitions("Socle.calculer")[0].path == "src/base.py"


def test_les_appelants_sont_retrouves(index):
    """La règle « vérifie qui appelle avant de changer » devient une requête."""
    assert index.callers("calculer") == ["src/service.py"]


def test_l_impact_d_un_renommage_reunit_appelants_et_tests(index):
    """Les tests viennent du graphe d'imports, pas d'une convention de nom."""
    impact = index.rename_impact("calculer")
    assert impact["defined_in"] == ["src/base.py:10"]
    assert impact["callers"] == ["src/service.py"]
    assert impact["tests_to_run"] == ["tests/test_api.py"]
    assert impact["ambiguous"] is False
    assert impact["known"] is True


def test_un_nom_inconnu_est_dit_inconnu_et_non_sans_appelant(index):
    """
    « Aucune définition » et « aucun appelant » sont deux réponses différentes :
    conclure « rien à faire » sur une recherche qui a cherché au mauvais endroit
    est exactement l'erreur que l'index doit empêcher.
    """
    impact = index.rename_impact("nom_qui_n_existe_pas")
    assert impact["known"] is False
    assert impact["defined_in"] == []


def test_les_symboles_d_un_fichier_sont_rendus_avec_leurs_methodes(index):
    noms = {symbole.qualified for symbole in index.symbols_in("src/base.py")}
    assert noms == {"Socle", "Socle.calculer", "Socle._interne", "aider"}


def test_un_symbole_public_que_personne_n_utilise_est_une_piste(index):
    """
    `unused()` est une piste, jamais une preuve : un point d'entrée d'API ou un
    rappel chargé par son nom n'a aucun appelant visible et vit pourtant.
    """
    inutilises = {symbole.name for symbole in index.unused()}
    assert "seul" in inutilises
    assert "calculer" not in inutilises


def test_les_attributs_comptent_comme_usage_et_le_compromis_est_assume(index):
    """
    Rien ici ne sait ce qu'est `objet` dans `objet.calculer()` : l'usage est donc
    compté pour **tout** `calculer` du dépôt. Le sur-ensemble est délibéré —
    rater un appelant est ce que la règle de vérification cherche à empêcher, et
    ce test épingle le choix pour qu'il ne soit pas inversé par mégarde.
    """
    assert index.callers("calculer") == ["src/service.py"]


def test_le_resume_separe_classes_fonctions_et_methodes(index):
    resume = index.summary()
    assert resume["classes"] == 2
    assert resume["methods"] == 3
    assert resume["functions"] >= 4


def test_l_index_reutilise_le_graphe_qu_on_lui_donne(depot):
    """Les deux parcourent les mêmes fichiers : les relire deux fois ne sert à rien."""
    partage = RepoGraph(root=depot, packages=("src",)).build()
    construit = SymbolIndex(root=depot, packages=("src",), graph=partage).build()
    assert construit.rename_impact("calculer")["tests_to_run"] == ["tests/test_api.py"]


# ----------------------------------------------------------------------
# 3. Sur le vrai dépôt — les faits dont l'intérêt est de casser
# ----------------------------------------------------------------------


@pytest.fixture(scope="module")
def graphe_reel():
    """Graphe du dépôt lui-même, construit une seule fois."""
    return RepoGraph().build()


def test_le_depot_n_a_aucun_cycle_d_import_bloquant(graphe_reel):
    """
    Un cycle formé d'imports exécutés au chargement lève `ImportError` au premier
    des deux modules importé. Il y en a zéro aujourd'hui ; ce test le maintient.
    """
    bloquants = graphe_reel.cycles(blocking=True)
    assert bloquants == [], f"Cycles d'imports bloquants : {bloquants}"


def test_le_graphe_couvre_le_depot_reel(graphe_reel):
    """Un graphe qui ne trouve presque rien passerait tous les tests jouets."""
    resume = graphe_reel.summary()
    assert resume["code_files"] > 250
    assert resume["edges"] > 500


def test_le_graphe_atteint_ce_que_la_convention_de_nom_ratait(graphe_reel):
    """
    `RepoMap.tests_for('src/mcp/exposure.py')` rend `None` — aucun fichier ne
    s'appelle `test_exposure.py`. Le graphe, lui, voit que `tests/test_mcp.py`
    l'importe. C'est la raison d'être de ce chapitre.
    """
    from src.agent.repo_map import RepoMap

    assert RepoMap().build().tests_for("src/mcp/exposure.py") is None
    assert "tests/test_mcp.py" in graphe_reel.tests_to_run("src/mcp/exposure.py")
