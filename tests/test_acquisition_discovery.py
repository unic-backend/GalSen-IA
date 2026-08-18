"""
La découverte : profondeur 1, même domaine, source activée (ADR-021, étape 5).

Découvrir n'est pas explorer, et la différence tient à trois refus que ces tests
gardent : une source non activée ne rend rien, un lien hors du domaine est
écarté avec sa raison, et un plafond arrête l'exécution au lieu de la laisser
grossir.

Aucune requête réseau : le récupérateur est injecté.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.discovery import (  # noqa: E402
    DiscoveryRefused,
    discover,
    discovery_report,
    links_from_html,
    sitemaps_from_robots,
    urls_from_feed,
    urls_from_sitemap,
)
from src.acquisition.fetcher import FetchResult  # noqa: E402
from src.knowledge_engine.source_registry import SourceTier  # noqa: E402

ROBOTS = """User-agent: *
Disallow: /prive/
Sitemap: https://www.ansd.sn/sitemap.xml
"""

SITEMAP = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.ansd.sn/rapport-2024.pdf</loc></url>
  <url><loc>https://www.ansd.sn/annuaire-2023.pdf</loc></url>
  <url><loc>https://ailleurs.example/copie.pdf</loc></url>
</urlset>"""

INDEX_DE_PLANS = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://www.ansd.sn/sitemap-publications.xml</loc></sitemap>
</sitemapindex>"""

PLAN_ENFANT = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://www.ansd.sn/publication-a.pdf</loc></url>
</urlset>"""

FIL_RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item><link>https://www.ansd.sn/note-2026.pdf</link></item>
</channel></rss>"""

FIL_ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry><link href="https://www.ansd.sn/atom-2026.pdf"/></entry>
</feed>"""

PAGE = b"""<html><body>
  <a href="/publications/etude.pdf">Etude</a>
  <a href="https://ailleurs.example/ailleurs.pdf">Ailleurs</a>
  <a href="javascript:void(0)">Menu</a>
</body></html>"""


def _source(**surcharges):
    """Une entrée de registre activée, comme le sera une source du pilote."""
    entree = {
        "name": "ANSD", "domain": "ansd.sn", "enabled": True,
        "tier": SourceTier.A_PRIMARY_OFFICIAL,
        "allowed_content_types": ["pdf", "html", "xml"],
        "access_policy": {"rate_limit_rps": 1000.0},
    }
    entree.update(surcharges)
    return entree


class _Serveur:
    """Un récupérateur injecté : une table d'URL vers des octets."""

    def __init__(self, table):
        self.table = table
        self.appels = []

    def __call__(self, url, **_):
        self.appels.append(url)
        corps = self.table.get(url)
        if corps is None:
            raise RuntimeError(f"404 {url}")
        return FetchResult(url=url, status=200, body=corps, size=len(corps))


# ----------------------------------------------------------------------
# Ce qui empêche ce module d'être un explorateur
# ----------------------------------------------------------------------

def test_une_source_non_activee_ne_decouvre_rien():
    """
    Inscrire n'est pas activer. C'est ce refus qui fait qu'aujourd'hui la
    découverte ne peut atteindre **aucune** source réelle.
    """
    with pytest.raises(DiscoveryRefused) as echec:
        discover(_source(enabled=False), robots_txt=ROBOTS)

    assert "pas activée" in str(echec.value)


def test_une_source_de_decouverte_seule_n_est_jamais_parcourue():
    """`TIER_D` peut faire chercher ailleurs ; il n'est pas la source."""
    with pytest.raises(DiscoveryRefused) as echec:
        discover(_source(tier=SourceTier.D_DISCOVERY_ONLY), robots_txt=ROBOTS)

    assert "piste" in str(echec.value)


def test_un_lien_hors_du_domaine_est_ecarte_avec_sa_raison():
    """Profondeur 1, même domaine : le lien vers ailleurs ne devient pas candidat."""
    serveur = _Serveur({"https://www.ansd.sn/sitemap.xml": SITEMAP})

    rapport = discover(_source(), robots_txt=ROBOTS, fetch_fn=serveur)

    adresses = [c["url"] for c in rapport["candidates"]]
    assert "https://ailleurs.example/copie.pdf" not in adresses
    assert len(adresses) == 2
    ecarte = [d for d in rapport["dropped"] if "ailleurs" in d["url"]][0]
    assert "Hors du domaine" in ecarte["reason"]


def test_un_domaine_qui_imite_le_domaine_declare_n_est_pas_retenu():
    """La comparaison porte sur les étiquettes : `faux-ansd.sn` n'est pas l'ANSD."""
    serveur = _Serveur({})

    rapport = discover(
        _source(), robots_txt="", seeds=["https://faux-ansd.sn/x.pdf"], fetch_fn=serveur
    )

    assert rapport["candidates"] == []
    # Un vrai sous-domaine, lui, passe.
    autre = discover(
        _source(), robots_txt="", seeds=["https://data.ansd.sn/x.pdf"], fetch_fn=serveur
    )
    assert len(autre["candidates"]) == 1


def test_un_schema_non_acceptable_est_ecarte():
    """Une URL découverte est une donnée venue de l'extérieur, pas une intention."""
    serveur = _Serveur({"https://www.ansd.sn/index.html": PAGE})

    rapport = discover(
        _source(), robots_txt="", index_pages=["https://www.ansd.sn/index.html"],
        fetch_fn=serveur,
    )

    raisons = [d["reason"] for d in rapport["dropped"]]
    assert any("Schéma" in raison for raison in raisons)


