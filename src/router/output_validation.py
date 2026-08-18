"""
Le contrat de sortie d'un agent (VOLET 06, ch. 02, étape 6).

L'étape « valider les sorties » était déclarée par le manuel et n'existait nulle
part : rien ne se tenait entre le dictionnaire rendu par un agent et la réponse
agrégée. Trois conséquences, toutes mesurées sur le dépôt avant ce module :

1. **Un résultat sans statut, ou avec un statut non déclaré, disparaissait.**
   `aggregate()` filtrait sur `success`, `error` et `requires_approval` ; tout
   le reste n'entrait dans aucune des trois listes, sortait de `agent_results`
   et laissait le statut global à `success`. Un agent avait tourné, produit
   quelque chose, et la réponse ne le mentionnait pas.
2. **`skipped` est pourtant un statut déclaré** (`AgentResult.STATUS_SKIPPED`,
   et `RetryManager` le traite comme terminal). L'agrégateur l'effaçait en
   rendant `success` ; le routeur, lui, le comptait dans `failed_agents` et
   rendait `partial_success`. **La même réponse portait les deux.**
3. **Un résultat qui n'est pas un dictionnaire levait une `AttributeError`**
   au milieu de l'agrégation, convertie plus haut en échec de toute la requête :
   un agent mal écrit faisait tomber les agents qui avaient réussi avant lui.

Ce module tient donc deux choses, et rien d'autre :

- **le contrat** — ce qu'un résultat d'agent doit être, et ce qu'il devient
  quand il ne l'est pas ;
- **la règle de statut unique** — `overall_status()`, appelée par l'agrégateur
  *et* par le routeur. Deux implémentations d'un même contrat qui divergent est
  le défaut que ce dépôt a déjà trouvé quatre fois ; ici les deux divergeaient
  dans une même réponse.

Un résultat invalide n'est **pas** écarté et n'est **pas** deviné : il devient
une erreur qui nomme la clause violée. Écarter reviendrait à faire disparaître
un agent de la réponse ; deviner reviendrait à fabriquer un résultat plausible,
ce que `.claude/rules/verification.md` interdit explicitement.
"""

from typing import Any, Dict, List, Optional

# Les quatre statuts qu'un agent peut rendre. Ce sont ceux de `AgentResult` ;
# la constante est ici parce que le routeur ne doit pas dépendre de la couche
# agent pour valider ce qu'elle lui envoie.
STATUS_SUCCESS = "success"
STATUS_ERROR = "error"
STATUS_SKIPPED = "skipped"
STATUS_REQUIRES_APPROVAL = "requires_approval"

AGENT_STATUSES = frozenset({
    STATUS_SUCCESS, STATUS_ERROR, STATUS_SKIPPED, STATUS_REQUIRES_APPROVAL,
})

# Statuts que l'agrégation peut rendre pour l'ensemble d'une requête.
AGGREGATE_STATUSES = frozenset({
    STATUS_SUCCESS, STATUS_ERROR, STATUS_REQUIRES_APPROVAL, "partial_success",
})


def violations(result: Any) -> List[str]:
    """
    Énumère ce qui, dans un résultat d'agent, rompt le contrat.

    Args:
        result: Ce qu'un agent a rendu, quel qu'en soit le type.

    Returns:
        La liste des clauses violées, vide si le résultat est conforme. Les
        violations sont **toutes** rendues, pas seulement la première : corriger
        un agent une clause à la fois demanderait autant d'exécutions.
    """
    if not isinstance(result, dict):
        return [f"le résultat n'est pas un dictionnaire mais un {type(result).__name__}"]

    manquements: List[str] = []

    agent = result.get("agent")
    if not isinstance(agent, str) or not agent.strip():
        # Sans le nom de l'agent, un échec ne peut être imputé à personne :
        # l'analyse des défaillances (VOLET 18, ch. 06) demande de le nommer.
        manquements.append("le champ « agent » est absent ou vide")

    statut = result.get("status")
    if statut is None:
        manquements.append("le champ « status » est absent")
    elif statut not in AGENT_STATUSES:
        manquements.append(
            f"statut « {statut} » non déclaré "
            f"(attendus : {', '.join(sorted(AGENT_STATUSES))})"
        )

    if statut == STATUS_ERROR and not result.get("error"):
        # Une erreur sans message est une erreur qu'on ne peut pas corriger.
        manquements.append("statut « error » sans message dans « error »")

    if statut == STATUS_REQUIRES_APPROVAL and not result.get("approval_request_id"):
        # Une action suspendue sans identifiant de demande ne peut plus être
        # approuvée par personne : elle attendrait indéfiniment (ADR-006).
        manquements.append(
            "statut « requires_approval » sans « approval_request_id »"
        )

    return manquements


