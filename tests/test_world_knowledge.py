"""
La connaissance mondiale, dérivée et non écrite de mémoire (phase 52.1).

La couche sénégalaise de ce dépôt est fiable pour une seule raison : ses quatorze
régions et ses quarante-cinq départements ont été **lus** dans des limites
administratives publiées, jamais écrits depuis la connaissance générale d'un
modèle. Peupler le monde autrement annulerait cette garantie du même geste.

Ce que ces tests gardent :

1. **Rien n'est écrit de mémoire.** Chaque valeur vient d'une ligne d'un jeu
   acquis ; un champ que la source ne porte pas vaut `UNKNOWN`.
2. **`global` porte la taxonomie, pas les pays.** Un fait sur la France porte la
   portée `country:fr`. Ranger les pays en `global` ferait passer une
   connaissance locale pour universelle — l'erreur exacte que `scope.py` existe
   pour empêcher.
3. **Deux sources qui divergent sont rapportées, jamais réconciliées.**
4. **Une ligne écartée est comptée.** Une base dont la taille s'explique par des
   lignes disparues n'est pas vérifiable.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.world import (  # noqa: E402
    INCONNU,
    JEUX_MONDIAUX,
    WorldDerivationError,
    build_world_knowledge,
    answer_country,
    answer_field,
    country_lookup,
    derive_countries,
    derive_reference,
    read_country_codes,
    world_report,
)

#: Deux lignes réalistes, plus une sans code : la forme du vrai fichier.
CSV_CODES = (
    "ISO3166-1-Alpha-3,ISO3166-1-Alpha-2,M49,official_name_en,official_name_fr,"
    "Capital,Continent,Region Name,Sub-region Name,"
    "ISO4217-currency_alphabetic_code,ISO4217-currency_name,TLD,Languages,is_independent\n"
    "SEN,SN,686,Senegal,Sénégal,Dakar,AF,Africa,Sub-Saharan Africa,XOF,CFA Franc BCEAO,.sn,fr-SN,Yes\n"
    "FRA,FR,250,France,France,Paris,EU,Europe,Western Europe,EUR,Euro,.fr,fr-FR,Yes\n"
    ",,,Territoire sans code,,,,,,,,,,\n"
)

PROFILS = [
    {"cca3": "SEN", "capital": ["Dakar"], "currencies": {"XOF": {}},
     "area": 196722.0, "borders": ["GMB", "GIN"], "unMember": True},
    {"cca3": "FRA", "capital": ["Paris"], "currencies": {"EUR": {}},
     "area": 551695.0, "borders": ["AND", "BEL"], "unMember": True},
]

CHEMIN_DERIVE = os.path.join(
    os.path.dirname(__file__), "..", "data", "processed_global",
    "world_countries.json",
)


@pytest.fixture
def monde():
    """Le monde dérivé des deux lignes d'exemple."""
    return build_world_knowledge(CSV_CODES, PROFILS)


# ----------------------------------------------------------------------
# 1. Rien n'est écrit de mémoire
# ----------------------------------------------------------------------

def test_chaque_valeur_vient_d_une_ligne_de_la_source(monde):
    """Le point de tout le module."""
    senegal = country_lookup(monde, "SEN")[0]

    assert senegal["capital"] == "Dakar"
    assert senegal["currency_code"] == "XOF"
    assert senegal["provenance"]["source_url"].endswith("country-codes.csv")


def test_un_champ_absent_de_la_source_vaut_unknown():
    """Jamais une valeur plausible : c'est toute la différence."""
    csv_partiel = (
        "ISO3166-1-Alpha-3,ISO3166-1-Alpha-2,official_name_en,Capital\n"
        "MLI,ML,Mali,\n"
    )

    mali = build_world_knowledge(csv_partiel)["countries"][0]

    assert mali["capital"] == INCONNU
    assert mali["currency_code"] == INCONNU
    assert mali["region"] == INCONNU


def test_un_champ_manquant_ne_disparait_pas_de_l_objet():
    """Un champ absent doit se distinguer d'un champ oublié."""
    csv_minimal = "ISO3166-1-Alpha-3,ISO3166-1-Alpha-2\nMLI,ML\n"

    mali = build_world_knowledge(csv_minimal)["countries"][0]

    assert "sub_region" in mali
    assert mali["sub_region"] == INCONNU


