"""
Tests du bornage du journal (VOLET_04 ch. 08, seconde moitié du critère C5).

`logging.FileHandler` n'impose aucune limite. Le fichier avait atteint 6,7 Mo et
43 638 lignes, et avait déjà cassé l'agent de supervision une fois — avant qu'un
`tail` ne soit ajouté pour contourner le symptôme.

Ce que ces tests protègent, dans l'ordre :

1. **Le journal est borné.** C'est la propriété, et elle est vérifiée en
   écrivant réellement de quoi déclencher plusieurs rotations, pas en
   inspectant le type du gestionnaire.
2. **Une configuration fautive reste bornée.** Une variable illisible ou
   absurde doit retomber sur la valeur par défaut, jamais rouvrir la
   croissance infinie.
3. **L'historique survit.** Borner ne doit pas vouloir dire tout perdre : les
   archives gardent les lignes précédentes.
"""

import logging
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.router.logger import Logger, _entier_positif  # noqa: E402


class _Configuration:
    """Configuration minimale demandant l'écriture d'un fichier de journal."""

    def __init__(self, save_history: bool = True):
        self._valeurs = {"logging.level": "info", "logging.save_history": save_history}

    def get(self, cle, defaut=None):
        """Retourne la valeur demandée, ou le défaut."""
        return self._valeurs.get(cle, defaut)


@pytest.fixture
def journal(tmp_path, monkeypatch):
    """Fabrique un logger écrivant dans un répertoire jetable.

    Le gestionnaire est retiré du logger racine en fin de test : le laisser en
    place ferait écrire toutes les suites suivantes dans un `tmp_path` détruit.
    """
    monkeypatch.chdir(tmp_path)
    racine = logging.getLogger()
    handlers_avant = list(racine.handlers)

    def _construire(taille_max=None, archives=None):
        if taille_max is not None:
            monkeypatch.setenv("GALSEN_LOG_MAX_BYTES", str(taille_max))
        if archives is not None:
            monkeypatch.setenv("GALSEN_LOG_BACKUP_COUNT", str(archives))
        return Logger(_Configuration()).get_logger("essai_rotation")

    yield _construire

    for handler in list(racine.handlers):
        if handler not in handlers_avant:
            handler.close()
            racine.removeHandler(handler)


def _ecrire(logger, lignes: int) -> None:
    """Écrit assez de lignes pour dépasser plusieurs fois la borne.

    En `warning` et non en `info` : `logging.basicConfig()` ne fixe pas le
    niveau du logger racine quand celui-ci porte déjà des gestionnaires, ce qui
    est le cas sous pytest. Écrire en `info` produisait un fichier vide, et le
    test du bornage passait alors à vide — un piège qu'il vaut mieux nommer que
    contourner en silence.
    """
    for numero in range(lignes):
        logger.warning("ligne %d, remplissage volontaire pour dépasser la borne", numero)


def _fichiers_de_journal(base: pathlib.Path):
    """Retourne les fichiers de journal présents, courant et archives."""
    return sorted((base / "logs").iterdir())


class TestBornage:
    """La propriété qui compte : le journal cesse de grossir."""

    def test_le_journal_est_borne(self, journal, tmp_path):
        """400 lignes ne doivent pas produire un fichier de 400 lignes."""
        _ecrire(journal(taille_max=2000, archives=2), 400)

        fichiers = _fichiers_de_journal(tmp_path)
        total = sum(f.stat().st_size for f in fichiers)
        # Sans cette borne inférieure, un fichier vide ferait passer le test.
        assert total > 0, "rien n'a été écrit : le test ne prouverait rien"
        # 3 fichiers × 2000 octets, avec la marge de la rotation.
        assert total <= 3 * 2000 + 512, f"{total} octets conservés"

    def test_le_nombre_d_archives_est_respecte(self, journal, tmp_path):
        """Garder les archives sans les compter reviendrait à ne rien borner."""
        _ecrire(journal(taille_max=1000, archives=2), 400)
        assert len(_fichiers_de_journal(tmp_path)) == 3  # courant + 2 archives

    def test_sans_archive_le_fichier_est_seul(self, journal, tmp_path):
        """Zéro archive est un choix légitime sur un support contraint."""
        _ecrire(journal(taille_max=1000, archives=0), 300)
        assert len(_fichiers_de_journal(tmp_path)) == 1

    def test_l_historique_survit_a_la_rotation(self, journal, tmp_path):
        """Borner ne doit pas vouloir dire perdre : les archives gardent le passé."""
        _ecrire(journal(taille_max=1500, archives=2), 400)

        archives = [f for f in _fichiers_de_journal(tmp_path) if f.suffix != ".log"]
        assert archives
        assert any(f.stat().st_size > 0 for f in archives)


class TestConfigurationFautive:
    """Une variable mal écrite ne doit pas rouvrir la croissance infinie."""

    @pytest.mark.parametrize("valeur", ["", "   ", "beaucoup", "-1", "0", None])
    def test_taille_illisible_retombe_sur_le_defaut(self, valeur, monkeypatch):
        """C'est le point : un réglage fautif reste borné."""
        if valeur is None:
            monkeypatch.delenv("GALSEN_LOG_MAX_BYTES", raising=False)
        else:
            monkeypatch.setenv("GALSEN_LOG_MAX_BYTES", valeur)
        assert Logger.taille_max_journal() == Logger.TAILLE_MAX_JOURNAL

    def test_taille_valide_est_honoree(self, monkeypatch):
        """Le réglage doit servir à quelque chose."""
        monkeypatch.setenv("GALSEN_LOG_MAX_BYTES", "12345")
        assert Logger.taille_max_journal() == 12345

    def test_zero_archive_est_accepte(self, monkeypatch):
        """Zéro est une valeur, pas une erreur — contrairement à la taille."""
        monkeypatch.setenv("GALSEN_LOG_BACKUP_COUNT", "0")
        assert Logger.archives_conservees() == 0

    @pytest.mark.parametrize("brut,defaut,attendu", [
        ("42", 5, 42),
        ("  7  ", 5, 7),
        ("zero", 5, 5),
        (None, 5, 5),
        ("-3", 5, 5),
    ])
    def test_conversion(self, brut, defaut, attendu):
        """La conversion ne doit jamais lever : un journal ne casse pas un démarrage."""
        assert _entier_positif(brut, defaut) == attendu


class TestDesactivation:
    """Sans historique demandé, aucun fichier ne doit apparaître."""

    def test_aucun_fichier_si_l_historique_est_desactive(self, tmp_path, monkeypatch):
        """La rotation ne doit pas créer un journal que personne n'a demandé."""
        monkeypatch.chdir(tmp_path)
        racine = logging.getLogger()
        avant = list(racine.handlers)

        Logger(_Configuration(save_history=False)).get_logger("essai").info("rien")

        try:
            assert not (tmp_path / "logs").exists()
        finally:
            for handler in list(racine.handlers):
                if handler not in avant:
                    handler.close()
                    racine.removeHandler(handler)
