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
    check_source,
    denied_reason,
    known_sources,
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
