"""
La dérogation cadrée à la souveraineté (ADR-018, option B, acceptée).

ADR-014 refuse les fournisseurs tiers : en mode souverain ils ne sont **pas
inscrits**, donc aucun chemin ne peut en choisir un. Le brief demandait la
bascule vers le cloud ; le propriétaire a tranché l'option **B** — souverain par
défaut, avec une exception nommée, configurée et tracée.

Ce module est cette exception, et il est écrit pour être plus strict que ce
qu'il remplace.

## Ce qui existait avant, et pourquoi c'était pire

Un seul levier : `GALSEN_SOVEREIGN_MODE=false`. **Global** — il ouvre tout, y
compris les requêtes portant les mémoires, les fichiers et la connaissance de
quelqu'un. **Binaire** — aucun « pour cette tâche seulement ». Et cadré par une
phrase d'ADR, pas par un mécanisme : *une phrase dans un document n'est pas une
frontière.*

## Les trois règles de ce fichier

1. **La dérogation est une configuration, jamais un paramètre de requête.**
   Un appelant ne peut pas demander le cloud. ADR-016 a mesuré ce défaut la
   semaine dernière : `CloudFileItem.provider` était un champ rempli par
   l'appelant, enregistré comme un fait et rendu par `/cloud/stats` comme s'il
   décrivait la réalité. Le même défaut ici enregistrerait une **croyance** sur
   l'endroit où une requête est partie.

2. **Trois catégories sont refusées quoi qu'en dise la configuration** — voir
   `REFUS_INCONDITIONNELS`. Ce sont celles où l'envoi est précisément ce que le
   projet existe pour empêcher.

3. **Une dérogation invisible ne se distingue pas d'une fuite.** Chaque appel
   dérogé porte le nom de la dérogation qui l'a permis, et `report()` alimente
   `/health`.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

VARIABLE = "GALSEN_SOVEREIGN_DEROGATIONS"

#: Ce qui ne sort pas, quelle que soit la configuration (ADR-018 §2).
#: Chaque entrée porte sa raison : un refus sans raison finit par être levé par
#: quelqu'un qui ne sait pas ce qu'il lève.
REFUS_INCONDITIONNELS = {
    "user_content": (
        "la requête porte les mémoires, fichiers ou connaissances d'une "
        "personne — ADR-010 en fait sa propriété, et les envoyer dehors est "
        "exactement ce que ce projet existe pour empêcher"
    ),
    "screen_capture": (
        "une image de l'écran de quelqu'un est la charge la plus révélatrice "
        "que la plateforme manipulera jamais (VOLET 34, ch. 05)"
    ),
    "training_export": (
        "l'export de données d'entraînement passe par une décision humaine "
        "(VOLET 33) ; un chemin cloud la contournerait"
    ),
}


@dataclass(frozen=True)
class Derogation:
    """
    Une exception déclarée par l'opérateur.

    Attributes:
        task_type: Type de tâche concerné — et lui seul.
        provider_id: Fournisseur autorisé pour ce type de tâche.
    """

    task_type: str
    provider_id: str

    def to_dict(self) -> Dict[str, str]:
        """Sérialise la dérogation."""
        return {"task_type": self.task_type, "provider_id": self.provider_id}

    def name(self) -> str:
        """Nom porté par l'audit : il doit suffire à retrouver la ligne de config."""
        return f"{self.task_type}->{self.provider_id}"


def declared_derogations(declaration: Optional[str] = None) -> List[Derogation]:
    """
    Lit les dérogations déclarées.

    Args:
        declaration: Déclaration `type:fournisseur[,type:fournisseur]` ;
            `GALSEN_SOVEREIGN_DEROGATIONS` sinon.

    Returns:
        Les dérogations déclarées. **Vide par défaut**, et une entrée malformée
        est écartée avec une erreur au journal plutôt que devinée : deviner un
        type de tâche ouvrirait une porte que personne n'a demandée.
    """
    brut = declaration if declaration is not None else os.getenv(VARIABLE, "")
    derogations: List[Derogation] = []
    for entree in brut.split(","):
        entree = entree.strip()
        if not entree:
            continue
        if ":" not in entree:
            logger.error("Dérogation « %s » ignorée : forme attendue type:fournisseur.", entree)
            continue
        type_tache, fournisseur = (partie.strip() for partie in entree.split(":", 1))
        if not type_tache or not fournisseur:
            logger.error("Dérogation « %s » ignorée : type ou fournisseur vide.", entree)
            continue
        if type_tache in REFUS_INCONDITIONNELS:
            # Déclarer l'indéclarable est une erreur d'opérateur, pas une
            # autorisation : elle est écartée **et** dite.
            logger.error(
                "Dérogation « %s » refusée : %s (ADR-018 §2).",
                entree, REFUS_INCONDITIONNELS[type_tache],
            )
            continue
        derogations.append(Derogation(task_type=type_tache, provider_id=fournisseur))
    return derogations


def allowed_providers(derogations: Optional[List[Derogation]] = None) -> List[str]:
    """Retourne les fournisseurs tiers qu'au moins une dérogation autorise."""
    effectives = derogations if derogations is not None else declared_derogations()
    return sorted({derogation.provider_id for derogation in effectives})


def allow(
    task_type: str,
    provider_id: str,
    carries_user_content: bool = False,
    derogations: Optional[List[Derogation]] = None,
) -> Tuple[bool, str]:
    """
    Décide si un appel tiers est permis, et dit pourquoi dans les deux cas.

    Args:
        task_type: Type de la tâche à traiter.
        provider_id: Fournisseur envisagé.
        carries_user_content: La requête porte-t-elle le contenu d'une personne.
            **L'appelant le déclare, et un doute vaut vrai** : se tromper dans ce
            sens coûte une réponse plus lente ; l'inverse coûte des données.
        derogations: Dérogations en vigueur ; celles de la configuration sinon.

    Returns:
        `(autorisé, raison)`. La raison est rendue à l'audit et à la réponse.
    """
    if carries_user_content:
        return False, f"Refus inconditionnel : {REFUS_INCONDITIONNELS['user_content']}."
    if task_type in REFUS_INCONDITIONNELS:
        return False, f"Refus inconditionnel : {REFUS_INCONDITIONNELS[task_type]}."

    effectives = derogations if derogations is not None else declared_derogations()
    for derogation in effectives:
        if derogation.task_type == task_type and derogation.provider_id == provider_id:
            return True, f"Dérogation « {derogation.name()} » (ADR-018)."

    return False, (
        f"Aucune dérogation ne couvre « {task_type} » vers « {provider_id} ». "
        f"Souverain par défaut (ADR-014) ; l'exception se déclare dans {VARIABLE}."
    )


def report(derogations: Optional[List[Derogation]] = None) -> Dict[str, object]:
    """
    Décrit les dérogations actives, pour `/health`.

    Une dérogation que personne ne peut voir ne se distingue pas d'une fuite.
    """
    effectives = derogations if derogations is not None else declared_derogations()
    return {
        "variable": VARIABLE,
        "count": len(effectives),
        "derogations": [derogation.to_dict() for derogation in effectives],
        "unconditional_refusals": sorted(REFUS_INCONDITIONNELS),
        "caller_can_request": False,
        "reference": "ADR-018",
    }
