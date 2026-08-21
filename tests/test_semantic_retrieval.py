"""
Récupération sémantique (VOLET 27 — ADR-015).

Toute la récupération de la plateforme était lexicale : Jaccard sur des jetons.
« Comment soigner le mil malade ? » et « traitement des maladies du sorgho »
n'ont presque aucun jeton commun et sont la même question — la première rendait
un score **nul** sur la seconde.

L'encodeur utilisé ici est déterministe et écrit dans ce fichier. Ce n'est pas un
substitut au modèle sous test : **le modèle n'est pas le sujet**. Ce qui est
vérifié, c'est le magasin, le cosinus, la détection de mélange d'espaces, le
repli lexical et le fait que la méthode employée soit **rapportée**. Le vrai
encodeur — `sentence-transformers` — ne peut pas être exercé ici : `huggingface.co`
répond 403 à travers le mandataire de cet environnement, donc ses poids sont
inatteignables. Ce qui est testé de lui, c'est qu'il **le dit** au lieu de rendre
un vecteur.
"""

import math
import os
import sys
from typing import List, Sequence

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.embeddings.interfaces import (  # noqa: E402
    EmbeddingProvider,
    EmbeddingProviderInfo,
    EmbeddingUnavailable,
)
from src.embeddings.registry import (  # noqa: E402
    ENABLED_VARIABLE,
    active_embedder,
    embedding_status,
    reset_embedder,
    set_embedder,
)
from src.embeddings.semantic_index import (  # noqa: E402
    METHOD_LEXICAL,
    METHOD_SEMANTIC,
    SemanticIndex,
    rank_or_fallback,
)
from src.embeddings.sentence_transformers_provider import (  # noqa: E402
    SentenceTransformersEmbedder,
)
from src.embeddings.vector_store import (  # noqa: E402
    DimensionMismatch,
    SQLiteVectorStore,
    Vector,
)

# Concepts portés par des mots différents : c'est exactement ce que le lexical
# ne peut pas rapprocher.
CONCEPTS = {
    "cereale_malade": ("mil", "sorgho", "cereale", "maladie", "soigner", "traitement"),
    "peche": ("poisson", "pirogue", "peche", "filet", "ocean"),
}


class EncodeurDeTest(EmbeddingProvider):
    """
    Encodeur déterministe : un axe par concept, valeur = mots du concept présents.

    Il n'imite pas un réseau de neurones et ne prétend pas le faire. Il produit
    des vecteurs **réels et normalisés** dans un espace connu, ce qui suffit à
    exercer le magasin, le classement et le repli.
    """

    def __init__(self, model_name: str = "encodeur-de-test"):
        self._model_name = model_name
        self._axes = sorted(CONCEPTS)

    @property
    def provider_id(self) -> str:
        return "test"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return len(self._axes)

    def check_availability(self) -> EmbeddingProviderInfo:
        return EmbeddingProviderInfo(
            provider_id=self.provider_id,
            model_name=self._model_name,
            dimension=self.dimension,
            available=True,
        )

    def embed(self, textes: Sequence[str]) -> List[List[float]]:
        vecteurs = []
        for texte in textes:
            minuscule = texte.lower()
            brut = [
                float(sum(1 for mot in CONCEPTS[axe] if mot in minuscule))
                for axe in self._axes
            ]
            norme = math.sqrt(sum(valeur * valeur for valeur in brut)) or 1.0
            vecteurs.append([valeur / norme for valeur in brut])
        return vecteurs


@pytest.fixture
def magasin(tmp_path):
    """Magasin de vecteurs isolé."""
    return SQLiteVectorStore(str(tmp_path / "vectors.sqlite"))


@pytest.fixture
def encodeur():
    """Encodeur déterministe, installé puis retiré du registre."""
    fournisseur = EncodeurDeTest()
    set_embedder(fournisseur)
    yield fournisseur
    reset_embedder()


# ----------------------------------------------------------------------
# Le magasin de vecteurs
# ----------------------------------------------------------------------

def test_un_vecteur_ecrit_se_retrouve(magasin, encodeur):
    """Le tour complet : écrire, chercher, retrouver."""
    vecteurs = encodeur.embed(["Le mil est malade", "La pirogue est au port"])
    magasin.upsert([
        Vector("m1", "memory", vecteurs[0], encodeur.model_name),
        Vector("m2", "memory", vecteurs[1], encodeur.model_name),
    ])

    requete = encodeur.embed(["maladie des cereales"])[0]
    resultats = magasin.search("memory", requete, encodeur.model_name, limit=2)

    assert resultats[0].item_id == "m1"
    assert resultats[0].score > resultats[1].score


