"""
Les deux agents du VOLET 36 (ch. G), chacun défini par ce qu'il ne décide pas.

1. **`knowledge_architect`** — il peut poser `scope: country:sn` sur un document
   et décider seul quelles questions la plateforme s'autorise à répondre avec
   lui. Le test qui compte est que sa proposition **n'est jamais appliquée**.
2. **`data_engineer`** — il peut décrire une série sans unité ni année, et
   produire un chiffre faux en attente d'être cité. Le test qui compte est le
   **refus**, et il vient avant le cas nominal.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.data_engineer.agent import (  # noqa: E402
    DECLARATIONS_EXIGEES,
    NON_DEDUIT,
    DataEngineeringAgent,
)
from agents.knowledge_architect.agent import (  # noqa: E402
    NON_DECIDE,
    KnowledgeArchitectAgent,
)
from src.agent.context import AgentContext  # noqa: E402
from src.knowledge_engine.scope import KnowledgeSubject  # noqa: E402


def contexte(requete: str = "", agent_id: str = "test", **options) -> AgentContext:
    """Contexte d'agent avec ses options."""
    return AgentContext(request=requete, agent_id=agent_id, options=options or None)


# ----------------------------------------------------------------------
# 1. L'architecte de connaissance
# ----------------------------------------------------------------------

def test_la_proposition_n_est_jamais_appliquee(tmp_path):
    """
    Le test qui justifie cet agent.

    Poser une portée, c'est décider quelles questions la plateforme s'autorise
    à répondre avec ce document — `senegal` refuse un sujet national sans source
    nationale. Cette décision revient à une personne.
    """
    document = tmp_path / "guide-mil-kaolack.md"
    document.write_text(
        "# Guide de culture du mil\n\nLe semis du mil à Kaolack commence avec les "
        "premières pluies. La récolte suit l'hivernage.",
        encoding="utf-8",
    )

    resultat = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path=str(document))
    )

    assert resultat["status"] == "proposed"
    assert resultat["requires_human_confirmation"] is True
    assert resultat["proposal"]["status"] == "DRAFT"
    assert resultat["not_decided"] == list(NON_DECIDE)


def test_la_proposition_porte_les_deux_axes_et_un_titre(tmp_path):
    """Ce qu'un humain écrit à la main aujourd'hui : titre, portée, sujet."""
    document = tmp_path / "guide-mil.md"
    document.write_text(
        "# Guide de culture du mil\n\nLe semis à Kaolack suit les pluies.",
        encoding="utf-8",
    )

    proposition = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path=str(document))
    )["proposal"]

    assert proposition["title"] == "Guide de culture du mil"
    assert proposition["scope"] == "country:sn"
    assert proposition["subject"] == KnowledgeSubject.AGRICULTURE.value


def test_un_classement_incertain_propose_unspecified_et_le_dit(tmp_path):
    """
    Un sujet deviné est pire qu'un sujet absent : le document devient trouvable
    sous une étiquette qu'il ne mérite pas, et introuvable sous la bonne.
    """
    document = tmp_path / "note.md"
    document.write_text("Compte rendu de la réunion hebdomadaire.", encoding="utf-8")

    resultat = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path=str(document))
    )

    assert resultat["proposal"]["subject"] == KnowledgeSubject.UNSPECIFIED.value
    assert any("subject" in ligne for ligne in resultat["uncertain"])


def test_ni_la_categorie_de_source_ni_la_langue_ne_sont_devinees(tmp_path):
    """
    La catégorie dépend de qui publie, pas du texte : elle reste vide.

    **Mis à jour le 2026-08-13 (ADR-021, étape 6)** : la langue avait la même
    raison d'être vide — « aucun détecteur dans le dépôt ». Ce n'est plus vrai.
    Ici elle reste `None` pour une **autre** raison, mesurée : une phrase de dix
    mots est trop courte pour qu'un verdict veuille dire quelque chose.
    """
    document = tmp_path / "texte.md"
    document.write_text("Le foncier à Ziguinchor relève d'une loi propre.", encoding="utf-8")

    resultat = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path=str(document))
    )
    proposition = resultat["proposal"]

    assert proposition["source_category"] is None
    assert proposition["language"] is None
    assert any("non détectée" in ligne for ligne in resultat["uncertain"])


