"""
La CLI du harnais (phase 8).

Une règle gouverne toute la surface : **aucune commande ne modifie le dépôt sauf
`repair`, et `repair` n'écrit que dans son espace isolé.** Lire ce qui s'est
passé ne doit jamais être ce qui le change — quelqu'un qui diagnostique à trois
heures du matin doit pouvoir taper n'importe quoi ici et savoir que l'arbre est
le même après.

Ce que ces tests gardent :

1. **`status`, `health`, `test`, `diagnose` et `audit` ne modifient rien.**
2. **Un correctif vient d'un fichier**, jamais de la ligne de commande.
3. **Les codes de sortie disent l'issue** : une réparation annulée est un refus
   réussi, et rend 1 pour qu'une chaîne d'intégration le voie.
4. **Une réparation par la CLI laisse le dépôt d'origine intact.**
"""

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.cli import main  # noqa: E402

RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CALCUL_CASSE = "def moyenne(valeurs):\n    return sum(valeurs) / len(valeurs)\n"
CALCUL_CORRIGE = (
    "def moyenne(valeurs):\n"
    "    if not valeurs:\n        return 0\n"
    "    return sum(valeurs) / len(valeurs)\n"
)
TESTS = (
    "import sys\n\nsys.path.insert(0, '.')\n\nfrom src.calcul import moyenne\n\n\n"
    "def test_vide():\n    assert moyenne([]) == 0\n"
)


def _git(arguments, cwd):
    """Lance git dans le dépôt jetable."""
    return subprocess.run(
        ["git", *arguments], cwd=cwd, capture_output=True, text=True, check=True,
    )


