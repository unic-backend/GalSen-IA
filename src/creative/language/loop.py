"""
Apprendre une langue par l'usage, sans entraîner quoi que ce soit (C14, §27–§33).

## La phrase que ce module existe pour tenir

§31, mot pour mot : *« apprendre des utilisateurs » ne veut PAS dire entraîner
silencieusement un modèle de fondation sur des conversations.*

C'est la distinction que tout le monde confond, et elle n'est pas subtile :

| Acquisition de connaissance | Entraînement de modèle |
|---|---|
| Une entrée s'ajoute à une base | Des poids changent |
| Auditable ligne à ligne | Opaque une fois fondu |
| Révocable — on retire l'entrée | Irréversible sans réentraîner |
| Consentement par observation | Consentement par jeu de données |

Ce module fait la colonne de gauche. `training_status()` dit en toutes lettres
que la colonne de droite n'a pas lieu, et énumère ce que §31 exigerait avant
qu'elle ait lieu un jour. Un module qui se contenterait de *ne pas* entraîner
laisserait la question ouverte ; celui-ci y répond.

## La boucle de §31

```
UTILISATEURS → interaction naturelle → observation candidate
             → validation (humaine)  → base de connaissance
             → meilleure récupération → meilleures réponses
             → plus d'observations validées
```

Le seul cran qui ne s'automatise pas est la validation, et c'est ce qui empêche
la boucle de tourner sur ses propres erreurs. Une boucle sans humain amplifie ce
qu'elle a mal compris au premier tour.

## Demander plutôt que deviner

§29 : quand la plateforme hésite entre deux sens, elle **demande**. La question
est posée avec les deux hypothèses, jamais avec une seule — proposer un sens
unique fait acquiescer, et transforme l'hésitation de la machine en confirmation
de l'utilisateur.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .knowledge import LanguageKnowledgeBase
from .observation import (
    CANDIDAT,
    CORROBORE,
    OFFICIEL,
    VALIDE,
    LanguageObservation,
    new_observation,
)

#: Ce que fait ce module, et ce qu'il ne fait pas. Nommé pour qu'une lecture
#: rapide ne puisse pas confondre les deux.
ACQUISITION = "KNOWLEDGE_ACQUISITION"
ENTRAINEMENT = "MODEL_TRAINING"

#: Les sept conditions de §31 avant qu'un entraînement soit seulement
#: envisageable. Aucune n'est remplie ici, et la liste sert à le vérifier
#: plutôt qu'à le promettre.
CONDITIONS_ENTRAINEMENT = (
    "explicit",
    "consent-aware",
    "legally reviewed",
    "dataset-controlled",
    "reproducible",
    "isolated",
    "auditable",
)

#: Les états à partir desquels une observation mérite d'être proposée à un
#: humain. En dessous, la question arriverait trop tôt et trop souvent.
ETATS_A_VALIDER = (CANDIDAT, CORROBORE)


class LoopRefused(ValueError):
    """Un geste de la boucle d'acquisition refusé, avec sa raison."""


def observe_from_interaction(
    base: LanguageKnowledgeBase,
    language: str,
    expression: str,
    by: str,
    meaning: Optional[str] = None,
    context: str = "",
    **champs: Any,
) -> LanguageObservation:
    """
    Range ce qu'une interaction a fait apparaître, à son premier échelon.

    Args:
        base: La base de connaissance.
        language: La langue observée.
        expression: L'expression rencontrée.
        by: Qui a produit l'interaction.
        meaning: Le sens proposé, s'il y en a un. `None` est une réponse.
        context: La situation.
        **champs: Les autres champs de l'observation.

    Returns:
        L'entrée telle qu'elle est après rangement — `OBSERVED` et **`PRIVATE`**.
        Le privé est le défaut parce qu'une interaction est privée jusqu'à ce
        que quelqu'un décide le contraire ; l'inverse ferait entrer une
        conversation dans la connaissance globale par simple oubli.

    Raises:
        ObservationRefused: Observateur absent, langue non déclarée.
    """
    observation = new_observation(
        language=language, expression=expression, by=by,
        meaning=meaning, context=context, **champs,
    )
    return base.add(observation)


