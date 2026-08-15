"""
Les chiffres publiés sont ceux qui sont mesurés (phase 70.1).

`CLAUDE.md` et `docs/architecture/overview.md` annonçaient **76 routes** et
**3238 tests** ; la mesure du 2026-08-15 en donne 127 et 4327. Les deux fichiers
promettent pourtant d'être « kept synchronized with the measured state ». Un
chiffre périmé dans le document qu'un agent lit en premier est pire qu'aucun
chiffre : il est cité, il fait décider, et rien ne le contredit.

Ces tests confrontent donc ce qui est écrit à ce qui est comptable **maintenant**.
Ils ne vérifient pas une valeur figée — ils vérifient que la valeur écrite est
celle du dépôt le jour où la suite tourne.
"""

import os
import re
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _lire(chemin: str) -> str:
    """Lit un document du dépôt."""
    with open(os.path.join(RACINE, chemin), encoding="utf-8") as fichier:
        return fichier.read()


def _nombre_annonce(texte: str, motif: str) -> int:
    """Extrait le nombre annoncé par un motif, ou échoue en le disant."""
    trouve = re.search(motif, texte)
    assert trouve, f"Aucun nombre annoncé pour « {motif} »"
    return int(trouve.group(1).replace(" ", "").replace(" ", ""))


@pytest.fixture(scope="module")
def routes_reelles() -> int:
    """
    Le nombre de **routes d'API** réellement servies.

    Compté sur `APIRoute`, comme le fait déjà `test_gateway_surface.py`, et non
    sur tout ce qui porte des méthodes : `/docs`, `/redoc`, `/openapi.json` et
    la redirection OAuth sont générées par le cadre et peuvent être désactivées
    par configuration. Les inclure faisait dire « 127 » à une mesure qui donnait
    123 dès qu'un autre test les éteignait — un chiffre qui dépend de l'ordre
    des tests n'est pas une mesure.
    """
    from fastapi.routing import APIRoute

    from src.api.server import app

    return len([route for route in app.routes if isinstance(route, APIRoute)])


# ----------------------------------------------------------------------
# 1. Les routes
# ----------------------------------------------------------------------

def test_le_nombre_de_routes_annonce_est_le_nombre_servi(routes_reelles):
    """Un lecteur qui compte doit trouver ce qui est écrit."""
    annonce = _nombre_annonce(
        _lire("docs/architecture/overview.md"), r"\*\*(\d+) routes\*\*",
    )

    assert annonce == routes_reelles


def test_claude_md_annonce_le_meme_nombre_de_routes(routes_reelles):
    """Deux documents qui se contredisent valent moins qu'un seul."""
    annonce = _nombre_annonce(_lire("CLAUDE.md"), r"\*\*(\d+) API routes\*\*")

    assert annonce == routes_reelles


# ----------------------------------------------------------------------
# 2. Les agents, les outils, les ADR
# ----------------------------------------------------------------------

def test_le_nombre_d_agents_annonce_est_celui_du_registre():
    """Le registre est l'autorité ; le document le cite."""
    with open(os.path.join(RACINE, "agents", "registry.yaml"), encoding="utf-8") as f:
        agents = yaml.safe_load(f)["agents"]

    annonce = _nombre_annonce(_lire("CLAUDE.md"), r"\*\*(\d+) agents\*\*")

    assert annonce == len(agents)


def test_le_nombre_d_outils_annonce_est_celui_des_capacites():
    """Déclaré, pas estimé : c'est `capabilities.yaml` qui tranche."""
    from src.tool.capabilities import load_capabilities

    capacites = load_capabilities()
    annonce = _nombre_annonce(_lire("CLAUDE.md"), r"\*\*(\d+) declared tools\*\*")

    assert annonce == len(capacites.declared_ids())


def test_le_nombre_d_adr_annonce_est_celui_du_repertoire():
    """Un ADR écrit et non compté disparaît de la vue d'ensemble."""
    repertoire = os.path.join(RACINE, "docs", "architecture", "decisions")
    fichiers = [
        nom for nom in os.listdir(repertoire)
        if nom.lower().endswith(".md") and "readme" not in nom.lower()
    ]

    annonce = _nombre_annonce(_lire("CLAUDE.md"), r"(\d+) ADRs")

    assert annonce == len(fichiers)


# ----------------------------------------------------------------------
# 3. Les sous-systèmes
# ----------------------------------------------------------------------

def test_le_nombre_de_sous_systemes_annonce_est_celui_des_sondes():
    """
    Écrit « dix » d'abord, mesuré à neuf : le bac à sable est sondé **dans**
    la sonde des greffons, pas à côté. Corrigé partout plutôt qu'arrondi.
    """
    from src.integration.degradation import SOUS_SYSTEMES

    annonce = re.search(r"plus (\w+) subsystems probed", _lire("CLAUDE.md"))
    assert annonce, "CLAUDE.md n'annonce plus de nombre de sous-systèmes"
    mots = {"nine": 9, "ten": 10, "eleven": 11}

    assert mots[annonce.group(1)] == len(SOUS_SYSTEMES)


def test_la_date_de_mesure_est_nommee():
    """Un chiffre sans date de mesure ne peut pas être jugé périmé."""
    for document in ("CLAUDE.md", "docs/architecture/overview.md"):
        texte = _lire(document)

        assert re.search(r"Measured 20\d\d-\d\d-\d\d", texte), document
