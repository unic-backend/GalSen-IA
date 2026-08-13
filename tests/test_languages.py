"""
Les langues du Sénégal, et l'écart entre étiqueter et comprendre
(VOLET 36, ch. B).

Avant ce chapitre, un document wolof ne pouvait entrer dans la base qu'étiqueté
dans une langue qui n'est pas la sienne : `Language` s'arrêtait au français, à
l'anglais et à huit langues africaines qui ne sont pas celles du Sénégal.

Le risque de la correction est plus grand que le défaut qu'elle répare : trois
lignes dans une énumération, et la plateforme pourrait annoncer « quatre langues
supportées ». Ces tests épinglent les deux faces — ce qui devient réellement
possible (L1), et ce que le rapport de capacités refuse de laisser croire (L2).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.ingestion import DocumentIngestor  # noqa: E402
from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl  # noqa: E402
from src.knowledge_engine.languages import (  # noqa: E402
    SENEGAL_LANGUAGES,
    Capability,
    LanguageRefused,
    Support,
    known_languages,
    language_support,
    languages_report,
    parse_language,
)
from src.knowledge_engine.types import Language, SourceCategory  # noqa: E402

# Un texte wolof, assez long pour produire au moins un bloc.
TEXTE_WOLOF = (
    "Gëstu bi ci mbay mi dafa am solo ci réew mi. "
    "Ndox mi ak suuf si ñoo tax mbay mi di dox. "
) * 12


@pytest.fixture
def base(tmp_path, monkeypatch):
    """Base de connaissances isolée, en mémoire."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    return KnowledgeManagerImpl()


@pytest.fixture
def document_wolof(tmp_path):
    """Un document rédigé en wolof."""
    chemin = tmp_path / "mbay-mi.md"
    chemin.write_text(TEXTE_WOLOF, encoding="utf-8")
    return str(chemin)


# ----------------------------------------------------------------------
# L1 — les trois langues existent, et servent réellement
# ----------------------------------------------------------------------

def test_les_trois_langues_nationales_sont_declarables():
    """Le fait qui justifie le chapitre : elles n'existaient pas."""
    codes = known_languages()

    assert "wo" in codes, "Le wolof n'est pas déclarable"
    assert "ff" in codes, "Le pulaar n'est pas déclarable"
    assert "srr" in codes, "Le sérère n'est pas déclarable"


def test_un_document_wolof_est_ingere_stocke_et_retrouve_comme_wolof(base, document_wolof):
    """
    La vérification de L1, de bout en bout.

    Étiqueter ne sert à rien si le filtre ne suit pas : le test ingère, puis
    **relit par la langue**, ce qui est ce qu'un usage réel fera.
    """
    rapport = DocumentIngestor(base).ingest_file(
        document_wolof,
        title="Mbay mi ci Senegaal",
        source_category=SourceCategory.INSTITUTIONAL,
        scope="country:sn",
        subject="agriculture",
        language="wo",
    )

    assert rapport.errors == []
    item = base.get_knowledge(rapport.knowledge_ids[0])
    assert item.language is Language.WO

    trouves = base.get_store().list_items(limit=100, language="wo")
    assert rapport.knowledge_ids[0] in {trouve.id for trouve in trouves}


def test_une_langue_inconnue_refuse_le_document(base, document_wolof):
    """
    Rien n'est deviné.

    « wolof » retombant sur le français rendrait le document introuvable par la
    langue sur laquelle on le cherchera — et le silence rendrait la faute
    invisible jusqu'à ce que quelqu'un cherche.
    """
    with pytest.raises(LanguageRefused):
        DocumentIngestor(base).ingest_file(
            document_wolof, title="Mbay mi", source_category=SourceCategory.INSTITUTIONAL,
            language="wolof",
        )


def test_parse_language_accepte_les_formes_ecrites_a_la_main():
    """Un manifeste est écrit par un humain, pas par la machine."""
    assert parse_language("WO ") is Language.WO
    assert parse_language(Language.FF) is Language.FF
    assert parse_language(None) is Language.FR, "Une langue absente doit rester le défaut"


# ----------------------------------------------------------------------
# L2 — le rapport honnête : ce qui est réel, et ce qui n'a jamais été mesuré
# ----------------------------------------------------------------------

def test_etiqueter_le_wolof_ne_dit_pas_que_la_plateforme_le_comprend():
    """
    Le contrepoids de L1, et la raison d'être de ce module.

    Trois lignes dans une énumération ne créent ni détection, ni traduction, ni
    génération. Le rapport le dit capacité par capacité.
    """
    rapport = language_support(Language.WO)
    capacites = rapport["capabilities"]

    assert capacites[Capability.CLASSIFICATION.value]["support"] == Support.YES.value
    assert capacites[Capability.LEXICAL_RETRIEVAL.value]["support"] == Support.YES.value
    assert capacites[Capability.DETECTION.value]["support"] == Support.NO.value
    assert capacites[Capability.TRANSLATION.value]["support"] == Support.NO.value


