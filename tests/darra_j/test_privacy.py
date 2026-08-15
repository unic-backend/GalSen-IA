"""
Deux verrous sur les données d'un enfant, et aucun n'ouvre sans l'autre
(VOLET 13 de Darra J).

La question de ce volet n'est pas « qui a le droit ? » — `src/api/rbac.py` y
répond. C'est celle, plus étroite, qu'un système éducatif rate : *un rôle
autorisé à lire des apprenants n'est pas autorisé à lire **cet** apprenant.*

Ce que ces tests gardent :

1. **La permission et le rattachement sont tous deux requis.**
2. **Les deux refus sont distincts** : « pas de données d'apprenant » et « pas
   cet enfant-là » ne se confondent pas.
3. **Aucun rôle de plateforme ne lit un apprenant**, administrateur compris.
4. **Une autorité éducative et un chercheur non plus.**
5. **Une piste d'audit porte une empreinte**, jamais une référence en clair.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.api.rbac import (  # noqa: E402
    EDUCATION_ROLES,
    PERMISSIONS_HORS_PLATEFORME,
    Permission,
    Role,
    get_permissions_for_role,
)
from src.darra_j.access import AccessRefused  # noqa: E402
from src.darra_j.privacy import (  # noqa: E402
    PrivacyRefused,
    authorize_learner_read,
    may_read_learners,
    privacy_report,
    redact_learner,
    safe_trail_entry,
)
from src.knowledge_engine.knowledge_security import (  # noqa: E402
    readable_sensitivities,
)
from src.knowledge_engine.types import KnowledgeSensitivity  # noqa: E402
from src.tool.authorization import PLAFONDS, ceiling_for  # noqa: E402
from src.tool.capabilities import DataScope  # noqa: E402

ENFANT = "enfant-7f3a"
DECLARES = [ENFANT]


# ----------------------------------------------------------------------
# 1. Les deux verrous
# ----------------------------------------------------------------------

def test_un_eleve_lit_ses_propres_donnees():
    """Le cas nominal existe, et le lien passe par « own »."""
    verdict = authorize_learner_read(Role.STUDENT, ENFANT, ENFANT)

    assert verdict["authorized"] is True
    assert verdict["link"] == "own"


def test_un_eleve_ne_lit_pas_un_autre_eleve():
    """La permission ne dit pas *lequel*."""
    with pytest.raises(AccessRefused):
        authorize_learner_read(Role.STUDENT, "eleve-1", "eleve-2")


def test_un_parent_lit_l_enfant_declare():
    """Le lien vient d'une source d'inscription, et il est nommé."""
    verdict = authorize_learner_read(Role.PARENT, "parent-1", ENFANT, DECLARES)

    assert verdict["link"] == "declared_link"


def test_un_parent_sans_declaration_n_ouvre_rien():
    """La permission seule n'ouvre aucun enfant."""
    with pytest.raises(AccessRefused):
        authorize_learner_read(Role.PARENT, "parent-1", ENFANT, None)


def test_un_enseignant_ne_lit_pas_un_eleve_hors_de_sa_liste():
    """Enseigner à une classe n'ouvre pas l'école."""
    with pytest.raises(AccessRefused):
        authorize_learner_read(Role.TEACHER, "prof-1", "eleve-autre", DECLARES)


# ----------------------------------------------------------------------
# 2. Les deux refus ne se confondent pas
# ----------------------------------------------------------------------

def test_un_refus_de_permission_n_est_pas_un_refus_de_lien():
    """
    Les confondre rendrait le second impossible à diagnostiquer.

    « Ce rôle ne lit aucun apprenant » et « ce rôle en lit, mais pas celui-ci »
    sont deux faits différents, et l'exploitant doit pouvoir les distinguer.
    """
    with pytest.raises(PrivacyRefused) as permission:
        authorize_learner_read(Role.RESEARCHER, "chercheur-1", ENFANT, DECLARES)

    with pytest.raises(AccessRefused) as lien:
        authorize_learner_read(Role.PARENT, "parent-1", "autre", DECLARES)

    assert "ne lit aucune donnée d'apprenant" in str(permission.value)
    assert "n'est pas rattaché" in str(lien.value)


def test_un_refus_de_permission_ne_regarde_meme_pas_la_liste():
    """Une liste complaisante ne doit pas rattraper une permission absente."""
    with pytest.raises(PrivacyRefused):
        authorize_learner_read(Role.EDUCATION_AUTHORITY, "ministere", ENFANT,
                               [ENFANT])


# ----------------------------------------------------------------------
# 3. Qui ne lit jamais un apprenant
# ----------------------------------------------------------------------

@pytest.mark.parametrize("role", [
    Role.ADMIN, Role.OPERATOR, Role.USER, Role.READONLY,
])
def test_aucun_role_de_plateforme_ne_lit_un_apprenant(role):
    """La plateforme n'est ni un parent, ni un enseignant."""
    assert may_read_learners(role) is False

    with pytest.raises(PrivacyRefused):
        authorize_learner_read(role, "operateur", ENFANT, DECLARES)


@pytest.mark.parametrize("role", [Role.EDUCATION_AUTHORITY, Role.RESEARCHER])
def test_ni_l_autorite_educative_ni_le_chercheur(role):
    """Publier un programme ou étudier des agrégats ne l'a jamais demandé."""
    assert may_read_learners(role) is False


