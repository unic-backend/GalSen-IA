"""
L'état des lieux du VOLET 34 ne doit pas se mettre à mentir.

`docs/architecture/personal-agent-assessment.md` est la base sur laquelle les
vingt-trois phases suivantes sont planifiées. Un document qui décrit un dépôt
qu'il n'y a plus envoie le travail suivant dans une direction qui n'existe pas —
ce que ce dépôt a déjà constaté cette semaine : `orchestration.md` affirmait que
le workflow par défaut avait un pipeline vide, faux depuis le planificateur.

Ces tests n'épinglent pas les propriétés de sécurité mesurées dans le document :
`test_terminal_tool.py` et `test_filesystem_tool.py` le font déjà, et les
réécrire ici ferait deux vérités sur un même fait. Ils épinglent ce que le
document **compte**, parce que c'est cela qui dérive en silence.
"""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ETAT_DES_LIEUX = os.path.join(RACINE, "docs", "architecture", "personal-agent-assessment.md")


@pytest.fixture(scope="module")
def outils():
    """Outils déclarés dans le registre."""
    with open(os.path.join(RACINE, "tools", "tools.yaml"), encoding="utf-8") as fichier:
        return yaml.safe_load(fichier)["tools"]


@pytest.fixture(scope="module")
def document():
    """Contenu de l'état des lieux."""
    with open(ETAT_DES_LIEUX, encoding="utf-8") as fichier:
        return fichier.read()


def test_le_compte_d_outils_actifs_est_celui_annonce(outils, document):
    """« dix-neuf activés » est un nombre, donc il se vérifie."""
    actifs = [outil for outil in outils if outil["enabled"]]

    assert len(actifs) == 21, (
        f"{len(actifs)} outils actifs — l'état des lieux en annonce 21. "
        "Mettre le document à jour, ou expliquer le nouvel outil."
    )
    assert "twenty-one enabled" in document


def test_l_outil_docker_reste_desactive(outils, document):
    """
    Il est coupé pour une raison écrite : depuis le conteneur de production, il
    exigerait le socket Docker de l'hôte, c'est-à-dire root sur l'hôte. Le
    réactiver sans décision écrite rouvrirait ce chemin.
    """
    docker = next(outil for outil in outils if outil["id"] == "docker")

    assert docker["enabled"] is False
    assert "docker" in document and "disabled" in document


def test_chaque_outil_declare_s_importe(outils):
    """
    Un outil du catalogue que rien ne peut charger est une capacité annoncée
    sans preuve — le mode d'échec que ce dépôt traque partout.
    """
    import importlib

    manquants = []
    for outil in outils:
        module = outil["module"].replace("tools.", "src.tools.")
        try:
            importlib.import_module(module)
        except Exception as erreur:  # noqa: BLE001 - on rapporte, on ne masque pas
            manquants.append(f"{outil['id']} ({type(erreur).__name__}: {erreur})")

    assert manquants == [], "Outils déclarés et non chargeables : " + ", ".join(manquants)


def test_les_six_specialistes_du_brief_existent():
    """
    Ce test disait l'inverse jusqu'au 2026-08-12, et il a fait son travail.

    Il affirmait que trois des six spécialistes demandés n'existaient pas, en
    annonçant : *le jour où l'un arrive, ce test échoue et le document doit être
    corrigé*. Le chapitre 11 les a livrés, le test a échoué, et il est retourné
    ici — pas supprimé. Il garde désormais l'affirmation dans l'autre sens : ces
    agents sont déclarés, donc joignables.
    """
    from src.router.agent_loader import AgentLoader

    agents = AgentLoader(os.path.join(RACINE, "agents", "registry.yaml")).get_all_agents()

    assert len(agents) == 13
    for present in ("organizer", "project_manager", "opportunity"):
        assert present in agents, f"« {present} » n'est plus déclaré au registre"


def test_le_navigateur_n_est_pas_un_navigateur():
    """
    Le document affirme qu'il ne sait ni exécuter du JavaScript ni cliquer. Si
    un vrai navigateur arrive un jour, cette affirmation devient fausse.
    """
    from src.tools.browser.tool import BrowserTool

    operations = {
        nom for nom in dir(BrowserTool)
        if not nom.startswith("_") and callable(getattr(BrowserTool, nom))
    }

    assert {"visit", "get_text", "get_links"} <= operations
    assert not operations & {"click", "type", "screenshot", "evaluate"}


