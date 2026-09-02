"""
Générer, critiquer, recommencer — et savoir s'arrêter.

## Ce que cette boucle change réellement

Avant elle, `/chat` générait **une fois** et rendait le résultat. Un calcul faux,
une affirmation contredite par un constat rassemblé, une certitude affichée sans
rien derrière : tout passait, parce que rien ne relisait.

Cette boucle relit. Elle ne rend pas la réponse plus intelligente — elle rend
possible qu'une réponse fausse soit reprise avant d'être servie. C'est une
différence de procédé, pas un drapeau `reasoning=true`.

## Ce qu'elle refuse de faire

- **Elle ne demande jamais au modèle s'il avait raison.** Les critiques sont
  déterministes (`critics.py`), pour la raison qu'`agents/verifier/agent.py`
  écrit déjà : la confiance d'un modèle en lui-même n'est pas une vérification.
- **Elle ne tourne pas indéfiniment.** Trois arrêts, et le rapport dit lequel a
  servi : plus de constat bloquant, budget d'itérations épuisé, délai dépassé.
- **Elle ne cache pas un échec.** Quand le budget s'épuise sur une réponse
  encore critiquée, la dernière tentative est rendue **avec ses constats**. Une
  boucle qui rend silencieusement une réponse qu'elle sait douteuse vaut moins
  que pas de boucle : elle ajoute une garantie qui n'existe pas.

## Le coût, et pourquoi il est borné

Chaque itération est un appel de modèle de plus. Le budget par défaut autorise
**une seule reprise** : c'est la reprise qui corrige un calcul ou retire une
certitude, et les suivantes rapportent beaucoup moins pour le même prix. Un
appelant qui veut davantage le demande explicitement.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .critics import Constat, critiquer

logger = logging.getLogger(__name__)

#: Pourquoi la boucle s'est arrêtée. Rendu tel quel : un appelant qui lit
#: « budget épuisé » n'agit pas comme un appelant qui lit « plus rien à
#: reprendre ».
VERIFIEE = "verified"
BUDGET_EPUISE = "iteration_budget_exhausted"
DELAI_DEPASSE = "deadline_exceeded"
GENERATION_IMPOSSIBLE = "generation_failed"

#: Une seule reprise par défaut. Voir la note de coût dans l'en-tête.
REPRISES_PAR_DEFAUT = 1

#: Délai total, reprises comprises. Un modèle local lent doit pouvoir finir sa
#: première tentative : ce plafond protège l'appelant, il ne hache pas le travail.
DELAI_PAR_DEFAUT_SECONDES = 90.0


@dataclass
class Tentative:
    """Une passe de la boucle : ce qui a été produit, et ce qu'on y a trouvé."""

    numero: int
    texte: str
    modele: Optional[str] = None
    constats: List[Constat] = field(default_factory=list)
    duree_secondes: float = 0.0

    @property
    def bloquants(self) -> List[Constat]:
        """Les constats qui justifieraient une autre tentative."""
        return [c for c in self.constats if c.bloquant]

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la tentative pour la trace."""
        return {
            "attempt": self.numero,
            "model_used": self.modele,
            "findings": [c.to_dict() for c in self.constats],
            "elapsed_seconds": round(self.duree_secondes, 3),
        }


@dataclass
class Deliberation:
    """
    Le résultat de la boucle : la réponse retenue et tout ce qui y a mené.

    Attributes:
        texte: La réponse finale.
        modele: Le modèle qui l'a produite, si le moteur sait le dire.
        tentatives: Chaque passe, dans l'ordre.
        arret: Pourquoi la boucle s'est arrêtée.
        constats_restants: Ce qui n'a pas pu être corrigé. **Non vide n'est pas
            un échec de la boucle** : c'est ce qu'elle a détecté et signalé.
    """

    texte: str
    modele: Optional[str] = None
    tentatives: List[Tentative] = field(default_factory=list)
    arret: str = VERIFIEE
    constats_restants: List[Constat] = field(default_factory=list)

    @property
    def reprises(self) -> int:
        """Combien de fois la boucle a redemandé une réponse."""
        return max(0, len(self.tentatives) - 1)

    @property
    def corrigee(self) -> bool:
        """Vrai si une reprise a réellement fait disparaître un constat bloquant."""
        if len(self.tentatives) < 2:
            return False
        return bool(self.tentatives[0].bloquants) and not self.constats_restants

    def to_dict(self) -> Dict[str, Any]:
        """
        Sérialise la délibération.

        Rien n'est arrondi ni résumé au point de perdre le motif d'arrêt : c'est
        la seule information qui distingue « vérifiée » de « on a manqué de
        temps ».
        """
        return {
            "attempts": [t.to_dict() for t in self.tentatives],
            "retries": self.reprises,
            "stop_reason": self.arret,
            "corrected": self.corrigee,
            "remaining_findings": [c.to_dict() for c in self.constats_restants],
        }


#: Un générateur rend le couple `(texte, nom du modèle ou None)` à partir d'une
#: consigne de reprise — vide à la première passe.
Generateur = Callable[[str], Tuple[str, Optional[str]]]


def deliberer(
    generer: Generateur,
    evidence: Optional[Sequence[Dict[str, Any]]] = None,
    grounding_status: str = "",
    reprises_max: int = REPRISES_PAR_DEFAUT,
    delai_secondes: float = DELAI_PAR_DEFAUT_SECONDES,
) -> Deliberation:
    """
    Génère, critique, et redemande tant que c'est utile et permis.

    Args:
        generer: Appelé avec la consigne de reprise (chaîne vide la première
            fois) et rendant `(texte, modèle)`.
        evidence: Les constats rassemblés, transmis aux critiques.
        grounding_status: L'ancrage calculé avant la génération.
        reprises_max: Nombre maximal de **reprises**, donc `reprises_max + 1`
            générations au plus. Zéro désactive la boucle sans désactiver la
            critique : la réponse est rendue avec ses constats.
        delai_secondes: Plafond de durée totale. Vérifié **avant** chaque
            reprise, jamais au milieu d'une génération — interrompre un modèle
            en cours rendrait un texte tronqué, ce qui est pire que tard.

    Returns:
        La délibération. `texte` est toujours renseigné dès qu'une génération a
        abouti, même quand des constats subsistent.

    Raises:
        Rien. Une panne de génération à la **première** passe est propagée à
        l'appelant, parce qu'il n'y a alors aucune réponse à rendre ; une panne
        à une reprise est absorbée et la tentative précédente est conservée.
    """
    debut = time.perf_counter()
    tentatives: List[Tentative] = []
    consigne = ""

    for numero in range(reprises_max + 1):
        depart = time.perf_counter()
        try:
            texte, modele = generer(consigne)
        except Exception:
            if not tentatives:
                # Rien à rendre : c'est l'affaire de l'appelant, pas la nôtre.
                raise
            # Une reprise ratée laisse la tentative précédente en place. Perdre
            # une réponse obtenue en essayant de l'améliorer serait une
            # régression provoquée par le correcteur lui-même.
            logger.warning("Reprise %d impossible : la tentative précédente est conservée.",
                           numero + 1)
            derniere = tentatives[-1]
            return Deliberation(
                texte=derniere.texte,
                modele=derniere.modele,
                tentatives=tentatives,
                arret=GENERATION_IMPOSSIBLE,
                constats_restants=derniere.bloquants,
            )

        texte = (texte or "").strip()
        tentative = Tentative(
            numero=numero + 1,
            texte=texte,
            modele=modele,
            constats=critiquer(texte, evidence=evidence, grounding_status=grounding_status),
            duree_secondes=time.perf_counter() - depart,
        )
        tentatives.append(tentative)

        bloquants = tentative.bloquants
        if not bloquants:
            return Deliberation(
                texte=texte, modele=modele, tentatives=tentatives, arret=VERIFIEE,
            )

        if numero >= reprises_max:
            return Deliberation(
                texte=texte, modele=modele, tentatives=tentatives,
                arret=BUDGET_EPUISE, constats_restants=bloquants,
            )

        if time.perf_counter() - debut >= delai_secondes:
            return Deliberation(
                texte=texte, modele=modele, tentatives=tentatives,
                arret=DELAI_DEPASSE, constats_restants=bloquants,
            )

        consigne = consigne_de_reprise(bloquants)

    # Inatteignable : la boucle rend dans tous ses cas. Gardé pour que la
    # fonction ait un type de retour vrai quoi qu'il arrive.
    derniere = tentatives[-1]
    return Deliberation(
        texte=derniere.texte, modele=derniere.modele, tentatives=tentatives,
        arret=BUDGET_EPUISE, constats_restants=derniere.bloquants,
    )


def consigne_de_reprise(constats: Sequence[Constat]) -> str:
    """
    Écrit ce que la prochaine tentative doit faire autrement.

    La consigne ne redonne **pas** la réponse précédente au modèle : elle lui
    dit ce qui n'allait pas. Lui renvoyer son propre texte l'invite à le
    reformuler plutôt qu'à le refaire, et c'est ainsi qu'une erreur survit à sa
    correction.

    Args:
        constats: Les constats bloquants de la tentative précédente.

    Returns:
        Un bloc de consignes en anglais — comme toute invite système
        (`.claude/rules/prompts.md`) — ou une chaîne vide s'il n'y a rien à dire.
    """
    consignes = [c.consigne for c in constats if c.consigne]
    if not consignes:
        return ""
    lignes = "\n".join(f"- {c}" for c in consignes)
    return (
        "Your previous answer was checked and did not pass. "
        "Write a new answer that fixes exactly these points:\n"
        f"{lignes}\n"
        "Do not mention this correction, the check, or your previous attempt. "
        "Write the answer the user should have received the first time."
    )