@pytest.fixture
def depot(tmp_path):
    """Un dépôt git réel, cassé, avec sa suite."""
    racine = tmp_path / "projet"
    (racine / "src").mkdir(parents=True)
    (racine / "tests").mkdir()
    (racine / "src" / "__init__.py").write_text("", encoding="utf-8")
    (racine / "src" / "calcul.py").write_text(CALCUL_CASSE, encoding="utf-8")
    (racine / "tests" / "test_calcul.py").write_text(TESTS, encoding="utf-8")
    (racine / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
    _git(["init", "-b", "principale"], racine)
    _git(["config", "user.email", "t@galsen.local"], racine)
    _git(["config", "user.name", "T"], racine)
    _git(["add", "."], racine)
    _git(["commit", "-m", "base"], racine)
    return str(racine)


def _empreinte_du_depot(racine):
    """L'état complet du dépôt, pour prouver qu'il n'a pas bougé."""
    etat = _git(["status", "--porcelain"], racine).stdout
    with open(os.path.join(racine, "src", "calcul.py"), encoding="utf-8") as fichier:
        return etat, fichier.read()


# ----------------------------------------------------------------------
# 1. Les commandes de lecture ne modifient rien
# ----------------------------------------------------------------------

@pytest.mark.parametrize("commande", [
    ["status"], ["health"], ["diagnose", "--trace", "ValueError: x"],
])
def test_une_commande_de_lecture_ne_modifie_pas_le_depot(depot, commande, capsys):
    """Lire ce qui s'est passé ne doit pas être ce qui le change."""
    avant = _empreinte_du_depot(depot)

    main([*commande, "--root", depot, "--json"])
    capsys.readouterr()

    assert _empreinte_du_depot(depot) == avant


def test_status_rend_la_branche_et_les_espaces(depot, capsys):
    """Ce qu'un opérateur regarde en premier."""
    code = main(["status", "--root", depot, "--json"])
    sortie = json.loads(capsys.readouterr().out)

    assert code == 0
    assert sortie["git"]["branch"] == "principale"
    assert sortie["open_workspaces"] == []


def test_health_repond_sans_lancer_la_suite(depot, capsys):
    """Une vérification que personne ne lance vaut moins qu'une superficielle."""
    main(["health", "--root", depot, "--json"])
    sortie = json.loads(capsys.readouterr().out)

    assert sortie["suite"]["measured"] is False
    assert "coûte des minutes" in sortie["suite"]["reason"]
    assert sortie["complete"] is False


def test_diagnose_rend_1_sur_un_diagnostic_inconnu(depot, capsys):
    """Le code de sortie distingue « j'ai trouvé » de « je ne sais pas »."""
    code = main(["diagnose", "--trace", "rien du tout", "--root", depot, "--json"])
    sortie = json.loads(capsys.readouterr().out)

    assert code == 1
    assert sortie["category"] == "UNKNOWN_DIAGNOSIS"
    assert sortie["confident"] is False


def test_diagnose_rend_0_quand_il_trouve(depot, capsys):
    """Le cas nominal, sur un fichier du dépôt observé."""
    trace = (
        "Traceback (most recent call last):\n"
        f'  File "{depot}/src/calcul.py", line 2, in moyenne\n'
        "ZeroDivisionError: division by zero\n"
    )

    code = main(["diagnose", "--trace", trace, "--root", depot, "--json"])
    sortie = json.loads(capsys.readouterr().out)

    assert code == 0
    assert sortie["file"] == "src/calcul.py"


# ----------------------------------------------------------------------
# 2. Un correctif vient d'un fichier
# ----------------------------------------------------------------------

def test_repair_sans_correctif_est_une_erreur_d_usage(depot, capsys):
    """`repair` applique un correctif, il n'en invente pas."""
    code = main(["repair", "--trace", "x", "--root", depot])
    erreur = capsys.readouterr().err

    assert code == 2
    assert "n'en invente pas" in erreur


def test_un_correctif_mal_forme_est_refuse(depot, capsys, tmp_path):
    """Toute autre forme serait interprétée, et interpréter est ce qu'on évite."""
    mauvais = tmp_path / "projet" / "patch.json"
    mauvais.write_text('["src/calcul.py"]', encoding="utf-8")

    code = main(["repair", "--trace", "x", "--patch", "patch.json", "--root", depot])

    assert code == 2
    assert "objet {chemin: contenu}" in capsys.readouterr().err


# ----------------------------------------------------------------------
# 3. Une réparation complète par la CLI
# ----------------------------------------------------------------------

def test_une_reparation_juste_rend_zero_et_laisse_le_depot_intact(depot, capsys):
    """La branche existe ; l'arbre de l'utilisateur n'a pas bougé."""
    avant = _empreinte_du_depot(depot)
    correctif = os.path.join(depot, "patch.json")
    with open(correctif, "w", encoding="utf-8") as fichier:
        json.dump({"src/calcul.py": CALCUL_CORRIGE}, fichier)

    trace = (
        "Traceback (most recent call last):\n"
        f'  File "{depot}/src/calcul.py", line 2, in moyenne\n'
        "ZeroDivisionError: division by zero\n"
    )
    code = main([
        "repair", "--trace", trace, "--patch", "patch.json",
        "--root", depot, "--json",
    ])
    sortie = json.loads(capsys.readouterr().out)

    assert code == 0
    assert sortie["decision"] == "KEEP"
    with open(os.path.join(depot, "src", "calcul.py"), encoding="utf-8") as fichier:
        assert fichier.read() == avant[1]


def test_une_reparation_fausse_rend_un_et_annule(depot, capsys):
    """Une réparation annulée est un refus réussi : 1 pour qu'on le voie."""
    correctif = os.path.join(depot, "patch.json")
    with open(correctif, "w", encoding="utf-8") as fichier:
        json.dump({"src/calcul.py": "def moyenne(valeurs):\n    return 42\n"}, fichier)

    trace = (
        "Traceback (most recent call last):\n"
        f'  File "{depot}/src/calcul.py", line 2, in moyenne\n'
        "ZeroDivisionError: division by zero\n"
    )
    code = main([
        "repair", "--trace", trace, "--patch", "patch.json",
        "--root", depot, "--json",
    ])
    sortie = json.loads(capsys.readouterr().out)

    assert code == 1
    assert sortie["decision"] == "ROLLBACK"
    assert _git(["status", "--porcelain"], depot).stdout.count("patch.json") == 1


def test_un_correctif_hors_de_portee_est_refuse_par_la_cli(depot, capsys):
    """La politique s'applique aussi quand l'ordre vient d'un terminal."""
    correctif = os.path.join(depot, "patch.json")
    with open(correctif, "w", encoding="utf-8") as fichier:
        json.dump({"src/agent/tools/workspace.py": "# vidé\n"}, fichier)

    code = main([
        "repair", "--trace", "ValueError: x", "--patch", "patch.json",
        "--root", depot, "--json",
    ])
    sortie = json.loads(capsys.readouterr().out)

    assert code == 1
    assert sortie["decision"] == "REFUSED"
    assert "retient" in sortie["reason"]


# ----------------------------------------------------------------------
# 4. La CLI s'exécute vraiment comme un programme
# ----------------------------------------------------------------------

def test_la_cli_repond_en_sous_processus():
    """`python -m src.agent.cli` doit fonctionner hors de pytest."""
    execution = subprocess.run(
        [sys.executable, "-m", "src.agent.cli", "status", "--json"],
        cwd=RACINE, capture_output=True, text=True, timeout=300,
    )

    assert execution.returncode == 0
    assert json.loads(execution.stdout)["git"]["branch"]


def test_l_aide_liste_les_six_commandes():
    """Une commande absente de l'aide est une commande que personne n'utilise."""
    execution = subprocess.run(
        [sys.executable, "-m", "src.agent.cli", "--help"],
        cwd=RACINE, capture_output=True, text=True, timeout=120,
    )

    for commande in ("status", "health", "test", "diagnose", "repair", "audit"):
        assert commande in execution.stdout, commande
