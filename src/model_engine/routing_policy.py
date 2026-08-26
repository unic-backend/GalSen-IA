"""
Quel modèle sert quelle tâche (VOLET 30 — ADR-014).

La politique existait, mais **en dur** dans `ProviderSelector.TASK_REQUIREMENTS` :
huit types de tâche avec leur contexte minimal. La changer demandait de modifier
du code, alors que c'est une décision d'exploitation — elle dépend des modèles
réellement installés sur la machine, pas de l'architecture. Les règles du projet
le disent : « Never hardcode business logic. Use configuration files whenever
possible. »

Ce module la lit dans `config/model_routing.yaml` et y ajoute ce qui manquait :

- **Les familles SamP et ToP** (ADR-014). SamP raisonne et parle, ToP code et
  voit. Elles n'existent pas encore — le VOLET 33 les produira — donc la
  politique **rapporte** qu'aucun modèle de la famille visée n'est servi et
  retombe sur le meilleur disponible. Elle ne fait jamais passer un modèle
  générique pour SamP : ce serait exactement la fabrication que ce dépôt refuse.
- **Le coût comme critère qui filtre vraiment.** `max_cost` était accepté par
  `SimpleModelSelector` et suivi d'un `pass` commenté « dans une implémentation
  réelle » : l'appelant croyait poser un plafond qui n'existait pas.
- **La règle « question simple → petit modèle »**, sous la forme
  `prefer_cheapest` : pour une conversation ordinaire, le moins cher des modèles
  capables suffit, et c'est la seule optimisation de coût qui ne dégrade rien.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

FICHIER_POLITIQUE = os.path.join("config", "model_routing.yaml")

# Politique minimale, appliquée si le fichier est absent ou illisible. Elle est
# volontairement modeste : mieux vaut router prudemment que refuser de router.
POLITIQUE_DE_SECOURS: Dict[str, Any] = {
    "families": {},
    "complexity_context": {"simple": 4096, "medium": 8192, "high": 32000, "very_high": 100000},
    "tasks": {},
    "default": {"min_context_window": 4096, "prefer_cheapest": True},
}


@dataclass
class RouteDecision:
    """Ce que la politique a décidé, et pourquoi."""

    task_type: Optional[str]
    family: Optional[str]
    requirements: Dict[str, Any] = field(default_factory=dict)
    family_available: bool = True
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la décision, pour la réponse et pour la trace."""
        donnees = {
            "task_type": self.task_type,
            "family": self.family,
            "requirements": self.requirements,
            "reason": self.reason,
        }
        if self.family and not self.family_available:
            donnees["family_available"] = False
        return donnees


