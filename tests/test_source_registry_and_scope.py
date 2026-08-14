"""
Le registre des sources et la récupération par portée (VOLET 35, ch. 03 à 05).

Trois manques, un par chapitre :

- **03** — `SourceCategory` existait et `retrieve_reliable()` s'en servait, mais
  **la catégorie était déclarée par celui qui ingérait** : un blog rangé en
  `government` pesait autant que le Journal officiel.
- **04** — la base portait deux axes depuis l'ADR-019 et la récupération les
  ignorait : une question de droit sénégalais et une question d'irrigation
  étaient traitées de la même façon.
- **05** — rien ne disait, dans une réponse, si elle avait été construite avec
  des sources du pays de la question.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.scope import KnowledgeSubject  # noqa: E402
from src.knowledge_engine.scoped_retrieval import (  # noqa: E402
    PORTEE_LOCALE,
    apply_scope_policy,
    detect_scope,
    retrieve_scoped,
    scope_notice,
)
from src.knowledge_engine.source_registry import (  # noqa: E402
    SourceRefused,
    SourceTier,
    acquirable_sources,
    check_source,
    denied_reason,
    known_sources,
    load_registry,
    registry_report,
)
from src.knowledge_engine.types import SourceCategory  # noqa: E402


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base de connaissances isolée, en mémoire."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    return KnowledgeManagerImpl()


@pytest.fixture
def document(tmp_path):
    """Un document quelconque, assez long pour être ingéré."""
    chemin = tmp_path / "note.md"
    chemin.write_text("Le semis du mil suit les premières pluies. " * 20, encoding="utf-8")
    return str(chemin)


# ----------------------------------------------------------------------
# Chapitre 03 — le registre des sources
# ----------------------------------------------------------------------

def test_le_registre_declare_des_sources_et_des_refus():
    """Le fichier existe, il est lu, et il porte les deux listes."""
    rapport = registry_report()

    assert rapport["loaded"] is True
    assert rapport["sources"] >= 10
    assert rapport["denied_domains"] >= 8
    assert PORTEE_LOCALE in rapport["by_scope"]


def test_une_source_de_la_liste_de_refus_est_refusee_avec_sa_raison():
    """
    Rétrograder en silence laisserait la source entrer et peser un peu, ce qui
    est pire que de la refuser : le refus porte sa raison.
    """
    raison = denied_reason("https://www.tiktok.com/@compte/video/123")

    assert raison, "Une plateforme vidéo passe le registre"
    assert "vidéo" in raison.lower() or "source" in raison.lower()

    verdict = check_source("https://www.tiktok.com/@compte/video/123", SourceCategory.OPINION)
    assert verdict["allowed"] is False
    assert "refusée" in verdict["reason"]


def test_une_autorite_ne_se_declare_pas_soi_meme():
    """
    Le cœur du chapitre : « ceci est officiel » devient vérifiable au lieu
    d'être seulement crédible.
    """
    usurpation = check_source("https://mon-blog-perso.example/loi", SourceCategory.GOVERNMENT)
    modeste = check_source("https://mon-blog-perso.example/loi", SourceCategory.OPINION)

    assert usurpation["allowed"] is False
    assert "registre" in usurpation["reason"]
    assert modeste["allowed"] is True


def test_une_source_inscrite_garde_son_autorite():
    """Le registre autorise ce qu'il déclare, sous-domaines compris."""
    verdict = check_source("https://www.ansd.sn/publication", SourceCategory.GOVERNMENT)

    assert verdict["allowed"] is True
    assert verdict["registry_category"] == SourceCategory.GOVERNMENT.value
    assert "ANSD" in verdict["reason"]


def test_un_domaine_qui_imite_un_domaine_inscrit_n_en_herite_pas():
    """
    La comparaison porte sur les étiquettes, pas sur la fin de la chaîne :
    sinon « faux-ansd.sn » passerait pour l'ANSD.
    """
    assert check_source("https://faux-ansd.sn/x", SourceCategory.GOVERNMENT)["allowed"] is False
    # Un vrai sous-domaine, lui, hérite bien.
    assert check_source("https://ifan.ucad.sn/x", SourceCategory.PEER_REVIEWED)["allowed"] is True


def test_une_url_relative_au_protocole_est_lue_comme_une_url():
    """
    `//ansd.sn/x` est une adresse parfaitement lisible. Le registre la traitait
    comme « aucune URL », ce qui laissait passer une autorité usurpée par la
    porte des fichiers locaux.
    """
    verdict = check_source("//ansd.sn/rapport", SourceCategory.GOVERNMENT)

    assert verdict["allowed"] is True
    assert verdict["registry_category"] is not None
    assert check_source("//faux-ansd.sn/x", SourceCategory.GOVERNMENT)["allowed"] is False


