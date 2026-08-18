"""
La tranche verticale, et l'endroit exact où elle s'arrête (C17, §65, §66).

## Ce que §65 demande

Un flux de bout en bout : *utilisateur → voix → compréhension multi-locuteurs →
mise en correspondance des références → création du monde → direction →
découpage en plans → fournisseur vidéo → audio d'origine → synchronisation
labiale → vérification d'identité → continuité → vidéo finale*.

Et §72, juste après : *« ne pas surdimensionner le MVP »* — un flux qui marche
vaut mieux que cent abstractions incomplètes.

## Ce que cette tranche fait réellement

Elle **parcourt les treize étapes** et rend, pour chacune, ce qui s'est
réellement passé : ce qui a eu lieu, ce qui bute sur une capacité absente, ce
qui ne peut pas être jugé faute de mesure, et ce qui vient après le premier
blocage dur. Le compte n'est pas écrit ici — il dépend de la machine, et le
figer dans une docstring le ferait mentir au premier GPU branché.

Aucune vidéo n'est produite. Le dire ici, en tête du module, est le point :
`scripts/demonstration.py` a établi cette forme dans ce dépôt — parcourir la
chaîne réelle et **rapporter ce qui a eu lieu**, `OK` ou `NOT_CONFIGURED`, sans
que le compte final ne puisse se lire comme un succès.

## Ce que la tranche refuse de faire

Elle ne saute pas une étape bloquée pour atteindre la suivante. §21 l'a établi
pour la chaîne vocale : *le premier blocage est le point où la chaîne s'arrête
réellement, et les étapes suivantes ne sont pas « prêtes » au sens utile du
terme*. Les étapes après le premier blocage dur sont donc parcourues pour dire
ce qu'elles feraient, jamais comptées comme franchies.

Et elle n'invente aucun locuteur, aucune entité, aucune transcription : ce que
l'appelant n'a pas fourni reste vide, et l'étape le rapporte.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

#: L'issue d'une étape. Quatre, et chacune dit autre chose : `OK` a eu lieu,
#: `BLOCKED` attend une capacité, `NOT_MEASURABLE` ne peut pas être jugé même
#: si tout le reste marchait, `NOT_REACHED` est après le premier blocage dur.
OK = "OK"
BLOQUE = "BLOCKED"
NON_MESURABLE = "NOT_MEASURABLE"
NON_ATTEINT = "NOT_REACHED"
ISSUES = (OK, BLOQUE, NON_MESURABLE, NON_ATTEINT)

#: Les treize étapes de §65, dans l'ordre du texte.
ETAPES = (
    "user_intent", "voice_understanding", "reference_entity_mapping",
    "world_creation", "direction", "shot_planning", "provider_routing",
    "video_generation", "original_audio", "lip_sync",
    "identity_verification", "continuity", "final_video",
)


def _etape(name: str, outcome: str, detail: str, **preuve: Any) -> Dict[str, Any]:
    """Une étape parcourue, avec ce qu'elle a donné."""
    return {"stage": name, "outcome": outcome, "detail": detail,
            "evidence": preuve}


