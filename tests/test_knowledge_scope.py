"""
Les deux axes de la connaissance (VOLET 35, ch. 01).

Le VOLET 35 vise « une IA internationale avec une expertise exceptionnelle sur
le Sénégal ». Tout le reste du VOLET lit l'axe de portée ; ce chapitre le pose,
et ces tests protègent les trois propriétés dont dépendent les onze chapitres
suivants :

1. **Rien n'est deviné.** Une portée ou un sujet malformé refuse l'écriture
   plutôt que de retomber sur une valeur par défaut — une connaissance
   sénégalaise rangée « mondiale » par charité est précisément l'erreur que ce
   VOLET existe pour empêcher.
2. **Le défaut est « mondial, non classé »**, jamais « sénégalais ».
3. **Une base d'avant la migration se relit sans perte.** C'est la propriété qui
   coûte le plus cher si elle manque : ré-étiqueter des passages à la main est
   la migration que personne ne finit jamais.
"""

import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.scope import (  # noqa: E402
    NATIONAL_SUBJECTS,
    SAFETY_CRITICAL_SUBJECTS,
    SEUIL_DE_SUSPICION,
    KnowledgeScope,
    KnowledgeSubject,
    ScopeRefused,
    known_subjects,
    parse_subject,
    requires_national_source,
    scopes_report,
)
from src.knowledge_engine.types import KnowledgeItem  # noqa: E402

#: Le schéma tel qu'il existait **avant** ce chapitre : ni `scope`, ni `subject`.
SCHEMA_AVANT = """
CREATE TABLE knowledge_items (
 id TEXT PRIMARY KEY, content TEXT, summary TEXT, knowledge_type TEXT,
 content_type TEXT, language TEXT, domain TEXT, sensitivity TEXT, status TEXT,
 tags TEXT, categories TEXT, source_id TEXT, source_type TEXT,
 source_location TEXT, source_accessed_at TEXT, source_hash TEXT,
 source_category TEXT, source_title TEXT, source_author TEXT, source_url TEXT,
 source_citation TEXT, source_retrieved_at TEXT, confidence REAL, version INTEGER,
 created_at TEXT, updated_at TEXT, metadata TEXT, relations TEXT, priority INTEGER)
"""

LIGNE_AVANT = """
INSERT INTO knowledge_items (id, content, knowledge_type, content_type, language,
 domain, sensitivity, status, tags, categories, source_id, source_type,
 source_location, source_accessed_at, confidence, version, created_at, updated_at,
 metadata, relations, priority)
VALUES ('kn_ancien','une connaissance écrite avant le VOLET 35','fact','text','fr',
 'technical','public','approved','[]','[]','s1','file','/x','2026-01-01T00:00:00',
 0.5,1,'2026-01-01T00:00:00','2026-01-01T00:00:00','{}','[]',3)
"""


# ----------------------------------------------------------------------
# 1. La portée
# ----------------------------------------------------------------------


def test_la_portee_par_defaut_est_mondiale():
    """Une connaissance sans portée déclarée n'est pas sénégalaise par accident."""
    assert KnowledgeItem(content="essai").scope == "global"


def test_une_portee_nationale_se_lit_et_se_reecrit():
    portee = KnowledgeScope.parse("country:sn")

    assert portee.kind == "country"
    assert portee.country == "SN"
    assert str(portee) == "country:sn"


def test_la_casse_du_code_pays_est_normalisee():
    assert str(KnowledgeScope.parse("COUNTRY:Sn")) == "country:sn"


def test_une_portee_inconnue_est_refusee_et_ne_retombe_pas_sur_mondial():
    """
    Le cœur du chapitre : deviner ferait passer une connaissance locale pour
    universelle, ce qui est l'erreur la plus coûteuse de ce VOLET.
    """
    for mauvaise in ("senegal", "sn", "pays:sn", "", None, "country:senegal"):
        with pytest.raises(ScopeRefused):
            KnowledgeScope.parse(mauvaise)


def test_une_portee_mondiale_qui_nomme_un_pays_est_refusee():
    """Deux vérités sur le même élément : l'une des deux serait fausse."""
    with pytest.raises(ScopeRefused):
        KnowledgeScope(kind="global", country="SN")


def test_une_portee_deja_analysee_se_relit_telle_quelle():
    portee = KnowledgeScope.country_("sn")

    assert KnowledgeScope.parse(portee) is portee