def test_un_nom_de_fichier_ne_devient_pas_un_domaine():
    """
    Le revers de la règle précédente : `rapport.pdf` ressemble à un domaine et
    n'en est pas un. Lui en inventer un ferait refuser l'ingestion d'un document
    que le projet détient déjà.
    """
    verdict = check_source("rapport.pdf", SourceCategory.OFFICIAL)

    assert verdict["allowed"] is True
    assert "manifeste" in verdict["reason"]
    assert check_source("/data/notes.pdf", SourceCategory.OFFICIAL)["allowed"] is True


# ----------------------------------------------------------------------
# ADR-021 — les champs d'acquisition
# ----------------------------------------------------------------------

def _registre(tmp_path, entree: str) -> str:
    """Écrit un registre d'une source et rend son chemin."""
    chemin = tmp_path / "registre.yaml"
    chemin.write_text("sources:\n" + entree + "\ndeny: []\n", encoding="utf-8")
    return str(chemin)


def test_aucune_source_inscrite_n_est_collectable_par_defaut():
    """
    Le cœur de l'ADR-021 : inscrire n'est pas activer. Les **23** sources
    réelles — 9 sénégalaises, 14 mondiales (12 à la phase 51.2, plus FIFA et le
    CIO à la 56.2) — sont inscrites et **aucune** n'est atteignable par un
    chemin d'acquisition. Le registre a grandi trois fois ; la règle n'a pas
    bougé une seule.
    """
    rapport = registry_report()

    assert rapport["sources"] == 23
    assert rapport["by_registry"] == {"global.yaml": 14, "senegal.yaml": 9}
    assert rapport["enabled"] == 0
    assert rapport["acquirable"] == 0
    assert acquirable_sources() == []


def test_un_rang_replie_est_nomme_et_non_supposé_validé():
    """
    Un rang replié depuis la catégorie est un rang que personne n'a relu.
    Le taire donnerait à une source un régime que personne n'a choisi.
    """
    rapport = registry_report()

    # Les 9 sources sénégalaises ne déclarent pas de rang : toutes sont nommées.
    # Les 12 sources mondiales déclarent le leur — déclarer est la relecture.
    assert len(rapport["tiers_defaulted"]) == 9, "Un repli est passé sous silence"
    assert rapport["by_tier"]["TIER_A_PRIMARY_OFFICIAL"] == 6
    assert set(rapport["tiers_defaulted"]) <= set(rapport["never_verified"])


def test_un_rang_declare_n_est_pas_signale_comme_replie(tmp_path):
    """Déclarer le rang est la relecture ; il ne doit plus apparaître comme replié."""
    chemin = _registre(tmp_path, """
  - name: "Source relue"
    base_url: https://exemple.sn
    category: government
    tier: TIER_A_PRIMARY_OFFICIAL
    last_verified: "2026-08-13"
""")
    entree = load_registry(chemin)["sources"][0]

    assert entree["tier"] is SourceTier.A_PRIMARY_OFFICIAL
    assert entree["tier_defaulted"] is False
    assert registry_report(chemin)["never_verified"] == []


def test_un_rang_inexistant_refuse_l_entree_au_lieu_de_retomber(tmp_path):
    """
    Une faute de frappe dans `tier` donnerait une source dont personne ne connaît
    le régime — et c'est le genre d'entrée qui finit par être crue.
    """
    chemin = _registre(tmp_path, """
  - name: "Source mal déclarée"
    base_url: https://exemple.sn
    category: government
    tier: TIER_A_OFFICIEL
""")
    with pytest.raises(SourceRefused) as echec:
        load_registry(chemin)

    assert "TIER_A_OFFICIEL" in str(echec.value)


def test_une_source_de_decouverte_activee_reste_non_collectable(tmp_path):
    """
    `TIER_D` est une piste, jamais une preuve : il peut faire chercher un
    document ailleurs, il n'est pas collecté lui-même — même activé.
    """
    chemin = _registre(tmp_path, """
  - name: "Blog spécialisé"
    base_url: https://blog.exemple.sn
    category: opinion
    tier: TIER_D_DISCOVERY_ONLY
    enabled: true
""")
    assert load_registry(chemin)["sources"][0]["enabled"] is True
    assert acquirable_sources(chemin) == []


def test_une_source_activee_et_de_rang_acquerable_devient_collectable(tmp_path):
    """La contrepartie : la règle doit pouvoir dire oui, sinon elle ne mesure rien."""
    chemin = _registre(tmp_path, """
  - name: "Agence activée"
    base_url: https://agence.gouv.sn
    category: government
    tier: TIER_A_PRIMARY_OFFICIAL
    enabled: true
""")
    collectables = acquirable_sources(chemin)

    assert [entree["name"] for entree in collectables] == ["Agence activée"]