def run_slice(
    request: str,
    audio_segments: Optional[Sequence[Any]] = None,
    references: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Parcourt la tranche verticale de §65 et rapporte ce qui a eu lieu.

    Args:
        request: La demande de l'utilisateur, en langage naturel.
        audio_segments: Les `AudioSegment` mesurés, quand une voix est fournie.
        references: L'attribution locuteur → entité, quand quelqu'un l'a
            établie. **Rien n'est deviné** : sans elle, l'étape de mise en
            correspondance rapporte les locuteurs non attribués.

    Returns:
        Les treize étapes et leur issue, plus le constat final. Le compte est
        `done / total` d'étapes réellement franchies — et il ne peut pas se
        lire comme un succès, parce que `final_video` y figure et n'a pas eu
        lieu.
    """
    from .direction import DirectorSpec, ShotPlanner
    from .language.switching import switching_report
    from .pipelines import PIPELINE_A, plan_pipeline
    from .providers import AUCUN, CreativeRequest, ProviderRegistry, adapt_declared
    from .representation import from_request
    from .research import load_research
    from .routing import route
    from .verification import identity_dimensions_here
    from .voice.scene import build_scene, original_audio_exists, voice_plan
    from .world import EntityState, WorldState

    etapes: List[Dict[str, Any]] = []
    segments = list(audio_segments or [])

    # 1. L'intention. Un champ que l'utilisateur n'a pas énoncé reste ouvert.
    representation = from_request(request)
    manquants = [champ for champ, valeur in representation.as_dict().items()
                 if isinstance(valeur, dict) and valeur.get("origin") == "UNSET"]
    etapes.append(_etape(
        "user_intent", OK,
        "La demande est structurée ; les champs non énoncés restent ouverts "
        "au lieu d'être comblés par un défaut.",
        unset_fields=len(manquants)))

    # 2. La voix. Sans segments fournis, rien n'est transcrit ni séparé.
    if segments:
        scene = build_scene(segments)
        alternance = switching_report(segments)
        etapes.append(_etape(
            "voice_understanding", OK,
            "Les segments fournis sont assemblés tels quels. La séparation de "
            "locuteurs et la transcription restent indisponibles ici, et rien "
            "ne les remplace.",
            languages=alternance["languages"],
            code_switching=alternance["code_switching"],
            without_transcript=len(scene["segments_without_transcript"])))
    else:
        scene = None
        etapes.append(_etape(
            "voice_understanding", BLOQUE,
            "Aucun enregistrement fourni, et rien ici ne peut en produire : "
            "ni transcription, ni séparation de locuteurs."))

    # 3. Les références. Un locuteur sans entité déclarée le reste.
    attribution = dict(references or {})
    locuteurs = sorted({s.speaker_id for s in segments if s.speaker_id})
    non_attribues = [nom for nom in locuteurs if nom not in attribution]
    etapes.append(_etape(
        "reference_entity_mapping", OK,
        "Les correspondances fournies sont reprises ; les locuteurs sans "
        "entité sont **nommés**, jamais rattachés au plus proche.",
        mapped=len(attribution), unassigned=non_attribues))

    # 4. Le monde. Il porte les entités, pas le style (§46).
    monde = WorldState(environment="unspecified")
    for entite in attribution.values():
        monde.place(EntityState(entity_id=entite, entity_type="human",
                                reference_id=None))
    etapes.append(_etape(
        "world_creation", OK,
        "Le monde est ouvert et porte les entités déclarées. Le style n'y est "
        "pas : le même monde peut être rendu photoréaliste ou animé.",
        entities=len(attribution),
        environment_declared=False))

    # 5. La direction. Structurée, jamais un adjectif ajouté au prompt.
    specification = DirectorSpec(shot_size="medium", movement="static",
                                 intent=request[:80])
    etapes.append(_etape(
        "direction", OK,
        "Les instructions sont structurées — taille de plan, hauteur, "
        "mouvement — au lieu d'adjectifs accolés à une phrase.",
        shot_size=specification.shot_size, movement=specification.movement))

    # 6. Le découpage. Un plan est adressable, donc régénérable seul.
    planificateur = ShotPlanner(monde)
    plan = planificateur.add(specification,
                             entity_ids=sorted(attribution.values()))
    etapes.append(_etape(
        "shot_planning", OK,
        "Au moins un plan existe et porte sa propre identité : une "
        "régénération n'oblige pas à refaire la production entière.",
        shots=1, shot_id=getattr(plan, "shot_id", None)))

    # 7. Le routage. Aucun repli sur le fournisseur le plus proche.
    registre = ProviderRegistry()
    for fournisseur in adapt_declared(load_research().get("candidates") or []):
        registre.register(fournisseur)
    routage = route(registre, CreativeRequest(task="text_to_video"))
    routage_ok = routage["status"] != AUCUN
    etapes.append(_etape(
        "provider_routing", OK if routage_ok else BLOQUE,
        "Un fournisseur est retenu." if routage_ok else
        "Aucun fournisseur déclaré ne sert cette demande, et aucun repli n'est "
        "proposé : servir autre chose serait une substitution silencieuse.",
        status=routage["status"],
        provider_id=routage.get("provider_id")))

    # 8. La génération. C'est ici que la chaîne s'arrête réellement.
    architecture = plan_pipeline(registre, PIPELINE_A)
    genere = architecture["state"] == "FEASIBLE"
    etapes.append(_etape(
        "video_generation", OK if genere else BLOQUE,
        "L'architecture composée est réalisable." if genere else
        f"L'architecture bute sur « {architecture['first_block']} ». Aucune "
        "vidéo n'est produite, et aucune n'est simulée.",
        first_block=architecture["first_block"]))
    premier_blocage_dur = None if genere else "video_generation"

    # 9. L'audio d'origine. La seule étape qu'une absence de travail satisfait.
    if scene is not None:
        conservation = original_audio_exists(scene)
        chemin = voice_plan(scene)
        etapes.append(_etape(
            "original_audio", OK,
            "L'enregistrement de la personne est conservé — c'est le chemin "
            "par défaut de §22, pas un repli, et il ne dépend d'aucun "
            "fournisseur.",
            path=chemin["path"], files_present=len(conservation["present"]),
            files_missing=len(conservation["missing"])))
    else:
        etapes.append(_etape(
            "original_audio", NON_ATTEINT,
            "Aucun enregistrement fourni : il n'y a rien à préserver."))

    # 10 à 13 : après le premier blocage dur, on dit ce qu'on ferait.
    etapes.append(_etape(
        "lip_sync", NON_ATTEINT if premier_blocage_dur else BLOQUE,
        "Aucune vidéo n'existe à synchroniser. La synchronisation exige par "
        "ailleurs un GPU et des points de repère faciaux, tous deux absents."))

    dimensions = identity_dimensions_here()
    non_mesurables = [d.dimension for d in dimensions
                      if d.outcome == "NOT_MEASURABLE"]
    etapes.append(_etape(
        "identity_verification", NON_MESURABLE,
        "Les dimensions d'identité sont déclarées, aucune n'est mesurable sur "
        "cette machine. Un score serait inventé, et ADR-026 l'interdit.",
        dimensions=len(dimensions), not_measurable=len(non_mesurables)))

    etapes.append(_etape(
        "continuity", NON_MESURABLE,
        "Sans plans rendus, la continuité n'a rien à comparer. `NOT_CHECKED` "
        "est une issue à part entière, jamais un `PASS` par défaut."))

    etapes.append(_etape(
        "final_video", NON_ATTEINT,
        "Aucune vidéo finale. C'est le constat de la tranche, pas son échec : "
        "tout ce qui pouvait avoir lieu sans génération a eu lieu."))

    comptes = {issue: len([e for e in etapes if e["outcome"] == issue])
               for issue in ISSUES}
    return {
        "stages": etapes,
        "total": len(etapes),
        "counts": comptes,
        "first_hard_block": premier_blocage_dur,
        "produced_video": False,
        "note": (
            f"{comptes[OK]} étapes sur {len(etapes)} ont réellement eu lieu. "
            "Aucune vidéo n'a été produite et aucune n'a été simulée : la "
            "chaîne s'arrête à la génération, faute de fournisseur dégagé et "
            "de GPU. Les étapes suivantes sont parcourues pour dire ce "
            "qu'elles feraient, jamais comptées comme franchies."
        ),
    }


def slice_report() -> Dict[str, Any]:
    """
    Ce que la tranche démontre, sans rien exécuter.

    Returns:
        Les étapes de §65, les issues possibles, et ce que la tranche refuse
        de faire.
    """
    return {
        "stages": list(ETAPES),
        "outcomes": list(ISSUES),
        "requires": {
            "text": "toujours",
            "audio": "pour les étapes de voix et d'audio d'origine",
            "references": "pour l'attribution locuteur → entité",
        },
        "refuses": [
            "Sauter une étape bloquée pour atteindre la suivante : le premier "
            "blocage est le point où la chaîne s'arrête réellement.",
            "Inventer un locuteur, une entité ou une transcription que "
            "l'appelant n'a pas fournis.",
            "Compter une étape non atteinte comme franchie.",
            "Produire un compte final qui puisse se lire comme un succès.",
        ],
        "note": (
            "§66 décrit le scénario complet — conversation spontanée en wolof "
            "et français, plusieurs entités, boutique, véhicule, animal. Tout "
            "ce qui en relève de l'orchestration est en place ; ce qui en "
            "relève de la génération attend un GPU et un fournisseur dont la "
            "licence des poids est vérifiée."
        ),
    }
