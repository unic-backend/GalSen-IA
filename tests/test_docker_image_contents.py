"""
L'image de production contient-elle ce que le code lit ? (audit de déploiement, D1)

Le `Dockerfile` ne copiait que `src/` et `tools/`. `RouterEngine` lit pourtant
`config/settings.yaml`, `agents/registry.yaml` et `workflows/workflows.yaml`, et
importe les agents par leur chemin de module (`agents.planner.agent`). Les
routes `/workflow/*` échouaient donc dans le conteneur **tout en passant en
local**, et rien ne le montrait : la CI ne construit pas l'image.

Ces tests ne construisent pas l'image non plus — Docker n'est pas disponible
partout où la suite tourne. Ils comparent ce que le code lit à ce que le
`Dockerfile` copie, ce qui est la partie qui se trompait.
"""

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
DOCKERFILE = RACINE / "Dockerfile"

# Répertoires attendus dans l'image, avec la raison de leur présence. Une liste
# nommée plutôt que déduite : le test suivant, lui, part du code et attrape ce
# que cette liste oublierait.
REPERTOIRES_REQUIS = {
    "src": "le code de l'application",
    "tools": "les outils et leur registre (tools/tools.yaml)",
    "config": "config/settings.yaml, lu par ConfigLoader",
    "agents": "agents/registry.yaml et les modules Python des agents",
    "workflows": "workflows/workflows.yaml, lu par WorkflowLoader",
}

# Chemins racine assemblés dans le code : os.path.join(project_root, 'x', ...)
_JOINTURE_RACINE = re.compile(r"os\.path\.join\(\s*project_root\s*,\s*['\"]([a-z_]+)['\"]")


def _repertoires_copies() -> set:
    """Retourne les répertoires racine copiés par le Dockerfile."""
    contenu = DOCKERFILE.read_text(encoding="utf-8")
    copies = re.findall(r"^COPY\s+(?!--from)(\S+)\s", contenu, re.M)
    return {chemin.rstrip("/") for chemin in copies if not chemin.endswith(".txt")}


def _repertoires_lus_par_le_code() -> set:
    """Retourne les répertoires racine que le code assemble à l'exécution."""
    trouves = set()
    for chemin in (RACINE / "src").rglob("*.py"):
        trouves.update(_JOINTURE_RACINE.findall(chemin.read_text(encoding="utf-8")))
    return trouves


@pytest.mark.parametrize("repertoire,raison", sorted(REPERTOIRES_REQUIS.items()))
def test_le_repertoire_est_dans_l_image(repertoire, raison):
    """Chaque répertoire nécessaire à l'exécution doit être copié."""
    assert repertoire in _repertoires_copies(), (
        f"`{repertoire}/` manque dans l'image alors qu'il porte {raison}"
    )


def test_aucun_repertoire_lu_par_le_code_n_est_oublie():
    """
    Le garde-fou réel : il part du **code**, pas d'une liste écrite à la main.

    Un futur `os.path.join(project_root, 'prompts', ...)` fera échouer ce test
    tant que `prompts/` n'aura pas été ajouté au Dockerfile — c'est exactement
    l'oubli qui a mis les routes de workflow en panne dans l'image.
    """
    oublies = sorted(_repertoires_lus_par_le_code() - _repertoires_copies())

    assert oublies == [], (
        "Le code lit ces répertoires à l'exécution et l'image ne les contient pas : "
        + ", ".join(oublies)
    )


def test_les_registres_existent_reellement():
    """
    Copier un répertoire vide ne prouve rien : les trois fichiers doivent exister.
    """
    for fichier in ("config/settings.yaml", "agents/registry.yaml",
                    "workflows/workflows.yaml", "tools/tools.yaml"):
        assert (RACINE / fichier).is_file(), f"{fichier} est référencé et absent du dépôt"


def test_les_agents_declares_sont_des_modules_presents():
    """
    `agents/` est copié pour ses YAML **et** pour ses modules Python : le
    répartiteur importe `agents.planner.agent`, pas un fichier de déclaration.
    """
    import yaml

    registre = yaml.safe_load((RACINE / "agents" / "registry.yaml").read_text(encoding="utf-8"))
    modules = [
        agent["module"] for agent in registre["agents"]
        if agent.get("module", "").startswith("agents.")
    ]

    assert modules, "aucun agent déclaré comme module Python : la mesure est à refaire"
    for module in modules:
        chemin = RACINE / Path(module.replace(".", "/") + ".py")
        assert chemin.is_file(), f"{module} est déclaré et son fichier est absent"