def is_valid(result: Any) -> bool:
    """Indique si un résultat d'agent respecte le contrat."""
    return not violations(result)


def validated(result: Any, agent_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Rend un résultat conforme au contrat, ou l'erreur qui dit pourquoi il ne l'est pas.

    C'est le point de passage unique : appliqué à la frontière où la sortie d'un
    agent entre dans la plateforme, il garantit qu'aucun code en aval n'a à se
    défendre contre une forme inattendue.

    Args:
        result: Ce que l'agent a rendu.
        agent_id: Identifiant attendu, utilisé pour imputer la violation quand
            le résultat lui-même ne porte pas de nom exploitable.

    Returns:
        Le résultat inchangé s'il est conforme ; sinon un résultat d'erreur qui
        **nomme les clauses violées**. Le résultat d'origine est conservé sous
        `invalid_output` : il est souvent la seule trace de ce que l'agent a
        voulu dire, et l'effacer rendrait le défaut indébogable.
    """
    manquements = violations(result)
    if not manquements:
        return result

    nom = agent_id
    if not nom and isinstance(result, dict):
        candidat = result.get("agent")
        nom = candidat if isinstance(candidat, str) and candidat.strip() else None

    return {
        "agent": nom or "unknown",
        "status": STATUS_ERROR,
        "result": None,
        "error": "Sortie d'agent non conforme : " + " ; ".join(manquements),
        "invalid_output": _tracable(result),
    }


def _tracable(result: Any) -> Any:
    """
    Rend une forme conservable du résultat rejeté.

    Un résultat non sérialisable ne doit pas empêcher la réponse d'être rendue :
    le défaut à signaler est celui de l'agent, pas celui de la sérialisation.
    """
    if isinstance(result, (dict, list, str, int, float, bool)) or result is None:
        return result
    return repr(result)[:500]


def counts(results: List[Any]) -> Dict[str, int]:
    """
    Compte les résultats par statut, en une seule lecture.

    Le routeur comptait ses échecs par soustraction — `total - succès -
    approbations` — ce qui rangeait `skipped` parmi les échecs sans que rien ne
    le dise. Compter explicitement rend ce cas visible au lieu de le déduire.

    Args:
        results: Résultats d'agents, conformes ou non.

    Returns:
        Un compte par statut déclaré, plus `invalid` pour ceux qui rompent le
        contrat, plus `total`.
    """
    comptes = {statut: 0 for statut in AGENT_STATUSES}
    comptes["invalid"] = 0

    for resultat in results:
        if not is_valid(resultat):
            comptes["invalid"] += 1
            continue
        comptes[resultat["status"]] += 1

    comptes["total"] = len(results)
    return comptes


def overall_status(results: List[Any]) -> str:
    """
    Détermine le statut d'une requête à partir des résultats de ses agents.

    **Règle unique**, appelée par l'agrégateur et par le routeur. Ils la
    calculaient chacun de leur côté et rendaient deux statuts différents dans
    une même réponse dès qu'un agent était `skipped`.

    L'ordre des cas est l'ordre de gravité :

    1. **aucun agent exécuté → `error`.** Rendre `success` sur une requête où
       rien n'a tourné est le faux positif le plus coûteux de la plateforme :
       il suffit que tous les agents soient désactivés pour que chaque requête
       soit déclarée servie sans que personne ne l'ait traitée ;
    2. une erreur (ou une sortie non conforme) → `partial_success` s'il reste un
       succès, `error` sinon ;
    3. une approbation en attente → `requires_approval` : la requête est
       suspendue, pas terminée (ADR-006) ;
    4. sinon `success` — les agents `skipped` ont décidé de ne pas agir, ce qui
       est une décision, pas une panne.

    Args:
        results: Résultats d'agents.

    Returns:
        L'un des statuts de `AGGREGATE_STATUSES`.
    """
    if not results:
        return STATUS_ERROR

    comptes = counts(results)
    en_echec = comptes[STATUS_ERROR] + comptes["invalid"]

    if en_echec:
        return "partial_success" if comptes[STATUS_SUCCESS] else STATUS_ERROR
    if comptes[STATUS_REQUIRES_APPROVAL]:
        return STATUS_REQUIRES_APPROVAL
    return STATUS_SUCCESS


EMPTY_PIPELINE_ERROR = (
    "Aucun agent n'a été exécuté : la requête n'a pas été traitée. "
    "Vérifier le pipeline du workflow et les agents activés."
)