def test_deux_espaces_vectoriels_ne_se_melangent_pas(magasin):
    """
    Un cosinus entre deux modèles est un nombre bien calculé qui ne veut rien dire.

    Le magasin doit refuser le mélange, pas le classer.
    """
    magasin.upsert([Vector("a", "memory", [1.0, 0.0], "modele-x")])

    with pytest.raises(DimensionMismatch, match="dimension"):
        magasin.upsert([Vector("b", "memory", [1.0, 0.0, 0.0], "modele-x")])


def test_les_modeles_differents_sont_cloisonnes(magasin):
    """Chercher avec un modèle ne doit pas rendre les vecteurs d'un autre."""
    magasin.upsert([
        Vector("a", "memory", [1.0, 0.0], "modele-x"),
        Vector("b", "memory", [1.0, 0.0], "modele-y"),
    ])

    resultats = magasin.search("memory", [1.0, 0.0], "modele-x", limit=10)

    assert [r.item_id for r in resultats] == ["a"]


def test_le_magasin_persiste(tmp_path, encodeur):
    """Les vecteurs survivent au redémarrage : sinon tout serait réencodé."""
    chemin = str(tmp_path / "vectors.sqlite")
    valeurs = encodeur.embed(["Le mil est malade"])[0]
    SQLiteVectorStore(chemin).upsert([Vector("m1", "memory", valeurs, encodeur.model_name)])

    assert SQLiteVectorStore(chemin).count("memory") == 1


def test_un_vecteur_vide_est_refuse(magasin):
    """Un vecteur sans dimension n'est pas un vecteur."""
    with pytest.raises(ValueError):
        magasin.upsert([Vector("a", "memory", [], "modele-x")])


# ----------------------------------------------------------------------
# Le classement sémantique
# ----------------------------------------------------------------------

def test_le_sens_rapproche_ce_que_les_mots_separent(magasin, encodeur):
    """
    Le fait qui justifie tout le VOLET.

    « maladie du sorgho » et « soigner le mil » ne partagent aucun jeton : le
    classement lexical rend zéro. Le classement sémantique les rapproche.
    """
    elements = [
        ("m1", "Comment soigner le mil"),
        ("m2", "La pirogue rentre avec le poisson"),
    ]
    index = SemanticIndex(encodeur, magasin, "memory")

    classement = index.rank("traitement des maladies du sorgho", elements, limit=2)

    assert classement[0].item_id == "m1", "Le sens n'a pas rapproché les deux céréales"
    assert classement[0].score > classement[1].score


def test_l_indexation_est_paresseuse_et_ne_se_refait_pas(magasin, encodeur):
    """Un élément est encodé au premier passage, puis retrouvé, jamais réencodé."""
    elements = [("m1", "Le mil est malade")]
    index = SemanticIndex(encodeur, magasin, "memory")

    index.rank("maladie", elements)
    assert magasin.count("memory") == 1

    index.rank("maladie", elements)
    assert magasin.count("memory") == 1, "L'élément a été réencodé"


def test_le_classement_se_limite_aux_candidats(magasin, encodeur):
    """Le magasin peut contenir d'autres sujets : ils ne doivent pas remonter."""
    index = SemanticIndex(encodeur, magasin, "memory")
    index.index([("autre", "Le mil est malade")])

    classement = index.rank("maladie du mil", [("m1", "Le sorgho est atteint")], limit=5)

    assert [c.item_id for c in classement] == ["m1"]


# ----------------------------------------------------------------------
# Ce qui est rapporté à l'appelant
# ----------------------------------------------------------------------

def test_sans_encodeur_le_repli_est_lexical_et_annonce(magasin, monkeypatch):
    """Un résultat lexical ne doit jamais être présenté comme sémantique."""
    monkeypatch.delenv(ENABLED_VARIABLE, raising=False)
    reset_embedder()

    classement, rapport = rank_or_fallback(
        "maladie", [("m1", "Le mil est malade")],
        repli=lambda: [("m1", 0.5)],
        embedder=None, collection="memory", store=magasin,
    )

    assert classement == [("m1", 0.5)]
    assert rapport["method"] == METHOD_LEXICAL
    assert "encodeur" in rapport["reason"].lower()


