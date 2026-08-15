"""
L'isolation d'une réparation (phase 3 du harnais).

L'arbre de travail dans lequel quelqu'un travaille n'est pas un brouillon. Tout
ce qu'une réparation automatique fait se passe dans un **arbre git séparé**, avec
sa propre branche. Ces tests gardent ce qui rend cette promesse vraie :

1. L'arbre de l'utilisateur garde sa branche, ses fichiers et ses modifications
   non validées, quoi que la réparation fasse.
2. « Annuler » veut dire **détruire l'espace isolé** — jamais réinitialiser un
   arbre que le harnais n'a pas créé.
3. Un identifiant d'incident est **validé**, pas échappé : il devient un nom de
   branche et un chemin.
4. Une branche qui ne porte pas le préfixe des réparations n'est jamais
   supprimée par ce module.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.tools.git_tools import (  # noqa: E402
    PREFIXE_BRANCHE,
    GitRefused,
    IsolatedWorkspace,
    create_isolated_workspace,
    destroy_isolated_workspace,
    get_changed_files,
    git_commit_changes,
    git_status,
    list_repair_workspaces,
    restore_file_from_snapshot,
)


def _git(arguments, cwd):
    """Lance git dans un dépôt de test."""
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True,
    )


@pytest.fixture
def depot(tmp_path):
    """Un dépôt git réel, minuscule, avec un commit."""
    racine = tmp_path / "depot"
    racine.mkdir()
    _git(["init", "-b", "principale"], racine)
    _git(["config", "user.email", "test@galsen.local"], racine)
    _git(["config", "user.name", "Test"], racine)
    (racine / "calcul.py").write_text("def somme(a, b):\n    return a + b\n", encoding="utf-8")
    _git(["add", "."], racine)
    _git(["commit", "-m", "base"], racine)
    return str(racine)


# ----------------------------------------------------------------------
# 1. L'arbre de l'utilisateur n'est pas touché
# ----------------------------------------------------------------------

def test_l_espace_isole_est_un_autre_repertoire(depot):
    """Une seconde copie, pas la même."""
    espace = create_isolated_workspace("inc-001", root=depot)

    assert os.path.realpath(espace.path) != os.path.realpath(depot)
    assert os.path.isfile(os.path.join(espace.path, "calcul.py"))
    destroy_isolated_workspace(espace, root=depot)


def test_les_modifications_non_validees_survivent_a_la_reparation(depot):
    """Le travail de quelqu'un d'autre n'est pas un dommage collatéral."""
    with open(os.path.join(depot, "calcul.py"), "a", encoding="utf-8") as fichier:
        fichier.write("# travail en cours\n")

    espace = create_isolated_workspace("inc-002", root=depot)
    with open(os.path.join(espace.path, "calcul.py"), "w", encoding="utf-8") as fichier:
        fichier.write("def somme(a, b):\n    return a - b\n")
    destroy_isolated_workspace(espace, root=depot)

    with open(os.path.join(depot, "calcul.py"), encoding="utf-8") as fichier:
        contenu = fichier.read()
    assert "# travail en cours" in contenu
    assert "a + b" in contenu


def test_la_branche_de_l_utilisateur_ne_change_pas(depot):
    """Une réparation ne déplace personne."""
    avant = git_status(depot)["branch"]

    espace = create_isolated_workspace("inc-003", root=depot)
    apres_ouverture = git_status(depot)["branch"]
    destroy_isolated_workspace(espace, root=depot)

    assert avant == apres_ouverture == git_status(depot)["branch"] == "principale"


def test_l_espace_a_sa_propre_branche(depot):
    """Deux réparations ne se marchent pas dessus."""
    espace = create_isolated_workspace("inc-004", root=depot)

    assert espace.branch == f"{PREFIXE_BRANCHE}inc-004"
    assert git_status(espace.path)["branch"] == espace.branch
    destroy_isolated_workspace(espace, root=depot)


# ----------------------------------------------------------------------
# 2. Annuler, c'est détruire l'espace
# ----------------------------------------------------------------------