def test_le_plafond_arrete_l_execution_au_lieu_de_la_laisser_grossir():
    """Un plan de site institutionnel peut porter des dizaines de milliers d'entrées."""
    serveur = _Serveur({"https://www.ansd.sn/sitemap.xml": SITEMAP})

    rapport = discover(_source(), robots_txt=ROBOTS, max_links=1, fetch_fn=serveur)

    assert len(rapport["candidates"]) == 1
    assert any("Plafond" in d["reason"] for d in rapport["dropped"])


# ----------------------------------------------------------------------
# Les quatre modes
# ----------------------------------------------------------------------

def test_le_plan_de_site_est_lu_depuis_robots():
    """Le mode le plus fiable : le site le publie précisément pour être lu."""
    assert sitemaps_from_robots(ROBOTS) == ["https://www.ansd.sn/sitemap.xml"]


def test_un_index_de_plans_mene_a_ses_plans_sans_les_confondre_avec_des_documents():
    """
    Confondre un `<sitemapindex>` et un `<urlset>` ferait entrer des plans de
    site dans la base comme s'ils étaient des documents.
    """
    urls, imbriques = urls_from_sitemap(INDEX_DE_PLANS)
    assert urls == []
    assert imbriques == ["https://www.ansd.sn/sitemap-publications.xml"]

    serveur = _Serveur({
        "https://www.ansd.sn/sitemap.xml": INDEX_DE_PLANS,
        "https://www.ansd.sn/sitemap-publications.xml": PLAN_ENFANT,
    })
    rapport = discover(_source(), robots_txt=ROBOTS, fetch_fn=serveur)

    assert [c["url"] for c in rapport["candidates"]] == [
        "https://www.ansd.sn/publication-a.pdf"
    ]


@pytest.mark.parametrize("fil,attendu", [
    (FIL_RSS, "https://www.ansd.sn/note-2026.pdf"),
    (FIL_ATOM, "https://www.ansd.sn/atom-2026.pdf"),
])
def test_rss_et_atom_sont_lus_tous_les_deux(fil, attendu):
    """RSS met l'adresse dans le texte, Atom dans `href` : n'en lire qu'un en perdrait la moitié."""
    assert urls_from_feed(fil) == [attendu]


def test_une_page_d_index_declaree_rend_ses_liens_resolus():
    """Un lien relatif doit être résolu contre l'adresse de la page."""
    liens = links_from_html(PAGE, "https://www.ansd.sn/index.html")

    assert "https://www.ansd.sn/publications/etude.pdf" in liens


def test_un_semis_colle_par_une_personne_est_filtre_comme_le_reste():
    """Le repli n'est pas « on explore » : c'est une personne qui colle des URL."""
    rapport = discover(
        _source(), robots_txt="",
        seeds=["https://www.ansd.sn/manuel.pdf", "https://ailleurs.example/x.pdf"],
        fetch_fn=_Serveur({}),
    )

    assert [c["mode"] for c in rapport["candidates"]] == ["seed"]
    assert len(rapport["dropped"]) == 1


# ----------------------------------------------------------------------
# Ce qui ne rend rien le dit
# ----------------------------------------------------------------------

def test_un_site_sans_plan_ni_fil_ni_index_le_dit_au_lieu_de_ressembler_a_un_site_vide():
    """Une liste vide sans explication ferait croire à une institution sans publications."""
    rapport = discover(_source(), robots_txt="", fetch_fn=_Serveur({}))

    assert rapport["candidates"] == []
    assert set(rapport["modes_without_result"]) == {"sitemap", "feed", "index", "seed"}


def test_une_ressource_absente_n_est_pas_une_panne():
    """Un plan de site annoncé mais introuvable ne doit pas arrêter la découverte."""
    rapport = discover(
        _source(), robots_txt=ROBOTS, seeds=["https://www.ansd.sn/a.pdf"],
        fetch_fn=_Serveur({}),
    )

    assert [c["url"] for c in rapport["candidates"]] == ["https://www.ansd.sn/a.pdf"]


def test_un_xml_illisible_ne_leve_pas():
    """Un fichier corrompu est une donnée externe comme une autre."""
    assert urls_from_sitemap("<urlset><url><loc>pas fermé".encode("utf-8")) == ([], [])
    assert urls_from_feed("n'importe quoi".encode("utf-8")) == []


def test_le_rapport_nomme_ce_que_la_decouverte_ne_voit_pas():
    """Les angles morts sont écrits, pas sous-entendus."""
    rapport = discovery_report()

    assert rapport["depth"] == 1
    assert rapport["follows_links_inside_documents"] is False
    assert rapport["free_web_search"] is False
    assert rapport["requires_enabled_source"] is True
    assert any("ElementTree" in ligne for ligne in rapport["not_detected"])


def test_ce_module_ne_suit_aucun_lien_trouve_dans_un_document():
    """
    La limite structurelle : la découverte lit des **index**, jamais des
    documents. Ce test garde l'absence d'un chemin, pas la présence d'un autre.
    """
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "src", "acquisition", "discovery.py"), encoding="utf-8") as f:
        source = f.read()

    # Aucune primitive réseau : tout passe par le récupérateur, qui applique
    # robots.txt, le débit et le plafond.
    for interdit in ("requests.", "urlopen", "httpx.", "socket."):
        assert interdit not in source, f"La découverte atteint l'extérieur via {interdit}"

    # Et aucun moteur de recherche : « cherche sur internet » n'entre par aucune
    # porte, les points de départ viennent du registre.
    for moteur in ("WebSearchTool", "duckduckgo", "tools.web_search"):
        assert moteur not in source, f"La découverte passe par {moteur}"
