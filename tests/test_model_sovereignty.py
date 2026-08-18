"""
GalSen IA ne dépend d'aucun modèle tiers à l'exécution (phase 26.0 — ADR-014).

Le registre inscrivait OpenAI, Anthropic et Google par défaut. Ils restaient
inertes faute de clé — mais **inerte n'est pas absent** : « personne n'a mis de
clé » est un état, pas une garantie. Une variable d'environnement héritée, un
fichier `.env` recopié d'un autre projet, et la plateforme redevenait locataire.

Le test qui compte est le premier : **mode souverain actif, toutes les clés
hébergées présentes, et aucun fournisseur tiers joignable.** Vérifier que le
drapeau est lu ne prouverait rien.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.providers.anthropic_provider import AnthropicProvider  # noqa: E402
from src.model_engine.providers.google_provider import GoogleProvider  # noqa: E402
from src.model_engine.providers.hosted_provider import HostedProvider  # noqa: E402
from src.model_engine.providers.openai_compatible_provider import (  # noqa: E402
    URL_VARIABLE,
    OpenAICompatibleProvider,
)
from src.model_engine.providers.openai_provider import OpenAIProvider  # noqa: E402
from src.model_engine.providers.provider_registry import (  # noqa: E402
    SOVEREIGN_MODE_VARIABLE,
    ProviderRegistry,
    sovereign_mode,
)

CLES_TIERCES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")


@pytest.fixture
def souverain(monkeypatch):
    """Mode souverain explicite, sans URL compatible déclarée."""
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    monkeypatch.delenv(URL_VARIABLE, raising=False)
    return ProviderRegistry()


# ----------------------------------------------------------------------
# La garantie
# ----------------------------------------------------------------------

def test_des_cles_tierces_presentes_ne_font_pas_revenir_les_fournisseurs(monkeypatch):
    """
    Le fait qui justifie tout le chantier.

    Avec les trois clés renseignées, l'ancien registre inscrivait et **activait**
    les trois fournisseurs tiers. La souveraineté ne doit pas dépendre de
    l'absence d'une configuration.
    """
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    for cle in CLES_TIERCES:
        monkeypatch.setenv(cle, "une-cle-qui-fonctionnerait")

    registre = ProviderRegistry()

    assert registre.provider_ids() == ["local", "openai_compatible"]
    assert all(
        not isinstance(fournisseur, HostedProvider)
        for fournisseur in registre.list_providers()
    )


def test_le_defaut_est_souverain(monkeypatch):
    """La souveraineté n'est pas une option qu'on active : c'est l'état normal."""
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)

    assert sovereign_mode() is True


def test_un_fournisseur_tiers_inscrit_a_la_main_est_refuse(souverain):
    """
    Ne pas les inscrire par défaut protège du hasard, pas d'un appel explicite.

    La garantie doit tenir dans les deux cas, sinon elle ne tient pas.
    """
    for classe in (OpenAIProvider, AnthropicProvider, GoogleProvider):
        with pytest.raises(ValueError, match="souverain"):
            souverain.register(classe())


def test_le_refus_dit_quoi_faire(souverain):
    """Un refus qui ne nomme pas la sortie de secours bloque sans informer."""
    with pytest.raises(ValueError) as refus:
        souverain.register(OpenAIProvider())

    message = str(refus.value)
    assert SOVEREIGN_MODE_VARIABLE in message
    assert "ADR-014" in message


def test_l_url_compatible_ne_peut_pas_viser_un_service_tiers(monkeypatch):
    """
    La porte de derrière : le format de fil est public, l'infrastructure non.

    Pointer le fournisseur « compatible » vers `api.openai.com` rendrait la
    souveraineté nominale et fausse.
    """
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    monkeypatch.setenv(URL_VARIABLE, "https://api.openai.com/v1")

    registre = ProviderRegistry(register_defaults=False)
    with pytest.raises(ValueError, match="api.openai.com"):
        registre.register(OpenAICompatibleProvider())


def test_une_url_propre_reste_acceptee(monkeypatch):
    """Le contre-test : la règle ne doit pas fermer le chemin légitime."""
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    monkeypatch.setenv(URL_VARIABLE, "http://localhost:11434/v1")

    registre = ProviderRegistry(register_defaults=False)
    registre.register(OpenAICompatibleProvider())

    assert "openai_compatible" in registre.provider_ids()


# ----------------------------------------------------------------------
# La sortie de secours, et son prix
# ----------------------------------------------------------------------

def test_le_mode_non_souverain_reinscrit_les_tiers(monkeypatch):
    """
    Comparer un modèle propre à une référence reste possible — déclaré.

    Sans cette sortie, l'évaluation du VOLET 33 n'aurait aucun point de
    comparaison, et la règle serait contournée en douce plutôt qu'assumée.
    """
    monkeypatch.setenv(SOVEREIGN_MODE_VARIABLE, "false")

    registre = ProviderRegistry()

    for attendu in ("openai", "anthropic", "google", "local"):
        assert attendu in registre.provider_ids()


def test_l_ecart_est_journalise(monkeypatch, caplog):
    """Un opérateur doit avoir une trace du jour où la plateforme a cédé."""
    monkeypatch.setenv(SOVEREIGN_MODE_VARIABLE, "false")

    with caplog.at_level("WARNING"):
        ProviderRegistry()

    assert "ADR-014" in caplog.text


# ----------------------------------------------------------------------
# Ce que l'opérateur peut constater
# ----------------------------------------------------------------------

def test_le_rapport_expose_le_mode_et_les_tiers(souverain):
    """La souveraineté se constate, elle ne se lit pas seulement dans un ADR."""
    rapport = souverain.sovereignty_report()

    assert rapport["sovereign_mode"] is True
    assert rapport["third_party_providers"] == []
    assert rapport["reference"] == "ADR-014"


def test_le_rapport_ne_divulgue_aucun_secret(monkeypatch):
    """`/health` n'est pas authentifiée : aucune clé ne doit y transiter."""
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-a-ne-pas-divulguer")
    monkeypatch.setenv(URL_VARIABLE, "http://localhost:11434/v1")

    rapport = str(ProviderRegistry().sovereignty_report())

    assert "sk-secret-a-ne-pas-divulguer" not in rapport
    assert "localhost:11434" not in rapport


def test_le_rapport_nomme_l_hote_tiers_quand_il_y_en_a_un(monkeypatch):
    """Quand une URL vise un tiers, la taire priverait l'opérateur du motif."""
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    monkeypatch.setenv(URL_VARIABLE, "https://api.deepseek.com/v1")

    rapport = ProviderRegistry(register_defaults=False).sovereignty_report()

    assert rapport["third_party_endpoint"] == "api.deepseek.com"
