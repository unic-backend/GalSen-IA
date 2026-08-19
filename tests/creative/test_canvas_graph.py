"""
Tests du graphe et de ses ports (K07.1, ADR-031 décisions 1 et 2).

Les tests qui comptent sont ceux des trois refus : types différents, cycle, et
entrée requise non branchée. Ce sont les trois endroits où un canvas
complaisant produirait un résultat que personne n'a demandé.
"""

import pytest

from src.creative.canvas.graph import (
    DECIDE_PAR_LE_FOURNISSEUR,
    TYPES_DE_NOEUD,
    CanvasGraph,
    GraphRefused,
    graph_report,
)
from src.creative.canvas.ports import (
    TYPE_INCONNU,
    TYPES_DE_PORT,
    TYPES_DIFFERENTS,
    Port,
    PortRefused,
    declared_types,
    edge_is_legal,
    port_report,
)
from src.security.trust import TrustLevel


def _chaine_simple() -> CanvasGraph:
    """prompt → intent → video_generation, la plus courte chaîne complète."""
    graphe = CanvasGraph()
    graphe.add_node("p", "prompt")
    graphe.add_node("i", "intent")
    graphe.add_node("v", "video_generation")
    graphe.connect("p", "text", "i", "text")
    graphe.connect("i", "intent", "v", "intent")
    return graphe


class TestPorts:
    """Le vocabulaire, et la règle d'égalité stricte."""

    def test_un_type_non_declare_est_refuse(self):
        with pytest.raises(PortRefused, match="non déclaré"):
            Port("x", "hologram")

    def test_un_port_sans_nom_est_refuse(self):
        with pytest.raises(PortRefused, match="ne se branche pas"):
            Port("  ", "text")

    def test_deux_types_egaux_sont_legaux(self):
        verdict = edge_is_legal(Port("out", "image"), Port("in", "image"))

        assert verdict["legal"] is True

    def test_deux_types_differents_sont_refuses(self):
        verdict = edge_is_legal(Port("out", "text"), Port("in", "reference"))

        assert verdict["legal"] is False
        assert verdict["refusal"] == TYPES_DIFFERENTS

    def test_le_refus_nomme_les_deux_types(self):
        """Un refus qui n'en nomme qu'un oblige à deviner lequel changer."""
        verdict = edge_is_legal(Port("out", "text"), Port("in", "reference"))

        assert "text" in verdict["reason"]
        assert "reference" in verdict["reason"]

    def test_aucun_elargissement_entre_artefacts(self):
        """image et video sont deux types, pas deux nuances d'un seul."""
        verdict = edge_is_legal(Port("out", "image"), Port("in", "video"))

        assert verdict["legal"] is False

    def test_le_rapport_liste_les_types_avec_leur_definition(self):
        rapport = port_report()

        assert rapport["count"] == len(TYPES_DE_PORT)
        assert set(declared_types()) == set(TYPES_DE_PORT)
        assert all(rapport["port_types"].values())

    def test_le_type_inconnu_a_son_propre_refus(self):
        legal = edge_is_legal(Port("out", "text"), Port("in", "text"))
        assert legal["legal"] is True
        assert TYPE_INCONNU in port_report()["refusals"]


class TestGraphe:
    """Nœuds, arêtes, et ce qui est refusé à la construction."""

    def test_un_type_de_noeud_inconnu_est_refuse(self):
        with pytest.raises(GraphRefused, match="non déclaré"):
            CanvasGraph().add_node("a", "hologram_generation")

    def test_deux_noeuds_de_meme_identifiant_sont_refuses(self):
        graphe = CanvasGraph()
        graphe.add_node("a", "prompt")

        with pytest.raises(GraphRefused, match="existe déjà"):
            graphe.add_node("a", "world")

    def test_une_arete_de_types_differents_est_refusee(self):
        graphe = CanvasGraph()
        graphe.add_node("p", "prompt")
        graphe.add_node("r", "reference")

        with pytest.raises(GraphRefused, match="Aucune conversion implicite"):
            graphe.connect("p", "text", "r", "image")

    def test_un_port_inconnu_est_refuse(self):
        graphe = CanvasGraph()
        graphe.add_node("p", "prompt")
        graphe.add_node("i", "intent")

        with pytest.raises(GraphRefused, match="n'a pas de sortie"):
            graphe.connect("p", "image", "i", "text")

    def test_un_noeud_inconnu_est_refuse(self):
        graphe = CanvasGraph()
        graphe.add_node("p", "prompt")

        with pytest.raises(GraphRefused, match="inconnu"):
            graphe.connect("p", "text", "absent", "text")

    def test_une_entree_n_accepte_qu_une_source(self):
        graphe = CanvasGraph()
        graphe.add_node("p1", "prompt")
        graphe.add_node("p2", "prompt")
        graphe.add_node("i", "intent")
        graphe.connect("p1", "text", "i", "text")

        with pytest.raises(GraphRefused, match="déjà"):
            graphe.connect("p2", "text", "i", "text")


