"""
Tests de la validation des workflows (VOLET 08, chapitres 02, 03 et 04).

Rien ne validait un workflow : celui qui citait un agent inexistant se chargeait
sans bruit, et celui qui n'avait aucune étape produisait un plan vide dont
l'exécution rapportait `success` sans avoir exécuté un seul agent. C'est le pire
des deux mondes — une réponse crédible obtenue sans travail.
"""

from pathlib import Path

import pytest
import yaml

from src.router.agent_loader import AgentLoader
from src.router.workflow_loader import WorkflowLoader
from src.router.workflow_validator import (
    blocking_errors, validate_registry, validate_workflow,
)

RACINE = Path(__file__).resolve().parent.parent
AGENTS = ("planner", "researcher", "coder", "reviewer", "tester",
          "security", "documentation", "deployment", "monitor")


def _registre(tmp_path: Path, contenu: dict) -> WorkflowLoader:
    """Écrit un registre de workflows temporaire et retourne son chargeur."""
    chemin = tmp_path / "workflows.yaml"
    chemin.write_text(yaml.safe_dump(contenu, allow_unicode=True), encoding="utf-8")
    return WorkflowLoader(str(chemin))


def test_le_registre_du_depot_est_valide():
    """Les workflows livrés doivent passer leur propre validation."""
    chargeur = WorkflowLoader(str(RACINE / "workflows" / "workflows.yaml"))
    agents = AgentLoader(str(RACINE / "agents" / "registry.yaml")).get_all_agents()
    problemes = chargeur.validate(agents.keys(), journaliser=False)
    assert problemes == [], [p.to_dict() for p in problemes]


def test_un_agent_inexistant_est_une_erreur():
    """L'absence ne se voyait qu'à l'exécution, à mi-parcours du pipeline."""
    problemes = validate_workflow(
        "casse", {"description": "x", "version": "1.0", "owner": "y",
                  "pipeline": ["reviewer", "agent_fantome"]}, AGENTS)
    erreurs = blocking_errors(problemes)
    assert len(erreurs) == 1
    assert "agent_fantome" in erreurs[0].message


def test_un_workflow_sans_etape_est_une_erreur():
    """Il rapportait `success` sans rien faire : c'est le défaut le plus coûteux."""
    problemes = validate_workflow("vide", {"description": "x", "version": "1.0",
                                           "owner": "y"}, AGENTS)
    erreurs = blocking_errors(problemes)
    assert len(erreurs) == 1
    assert "aucune étape" in erreurs[0].message


def test_le_routeur_orchestrateur_n_est_pas_un_agent_manquant():
    """`router` figure dans le pipeline standard et est filtré à l'exécution."""
    problemes = validate_workflow(
        "standard", {"description": "x", "version": "1.0", "owner": "y",
                     "pipeline": ["router", "reviewer"]}, AGENTS)
    assert blocking_errors(problemes) == []


def test_les_metadonnees_manquantes_sont_des_avertissements():
    """Une définition incomplète tourne ; elle ne dit pas qui en répond."""
    problemes = validate_workflow("minimal", {"pipeline": ["reviewer"]}, AGENTS)
    assert blocking_errors(problemes) == []
    manquants = {p.message for p in problemes}
    assert any("version" in m for m in manquants)
    assert any("owner" in m for m in manquants)


def test_un_agent_repete_dans_une_meme_liste_est_signale():
    """Répété dans `pipeline` : suspect. Présent aussi dans `execution` : normal."""
    repete = validate_workflow(
        "repete", {"description": "x", "version": "1.0", "owner": "y",
                   "pipeline": ["reviewer", "reviewer"]}, AGENTS)
    assert any("plusieurs fois" in p.message for p in repete)

    deux_sources = validate_workflow(
        "deux", {"description": "x", "version": "1.0", "owner": "y",
                 "pipeline": ["reviewer"],
                 "execution": {"sequential_agents": ["reviewer"]}}, AGENTS)
    assert not any("plusieurs fois" in p.message for p in deux_sources)


def test_une_cle_inconnue_est_signalee():
    """Une faute de frappe se charge normalement et n'a aucun effet."""
    problemes = validate_workflow(
        "typo", {"description": "x", "version": "1.0", "owner": "y",
                 "pipeline": ["reviewer"], "piepline": ["security"]}, AGENTS)
    assert any("piepline" in p.message for p in problemes)


def test_un_workflow_par_defaut_absent_est_une_erreur():
    """Le défaut doit exister, sinon toute requête sans workflow échoue."""
    problemes = validate_registry(
        {"default_workflow": "fantome",
         "workflows": {"revue": {"description": "x", "version": "1.0", "owner": "y",
                                 "pipeline": ["reviewer"]}}}, AGENTS)
    assert any("fantome" in p.message for p in blocking_errors(problemes))


def test_un_bloc_execution_a_la_racine_est_signale():
    """Il se lit comme une configuration globale et n'est lu par personne."""
    problemes = validate_registry(
        {"workflows": {}, "execution": {"parallel_agents": ["researcher"]}}, AGENTS)
    assert any("racine" in p.message for p in problemes)


def test_le_chargeur_expose_l_executabilite(tmp_path):
    """`is_executable` sépare ce qui peut tourner de ce qui mentirait."""
    chargeur = _registre(tmp_path, {
        "default_workflow": "bon",
        "workflows": {
            "bon": {"description": "x", "version": "1.0", "owner": "y",
                    "pipeline": ["reviewer"]},
            "casse": {"description": "x", "version": "1.0", "owner": "y",
                      "pipeline": ["agent_fantome"]},
        },
    })
    chargeur.validate(AGENTS, journaliser=False)
    assert chargeur.is_executable("bon") is True
    assert chargeur.is_executable("casse") is False


def test_le_moteur_refuse_un_workflow_inexecutable(tmp_path, monkeypatch):
    """Plutôt qu'un `success` obtenu sans exécuter un seul agent."""
    from src.router.router_engine import RouterEngine

    moteur = RouterEngine()
    chargeur = _registre(tmp_path, {
        "default_workflow": "vide",
        "workflows": {"vide": {"description": "aucune étape", "version": "1.0",
                               "owner": "y"}},
    })
    chargeur.validate(AGENTS, journaliser=False)
    monkeypatch.setattr(moteur, "workflow_loader", chargeur)
    monkeypatch.setattr(moteur.execution_planner, "workflow_loader", chargeur)

    reponse = moteur.process_request("Peu importe", workflow_id="vide")
    assert reponse["status"] == "error"
    assert "inexécutable" in str(reponse.get("error", "")) or "inexécutable" in str(reponse)
