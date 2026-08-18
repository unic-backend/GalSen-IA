"""
La connaissance mondiale cherchable, et les extraits (phases 54.2 et 54.3).

54.2 — la connaissance mondiale existait depuis le VOLET 52 et **rien ne la
cherchait** : on ne l'atteignait qu'en donnant un code ISO ou un nom exact à
`/knowledge/world/country/…`. Une question posée en langue — « quelle est la
monnaie du Sénégal » — ne la touchait pas.

54.3 — un résultat qui montre un titre et un score demande qu'on lui fasse
confiance. Un **extrait** montre où est la correspondance et laisse juger d'un
coup d'œil. Toute la difficulté est ce qu'un extrait ne doit pas devenir : un
résumé écrit par la plateforme, c'est-à-dire une fabrication sous un autre nom.

Ce que ces tests gardent :

1. **Aucune approximation sur les pays**, et **un code n'est reconnu qu'écrit
   comme un code** — le premier essai rendait l'Estonie et le Laos pour
   « quelle **est** la monnaie du Sénégal ».
2. **Un extrait est verbatim**, coupé aux bords seulement.
3. **Sans terme trouvé, l'extrait dit qu'il est le début du document**, pas une
   correspondance.
4. **Ce qui est retenu par un filtre est compté**, jamais tu.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.services.search.excerpt import (  # noqa: E402
    LARGEUR_EXTRAIT,
    excerpt_around,
    excerpt_report,
)
from src.services.search.providers import WorldSearchProvider  # noqa: E402
from src.services.search.types import SearchQuery, SearchSource  # noqa: E402


@pytest.fixture
def mondial():
    """Le fournisseur branché sur la connaissance mondiale réelle du dépôt."""
    return WorldSearchProvider()


def _identifiants(resultats):
    """Les codes rendus."""
    return sorted(resultat.id for resultat in resultats)


# ----------------------------------------------------------------------
# 1. La connaissance mondiale devient cherchable (54.2)
# ----------------------------------------------------------------------

def test_une_question_en_langue_atteint_la_connaissance_mondiale(mondial):
    """Le point de la phase : elle existait, rien ne la cherchait."""
    resultats = mondial.search(SearchQuery(query="quelle est la monnaie du Sénégal ?"))

    assert _identifiants(resultats) == ["SEN"]
    assert resultats[0].source is SearchSource.WORLD


def test_un_mot_francais_courant_ne_declenche_pas_un_pays(mondial):
    """
    **Le défaut trouvé en écrivant cette phase.** `EST` est l'Estonie, `LA` le
    Laos : « quelle **est** la monnaie du Sénégal » rendait trois pays. Un code
    n'est reconnu qu'en majuscules, telles que la norme l'écrit.
    """
    resultats = mondial.search(SearchQuery(query="quelle est la monnaie du Sénégal ?"))

    assert "EST" not in _identifiants(resultats)
    assert "LAO" not in _identifiants(resultats)


def test_un_code_ecrit_comme_un_code_est_reconnu(mondial):
    """« SEN » est un pays ; « sen » dans une phrase est un mot."""
    assert _identifiants(mondial.search(SearchQuery(query="SEN"))) == ["SEN"]
    assert mondial.search(SearchQuery(query="sen")) == []


def test_deux_pays_aux_noms_voisins_ne_se_declenchent_pas_l_un_l_autre(mondial):
    """« Nigeria » ne déclenche pas « Niger » : ce sont deux pays."""
    assert _identifiants(mondial.search(SearchQuery(query="Nigeria"))) == ["NGA"]
    assert _identifiants(mondial.search(SearchQuery(query="Niger"))) == ["NER"]


def test_une_requete_qui_ne_nomme_aucun_pays_ne_rend_rien(mondial):
    """Rendre le plus proche serait plausible et faux."""
    assert mondial.search(SearchQuery(query="atlantide")) == []


def test_le_resultat_porte_la_portee_et_la_provenance(mondial):
    """Une valeur sans provenance n'entre pas et ne sort pas."""
    resultat = mondial.search(SearchQuery(query="France"))[0]

    assert resultat.metadata["scope"] == "country:fr"
    assert "country-codes.csv" in resultat.metadata["provenance"]["source_url"]