def test_avec_encodeur_la_methode_est_semantique(magasin, encodeur):
    """Le contre-test : la méthode annoncée doit suivre le chemin réellement pris."""
    _, rapport = rank_or_fallback(
        "maladie du sorgho", [("m1", "Le mil est malade")],
        repli=lambda: [], embedder=encodeur, collection="memory", store=magasin,
    )

    assert rapport["method"] == METHOD_SEMANTIC
    assert rapport["model"] == encodeur.model_name


def test_un_encodeur_qui_tombe_ne_casse_pas_la_recherche(magasin):
    """Une panne d'encodage doit replier — et le repli doit être annoncé."""

    class EncodeurCasse(EncodeurDeTest):
        def embed(self, textes):
            raise RuntimeError("modèle introuvable")

    classement, rapport = rank_or_fallback(
        "maladie", [("m1", "Le mil est malade")],
        repli=lambda: [("m1", 0.4)],
        embedder=EncodeurCasse(), collection="memory", store=magasin,
    )

    assert classement == [("m1", 0.4)]
    assert rapport["method"] == METHOD_LEXICAL
    assert "modèle introuvable" in rapport["reason"]


# ----------------------------------------------------------------------
# Le registre, et le fournisseur réel
# ----------------------------------------------------------------------

def test_sans_bibliotheque_le_registre_ne_rend_aucun_encodeur(monkeypatch):
    """L'état normal d'une installation sans `sentence-transformers`."""
    monkeypatch.delenv(ENABLED_VARIABLE, raising=False)
    reset_embedder()

    assert active_embedder() is None


def test_le_fournisseur_reel_signale_sa_dependance_manquante():
    """
    Le seul comportement du vrai fournisseur vérifiable ici — et le bon.

    Les poids ne sont pas récupérables dans cet environnement ; ce qui compte
    est qu'il **rapporte** au lieu de rendre un vecteur de complaisance.
    """
    etat = SentenceTransformersEmbedder().check_availability()

    assert etat.available is False
    assert etat.reason is EmbeddingUnavailable.MISSING_DEPENDENCY
    assert "requirements-embeddings.txt" in etat.detail


def test_le_fournisseur_reel_leve_plutot_que_d_inventer():
    """Encoder sans bibliothèque doit échouer bruyamment, jamais rendre un vecteur."""
    with pytest.raises(RuntimeError, match="sentence-transformers"):
        SentenceTransformersEmbedder().embed(["Le mil est malade"])


def test_l_encodage_peut_etre_coupe_explicitement(monkeypatch, encodeur):
    """Un exploitant doit pouvoir rester lexical, et le voir dans l'état."""
    monkeypatch.setenv(ENABLED_VARIABLE, "false")

    assert active_embedder() is None
    assert embedding_status()["available"] is False
    assert embedding_status()["reason"] == "disabled"


# ----------------------------------------------------------------------
# La mémoire, bout en bout
# ----------------------------------------------------------------------

def test_la_memoire_retrouve_par_le_sens(tmp_path, monkeypatch, encodeur):
    """
    Le cas réel : deux mémoires, une requête sans jeton commun avec la bonne.

    `retrieve()` — le chemin lexical — ne la trouve pas. `retrieve_with_method()`
    la trouve **et** dit par quel chemin.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    from src.memory_engine.memory_store import InMemoryMemoryStore
    from src.memory_engine.memory_retriever import InMemoryMemoryRetriever
    from src.memory_engine.types import MemoryItem, MemoryType

    magasin = InMemoryMemoryStore()
    for identifiant, contenu in (
        ("m1", "Comment soigner le mil"),
        ("m2", "La pirogue rentre avec le poisson"),
    ):
        magasin.save(MemoryItem(
            id=identifiant, content=contenu,
            memory_type=MemoryType.LONG_TERM, user_id="u1",
        ))

    retriever = InMemoryMemoryRetriever(magasin)
    requete = "traitement des maladies du sorgho"

    # Le chemin lexical ne trouve rien : aucun jeton commun.
    assert retriever.retrieve(requete, user_id="u1") == []

    resultats, rapport = retriever.retrieve_with_method(requete, user_id="u1", limit=5)

    assert rapport["method"] == METHOD_SEMANTIC
    assert [item.id for item, _ in resultats][:1] == ["m1"]


def test_sans_encodeur_la_memoire_reste_lexicale_et_le_dit(tmp_path, monkeypatch):
    """Le repli doit rendre exactement ce que rendait le chemin d'avant."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv(ENABLED_VARIABLE, raising=False)
    reset_embedder()

    from src.memory_engine.memory_store import InMemoryMemoryStore
    from src.memory_engine.memory_retriever import InMemoryMemoryRetriever
    from src.memory_engine.types import MemoryItem, MemoryType

    magasin = InMemoryMemoryStore()
    magasin.save(MemoryItem(
        id="m1", content="Le mil est malade",
        memory_type=MemoryType.LONG_TERM, user_id="u1",
    ))
    retriever = InMemoryMemoryRetriever(magasin)

    resultats, rapport = retriever.retrieve_with_method("mil malade", user_id="u1")

    assert rapport["method"] == METHOD_LEXICAL
    assert [item.id for item, _ in resultats] == ["m1"]


