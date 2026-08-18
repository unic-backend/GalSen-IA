"""
Entités, relations et provenance (VOLET 36, ch. E).

Le graphe existant stockait `nœud = identifiant de connaissance` et
`arête = (cible, relation)`. Une personne, une loi, un lieu n'y existaient pas,
et surtout : **une relation n'y portait aucune source**. « Cette loi abroge
celle-là » se lisait comme un fait sans que personne puisse dire d'où il venait.

Ces tests épinglent la règle qui ne se négocie pas — rien n'entre sans source —
et le parcours qui rend le magasin utile sans base graphe.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.entities import (  # noqa: E402
    DECLENCHEUR_BASE_GRAPHE,
    PROFONDEUR_MAXIMALE,
    Entity,
    EntityRefused,
    EntityType,
    InMemoryEntityStore,
    Relation,
    entity_store,
)
from src.knowledge_engine.scope import KnowledgeSubject  # noqa: E402

SOURCE = "manifeste:corpus/senegal.yaml#isra-guide"


def entite(label: str, type=EntityType.INSTITUTION, **kwargs) -> Entity:
    """Une entité sourcée, telle qu'un manifeste en produirait."""
    kwargs.setdefault("sources", (SOURCE,))
    kwargs.setdefault("scope", "country:sn")
    return Entity(label=label, type=type, **kwargs)


@pytest.fixture
def magasin() -> InMemoryEntityStore:
    """Un magasin vide."""
    return InMemoryEntityStore()


# ----------------------------------------------------------------------
# Rien n'entre sans source
# ----------------------------------------------------------------------

def test_une_entite_sans_source_est_refusee():
    """
    La règle qui ne se négocie pas.

    Une entité extraite d'un texte par un modèle et rangée sans source serait de
    la connaissance par inférence : elle se lirait comme un fait établi. Le
    magasin refuse — il ne signale pas, il ne marque pas « à vérifier ».
    """
    with pytest.raises(EntityRefused):
        Entity(label="ISRA", type=EntityType.INSTITUTION, sources=())


def test_une_relation_sans_source_est_refusee(magasin):
    """
    Ce que le graphe existant ne savait pas porter.

    Les sources d'une relation sont **distinctes** de celles de ses extrémités :
    savoir qui est ministre et savoir qu'il dirige tel ministère ne viennent pas
    forcément du même document.
    """
    a = magasin.save_entity(entite("ISRA"))
    b = magasin.save_entity(entite("Kaolack", type=EntityType.LOCATION))

    with pytest.raises(EntityRefused):
        Relation(source_id=a, target_id=b, relation="opere_dans", sources=())


def test_une_relation_vers_une_entite_inconnue_est_refusee(magasin):
    """Un lien pendant se lit comme un fait et ne mène nulle part."""
    a = magasin.save_entity(entite("ISRA"))

    with pytest.raises(EntityRefused):
        magasin.save_relation(Relation(
            source_id=a, target_id="ent_inexistante", relation="opere_dans",
            sources=(SOURCE,),
        ))


def test_une_confiance_absente_reste_absente(magasin):
    """
    `None` n'est pas `0.5`.

    Un défaut à mi-chemin serait un chiffre inventé, et il serait lu comme une
    mesure rapportée par la source.
    """
    identifiant = magasin.save_entity(entite("ISRA"))

    assert magasin.get_entity(identifiant).confidence is None


# ----------------------------------------------------------------------
# Aller-retour et identité
# ----------------------------------------------------------------------

def test_une_entite_fait_l_aller_retour_avec_sa_provenance(magasin):
    """Ce qui ressort porte ce qui est entré, provenance comprise."""
    identifiant = magasin.save_entity(entite(
        "ISRA", aliases=("Institut sénégalais de recherches agricoles",),
        subject=KnowledgeSubject.AGRICULTURE, properties={"secteur": "recherche"},
    ))

    relue = magasin.get_entity(identifiant)

    assert relue.label == "ISRA"
    assert relue.sources == (SOURCE,)
    assert relue.scope == "country:sn"
    assert relue.subject is KnowledgeSubject.AGRICULTURE
    assert relue.properties["secteur"] == "recherche"
    assert Entity.from_dict(relue.to_dict()).entity_id == identifiant


