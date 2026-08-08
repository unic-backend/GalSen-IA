"""
Garde-fou sur la convention d'imports (`docs/architecture/overview.md`).

À l'intérieur de `src/`, tout import interne s'écrit `from src.<module>`. La
règle n'est pas cosmétique : quand `src/` est aussi dans `sys.path`, le même
fichier devient importable sous deux noms, Python en fait **deux modules
distincts**, et les classes qu'ils définissent cessent d'être égales.
`isinstance` échoue, deux membres d'énumération de même nom ne sont plus le même
objet — et le défaut se manifeste très loin de sa cause.

Ce fichier existe parce que la règle a déjà été enfreinte deux fois : une
première dans le moteur de mémoire et les magasins SQLite historiques, une
seconde dans les services calendar / cloud / email / notification / file
arrivés par une branche parallèle. Les deux fois, des tests verts passaient
à côté, parce qu'ils importaient eux aussi par le nom nu.
"""

import ast
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RACINE = pathlib.Path(__file__).resolve().parent.parent
SOURCES = RACINE / "src"

# Les paquets internes de `src/`. Un import qui commence par l'un de ces noms
# sans le préfixe `src.` désigne le même fichier sous une seconde identité.
PAQUETS_INTERNES = sorted(
    chemin.name
    for chemin in SOURCES.iterdir()
    if chemin.is_dir() and (chemin / "__init__.py").exists()
)


def _modules_python():
    """Retourne tous les fichiers Python livrés sous `src/`."""
    return [
        chemin
        for chemin in SOURCES.rglob("*.py")
        if "__pycache__" not in chemin.parts
    ]


def _imports_de(chemin: pathlib.Path):
    """Retourne les modules importés par un fichier, imports relatifs exclus."""
    arbre = ast.parse(chemin.read_text(encoding="utf-8"), filename=str(chemin))
    noms = []
    for noeud in ast.walk(arbre):
        if isinstance(noeud, ast.ImportFrom):
            # `level > 0` : import relatif (`from .types import ...`), légitime.
            if noeud.level == 0 and noeud.module:
                noms.append(noeud.module)
        elif isinstance(noeud, ast.Import):
            noms.extend(alias.name for alias in noeud.names)
    return noms


class TestConventionDImports:
    """Aucun module de `src/` ne doit importer un paquet interne par son nom nu."""

    def test_des_paquets_internes_sont_detectes(self):
        """Sans cette liste, le test ne vérifierait rien du tout."""
        assert "storage" in PAQUETS_INTERNES
        assert "services" in PAQUETS_INTERNES

    def test_aucun_import_nu(self):
        """Un import `from storage...` crée une seconde identité du module."""
        fautifs = []
        for chemin in _modules_python():
            for module in _imports_de(chemin):
                racine = module.split(".", 1)[0]
                if racine in PAQUETS_INTERNES:
                    fautifs.append(f"{chemin.relative_to(RACINE)} : {module}")

        assert fautifs == [], (
            "Imports internes sans le préfixe `src.` — ils font exister le même "
            "module deux fois :\n  " + "\n  ".join(fautifs)
        )

    def test_le_paquet_ne_touche_pas_au_chemin(self):
        """`src/__init__.py` ne doit pas se rendre importable par son contenu.

        Ajouter `src/` à `sys.path` fait résoudre les imports nus, ce qui rend
        la violation invisible au lieu de la corriger.

        La vérification porte sur le **code**, pas sur le texte : le fichier
        mentionne `sys.path` en commentaire pour expliquer pourquoi il n'y
        touche pas, et interdire le mot confondrait l'explication avec la faute.
        """
        arbre = ast.parse((SOURCES / "__init__.py").read_text(encoding="utf-8"))

        corps = arbre.body
        # Une docstring seule est admise ; tout le reste est de la logique.
        if corps and isinstance(corps[0], ast.Expr) and isinstance(corps[0].value, ast.Constant):
            corps = corps[1:]

        assert corps == [], (
            "src/__init__.py exécute du code. S'il ajoute `src/` à sys.path, il "
            "rend les imports nus fonctionnels et la violation invisible."
        )


class TestIdentiteUnique:
    """La conséquence concrète, vérifiée plutôt que décrite."""

    @pytest.mark.parametrize("nom_nu", ["storage", "services", "memory_engine"])
    def test_le_nom_nu_ne_resout_pas(self, nom_nu):
        """Si ce nom résout, deux copies de chaque classe coexistent."""
        import importlib

        with pytest.raises(ModuleNotFoundError):
            importlib.import_module(nom_nu)

    def test_une_seule_classe_par_fichier(self):
        """Deux chemins d'import vers un même fichier casseraient `isinstance`."""
        from src.storage.sqlite_notification_store import SQLiteNotificationStore
        from src.services.notification.manager import NotificationManagerImpl

        gestionnaire = NotificationManagerImpl(store=SQLiteNotificationStore(":memory:"))
        assert isinstance(gestionnaire._store, SQLiteNotificationStore)
