"""
L'instrument qui rend « la capacité est absente » mesurable (2026-09-12).

Il existe parce que trente tests de ce dépôt mesuraient le bac à sable au lieu
de mesurer le code : ils affirmaient « sans Whisper, l'audio est refusé » en
comptant sur le fait que Whisper n'était pas installé *ici*. Le jour où il l'a
été, ils sont devenus rouges alors que rien n'avait cassé.

Un instrument non vérifié ne vaut pas mieux que ce qu'il remplace : s'il ne
bloquait rien, les tests qui l'utilisent passeraient pour la mauvaise raison —
exactement le défaut qu'il corrige, retourné. D'où ce fichier.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from conftest import module_absent  # noqa: E402

# Un module de la bibliothèque standard, toujours installé, jamais optionnel :
# le sujet du test est l'instrument, pas la disponibilité de son cobaye.
COBAYE = "json"


def test_un_module_installe_devient_non_importable():
    """L'absence simulée doit lever exactement ce qu'une absence réelle lève."""
    import json  # noqa: F401 - la preuve qu'il est bien là avant le bloc

    with module_absent(COBAYE):
        with pytest.raises(ImportError):
            import json  # noqa: F401


def test_le_module_revient_apres_le_bloc():
    """Un instrument qui ne se range pas casse les tests suivants du fichier."""
    import json as avant

    with module_absent(COBAYE):
        pass

    import json as apres

    assert apres is avant, "le module d'origine doit être rendu, pas réimporté"


def test_le_module_revient_meme_si_le_bloc_leve():
    """
    Le cas qui compte : un test qui échoue à l'intérieur du bloc.

    Sans `finally`, une seule assertion ratée empoisonnerait tout le reste de
    la session — et le coupable serait introuvable.
    """
    with pytest.raises(RuntimeError):
        with module_absent(COBAYE):
            raise RuntimeError("échec à l'intérieur du bloc")

    import json  # noqa: F401


def test_un_sous_module_deja_importe_est_bloque_lui_aussi():
    """
    `import json.decoder` résolu plus tôt resterait dans `sys.modules`.

    Le laisser rendrait l'absence partielle, donc fausse : le code sous test
    pourrait encore atteindre la capacité qu'on prétend lui retirer.
    """
    import json.decoder  # noqa: F401

    with module_absent(COBAYE):
        assert "json.decoder" not in sys.modules
        with pytest.raises(ImportError):
            import json.decoder  # noqa: F401

    import json.decoder  # noqa: F401

    assert sys.modules["json.decoder"] is not None


def test_un_module_jamais_importe_ne_laisse_pas_de_trace():
    """
    Le contre-test du rangement.

    Bloquer un module absent puis laisser un `None` derrière soi le rendrait
    définitivement inimportable pour le reste de la session — une panne bien
    pire que celle qu'on simulait.
    """
    nom = "un_module_qui_n_existe_pas_galsen"
    assert nom not in sys.modules

    with module_absent(nom):
        with pytest.raises(ImportError):
            __import__(nom)

    assert nom not in sys.modules


def test_plusieurs_modules_a_la_fois():
    """Une capacité tient souvent à deux paquets : Whisper, ou son alternative."""
    with module_absent("json", "base64"):
        with pytest.raises(ImportError):
            import json  # noqa: F401
        with pytest.raises(ImportError):
            import base64  # noqa: F401

    import base64  # noqa: F401
    import json  # noqa: F401


def test_la_fixture_donne_le_meme_outil(sans_module):
    """La fixture existe pour éviter un import de `conftest` dans chaque test."""
    assert sans_module is module_absent
