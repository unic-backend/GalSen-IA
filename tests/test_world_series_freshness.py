"""
Séries mesurées et fraîcheur (phases 52.3 et 53.1).

Une base de connaissance ne devient pas fausse d'un coup. Elle le devient comme
un almanach imprimé : lentement, en silence, chaque page ayant toujours l'air
juste. Le chiffre de population correct en 2024 est **le même nombre** en 2030 ;
ce qui a changé, c'est ce que signifie le servir sans dire quand il a été mesuré.

Ce que ces tests gardent :

1. **Rien n'est interpolé ni extrapolé.** Une année absente le reste. Tracer une
   droite entre 2019 et 2023 inventerait quatre mesures indiscernables des
   vraies dès qu'elles seraient écrites.
2. **Une valeur n'est jamais servie sans son année.** L'année est la moitié du
   fait.
3. **Un pays absent rend `UNKNOWN`, jamais zéro.** Zéro est une mesure : cela
   veut dire que quelqu'un n'a compté personne.
4. **Un agrégat n'est pas un pays.** `WLD` et `ARB` sont réels et utiles ;
   mêlés aux pays, ils rendraient faux tout décompte de couverture.
5. **Une valeur périmée est servie avec son âge**, ni remplacée, ni cachée.
"""

import os
import sys
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.freshness import (  # noqa: E402
    CADENCE_PAR_DEFAUT,
    Freshness,
    cadence_of,
    freshness_of_series,
    freshness_of_year,
    freshness_report,
)
from src.knowledge_engine.series import (  # noqa: E402
    SeriesRefused,
    answer_series,
    build_series,
    coverage,
    known_country_codes,
    latest,
    load_series,
    read_series,
    series_report,
)

CSV_POPULATION = (
    "Country Name,Country Code,Year,Value\n"
    "Senegal,SEN,2019,16296364\n"
    "Senegal,SEN,2023,17763163\n"
    "France,FRA,2023,68170228\n"
    "World,WLD,2023,8024997000\n"
    "Ligne cassée,XXX,mille,12\n"
    "Sans valeur,SEN,2024,\n"
)

CODES = ["SEN", "FRA"]


def _en(annee: int) -> datetime:
    """Un instant de référence, pour ne pas dépendre de l'horloge réelle."""
    return datetime(annee, 6, 1, tzinfo=timezone.utc)


@pytest.fixture
def series():
    """Les séries construites depuis l'exemple."""
    return build_series({"population": CSV_POPULATION}, CODES)


# ----------------------------------------------------------------------
# 1. Rien n'est comblé
# ----------------------------------------------------------------------

def test_une_annee_absente_le_reste(series):
    """
    Le point de la phase. Tracer une droite entre 2019 et 2023 inventerait
    quatre mesures indiscernables des vraies.
    """
    reponse = answer_series("SEN", "population", series, year="2021")

    assert reponse["status"] == "UNKNOWN"
    assert "Rien n'est interpolé" in reponse["reason"]


def test_les_annees_manquantes_sont_nommees(series):
    """Une série continue en apparence et trouée en réalité ment discrètement."""
    couverture = coverage(series["series"]["population"]["values"]["SEN"])

    assert couverture["first_year"] == "2019"
    assert couverture["last_year"] == "2023"
    assert couverture["missing_years"] == ["2020", "2021", "2022"]


def test_la_derniere_annee_mesuree_n_est_pas_l_annee_en_cours(series):
    """Les confondre ferait passer une mesure de 2023 pour une mesure d'aujourd'hui."""
    annee, valeur = latest(series["series"]["population"]["values"]["SEN"])

    assert annee == "2023"
    assert valeur == 17763163


def test_une_valeur_est_toujours_rendue_avec_son_annee(series):
    """L'année n'est pas une métadonnée ici : elle est la moitié du fait."""
    reponse = answer_series("SEN", "population", series)

    assert reponse["year"] == "2023"
    assert reponse["unit"] == "habitants"
    assert reponse["provenance"]["indicator"] == "SP.POP.TOTL"


# ----------------------------------------------------------------------
# 2. Ce qui n'est pas là ne devient pas zéro
# ----------------------------------------------------------------------

def test_un_pays_absent_rend_unknown_jamais_zero(series):
    """Zéro est une mesure : cela veut dire que quelqu'un n'a compté personne."""
    reponse = answer_series("MLI", "population", series)

    assert reponse["status"] == "UNKNOWN"
    assert "Zéro n'est pas rendu" in reponse["reason"]
    assert "value" not in reponse


def test_une_cellule_vide_n_est_pas_un_zero():
    """Elle ferait apparaître un pays qui aurait disparu."""
    lue = read_series(CSV_POPULATION, set(CODES))

    assert "2024" not in lue["countries"]["SEN"]
    assert lue["refused_rows"] == 2


def test_une_serie_inexploitable_est_refusee():
    """Un objet vide laisserait croire qu'aucune mesure n'existe."""
    with pytest.raises(SeriesRefused, match="laisserait croire"):
        build_series({"population": "Country Name,Country Code,Year,Value\n"}, CODES)