def test_detruire_un_espace_le_retire_et_supprime_sa_branche(depot):
    """L'annulation ne laisse pas de trace à nettoyer plus tard."""
    espace = create_isolated_workspace("inc-005", root=depot)

    resultat = destroy_isolated_workspace(espace, root=depot)

    assert resultat["worktree_removed"] is True
    assert resultat["branch_deleted"] is True
    assert not os.path.exists(espace.path)
    assert list_repair_workspaces(depot) == []


def test_une_branche_hors_prefixe_n_est_jamais_supprimee(depot):
    """Effacer la branche de quelqu'un d'autre ne se répare pas."""
    espace = create_isolated_workspace("inc-006", root=depot)
    usurpateur = IsolatedWorkspace(
        incident_id="inc-006", path=espace.path,
        branch="principale", base_commit=espace.base_commit,
    )

    resultat = destroy_isolated_workspace(usurpateur, root=depot)

    assert resultat["branch_deleted"] is False
    assert git_status(depot)["branch"] == "principale"


def test_un_espace_deja_ouvert_est_refuse(depot):
    """Deux réparations dans un même arbre les mêleraient."""
    espace = create_isolated_workspace("inc-007", root=depot)

    with pytest.raises(GitRefused):
        create_isolated_workspace("inc-007", root=depot)

    destroy_isolated_workspace(espace, root=depot)


# ----------------------------------------------------------------------
# 3. L'identifiant est validé, pas échappé
# ----------------------------------------------------------------------

@pytest.mark.parametrize("identifiant", [
    "../evasion", "inc 001", "inc;rm -rf /", "", "a" * 100, "-inc",
])
def test_un_identifiant_invalide_est_refuse(depot, identifiant):
    """Il devient un nom de branche et un chemin."""
    with pytest.raises(GitRefused):
        create_isolated_workspace(identifiant, root=depot)


# ----------------------------------------------------------------------
# 4. Valider, restaurer
# ----------------------------------------------------------------------

def test_un_commit_sans_changement_est_refuse(depot):
    """Un commit vide ferait croire à une réparation."""
    espace = create_isolated_workspace("inc-008", root=depot)

    with pytest.raises(GitRefused):
        git_commit_changes("incident inc-008 : rien", cwd=espace.path)

    destroy_isolated_workspace(espace, root=depot)


def test_un_commit_nomme_ses_fichiers(depot):
    """Un commit qu'on ne peut pas relier à son diagnostic est orphelin."""
    espace = create_isolated_workspace("inc-009", root=depot)
    with open(os.path.join(espace.path, "calcul.py"), "w", encoding="utf-8") as fichier:
        fichier.write("def somme(a, b):\n    return a + b + 0\n")

    resultat = git_commit_changes("incident inc-009 : correction", cwd=espace.path)

    assert resultat["files"] == ["calcul.py"]
    assert resultat["commit"]
    assert get_changed_files(espace.path) == []
    destroy_isolated_workspace(espace, root=depot)


def test_restaurer_un_fichier_qui_n_existait_pas_le_supprime(depot):
    """C'est la seule restauration correcte d'un fichier créé par erreur."""
    espace = create_isolated_workspace("inc-010", root=depot)
    nouveau = os.path.join(espace.path, "ajoute.py")
    with open(nouveau, "w", encoding="utf-8") as fichier:
        fichier.write("x = 1\n")

    restore_file_from_snapshot("ajoute.py", None, cwd=espace.path)

    assert not os.path.exists(nouveau)
    destroy_isolated_workspace(espace, root=depot)


def test_restaurer_remet_le_contenu_d_origine(depot):
    """L'instantané est le contenu, pas une promesse."""
    espace = create_isolated_workspace("inc-011", root=depot)
    origine = "def somme(a, b):\n    return a + b\n"
    with open(os.path.join(espace.path, "calcul.py"), "w", encoding="utf-8") as fichier:
        fichier.write("casse")

    restore_file_from_snapshot("calcul.py", origine, cwd=espace.path)

    with open(os.path.join(espace.path, "calcul.py"), encoding="utf-8") as fichier:
        assert fichier.read() == origine
    destroy_isolated_workspace(espace, root=depot)