# ----------------------------------------------------------------------
# 2. Le sujet
# ----------------------------------------------------------------------


def test_le_sujet_par_defaut_dit_non_classe():
    assert KnowledgeItem(content="essai").subject is KnowledgeSubject.UNSPECIFIED


def test_un_sujet_inconnu_est_refuse_et_non_silencieusement_ignore():
    """
    Retomber sur `UNSPECIFIED` rendrait la connaissance introuvable par son
    sujet — et introuvable aussi pour celui qui l'a ingérée.
    """
    with pytest.raises(ScopeRefused) as erreur:
        parse_subject("agricultre")

    assert "agriculture" in str(erreur.value), "le message doit lister les sujets déclarés"


def test_un_sujet_vide_vaut_non_classe():
    """Absent et faux sont deux choses différentes : seul le faux est refusé."""
    assert parse_subject(None) is KnowledgeSubject.UNSPECIFIED
    assert parse_subject("") is KnowledgeSubject.UNSPECIFIED


def test_les_sujets_du_brief_existent_tous():
    """Le brief nomme les domaines attendus ; aucun ne doit manquer."""
    declares = set(known_subjects())
    for attendu in (
        "science", "technology", "engineering", "health", "economics", "history",
        "culture", "education", "law", "agriculture", "environment", "business",
    ):
        assert attendu in declares, f"sujet « {attendu} » du brief absent"


def test_les_sujets_specifiques_au_senegal_existent():
    """Pêche, langues nationales, administration, géographie : demandés explicitement."""
    declares = set(known_subjects())
    for attendu in ("fisheries", "languages", "administration", "geography", "society"):
        assert attendu in declares


# ----------------------------------------------------------------------
# 3. Ce qui ne retombe jamais sur le mondial
# ----------------------------------------------------------------------


def test_le_droit_ne_se_transporte_pas_d_un_pays_a_l_autre():
    """
    Répondre le droit français à une question sur le foncier sénégalais serait
    pire que ne pas répondre : fluide, plausible, et faux là où ça coûte cher.
    """
    assert requires_national_source(KnowledgeSubject.LAW) is True
    assert requires_national_source(KnowledgeSubject.ADMINISTRATION) is True
    assert requires_national_source(KnowledgeSubject.LANGUAGES) is True


def test_l_agronomie_se_transporte_et_le_local_enrichit():
    """Le mil pousse selon la même biologie partout ; ce sont les variétés qui changent."""
    assert requires_national_source(KnowledgeSubject.AGRICULTURE) is False
    assert requires_national_source(KnowledgeSubject.SCIENCE) is False


def test_la_liste_nationale_reste_courte():
    """
    Chaque entrée coûte un refus de réponse. L'élargir sans raison transformerait
    l'IA internationale en IA qui ne répond qu'au Sénégal — l'inverse du brief.
    """
    assert len(NATIONAL_SUBJECTS) <= 5
    assert KnowledgeSubject.HEALTH in SAFETY_CRITICAL_SUBJECTS


# ----------------------------------------------------------------------
# 4. Le rapport : voir ce que la base contient vraiment
# ----------------------------------------------------------------------


class _Element:
    """Élément minimal, pour mesurer le rapport sans construire une base."""

    def __init__(self, scope="global", subject=KnowledgeSubject.UNSPECIFIED):
        self.scope = scope
        self.subject = subject


def test_le_rapport_compte_par_portee_et_par_sujet():
    rapport = scopes_report([
        _Element("country:sn", KnowledgeSubject.AGRICULTURE),
        _Element("country:sn", KnowledgeSubject.LAW),
        _Element("global", KnowledgeSubject.SCIENCE),
    ])

    assert rapport["total"] == 3
    assert rapport["by_scope"]["country:sn"] == 2
    assert rapport["countries"] == ["country:sn"]


def test_une_portee_isolee_dans_une_base_fournie_est_signalee():
    """Une faute de frappe crée une portée que rien ne viendra jamais rejoindre."""
    rapport = scopes_report(
        [_Element("global")] * SEUIL_DE_SUSPICION + [_Element("country:xx")]
    )

    assert rapport["suspicious_scopes"] == ["country:xx"]


def test_une_base_jeune_ne_signale_rien():
    """
    Crier au loup dès le premier pays rendrait le signal invisible quand il
    compterait vraiment.
    """
    rapport = scopes_report([_Element("country:sn"), _Element("global")])

    assert rapport["suspicious_scopes"] == []
    assert rapport["suspicion_threshold"] == SEUIL_DE_SUSPICION