def test_le_rang_est_celui_de_ce_qui_est_recupere(monde):
    """Il n'hérite jamais du rang de l'institution en amont."""
    provenance = monde["countries"][0]["provenance"]

    assert provenance["source_tier"] == "TIER_C_SECONDARY"
    assert provenance["upstream_tier"] == "TIER_B_INTERNATIONAL"


def test_un_monde_vide_est_refuse():
    """Rendre un objet vide laisserait croire que le monde l'est."""
    with pytest.raises(WorldDerivationError, match="laisserait croire"):
        build_world_knowledge("ISO3166-1-Alpha-3\n")


# ----------------------------------------------------------------------
# 2. `global` porte la taxonomie, pas les pays
# ----------------------------------------------------------------------

def test_un_pays_porte_la_portee_de_son_pays(monde):
    """
    Ranger un fait français en `global` ferait passer une connaissance locale
    pour universelle.
    """
    france = country_lookup(monde, "FRA")[0]

    assert france["scope"] == "country:fr"
    assert all(pays["scope"] != "global" for pays in monde["countries"])


def test_la_reference_est_ce_qui_vaut_partout(monde):
    """Les continents et les régions M49 ne valent pas « dans un pays »."""
    reference = monde["reference"]

    assert reference["scope"] == "global"
    assert reference["regions"] == {"Africa": 1, "Europe": 1}
    assert reference["currencies"] == {"EUR": 1, "XOF": 1}


def test_la_reference_compte_ce_qui_l_atteste(monde):
    """Une taxonomie sans effectif ne dit pas ce qu'elle recouvre."""
    reference = derive_reference(monde["countries"])

    assert sum(reference["continents"].values()) == len(monde["countries"])


def test_la_reference_dit_ou_ne_sont_pas_les_faits(monde):
    """Le dire vaut mieux que le laisser deviner."""
    assert "portée de leur pays" in monde["reference"]["note"]


# ----------------------------------------------------------------------
# 3. Les désaccords sont rapportés, jamais résolus
# ----------------------------------------------------------------------

def test_deux_sources_qui_divergent_sont_rapportees_cote_a_cote():
    """Choisir en silence rendrait la plateforme catégorique sur ce qu'elle
    ne peut pas établir."""
    profils = [{"cca3": "SEN", "capital": ["Saint-Louis"], "currencies": {"XOF": {}}}]

    monde = build_world_knowledge(CSV_CODES, profils)

    ecart = [d for d in monde["disagreements"] if d["iso3"] == "SEN"][0]
    assert ecart["field"] == "capital"
    assert ecart["country_codes"] == "Dakar"
    assert ecart["country_profile"] == "Saint-Louis"
    assert ecart["resolved"] == "no"


def test_un_accent_n_est_pas_un_desaccord():
    """
    « Brasília » et « Brasilia » sont le même nom écrit deux fois. Une liste où
    presque tout est du bruit n'est plus lue — c'est aussi grave que d'en cacher
    un.
    """
    profils = [{"cca3": "SEN", "capital": ["Dàkar"], "currencies": {"XOF": {}}}]

    monde = build_world_knowledge(CSV_CODES, profils)

    assert [d for d in monde["disagreements"] if d["iso3"] == "SEN"] == []


def test_l_ordre_des_monnaies_n_est_pas_un_desaccord():
    """`INR,BTN` et `BTN, INR` sont le même ensemble, écrit dans deux ordres."""
    lignes = read_country_codes(CSV_CODES)[:1]
    lignes[0]["ISO4217-currency_alphabetic_code"] = "INR,BTN"
    profils = [{"cca3": "SEN", "currencies": {"BTN": {}, "INR": {}}}]

    assert derive_countries(lignes, profils)["disagreements"] == []


def test_une_monnaie_reellement_differente_reste_un_desaccord():
    """La contre-épreuve : la normalisation ne doit rien avaler."""
    lignes = read_country_codes(CSV_CODES)[:1]
    profils = [{"cca3": "SEN", "currencies": {"EUR": {}}}]

    ecarts = derive_countries(lignes, profils)["disagreements"]

    assert [e["field"] for e in ecarts] == ["currency_code"]


def test_un_pays_sans_profil_est_nomme(monde):
    """Une absence silencieuse se lirait comme une absence de désaccord."""
    sans = build_world_knowledge(CSV_CODES, [PROFILS[0]])

    assert sans["without_profile"] == ["FRA"]
    assert sans["counts"]["with_profile"] == 1


