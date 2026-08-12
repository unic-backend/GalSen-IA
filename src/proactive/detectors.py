"""
Les détecteurs : ce qui est réellement lu avant d'être suggéré.

Chaque détecteur lit un état que la plateforme mesure déjà — le graphe
d'imports (ch. 10), la posture de sécurité (ch. 13), le portillon (ADR-006), le
signal utilisateur (VOLET 33), les racines déclarées (ch. 07) — et rend zéro ou
plusieurs observations.

**Un détecteur silencieux est le cas normal.** Aucun ne cherche « quelque chose
à dire » : sans constat, il rend une liste vide, et le scan le rapporte comme
tel plutôt que de combler.

Un détecteur qui échoue est rapporté en panne, jamais confondu avec un
détecteur qui n'a rien trouvé : « rien à signaler » et « je n'ai pas pu
regarder » sont deux phrases différentes, et les confondre est la façon la plus
simple de rater une dégradation.
"""

import logging
import time
from typing import Any, Callable, Dict, List

from .observations import Observation, observation

logger = logging.getLogger(__name__)

#: Ancienneté d'une demande d'approbation au-delà de laquelle elle est signalée.
#: Une décision oubliée bloque un agent en silence, et c'est le seul cas où la
#: plateforme sait que quelqu'un attend.
ATTENTE_TROP_LONGUE_SECONDES = 24 * 3600

#: Part de fichiers de code qu'aucun test n'atteint au-delà de laquelle on le
#: signale. À 15 %, on ne réveille personne pour trois fichiers.
SEUIL_NON_TESTE = 0.15


def modele_indisponible() -> List[Observation]:
    """
    Signale que la plateforme n'a aucun modèle capable de répondre.

    C'est le critère C1, et la suggestion la plus rentable du dépôt : elle coûte
    une commande à l'opérateur et débloque toutes les capacités de génération.
    """
    from src.model_engine.model_manager import ModelManagerImpl

    moteur = ModelManagerImpl()
    if moteur.select_model_for_task({}) is not None:
        return []

    return [observation(
        source="model_availability",
        finding="Aucun modèle ne peut répondre : les capacités de génération sont hors service.",
        evidence={
            "selectable_model": None,
            "sovereignty": moteur.sovereignty_report().get("providers", []),
        },
        suggested_action=(
            "Démarrer un modèle local : `ollama serve` puis `ollama pull` d'un "
            "modèle à contexte ≥ 8192 (critère C1)."
        ),
        priority="blocking",
    )]


def approbations_en_attente(maintenant: float = None) -> List[Observation]:
    """Signale les décisions humaines qui bloquent un travail depuis trop longtemps."""
    from src.integration.engine_registry import get_shared_registry

    portillon = get_shared_registry().try_get("approval")
    if portillon is None:
        return []

    instant = maintenant if maintenant is not None else time.time()
    attendues = [
        demande for demande in portillon.list_pending(limit=100)
        if instant - getattr(demande, "created_at", instant) > ATTENTE_TROP_LONGUE_SECONDES
    ]
    if not attendues:
        return []

    return [observation(
        source="pending_approvals",
        finding=f"{len(attendues)} action(s) attendent une décision depuis plus de 24 h.",
        evidence={
            "count": len(attendues),
            "oldest_hours": round(
                (instant - min(d.created_at for d in attendues)) / 3600, 1
            ),
            "actions": [demande.action for demande in attendues[:5]],
        },
        suggested_action=(
            "Trancher ces demandes : un agent les attend, et rien ne se passera "
            "avant. `/approval/pending` les liste."
        ),
        decided_by="owner",
        priority="blocking",
    )]


def code_sans_test() -> List[Observation]:
    """
    Signale la part du code qu'aucun test n'atteint (ch. 10).

    La mesure vient du graphe d'imports, pas d'une convention de nom : c'est la
    différence entre 22 % et 87 % de couverture apparente.
    """
    from src.agent.repo_graph import RepoGraph

    resume = RepoGraph().build().summary()
    total = resume["code_files"] or 0
    hors_portee = resume["code_unreached_by_tests"]
    if not total or hors_portee / total < SEUIL_NON_TESTE:
        return []

    return [observation(
        source="untested_code",
        finding=(
            f"{hors_portee} fichiers de code sur {total} ne sont atteints par "
            "aucun test."
        ),
        evidence={"unreached": hors_portee, "code_files": total,
                  "ratio": round(hors_portee / total, 3)},
        suggested_action=(
            "Une modification dans ces fichiers ne peut pas être vérifiée. "
            "`RepoGraph().describe(chemin)` dit lesquels."
        ),
    )]


