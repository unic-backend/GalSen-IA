"""
Tests for routing the declared MoneyPrinterTurbo provider (M06.2, M07).

This is the first provider in either programme that the creative router can
actually select, so these tests guard the three answers that must stay different
from one another.

**`stock_assembly`, not commercial → SELECTED.** It needs no GPU, its repository
licence was read, and nothing blocks it here.

**`stock_assembly`, commercial → NO_PROVIDER.** The output is made of Pexels and
Pixabay footage whose terms nobody read, so commercial rights are `UNKNOWN` — and
a commercial use requires an *established* right, not the absence of a known
prohibition.

**`text_to_video` → NO_PROVIDER.** MoneyPrinterTurbo is never offered as a
generator. Were it, a request for "a scene with my friend" would be served
footage of a stranger.

The three assertions together are the point: a router that got any one of them
right by accident would get the other two wrong.
"""

import pytest

from src.creative.providers import (
    AUCUN,
    CHOISI,
    CreativeRequest,
    ProviderRegistry,
    adapt_declared,
)
from src.creative.research import load_research
from src.creative.routing import route


@pytest.fixture(scope="module")
def registre():
    """Le registre chargé depuis le dossier de recherche réel."""
    inscrit = ProviderRegistry()
    for fournisseur in adapt_declared(load_research()["candidates"]):
        inscrit.register(fournisseur)
    return inscrit


@pytest.fixture(scope="module")
def mpt(registre):
    """Le fournisseur MoneyPrinterTurbo tel qu'il est déclaré."""
    return registre.get("moneyprinterturbo")


class TestDeclaration:
    """Ce que le dossier de recherche affirme, et ce qu'il refuse d'affirmer."""

    def test_le_fournisseur_est_declare(self, mpt):
        assert mpt is not None

    def test_il_ne_sert_que_l_assemblage(self, mpt):
        assert mpt.tasks == frozenset({"stock_assembly"})
        assert not mpt.serves("text_to_video")

    def test_il_n_exige_aucun_gpu(self, mpt):
        """Sa seule vraie supériorité ici — et `0` n'est pas `None`."""
        assert mpt.min_vram_gb == 0

    def test_la_licence_du_depot_est_lue_a_la_source(self, mpt):
        assert mpt.licence.repository == "MIT"
        assert mpt.licence.verified_from.startswith("https://")

    def test_le_droit_commercial_reste_inconnu(self, mpt):
        """Les rushes viennent de banques dont personne n'a lu les conditions."""
        assert mpt.licence.commercial == "UNKNOWN"
        assert mpt.licence.usable_commercially is False


class TestLesTroisReponses:
    """Trois demandes, trois réponses, et elles doivent rester distinctes."""

    def test_l_assemblage_non_commercial_est_servi(self, registre):
        resultat = route(registre, CreativeRequest(task="stock_assembly"))
        assert resultat["status"] == CHOISI
        assert resultat["provider_id"] == "moneyprinterturbo"

    def test_l_assemblage_commercial_est_refuse(self, registre):
        """Un usage commercial exige un droit établi, pas un silence."""
        resultat = route(
            registre, CreativeRequest(task="stock_assembly", commercial=True))
        assert resultat["status"] == AUCUN
        entree = [e for e in resultat["matrix"]
                  if e["provider_id"] == "moneyprinterturbo"][0]
        assert any("commercial" in obstacle.lower()
                   for obstacle in entree["obstacles"])

    def test_la_generation_video_ne_lui_est_jamais_confiee(self, registre):
        """Sinon « une scène avec mon ami » rendrait des rushes d'un inconnu."""
        resultat = route(registre, CreativeRequest(task="text_to_video"))
        # `NO_PROVIDER` ne porte pas de `provider_id` : lire la clé
        # supposerait qu'un choix a eu lieu.
        assert resultat["status"] == AUCUN
        assert resultat.get("provider_id") is None
        assert "moneyprinterturbo" not in [
            e["provider_id"] for e in resultat["matrix"] if e["eligible"]
        ]

    def test_le_refus_commercial_nomme_sa_raison(self, registre):
        resultat = route(
            registre, CreativeRequest(task="stock_assembly", commercial=True))
        entree = [e for e in resultat["matrix"]
                  if e["provider_id"] == "moneyprinterturbo"][0]
        raisons = " ".join(entree["obstacles"])
        assert "établi" in raisons


class TestZeroNEstPasNone:
    """Le défaut que cette entrée a révélé, et qu'elle garde corrigé."""

    def test_un_besoin_nul_ne_declenche_pas_la_mesure_de_vram(self, registre):
        """`0 Go exigés` et `VRAM non déclarée` sont deux informations.

        Les confondre écartait un fournisseur qui n'a besoin d'aucun GPU, sur
        une machine qui n'en a pas — un refus juste par accident, pour la
        mauvaise raison.
        """
        resultat = route(registre, CreativeRequest(task="stock_assembly"))
        entree = [e for e in resultat["matrix"]
                  if e["provider_id"] == "moneyprinterturbo"][0]
        assert entree["eligible"] is True
        assert not any("gpu" in obstacle.lower()
                       for obstacle in entree["obstacles"])

    def test_un_besoin_positif_declenche_toujours_la_mesure(self, registre):
        """Les candidats à GPU restent écartés : la correction est étroite."""
        gourmand = registre.get("wan2.2")
        assert gourmand is not None and gourmand.min_vram_gb > 0
        resultat = route(registre, CreativeRequest(task="text_to_video"))
        entree = [e for e in resultat["matrix"]
                  if e["provider_id"] == "wan2.2"][0]
        assert entree["eligible"] is False


def test_les_autres_fournisseurs_restent_inchanges(registre):
    """§1 : l'ajout ne rend éligible aucun candidat qui ne l'était pas."""
    eligibles = [
        e["provider_id"]
        for e in route(registre, CreativeRequest(task="text_to_video"))["matrix"]
        if e["eligible"]
    ]
    assert eligibles == [], (
        "Aucun générateur n'est dégagé ; en rendre un éligible serait une "
        "régression silencieuse."
    )