# ----------------------------------------------------------------------
# 4. Ce qui n'entre pas est compté
# ----------------------------------------------------------------------

def test_une_ligne_sans_code_iso_n_entre_pas_et_est_comptee(monde):
    """Une base dont la taille s'explique par des lignes disparues n'est pas
    vérifiable."""
    assert monde["counts"]["countries"] == 2
    assert monde["counts"]["refused_rows"] == 1
    assert "identité stable" in monde["refused_rows"][0]["reason"]


def test_un_code_inconnu_ne_rend_pas_le_pays_le_plus_proche(monde):
    """Un code voisin désigne un autre pays."""
    trouve, motif = country_lookup(monde, "SEM")

    assert trouve is None
    assert "n'est pas rendu" in motif


def test_la_recherche_accepte_les_deux_codes(monde):
    """Alpha-2 et alpha-3 désignent le même pays."""
    assert country_lookup(monde, "sn")[0]["iso3"] == "SEN"
    assert country_lookup(monde, "SEN")[0]["iso2"] == "SN"


# ----------------------------------------------------------------------
# 5. La connaissance réellement dérivée dans le dépôt
# ----------------------------------------------------------------------

def test_le_fichier_derive_existe_et_porte_le_monde():
    """
    Le brut n'est pas versionné, le dérivé l'est — comme pour le Sénégal. Ce
    test lit ce que le dépôt contient réellement, pas une reconstruction.
    """
    with open(CHEMIN_DERIVE, "r", encoding="utf-8") as flux:
        monde = json.load(flux)

    assert monde["counts"]["countries"] >= 200
    assert monde["counts"]["refused_rows"] == 0
    assert set(monde["built_from"]) == set(JEUX_MONDIAUX)


def test_aucun_pays_derive_n_est_range_en_global():
    """La règle de portée, vérifiée sur les 249 pays réels."""
    with open(CHEMIN_DERIVE, "r", encoding="utf-8") as flux:
        monde = json.load(flux)

    assert all(pays["scope"] != "global" for pays in monde["countries"])
    assert monde["reference"]["scope"] == "global"


def test_les_desaccords_reels_sont_conserves_non_resolus():
    """Ils existent : les taire donnerait une base plus propre et moins vraie."""
    with open(CHEMIN_DERIVE, "r", encoding="utf-8") as flux:
        monde = json.load(flux)

    assert monde["counts"]["disagreements"] > 0
    assert all(d["resolved"] == "no" for d in monde["disagreements"])


# ----------------------------------------------------------------------
# 6. Répondre, et dire UNKNOWN (phase 52.2)
# ----------------------------------------------------------------------

def test_une_question_sur_un_pays_trouve_sa_reponse_et_sa_provenance():
    """Une valeur sans provenance n'est pas une connaissance dans ce dépôt."""
    reponse = answer_field("Sénégal", "capital")

    assert reponse["status"] == "FOUND"
    assert reponse["value"] == "Dakar"
    assert reponse["scope"] == "country:sn"
    assert reponse["provenance"]["source_tier"] == "TIER_C_SECONDARY"


def test_un_pays_se_nomme_en_francais_en_anglais_ou_par_son_code():
    """Trois façons de désigner le même pays, une seule réponse."""
    codes = {
        answer_country(nom)["country"]["iso3"]
        for nom in ("Sénégal", "Senegal", "SN", "sen")
    }

    assert codes == {"SEN"}


def test_un_nom_inconnu_ne_rend_jamais_le_pays_le_plus_proche():
    """
    « Niger » et « Nigeria » sont deux pays. Rendre l'un pour l'autre serait la
    pire réponse possible : plausible et fausse.
    """
    reponse = answer_country("Nigerie")

    assert reponse["status"] == "UNKNOWN"
    assert reponse["country"] is None
    assert reponse["what_would_settle_it"]


def test_deux_pays_aux_noms_voisins_restent_distincts():
    """La contre-épreuve : les deux existent et ne se confondent pas."""
    niger = answer_country("Niger")["country"]
    nigeria = answer_country("Nigeria")["country"]

    assert niger["iso3"] == "NER"
    assert nigeria["iso3"] == "NGA"


