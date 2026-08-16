"""
Tests for the creative provider contract (ADR-024, directive §34–§36).

Two properties carry the weight here: a licence is a routing constraint that
cannot be talked around, and a declaration is never mistaken for an
availability.
"""

import pytest

from src.creative.providers import (
    COMMERCIAL_AUTORISE,
    COMMERCIAL_INCONNU,
    COMMERCIAL_RESTREINT,
    DANS_LE_PROCESSUS,
    DESACTIVE,
    HORS_PROCESSUS,
    TACHES_CREATIVES,
    CreativeProvider,
    CreativeRequest,
    LicenceRecord,
    ProviderRefused,
    ProviderRegistry,
    adapt_declared,
    availability,
    evaluate,
    provider_report,
)
from src.creative.research import load_research


def _local(identite="local", taches=("text_to_image",), **kwargs):
    """Un fournisseur qui déclare ne rien exiger — et le déclare vraiment."""
    return CreativeProvider(
        provider_id=identite, tasks=frozenset(taches),
        runs_locally=True, **kwargs,
    )


# --------------------------------------------------------------------------
# Le contrat
# --------------------------------------------------------------------------


def test_les_taches_sont_des_valeurs_declarees():
    assert "audio_to_video" in TACHES_CREATIVES
    assert "identity_verification" in TACHES_CREATIVES
    with pytest.raises(ProviderRefused) as erreur:
        CreativeProvider(provider_id="x", tasks=frozenset({"faire_un_film"}))
    assert "inconnues" in str(erreur.value)


def test_une_capacite_machine_inventee_est_refusee():
    with pytest.raises(ProviderRefused) as erreur:
        CreativeProvider(provider_id="x", requires=("teleportation",))
    # Une capacité inventée au moment de s'en servir n'apparaît nulle part.
    assert "non déclarées" in str(erreur.value)


def test_un_mode_d_invocation_non_declare_est_refuse():
    with pytest.raises(ProviderRefused):
        CreativeProvider(provider_id="x", invocation="par_magie")


def test_un_droit_commercial_autorise_sans_source_est_refuse():
    with pytest.raises(ProviderRefused) as erreur:
        LicenceRecord(commercial=COMMERCIAL_AUTORISE)
    assert "§40" in str(erreur.value)


def test_un_droit_commercial_autorise_avec_source_est_accepte():
    licence = LicenceRecord(commercial=COMMERCIAL_AUTORISE,
                            verified_from="https://exemple/LICENSE")
    assert licence.usable_commercially is True


# --------------------------------------------------------------------------
# La licence comme contrainte de routage
# --------------------------------------------------------------------------


def test_un_travail_commercial_refuse_un_droit_inconnu():
    fournisseur = _local(licence=LicenceRecord(commercial=COMMERCIAL_INCONNU))
    verdict = evaluate(fournisseur, CreativeRequest(task="text_to_image",
                                                    commercial=True))
    assert verdict["eligible"] is False
    # L'absence d'interdiction connue n'est pas une permission.
    assert any("droit **établi**" in o for o in verdict["obstacles"])


def test_un_travail_non_commercial_passe_avec_un_droit_inconnu():
    fournisseur = _local()
    verdict = evaluate(fournisseur, CreativeRequest(task="text_to_image"))
    assert verdict["eligible"] is True


def test_une_licence_restreinte_porte_sa_restriction_dans_le_refus():
    fournisseur = _local(licence=LicenceRecord(
        commercial=COMMERCIAL_RESTREINT,
        restrictions="ne s'applique pas dans l'Union européenne"))
    verdict = evaluate(fournisseur, CreativeRequest(task="text_to_image",
                                                    commercial=True))
    assert any("Union européenne" in o for o in verdict["obstacles"])


def test_le_copyleft_devient_un_mode_d_invocation():
    fournisseurs = {f.provider_id: f
                    for f in adapt_declared(load_research()["candidates"])}
    assert fournisseurs["seed-vc"].invocation == HORS_PROCESSUS
    assert fournisseurs["wan2.2"].invocation == DANS_LE_PROCESSUS


def test_un_appel_hors_processus_peut_etre_refuse_par_la_demande():
    fournisseur = _local(invocation=HORS_PROCESSUS)
    verdict = evaluate(fournisseur, CreativeRequest(
        task="text_to_image", allow_out_of_process=False))
    assert verdict["eligible"] is False


# --------------------------------------------------------------------------
# Déclaration contre disponibilité
# --------------------------------------------------------------------------


def test_une_exigence_non_declaree_rend_inconnu_pas_disponible():
    # Le défaut trouvé en exécutant : sans exigence déclarée, la sonde ne
    # trouve rien à reprocher et rendait « disponible » un modèle de 14
    # milliards de paramètres sur une machine sans GPU.
    muet = CreativeProvider(provider_id="muet", tasks=frozenset({"text_to_video"}))
    etat = availability(muet)
    assert etat["state"] == "UNKNOWN"
    assert "pas disponible" in etat["reason"]