def test_la_langue_detectee_est_proposee_et_marquee_comme_detectee(tmp_path):
    """
    Détectée n'est pas déclarée. La proposer sans le dire ferait passer une
    mesure pour une déclaration de l'éditeur.
    """
    document = tmp_path / "rapport.md"
    document.write_text(
        "Le rapport présente les résultats de l'enquête menée dans les régions du "
        "pays. Les données sont issues des services statistiques et ont été "
        "collectées par les équipes avec les partenaires qui participent à cette "
        "opération.",
        encoding="utf-8",
    )

    resultat = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path=str(document))
    )

    assert resultat["proposal"]["language"] == "fr"
    assert any("détectée" in ligne and "confirmer" in ligne for ligne in resultat["uncertain"])


def test_les_entites_sont_des_candidats_non_confirmes(tmp_path):
    """
    Une suite de mots capitalisés n'est pas une entité. Le magasin refuse tout
    ce qui n'a pas de source, et « vu dans un document » n'en est pas une.
    """
    document = tmp_path / "texte.md"
    document.write_text(
        "L'ISRA conduit des essais à Kaolack avec le Ministère de l'Agriculture.",
        encoding="utf-8",
    )

    candidats = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path=str(document))
    )["candidate_entities"]

    assert candidats, "Aucun candidat repéré dans un texte qui en porte"
    assert all(candidat["confirmed"] is False for candidat in candidats)
    assert all(candidat["type"] is None for candidat in candidats)


def test_un_fichier_absent_ne_produit_pas_de_proposition_vide():
    """Une proposition vide se lirait comme « rien à classer », ce qui est faux."""
    resultat = KnowledgeArchitectAgent().perform(
        contexte(agent_id="knowledge_architect", path="/introuvable/nulle-part.md")
    )

    assert resultat["status"] == "nothing_to_classify"
    assert resultat["proposal"] is None


# ----------------------------------------------------------------------
# 2. L'ingénieur de données — le refus d'abord
# ----------------------------------------------------------------------

@pytest.fixture
def serie(tmp_path):
    """Une série statistique, telle qu'une agence en publie."""
    chemin = tmp_path / "production-mil.csv"
    chemin.write_text(
        "annee,region,production\n2022,Kaolack,125000\n2023,Kaolack,131500\n",
        encoding="utf-8",
    )
    return str(chemin)


def test_une_serie_sans_unite_ni_periode_est_refusee(serie):
    """
    Le test qui vient avant le cas nominal.

    « La population est de 18 millions » est vraie, fausse ou dénuée de sens
    selon une année que personne n'a écrite. Un chiffre sans unité ni période
    est un chiffre faux en attente d'être cité.
    """
    resultat = DataEngineeringAgent().perform(
        contexte(agent_id="data_engineer", path=serie)
    )

    assert resultat["status"] == "undeclared_series"
    assert set(resultat["missing"]) == set(DECLARATIONS_EXIGEES)
    assert resultat["schema"] is None


def test_une_declaration_partielle_est_refusee_aussi(serie):
    """Deux déclarations sur trois ne font pas une série citable."""
    resultat = DataEngineeringAgent().perform(contexte(
        agent_id="data_engineer", path=serie, units="tonnes", period="2022-2023",
    ))

    assert resultat["status"] == "undeclared_series"
    assert resultat["missing"] == ["source"]


def test_le_refus_nomme_ce_qui_ne_se_deduit_pas_du_fichier(serie):
    """
    « montant » ne dit pas si ce sont des FCFA, des milliers ou des dollars.
    Deviner ici serait indiscernable d'un fait pour tout lecteur suivant.
    """
    resultat = DataEngineeringAgent().perform(
        contexte(agent_id="data_engineer", path=serie)
    )

    assert resultat["not_inferred"] == list(NON_DEDUIT)


