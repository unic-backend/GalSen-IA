"""
Contrôle humain sur les actions irréversibles (VOLET 01, chapitre 03).

La constitution énonce une règle finale : « aucune fonctionnalité ne peut être
implémentée si elle retire un contrôle humain significatif sur les décisions
importantes ». Le portillon existe (ADR-006, `BaseAgent.approval_required`), il
est testé, et **aucun agent ne l'active**.

Mesuré, c'est aujourd'hui **correct** : les neuf agents lisent, analysent et
rapportent — `read`, `search`, `list`, `stat`, `exists`, `git summary`. Aucun
n'écrit, ne déploie, ni n'envoie quoi que ce soit.

Ce qui manque, c'est ce qui maintient cet état. `approval_required` vaut `False`
par défaut : le jour où un agent appellera un outil qui modifie quelque chose,
il le fera sans portillon et rien ne le signalera. Ce test est ce signal.
"""

import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]

# Opérations d'outils qui changent quelque chose hors de la plateforme, ou de
# façon irréversible à l'intérieur. Un agent qui en appelle une prend une
# décision dont un humain doit répondre (chapitre 03).
OPERATIONS_MUTANTES = {
    "filesystem": {"append", "copy", "delete", "mkdir", "move", "write"},
    "git": {"add", "checkout", "commit", "create_branch", "push"},
    "github": {"create_issue", "create_pull_request", "comment"},
    "api": {"delete", "patch", "post", "put"},
    "docker": {"remove_container", "run_container", "stop_container"},
    "calendar": {"add_event", "delete_event"},
    "memory": {"delete", "store", "update"},
    "rag": {"add", "delete", "update"},
    "email": {"send"},
    "terminal": {"run", "execute"},
}

APPEL_OUTIL = re.compile(r'use_tool\(\s*["\'](\w+)["\']\s*,\s*["\'](\w+)["\']')


def _agents():
    """Retourne les modules d'agents livrés, avec leur source."""
    return [(chemin.parent.name, chemin.read_text(encoding="utf-8"))
            for chemin in sorted(RACINE.joinpath("agents").glob("*/agent.py"))]


def _appelle_le_portillon(source: str) -> bool:
    """Indique si l'agent déclare exiger une approbation humaine."""
    return re.search(r"approval_required\s*[:=].*True", source) is not None


def test_des_agents_sont_bien_livres():
    """Un test qui n'énumère rien passerait toujours."""
    assert len(_agents()) >= 9


@pytest.mark.parametrize("nom,source", _agents(), ids=lambda valeur: valeur if isinstance(valeur, str) and "\n" not in valeur else "")
def test_un_agent_qui_modifie_quelque_chose_passe_par_le_portillon(nom, source):
    """
    La règle finale du chapitre 03, rendue exécutable.

    Tant qu'un agent se contente de lire, aucun portillon n'est requis — exiger
    une approbation humaine pour lire un fichier ferait abandonner le portillon
    au premier jour. Dès qu'il écrit, déploie ou envoie, l'approbation devient
    la condition posée par la constitution.
    """
    mutations = [
        f"{outil}.{operation}"
        for outil, operation in APPEL_OUTIL.findall(source)
        if operation in OPERATIONS_MUTANTES.get(outil, ())
    ]

    if not mutations:
        return

    assert _appelle_le_portillon(source), (
        f"L'agent '{nom}' appelle {', '.join(sorted(set(mutations)))} sans "
        f"`approval_required = True` : une action irréversible échapperait au "
        f"portillon humain (VOLET 01, ch. 03 — ADR-006)"
    )


def test_l_etat_mesure_est_bien_celui_qu_on_croit():
    """
    Verrouille la mesure elle-même.

    Sans ce test, la règle ci-dessus passerait aussi si plus aucun agent
    n'appelait d'outil du tout — un test vert pour une mauvaise raison.
    """
    appels = [(nom, outil, operation)
              for nom, source in _agents()
              for outil, operation in APPEL_OUTIL.findall(source)]

    assert len(appels) >= 10, "les agents n'appellent plus d'outils : mesure à refaire"
    mutations = [entree for entree in appels
                 if entree[2] in OPERATIONS_MUTANTES.get(entree[1], ())]
    assert mutations == [], (
        "Un agent modifie désormais quelque chose : vérifier qu'il passe par le "
        f"portillon et mettre à jour docs/architecture/constitution.md — {mutations}"
    )


def test_le_portillon_reste_ferme_par_defaut():
    """
    `approval_required = False` par défaut est le bon choix — la plupart des
    agents lisent — mais c'est aussi ce qui rend le test précédent nécessaire.
    """
    from src.agent.base_agent import BaseAgent

    assert BaseAgent.approval_required is False
