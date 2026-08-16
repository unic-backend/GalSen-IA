"""
L'autorisation d'outil : croiser qui demande avec ce que l'outil touche.

Le défaut corrigé ici : `tool:execute` était **un seul droit global**. Qui le
détenait lançait `metrics` — lecture publique — et `terminal` — commandes
arbitraires sur la machine — par la même porte. Quatre rôles, un seul privilège.

Ce que ces tests gardent :

1. **Le verdict a trois états.** « Autorisé », « il faut un humain » et
   « jamais » sont trois réponses ; écraser celle du milieu est exactement
   comment un portillon se contourne.
2. **L'approbation porte sur l'acte, pas sur l'acteur.** Un administrateur ne
   saute pas le portillon de `terminal`.
3. **Le plafond est une borne, pas une liste.** Un outil ajouté demain est
   couvert le jour où il déclare sa capacité.
4. **Un rôle inconnu ne s'ouvre pas** : il tombe au plafond minimal.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.rbac import Permission, RBACContext, Role  # noqa: E402
from src.tool.authorization import (  # noqa: E402
    PERMISSION_EXECUTION,
    PLAFOND_MINIMAL,
    PLAFONDS,
    Actor,
    Decision,
    authorization_report,
    authorize,
    authorized_tools,
    ceiling_for,
)
from src.tool.capabilities import (  # noqa: E402
    DataScope,
    Effect,
    load_capabilities,
    may_run_unattended,
)


@pytest.fixture(scope="module")
def registre():
    """Le registre réel des 24 outils, chargé une fois."""
    return load_capabilities()


def _acteur(role, permissions=(PERMISSION_EXECUTION,)):
    """Un acteur de ce rôle, détenant les permissions données."""
    return Actor(subject="awa", role=role, permissions=frozenset(permissions))


# ----------------------------------------------------------------------
# 1. Les trois verdicts
# ----------------------------------------------------------------------

def test_le_verdict_n_est_pas_un_booleen(registre):
    """Les trois états existent réellement, sur trois outils réels."""
    admin = _acteur("admin")

    assert authorize("metrics", admin, registre).decision is Decision.ALLOWED
    assert authorize("terminal", admin, registre).decision is Decision.REQUIRES_APPROVAL
    assert authorize("terminal", _acteur("readonly"), registre).decision is Decision.REFUSED


def test_une_approbation_requise_n_est_pas_une_autorisation(registre):
    """
    Le point qui compte : `allowed` reste faux tant qu'un humain n'a pas
    tranché. Le rendre vrai laisserait un appelant sauter le portillon.
    """
    verdict = authorize("gui", _acteur("admin"), registre)

    assert verdict.decision is Decision.REQUIRES_APPROVAL
    assert verdict.allowed is False


def test_une_approbation_requise_n_est_pas_un_refus(registre):
    """Répondre « jamais » à un acte approuvable serait faux."""
    verdict = authorize("email", _acteur("user"), registre)

    assert verdict.decision is not Decision.REFUSED
    assert verdict.decision is Decision.REQUIRES_APPROVAL


# ----------------------------------------------------------------------
# 2. L'approbation porte sur l'acte
# ----------------------------------------------------------------------

@pytest.mark.parametrize("outil", ["terminal", "gui", "docker", "api"])
def test_l_administrateur_ne_saute_aucun_portillon(outil, registre):
    """
    Le rôle le plus large de la plateforme reste soumis aux approbations :
    elles qualifient l'acte, jamais la personne.
    """
    verdict = authorize(outil, _acteur("admin"), registre)

    assert verdict.decision is Decision.REQUIRES_APPROVAL
    assert verdict.reason.strip() != ""


def test_aucun_role_n_obtient_un_outil_sous_portillon_sans_approbation(registre):
    """
    L'invariant, vérifié sur les quatre rôles et les 24 outils, pas sur un
    exemple choisi.
    """
    fuites = []
    for role in PLAFONDS:
        for tool_id in registre.capabilities:
            verdict = authorize(tool_id, _acteur(role), registre)
            if verdict.allowed and registre.get(tool_id).requires_approval:
                fuites.append((role, tool_id))

    assert fuites == [], f"Portillon sauté : {fuites}"


# ----------------------------------------------------------------------
# 3. Les plafonds
# ----------------------------------------------------------------------

def test_un_operateur_n_atteint_pas_les_donnees_privees(registre):
    """Exploiter la plateforme ne demande jamais de lire le courrier de quelqu'un."""
    verdict = authorize("email", _acteur("operator"), registre)

    assert verdict.decision is Decision.REFUSED
    assert "user_private" in verdict.reason