class RoutingPolicy:
    """
    Politique de routage lue dans la configuration.

    Exemple:
        politique = RoutingPolicy()
        decision = politique.decide({"task_type": "code_generation"})
    """

    def __init__(self, chemin: Optional[str] = None):
        """
        Args:
            chemin: Fichier de politique ; `config/model_routing.yaml` par défaut,
                résolu depuis la racine du dépôt pour que le répertoire courant
                n'ait aucune influence.
        """
        self._chemin = chemin or self._chemin_par_defaut()
        self._politique = self._charger()

    @staticmethod
    def _chemin_par_defaut() -> str:
        """Résout le fichier de politique depuis la racine du dépôt."""
        racine = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return os.path.join(racine, FICHIER_POLITIQUE)

    def _charger(self) -> Dict[str, Any]:
        """Lit la politique ; retombe sur celle de secours en le journalisant."""
        try:
            import yaml

            with open(self._chemin, "r", encoding="utf-8") as fichier:
                politique = yaml.safe_load(fichier) or {}
        except (OSError, ValueError) as erreur:
            # Une politique illisible ne doit pas empêcher de router — mais elle
            # ne doit pas non plus disparaître en silence.
            logger.warning(
                "Politique de routage illisible (%s) : la politique de secours "
                "s'applique, et le choix des modèles sera moins fin.", erreur,
            )
            return dict(POLITIQUE_DE_SECOURS)

        for cle, valeur in POLITIQUE_DE_SECOURS.items():
            politique.setdefault(cle, valeur)
        return politique

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def task_types(self) -> List[str]:
        """Retourne les types de tâche déclarés."""
        return sorted(self._politique.get("tasks", {}))

    def families(self) -> Dict[str, Any]:
        """Retourne les familles déclarées et leurs motifs de reconnaissance."""
        return dict(self._politique.get("families", {}))

    def family_of(self, model_name: str) -> Optional[str]:
        """
        Retourne la famille d'un modèle, ou None s'il n'appartient à aucune.

        Args:
            model_name: Nom du modèle, tel que le fournisseur l'annonce.
        """
        nom = (model_name or "").lower()
        for famille, definition in self.families().items():
            for motif in definition.get("matches", []):
                if motif.lower() in nom:
                    return famille
        return None

    def decide(
        self,
        task_requirements: Optional[Dict[str, Any]] = None,
        available_models: Optional[List[str]] = None,
    ) -> RouteDecision:
        """
        Décide des exigences d'une tâche et de la famille visée.

        Args:
            task_requirements: `task_type`, `complexity`, `max_cost`,
                `requires_vision`, `min_context_window`, `required_capabilities`.
                Les valeurs explicites de l'appelant priment sur la politique :
                il en sait plus qu'un fichier de configuration sur sa requête.
            available_models: Noms des modèles réellement servis, pour dire si la
                famille visée est joignable.

        Returns:
            La décision, avec sa raison — jamais un choix muet.
        """
        demande = dict(task_requirements or {})
        task_type = demande.get("task_type")
        tache = self._politique.get("tasks", {}).get(task_type)

        if tache is None:
            base = dict(self._politique.get("default", {}))
            motif = (
                f"Type de tâche « {task_type} » inconnu de la politique : règle par défaut."
                if task_type else "Aucun type de tâche déclaré : règle par défaut."
            )
        else:
            base = dict(tache)
            motif = f"Politique « {task_type} »."

        famille = base.pop("family", None)
        exigences = self._fusionner(base, demande)

        famille_disponible = True
        if famille and available_models is not None:
            famille_disponible = any(
                self.family_of(nom) == famille for nom in available_models
            )
            if not famille_disponible:
                # Dire que la famille manque, plutôt que router en silence vers
                # autre chose : un appelant qui croit parler à SamP et parle à un
                # modèle générique tire de fausses conclusions de la réponse.
                motif += (
                    f" Aucun modèle de la famille « {famille} » n'est servi "
                    f"(VOLET 33) : repli sur le meilleur modèle disponible."
                )

        return RouteDecision(
            task_type=task_type,
            family=famille,
            requirements=exigences,
            family_available=famille_disponible,
            reason=motif,
        )

    def _fusionner(self, base: Dict[str, Any], demande: Dict[str, Any]) -> Dict[str, Any]:
        """Combine la politique, la complexité et ce que l'appelant a exigé."""
        exigences: Dict[str, Any] = {
            "min_context_window": base.get("min_context_window", 4096),
            "requires_vision": bool(base.get("requires_vision", False)),
            "requires_function_calling": bool(base.get("requires_function_calling", False)),
            "preferred_features": list(base.get("preferred_features", [])),
            "prefer_cheapest": bool(base.get("prefer_cheapest", False)),
            "max_input_cost": base.get("max_input_cost"),
            # Motifs de noms qui l'emportent **à compétence égale**. Vide quand
            # le rôle n'en déclare aucun : le comportement précédent tient.
            "role_preferences": list(
                self._politique.get("role_preferences", {}).get(demande.get("task_type"), [])
            ),
        }

        # La complexité relève le contexte minimal, elle ne l'abaisse jamais :
        # une tâche annoncée complexe ne doit pas se retrouver sur un modèle plus
        # court que ce que son type exige.
        complexite = demande.get("complexity")
        if complexite:
            contexte = self._politique.get("complexity_context", {}).get(complexite)
            if contexte:
                exigences["min_context_window"] = max(exigences["min_context_window"], contexte)

        # L'appelant sait des choses que la configuration ignore : ses valeurs
        # explicites l'emportent.
        if demande.get("min_context_window"):
            exigences["min_context_window"] = max(
                exigences["min_context_window"], int(demande["min_context_window"])
            )
        if demande.get("requires_vision"):
            exigences["requires_vision"] = True
        if demande.get("requires_function_calling"):
            exigences["requires_function_calling"] = True
        if demande.get("required_capabilities"):
            exigences["preferred_features"] = list(demande["required_capabilities"])

        # `max_cost` était accepté puis ignoré. Il devient un plafond réel.
        plafond = demande.get("max_cost", demande.get("max_input_cost"))
        if plafond is not None:
            exigences["max_input_cost"] = (
                float(plafond) if exigences["max_input_cost"] is None
                else min(float(plafond), float(exigences["max_input_cost"]))
            )

        return exigences


_politique_partagee: Optional[RoutingPolicy] = None


def shared_policy() -> RoutingPolicy:
    """
    Retourne la politique partagée par la plateforme.

    Une politique par appelant relirait le fichier à chaque requête et, pire,
    laisserait deux composants router différemment le jour où l'un rechargerait
    et l'autre non.
    """
    global _politique_partagee
    if _politique_partagee is None:
        _politique_partagee = RoutingPolicy()
    return _politique_partagee


def reset_policy() -> None:
    """Oublie la politique partagée ; le prochain appel la relira."""
    global _politique_partagee
    _politique_partagee = None