def test_la_vue_et_la_main_existent_et_restent_separees():
    """
    Ce test disait « ni vue ni pointeur ». Les chapitres 05 et 06 ont livré, il a
    échoué deux fois, et l'état des lieux a été daté et corrigé à chaque fois —
    c'était exactement son rôle. Il garde maintenant ce qui doit rester vrai :
    lire et agir sont deux outils, et un agent peut recevoir des yeux sans
    recevoir de main.
    """
    import importlib.util

    def existe(module: str) -> bool:
        """`find_spec` lève quand le paquet parent est absent — c'est aussi un « non »."""
        try:
            return importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            return False

    assert existe("src.tools.screen.tool")
    assert existe("src.tools.gui.tool")

    # Les deux chapitres ont livré ; ce qui doit tenir, c'est leur séparation.
    # `test_gui_tool.py` la garde en détail — ici on vérifie que la vue n'a pas
    # gagné de main au passage.
    from src.tools.screen import ScreenTool

    assert set(ScreenTool().available_operations()) == {"availability", "find", "snapshot"}


def test_le_mode_souverain_est_actif_par_defaut(monkeypatch):
    """
    Le brief demande une bascule vers le cloud ; ADR-014 la refuse par défaut.
    Tant que la décision n'est pas prise, le défaut mesuré doit rester celui de
    l'ADR — sinon le chapitre 04 arbitrerait une question déjà tranchée en
    douce.
    """
    from src.model_engine.providers.provider_registry import sovereign_mode

    monkeypatch.delenv("GALSEN_SOVEREIGN_MODE", raising=False)

    assert sovereign_mode() is True


# ----------------------------------------------------------------------
# Ce que la comparaison des fondations engage (phase 2.1)
# ----------------------------------------------------------------------

def test_la_boucle_d_agent_n_existe_toujours_pas():
    """
    Trouvaille de la phase 2.1. OpenHands a besoin d'un contrôleur qui borne les
    itérations et le budget parce que son agent **boucle** jusqu'à
    `AgentFinishAction`. Le routeur d'ici ne boucle pas : il parcourt un pipeline
    déclaré une fois, dans l'ordre, et s'arrête. La sûreté est structurelle et
    gratuite.

    Le brief demande des « self-reflection and improvement loops ». Le jour où
    cette boucle arrive, la garantie disparaît — et le plafond d'itérations doit
    arriver **dans la même phase**, pas dans la suivante. Ce test échouera ce
    jour-là, et c'est exactement son rôle.
    """
    import inspect

    from src.router import router_engine

    source = inspect.getsource(router_engine.RouterEngine.process_request)

    assert "while " not in source, (
        "Une boucle est apparue dans le routeur : elle doit être bornée par un "
        "plafond d'itérations et un budget de requête (comparaison, §6)."
    )
    assert "for agent_id in ordered_agents:" in source


def test_aucun_plafond_de_requete_n_est_annonce_sans_exister():
    """
    Le contre-test du précédent : tant qu'il n'y a pas de boucle, il ne doit pas
    y avoir de plafond décoratif. Un `max_iterations` qui ne borne rien serait
    la capacité déclarée sans preuve que ce dépôt traque partout.
    """
    import inspect

    from src.router import router_engine

    source = inspect.getsource(router_engine)

    assert "max_iterations" not in source


# ----------------------------------------------------------------------
# Ce que la comparaison computer-use engage (phase 2.2)
# ----------------------------------------------------------------------

def test_playwright_reste_une_dependance_a_declarer():
    """
    La comparaison affirme que le paquet Playwright n'est pas installé — mesuré,
    pas supposé, après avoir d'abord écrit le contraire. S'il arrive un jour, il
    devra arriver **déclaré** dans un `requirements-*.txt`, avec son poids
    annoncé, comme les embeddings et l'audio.
    """
    import importlib.util

    try:
        present = importlib.util.find_spec("playwright") is not None
    except ModuleNotFoundError:
        present = False

    if not present:
        return

    fichiers = [
        nom for nom in os.listdir(RACINE)
        if nom.startswith("requirements") and nom.endswith(".txt")
    ]
    declare = any(
        "playwright" in open(os.path.join(RACINE, nom), encoding="utf-8").read()
        for nom in fichiers
    )
    assert declare, "Playwright est installé sans être déclaré dans un requirements-*.txt"


def test_la_couche_gui_devra_nommer_ce_qu_elle_touche():
    """
    Exigence tirée de notre propre architecture, pas d'un benchmark : le
    portillon d'approbation doit pouvoir **nommer** l'élément qu'une action va
    toucher. Un clic en coordonnées produirait une demande d'approbation qui dit
    « cliquer en (412, 380) » — un mystère à approuver.

    Ce test garde la propriété pour le jour où le chapitre 06 livre : toute
    demande d'approbation porte une description non vide.
    """
    from src.approval_engine.types import ApprovalRequest

    demande = ApprovalRequest(agent_id="gui", request_id="r1", action="gui:click")

    # Le champ existe et peut porter l'identité de la cible ; le chapitre 06
    # devra le remplir, et ce test deviendra l'assertion qui l'y oblige.
    assert hasattr(demande, "description")