def test_la_source_dit_ce_qu_elle_ne_porte_pas(mondial):
    """
    Ni droit, ni administration, ni langues : ces sujets ne se transportent pas
    d'un pays à l'autre. Le dire évite qu'une absence se lise comme un trou.
    """
    mondial.search(SearchQuery(query="Sénégal"))

    ne_porte_pas = " ".join(mondial.last_method["carries_no"])
    assert "droit" in ne_porte_pas
    assert "administration" in ne_porte_pas


def test_la_source_dit_qu_elle_n_appartient_a_personne(mondial):
    """Sans cela, on chercherait un filtre de propriété absent."""
    mondial.search(SearchQuery(query="Sénégal"))

    assert "publique" in mondial.last_method["ownership"]


def test_une_connaissance_mondiale_absente_le_dit(mondial):
    """Absente n'est pas vide."""
    orphelin = WorldSearchProvider(world_knowledge={"countries": [], "reason": "jamais construite"})

    assert orphelin.search(SearchQuery(query="Sénégal")) == []
    assert "jamais construite" in orphelin.last_method["reason"]


# ----------------------------------------------------------------------
# 2. Les extraits (54.3)
# ----------------------------------------------------------------------

TEXTE = (
    "Le rapport annuel décrit les rendements observés dans la vallée du fleuve. "
    "La campagne agricole du Sénégal a bénéficié d'une pluviométrie favorable. "
    "Les stocks restent toutefois inférieurs aux besoins déclarés."
)


def test_un_extrait_est_centre_sur_le_terme_trouve():
    """Il montre où est la correspondance."""
    extrait = excerpt_around(TEXTE, ["pluviométrie"])

    assert "pluviométrie" in extrait["text"]
    assert extrait["centered_on"] == "pluviométrie"
    assert extrait["is_beginning"] is False


def test_un_extrait_est_verbatim():
    """Un extrait reformulé serait un résumé, c'est-à-dire une fabrication."""
    extrait = excerpt_around(TEXTE, ["campagne"])

    nu = extrait["text"].strip("…")
    assert nu in TEXTE


def test_la_coupure_est_marquee_aux_bords():
    """Un recollement silencieux produirait une phrase absente du document."""
    long = "début. " + ("mot " * 200) + "cible " + ("mot " * 200) + "fin."

    extrait = excerpt_around(long, ["cible"])

    assert extrait["truncated_left"] is True
    assert extrait["truncated_right"] is True
    assert extrait["text"].startswith("…") and extrait["text"].endswith("…")


def test_un_texte_court_n_est_pas_marque_tronque():
    """Le drapeau doit vouloir dire quelque chose."""
    extrait = excerpt_around("Un texte court.", ["texte"])

    assert extrait["truncated_left"] is False
    assert extrait["truncated_right"] is False
    assert extrait["text"] == "Un texte court."


def test_sans_terme_trouve_l_extrait_dit_qu_il_est_le_debut():
    """
    Rendre les premiers caractères en les laissant passer pour une
    correspondance serait le mensonge discret que ce dépôt refuse.
    """
    extrait = excerpt_around(TEXTE, ["bauxite"])

    assert extrait["is_beginning"] is True
    assert extrait["centered_on"] is None
    assert "début" in extrait["note"]


def test_l_accent_ne_fait_pas_rater_la_position():
    """« senegal » doit situer « Sénégal » — replier sert à trouver."""
    extrait = excerpt_around(TEXTE, ["senegal"])

    assert extrait["centered_on"] == "senegal"
    assert "Sénégal" in extrait["text"], "L'extrait rendu garde le texte d'origine"


def test_un_document_sans_texte_ne_produit_pas_d_extrait():
    """Rien à montrer, et le dire."""
    extrait = excerpt_around("", ["quoi que ce soit"])

    assert extrait["text"] == ""
    assert "aucun extrait" in extrait["note"].lower()