def test_une_serie_non_declaree_est_refusee():
    """Une clé inventée passerait sans provenance."""
    with pytest.raises(SeriesRefused, match="inconnue"):
        build_series({"inflation": CSV_POPULATION}, CODES)


# ----------------------------------------------------------------------
# 3. Un agrégat n'est pas un pays
# ----------------------------------------------------------------------

def test_un_agregat_est_separe_et_compte(series):
    """Mêlé aux pays, il rendrait faux tout décompte de couverture."""
    comptes = series["series"]["population"]["counts"]

    assert comptes["countries"] == 2
    assert series["series"]["population"]["aggregates"] == ["WLD"]
    assert comptes["aggregates"] == 1


def test_un_agregat_interroge_dit_ce_qu_il_est(series):
    """« Aucune mesure » serait faux : la mesure existe, ce n'est pas un pays."""
    reponse = answer_series("WLD", "population", series)

    assert reponse["status"] == "UNKNOWN"
    assert "agrégat de la source, pas un pays" in reponse["reason"]


def test_les_codes_pays_viennent_de_la_connaissance_derivee():
    """
    Une liste d'agrégats écrite à la main vieillirait sans que rien ne le dise.
    Elle est remplacée par la confrontation avec les codes ISO dérivés en 52.1.
    """
    from src.knowledge_engine.world import load_world

    codes = known_country_codes(load_world())

    assert "SEN" in codes and "FRA" in codes
    assert "WLD" not in codes and "EUU" not in codes


def test_sans_codes_connus_rien_n_est_declare_agregat():
    """Faute de référence, mieux vaut ne rien trier que trier au hasard."""
    lue = read_series(CSV_POPULATION, set())

    assert lue["aggregates"] == {}
    assert "WLD" in lue["countries"]


# ----------------------------------------------------------------------
# 4. La fraîcheur (phase 53.1)
# ----------------------------------------------------------------------

def test_une_mesure_de_l_an_dernier_est_fraiche():
    """
    Une statistique annuelle n'est pas publiée le 1er janvier. Traiter ce délai
    comme un retard ferait sonner l'alarme sur toutes les séries du dépôt — et
    une alarme toujours allumée n'est plus lue.
    """
    verdict = freshness_of_year("2024", "population", now=_en(2026))

    assert verdict["status"] == Freshness.FRESH.value
    assert verdict["age_years"] == 2


def test_une_mesure_un_peu_ancienne_vieillit_sans_etre_perimee():
    """Elle est servie telle quelle, avec son âge."""
    verdict = freshness_of_year("2022", "population", now=_en(2026))

    assert verdict["status"] == Freshness.AGING.value
    assert "avec son âge" in verdict["reason"]


def test_la_frontiere_entre_les_trois_verdicts_est_explicite():
    """
    Écrite ici pour qu'un changement de seuil se voie dans un diff, plutôt que
    de faire basculer en silence des mesures d'un verdict à l'autre.
    """
    statuts = {
        annee: freshness_of_year(str(annee), "population", now=_en(2026))["status"]
        for annee in range(2020, 2027)
    }

    assert statuts == {
        2026: "FRESH", 2025: "FRESH", 2024: "FRESH",
        2023: "AGING", 2022: "AGING",
        2021: "STALE", 2020: "STALE",
    }


def test_une_mesure_nettement_en_retard_est_dite_perimee_et_rendue_quand_meme():
    """
    La remplacer par une valeur plus récente d'apparence serait une
    fabrication ; la cacher laisserait sans réponse une question qu'une mesure
    datée sait éclairer.
    """
    verdict = freshness_of_year("2010", "population", now=_en(2026))

    assert verdict["status"] == Freshness.STALE.value
    assert verdict["age_years"] == 16
    assert "fabrication" in verdict["reason"]


def test_une_mesure_sans_annee_est_unknown_et_non_fraiche():
    """Une valeur non datée n'est pas récente — elle en a seulement l'air."""
    verdict = freshness_of_year("", "population")

    assert verdict["status"] == Freshness.UNKNOWN.value
    assert verdict["age_years"] == "UNKNOWN"


def test_un_indicateur_non_declare_recoit_une_cadence_indulgente():
    """
    Se tromper vers l'indulgence produit un « AGING » discutable ; se tromper
    vers la sévérité produit un « STALE » faux, qui ferait jeter une mesure
    valide.
    """
    assert cadence_of("inflation") == CADENCE_PAR_DEFAUT
    assert cadence_of("population")["publication_lag_years"] == 1


def test_le_temps_vient_de_l_appelant():
    """Une fonction qui lit l'horloge en douce ne se teste qu'en attendant."""
    assert freshness_of_year("2000", "population", now=_en(2001))["age_years"] == 1
    assert freshness_of_year("2000", "population", now=_en(2030))["age_years"] == 30