def test_un_utilisateur_n_atteint_pas_l_etat_de_la_plateforme(registre):
    """La symétrie du test précédent."""
    verdict = authorize("terminal", _acteur("user"), registre)

    assert verdict.decision is Decision.REFUSED
    assert "system" in verdict.reason


def test_un_role_en_lecture_seule_ne_produit_aucun_effet(registre):
    """Un effet hors plafond est nommé dans le refus."""
    verdict = authorize("filesystem", _acteur("readonly"), registre)

    assert verdict.decision is Decision.REFUSED
    assert "readonly" in verdict.reason


def test_un_role_inconnu_tombe_au_plafond_minimal():
    """Un rôle mal orthographié en configuration ne doit rien ouvrir de plus."""
    plafond = ceiling_for("adminn")

    assert plafond is PLAFOND_MINIMAL
    assert plafond.scopes == frozenset({DataScope.PUBLIC})
    assert plafond.effects == frozenset({Effect.READ})


def test_chaque_role_de_la_couche_api_a_un_plafond():
    """
    Un rôle ajouté dans `rbac.py` sans plafond ici tomberait au minimum sans
    que personne ne le remarque. Ce test le remarque.
    """
    manquants = [role.value for role in Role if role.value not in PLAFONDS]

    assert manquants == [], f"Rôles sans plafond : {manquants}"


def test_tout_refus_porte_sa_raison(registre):
    """Un refus sans motif est indébogable."""
    muets = []
    for role in list(PLAFONDS) + ["role_invente"]:
        for tool_id in registre.capabilities:
            verdict = authorize(tool_id, _acteur(role), registre)
            if verdict.decision is not Decision.ALLOWED and not verdict.reason.strip():
                muets.append((role, tool_id))

    assert muets == []


# ----------------------------------------------------------------------
# 4. La permission reste nécessaire
# ----------------------------------------------------------------------

def test_sans_la_permission_le_plafond_ne_sert_a_rien(registre):
    """Ce module complète `tool:execute`, il ne la remplace pas."""
    verdict = authorize("metrics", _acteur("admin", permissions=()), registre)

    assert verdict.decision is Decision.REFUSED
    assert PERMISSION_EXECUTION in verdict.reason


def test_un_outil_non_declare_n_est_autorise_a_personne(registre):
    """Un outil que nul n'a décrit ne peut être montré dans aucun plafond."""
    for role in PLAFONDS:
        verdict = authorize("outil_fantome", _acteur(role), registre)
        assert verdict.decision is Decision.REFUSED
        assert "non déclarée" in verdict.reason


# ----------------------------------------------------------------------
# 5. Le pont avec la couche API
# ----------------------------------------------------------------------

def test_un_contexte_rbac_devient_un_acteur():
    """
    Le pont se fait par attributs, sans que `src/tool` importe `src/api` :
    c'est ce qui garde la politique testable sans FastAPI.
    """
    contexte = RBACContext(key_fingerprint="abc123def456", role=Role.USER, subject="moussa")

    acteur = Actor.from_rbac(contexte)

    assert acteur.subject == "moussa"
    assert acteur.role == "user"
    assert Permission.TOOL_EXECUTE.value in acteur.permissions


def test_l_acteur_ne_porte_aucun_secret():
    """Un verdict finit dans l'audit ; rien de rejouable ne doit y entrer."""
    contexte = RBACContext(key_fingerprint="abc123def456", role=Role.ADMIN, subject="awa")

    verdict = authorize("metrics", Actor.from_rbac(contexte), load_capabilities())
    serialise = str(verdict.as_dict())

    assert "abc123def456" not in serialise
    assert verdict.as_dict()["subject"] == "awa"