def test_un_etat_inconnu_n_est_pas_un_feu_vert():
    muet = CreativeProvider(provider_id="muet", tasks=frozenset({"text_to_video"}))
    verdict = evaluate(muet, CreativeRequest(task="text_to_video"))
    assert verdict["eligible"] is False
    assert any("inconnu" in o for o in verdict["obstacles"])


def test_une_capacite_absente_rend_indisponible():
    fournisseur = CreativeProvider(
        provider_id="x", tasks=frozenset({"speech_recognition"}),
        requires=("transcription",))
    etat = availability(fournisseur)
    assert etat["state"] == "UNAVAILABLE"
    assert [m["capability"] for m in etat["missing"]] == ["transcription"]


def test_une_vram_exigee_sans_gpu_mesurable_rend_indisponible():
    fournisseur = CreativeProvider(
        provider_id="x", tasks=frozenset({"text_to_video"}), min_vram_gb=24)
    etat = availability(fournisseur)
    assert etat["state"] == "UNAVAILABLE"
    # « Peut-être assez » n'existe pas : non mesuré vaut indisponible.
    assert any("non mesurée" in m["reason"] for m in etat["missing"])


def test_un_fournisseur_declare_local_est_disponible():
    assert availability(_local())["state"] == "AVAILABLE"


# --------------------------------------------------------------------------
# Le registre
# --------------------------------------------------------------------------


def test_un_identifiant_en_double_est_refuse():
    registre = ProviderRegistry()
    registre.register(_local())
    with pytest.raises(ProviderRefused) as erreur:
        registre.register(_local())
    assert "déjà inscrit" in str(erreur.value)


def test_un_fournisseur_desactive_l_emporte_sur_la_sonde():
    registre = ProviderRegistry()
    registre.register(_local(), state=DESACTIVE)
    # Quelqu'un a décidé de l'écarter ; une sonde ne contredit pas une décision.
    assert registre.state_of("local") == DESACTIVE
    assert registre.select(CreativeRequest(task="text_to_image"))["status"] == (
        "NO_PROVIDER")


def test_aucun_repli_sur_le_plus_proche():
    registre = ProviderRegistry()
    registre.register(_local(taches=("text_to_image",)))
    resultat = registre.select(CreativeRequest(task="text_to_video"))
    assert resultat["status"] == "NO_PROVIDER"
    assert "substitution silencieuse" in resultat["reason"]


def test_un_cout_inconnu_exclut_d_un_plafond():
    registre = ProviderRegistry()
    registre.register(_local())
    resultat = registre.select(CreativeRequest(task="text_to_image",
                                               max_cost_per_second=0.5))
    assert resultat["status"] == "NO_PROVIDER"
    obstacles = resultat["evaluations"][0]["obstacles"]
    assert any("coût inconnu n'est pas un coût nul" in o for o in obstacles)


def test_le_rapport_nomme_les_taches_sans_fournisseur():
    registre = ProviderRegistry()
    registre.register(_local())
    rapport = registre.report()
    assert "text_to_video" in rapport["tasks_unserved"]
    # C'est la liste utile : elle dit ce que la plateforme ne peut pas faire.
    assert "ne peut pas faire" in rapport["note"]


# --------------------------------------------------------------------------
# Le dossier de recherche, adapté
# --------------------------------------------------------------------------


def test_les_neuf_candidats_s_adaptent_en_fournisseurs():
    fournisseurs = adapt_declared(load_research()["candidates"])
    assert len(fournisseurs) == 9
    assert all(isinstance(f, CreativeProvider) for f in fournisseurs)


def test_aucun_candidat_n_est_exploitable_commercialement():
    registre = ProviderRegistry()
    for fournisseur in adapt_declared(load_research()["candidates"]):
        registre.register(fournisseur)
    # Zéro, et ce n'est pas du pessimisme : c'est l'état de la preuve.
    assert registre.report()["commercially_usable"] == []
    assert registre.select(CreativeRequest(task="text_to_video",
                                           commercial=True))["status"] == (
        "NO_PROVIDER")


def test_aucun_candidat_ne_sert_la_verification_d_identite():
    registre = ProviderRegistry()
    for fournisseur in adapt_declared(load_research()["candidates"]):
        registre.register(fournisseur)
    assert "identity_verification" in registre.report()["tasks_unserved"]


def test_le_rapport_du_contrat_nomme_ce_qu_il_refuse():
    rapport = provider_report()
    refus = " ".join(rapport["does_not"]).lower()
    assert "remplacer" in refus
    assert "déduire" in refus
    assert len(rapport["tasks"]) == len(TACHES_CREATIVES)