def test_rien_n_est_devine_dans_la_politique_d_acces(tmp_path):
    """
    Un `robots.txt` non mesuré vaut `unknown`, pas « absent ». Seul le débit
    reçoit un défaut, et il est bas : se tromper vers la lenteur est réparable.
    """
    chemin = _registre(tmp_path, """
  - name: "Agence sans politique déclarée"
    base_url: https://agence.gouv.sn
    scope: country:sn
    category: government
""")
    entree = load_registry(chemin)["sources"][0]

    assert entree["access_policy"]["robots_txt"] == "unknown"
    assert entree["access_policy"]["sitemap"] == "unknown"
    assert entree["access_policy"]["terms_reviewed"] == "unknown"
    assert entree["access_policy"]["rate_limit_rps"] == 0.2
    assert entree["last_verified"] == "unknown"
    assert entree["allowed_content_types"] == [], "Un type non déclaré serait permis"
    # Le pays n'est pas une supposition : c'est la portée écrite dans l'autre sens.
    assert entree["country"] == "SN"


def test_les_champs_d_acquisition_n_ont_pas_change_le_portillon_d_autorite():
    """
    Le rang s'ajoute à la catégorie, il ne la remplace pas : la règle « une
    autorité ne se déclare pas soi-même » doit se comporter exactement comme avant.
    """
    assert check_source("https://www.ansd.sn/x", SourceCategory.GOVERNMENT)["allowed"] is True
    assert check_source("https://blog-inconnu.sn/x", SourceCategory.GOVERNMENT)["allowed"] is False


def test_un_document_sans_url_n_est_pas_bloque_par_le_registre(base, document):
    """
    Sa provenance est le manifeste. Refuser tout fichier local reviendrait à
    interdire l'ingestion de ce que le projet détient déjà.
    """
    rapport = DocumentIngestor(base).ingest_file(
        document, title="Note interne", source_category=SourceCategory.INSTITUTIONAL,
    )

    assert rapport.errors == []
    assert rapport.knowledge_ids


def test_l_ingestion_refuse_une_url_de_la_liste_de_refus(base, document):
    """Le registre est branché sur le chemin réel, pas seulement disponible."""
    with pytest.raises(SourceRefused):
        DocumentIngestor(base).ingest_file(
            document, title="Vidéo", source_category=SourceCategory.OPINION,
            url="https://www.youtube.com/watch?v=abc",
        )


def test_l_ingestion_refuse_une_autorite_usurpee(base, document):
    """Déclarer un blog comme officiel devient impossible, pas seulement malhonnête."""
    with pytest.raises(SourceRefused):
        DocumentIngestor(base).ingest_file(
            document, title="Faux officiel", source_category=SourceCategory.OFFICIAL,
            url="https://blog-anonyme.example/loi-fonciere",
        )


def test_les_sources_declarees_portent_leur_portee_et_leurs_sujets():
    """Le registre sert aussi à savoir qui fait autorité **sur quoi**."""
    sources = {source["name"]: source for source in known_sources()}
    isra = next(source for nom, source in sources.items() if "ISRA" in nom)

    assert isra["scope"] == PORTEE_LOCALE
    assert "agriculture" in isra["subjects"]


# ----------------------------------------------------------------------
# Chapitre 04 — la récupération par portée
# ----------------------------------------------------------------------

MONDIAL = {"id": "k-global", "scope": "global", "content": "Le droit foncier distingue propriété et usage."}
LOCAL = {"id": "k-sn", "scope": "country:sn", "content": "Le domaine national relève d'une loi propre."}
AGRO_MONDIAL = {"id": "k-agro", "scope": "global", "content": "Le mil résiste à la sécheresse."}


def test_la_portee_se_detecte_sur_les_marqueurs_et_le_dit():
    """`keywords` n'est pas une compréhension, et la méthode voyage avec la valeur."""
    locale = detect_scope("Quels sont les prix à Kaolack ?")
    mondiale = detect_scope("Comment fonctionne l'irrigation goutte à goutte ?")

    assert locale["scope"] == PORTEE_LOCALE and locale["method"] == "keywords"
    assert mondiale["scope"] == "global"


def test_un_sujet_national_sans_source_locale_interdit_la_reponse():
    """
    L'unique interdiction du module, et elle ne dépend pas du nombre trouvé :
    cent passages mondiaux ne font pas une source nationale, ils font cent
    façons de se tromper de pays.
    """
    politique = apply_scope_policy(
        [MONDIAL] * 100, question="Comment immatriculer un terrain à Dakar ?",
        subject=KnowledgeSubject.LAW,
    )

    assert politique["allowed"] is False
    assert politique["status"] == "no_national_source"
    assert politique["items"] == []
    assert politique["what_would_settle_it"]


