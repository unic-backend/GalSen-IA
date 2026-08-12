"""
La dérogation cadrée à la souveraineté (ADR-018, option B).

Le propriétaire a tranché l'option B le 2026-08-12 : souverain par défaut, avec
une exception **nommée, configurée et tracée**. Ces tests protègent la propriété
qui rend B défendable — *B est plus strict que ce qu'il remplace*, parce que les
trois refus inconditionnels n'existaient pas avant lui.

Le test le plus important du fichier est
`test_une_derogation_active_ne_couvre_pas_le_contenu_d_une_personne` : c'est
celui que l'ADR promettait, et sans lui la dérogation serait exactement le levier
global qu'elle prétend remplacer.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.providers.derogations import (  # noqa: E402
    REFUS_INCONDITIONNELS,
    VARIABLE,
    Derogation,
    allow,
    allowed_providers,
    declared_derogations,
    report,
)


@pytest.fixture
def sans_derogation(monkeypatch):
    """Aucune dérogation déclarée — le défaut."""
    monkeypatch.delenv(VARIABLE, raising=False)


UNE = [Derogation(task_type="code_generation", provider_id="openai")]


# ----------------------------------------------------------------------
# 1. Le défaut n'a pas bougé
# ----------------------------------------------------------------------


def test_aucune_derogation_par_defaut(sans_derogation):
    """La souveraineté reste l'état normal ; l'exception se déclare."""
    assert declared_derogations() == []
    assert allowed_providers() == []


def test_sans_derogation_tout_appel_tiers_est_refuse(sans_derogation):
    autorise, raison = allow("code_generation", "openai")

    assert autorise is False
    assert VARIABLE in raison


# ----------------------------------------------------------------------
# 2. La dérogation est une configuration, jamais une demande
# ----------------------------------------------------------------------


def test_la_derogation_se_lit_dans_la_configuration():
    derogations = declared_derogations("code_generation:openai,translation:anthropic")

    assert [d.task_type for d in derogations] == ["code_generation", "translation"]
    assert allowed_providers(derogations) == ["anthropic", "openai"]


def test_une_entree_malformee_est_ecartee_et_non_devinee():
    """Deviner un type de tâche ouvrirait une porte que personne n'a demandée."""
    assert declared_derogations("sans-deux-points,:openai,code_generation:") == []


def test_un_appelant_ne_peut_pas_demander_le_cloud():
    """
    ADR-016 a mesuré ce défaut : un champ rempli par l'appelant, enregistré
    comme un fait. Ici, la réponse le dit explicitement.
    """
    assert report(UNE)["caller_can_request"] is False


def test_la_derogation_ne_couvre_que_le_type_de_tache_nomme():
    autorise, _ = allow("translation", "openai", derogations=UNE)

    assert autorise is False


def test_la_derogation_ne_couvre_que_le_fournisseur_nomme():
    autorise, _ = allow("code_generation", "anthropic", derogations=UNE)

    assert autorise is False


def test_le_type_de_tache_derogé_passe():
    autorise, raison = allow("code_generation", "openai", derogations=UNE)

    assert autorise is True
    assert "code_generation->openai" in raison


# ----------------------------------------------------------------------
# 3. Les trois refus inconditionnels
# ----------------------------------------------------------------------


def test_une_derogation_active_ne_couvre_pas_le_contenu_d_une_personne():
    """
    Le test que l'ADR promettait.

    Sans lui, la dérogation serait le levier global qu'elle prétend remplacer :
    une exception déclarée pour la génération de code laisserait passer une
    requête portant les mémoires de quelqu'un.
    """
    autorise, raison = allow(
        "code_generation", "openai", carries_user_content=True, derogations=UNE,
    )

    assert autorise is False
    assert "inconditionnel" in raison


def test_les_trois_categories_sont_refusees_quoi_qu_en_dise_la_configuration():
    for categorie in REFUS_INCONDITIONNELS:
        derogation = [Derogation(task_type=categorie, provider_id="openai")]
        autorise, raison = allow(categorie, "openai", derogations=derogation)

        assert autorise is False, f"« {categorie} » ne doit jamais passer"
        assert "inconditionnel" in raison


def test_declarer_une_categorie_refusee_est_ecarte_et_non_honore():
    """Une erreur d'opérateur n'est pas une autorisation."""
    derogations = declared_derogations("user_content:openai,code_generation:openai")

    assert [d.task_type for d in derogations] == ["code_generation"]


def test_chaque_refus_inconditionnel_porte_sa_raison():
    """Un refus sans raison finit par être levé par quelqu'un qui ignore ce qu'il lève."""
    for categorie, raison in REFUS_INCONDITIONNELS.items():
        assert raison.strip(), f"« {categorie} » refusé sans raison écrite"


# ----------------------------------------------------------------------
# 4. Rien n'est invisible
# ----------------------------------------------------------------------


def test_le_rapport_nomme_les_derogations_et_les_refus():
    """Une dérogation que personne ne peut voir ne se distingue pas d'une fuite."""
    rapport = report(UNE)

    assert rapport["count"] == 1
    assert rapport["derogations"][0]["provider_id"] == "openai"
    assert sorted(rapport["unconditional_refusals"]) == sorted(REFUS_INCONDITIONNELS)


def test_la_souverainete_rapporte_les_derogations(sans_derogation):
    """`/health` les rend en même temps que le mode (ADR-018 §3)."""
    from src.model_engine.providers.provider_registry import ProviderRegistry

    rapport = ProviderRegistry().sovereignty_report()

    assert rapport["sovereign_mode"] is True
    assert rapport["derogations"]["count"] == 0
    assert rapport["derogations"]["reference"] == "ADR-018"


def test_un_fournisseur_tiers_reste_refuse_sans_derogation(sans_derogation):
    """Le défaut d'ADR-014 est intact : B ne le desserre pas."""
    from src.model_engine.providers.openai_provider import OpenAIProvider
    from src.model_engine.providers.provider_registry import ProviderRegistry

    registre = ProviderRegistry(register_defaults=False)

    with pytest.raises(ValueError) as erreur:
        registre.register(OpenAIProvider())

    assert "souverain" in str(erreur.value).lower()


def test_un_fournisseur_nomme_par_une_derogation_peut_etre_inscrit(monkeypatch):
    """
    L'inscription n'est pas la permission : `allow()` tranche encore à chaque
    appel. Sans cette porte, la dérogation resterait une phrase.
    """
    from src.model_engine.providers.openai_provider import OpenAIProvider
    from src.model_engine.providers.provider_registry import ProviderRegistry

    monkeypatch.setenv(VARIABLE, "code_generation:openai")
    registre = ProviderRegistry(register_defaults=False)

    registre.register(OpenAIProvider())

    assert "openai" in registre.provider_ids()
    # …et le contenu d'une personne reste refusé, registre ou pas.
    autorise, _ = allow("code_generation", "openai", carries_user_content=True)
    assert autorise is False