def test_une_serie_declaree_est_decrite_avec_ses_types_deduits(serie):
    """Le cas nominal, une fois la déclaration faite."""
    resultat = DataEngineeringAgent().perform(contexte(
        agent_id="data_engineer", path=serie, units="tonnes",
        period="2022-2023", source="ANSD — annuaire statistique",
    ))

    assert resultat["status"] == "described"
    colonnes = {colonne["name"]: colonne for colonne in resultat["schema"]["columns"]}
    assert colonnes["production"]["type"] == "number"
    assert colonnes["region"]["type"] == "text"
    # `2022` est une année et un compte : la colonne est rendue « number », et
    # c'est la déclaration `period` qui porte l'année — la raison même pour
    # laquelle cet agent l'exige au lieu de la deviner.
    assert colonnes["annee"]["type"] == "number"
    assert all(colonne["type_method"] == "inferred" for colonne in colonnes.values())
    assert resultat["schema"]["rows_sampled"] == 2
    assert resultat["declared"]["units"] == "tonnes"
    assert resultat["requires_human_confirmation"] is True


def test_une_colonne_vide_n_est_pas_dite_texte(tmp_path):
    """
    Une colonne sans valeur est sans information. La dire « texte » ferait un
    schéma faux qui aurait l'air complet.
    """
    chemin = tmp_path / "vide.csv"
    chemin.write_text("annee,note\n2023,\n2024,\n", encoding="utf-8")

    resultat = DataEngineeringAgent().perform(contexte(
        agent_id="data_engineer", path=str(chemin), units="sans objet",
        period="2023-2024", source="test",
    ))

    colonnes = {colonne["name"]: colonne["type"] for colonne in resultat["schema"]["columns"]}
    assert colonnes["note"] == "unknown"


def test_rien_n_est_enregistre_par_l_ingenieur_de_donnees(serie):
    """Décrire n'est pas ingérer : l'ingestion de documents reste ailleurs."""
    resultat = DataEngineeringAgent().perform(contexte(
        agent_id="data_engineer", path=serie, units="tonnes",
        period="2022-2023", source="ANSD",
    ))

    serialise = str(resultat)
    assert "knowledge_ids" not in serialise and "ingested" not in serialise


# ----------------------------------------------------------------------
# Le registre
# ----------------------------------------------------------------------

def test_les_deux_agents_sont_declares_au_registre():
    """Un agent absent du registre n'est joignable par aucun chemin."""
    import yaml

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "agents", "registry.yaml"), encoding="utf-8") as fichier:
        registre = yaml.safe_load(fichier)

    declares = {agent["id"]: agent for agent in registre["agents"]}
    for agent_id in ("knowledge_architect", "data_engineer"):
        assert agent_id in declares, f"« {agent_id} » absent de agents/registry.yaml"
        assert declares[agent_id]["enabled"] is True
        assert declares[agent_id]["module"] == f"agents.{agent_id}.agent"


@pytest.mark.parametrize("agent_id", ["knowledge_architect", "data_engineer"])
def test_les_deux_agents_repondent_par_leur_point_d_entree(agent_id):
    """Le point d'entrée historique est ce que le répartiteur appelle."""
    import importlib

    module = importlib.import_module(f"agents.{agent_id}.agent")
    resultat = module.execute("Le mil se sème avec les premières pluies à Kaolack.")

    assert resultat["agent"] == agent_id
    assert resultat["status"] == "success", resultat.get("error")


def test_les_marqueurs_ne_sont_ecrits_qu_une_fois():
    """
    Le chapitre G a donné un second lecteur aux marqueurs du chapitre F.

    Deux copies d'une même liste divergent — le dépôt a déjà payé quatre fois ce
    mode de défaillance. Elles vivent désormais dans un seul module.
    """
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    porteurs = []
    for dossier in ("src", "agents"):
        for chemin_racine, _, fichiers in os.walk(os.path.join(racine, dossier)):
            for nom in fichiers:
                if not nom.endswith(".py"):
                    continue
                chemin = os.path.join(chemin_racine, nom)
                with open(chemin, encoding="utf-8") as fichier:
                    if '"ziguinchor"' in fichier.read():
                        porteurs.append(os.path.relpath(chemin, racine))

    assert porteurs == [os.path.join("src", "knowledge_engine", "markers.py")]
