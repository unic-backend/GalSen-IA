"""
Un graphe dérivé du programme officiel, jamais écrit
(VOLET 14 de Darra J).

La chaîne de la directive XXIX — niveau → matière → unité → objectif →
prérequis — est facile à dessiner et facile à rater d'une manière précise : un
graphe est l'artefact le plus convaincant qu'une plateforme puisse produire, et
personne ne lit une arête en demandant qui l'a décidée.

Ce que ces tests gardent :

1. **Chaque arête porte le champ officiel dont elle vient.**
2. **Les prérequis sont rapprochés par égalité exacte**, jamais par
   ressemblance.
3. **Un prérequis qui ne désigne rien reste `DANGLING`**, avec son texte.
4. **Un cycle est rendu, jamais coupé.**
5. **Un registre vide donne un graphe vide qui le dit.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j import (  # noqa: E402
    CurriculumUnit,
    CurriculumVersion,
    EducationSystem,
    Grade,
    Period,
    Subject,
    make_provenance,
)
from src.darra_j.graph import (  # noqa: E402
    ARETE_CONTIENT,
    ARETE_EXIGE,
    ARETE_VISE,
    NOEUD_OBJECTIF,
    NOEUD_UNITE,
    PENDANT,
    build_graph,
    graph_report,
)
from src.darra_j.registry import CurriculumRegistry  # noqa: E402

SYSTEME = EducationSystem(country="sn", system_id="sn-general")


def _officielle():
    """Une provenance de rang officiel."""
    return make_provenance(
        authority="Ministère de l'Éducation nationale",
        source_tier="TIER_A_PRIMARY_OFFICIAL",
        source_document="jo://curriculum/2026",
    )


def _registre(*unites):
    """Un registre portant ces unités, dans une version enregistrée."""
    depot = CurriculumRegistry()
    depot.register_version(CurriculumVersion(
        version_id="v-2026", education_system=SYSTEME,
        academic_year="2026-2027", provenance=_officielle(),
    ))
    for unite in unites:
        depot.add_unit(unite)
    return depot


def _unite(titre, semaine, objectifs=(), prerequis=(), matiere="maths"):
    """Une unité officielle."""
    return CurriculumUnit(
        version_id="v-2026", grade=Grade("g6", "Sixième"),
        subject=Subject(matiere, matiere.capitalize()),
        period=Period(academic_year="2026-2027", week=semaine),
        official_title=titre, objectives=tuple(objectifs),
        prerequisites=tuple(prerequis), provenance=_officielle(),
    )


@pytest.fixture
def graphe():
    """Deux unités officielles, la seconde exigeant la première."""
    return build_graph(_registre(
        _unite("La division euclidienne", 8,
               objectifs=("Poser une division",)),
        _unite("Les fractions", 10,
               objectifs=("Comparer deux fractions",),
               prerequis=("La division euclidienne",)),
    ), "v-2026")


# ----------------------------------------------------------------------
# 1. Chaque arête dit d'où elle vient
# ----------------------------------------------------------------------

def test_chaque_arete_nomme_le_champ_officiel(graphe):
    """Sans cela, une arête est une affirmation incontestable."""
    for arete in graphe.edges:
        assert arete.derived_from, arete

    natures = {arete.derived_from.split(".")[-1] for arete in graphe.edges}
    assert natures <= {"grade", "subject", "objectives", "prerequisites"}


def test_une_arete_de_prerequis_vient_du_champ_prerequisites(graphe):
    """Le champ est nommé, pas seulement l'unité."""
    exigences = [a for a in graphe.edges if a.kind == ARETE_EXIGE]

    assert len(exigences) == 1
    assert exigences[0].derived_from.endswith(".prerequisites")


def test_la_chaine_niveau_matiere_unite_objectif_existe(graphe):
    """La chaîne de la directive XXIX, dérivée et non dessinée."""
    natures = graphe.as_dict()["nodes_by_kind"]

    assert natures["grade"] == 1
    assert natures["subject"] == 1
    assert natures[NOEUD_UNITE] == 2
    assert natures[NOEUD_OBJECTIF] == 2
    assert {a.kind for a in graphe.edges} == {ARETE_CONTIENT, ARETE_VISE,
                                             ARETE_EXIGE}


def test_les_objectifs_sont_rattaches_a_leur_unite(graphe):
    """Un objectif appartient à une unité, pas au programme en général."""
    identifiants = graphe.objectives_of(
        [i for i, n in graphe.nodes.items()
         if n["label"] == "Les fractions"][0]
    )

    assert len(identifiants) == 1
    assert graphe.nodes[identifiants[0]]["label"] == "Comparer deux fractions"


# ----------------------------------------------------------------------
# 2. Le rapprochement est exact, jamais approché
# ----------------------------------------------------------------------

def test_un_prerequis_designe_l_unite_au_titre_identique(graphe):
    """Le cas nominal existe."""
    fractions = [i for i, n in graphe.nodes.items()
                 if n["label"] == "Les fractions"][0]
    division = [i for i, n in graphe.nodes.items()
                if n["label"] == "La division euclidienne"][0]

    assert graphe.prerequisites_of(fractions) == [division]
    assert graphe.unlocked_by(division) == [fractions]