class TestCycle:
    """Un graphe cyclique n'a pas d'ordre, et aucun ne s'invente."""

    def test_un_cycle_est_refuse(self):
        graphe = CanvasGraph()
        graphe.add_node("g", "image_generation")
        graphe.add_node("r", "reference")
        graphe.connect("g", "image", "r", "image")

        with pytest.raises(GraphRefused, match="cycle"):
            graphe.connect("r", "reference", "g", "reference")

    def test_le_graphe_reste_intact_apres_un_refus_de_cycle(self):
        graphe = CanvasGraph()
        graphe.add_node("g", "image_generation")
        graphe.add_node("r", "reference")
        graphe.connect("g", "image", "r", "image")

        with pytest.raises(GraphRefused):
            graphe.connect("r", "reference", "g", "reference")

        assert len(graphe.edges) == 1
        assert graphe.topological_order() == ["g", "r"]


class TestOrdre:
    """L'ordre est déterministe, sinon le plan n'est pas reproductible."""

    def test_chaque_noeud_vient_apres_ses_sources(self):
        assert _chaine_simple().topological_order() == ["p", "i", "v"]

    def test_l_ordre_est_stable_d_un_appel_a_l_autre(self):
        graphe = _chaine_simple()

        assert graphe.topological_order() == graphe.topological_order()

    def test_un_noeud_isole_figure_dans_l_ordre(self):
        graphe = _chaine_simple()
        graphe.add_node("w", "world")

        assert set(graphe.topological_order()) == {"p", "i", "v", "w"}


class TestEntreesRequises:
    """Une entrée requise non branchée est nommée, jamais remplie."""

    def test_une_entree_requise_non_branchee_est_nommee(self):
        graphe = CanvasGraph()
        graphe.add_node("v", "video_generation")

        manquantes = graphe.unconnected_required_inputs()

        assert manquantes == [{"node_id": "v", "port": "intent",
                               "port_type": "intent"}]

    def test_les_entrees_optionnelles_ne_manquent_jamais(self):
        graphe = _chaine_simple()

        assert graphe.unconnected_required_inputs() == []

    def test_aucun_defaut_n_est_pose(self):
        """Le port manquant est rendu, pas comblé — c'est le geste refusé."""
        graphe = CanvasGraph()
        graphe.add_node("i", "intent")

        manquantes = graphe.unconnected_required_inputs()

        assert len(manquantes) == 1
        assert graphe.edges == []


class TestConfiance:
    """La correspondance que K00 a trouvée manquante."""

    def test_chaque_type_de_noeud_porte_une_confiance(self):
        for nom, type_de_noeud in TYPES_DE_NOEUD.items():
            assert type_de_noeud.trust is not None, nom

    def test_une_demande_est_de_niveau_utilisateur(self):
        assert _chaine_simple().trust_of("p") == TrustLevel.USER

    def test_un_fichier_fourni_est_une_donnee(self):
        graphe = CanvasGraph()
        graphe.add_node("u", "image_upload")

        assert graphe.trust_of("u") == TrustLevel.DOCUMENT

    def test_un_noeud_de_generation_n_a_pas_de_confiance_par_defaut(self):
        graphe = _chaine_simple()

        with pytest.raises(GraphRefused, match="où part la donnée"):
            graphe.trust_of("v")

    def test_un_noeud_de_generation_prend_celle_du_fournisseur(self):
        graphe = _chaine_simple()

        assert graphe.trust_of("v", TrustLevel.EXTERNAL) == TrustLevel.EXTERNAL

    def test_les_noeuds_de_generation_sont_marques_comme_tels(self):
        assert TYPES_DE_NOEUD["video_generation"].trust == DECIDE_PAR_LE_FOURNISSEUR
        assert TYPES_DE_NOEUD["image_generation"].trust == DECIDE_PAR_LE_FOURNISSEUR


class TestRapport:
    """Le rapport dit ce qui est tenu."""

    def test_le_rapport_compte_les_types_de_noeud(self):
        assert graph_report()["count"] == len(TYPES_DE_NOEUD)

    def test_le_rapport_serialise_la_confiance(self):
        rapport = graph_report()["node_types"]

        assert rapport["prompt"]["trust"] == "user"
        assert rapport["video_generation"]["trust"] == DECIDE_PAR_LE_FOURNISSEUR

    def test_le_graphe_se_serialise(self):
        serialise = _chaine_simple().as_dict()

        assert len(serialise["nodes"]) == 3
        assert len(serialise["edges"]) == 2