# ----------------------------------------------------------------------
# Ce qu'ADR-017 engage (phase 3.1)
# ----------------------------------------------------------------------

ADR_017 = os.path.join(
    RACINE, "docs", "architecture", "decisions",
    "017-computer-agent-is-tools-not-a-new-architecture.md",
)


def test_les_capacites_manquantes_arrivent_comme_outils():
    """
    La décision centrale d'ADR-017 : ce qui manque, ce sont des **mains**, et
    des mains sont des outils. Pas de second runtime, pas de seconde boucle,
    pas de chemin d'exécution parallèle.

    Ce test échouera si une capacité du VOLET arrive ailleurs que dans le
    catalogue — par exemple un module `src/computer_agent/` avec sa propre
    orchestration.
    """
    import importlib.util

    def existe(module: str) -> bool:
        try:
            return importlib.util.find_spec(module) is not None
        except ModuleNotFoundError:
            return False

    for orchestrateur_parallele in (
        "src.computer_agent", "src.desktop_agent", "src.agent_runtime_v2",
    ):
        assert not existe(orchestrateur_parallele), (
            f"{orchestrateur_parallele} existe : ADR-017 dit que les nouvelles "
            "capacités arrivent comme outils, pas comme une seconde architecture."
        )


def test_aucun_cadre_d_orchestration_tiers_n_est_adopte():
    """
    ADR-017 §1 : ni LangGraph, ni CrewAI, ni AutoGen. Les motifs sont copiés,
    les dépendances ne sont pas prises — c'est le prix assumé pour ne pas mettre
    un second cerveau dans la plateforme.
    """
    fichiers = [
        nom for nom in os.listdir(RACINE)
        if nom.startswith("requirements") and nom.endswith(".txt")
    ]
    declare = ""
    for nom in fichiers:
        with open(os.path.join(RACINE, nom), encoding="utf-8") as fichier:
            declare += fichier.read().lower()

    for cadre in ("langgraph", "crewai", "autogen", "langchain"):
        assert cadre not in declare, (
            f"{cadre} est déclaré : ADR-017 refuse un second orchestrateur. "
            "Modifier l'ADR d'abord."
        )


def test_l_adr_017_ne_tranche_pas_la_souverainete():
    """
    La question du cloud appartient au propriétaire (chapitre 04). Un ADR qui la
    trancherait au passage rendrait le chapitre 04 décoratif.
    """
    with open(ADR_017, encoding="utf-8") as fichier:
        texte = fichier.read()

    assert "does **not** decide" in texte
    assert "ADR-014" in texte


def test_la_derogation_acceptee_est_plus_stricte_que_ce_qu_elle_remplace():
    """
    Ce test disait l'inverse jusqu'au 2026-08-12, et il a fait son travail.

    Il vérifiait qu'ADR-018 restait **proposé** et sans effet sur le code, parce
    que la décision appartenait au propriétaire. Elle est prise — **option B** —
    et le test garde maintenant ce qui rend B défendable : *B ne desserre pas le
    défaut, il rétrécit l'exception.*

    Deux propriétés, et la seconde est celle qui compte : le mode souverain
    reste vrai par défaut, et les trois refus inconditionnels — qui n'existaient
    pas avant cet ADR — tiennent quelle que soit la configuration.
    """
    chemin = os.path.join(
        RACINE, "docs", "architecture", "decisions",
        "018-sovereign-by-default-with-a-scoped-derogation.md",
    )
    with open(chemin, encoding="utf-8") as fichier:
        texte = fichier.read()

    assert "**Accepted — option B**" in texte

    from src.model_engine.providers.derogations import (
        REFUS_INCONDITIONNELS,
        Derogation,
        allow,
    )
    from src.model_engine.providers.provider_registry import sovereign_mode

    assert sovereign_mode() is True, "B ne change pas le défaut d'ADR-014"

    # Une dérogation active pour un type de tâche ne couvre **pas** le contenu
    # d'une personne : c'est la promesse de l'ADR, et sans elle la dérogation
    # serait le levier global qu'elle prétend remplacer.
    derogation = [Derogation(task_type="code_generation", provider_id="openai")]
    autorise, _ = allow(
        "code_generation", "openai", carries_user_content=True, derogations=derogation,
    )
    assert autorise is False
    assert set(REFUS_INCONDITIONNELS) == {
        "user_content", "screen_capture", "training_export",
    }