def test_la_meme_entite_enregistree_deux_fois_ne_se_duplique_pas(magasin):
    """
    Deux fiches pour la même institution seraient deux vérités que plus rien ne
    rapprocherait. Les sources se réunissent, la version augmente.
    """
    premier = magasin.save_entity(entite("ISRA"))
    second = magasin.save_entity(entite("isra", sources=("manifeste:autre.yaml",)))

    assert premier == second
    relue = magasin.get_entity(premier)
    assert relue.version == 2
    assert set(relue.sources) == {SOURCE, "manifeste:autre.yaml"}
    assert magasin.report()["entities"] == 1


def test_une_entite_se_retrouve_par_son_alias(magasin):
    """Une entité qu'on ne trouve que sous son nom officiel est introuvable."""
    magasin.save_entity(entite("ISRA", aliases=("Institut sénégalais de recherches agricoles",)))

    trouvees = magasin.find_entities(label="recherches agricoles")

    assert len(trouvees) == 1


def test_les_entites_se_filtrent_par_portee_et_par_type(magasin):
    """Les deux axes de l'ADR-019 s'appliquent aussi aux entités."""
    magasin.save_entity(entite("ISRA"))
    magasin.save_entity(entite("FAO", scope="global"))
    magasin.save_entity(entite("Kaolack", type=EntityType.LOCATION))

    assert len(magasin.find_entities(scope="country:sn")) == 2
    assert len(magasin.find_entities(type=EntityType.LOCATION)) == 1


# ----------------------------------------------------------------------
# Relations : validité et parcours
# ----------------------------------------------------------------------

def test_une_relation_porte_ses_sources_et_ses_bornes_de_validite(magasin):
    """
    Une relation cesse d'être vraie : un ministre quitte son poste, une loi est
    abrogée. Sans bornes, une base de relations devient fausse en vieillissant
    sans que rien ne le dise.
    """
    a = magasin.save_entity(entite("Ministère de l'Agriculture"))
    b = magasin.save_entity(entite("Aïssatou Diallo", type=EntityType.PERSON))
    lien = Relation(
        source_id=b, target_id=a, relation="dirige",
        sources=("journal officiel:decret-2024-118",),
        valid_from="2024-03-01", valid_to="2025-09-30",
    )
    magasin.save_relation(lien)

    relue = magasin.relations_of(b)[0]

    assert relue.sources == ("journal officiel:decret-2024-118",)
    assert relue.is_valid_at("2024-06-01") is True
    assert relue.is_valid_at("2026-01-01") is False
    assert relue.is_valid_at("2023-01-01") is False


def test_le_parcours_atteint_la_profondeur_2_avec_son_chemin(magasin):
    """
    Le parcours qui justifie de ne pas prendre de base graphe.

    Le chemin est rendu avec le voisin : un voisin de profondeur 2 sans son
    chemin est une affirmation sans raisonnement.
    """
    isra = magasin.save_entity(entite("ISRA"))
    kaolack = magasin.save_entity(entite("Kaolack", type=EntityType.LOCATION))
    mil = magasin.save_entity(entite("Culture du mil", type=EntityType.CULTURAL_PRACTICE))
    magasin.save_relation(Relation(source_id=isra, target_id=kaolack,
                                   relation="opere_dans", sources=(SOURCE,)))
    magasin.save_relation(Relation(source_id=kaolack, target_id=mil,
                                   relation="pratique", sources=(SOURCE,)))

    voisins = {v["entity"]["entity_id"]: v for v in magasin.neighbours(isra, depth=2)}

    assert voisins[kaolack]["depth"] == 1
    assert voisins[mil]["depth"] == 2
    assert voisins[mil]["path"] == ["opere_dans", "pratique"]


