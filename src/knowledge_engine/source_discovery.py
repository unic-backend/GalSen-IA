"""
Proposer des sources pour un manque — et ne rien décider (VOLET 35, chapitre 07).

Le chapitre 06 mesure ce que la base ne couvre pas. Celui-ci répond à la
question suivante : **qui, parmi les sources déjà reconnues, ferait autorité
sur ce manque ?**

## La règle qui tient tout le chapitre

Les candidats viennent **du registre**, jamais d'une recherche libre sur le web.
« Cherche sur internet et apprends » est la façon la plus rapide de remplir une
base de connaissances d'absurdités confiantes, et ce dépôt a déjà écrit pourquoi
il refuse d'y aller.

Une source hors registre peut être **proposée** — jamais utilisée. Ajouter une
autorité est une décision humaine, et c'est cette décision qui donne au registre
sa valeur : sans elle, le registre ne serait qu'une liste de favoris.

## Ce que ce module ne fait pas

Il ne visite aucune URL, ne télécharge rien, n'ingère rien. La collecte est le
chapitre 08 — sous approbation, licence vérifiée, `robots.txt` respecté. Ici,
tout tient dans une liste de noms et de raisons.
"""

from typing import Any, Dict, List, Optional

from .scope import GLOBAL, KnowledgeScope, parse_subject
from .source_registry import load_registry


def propose_for_gap(
    subject: Any,
    scope: Any = GLOBAL,
    registre: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Propose les sources du registre qui feraient autorité sur ce manque.

    Args:
        subject: Le sujet du manque.
        scope: La portée du manque — `global` ou `country:xx`.
        registre: Registre déjà chargé.

    Returns:
        Les candidats, chacun avec la raison de sa présence, et
        `decides_nothing: True`. Aucun candidat n'est une réponse en soi : c'est
        `what_would_settle_it` qui dit alors quoi faire.
    """
    registre = registre or load_registry()
    sujet = parse_subject(subject)
    portee = str(KnowledgeScope.parse(scope))

    candidats: List[Dict[str, Any]] = []
    for entree in registre["sources"]:
        couvre_le_sujet = sujet.value in entree["subjects"]
        # Une source mondiale sert une question locale en arrière-plan ; une
        # source nationale d'un autre pays, non. La portée est comparée, jamais
        # supposée compatible.
        portee_compatible = entree["scope"] == portee or entree["scope"] == GLOBAL
        if not couvre_le_sujet or not portee_compatible:
            continue
        candidats.append({
            "name": entree["name"],
            "domain": entree["domain"],
            "base_url": entree["base_url"],
            "category": entree["category"].value,
            "scope": entree["scope"],
            "match": "scope+subject" if entree["scope"] == portee else "subject, global scope",
        })

    # Les sources de la portée demandée d'abord : pour un manque sénégalais,
    # l'ANSD passe avant la FAO, même si les deux couvrent le sujet.
    candidats.sort(key=lambda candidat: (candidat["scope"] != portee, candidat["name"]))

    return {
        "subject": sujet.value,
        "scope": portee,
        "candidates": candidats,
        # Ce champ n'est pas décoratif : c'est le contrat de l'agent qui lira ce
        # rapport. Proposer et décider sont deux actes différents, et celui-ci
        # ne fait que le premier.
        "decides_nothing": True,
        "source_of_candidates": "registry",
        "what_would_settle_it": (
            [] if candidats else [
                f"Aucune source inscrite ne couvre « {sujet.value} » en portée "
                f"« {portee} ». Inscrire l'institution compétente dans "
                "`corpus/sources/senegal.yaml` — c'est une décision humaine, et "
                "c'est elle qui donne sa valeur au registre.",
                "Aucune recherche libre sur le web n'est faite ni proposée : une "
                "source hors registre peut être proposée par une personne, jamais "
                "utilisée par la plateforme.",
            ]
        ),
    }


def propose_for_gaps(gaps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Propose des sources pour chaque manque mesuré au chapitre 06.

    L'entrée vient de `detect_gaps()` : la proposition suit donc toujours une
    mesure, jamais une intuition sur ce qui manquerait.
    """
    registre = load_registry()
    return [
        propose_for_gap(manque.get("subject"), manque.get("scope", GLOBAL), registre)
        for manque in gaps
    ]