def test_ce_qui_n_a_jamais_ete_mesure_se_dit_unknown_et_non_no():
    """
    `unknown` nomme ce qui reste à mesurer ; `no` refermerait la question.

    La génération et le récupérateur sémantique attendent C1 — le modèle local
    n'est pas joignable dans cet environnement, et prétendre le contraire dans
    un sens ou dans l'autre serait une mesure inventée.
    """
    capacites = language_support(Language.WO)["capabilities"]

    generation = capacites[Capability.GENERATION.value]
    assert generation["support"] == Support.UNKNOWN.value
    assert "C1" in generation["blocked_on"], "Le rapport ne dit pas ce qui bloque la mesure"

    assert capacites[Capability.SEMANTIC_RETRIEVAL.value]["support"] == Support.UNKNOWN.value


def test_la_regle_du_pluriel_francais_ne_s_applique_plus_au_wolof():
    """
    L3 livré : la règle `-s` est française, et elle reste française.

    Le test a suivi la mesure. Il exigeait auparavant que le rapport nomme la
    phase à venir (`blocked_on: L3`) ; cette phase est faite, et ce qui est
    épinglé maintenant est le comportement réel — un mot wolof n'est plus amputé.
    """
    from src.text_normalization import tokenize

    assert tokenize("ndaws", language="wo") == ["ndaws"]
    assert tokenize("arachides", language="fr") == ["arachide"]

    wolof = language_support(Language.WO)["capabilities"][Capability.NORMALIZATION.value]
    francais = language_support(Language.FR)["capabilities"][Capability.NORMALIZATION.value]

    assert "plural_s" not in wolof["evidence"]
    assert "plural_s" in francais["evidence"]
    # Le pliage des accents reste, et il fond « ñ » et « n » : la capacité est
    # partielle, et le rapport dit pourquoi au lieu de s'annoncer complète.
    assert wolof["support"] == Support.PARTIAL.value
    assert francais["support"] == Support.YES.value


def test_la_capacite_d_evaluation_suit_le_vrai_jeu_de_test(tmp_path):
    """
    La seule capacité mesurée sur un fichier réel.

    Un jeu de test existe ou n'existe pas ; le dépôt sait le dire, donc il le
    dit — au lieu d'un verdict figé qui resterait vrai le jour où le fichier
    change.
    """
    jeu = tmp_path / "retrieval.jsonl"
    jeu.write_text(
        '{"query": "mbay mi", "expected_ids": ["k1"], "language": "wo"}\n',
        encoding="utf-8",
    )

    avec = language_support(Language.WO, evaluation_set=str(jeu))
    sans = language_support(Language.FR, evaluation_set=str(jeu))

    assert avec["capabilities"][Capability.EVALUATION.value]["support"] == Support.PARTIAL.value
    assert sans["capabilities"][Capability.EVALUATION.value]["support"] == Support.NO.value
    assert "jeu de test" in sans["capabilities"][Capability.EVALUATION.value]["blocked_on"]


def test_le_rapport_couvre_les_quatre_langues_du_senegal_et_porte_son_avertissement():
    """
    Un tableau de `yes` se lit vite ; l'avertissement doit voyager avec lui.
    """
    rapport = languages_report()

    assert set(rapport["support"]) == {langue.value for langue in SENEGAL_LANGUAGES}
    assert len(rapport["capabilities"]) == len(Capability)
    assert "comprend le wolof" in rapport["caveat"]
    # Les capacités non acquises se lisent sans parcourir le détail.
    assert rapport["support"]["wo"]["unknown"], "Aucune capacité n'est marquée non mesurée"


# ----------------------------------------------------------------------
# L3 — la normalisation par langue, sans perdre la symétrie
# ----------------------------------------------------------------------

def test_un_document_wolof_reste_trouvable_par_une_requete_sans_langue(base):
    """
    Le risque réel de L3, vérifié plutôt que supposé.

    Un texte wolof n'est plus amputé à l'indexation, mais **une requête n'a pas
    de langue déclarée** — aucun détecteur n'existe. Sans expansion de requête,
    « arachides » ne retrouverait plus un document indexé sous « arachides » ;
    avec elle, les deux formes sont interrogées et rien ne se perd.
    """
    from src.knowledge_engine.types import KnowledgeItem

    wolof = base.add_knowledge(KnowledgeItem(
        content="Gerte gi ak arachides yi ci Kaolack.", language=Language.WO,
    ))
    francais = base.add_knowledge(KnowledgeItem(
        content="La récolte des arachides à Kaolack.", language=Language.FR,
    ))

    trouves = {item.id for item, _ in base.search_knowledge_with_scores("arachides", limit=10)}

    assert wolof in trouves, "Le document wolof est devenu introuvable"
    assert francais in trouves
    # Et la forme stockée reste celle qui a été écrite.
    assert base.get_knowledge(wolof).content.endswith("Kaolack.")


def test_l_index_conserve_le_terme_wolof_tel_qu_il_est_ecrit(base):
    """`ndaws` reste `ndaws` : l'amputer produirait une forme que personne n'a écrite."""
    from src.knowledge_engine.knowledge_indexer import InMemoryKnowledgeIndexer
    from src.knowledge_engine.types import KnowledgeItem

    indexeur = InMemoryKnowledgeIndexer(base.get_store())
    wolof = KnowledgeItem(content="Ndaws yi ak gerte gi.", language=Language.WO, id="k-wo")
    francais = KnowledgeItem(content="Les arachides du Sénégal.", language=Language.FR, id="k-fr")

    assert "ndaws" in indexeur._tokenize(wolof.content, "wo")
    assert "arachide" in indexeur._tokenize(francais.content, "fr")
