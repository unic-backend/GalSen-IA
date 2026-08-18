"""
Validation des workflows (VOLET 08, chapitres 02, 03 et 04).

Le chapitre 02 place « valider les entrées » en deuxième étape du flux, le
chapitre 03 fait de la validation la deuxième étape du cycle de vie, et le
chapitre 04 fixe les métadonnées qu'une définition doit porter. Rien ne validait
quoi que ce soit : un workflow citant un agent inexistant se chargeait sans
bruit, et un workflow sans aucune étape produisait un plan vide dont
l'exécution rapportait `success` sans avoir rien fait.

Ce module sépare deux gravités, parce qu'elles appellent des réactions
différentes :

- **une erreur** rend le workflow inexécutable — l'exécuter produirait un
  résultat trompeur, donc le moteur refuse ;
- **un avertissement** signale une définition incomplète — le workflow tourne,
  mais quelque chose que le manuel exige manque.
"""

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Set

# Métadonnées exigées par le chapitre 04. Leur absence n'empêche pas d'exécuter :
# elle empêche de savoir qui répond du workflow et ce qu'il a changé.
METADONNEES_ATTENDUES = ("description", "version", "owner")

# Clés qu'un workflow peut porter. Une clé inconnue est presque toujours une
# faute de frappe qui laisse la valeur sans effet — le cas le plus coûteux,
# puisque tout se charge normalement.
CLES_CONNUES = {"description", "pipeline", "execution", "version", "owner", "tags"}


@dataclass
class ProblemeWorkflow:
    """Un défaut trouvé dans une définition de workflow."""

    workflow: str
    gravite: str  # "error" ou "warning"
    message: str

    def to_dict(self) -> Dict[str, str]:
        """Sérialise le problème pour un journal ou une réponse d'API."""
        return {"workflow": self.workflow, "severity": self.gravite, "message": self.message}


def _etapes(definition: Dict[str, Any]) -> List[str]:
    """Retourne les agents cités par un workflow, pipeline et groupes confondus."""
    etapes = list(definition.get("pipeline", []) or [])
    execution = definition.get("execution", {}) or {}
    etapes += list(execution.get("sequential_agents", []) or [])
    etapes += list(execution.get("parallel_agents", []) or [])
    return etapes


def validate_workflow(nom: str, definition: Dict[str, Any],
                      agents_connus: Iterable[str]) -> List[ProblemeWorkflow]:
    """
    Valide une définition de workflow.

    Args:
        nom: identifiant du workflow
        definition: sa définition telle que déclarée
        agents_connus: identifiants des agents réellement enregistrés

    Returns:
        La liste des problèmes, vide si la définition est complète et exécutable.
    """
    problemes: List[ProblemeWorkflow] = []
    connus: Set[str] = set(agents_connus)

    if not isinstance(definition, dict):
        return [ProblemeWorkflow(nom, "error", "la définition n'est pas un dictionnaire")]

    etapes = _etapes(definition)
    if not etapes:
        problemes.append(ProblemeWorkflow(
            nom, "error",
            "aucune étape : ni `pipeline` ni `execution` ne cite d'agent. "
            "Exécuter ce workflow rapporterait un succès sans rien faire.",
        ))

    # `router` est l'orchestrateur lui-même : il est filtré à l'exécution et ne
    # compte pas comme un agent manquant.
    inconnus = sorted({e for e in etapes if e != "router" and e not in connus})
    if inconnus:
        problemes.append(ProblemeWorkflow(
            nom, "error",
            f"agent(s) inconnu(s) : {', '.join(inconnus)}. "
            "L'absence ne se voit qu'à l'exécution, à mi-parcours du pipeline.",
        ))

    # Les doublons sont cherchés **à l'intérieur** d'une même liste : un agent
    # présent à la fois dans `pipeline` et dans `execution` n'est pas répété, ce
    # sont deux expressions de la même séquence.
    execution = definition.get("execution", {}) or {}
    for source, liste in (
        ("pipeline", definition.get("pipeline", []) or []),
        ("execution.sequential_agents", execution.get("sequential_agents", []) or []),
        ("execution.parallel_agents", execution.get("parallel_agents", []) or []),
    ):
        doublons = sorted({e for e in liste if liste.count(e) > 1})
        if doublons:
            problemes.append(ProblemeWorkflow(
                nom, "warning",
                f"agent(s) cité(s) plusieurs fois dans `{source}` : {', '.join(doublons)}",
            ))

    for cle in sorted(set(definition) - CLES_CONNUES):
        problemes.append(ProblemeWorkflow(
            nom, "warning",
            f"clé inconnue `{cle}` : elle est chargée et n'a aucun effet",
        ))

    for champ in METADONNEES_ATTENDUES:
        if not definition.get(champ):
            problemes.append(ProblemeWorkflow(
                nom, "warning",
                f"métadonnée absente : `{champ}` (VOLET 08, chapitre 04)",
            ))

    return problemes


def validate_registry(registre: Dict[str, Any],
                      agents_connus: Iterable[str]) -> List[ProblemeWorkflow]:
    """
    Valide un registre de workflows entier, y compris sa cohérence globale.

    Args:
        registre: le contenu de `workflows.yaml`
        agents_connus: identifiants des agents enregistrés

    Returns:
        Tous les problèmes trouvés, workflow par workflow puis registre.
    """
    problemes: List[ProblemeWorkflow] = []
    workflows = registre.get("workflows", {}) or {}

    for nom, definition in workflows.items():
        problemes += validate_workflow(nom, definition, agents_connus)

    defaut = registre.get("default_workflow")
    if defaut and defaut not in workflows:
        problemes.append(ProblemeWorkflow(
            "<registre>", "error",
            f"le workflow par défaut `{defaut}` n'est pas déclaré",
        ))

    # Un bloc `execution` à la racine se lit comme une configuration globale et
    # n'en est pas une : le planificateur lit `execution` **dans** le workflow.
    if "execution" in registre:
        problemes.append(ProblemeWorkflow(
            "<registre>", "warning",
            "bloc `execution` à la racine : il est ignoré, seul le bloc placé "
            "dans un workflow est lu",
        ))

    return problemes


def blocking_errors(problemes: Iterable[ProblemeWorkflow]) -> List[ProblemeWorkflow]:
    """Retourne les seuls problèmes qui rendent un workflow inexécutable."""
    return [p for p in problemes if p.gravite == "error"]