# ----------------------------------------------------------------------
# Le service de recherche est passé au chemin sémantique (backlog P1)
# ----------------------------------------------------------------------

def test_la_recherche_de_connaissances_dit_sa_methode(tmp_path, monkeypatch):
    """
    `/search` répondait lexicalement **même avec un encodeur installé** : le
    récupérateur de mémoire avait été converti au VOLET 27, le service de
    recherche non. C'est la marche qui manquait.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
    from src.knowledge_engine.types import KnowledgeItem

    manager = KnowledgeManagerImpl()
    manager.add_knowledge(KnowledgeItem(content="Le sorgho souffre de la sécheresse"))

    _resultats, rapport = manager.search_knowledge_with_method("sécheresse", role="admin")

    assert rapport["method"] in ("lexical", "semantic")
    if rapport["method"] == "lexical":
        assert rapport["reason"], "Un repli lexical doit dire pourquoi"


def test_la_recherche_de_connaissances_passe_au_semantique(tmp_path, monkeypatch):
    """
    Avec un encodeur, une question sans terme commun doit retrouver le document.

    C'est exactement ce que le classement lexical ne peut pas faire, et ce que
    la référence mesurée du VOLET 33 (0,40) attend d'améliorer.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    from src.embeddings.registry import reset_embedder, set_embedder
    from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
    from src.knowledge_engine.types import KnowledgeItem

    manager = KnowledgeManagerImpl()
    # Aucun terme commun avec la requête : le classement lexical le note zéro.
    attendu = manager.add_knowledge(KnowledgeItem(content="Le sorgho est atteint"))
    manager.add_knowledge(KnowledgeItem(content="La pirogue rentre avec du poisson"))

    set_embedder(EncodeurDeTest())
    try:
        resultats, rapport = manager.search_knowledge_with_method(
            "soigner une maladie du mil", role="admin",
        )
    finally:
        reset_embedder()

    assert rapport["method"] == "semantic"
    assert resultats, "Le chemin sémantique ne rend rien"
    assert resultats[0][0].id == attendu


# ----------------------------------------------------------------------
# Le cache de matrice : ce qu'il accélère, et ce qu'il ne doit jamais servir
#
# `search()` reconstruisait la matrice à chaque requête — 49,4 ms à 271
# vecteurs et 1 856,8 ms à 10 000, mesuré avant correction. La matrice est
# désormais gardée par (collection, modèle) et validée par un compteur de
# version inscrit dans la base. Ces tests portent sur la validité, pas sur la
# vitesse : un cache rapide qui rend un résultat périmé est pire que la
# lenteur qu'il remplace.
# ----------------------------------------------------------------------


def _vecteur(item_id, valeurs, collection="c", modele="m", metadata=None):
    """Un vecteur normalisé, pour les tests de cache."""
    norme = math.sqrt(sum(v * v for v in valeurs)) or 1.0
    return Vector(item_id=item_id, collection=collection,
                  values=[v / norme for v in valeurs], model_name=modele,
                  metadata=metadata or {})


def test_une_ecriture_invalide_le_cache(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0])])
    assert [r.item_id for r in magasin.search("c", [1.0, 0.0], "m")] == ["a"]

    magasin.upsert([_vecteur("b", [0.9, 0.1])])
    trouves = [r.item_id for r in magasin.search("c", [1.0, 0.0], "m")]
    # Sans invalidation, « b » serait resté invisible jusqu'au redémarrage.
    assert set(trouves) == {"a", "b"}


def test_une_valeur_remplacee_est_bien_relue(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0]), _vecteur("b", [0.0, 1.0])])
    assert magasin.search("c", [1.0, 0.0], "m", limit=1)[0].item_id == "a"

    # Même identifiant, valeur opposée : le nombre de lignes ne change pas.
    # Un cache validé par un simple décompte aurait manqué ce cas.
    magasin.upsert([_vecteur("a", [0.0, -1.0])])

    # On interroge la direction d'origine de « a » : sur une matrice périmée
    # son score vaudrait encore 1,0. C'est le score, et non le classement, qui
    # distingue les deux cas — un test qui ne regarde que l'ordre passerait
    # dans les deux, et ne garderait donc rien.
    scores = {r.item_id: r.score for r in magasin.search("c", [1.0, 0.0], "m")}
    assert scores["a"] < 0.5, (
        f"« a » marque {scores['a']} sur sa valeur remplacée : la matrice "
        "servie est celle d'avant l'écriture."
    )


