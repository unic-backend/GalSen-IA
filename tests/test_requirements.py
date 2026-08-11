"""
Les dépendances déclarées doivent correspondre à celles que le code importe.

Deux défauts ont motivé ces tests, tous deux invisibles pour la suite existante
parce qu'elle tourne dans un environnement où tout est déjà installé :

- **Les versions n'étaient pas figées** (`>=`). La même étiquette git produisait
  deux images différentes à six mois d'écart, et le jour où l'une casse, plus
  moyen de dire laquelle a bougé. Une publication doit se reconstruire à
  l'identique.
- **L'image de production installait les outils de test.** `requirements.txt`
  portait pytest, ses greffons et le client HTTP de test ; ils partaient dans le
  conteneur exposé au réseau. Du code qui ne sert jamais en production reste du
  code à mettre à jour et à surveiller.

Le contrôle central est celui qui **dérive** la liste attendue du code lui-même :
séparer exécution et développement à la main se défait au premier import ajouté,
et l'erreur n'apparaîtrait qu'à la construction de l'image — c'est-à-dire nulle
part, puisque `docker` n'est pas disponible ici.
"""

import ast
import os
import re
import sys
from importlib.metadata import packages_distributions
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent

# Répertoires dont les imports doivent être couverts par les dépendances
# d'exécution : ce sont ceux que l'image de production embarque.
SOURCES_EXECUTION = ("src", "agents", "tools")

# Modules du dépôt lui-même : ils ne se déclarent pas comme dépendances.
PREMIERE_PARTIE = {
    "src", "agents", "tools", "scripts", "config", "workflows", "tests",
    "prompts", "serveur_cerveau",
}

# Dépendances utilisées uniquement par la suite de tests.
DEVELOPPEMENT = {"pytest", "pytest-asyncio", "pytest-cov", "httpx2"}


def _lire(nom: str) -> str:
    """Retourne le contenu d'un fichier d'exigences."""
    return (RACINE / nom).read_text(encoding="utf-8")


def _declarees(nom: str) -> set:
    """Retourne les distributions déclarées dans un fichier d'exigences."""
    declarees = set()
    for ligne in _lire(nom).splitlines():
        ligne = ligne.split("#", 1)[0].strip()
        if not ligne or ligne.startswith("-"):
            continue
        declarees.add(re.split(r"[=<>!~\[]", ligne, 1)[0].strip().lower())
    return declarees


def _modules_importes(racines) -> set:
    """
    Retourne les modules de premier niveau importés par le code.

    L'arbre syntaxique est lu plutôt que le texte : une chaîne contenant
    « import numpy » dans une docstring ne doit pas compter comme un import.
    """
    modules = set()
    for racine in racines:
        for chemin in (RACINE / racine).rglob("*.py"):
            try:
                arbre = ast.parse(chemin.read_text(encoding="utf-8"))
            except (OSError, SyntaxError):  # pragma: no cover - fichier illisible
                continue
            for noeud in ast.walk(arbre):
                if isinstance(noeud, ast.Import):
                    modules.update(alias.name.split(".")[0] for alias in noeud.names)
                elif isinstance(noeud, ast.ImportFrom):
                    if noeud.level == 0 and noeud.module:
                        modules.add(noeud.module.split(".")[0])
    return modules


def _distributions(modules) -> set:
    """Traduit des noms de modules en noms de distributions installées."""
    table = packages_distributions()
    distributions = set()
    for module in modules:
        if module in sys.stdlib_module_names or module in PREMIERE_PARTIE:
            continue
        for distribution in table.get(module, []):
            distributions.add(distribution.lower())
    return distributions


def test_toute_dependance_importee_par_le_code_est_declaree():
    """
    Le contrôle qui rend la séparation sûre.

    Sans lui, déplacer un paquet vers `requirements-dev.txt` par erreur ne se
    verrait qu'au démarrage du conteneur, en production.
    """
    attendues = _distributions(_modules_importes(SOURCES_EXECUTION))
    manquantes = sorted(attendues - _declarees("requirements.txt"))

    assert manquantes == [], (
        f"importées par {'/'.join(SOURCES_EXECUTION)} mais absentes de "
        f"requirements.txt : {manquantes}"
    )


def test_les_outils_de_test_ne_sont_pas_dans_l_image():
    """pytest n'a rien à faire dans un conteneur exposé au réseau."""
    execution = _declarees("requirements.txt")

    assert not (execution & DEVELOPPEMENT), (
        f"outils de test dans les dépendances d'exécution : "
        f"{sorted(execution & DEVELOPPEMENT)}"
    )


def test_les_outils_de_test_restent_disponibles_pour_la_suite():
    """Le contre-test : les avoir sortis ne doit pas les avoir perdus."""
    developpement = _declarees("requirements-dev.txt")

    assert DEVELOPPEMENT <= developpement, (
        f"absents de requirements-dev.txt : {sorted(DEVELOPPEMENT - developpement)}"
    )


def test_les_versions_sont_figees():
    """
    Une publication doit se reconstruire à l'identique.

    `>=` laisse la construction choisir, donc deux images différentes pour la
    même étiquette git.
    """
    for fichier in ("requirements.txt", "requirements-dev.txt"):
        for ligne in _lire(fichier).splitlines():
            ligne = ligne.split("#", 1)[0].strip()
            if not ligne or ligne.startswith("-"):
                continue
            assert "==" in ligne, f"{fichier} : « {ligne} » n'est pas figée"


def test_le_dockerfile_n_installe_que_l_execution():
    """L'image ne doit pas installer le fichier de développement."""
    instructions = [
        ligne for ligne in _lire("Dockerfile").splitlines()
        if ligne.strip() and not ligne.lstrip().startswith("#")
    ]
    dockerfile = "\n".join(instructions)

    assert "requirements.txt" in dockerfile
    assert "requirements-dev.txt" not in dockerfile


def test_la_ci_installe_le_fichier_de_developpement():
    """Sans les outils de test, la suite ne peut pas tourner en CI."""
    for workflow in ("tests.yml", "release.yml"):
        contenu = _lire(os.path.join(".github", "workflows", workflow))
        assert "requirements-dev.txt" in contenu, f"{workflow} n'installe pas les outils de test"