def test_le_local_passe_devant_sans_effacer_le_mondial():
    """Pour tout ce qui n'est pas national, le local enrichit, il ne remplace pas."""
    politique = apply_scope_policy(
        [AGRO_MONDIAL, LOCAL], question="Quel mil semer à Kaolack ?",
        subject=KnowledgeSubject.AGRICULTURE,
    )

    assert politique["allowed"] is True
    assert [item["id"] for item in politique["items"]] == ["k-sn", "k-agro"]
    assert politique["scope_report"]["answered_with"] == {"local": 1, "global": 1}


def test_une_question_mondiale_n_est_pas_bridee():
    """L'agronomie voyage : rien n'oblige une source locale pour une question générale."""
    politique = apply_scope_policy(
        [AGRO_MONDIAL], question="Comment fonctionne l'irrigation goutte à goutte ?",
        subject=KnowledgeSubject.AGRICULTURE,
    )

    assert politique["status"] == "global"
    assert politique["items"] == [AGRO_MONDIAL]


def test_le_moteur_passe_par_le_recuperateur_existant(base, monkeypatch):
    """
    Pas de second chemin de récupération : `retrieve_reliable()` reste celui qui
    cherche, la portée arbitre après.
    """
    appels = []
    original = base.retrieve_reliable

    def espion(prompt, **kwargs):
        appels.append(prompt)
        return original(prompt, **kwargs)

    monkeypatch.setattr(base, "retrieve_reliable", espion)
    resultat = retrieve_scoped(base, "Quel mil semer à Kaolack ?",
                               subject=KnowledgeSubject.AGRICULTURE)

    assert appels == ["Quel mil semer à Kaolack ?"]
    assert "scope_report" in resultat
    # Les champs du récupérateur survivent : la portée s'ajoute, elle ne remplace pas.
    assert "citation_coverage" in resultat and "reliable" in resultat


def test_un_refus_ne_rend_pas_de_citations():
    """
    Une réponse vide accompagnée de sources serait la pire des deux lectures :
    elle aurait l'air sourcée.
    """
    class BaseFictive:
        """Récupérateur qui rend un passage mondial et ses citations."""

        def retrieve_reliable(self, prompt, **kwargs):
            """Rend toujours le même passage mondial."""
            return {"items": [MONDIAL], "reliable": True, "sources": [{"title": "x"}],
                    "citation_coverage": {"coverage": 1.0}, "reason": "trouvé",
                    "best_priority": "P1", "best_confidence": 0.9}

    resultat = retrieve_scoped(BaseFictive(), "Quelle loi à Dakar ?",
                               subject=KnowledgeSubject.LAW)

    assert resultat["allowed"] is False
    assert resultat["sources"] == []
    assert resultat["what_would_settle_it"]


# ----------------------------------------------------------------------
# Chapitre 05 — la réponse dit sa portée
# ----------------------------------------------------------------------

def test_la_reponse_dit_avec_quelles_sources_elle_est_construite():
    """
    L'équivalent, pour la portée, de ce que l'ADR-015 impose à la méthode de
    récupération.
    """
    politique = apply_scope_policy([AGRO_MONDIAL, LOCAL], question="Quel mil à Kaolack ?",
                                   subject=KnowledgeSubject.AGRICULTURE)

    phrase = scope_notice(politique["scope_report"])

    assert PORTEE_LOCALE in phrase and "mondiale" in phrase


def test_une_reponse_locale_sans_source_locale_le_dit():
    """
    Le cas qui compte : sans cette phrase, la réponse se lit exactement comme
    une réponse bien sourcée.
    """
    politique = apply_scope_policy([AGRO_MONDIAL], question="Quel mil à Kaolack ?",
                                   subject=KnowledgeSubject.AGRICULTURE)

    phrase = scope_notice(politique["scope_report"])

    assert "aucune source de cette portée" in phrase.lower()


def test_l_outil_rag_publie_la_portee_de_ce_qu_il_rend(base):
    """Le chemin conçu pour verser du texte dans une invite porte aussi sa portée."""
    from src.tools.rag.tool import RAGTool

    outil = RAGTool()
    outil._knowledge_manager = base
    resultat = outil.execute("retrieve_for_prompt", "Quel mil à Kaolack ?",
                             require_reliable=True)

    assert "scope_report" in resultat
    assert "scope_notice" in resultat
    assert resultat["scope_report"]["question_scope"] == PORTEE_LOCALE
