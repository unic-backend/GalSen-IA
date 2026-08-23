"""
Composer une réponse finale à partir de ce que l'orchestration a trouvé.

Ce module ne cherche rien, n'appelle aucun outil et n'ouvre aucune connexion.
Il reçoit un contexte déjà constitué et le transforme en texte — ce qui le rend
testable sans modèle et sans réseau, et c'est délibéré : sur cette machine
aucun modèle n'est enregistré, et un composant qu'on ne peut pas éprouver ici
serait un composant qu'on ne peut pas éprouver du tout.

Deux fonctions, deux responsabilités qui ne doivent pas se mélanger :

- `construire_invite()` prépare ce qu'on demande au modèle ;
- `composer_sans_modele()` répond quand aucun modèle ne peut le faire.

La seconde existe parce que **l'absence de modèle ne doit jamais produire une
réponse inventée**. Elle rend ce que les agents ont réellement rapporté, ou dit
qu'il n'y a rien — jamais autre chose.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..agent.context import executer_coroutine

# Les trois issues d'ancrage de la plateforme. Reprises telles quelles : cette
# couche ne les calcule pas, elle les transporte.
GROUNDED = "GROUNDED"
UNGROUNDED = "UNGROUNDED"
NOT_CHECKED = "NOT_CHECKED"

_JOURNAL = logging.getLogger(__name__)


@dataclass
class ContexteReponse:
    """
    Tout ce dont la rédaction a besoin, et rien de plus.

    Ce que ce contexte ne porte **pas** est aussi important que ce qu'il porte :
    ni le plan du planner, ni sa liste de tâches, ni les durées d'exécution.
    Ce sont des rouages, pas des éléments de réponse (§8 du brief).
    """

    message: str
    history: List[Dict[str, str]] = field(default_factory=list)
    axes: Dict[str, Any] = field(default_factory=dict)
    # Chaque constat porte `content`, `source`, `scope` et `verified`, à la
    # forme rendue par `agents/researcher/agent.py`.
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    # Les refus que les agents ont écrits eux-mêmes : « la base est vide sur ce
    # sujet », les lacunes du chercheur. Ce sont des faits sur la recherche.
    agent_notes: List[str] = field(default_factory=list)
    grounding_status: str = NOT_CHECKED

    def axe(self, nom: str) -> Any:
        """Retourne la valeur d'un axe du planner, ou `None` s'il est absent."""
        entree = (self.axes or {}).get(nom)
        if isinstance(entree, dict):
            return entree.get("value")
        return entree

    @property
    def constats_verifies(self) -> List[Dict[str, Any]]:
        """Les constats que le chercheur lui-même marque comme vérifiés."""
        return [c for c in self.evidence if isinstance(c, dict) and c.get("verified")]


@dataclass
class ReponseFinale:
    """
    Le résultat de la rédaction.

    `generated` est le champ qui tient tout le reste honnête : il est vrai
    **seulement** si un modèle a produit le texte. Sans lui, un refus composé
    par la plateforme serait indiscernable d'une réponse du modèle, et c'est
    exactement le mensonge que ce projet refuse partout ailleurs.
    """

    answer: str
    generated: bool = False
    model_used: Optional[str] = None
    # Court, stable, sans détail d'infrastructure : c'est ce qu'un appelant de
    # l'API peut recevoir.
    failure_reason: Optional[str] = None
    # La cause réelle, entière. **Journalisée, jamais rendue par la route.**
    # Le §14 demande de garder l'information de panne à l'intérieur ; la perdre
    # pour la cacher serait la mauvaise moitié de la consigne.
    failure_detail: Optional[str] = None
    elapsed_seconds: float = 0.0


# --------------------------------------------------------------------------
# L'invite
# --------------------------------------------------------------------------

# Écrite en anglais : `.claude/rules/prompts.md` l'impose pour toute invite
# système. La consigne demande explicitement de répondre dans la langue de
# l'utilisateur, qui est portée par l'axe `language`.
_CONSIGNE = """You are GalSen IA, a general-purpose AI assistant.

Answer the user's question directly, in natural conversational language.

Rules you must follow:
- Answer in the user's language.
- Use the evidence provided below when it is relevant. When it is not, answer
  from your own knowledge.
- Never invent a source, a citation, a tool result, or a search that did not
  happen. If the context says nothing was found, say so plainly.
- Evidence marked UNVERIFIED comes from outside the platform. You may use it,
  but say that it is unverified. Never present it as established fact.