def test_seuls_quatre_roles_educatifs_lisent_des_apprenants():
    """La liste est courte, et elle doit le rester visiblement."""
    lecteurs = {role.value for role in Role if may_read_learners(role)}

    assert lecteurs == {"student", "parent", "teacher", "school_admin"}


def test_la_permission_d_apprenant_est_hors_plateforme():
    """C'est ce qui empêche l'administrateur de la recevoir par compréhension."""
    assert Permission.LEARNER_DATA_READ_LINKED in PERMISSIONS_HORS_PLATEFORME
    assert Permission.LEARNER_DATA_READ_LINKED not in \
        get_permissions_for_role(Role.ADMIN)


def test_il_n_existe_aucune_permission_pour_un_apprenant_non_rattache():
    """
    La garantie est structurelle : la permission n'a pas été créée.

    Un nom comme `learner:read_any` ouvrirait la porte que tout ce volet ferme ;
    ce test constate qu'aucune permission ne parle d'apprenant sans rattachement.
    """
    parlant_d_apprenant = sorted(
        permission.value for permission in Permission
        if permission.value.startswith("learner:")
    )

    assert parlant_d_apprenant == ["learner:decide", "learner:read_linked"]


# ----------------------------------------------------------------------
# 4. Les plafonds d'outils suivent les rôles
# ----------------------------------------------------------------------

def test_chaque_role_educatif_a_un_plafond_d_outils():
    """Un rôle sans plafond tomberait au minimum sans que personne le voie."""
    for role in EDUCATION_ROLES:
        assert role.value in PLAFONDS, role.value


def test_aucun_role_educatif_n_atteint_l_etat_de_la_plateforme():
    """Une position dans une école n'est pas une position dans le système."""
    for role in EDUCATION_ROLES:
        assert DataScope.SYSTEM not in ceiling_for(role.value).scopes, role.value


def test_aucun_role_educatif_ne_lit_l_interne_de_la_plateforme():
    """
    La troisième table que l'ajout de six rôles pouvait laisser diverger.

    Une autorité éducative n'est pas une exception : définir un programme
    national ne demande rien de confidentiel ici, et lui accorder `INTERNAL`
    par respect institutionnel serait un privilège accordé pour un motif qui
    n'est pas un besoin.
    """
    for role in EDUCATION_ROLES:
        assert readable_sensitivities(role.value) == frozenset(
            {KnowledgeSensitivity.PUBLIC}
        ), role.value


def test_le_chercheur_est_arrete_par_le_plafond_avant_la_permission():
    """Deux barrières indépendantes valent mieux qu'une bien placée."""
    plafond = ceiling_for("researcher")

    assert plafond.scopes == frozenset({DataScope.PUBLIC})
    assert may_read_learners(Role.RESEARCHER) is False


# ----------------------------------------------------------------------
# 5. Une trace ne nomme aucun enfant
# ----------------------------------------------------------------------

def test_une_reference_d_apprenant_devient_une_empreinte():
    """Une piste qui nomme des enfants est une piste qu'on ne peut publier."""
    empreinte = redact_learner("awa-diop-6e-b")

    assert "awa" not in empreinte
    assert empreinte.startswith("learner:")
    assert len(empreinte) == len("learner:") + 12


def test_l_empreinte_est_stable_donc_suivable():
    """Sinon on ne peut plus suivre un apprenant dans un incident."""
    assert redact_learner(ENFANT) == redact_learner(ENFANT)
    assert redact_learner(ENFANT) != redact_learner("enfant-autre")


def test_une_reference_absente_ne_fabrique_pas_d_empreinte():
    """Une empreinte de rien laisserait croire qu'un apprenant existe."""
    assert redact_learner("") == "learner:—"


def test_une_entree_de_piste_ne_porte_aucune_reference_en_clair():
    """Elle est construite champ par champ, pas expurgée après coup."""
    entree = safe_trail_entry("quiz.score", "prof-1", "awa-diop", items=3)

    rendu = repr(entree)
    assert "awa-diop" not in rendu
    assert "prof-1" not in rendu
    assert entree["items"] == 3


def test_l_autorisation_ne_renvoie_pas_les_references_en_clair():
    """Le verdict lui-même finit dans un journal."""
    verdict = authorize_learner_read(Role.PARENT, "parent-1", ENFANT, DECLARES)

    assert ENFANT not in repr(verdict)
    assert verdict["subject"].startswith("learner:")


# ----------------------------------------------------------------------
# 6. Ce que le module ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_nomme_la_conjonction():
    """Une garantie qui n'est pas écrite se perd au premier refactor."""
    regles = " ".join(privacy_report()["rules"])

    assert "conjonction" in regles
    assert "non rattaché" in regles


def test_le_rapport_liste_qui_ne_lit_jamais_un_apprenant():
    """Un exploitant doit pouvoir le vérifier sans lire le code."""
    rapport = privacy_report()

    assert rapport["roles_reading_learners"] == [
        "parent", "school_admin", "student", "teacher",
    ]
    assert "admin" in rapport["roles_never_reading_learners"]
    assert "education_authority" in rapport["roles_never_reading_learners"]