def test_un_role_sans_permission_d_execution_ne_peut_rien(registre):
    """`readonly` ne détient pas `tool:execute` : le plafond n'a pas à trancher."""
    contexte = RBACContext(key_fingerprint="0" * 12, role=Role.READONLY, subject="scrutin")

    rangement = authorized_tools(Actor.from_rbac(contexte), registre)

    assert rangement["allowed"] == []
    assert rangement["requires_approval"] == []
    assert len(rangement["refused"]) == 24


# ----------------------------------------------------------------------
# 6. La matrice publiée
# ----------------------------------------------------------------------

def test_la_matrice_est_calculee_pas_recopiee():
    """
    Une politique décrite dans un document et une politique appliquée par le
    code divergent au premier changement. Celle-ci vient du code.
    """
    rapport = authorization_report()

    assert rapport["tools"] == 24
    assert set(rapport["roles"]) == set(PLAFONDS)
    for role, detail in rapport["roles"].items():
        total = sum(len(ids) for ids in detail["tools"].values())
        assert total == 24, f"{role} : {total} outils rangés sur 24"


def test_le_plafond_se_resserre_du_plus_large_au_plus_etroit():
    """
    Une inversion — `readonly` plus large que `admin` — serait une faille
    silencieuse. La comparaison porte sur ce que le code accorde vraiment.
    """
    rapport = authorization_report()
    ouverts = {
        role: len(detail["tools"]["allowed"]) + len(detail["tools"]["requires_approval"])
        for role, detail in rapport["roles"].items()
    }

    assert ouverts["admin"] == 24
    assert ouverts["admin"] >= ouverts["operator"] > ouverts["readonly"]
    assert ouverts["admin"] >= ouverts["user"] > ouverts["readonly"]


def test_le_modele_reste_atteignable_par_un_utilisateur(registre):
    """
    Régression trouvée en construisant ce module : `model` était déclaré
    `system`, ce qui refusait la génération à tout utilisateur. Le plafond a
    rendu la déclaration visible ; c'était la déclaration qui était fausse.
    """
    verdict = authorize("model", _acteur("user"), registre)

    assert verdict.decision is Decision.ALLOWED


# ----------------------------------------------------------------------
# 7. Le chemin des agents, fermé par la borne (phase 39.3)
#
# Ces deux tests remplacent les deux gardes de la phase 39.2, qui constataient
# le trou. Ils ont été remplacés par leur inverse, pas supprimés : le trou avait
# été écrit noir sur blanc pour être refermé, et voici la fermeture.
# ----------------------------------------------------------------------

def test_le_chemin_des_agents_consulte_desormais_le_portillon():
    """Un agent tourne sans témoin : c'est cette question-là qui lui est posée."""
    import inspect

    from src.agent.context import AgentContext

    source = inspect.getsource(AgentContext.use_tool)

    assert "may_run_unattended(" in source
    assert "sans témoin refusée" in source


def test_un_agent_n_obtient_terminal_que_dans_sa_borne(registre):
    """
    Le contournement mesuré en 39.2 : `/tool/execute` refusait `terminal` à un
    rôle `user`, et `POST /workflow/run` l'obtenait quand même. Fermé.
    """
    hors_borne, motif = may_run_unattended(
        "terminal", registre, arguments=["python", "-c", "import os"]
    )
    dans_borne, _ = may_run_unattended(
        "terminal", registre, arguments=["python", "-m", "pytest", "-q"]
    )

    assert hors_borne is False
    assert "approbation humaine" in motif
    assert dans_borne is True


def test_une_borne_ne_couvre_que_des_mots_entiers(registre):
    """
    `python -m pytest` ne doit pas couvrir `python -m pytester`. Un préfixe de
    caractères aurait ouvert exactement ce que la borne prétend fermer.
    """
    autorise, _ = may_run_unattended(
        "terminal", registre, arguments=["python", "-m", "pytester"]
    )

    assert autorise is False


def test_sans_arguments_la_question_porte_sur_l_outil_entier(registre):
    """Ne pas savoir ce qui est appelé est le pire cas, pas un cas favorable."""
    autorise, _ = may_run_unattended("terminal", registre)

    assert autorise is False
