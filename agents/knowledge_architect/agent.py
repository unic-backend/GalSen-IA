"""
Knowledge Architect Agent for GalSen IA (VOLET 36, ch. G).

Today a human writes every manifest entry by hand: title, scope, subject, source
category, language. That work is the reason corpora do not get ingested — not
the ingestion, which already works.

This agent **proposes** that entry. It never writes it.

## Why proposing and confirming stay separate

The classification decides where knowledge holds and what it is about, and
`senegal` refuses to answer a national subject without a national source. An
agent that could set `scope: country:sn` on its own would be deciding, alone,
which questions the platform is allowed to answer with which documents. The
proposal is returned as `DRAFT`, for a person to confirm.

## What it does when it does not know

It proposes `unspecified` **and says so**, in `uncertain`. A guessed subject is
worse than an absent one: the document becomes findable under a label it does
not deserve, and nobody looks for it under the right one.

Entities are proposed the same way — as candidates, never stored. The entity
store refuses anything without a source, and a name spotted in a sentence is
not a source (`src/knowledge_engine/entities.py`).
"""

import os
import re
from typing import Any, Dict, List

from src.agent.base_agent import BaseAgent
from src.agent.context import AgentContext
from src.agent.legacy import run_agent_module
from src.knowledge_engine.markers import est_senegalais, sujets_reperes
from src.knowledge_engine.scope import KnowledgeSubject

#: Nombre de caractères lus pour classer. Un document se classe sur son début et
#: son titre ; lire cinquante pages pour proposer un sujet coûterait sans rien
#: ajouter à une proposition qu'un humain relira de toute façon.
CARACTERES_LUS = 4000

#: Ce que l'agent ne décidera jamais, quelle que soit la demande.
NON_DECIDE = (
    "l'application de la proposition : elle appartient à une personne",
    "la catégorie de source : elle dépend de qui publie, pas du texte",
    "l'enregistrement d'entités : une entité sans source est refusée par le magasin",
)

#: Titre déduit d'un nom de fichier : séparateurs remplacés, extension retirée.
_SEPARATEURS = re.compile(r"[-_]+")


class KnowledgeArchitectAgent(BaseAgent):
    """Agent qui propose une entrée de manifeste, et ne l'applique jamais."""

    agent_id = "knowledge_architect"
    required_engines = ("knowledge",)

    def perform(self, context: AgentContext) -> Dict[str, Any]:
        """
        Propose le classement d'un document pour un manifeste.

        Args:
            context: Contexte d'exécution. `options["path"]` désigne le
                document ; à défaut, le texte de la demande est classé.

        Returns:
            Une entrée de manifeste **proposée**, en `DRAFT`, avec ce qui reste
            incertain et ce que l'agent refuse de décider.
        """
        chemin = str(context.options.get("path") or "").strip()
        texte, lecture = self._texte(chemin, context)

        if not texte.strip():
            return {
                "status": "nothing_to_classify",
                "reason": lecture,
                "proposal": None,
                "not_decided": list(NON_DECIDE),
            }

        sujets = sujets_reperes(texte)
        senegalais = est_senegalais(texte)
        incertain = []

        if not sujets:
            # Deviner ici rendrait le document trouvable sous une étiquette
            # qu'il ne mérite pas, et introuvable sous la bonne.
            incertain.append("subject : aucun marqueur reconnu, proposé « unspecified »")
        elif len(sujets) > 1:
            incertain.append(
                f"subject : plusieurs sujets repérés ({', '.join(sujets)}), le premier est proposé"
            )
        if not senegalais:
            incertain.append(
                "scope : aucun marqueur sénégalais, proposé « global » — un document "
                "sénégalais non déclaré ne doit pas être rangé au Sénégal par charité, "
                "et l'inverse non plus"
            )

        proposition = {
            "path": chemin or None,
            "title": self._titre(chemin, texte),
            "scope": "country:sn" if senegalais else "global",
            "subject": sujets[0] if sujets else KnowledgeSubject.UNSPECIFIED.value,
            # Ni catégorie de source ni langue devinées : la première dépend de
            # qui publie, la seconde n'a aucun détecteur dans le dépôt (ch. B).
            "source_category": None,
            "language": None,
            "status": "DRAFT",
        }

        return {
            "status": "proposed",
            "proposal": proposition,
            "requires_human_confirmation": True,
            "method": "keywords",
            "uncertain": incertain,
            "candidate_entities": self._entites_candidates(texte),
            "read": lecture,
            "not_decided": list(NON_DECIDE),
            "note": (
                "Proposition à relire, à compléter (`source_category`, `language`) "
                "et à coller dans un manifeste — voir `docs/knowledge/README.md`. "
                "Rien n'a été écrit."
            ),
        }

    @staticmethod
    def _texte(chemin: str, context: AgentContext) -> tuple:
        """Retourne le texte à classer et la façon dont il a été obtenu."""
        if not chemin:
            return context.request_text(), "texte de la demande"
        if not os.path.isfile(chemin):
            return "", f"Fichier introuvable : {chemin}"
        try:
            with open(chemin, "r", encoding="utf-8", errors="replace") as fichier:
                return fichier.read(CARACTERES_LUS), f"{chemin} ({CARACTERES_LUS} caractères)"
        except OSError as erreur:
            return "", f"Lecture impossible : {erreur}"

    @staticmethod
    def _titre(chemin: str, texte: str) -> str:
        """
        Propose un titre : premier titre Markdown, sinon nom de fichier.

        Le titre apparaîtra dans les citations. Il est proposé, pas imposé —
        c'est la première chose qu'un humain corrigera.
        """
        for ligne in texte.splitlines():
            ligne = ligne.strip()
            if ligne.startswith("#"):
                return ligne.lstrip("#").strip()
        if chemin:
            nom = os.path.splitext(os.path.basename(chemin))[0]
            return _SEPARATEURS.sub(" ", nom).strip()
        return ""

    @staticmethod
    def _entites_candidates(texte: str) -> List[Dict[str, Any]]:
        """
        Repère des noms propres, et les rend comme **candidats**.

        Une suite de mots capitalisés n'est pas une entité : c'est une chaîne
        de caractères qui y ressemble. Le magasin d'entités refuse tout ce qui
        n'a pas de source, et « vu dans un document » n'en est pas une tant que
        personne n'a confirmé de quoi il s'agit.
        """
        candidats: List[str] = []
        for trouve in re.findall(r"\b[A-ZÉÈÀÂÎÔÛ][\wÉÈÀÂÎÔÛéèàâîôûç]+(?:\s+[A-ZÉÈÀÂÎÔÛ][\wéèàâîôûç]+)*", texte):
            nom = trouve.strip()
            if len(nom) > 3 and nom not in candidats:
                candidats.append(nom)
        return [
            {"label": nom, "type": None, "confirmed": False}
            for nom in candidats[:10]
        ]


def execute(input_data: Any) -> Dict[str, Any]:
    """
    Point d'entrée historique de l'agent.

    Args:
        input_data: Document ou texte à classer.

    Returns:
        Résultat de l'agent au format standard.
    """
    return run_agent_module(KnowledgeArchitectAgent, input_data)