def test_les_pays_en_retard_sont_nommes_pas_moyennes(series):
    """Une moyenne cacherait exactement ceux qu'il faut voir."""
    serie = series["series"]["population"]

    verdict = freshness_of_series(serie, "population", now=_en(2026))

    assert verdict["series_last_year"] == "2023"
    assert verdict["behind"] == []
    assert verdict["countries"] == 2


def test_un_pays_en_retard_sur_ses_pairs_est_signale():
    """Un fait mesurable, pas un jugement."""
    csv_retard = CSV_POPULATION + "Erythree,ERI,2011,3213972\n"
    series_retard = build_series({"population": csv_retard}, CODES + ["ERI"])

    verdict = freshness_of_series(
        series_retard["series"]["population"], "population", now=_en(2026),
    )

    assert verdict["behind"][0]["country"] == "ERI"
    assert verdict["behind"][0]["years_behind"] == 12


def test_une_serie_vide_ne_pretend_pas_etre_datee():
    """« Aucune année » n'est pas « année inconnue mais récente »."""
    verdict = freshness_of_series({"values": {}}, "population")

    assert verdict["status"] == Freshness.UNKNOWN.value
    assert verdict["behind"] == []


def test_le_rapport_de_fraicheur_dit_ce_qu_il_ne_fait_pas(series):
    """Aucune source n'est activée : rien n'est rafraîchi ici."""
    rapport = freshness_report(series, now=_en(2026))

    ne_fait_pas = " ".join(rapport["does_not"])
    assert "Rafraîchir" in ne_fait_pas
    assert "Estimer la valeur d'aujourd'hui" in ne_fait_pas
    assert rapport["measured_at_year"] == 2026


# ----------------------------------------------------------------------
# 5. Les séries réellement dérivées dans le dépôt
# ----------------------------------------------------------------------

def test_les_series_du_depot_sont_construites_et_mesurees():
    """Lu dans le fichier versionné, pas reconstruit."""
    reelles = load_series()

    assert reelles["built"] is True
    comptes = series_report(reelles)["series"]
    assert comptes["population"]["countries"] >= 200
    assert comptes["population"]["aggregates"] > 0
    assert comptes["population"]["refused_rows"] == 0


def test_une_mesure_reelle_porte_son_annee_et_sa_provenance():
    """Le Sénégal, mesuré, daté, tracé."""
    reponse = answer_series("SEN", "population", load_series())

    assert reponse["status"] == "FOUND"
    assert reponse["year"].isdigit()
    assert reponse["value"] > 10_000_000
    assert "population.csv" in reponse["provenance"]["source_url"]


def test_le_rapport_reel_nomme_les_series_en_retard():
    """Elles existent : les taire donnerait une base plus propre et moins vraie."""
    rapport = freshness_report(load_series())

    verdicts = {cle: valeur["status"] for cle, valeur in rapport["series"].items()}
    assert set(verdicts) == {"population", "gdp"}
    assert all(statut != Freshness.UNKNOWN.value for statut in verdicts.values())


# ----------------------------------------------------------------------
# 6. Les routes
# ----------------------------------------------------------------------

@pytest.fixture
def client_series(monkeypatch):
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


def test_la_route_rend_la_mesure_avec_son_annee_et_sa_fraicheur(client_series):
    """Les deux phases branchées ensemble : la valeur, sa date, son âge."""
    client, cle = client_series

    reponse = client.get(
        "/knowledge/world/country/Sénégal/series/population", headers=cle,
    ).json()

    assert reponse["status"] == "FOUND"
    assert reponse["year"].isdigit()
    assert reponse["scope"] == "country:sn"
    assert reponse["freshness"]["status"] in ("FRESH", "AGING", "STALE")


def test_la_route_refuse_d_inventer_une_annee_absente(client_series):
    """1800 n'est pas dans la série, et rien ne la comble."""
    client, cle = client_series

    reponse = client.get(
        "/knowledge/world/country/SEN/series/population?year=1800", headers=cle,
    ).json()

    assert reponse["status"] == "UNKNOWN"
    assert "interpolé" in reponse["reason"]


def test_un_pays_inconnu_ne_devient_pas_une_serie_vide(client_series):
    """Le refus vient du pays, avant même la série."""
    client, cle = client_series

    reponse = client.get(
        "/knowledge/world/country/Atlantide/series/population", headers=cle,
    ).json()

    assert reponse["status"] == "UNKNOWN"
    assert reponse["country"] is None


def test_l_etat_des_series_publie_leur_fraicheur(client_series):
    """Un opérateur doit voir l'âge de ce qu'il sert."""
    client, cle = client_series

    etat = client.get("/knowledge/world/series", headers=cle).json()

    assert set(etat["series"]) == {"population", "gdp"}
    assert etat["freshness"]["series"]["population"]["series_last_year"].isdigit()
    assert any("Rafraîchir" in ligne for ligne in etat["freshness"]["does_not"])


def test_les_routes_de_series_exigent_une_cle(client_series):
    """Aucune n'est publique."""
    client, _ = client_series

    assert client.get("/knowledge/world/series").status_code in (401, 403)
