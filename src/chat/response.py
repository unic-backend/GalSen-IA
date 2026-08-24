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
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..agent.context import executer_coroutine
from ..reasoning import REPRISES_PAR_DEFAUT, deliberer

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
    #: Ce que la boucle de délibération a fait : tentatives, constats, motif
    #: d'arrêt. `None` quand aucune génération n'a eu lieu — un champ vide et un
    #: champ absent ne disent pas la même chose, et « aucune délibération » ne
    #: doit pas se lire comme « délibération sans constat ».
    deliberation: Optional[Dict[str, Any]] = None


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

# Un échange de courtoisie n'affirme rien sur le monde. C'est le seul endroit
# où une phrase écrite d'avance est honnête : « bonjour » ne prétend pas être
# une connaissance, et `generated` reste faux pour que personne ne s'y trompe.
#
# Les motifs suivent les mots-clés de l'intention `conversation` du planner —
# une seule liste ferait autorité, deux finiraient par diverger, donc celle-ci
# ne fait que répondre à ce que celle-là reconnaît.
_COURTOISIES = (
    (("merci", "merci beaucoup", "thanks", "thank you"),
     "Avec plaisir. Autre chose ?"),
    (("au revoir", "a bientot", "à bientôt", "bye", "adieu"),
     "À bientôt !"),
    (("nanga def", "na nga def"),
     "Maangi fi rekk, jërëjëf ! Comment puis-je t'aider ?"),
    (("bonjour", "bonsoir", "salut", "hello", "ca va", "ça va"),
     "Bonjour ! Comment puis-je t'aider ?"),
)