- Evidence marked VERIFIED comes from the platform's own sourced knowledge.
- If you do not know something and the context does not contain it, say you do
  not know. Do not fill the gap.
- Never mention the internal machinery of this platform: its planner, its
  researcher, its agents, its workflows. The user asked a question, not for a
  build log.
- Keep the thread of the conversation when earlier turns are provided.

You are a global assistant. Senegal is one of your specialities, not your
boundary. Use Senegalese context only when the question calls for it."""


def _rendre_constats(contexte: ContexteReponse) -> str:
    """
    Rend les constats sous une forme que le modèle peut citer sans se tromper.

    Chaque ligne porte son origine et son statut de vérification. Les fondre en
    un paragraphe continu les ferait lire comme la parole de la plateforme,
    alors qu'ils viennent d'ailleurs.
    """
    lignes: List[str] = []
    for constat in contexte.evidence:
        if not isinstance(constat, dict):
            continue
        contenu = str(constat.get("content") or "").strip()
        if not contenu:
            continue
        source = str(constat.get("source") or "unknown source")
        marque = "VERIFIED" if constat.get("verified") else "UNVERIFIED"
        portee = constat.get("scope")
        etendue = f", scope={portee}" if portee else ""
        lignes.append(f"- [{marque}{etendue}] {contenu}\n  (source: {source})")
    return "\n".join(lignes)


def _rendre_historique(contexte: ContexteReponse, tours: int = 6) -> str:
    """Rend les derniers tours, pour que la conversation garde son fil (§15)."""
    recents = [t for t in (contexte.history or []) if isinstance(t, dict)][-tours:]
    lignes = []
    for tour in recents:
        role = "User" if tour.get("role") == "user" else "Assistant"
        contenu = str(tour.get("content") or "").strip()
        if contenu:
            lignes.append(f"{role}: {contenu}")
    return "\n".join(lignes)


def construire_invite(contexte: ContexteReponse) -> str:
    """
    Assemble l'invite envoyée au modèle.

    Ce qui entre est décidé ici, et volontairement restreint : le message, les
    tours récents, les constats avec leur origine, et les refus que les agents
    ont écrits. Déverser tout le résultat d'orchestration dans l'invite
    reviendrait à demander au modèle de trier des rouages (§8).
    """
    morceaux = [_CONSIGNE]

    historique = _rendre_historique(contexte)
    if historique:
        morceaux.append("## Earlier in this conversation\n\n" + historique)

    constats = _rendre_constats(contexte)
    if constats:
        morceaux.append("## Evidence gathered for this question\n\n" + constats)

    notes = [str(n).strip() for n in (contexte.agent_notes or []) if str(n).strip()]
    if notes:
        # Ces phrases viennent des agents eux-mêmes. Elles disent ce qui a été
        # cherché et ce qui manque — une information, pas un aveu d'échec.
        morceaux.append(
            "## What the search reported\n\n"
            + "\n".join(f"- {n}" for n in notes)
        )

    if not constats and not notes:
        morceaux.append(
            "## Evidence gathered for this question\n\n"
            "No search was performed for this message. Answer from your own "
            "knowledge, and say so if the answer needs sources you do not have."
        )

    # `grounding_status` entrait dans le contexte et n'en sortait jamais —
    # un champ que personne ne lit est une promesse que personne ne tient.
    # Il sert ici à ce que le §12 demande : le modèle doit savoir quand il
    # répond de sa propre connaissance plutôt que de sources.
    if contexte.grounding_status == GROUNDED:
        morceaux.append(
            "## Grounding\n\nThe evidence above is sourced platform knowledge. "
            "Rely on it, and do not add claims it does not support."
        )
    else:
        morceaux.append(
            "## Grounding\n\nNothing here is verified platform knowledge. If you "
            "answer from your own knowledge, say so plainly. Never present this "
            "answer as sourced."
        )

    morceaux.append("## The user's message\n\n" + contexte.message.strip())
    return "\n\n".join(morceaux)


# --------------------------------------------------------------------------
# Le plancher honnête : répondre sans modèle
# --------------------------------------------------------------------------

def composer_sans_modele(contexte: ContexteReponse) -> str:
    """
    Compose une réponse quand aucun modèle ne peut rédiger.

    C'est le comportement que la plateforme avait déjà, et il est conservé :
    rendre ce que les agents ont trouvé, ou dire qu'il n'y a rien. Ce qui
    change, c'est qu'il cesse d'être le **seul** comportement possible.

    Rien n'est inventé ici, jamais. Une machine sans modèle ne devient pas
    bavarde parce que quelqu'un a posé une question.
    """
    if contexte.evidence:
        lignes = []
        sans_texte = 0
        for constat in contexte.evidence:
            if not isinstance(constat, dict):
                sans_texte += 1
                continue
            contenu = str(constat.get("content") or "").strip()
            if not contenu:
                sans_texte += 1
                continue
            source = str(constat.get("source") or "source inconnue")
            marque = "" if constat.get("verified") else " — non vérifié"
            lignes.append(f"- {contenu}\n  ({source}{marque})")

        if lignes:
            texte = (
                "Voici ce qui a été trouvé, avec l'origine de chaque élément :"
                "\n\n" + "\n".join(lignes)
            )
            if sans_texte:
                texte += (
                    f"\n\n{sans_texte} autre(s) élément(s) sans texte exploitable."
                )
            return texte

    notes = [str(n).strip() for n in (contexte.agent_notes or []) if str(n).strip()]
    if notes:
        return (
            "Je n'ai rien trouvé de fiable pour répondre.\n\n"
            + "\n".join(f"- {n}" for n in notes)
        )

    return (
        "Je n'ai pas de quoi répondre à cette question, et aucun modèle n'est "
        "disponible pour le faire depuis mes propres connaissances.\n\n"
        "Ce qui trancherait : démarrer un fournisseur de modèle, ou alimenter "
        "la base de connaissance sur ce sujet."
    )


# --------------------------------------------------------------------------
# La rédaction elle-même
# --------------------------------------------------------------------------

class RedacteurConversation:
    """
    Transforme un contexte en réponse, en passant par le moteur de modèles.

    Le gestionnaire de modèles est **injecté**, jamais construit ici. Deux
    raisons, et la seconde est la plus importante : la plateforme en partage
    déjà une instance (`_moteur_partage("model", ModelManagerImpl)`), et un
    composant qui construit son propre fournisseur est un composant qu'on ne
    peut pas éprouver sans fournisseur réel.

    ADR-014 tient ici : cette classe n'ouvre aucune connexion, ne connaît
    aucune URL et ne nomme aucun fournisseur. Elle appelle une méthode, et le
    moteur décide du reste — y compris du repli entre modèles.
    """

    def __init__(self, model_manager: Any) -> None:
        """
        Args:
            model_manager: un `ModelManagerImpl`, ou tout objet exposant
                `generate_text_with_fallback(prompt, task_requirements, **kw)`.
        """
        self._modeles = model_manager

    def exigences(self, contexte: ContexteReponse) -> Dict[str, Any]:
        """
        Traduit les axes du planner en exigences de sélection de modèle.

        `task_type` et `complexity` sont exactement les clés que lit
        `ModelSelector.select_model()`. Elles sont déjà calculées par le
        planner : les recalculer ici créerait une seconde classification, ce
        que le brief interdit — et deux classifications finissent par ne plus
        dire la même chose.

        À comparer avec `/model/generate`, qui passe `task_requirements={}`
        avec un commentaire « à enrichir » : ici elles sont renseignées.
        """
        type_tache = contexte.axe("task_type")
        if isinstance(type_tache, list):
            type_tache = type_tache[0] if type_tache else None
        exigences: Dict[str, Any] = {}
        if type_tache:
            exigences["task_type"] = type_tache
        complexite = contexte.axe("complexity")
        if complexite:
            exigences["complexity"] = complexite
        return exigences

    def rediger(self, contexte: ContexteReponse) -> ReponseFinale:
        """
        Rend la réponse finale, générée si un modèle répond, composée sinon.

        Aucune exception ne remonte : une panne de génération est une
        information à porter dans `failure_reason`, pas une erreur à faire
        éclater dans la route. Mais elle n'est jamais transformée en réponse
        plausible — `generated` reste faux et le texte rendu est celui des
        agents.
        """
        debut = time.perf_counter()
                # Une conversation simple ne nécessite pas de génération par modèle.
        # Le Planner a déjà déterminé qu'aucun agent n'est requis.
        type_tache = contexte.axe("task_type")
        if type_tache == "conversation" or (
            isinstance(type_tache, list) and "conversation" in type_tache
        ):
            return ReponseFinale(
                answer=composer_sans_modele(contexte),
                generated=False,
                failure_reason=None,
                failure_detail=None,
                elapsed_seconds=round(time.perf_counter() - debut, 3),
            )
        invite = construire_invite(contexte)

        try:
            texte = executer_coroutine(
                self._modeles.generate_text_with_fallback(
                    prompt=invite,
                    task_requirements=self.exigences(contexte),
                )
            )
        except Exception as erreur:  # noqa: BLE001 — toute panne est une donnée
            detail = _detail_complet(erreur)
            _JOURNAL.warning("Génération de réponse impossible : %s", detail)
            return ReponseFinale(
                answer=composer_sans_modele(contexte),
                generated=False,
                failure_reason=_classer_panne(erreur),
                failure_detail=detail,
                elapsed_seconds=round(time.perf_counter() - debut, 3),
            )

        texte = (texte or "").strip()
        if not texte:
            # Un modèle qui répond le vide n'a pas répondu. Le dire, plutôt que
            # de rendre une bulle vide à l'utilisateur.
            return ReponseFinale(
                answer=composer_sans_modele(contexte),
                generated=False,
                failure_reason=TEXTE_VIDE,
                failure_detail=TEXTE_VIDE,
                elapsed_seconds=round(time.perf_counter() - debut, 3),
            )

        duree = round(time.perf_counter() - debut, 3)
        modele = _modele_utilise(self._modeles)
        # Trace symétrique de celle des pannes : sans elle, un exploitant voit
        # les échecs et jamais les réussites, ce qui donne d'une plateforme qui
        # marche l'image d'une plateforme qui tombe.
        #
        # Aucune métrique n'est inventée ici (§20). La durée, le modèle et
        # l'issue voyagent aussi dans `ChatResponse` ; ce qui n'existe pas —
        # un compteur dans `/metrics`, un événement d'audit dédié — n'est pas
        # fabriqué pour faire nombre.
        _JOURNAL.info(
            "Réponse générée en %.3f s par %s", duree, modele or "modèle non nommé",
        )
        return ReponseFinale(
            answer=texte,
            generated=True,
            model_used=modele,
            elapsed_seconds=duree,
        )


# Les motifs rendus à l'appelant. Courts, stables, et **sans rien qui décrive
# l'infrastructure** : mesuré le 2026-08-23, le message brut du moteur contenait
# `http://localhost:11434`, c'est-à-dire un hôte et un port livrés à quiconque
# appelle l'API. Le §14 l'interdit.
#
# Une valeur énumérée vaut mieux qu'une prose de fournisseur pour une autre
# raison : elle ne change pas quand le fournisseur change, donc un client peut
# s'y fier.
AUCUN_FOURNISSEUR = "aucun fournisseur de modèle n'est disponible"
GENERATION_ECHOUEE = "la génération a échoué"
TEXTE_VIDE = "le modèle a rendu un texte vide"


def _classer_panne(erreur: Exception) -> str:
    """
    Rend un motif court et sûr pour une panne de génération.

    L'opérateur, lui, a besoin du détail : il est conservé dans
    `ReponseFinale.failure_detail` et journalisé. `/health` porte déjà l'état
    des fournisseurs, avec le geste à faire — c'est là qu'il a sa place, pas
    dans la réponse à un message de conversation.
    """
    if type(erreur).__name__ == "ProviderUnavailableError":
        return AUCUN_FOURNISSEUR
    return GENERATION_ECHOUEE


def _detail_complet(erreur: Exception) -> str:
    """La cause entière, pour le journal et le diagnostic."""
    message = str(erreur).strip()
    return f"{type(erreur).__name__}: {message}" if message else type(erreur).__name__


def _modele_utilise(gestionnaire: Any) -> Optional[str]:
    """
    Nomme le modèle qui a répondu — c'est-à-dire : rend `None`.

    **Cette fonction devinait, et sa docstring prétendait le contraire.** Elle
    rendait le premier modèle actif du moteur, alors que
    `generate_text_with_fallback()` essaie les candidats dans l'ordre et rend
    une chaîne : *lequel* a répondu n'est nulle part dans sa valeur de retour.
    Le premier de la liste n'est donc pas le bon dans le seul cas où la question
    est intéressante — quand le repli a servi.

    Trouvé le 2026-08-23 en relisant mon propre diff. Un nom deviné vaut moins
    que pas de nom : il se lit comme une mesure.

    Ce qui trancherait : que le moteur rende le modèle retenu avec le texte.
    Le jour où il le fera, c'est ici que ça se branche.
    """
    return None
