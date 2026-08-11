"""
Normalisation des mots avant indexation et recherche (P1 du backlog).

Mesuré avant correction, sur une base contenant « La pluviométrie du Sénégal
varie selon les régions » et « Les arachides se récoltent en octobre » :

```
pluviométrie → 1    pluviometrie → 0
Sénégal      → 1    senegal      → 0
arachides    → 1    arachide     → 0
```

La frappe sans accents est la norme sur un clavier utilisé au Sénégal : une
plateforme qui ne trouve rien sans accents ne trouve rien pour ses utilisateurs.
"""

import pytest

from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeDomain, KnowledgeItem
from src.memory_engine.memory_manager import MemoryManager
from src.memory_engine.types import MemoryItem, MemoryType
from src.text_normalization import normalize_token, singularize, strip_accents, tokenize


# ----------------------------------------------------------------------
# La normalisation elle-même
# ----------------------------------------------------------------------

def test_les_accents_disparaissent_sans_toucher_au_reste():
    assert strip_accents("pluviométrie") == "pluviometrie"
    assert strip_accents("Sénégal") == "Senegal"
    assert strip_accents("mil") == "mil"


def test_le_pluriel_simple_est_retire():
    assert singularize("arachides") == "arachide"
    assert singularize("régions") == "région"
    assert singularize("choix") == "choi"


def test_un_mot_court_garde_son_s():
    """« pas », « bus » ou « gaz » ne doivent pas devenir « pa », « bu », « ga ».

    Sur un mot court, le `s` final appartient bien plus souvent au mot qu'à son
    pluriel.
    """
    assert singularize("pas") == "pas"
    assert singularize("bus") == "bus"
    assert singularize("mois") == "mois"


def test_la_normalisation_ramene_singulier_et_pluriel_sur_la_meme_forme():
    """C'est la propriété qui fait tout marcher, dans les deux sens."""
    assert normalize_token("Arachides") == normalize_token("arachide")
    assert normalize_token("RÉGIONS") == normalize_token("region")


def test_aucun_mot_n_est_allonge():
    """Une normalisation qui allongerait un mot pourrait le sortir de l'index."""
    for mot in ("mil", "arachide", "pluviometrie", "senegal"):
        assert len(normalize_token(mot)) <= len(mot)


def test_les_mots_vides_sont_normalises_eux_aussi():
    """Sans cela, « où » resterait indexé alors que « ou » est écarté."""
    assert tokenize("où mil", stop_words={"ou"}) == ["mil"]
    # Et dans l'autre sens : un mot vide accentué écarte sa forme sans accents.
    assert tokenize("ou mil", stop_words={"où"}) == ["mil"]


def test_les_mots_d_une_lettre_sont_ecartes():
    assert tokenize("a b mil") == ["mil"]


# ----------------------------------------------------------------------
# L'effet sur la recherche de connaissances
# ----------------------------------------------------------------------

@pytest.fixture
def base():
    """Deux connaissances agricoles, accentuées."""
    manager = KnowledgeManagerImpl()
    manager.add_knowledge(KnowledgeItem(
        content="La pluviométrie du Sénégal varie selon les régions.",
        domain=KnowledgeDomain.OPERATIONAL))
    manager.add_knowledge(KnowledgeItem(
        content="Les arachides se récoltent en octobre.",
        domain=KnowledgeDomain.OPERATIONAL))
    return manager


@pytest.mark.parametrize("requete", ["pluviométrie", "pluviometrie", "Sénégal", "senegal",
                                     "régions", "region"])
def test_une_requete_sans_accents_trouve_ce_qui_est_accentue(base, requete):
    assert len(base.search_knowledge(requete)) == 1


@pytest.mark.parametrize("requete", ["arachides", "arachide"])
def test_le_singulier_trouve_le_pluriel(base, requete):
    resultats = base.search_knowledge(requete)
    assert len(resultats) == 1
    assert "arachides" in resultats[0].content


def test_une_requete_sans_rapport_ne_trouve_rien(base):
    """Le contre-test : tout normaliser ne doit pas tout rapprocher."""
    assert base.search_knowledge("automobile") == []


# ----------------------------------------------------------------------
# L'effet sur la recherche de mémoires
# ----------------------------------------------------------------------

@pytest.fixture
def memoire():
    """Deux mémoires du même sujet."""
    manager = MemoryManager()
    for contenu in ("La pluviométrie du Sénégal.", "Les arachides en octobre."):
        manager.save_memory(MemoryItem(content=contenu, memory_type=MemoryType.KNOWLEDGE,
                                       user_id="awa"))
    return manager


def test_une_memoire_sans_rapport_n_est_plus_rendue(memoire):
    """
    Le défaut mesuré : `search_memory("xyzzy")` rendait **toutes** les mémoires
    du sujet, notées 0. Le seuil par défaut valait `0.0` et le test était `>=`,
    si bien qu'un score nul — aucun terme en commun — passait. Le contexte d'un
    agent se remplissait de mémoires sans rapport, présentées comme pertinentes.
    """
    assert memoire.search_memory(query="xyzzy", user_id="awa") == []


def test_la_memoire_pertinente_est_toujours_rendue(memoire):
    """Le contre-test : filtrer ne doit pas rendre la recherche muette."""
    resultats = memoire.search_memory(query="arachide", user_id="awa")

    assert len(resultats) == 1
    assert "arachides" in resultats[0][0].content


def test_la_memoire_se_trouve_aussi_sans_accents(memoire):
    resultats = memoire.search_memory(query="pluviometrie senegal", user_id="awa")

    assert len(resultats) == 1


def test_une_memoire_non_textuelle_n_est_pas_un_resultat_de_recherche(memoire):
    """
    On ne peut pas rapprocher un dictionnaire d'une requête. Le rendre quand
    même en ferait un résultat que rien ne justifie ; `list_items()` reste la
    façon de tout obtenir.
    """
    memoire.save_memory(MemoryItem(content={"plan": "quelconque"},
                                   memory_type=MemoryType.AGENT_SHARED, user_id="awa"))

    resultats = memoire.search_memory(query="plan", user_id="awa")

    assert all(isinstance(item.content, str) for item, _ in resultats)