def reponse_de_courtoisie(message: str) -> Optional[str]:
    """
    Rend une réponse d'accueil quand le message n'est qu'un échange de politesse.

    Retourne `None` dès que le message dit autre chose — auquel cas la
    rédaction reprend son cours normal. **Ne jamais deviner ici** : une phrase
    toute faite servie à une vraie question serait pire que la latence qu'elle
    économise.
    """
    reduit = re.sub(r"[^\w\s'-]", " ", (message or "").lower())
    reduit = " ".join(reduit.split())
    if not reduit:
        return None

    for motifs, reponse in _COURTOISIES:
        for motif in motifs:
            if motif not in reduit:
                continue
            # Ce qui reste une fois la politesse retirée décide. « bonjour »
            # est un salut ; « bonjour, explique-moi la relativité » est une
            # question qui commence poliment, et lui répondre « bonjour ! »
            # serait pire que la milliseconde économisée.
            #
            # **Dans le doute, on génère.** Un raccourci manqué coûte une
            # latence ; un raccourci qui se trompe coûte une mauvaise réponse.
            reste = " ".join(reduit.replace(motif, " ").split())
            if len(reste.split()) <= 1:
                return reponse
    return None


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

    def __init__(self, model_manager: Any, reprises_max: Optional[int] = None) -> None:
        """
        Args:
            model_manager: un `ModelManagerImpl`, ou tout objet exposant
                `generate_text_with_fallback(prompt, task_requirements, **kw)`.
            reprises_max: Nombre de reprises autorisées quand la critique trouve
                un défaut bloquant. `GALSEN_CHAT_MAX_RETRIES` sinon, et
                `REPRISES_PAR_DEFAUT` en dernier recours. **Zéro n'éteint pas la
                critique** : les constats sont toujours rendus, seule la reprise
                cesse — un exploitant qui veut la latency minimale garde ainsi
                l'information.
        """
        self._modeles = model_manager
        self._reprises_max = (
            reprises_max if reprises_max is not None else _reprises_configurees()
        )

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

    def _generer(self, invite: str, exigences: Dict[str, Any]) -> Tuple[str, Optional[str]]:
        """
        Appelle le moteur et rend le texte **avec le nom du modèle**, si connu.

        Deux méthodes existent sur le moteur : `generate_text_with_source`, qui
        nomme le modèle ayant abouti, et `generate_text_with_fallback`, qui rend
        une chaîne seule. La première est préférée ; la seconde reste le repli,
        parce que tout objet exposant `generate_text_with_fallback` doit
        continuer de fonctionner ici — c'est le contrat annoncé au constructeur,
        et plusieurs doubles de test s'y tiennent.

        Args:
            invite: L'invite complète
            exigences: Exigences de sélection de modèle

        Returns:
            Le couple `(texte, nom du modèle ou None)`. `None` signifie que le
            moteur ne sait pas le dire — jamais qu'on l'a deviné.
        """
        avec_source = getattr(self._modeles, "generate_text_with_source", None)
        if callable(avec_source):
            resultat = executer_coroutine(
                avec_source(prompt=invite, task_requirements=exigences)
            )
            # Un double de test peut rendre une chaîne seule : l'accepter évite
            # qu'un objet conforme au contrat annoncé au constructeur casse ici.
            if isinstance(resultat, tuple):
                return resultat[0], resultat[1]
            return resultat, None

        texte = executer_coroutine(
            self._modeles.generate_text_with_fallback(
                prompt=invite, task_requirements=exigences
            )
        )
        return texte, None

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

        # Un échange de politesse ne mobilise pas un modèle. Le planificateur a
        # déjà écarté toute recherche pour l'intention `conversation` — mesuré
        # le 2026-08-24, l'orchestration d'un « bonjour » coûte alors 1,7 ms —
        # et le seul coût restant serait la génération.
        #
        # La première version de ce court-circuit rendait
        # `composer_sans_modele()`, qui sans preuve répond « je n'ai pas de quoi
        # répondre à cette question » : une salutation recevait un refus. Ce qui
        # manquait n'était pas le raccourci, c'était une chose à dire.
        #
        # `reponse_de_courtoisie()` rend `None` dès que le message dit autre
        # chose, et la rédaction reprend alors son cours. Un raccourci qui se
        # trompe coûte plus cher que la latence qu'il économise.
        if _est_une_conversation(contexte) and not contexte.evidence:
            courtoisie = reponse_de_courtoisie(contexte.message)
            if courtoisie:
                return ReponseFinale(
                    answer=courtoisie,
                    generated=False,
                    elapsed_seconds=round(time.perf_counter() - debut, 3),
                )

        invite = construire_invite(contexte)

        modele: Optional[str] = None
        exigences = self.exigences(contexte)

        def produire(consigne: str) -> Tuple[str, Optional[str]]:
            """Une passe de génération, la consigne de reprise ajoutée à l'invite."""
            return self._generer(
                f"{invite}\n\n{consigne}" if consigne else invite, exigences
            )

        try:
            deliberation = deliberer(
                produire,
                evidence=contexte.evidence,
                grounding_status=contexte.grounding_status,
                reprises_max=self._reprises_max,
            )
            texte, modele = deliberation.texte, deliberation.modele
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
        # Trace symétrique de celle des pannes : sans elle, un exploitant voit
        # les échecs et jamais les réussites, ce qui donne d'une plateforme qui
        # marche l'image d'une plateforme qui tombe.
        #
        # Aucune métrique n'est inventée ici (§20). La durée, le modèle et
        # l'issue voyagent aussi dans `ChatResponse` ; ce qui n'existe pas —
        # un compteur dans `/metrics`, un événement d'audit dédié — n'est pas
        # fabriqué pour faire nombre.
        _JOURNAL.info(
            "Réponse générée en %.3f s par %s (%d reprise(s), arrêt : %s)",
            duree, modele or "modèle non nommé",
            deliberation.reprises, deliberation.arret,
        )
        return ReponseFinale(
            answer=texte,
            generated=True,
            model_used=modele,
            elapsed_seconds=duree,
            deliberation=deliberation.to_dict(),
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


def _est_une_conversation(contexte: ContexteReponse) -> bool:
    """Vrai quand le planificateur a classé la demande comme un simple échange."""
    valeur = contexte.axe("task_type")
    if isinstance(valeur, list):
        return "conversation" in valeur
    return valeur == "conversation"


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


def _reprises_configurees() -> int:
    """
    Lit `GALSEN_CHAT_MAX_RETRIES`, ou rend le défaut.

    Une valeur illisible ou négative rend le défaut **et le journalise** : une
    variable mal écrite qui désactive silencieusement les reprises serait
    découverte le jour où une réponse fausse est servie.

    Returns:
        Le nombre de reprises autorisées.
    """
    brut = os.environ.get("GALSEN_CHAT_MAX_RETRIES")
    if brut is None:
        return REPRISES_PAR_DEFAUT
    try:
        valeur = int(brut)
    except ValueError:
        _JOURNAL.warning(
            "GALSEN_CHAT_MAX_RETRIES=%r n'est pas un entier : %d reprise(s) par défaut.",
            brut, REPRISES_PAR_DEFAUT,
        )
        return REPRISES_PAR_DEFAUT
    if valeur < 0:
        _JOURNAL.warning(
            "GALSEN_CHAT_MAX_RETRIES=%d est négatif : %d reprise(s) par défaut.",
            valeur, REPRISES_PAR_DEFAUT,
        )
        return REPRISES_PAR_DEFAUT
    return valeur


def _detail_complet(erreur: Exception) -> str:
    """La cause entière, pour le journal et le diagnostic."""
    message = str(erreur).strip()
    return f"{type(erreur).__name__}: {message}" if message else type(erreur).__name__


def _modele_utilise(gestionnaire: Any) -> Optional[str]:
    """
    Rend `None`. **Conservée pour ce qu'elle documente, pas pour ce qu'elle fait.**

    Cette fonction devinait — elle rendait le premier modèle actif du moteur —
    et sa docstring prétendait le contraire. Le premier de la liste n'est pas le
    bon dans le seul cas où la question est intéressante : quand le repli a
    servi. Elle a donc été réduite à `None` le 2026-08-23, avec cette note :
    *« ce qui trancherait, c'est que le moteur rende le modèle retenu avec le
    texte »*.

    C'est fait (2026-08-24) : `ModelManagerImpl.generate_text_with_source()`
    rend le couple, et `RedacteurConversation._generer()` l'utilise. Plus
    personne n'appelle cette fonction dans le chemin de rédaction.

    Args:
        gestionnaire: Ignoré. Le paramètre reste pour ne pas casser un appelant.

    Returns:
        `None`, toujours. Un nom deviné vaut moins que pas de nom : il se lit
        comme une mesure.
    """
    return None
