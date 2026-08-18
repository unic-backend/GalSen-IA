"""
Les primitives de l'agent d'ingénierie (phases 1 à 3 du harnais).

Un agent qui répare du code lit des fichiers, cherche du texte, lance des
commandes et manipule git. Chacune de ces quatre capacités est une façon de
sortir du dépôt si elle est écrite naïvement, et ces tests gardent la version
non naïve.

Ce qu'ils tiennent :

1. **Un chemin est jugé après résolution**, jamais sur son orthographe : c'est
   la seule façon d'attraper un lien symbolique qui pointe au-dehors.
2. **Une commande est une liste.** Une chaîne est refusée, parce qu'elle serait
   interprétée par un shell et que les valeurs qui arrivent ici viennent de
   traces d'exécution.
3. **L'arbre de travail de l'utilisateur n'est jamais l'espace de réparation.**
4. **Ce qui est tronqué ou tué le dit.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), ""))

from src.agent.tools import (  # noqa: E402
    OCTETS_MAXIMUM,
    CommandRefused,
    WorkspaceRefused,
    file_hash,
    hash_many,
    list_directory,
    parse_pytest_counts,
    read_file,
    repo_root,
    resolve,
    run_command,
    search_code,
    write_file,
)


# ----------------------------------------------------------------------
# 1. Les chemins
# ----------------------------------------------------------------------

@pytest.mark.parametrize("chemin", [
    "../etc/passwd",
    "../../etc/passwd",
    "/etc/passwd",
    "src/../../autre-depot/x.py",
    "docs/../../../root/.ssh/id_rsa",
])
def test_une_sortie_du_depot_est_refusee(chemin):
    """Refusé sur le point d'arrivée, pas sur l'orthographe."""
    with pytest.raises(WorkspaceRefused):
        resolve(chemin)


def test_un_detour_qui_reste_dedans_est_accepte():
    """`docs/../src` est légitime : rejeter la chaîne « .. » refuserait à tort."""
    assert resolve("docs/../src").endswith("/src")


@pytest.mark.parametrize("chemin", [".env", "config/secrets.yaml", "data/x.sqlite"])
def test_les_fichiers_hors_de_portee_le_restent(chemin):
    """Aucune approbation ne donne accès à ceux-là."""
    with pytest.raises(WorkspaceRefused):
        resolve(chemin)


def test_un_lien_symbolique_vers_l_exterieur_est_refuse(tmp_path):
    """C'est l'évasion qu'un simple préfixe de chaîne ne voit pas."""
    racine = tmp_path / "depot"
    racine.mkdir()
    (racine / "dedans.txt").write_text("ok", encoding="utf-8")
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (dehors / "cible.txt").write_text("secret", encoding="utf-8")
    os.symlink(dehors, racine / "evasion")

    assert resolve("dedans.txt", root=str(racine))
    with pytest.raises(WorkspaceRefused):
        resolve("evasion/cible.txt", root=str(racine))


def test_un_chemin_vide_est_refuse():
    """Deviner « la racine » serait la mauvaise réponse."""
    with pytest.raises(WorkspaceRefused):
        resolve("   ")


# ----------------------------------------------------------------------
# 2. Lire, écrire, chercher
# ----------------------------------------------------------------------

def test_lire_un_fichier_du_depot():
    """Le cas nominal, sur un fichier réel."""
    assert "GalSen" in read_file("CLAUDE.md")


def test_lire_un_fichier_absent_dit_pourquoi():
    """« Pas un fichier » et « hors du dépôt » ne se confondent pas."""
    with pytest.raises(WorkspaceRefused) as refus:
        read_file("src/agent/ce-qui-n-existe-pas.py")

    assert "pas un fichier" in str(refus.value)


def test_ecrire_puis_relire(tmp_path):
    """Écriture, empreinte et relecture dans un espace à soi."""
    resultat = write_file("sous/dossier/x.py", "print('ok')\n", root=str(tmp_path))

    assert resultat["bytes"] == len("print('ok')\n")
    assert read_file("sous/dossier/x.py", root=str(tmp_path)) == "print('ok')\n"
    assert resultat["sha256"] == file_hash("sous/dossier/x.py", root=str(tmp_path))