def test_un_titre_voisin_ne_suffit_pas():
    """
    La leçon déjà payée une fois (`find_country`, VOLET 69).

    « La division » et « La division euclidienne » sont deux titres. Les
    rapprocher déclarerait en silence un prérequis que le ministère n'a jamais
    désigné.
    """
    graphe = build_graph(_registre(
        _unite("La division euclidienne", 8),
        _unite("Les fractions", 10, prerequis=("La division",)),
    ), "v-2026")

    assert [a for a in graphe.edges if a.kind == ARETE_EXIGE] == []
    assert graphe.dangling[0]["text"] == "La division"


def test_l_accent_et_la_casse_ne_font_pas_deux_unites():
    """Le repliement est celui du reste du paquet : exact, pas approché."""
    graphe = build_graph(_registre(
        _unite("La division euclidienne", 8),
        _unite("Les fractions", 10, prerequis=("la DIVISION EUCLIDIENNE",)),
    ), "v-2026")

    assert len([a for a in graphe.edges if a.kind == ARETE_EXIGE]) == 1
    assert graphe.dangling == []


# ----------------------------------------------------------------------
# 3. Un prérequis pendant reste pendant
# ----------------------------------------------------------------------

def test_un_prerequis_sans_unite_est_nomme_pas_supprime():
    """C'est un fait sur lequel une équipe curriculaire peut agir."""
    graphe = build_graph(_registre(
        _unite("Les fractions", 10, prerequis=("Un chapitre jamais publié",)),
    ), "v-2026")

    pendant = graphe.dangling[0]
    assert pendant["status"] == PENDANT
    assert pendant["text"] == "Un chapitre jamais publié"
    assert "personne n'a publié" in pendant["reason"]


def test_un_prerequis_pendant_ne_cree_aucune_arete():
    """Inventer la cible serait écrire du curriculum."""
    graphe = build_graph(_registre(
        _unite("Les fractions", 10, prerequis=("Un chapitre jamais publié",)),
    ), "v-2026")

    assert [a for a in graphe.edges if a.kind == ARETE_EXIGE] == []
    assert graphe.as_dict()["dangling_prerequisites"]


# ----------------------------------------------------------------------
# 4. Un cycle est rendu, jamais coupé
# ----------------------------------------------------------------------

def test_un_cycle_de_prerequis_est_rapporte():
    """Couper produirait un ordre plausible et cacherait le défaut."""
    graphe = build_graph(_registre(
        _unite("A", 1, prerequis=("B",)),
        _unite("B", 2, prerequis=("A",)),
    ), "v-2026")

    cycles = graphe.cycles()

    assert cycles, "Le cycle publié doit être visible"
    assert len(graphe.as_dict()["edges"]) >= 2


def test_une_chaine_avec_cycle_dit_pourquoi_elle_s_arrete():
    """Un ordre rendu sans avertissement serait pire qu'aucun ordre."""
    graphe = build_graph(_registre(
        _unite("A", 1, prerequis=("B",)),
        _unite("B", 2, prerequis=("A",)),
    ), "v-2026")
    unite_a = [i for i, n in graphe.nodes.items() if n["label"] == "A"][0]

    chaine = graphe.chain_to(unite_a)

    assert chaine["cycles"]
    assert "défaut institutionnel" in chaine["reason"]


def test_une_chaine_sans_cycle_donne_l_ordre_officiel():
    """Du plus profond au plus proche."""
    graphe = build_graph(_registre(
        _unite("A", 1),
        _unite("B", 2, prerequis=("A",)),
        _unite("C", 3, prerequis=("B",)),
    ), "v-2026")
    identifiants = {n["label"]: i for i, n in graphe.nodes.items()
                    if n["kind"] == NOEUD_UNITE}

    chaine = graphe.chain_to(identifiants["C"])

    assert chaine["before"] == [identifiants["A"], identifiants["B"]]
    assert chaine["cycles"] == []


# ----------------------------------------------------------------------
# 5. Un registre vide donne un graphe vide
# ----------------------------------------------------------------------

def test_un_registre_vide_donne_un_graphe_vide_qui_le_dit():
    """C'est l'état attendu tant qu'aucune autorité n'a fourni de données."""
    rendu = build_graph(CurriculumRegistry(), "v-inconnue").as_dict()

    assert rendu["empty"] is True
    assert rendu["node_count"] == 0
    assert "aucune autorité" in rendu["note"]


def test_le_graphe_est_deterministe():
    """Deux constructions incomparables rendraient tout rapport inutile."""
    def _construire():
        return build_graph(_registre(
            _unite("A", 1), _unite("B", 2, prerequis=("A",)),
        ), "v-2026").as_dict()

    assert _construire() == _construire()


# ----------------------------------------------------------------------
# 6. Ce que le graphe ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_refuse_de_deduire_une_arete(graphe):
    """La règle est écrite là où elle est appliquée."""
    rapport = graph_report(graphe)

    interdits = " ".join(rapport["does_not"])
    assert "que le curriculum officiel ne porte pas" in interdits
    assert "titres voisins" in interdits
    assert rapport["graph"]["edge_count"] == len(graphe.edges)


def test_le_rapport_refuse_de_reparer_un_curriculum():
    """Réparer ici cacherait ce que le graphe existe pour montrer."""
    assert "Réparer un curriculum incohérent." in graph_report()["does_not"]