def test_un_champ_que_la_source_ne_porte_pas_rend_unknown():
    """La plateforme ne complète pas une source par ce qu'un modèle croit savoir."""
    monde = build_world_knowledge(
        "ISO3166-1-Alpha-3,ISO3166-1-Alpha-2,official_name_en,Capital\nMLI,ML,Mali,\n"
    )

    reponse = answer_field("Mali", "capital", monde)

    assert reponse["status"] == "UNKNOWN"
    assert "croit savoir" in reponse["reason"]


def test_un_champ_inexistant_dit_ceux_qui_existent():
    """Une erreur de champ ne doit pas se lire comme une absence de donnée."""
    reponse = answer_field("Sénégal", "president")

    assert reponse["status"] == "UNKNOWN"
    assert "n'existe pas dans la connaissance dérivée" in reponse["reason"]


def test_un_desaccord_voyage_avec_la_valeur():
    """Une réponse qui le tairait serait plus nette et moins vraie."""
    monde = build_world_knowledge(
        CSV_CODES, [{"cca3": "SEN", "capital": ["Saint-Louis"], "currencies": {"XOF": {}}}],
    )

    reponse = answer_field("Sénégal", "capital", monde)

    assert reponse["disagreements"][0]["country_profile"] == "Saint-Louis"
    assert reponse["disagreements"][0]["resolved"] == "no"


def test_un_monde_jamais_construit_le_dit_au_lieu_d_etre_vide():
    """Absent n'est pas vide, et la différence doit se voir avant la question."""
    from src.knowledge_engine.world import load_world

    monde = load_world("/chemin/qui/n/existe/pas.json")

    assert monde["built"] is False
    assert answer_country("Sénégal", monde)["status"] == "UNKNOWN"
    assert "jamais été construite" in answer_country("Sénégal", monde)["reason"]


def test_le_rapport_nomme_ce_qu_il_ne_sert_pas():
    """Le droit, l'administration et les langues ne se transportent pas."""
    ne_fait_pas = " ".join(world_report()["does_not"])

    assert "approximation" in ne_fait_pas
    assert "droit, l'administration ou les langues" in ne_fait_pas


# ----------------------------------------------------------------------
# 7. Les routes (phase 52.2)
# ----------------------------------------------------------------------

@pytest.fixture
def client_mondial(monkeypatch):
    """Client HTTP et clé nommée."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    with TestClient(server_module.app) as essai:
        yield essai, {"X-API-Key": "cle-awa"}
    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())


def test_la_route_sert_un_pays_avec_sa_portee(client_mondial):
    """Une donnée que rien ne lit n'est pas une connaissance."""
    client, cle = client_mondial

    reponse = client.get("/knowledge/world/country/SEN", headers=cle).json()

    assert reponse["status"] == "FOUND"
    assert reponse["country"]["official_name_en"] == "Senegal"
    assert reponse["scope"] == "country:sn"


def test_la_route_rend_un_champ_avec_sa_provenance(client_mondial):
    """Une valeur sans provenance n'entre pas et ne sort pas."""
    client, cle = client_mondial

    reponse = client.get(
        "/knowledge/world/country/France?field=currency_code", headers=cle,
    ).json()

    assert reponse["value"] == "EUR"
    assert "country-codes.csv" in reponse["provenance"]["source_url"]


def test_un_pays_inconnu_repond_200_et_unknown(client_mondial):
    """
    « Je ne sais pas » est une réponse, et elle porte ce qui trancherait. Un 404
    laisserait croire à une panne de route.
    """
    client, cle = client_mondial

    reponse = client.get("/knowledge/world/country/Atlantide", headers=cle)

    assert reponse.status_code == 200
    assert reponse.json()["status"] == "UNKNOWN"
    assert reponse.json()["what_would_settle_it"]


def test_l_etat_publie_dit_ce_qu_il_ne_fait_pas(client_mondial):
    """Le dire vaut mieux que le laisser croire."""
    client, cle = client_mondial

    etat = client.get("/knowledge/world", headers=cle).json()

    assert etat["built"] is True
    assert etat["counts"]["countries"] >= 200
    assert any("approximation" in ligne for ligne in etat["does_not"])


def test_les_routes_mondiales_exigent_une_cle(client_mondial):
    """Aucune n'est publique."""
    client, _ = client_mondial

    assert client.get("/knowledge/world").status_code in (401, 403)