def test_la_profondeur_1_ne_ramene_pas_le_voisin_du_voisin(magasin):
    """Une profondeur demandée est une profondeur respectée."""
    isra = magasin.save_entity(entite("ISRA"))
    kaolack = magasin.save_entity(entite("Kaolack", type=EntityType.LOCATION))
    mil = magasin.save_entity(entite("Culture du mil", type=EntityType.CULTURAL_PRACTICE))
    magasin.save_relation(Relation(source_id=isra, target_id=kaolack,
                                   relation="opere_dans", sources=(SOURCE,)))
    magasin.save_relation(Relation(source_id=kaolack, target_id=mil,
                                   relation="pratique", sources=(SOURCE,)))

    voisins = magasin.neighbours(isra, depth=1)

    assert [v["entity"]["entity_id"] for v in voisins] == [kaolack]


def test_au_dela_de_la_profondeur_maximale_le_magasin_renvoie_au_declencheur(magasin):
    """
    La limite n'est pas arbitraire : elle est le déclencheur écrit de la
    décision « base graphe », pour qu'elle ne devienne pas une affaire de goût.
    """
    isra = magasin.save_entity(entite("ISRA"))

    with pytest.raises(EntityRefused) as refus:
        magasin.neighbours(isra, depth=PROFONDEUR_MAXIMALE + 1)

    assert DECLENCHEUR_BASE_GRAPHE[0] in str(refus.value)


# ----------------------------------------------------------------------
# Mesure et persistance
# ----------------------------------------------------------------------

def test_le_rapport_publie_le_compte_des_entites_sans_source(magasin):
    """
    Il vaut 0 par construction, et le champ reste publié : le jour où un chemin
    d'écriture contournerait le refus, c'est là que ça se verrait.
    """
    magasin.save_entity(entite("ISRA"))

    rapport = magasin.report()

    assert rapport["entities_without_source"] == 0
    assert rapport["relations_without_source"] == 0
    assert rapport["max_depth"] == PROFONDEUR_MAXIMALE
    assert rapport["graph_database_trigger"] == list(DECLENCHEUR_BASE_GRAPHE)


def test_le_magasin_sqlite_persiste_entites_et_relations(tmp_path, monkeypatch):
    """
    Le même magasin, relu depuis le disque : les deux tables tiennent ce que
    l'ontologie exige, sans base graphe.
    """
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "sqlite")

    ecriture = entity_store()
    assert ecriture.report()["backend"] == "sqlite"
    isra = ecriture.save_entity(entite("ISRA", subject=KnowledgeSubject.AGRICULTURE))
    kaolack = ecriture.save_entity(entite("Kaolack", type=EntityType.LOCATION))
    ecriture.save_relation(Relation(source_id=isra, target_id=kaolack,
                                    relation="opere_dans", sources=(SOURCE,),
                                    valid_from="2020-01-01"))

    from src.storage.sqlite_entity_store import SQLiteEntityStore

    relecture = SQLiteEntityStore()
    relue = relecture.get_entity(isra)

    assert relue is not None
    assert relue.sources == (SOURCE,)
    assert relue.subject is KnowledgeSubject.AGRICULTURE
    lien = relecture.relations_of(isra)[0]
    assert lien.relation == "opere_dans"
    assert lien.sources == (SOURCE,)
    assert lien.valid_from == "2020-01-01"
    assert [v["entity"]["entity_id"] for v in relecture.neighbours(isra, depth=1)] == [kaolack]


def test_le_magasin_par_defaut_ne_persiste_pas(tmp_path, monkeypatch):
    """`in-memory` est le défaut, et il reste le défaut (ADR-005)."""
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("GALSEN_STORAGE_BACKEND", raising=False)

    assert entity_store().report()["backend"] == "in-memory"