def clarification_question(
    hypotheses: Sequence[LanguageObservation], expression: str = "",
) -> Dict[str, Any]:
    """
    Formule la question de §29, avec **toutes** les hypothèses.

    Args:
        hypotheses: Les sens concurrents observés.
        expression: L'expression, quand la liste est vide.

    Returns:
        La question à poser et les options, en français — la langue dans
        laquelle la plateforme s'adresse à l'utilisateur.

        Avec une seule hypothèse, la question **n'est pas posée** : proposer un
        sens unique fait acquiescer, et l'accord obtenu ainsi ne vaut rien. Le
        retour porte alors `ask=False` et dit pourquoi.

    Raises:
        LoopRefused: Ni hypothèse ni expression — il n'y a rien à demander.
    """
    sens = [h.meaning for h in hypotheses if h.meaning]
    terme = expression or (hypotheses[0].expression if hypotheses else "")
    if not terme:
        raise LoopRefused(
            "Aucune expression : il n'y a rien sur quoi demander une "
            "clarification."
        )

    if len(sens) < 2:
        return {
            "ask": False,
            "expression": terme,
            "question": None,
            "options": sens,
            "reason": (
                "Une seule hypothèse — ou aucune. Poser « cela signifie-t-il X ? » "
                "fait acquiescer : l'utilisateur confirme la proposition de la "
                "machine au lieu d'apporter la sienne. §29 demande un choix "
                "entre des sens, pas une validation d'un sens."
            ),
        }

    liste = " ou ".join(f"« {s} »" for s in sens)
    return {
        "ask": True,
        "expression": terme,
        "question": (
            f"Dans ce contexte, « {terme} » signifie-t-il {liste} ?"
        ),
        "options": sens,
        "reason": (
            "Deux sens ou plus ont été observés. La question les porte tous : "
            "en omettre un orienterait la réponse."
        ),
    }


def pending_validation(
    base: LanguageKnowledgeBase, language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Les observations qui attendent un humain.

    Args:
        base: La base de connaissance.
        language: Restreindre à une langue.

    Returns:
        Les entrées arrivées au plafond de la fréquence, dans l'ordre du plus
        observé au moins observé. Ce sont celles pour qui la répétition a donné
        tout ce qu'elle pouvait donner : leur seul chemin restant passe par
        quelqu'un.
    """
    uniques = {
        entree.observation_id: entree
        for entree in base.entries()
        if entree.status in ETATS_A_VALIDER
        and (language is None or entree.language == language)
    }
    return [
        {
            "observation_id": entree.observation_id,
            "language": entree.language,
            "expression": entree.expression,
            "meaning": entree.meaning,
            "status": entree.status,
            "observed_count": entree.observed_count,
            "privacy": entree.privacy,
            "blocked_on": (
                "un humain nommé — la fréquence ne mène pas plus haut (§28)"
            ),
        }
        for entree in sorted(uniques.values(),
                             key=lambda e: -e.observed_count)
    ]


def training_status() -> Dict[str, Any]:
    """
    Ce qui est entraîné à partir des conversations : rien.

    Returns:
        Le constat, et les sept conditions de §31 qu'un entraînement devrait
        remplir un jour. Elles sont listées `NOT_MET` — non pas parce qu'elles
        ont échoué, mais parce qu'aucun entraînement n'a lieu : il n'y a rien à
        évaluer.

        Cette fonction existe pour que la réponse soit vérifiable au lieu
        d'être promise dans une documentation. §45 interdit d'entraîner
        silencieusement ; le silence est justement ce qu'on ne peut pas
        contrôler.
    """
    return {
        "activity": ACQUISITION,
        "model_training": "NONE",
        "trains_on_conversations": False,
        "weights_modified": False,
        "conditions_for_future_training": [
            {"condition": condition, "state": "NOT_MET",
             "reason": "Aucun entraînement n'a lieu : rien à évaluer."}
            for condition in CONDITIONS_ENTRAINEMENT
        ],
        "difference": {
            ACQUISITION: (
                "Une entrée s'ajoute à une base : auditable ligne à ligne, "
                "révocable en la retirant, consentie observation par "
                "observation."
            ),
            ENTRAINEMENT: (
                "Des poids changent : opaque une fois fondu, irréversible sans "
                "réentraîner, consenti au niveau du jeu de données."
            ),
        },
        "note": (
            "§27 et §31 séparent les deux actes, et ce dépôt les garde "
            "séparés. Un futur entraînement serait un dispositif explicite, "
            "avec son ADR, son jeu de données et son audit — jamais un effet "
            "de bord de cette boucle."
        ),
    }


def loop_report(base: LanguageKnowledgeBase) -> Dict[str, Any]:
    """
    L'état de la boucle d'acquisition.

    Args:
        base: La base de connaissance.

    Returns:
        Les étapes de §31, ce qui attend un humain, et le statut
        d'entraînement — les trois choses qu'il faut pour juger si la boucle
        tourne honnêtement.
    """
    etat = base.report()
    return {
        "stages": [
            "interaction",
            "candidate observation",
            "human validation",
            "knowledge base",
            "improved retrieval",
            "better answers",
        ],
        "automatic_stages": [
            "interaction", "candidate observation", "knowledge base",
            "improved retrieval", "better answers",
        ],
        "manual_stages": ["human validation"],
        "knowledge": etat,
        "pending_validation": len(pending_validation(base)),
        "validated": etat["by_status"].get(VALIDE, 0),
        "official": etat["by_status"].get(OFFICIEL, 0),
        "training": training_status(),
        "note": (
            "Une seule étape ne s'automatise pas, et c'est celle qui empêche "
            "la boucle de tourner sur ses propres erreurs : sans humain, elle "
            "amplifierait ce qu'elle a mal compris au premier tour."
        ),
    }