def test_le_rapport_d_extraits_distingue_correspondance_et_debut():
    """Compter les deux ensemble cacherait des résultats sans correspondance."""
    rapport = excerpt_report([
        excerpt_around(TEXTE, ["campagne"]),
        excerpt_around(TEXTE, ["bauxite"]),
    ])

    assert rapport["excerpts"] == 2
    assert rapport["centered_on_a_term"] == 1
    assert rapport["beginnings"] == 1
    assert rapport["width"] == LARGEUR_EXTRAIT
    assert any("verbatim" in ligne for ligne in rapport["rules"])


# ----------------------------------------------------------------------
# 3. De bout en bout, par la recherche unifiée
# ----------------------------------------------------------------------

@pytest.fixture
def recherche():
    """Un gestionnaire de recherche portant documents et monde."""
    from src.document_intelligence_engine.document_manager import DocumentManagerImpl
    from src.document_intelligence_engine.types import DocumentItem, DocumentType
    from src.services.search.manager import SearchManagerImpl
    from src.services.search.providers import DocumentSearchProvider

    documents = DocumentManagerImpl()
    for identifiant, titre, contenu, metadonnees in [
        ("doc-public", "Rapport agricole", TEXTE, {"visibility": "public"}),
        ("doc-fatou", "Note privée",
         "La campagne agricole vue par quelqu'un d'autre.", {"user_id": "fatou"}),
    ]:
        documents.register_document(DocumentItem(
            document_id=identifiant, document_type=DocumentType.TXT,
            title=titre, content=contenu, metadata=metadonnees,
        ))
        documents.index_document(identifiant)

    gestionnaire = SearchManagerImpl()
    gestionnaire.register_provider(DocumentSearchProvider(documents))
    gestionnaire.register_provider(WorldSearchProvider())
    return gestionnaire


def test_un_resultat_documentaire_porte_son_extrait(recherche):
    """Le score seul demandait qu'on lui fasse confiance."""
    reponse = recherche.search(SearchQuery(
        query="pluviométrie", sources=[SearchSource.DOCUMENT], subject="awa",
    ))

    extrait = reponse.results[0].metadata["excerpt"]
    assert "pluviométrie" in extrait["text"]
    assert extrait["centered_on"] == "pluviométrie"


def test_le_resume_reste_vide_a_cote_de_l_extrait(recherche):
    """
    Un extrait n'est pas un résumé : le résumé reste `None` parce que rien ici
    ne l'écrit.
    """
    reponse = recherche.search(SearchQuery(
        query="pluviométrie", sources=[SearchSource.DOCUMENT], subject="awa",
    ))

    assert reponse.results[0].summary is None


def test_ce_qui_est_retenu_par_un_filtre_est_compte(recherche):
    """
    Une source qui filtre en silence se lit comme une source qui n'a rien
    trouvé. Chaque fournisseur le comptait déjà ; personne ne l'additionnait.
    """
    reponse = recherche.search(SearchQuery(
        query="campagne agricole", sources=[SearchSource.DOCUMENT], subject="awa",
    ))

    assert reponse.methods["withheld_total"] >= 1
    assert reponse.methods["withheld_by_source"]["document"] >= 1


def test_sans_retenue_aucun_compteur_n_est_publie(recherche):
    """Un compteur à zéro affiché partout finirait par ne plus être lu."""
    reponse = recherche.search(SearchQuery(
        query="Sénégal", sources=[SearchSource.WORLD],
    ))

    assert "withheld_total" not in reponse.methods


def test_les_deux_sources_repondent_a_la_meme_question(recherche):
    """La recherche unifiée doit maintenant atteindre la connaissance mondiale."""
    reponse = recherche.search(SearchQuery(
        query="Sénégal", sources=[SearchSource.DOCUMENT, SearchSource.WORLD],
        subject="awa",
    ))

    assert set(reponse.sources_used) == {"document", "world"}
    assert any(r.source is SearchSource.WORLD for r in reponse.results)