def test_une_suppression_invalide_le_cache(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0]), _vecteur("b", [0.0, 1.0])])
    magasin.search("c", [1.0, 0.0], "m")

    magasin.delete("c", ["a"])
    assert [r.item_id for r in magasin.search("c", [1.0, 0.0], "m")] == ["b"]


def test_un_vidage_invalide_le_cache(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0])])
    magasin.search("c", [1.0, 0.0], "m")

    magasin.clear("c")
    assert magasin.search("c", [1.0, 0.0], "m") == []


def test_une_ecriture_d_un_autre_processus_invalide_le_cache(tmp_path):
    """Le cas qui justifie un compteur en base plutôt qu'un drapeau en mémoire."""
    chemin = str(tmp_path / "vectors.sqlite")
    lecteur = SQLiteVectorStore(chemin)
    ecrivain = SQLiteVectorStore(chemin)

    ecrivain.upsert([_vecteur("a", [1.0, 0.0])])
    assert [r.item_id for r in lecteur.search("c", [1.0, 0.0], "m")] == ["a"]

    # Une seconde instance écrit — c'est ce que fait un autre processus.
    ecrivain.upsert([_vecteur("b", [0.9, 0.1])])
    trouves = [r.item_id for r in lecteur.search("c", [1.0, 0.0], "m")]
    assert set(trouves) == {"a", "b"}, (
        "Le lecteur a servi une matrice périmée : un cache que seul son "
        "processus sait invalider ment dès qu'un autre écrit."
    )


def test_les_metadonnees_rendues_sont_celles_du_vecteur(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0], metadata={"source": "x"}),
                    _vecteur("b", [0.0, 1.0], metadata={"source": "y"})])
    magasin.search("c", [1.0, 0.0], "m")  # remplit le cache

    resultat = magasin.search("c", [0.0, 1.0], "m", limit=1)[0]
    assert resultat.item_id == "b"
    assert resultat.metadata == {"source": "y"}


def test_le_cache_ne_melange_pas_deux_modeles(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0], modele="m1"),
                    _vecteur("b", [1.0, 0.0], modele="m2")])
    assert [r.item_id for r in magasin.search("c", [1.0, 0.0], "m1")] == ["a"]
    assert [r.item_id for r in magasin.search("c", [1.0, 0.0], "m2")] == ["b"]


def test_le_cache_ne_melange_pas_deux_collections(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0], collection="c1"),
                    _vecteur("b", [1.0, 0.0], collection="c2")])
    assert [r.item_id for r in magasin.search("c1", [1.0, 0.0], "m")] == ["a"]
    assert [r.item_id for r in magasin.search("c2", [1.0, 0.0], "m")] == ["b"]


def test_une_dimension_incompatible_est_toujours_refusee(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0])])
    magasin.search("c", [1.0, 0.0], "m")  # remplit le cache
    with pytest.raises(DimensionMismatch):
        magasin.search("c", [1.0, 0.0, 0.0], "m")


def test_le_cache_est_visible_dans_les_statistiques(magasin):
    magasin.upsert([_vecteur("a", [1.0, 0.0])])
    magasin.search("c", [1.0, 0.0], "m")
    magasin.search("c", [1.0, 0.0], "m")

    cache = magasin.stats()["cache"]
    assert cache["entries"] == 1
    assert cache["bytes"] > 0
    assert cache["hits"]["frais"] >= 1
    # Un cache qu'on ne peut pas voir est un cache dont personne ne sait s'il sert.
    assert cache["max_mb"] > 0


def test_une_collection_au_dela_du_plafond_est_servie_sans_cache(magasin, monkeypatch):
    import src.embeddings.vector_store as module

    magasin.upsert([_vecteur("a", [1.0, 0.0]), _vecteur("b", [0.0, 1.0])])
    monkeypatch.setattr(module, "CACHE_MAX_MO", 0)

    # Le résultat reste juste ; seule la mise en cache est refusée.
    assert [r.item_id for r in magasin.search("c", [1.0, 0.0], "m", limit=1)] == ["a"]
    assert magasin.stats()["cache"]["entries"] == 0
