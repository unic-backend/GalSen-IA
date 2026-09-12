"""
Configuration partagée pour pytest.

Fournit les fixtures communes utilisées par les tests du projet GalSen IA.
"""

import contextlib
import os
import sys

import pytest

# Chemin racine du projet
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope="session")
def engine():
    """
    Construit un ToolEngine à partir du registre tools/tools.yaml.

    Utilisé par test_tool_engine.py, test_search_types.py et d'autres
    tests qui nécessitent une instance du moteur d'outils.
    """
    from src.tool.tool_engine import ToolEngine

    registry_path = os.path.join(PROJECT_ROOT, "tools", "tools.yaml")
    return ToolEngine(registry_path)


# ---------------------------------------------------------------------------
# Capacité absente : le double contrôlé (2026-09-12)
# ---------------------------------------------------------------------------
#
# Une trentaine de tests affirmaient « quand l'outil manque, la plateforme le
# dit » en s'appuyant sur le fait que **ce bac à sable-là** ne l'avait pas
# installé. Mesuré le 2026-09-10 : le jour où `faster-whisper` et un OpenCV
# complet sont arrivés dans l'image, 24 tests ont échoué et 6 ont erré, sans
# qu'une seule ligne de `src/` ait bougé — le diff de la branche touchait neuf
# fichiers de règles et de documentation.
#
# Un test dont le verdict dépend de ce qui traîne dans l'environnement ne
# mesure pas le code : il mesure la machine. Et il échoue précisément dans le
# sens le plus coûteux — il devient rouge quand l'environnement **gagne** une
# capacité, c'est-à-dire quand rien n'a cassé.
#
# `module_absent` rend l'absence explicite : `None` dans `sys.modules` fait
# lever `ImportError` à l'import, exactement comme un paquet non installé, quoi
# que la machine ait réellement. Ce n'est pas mocker la chose sous test — le
# chemin d'exécution testé (la sonde, le refus, le rapport) reste entièrement
# réel ; c'est l'environnement qui est contrôlé au lieu d'être subi.

@contextlib.contextmanager
def module_absent(*noms: str):
    """
    Rend des modules non importables pendant la durée du bloc.

    Args:
        *noms: Noms de modules de premier niveau (`"cv2"`, `"faster_whisper"`).
            Leurs sous-modules déjà importés sont retirés eux aussi, sans quoi
            un `import cv2.dnn` déjà résolu continuerait de réussir.

    Yields:
        None. L'état de `sys.modules` est restauré à la sortie, y compris si le
        bloc lève.
    """
    sauvegarde = {}
    for nom in noms:
        prefixe = nom + "."
        for cle in [c for c in sys.modules if c == nom or c.startswith(prefixe)]:
            sauvegarde[cle] = sys.modules.pop(cle)
        # `None` dans `sys.modules` est la façon documentée de bloquer un
        # import : CPython lève « import of X halted; None in sys.modules ».
        sys.modules[nom] = None
    try:
        yield
    finally:
        for nom in noms:
            sys.modules.pop(nom, None)
        sys.modules.update(sauvegarde)


@pytest.fixture
def sans_module():
    """
    Donne `module_absent` aux tests, sans qu'ils aient à importer `conftest`.

    Returns:
        Le gestionnaire de contexte `module_absent`.
    """
    return module_absent


@pytest.fixture
def capacite_forcee(monkeypatch):
    """
    Force l'état rendu par une sonde de capacité média, sans rien (dés)installer.

    Le pendant de `module_absent` pour les capacités qui ne tiennent pas à un
    import : `audio_analysis` interroge le binaire `ffmpeg`, `transcription`
    passe par le registre du VOLET 32. Les tests qui affirment « quand cette
    capacité manque, la chaîne s'arrête ici » mesuraient donc ce que le bac à
    sable avait sous la main — et sont devenus rouges le jour où il a gagné un
    `ffmpeg` complet, alors que rien n'avait cassé.

    Ce qui reste réel : `probe()`, sa table, son `try/except`, `CONSEQUENCES`,
    et tout le code appelant. Seule la réponse de la sonde est posée.

    Returns:
        `forcer(nom, etat, raison=None, **detail)`. Un nom de capacité inconnu
        est refusé : sans cela, une faute de frappe ne forcerait rien et le
        test passerait pour la mauvaise raison.
    """
    def forcer(nom: str, etat: str, raison: str = None, **detail):
        from src.media.core import capabilities

        if nom not in capabilities.SONDES:
            raise KeyError(
                f"Capacité « {nom} » non déclarée. Déclarées : "
                f"{sorted(capabilities.SONDES)}."
            )
        resultat = {
            "state": etat,
            "reason": raison or f"Capacité forcée à {etat} par le test.",
            "detail": detail,
        }
        monkeypatch.setitem(capabilities.SONDES, nom, lambda: dict(resultat))

    return forcer
