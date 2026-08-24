"""
Ce qu'on réessaie, et ce qu'on cesse de réessayer.

`tests/test_web_search.py` est un **script**, pas un fichier de tests : il ne
contient aucune fonction `test_`, et `pytest` n'y collecte rien. L'outil de
recherche web n'avait donc aucune couverture automatisée — constat du
2026-08-24, laissé tel quel hors du périmètre de cette modification.

Ce fichier couvre la seule chose que ce changement a introduite : **un refus
définitif ne devient pas une acceptation en réessayant.**

Mesuré sur cette machine le 2026-08-24, avant le changement : un tour de
recherche coûtait 1 085 ms, dont 500 ms d'attente et 300 ms d'une seconde
tentative condamnée — le mandataire refusait le tunnel en 403, et le refus
était réessayé comme s'il pouvait changer d'avis.
"""

import os
import sys
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tools.web_search.tool import _refus_definitif  # noqa: E402


class TestCeQuiEstDefinitif:
    """
    La frontière entre « refusé » et « indisponible ».

    Elle porte tout le changement : se tromper d'un côté coûte une latence
    inutile, se tromper de l'autre coûte un résultat qu'on aurait pu obtenir.
    """

    @pytest.mark.parametrize("code", [400, 401, 403, 404, 410, 451])
    def test_un_4xx_ordinaire_ne_sera_pas_accepte_plus_tard(self, code):
        """La ressource est refusée, pas momentanément indisponible."""
        assert _refus_definitif(HTTPError("u", code, "refus", {}, None)) is True

    @pytest.mark.parametrize("code", [408, 429])
    def test_le_delai_et_la_limite_de_debit_restent_reessayables(self, code):
        """
        `408` et `429` sont les deux 4xx qui disent « plus tard », pas « non ».

        Les confondre avec un refus ferait abandonner exactement les cas où
        attendre fonctionne — et `429` est précisément le code qu'un service
        renvoie quand il veut qu'on réessaie plus lentement.
        """
        assert _refus_definitif(HTTPError("u", code, "attends", {}, None)) is False

    @pytest.mark.parametrize("code", [500, 502, 503, 504])
    def test_une_panne_serveur_reste_reessayable(self, code):
        assert _refus_definitif(HTTPError("u", code, "panne", {}, None)) is False

    def test_un_mandataire_qui_refuse_le_tunnel_est_definitif(self):
        """
        C'est le cas mesuré ici. CPython rend ce refus en `URLError` portant
        « Tunnel connection failed » : une décision de politique du mandataire,
        pas un incident réseau. Réessayer ne l'a jamais fait céder.
        """
        erreur = URLError("Tunnel connection failed: 403 Forbidden")
        assert _refus_definitif(erreur) is True

    @pytest.mark.parametrize("motif", ["timed out", "Connection refused",
                                       "Name or service not known"])
    def test_une_coupure_reseau_reste_reessayable(self, motif):
        assert _refus_definitif(URLError(motif)) is False

    def test_un_delai_depasse_reste_reessayable(self):
        assert _refus_definitif(TimeoutError("trop lent")) is False

    def test_dans_le_doute_on_reessaie(self):
        """
        Une erreur sans code ni motif reconnaissable n'est pas déclarée
        définitive. Réessayer à tort coûte une latence ; abandonner à tort
        coûte un résultat.
        """
        assert _refus_definitif(Exception("quelque chose d'inconnu")) is False


class TestLaBoucleDeReprise:
    """La distinction, appliquée là où elle change le temps passé."""

    @staticmethod
    def _outil(monkeypatch, erreur):
        """Un outil dont chaque tentative réseau lève `erreur`, et qui compte."""
        from src.tools.web_search import tool as module

        tentatives = []
        attentes = []

        def faux_urlopen(*args, **kwargs):
            tentatives.append(1)
            raise erreur

        monkeypatch.setattr(module, "urlopen", faux_urlopen)
        monkeypatch.setattr(module.time, "sleep", lambda s: attentes.append(s))

        outil = module.WebSearchTool()
        # Le limiteur de débit protège un service distant ; il n'a rien à faire
        # dans une mesure de reprise.
        monkeypatch.setattr(outil.rate_limiter, "wait", lambda: None)
        return outil, tentatives, attentes

    def test_un_refus_definitif_n_est_tente_qu_une_fois(self, monkeypatch):
        outil, tentatives, attentes = self._outil(
            monkeypatch, URLError("Tunnel connection failed: 403 Forbidden")
        )
        with pytest.raises(RuntimeError):
            outil._fetch_page("https://exemple.test/")
        assert len(tentatives) == 1, "un refus définitif ne se réessaie pas"
        assert attentes == [], "et ne fait attendre personne"

    def test_une_panne_passagere_garde_ses_reprises(self, monkeypatch):
        """Le repli existant n'est pas affaibli : seul le cas définitif change."""
        outil, tentatives, attentes = self._outil(
            monkeypatch, HTTPError("u", 503, "panne", {}, None)
        )
        with pytest.raises(RuntimeError):
            outil._fetch_page("https://exemple.test/")
        assert len(tentatives) == outil.max_retries + 1
        assert len(attentes) == outil.max_retries