def cycles_d_import() -> List[Observation]:
    """Signale un cycle d'imports **bloquant** — il casse au chargement."""
    from src.agent.repo_graph import RepoGraph

    cycles = RepoGraph().build().cycles(blocking=True)
    if not cycles:
        return []

    return [observation(
        source="import_cycles",
        finding=f"{len(cycles)} cycle(s) d'imports exécutés au chargement.",
        evidence={"cycles": cycles[:3], "count": len(cycles)},
        suggested_action=(
            "Un cycle au chargement lève `ImportError` au premier des modules "
            "importé. Différer l'un des imports ou couper la dépendance."
        ),
        priority="blocking",
    )]


def failles_de_posture() -> List[Observation]:
    """
    Signale les points que la posture de sécurité ne garantit pas (ch. 13).

    Une seule observation pour toutes les failles : en produire une par ligne
    remplirait la liste de sept entrées permanentes, et la sixième ferait
    ignorer la première.
    """
    from src.security.posture import posture

    mesure = posture()
    if not mesure["gaps"]:
        return []

    return [observation(
        source="security_posture",
        finding=f"{mesure['gap_count']} point(s) de sécurité non garanti(s).",
        evidence={"gaps": mesure["gaps"][:5], "count": mesure["gap_count"]},
        suggested_action=(
            "Lire `/security/posture` : chaque section dit ce qu'elle ne "
            "garantit pas et ce qui la refermerait."
        ),
        priority="for_information",
    )]


def qualite_en_baisse() -> List[Observation]:
    """
    Signale une dégradation **mesurée** de la qualité perçue (ch. 12).

    Silencieux tant que le volume ne permet pas de conclure : `measure()` rend
    `insufficient_data`, et transformer cela en alerte serait exactement le
    bruit que ce module refuse.
    """
    from src.training.improvement import measure

    rapport = measure()
    if rapport.get("status") != "measured":
        return []

    degrade = {
        nom: ecart for nom, ecart in rapport["deltas"].items()
        if ecart.get("direction") == "worse"
    }
    if not degrade:
        return []

    return [observation(
        source="quality_trend",
        finding=f"{len(degrade)} indicateur(s) de qualité en baisse sur la période.",
        evidence={"worse": degrade, "window_days": rapport["window_days"]},
        suggested_action=(
            "Regarder les corrections récentes : elles disent ce que les "
            "réponses ont raté."
        ),
    )]


def fichiers_a_ranger() -> List[Observation]:
    """
    Signale des fichiers en vrac dans une racine inscriptible (ch. 07 et 11).

    L'organisateur **propose** ; il ne range rien sans décision, et cette
    observation ne change pas cela — elle dit qu'un plan existe.
    """
    from agents.organizer.agent import FileOrganizerAgent
    from src.agent.context import AgentContext

    plan = FileOrganizerAgent().perform(
        AgentContext(request="rangement proactif", agent_id="organizer")
    )
    propositions = plan.get("proposals") or []
    if plan.get("status") != "planned" or len(propositions) < 5:
        return []

    return [observation(
        source="unorganised_files",
        finding=f"{len(propositions)} fichiers pourraient être rangés par catégorie.",
        evidence={
            "proposals": len(propositions),
            "roots": plan.get("roots", []),
            "categories": plan.get("categories", []),
        },
        suggested_action=(
            "Le plan est prêt et **rien n'a bougé** : il demande une "
            "approbation, et chaque déplacement reste annulable."
        ),
        decided_by="owner",
        priority="for_information",
    )]


#: Détecteurs exécutés par un scan, dans cet ordre.
DETECTEURS: Dict[str, Callable[[], List[Observation]]] = {
    "model_availability": modele_indisponible,
    "pending_approvals": approbations_en_attente,
    "import_cycles": cycles_d_import,
    "untested_code": code_sans_test,
    "quality_trend": qualite_en_baisse,
    "unorganised_files": fichiers_a_ranger,
    "security_posture": failles_de_posture,
}


def run_detector(nom: str) -> Dict[str, Any]:
    """
    Exécute un détecteur et rend ses observations, ou sa panne.

    « Rien à signaler » et « je n'ai pas pu regarder » sont deux réponses
    distinctes, et les confondre est la façon la plus simple de rater une
    dégradation.
    """
    detecteur = DETECTEURS.get(nom)
    if detecteur is None:
        return {"detector": nom, "status": "unknown", "observations": []}
    try:
        trouvees = detecteur()
    except Exception as erreur:  # noqa: BLE001 - une panne de détecteur se rapporte
        logger.warning("Détecteur « %s » en panne : %s", nom, erreur)
        return {"detector": nom, "status": "failed", "reason": str(erreur),
                "observations": []}
    return {"detector": nom, "status": "ok", "observations": trouvees}
