"""
Tests de la documentation des paquets (VOLET 03, chapitre 07).

Le chapitre exige que chaque module majeur documente son objectif, ses
responsabilités, ses interfaces publiques, ses dépendances, sa configuration et
ses limites connues. Trois paquets sur dix-huit n'avaient **aucune** docstring :
ce test empêche qu'un nouveau paquet arrive dans le même état.
"""

import ast
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
SRC = RACINE / "src"


def _paquets():
    """Retourne les paquets majeurs de `src/`, c'est-à-dire ses sous-dossiers importables."""
    return sorted(p for p in SRC.iterdir() if p.is_dir() and (p / "__init__.py").exists())


def _docstring(paquet: Path) -> str:
    """Retourne la docstring de module d'un paquet, chaîne vide si absente."""
    arbre = ast.parse((paquet / "__init__.py").read_text(encoding="utf-8"))
    return ast.get_docstring(arbre) or ""


def test_chaque_paquet_a_une_docstring():
    """Un paquet sans docstring ne dit ni ce qu'il fait ni ce qu'il ne fait pas."""
    muets = [p.name for p in _paquets() if not _docstring(p).strip()]
    assert muets == [], "Paquets sans docstring de module : " + ", ".join(muets)


def test_la_docstring_dit_a_quoi_sert_le_paquet():
    """Une docstring d'un mot — « Tool package » — ne documente rien."""
    trop_courtes = [p.name for p in _paquets() if len(_docstring(p).split()) < 8]
    assert trop_courtes == [], (
        "Docstrings trop courtes pour décrire un paquet : " + ", ".join(trop_courtes)
    )


def test_les_paquets_redocumentes_couvrent_les_six_champs():
    """Les trois paquets repris en phase 7.1 portent la structure du chapitre 07.

    Le test ne l'exige que d'eux : imposer les six champs aux quinze autres d'un
    coup produirait quinze docstrings écrites pour satisfaire un test.
    """
    attendus = ("Responsabilités", "Interfaces publiques", "Dépendances",
                "Configuration", "Limites connues")
    for nom in ("memory_engine", "router", "tool"):
        texte = _docstring(SRC / nom)
        manquants = [champ for champ in attendus if champ not in texte]
        assert manquants == [], f"{nom} : champs absents — {', '.join(manquants)}"