# ----------------------------------------------------------------------
# 5. La migration — la propriété la plus chère si elle manque
# ----------------------------------------------------------------------


def test_une_base_ecrite_avant_ce_chapitre_se_relit_sans_perte(tmp_path):
    """
    Une connaissance d'avant la migration devient « mondiale, non classée » —
    jamais sénégalaise, jamais dotée d'un sujet inventé.
    """
    chemin = str(tmp_path / "ancienne.sqlite")
    connexion = sqlite3.connect(chemin)
    connexion.execute(SCHEMA_AVANT)
    connexion.execute(LIGNE_AVANT)
    connexion.commit()
    connexion.close()

    from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore

    ancienne = SQLiteKnowledgeStore(db_path=chemin).get("kn_ancien")

    assert ancienne is not None
    assert ancienne.scope == "global"
    assert ancienne.subject is KnowledgeSubject.UNSPECIFIED
    assert ancienne.content == "une connaissance écrite avant le VOLET 35"


def test_les_deux_axes_survivent_a_un_aller_retour_sur_disque(tmp_path):
    from src.storage.sqlite_knowledge_store import SQLiteKnowledgeStore

    chemin = str(tmp_path / "base.sqlite")
    SQLiteKnowledgeStore(db_path=chemin).save(KnowledgeItem(
        id="kn_mil", content="variétés de mil adaptées au bassin arachidier",
        scope="country:sn", subject=KnowledgeSubject.AGRICULTURE,
    ))

    relu = SQLiteKnowledgeStore(db_path=chemin).get("kn_mil")

    assert relu.scope == "country:sn"
    assert relu.subject is KnowledgeSubject.AGRICULTURE


def test_une_nouvelle_version_garde_les_deux_axes():
    """Réécrire un contenu ne doit pas rapatrier une connaissance locale au mondial."""
    element = KnowledgeItem(
        content="ancien texte", scope="country:sn", subject=KnowledgeSubject.FISHERIES,
    )

    suivant = element.update_content("texte corrigé")

    assert suivant.scope == "country:sn"
    assert suivant.subject is KnowledgeSubject.FISHERIES


# ----------------------------------------------------------------------
# 6. L'ingestion porte les axes, et refuse avant d'écrire
# ----------------------------------------------------------------------


@pytest.fixture
def ingestor(tmp_path, monkeypatch):
    """Un ingesteur sur une base propre."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    from src.knowledge_engine.ingestion import DocumentIngestor
    from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl

    return DocumentIngestor(KnowledgeManagerImpl())


@pytest.fixture
def document(tmp_path):
    """Un document assez long pour produire plusieurs blocs."""
    chemin = tmp_path / "mil.txt"
    chemin.write_text("Le mil est cultivé au Sénégal. " * 80, encoding="utf-8")
    return str(chemin)


def test_l_ingestion_transmet_les_deux_axes_a_chaque_bloc(ingestor, document):
    from src.knowledge_engine.types import SourceCategory

    rapport = ingestor.ingest_file(
        document, title="Guide du mil", source_category=SourceCategory.INSTITUTIONAL,
        scope="country:sn", subject="agriculture",
    )

    assert rapport.knowledge_ids
    for identifiant in rapport.knowledge_ids:
        element = ingestor._knowledge.get_knowledge(identifiant)
        assert element.scope == "country:sn"
        assert element.subject is KnowledgeSubject.AGRICULTURE


def test_une_portee_fautive_refuse_l_ingestion_avant_toute_ecriture(ingestor, document):
    """
    Refuser après coup laisserait cent blocs mal étiquetés à retrouver un par un.
    """
    from src.knowledge_engine.types import SourceCategory

    with pytest.raises(ScopeRefused):
        ingestor.ingest_file(
            document, title="Guide", source_category=SourceCategory.INSTITUTIONAL,
            scope="senegal",
        )

    assert ingestor._knowledge.get_stats()["store"]["total_items"] == 0


def test_l_ingestion_sans_portee_declaree_reste_mondiale(ingestor, document):
    from src.knowledge_engine.types import SourceCategory

    rapport = ingestor.ingest_file(
        document, title="Article", source_category=SourceCategory.PEER_REVIEWED,
    )

    element = ingestor._knowledge.get_knowledge(rapport.knowledge_ids[0])
    assert element.scope == "global"