def test_un_contenu_trop_gros_est_refuse(tmp_path):
    """Au-delà, ce n'est plus une correction ciblée."""
    with pytest.raises(WorkspaceRefused):
        write_file("gros.py", "x" * (OCTETS_MAXIMUM + 1), root=str(tmp_path))


def test_la_recherche_rend_fichier_et_ligne():
    """Une correspondance sans position n'aide personne à corriger."""
    trouves = search_code(r"def create_isolated_workspace")

    assert trouves
    assert trouves[0]["path"].endswith("git_tools.py")
    assert trouves[0]["line"] > 0


def test_la_recherche_est_bornee():
    """Dix mille lignes rendues ne sont pas une recherche."""
    assert len(search_code(r"def ", limit=5)) == 5


def test_une_expression_invalide_est_refusee():
    """Le message vient de `re`, il n'est pas résumé."""
    with pytest.raises(WorkspaceRefused):
        search_code("(non fermée")


def test_le_listing_ignore_les_artefacts():
    """`__pycache__` n'est pas du code, et le parcourir coûte plus que tout."""
    contenus = list_directory("src/agent", recursive=True)

    assert not any("__pycache__" in chemin for chemin in contenus)
    assert any(chemin.endswith("context.py") for chemin in contenus)


def test_un_fichier_absent_rend_MISSING_et_pas_une_omission(tmp_path):
    """Disparaître et n'avoir jamais existé sont deux événements différents."""
    write_file("present.py", "x = 1\n", root=str(tmp_path))

    empreintes = hash_many(["present.py", "absent.py"], root=str(tmp_path))

    assert empreintes["absent.py"] == "MISSING"
    assert empreintes["present.py"] != "MISSING"


# ----------------------------------------------------------------------
# 3. Les commandes
# ----------------------------------------------------------------------

def test_une_commande_en_chaine_est_refusee():
    """C'est elle qui transformerait un message d'erreur en syntaxe shell."""
    with pytest.raises(CommandRefused) as refus:
        run_command("git status")

    assert "liste" in str(refus.value)


def test_une_injection_shell_reste_un_argument():
    """Sans shell, `;` n'est qu'un caractère."""
    resultat = run_command(["git", "rev-parse", "--verify", "HEAD; rm -rf /"])

    assert resultat.returncode != 0
    assert os.path.isdir(os.path.join(repo_root(), "src"))


def test_un_executable_inconnu_est_refuse():
    """Le harnais lance ses outils ; il n'est pas un interpréteur."""
    with pytest.raises(CommandRefused):
        run_command(["curl", "https://example.com"])


def test_un_depassement_de_delai_est_dit():
    """Une réparation qui pend est pire qu'une réparation qui échoue."""
    resultat = run_command(
        [sys.executable, "-c", "import time; time.sleep(30)"], timeout=1,
    )

    assert resultat.timed_out is True
    assert resultat.ok is False
    assert "tuée" in resultat.stderr


def test_une_sortie_enorme_est_tronquee_en_le_disant():
    """Tronquer en silence ferait lire une sortie pour une sortie complète."""
    resultat = run_command(
        [sys.executable, "-c", "print('x' * 200000)"], timeout=30,
    )

    assert "stdout" in resultat.truncated
    assert "tronqué" in resultat.stdout


def test_l_environnement_n_est_pas_herite(monkeypatch):
    """Un secret du processus parent n'a pas à atteindre un sous-processus."""
    monkeypatch.setenv("GALSEN_SECRET_DE_TEST", "valeur-sensible")

    resultat = run_command(
        [sys.executable, "-c",
         "import os; print(os.environ.get('GALSEN_SECRET_DE_TEST', 'ABSENT'))"],
        timeout=30,
    )

    assert "ABSENT" in resultat.stdout


def test_les_compteurs_de_pytest_sont_relus():
    """Un code de sortie nul ne dit pas si des tests ont tourné."""
    compteurs = parse_pytest_counts("42 passed, 2 skipped in 1.23s")

    assert compteurs["passed"] == 42
    assert compteurs["skipped"] == 2
    assert compteurs["failed"] == 0
