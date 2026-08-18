"""
Deux architectures pour un même résultat, et le refus d'en préférer une (C15, §43).

## Ce que §43 demande, littéralement

Évaluer **les deux** :

```
PIPELINE A   génération vidéo + audio (d'origine ou généré) + synchronisation labiale
PIPELINE B   génération audio-vidéo native
```

et, mot pour mot : *« ne pas supposer qu'une architecture est universellement
supérieure »*. C'est une consigne inhabituelle, et elle est justifiée : A et B
échouent sur des choses différentes. A compose des briques remplaçables et paie
la synchronisation labiale ; B produit l'image et le son ensemble et paie le
fait qu'on ne peut plus remplacer l'une sans l'autre.

Ce module ne choisit donc pas. Il **planifie les deux**, dit pour chacune où
elle s'arrête, et laisse le choix à un critère mesuré — ou l'annonce impossible.

## L'asymétrie qui compte, et qu'on oublie

L'étape audio de A **peut n'exiger aucun fournisseur**. Quand la personne a
fourni son enregistrement, §22 dit de le garder : il n'y a rien à générer, donc
rien à router. C'est le seul endroit de la chaîne où une étape est satisfaite
par une absence de travail, et c'est exactement ce que la plateforme veut pour
les langues peu dotées — B, elle, régénère la voix par construction.

Un planificateur qui traiterait « audio » comme une étape à fournisseur
obligatoire déclarerait A bloquée là où elle ne l'est pas, et pousserait vers B
précisément dans le cas où B est le mauvais choix.

## Ce qui est mesuré ici, aujourd'hui

Aucun fournisseur de génération n'est disponible sur cette machine, donc les
deux architectures sont `BLOCKED`. Le module le rapporte étape par étape plutôt
que globalement : savoir que A bute sur la synchronisation labiale et B sur la
génération elle-même n'est pas la même information, et la seconde ne se déduit
pas de la première.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .providers import AUCUN, CHOISI, CreativeRequest, ProviderRegistry
from .routing import CLASSABLES, NON_CLASSE, RoutingNeed, RoutingRefused, route

#: Les deux architectures de §43.
PIPELINE_A = "COMPOSED"
PIPELINE_B = "NATIVE_AUDIO_VIDEO"
PIPELINES = (PIPELINE_A, PIPELINE_B)

#: L'état d'une architecture. `BLOCKED` nomme l'étape qui bloque ; un état
#: global sans étape ne dit pas quoi installer.
REALISABLE = "FEASIBLE"
BLOQUE = "BLOCKED"

#: Ce qui satisfait une étape sans fournisseur : l'enregistrement de la
#: personne, gardé tel quel (§22).
SANS_FOURNISSEUR = "NO_PROVIDER_NEEDED"


class PipelineRefused(ValueError):
    """Une planification impossible à interpréter telle qu'elle est posée."""


@dataclass(frozen=True)
class Stage:
    """
    Une étape d'une architecture.

    Attributes:
        name: Ce que l'étape fait.
        task: La tâche à router, ou vide si l'étape n'en demande aucune.
        capabilities: Les capacités exigées du fournisseur.
        optional: Vrai si l'architecture tient sans cette étape.
        satisfied_without_provider: Vrai quand l'étape est remplie par ce que
            l'utilisateur a fourni — le cas de l'audio d'origine.
    """

    name: str
    task: str = ""
    capabilities: Tuple[str, ...] = ()
    optional: bool = False
    satisfied_without_provider: bool = False


def _etapes_a(preserve_original_audio: bool, needs_lip_sync: bool) -> List[Stage]:
    """Les étapes de l'architecture composée, selon ce qui est demandé."""
    etapes = [Stage("video_generation", task="text_to_video")]
    if preserve_original_audio:
        etapes.append(Stage(
            "audio", satisfied_without_provider=True,
            # Rien à générer : l'enregistrement existe et §22 dit de le garder.
        ))
    else:
        etapes.append(Stage("audio", task="speech_synthesis"))
    if needs_lip_sync:
        etapes.append(Stage("lip_sync", task="lip_sync",
                            capabilities=("lip_sync",)))
    return etapes


def _etapes_b(needs_lip_sync: bool) -> List[Stage]:
    """Les étapes de l'architecture native."""
    etapes = [Stage("audio_video_generation", task="audio_to_video",
                    capabilities=("audio_output",))]
    if needs_lip_sync:
        # La synchronisation est interne au modèle : c'est l'argument de B, et
        # c'est une capacité qu'il doit **déclarer**, pas qu'on lui suppose.
        etapes[0] = Stage("audio_video_generation", task="audio_to_video",
                          capabilities=("audio_output", "lip_sync"))
    return etapes


def plan_pipeline(
    registry: ProviderRegistry,
    pipeline: str,
    commercial: bool = False,
    preserve_original_audio: bool = True,
    needs_lip_sync: bool = True,
    need: Optional[RoutingNeed] = None,
) -> Dict[str, Any]:
    """
    Planifie une architecture, étape par étape.

    Args:
        registry: Les fournisseurs déclarés.
        pipeline: `COMPOSED` ou `NATIVE_AUDIO_VIDEO`.
        commercial: Si le résultat sera exploité commercialement.
        preserve_original_audio: Garder l'enregistrement de la personne. Vrai
            par défaut : §22 en fait le chemin normal, pas un repli.
        needs_lip_sync: Si les lèvres doivent suivre la parole.
        need: Les exigences de capacité communes aux étapes.

    Returns:
        L'état de l'architecture et le détail de chaque étape. `BLOCKED` nomme
        **la première** étape qui bloque : les suivantes ne sont pas « prêtes »
        au sens utile du terme, puisqu'on ne les atteint pas.

    Raises:
        PipelineRefused: Architecture inconnue.
    """
    if pipeline not in PIPELINES:
        raise PipelineRefused(
            f"Architecture « {pipeline} » inconnue. Déclarées : {list(PIPELINES)}."
        )

    etapes = (_etapes_a(preserve_original_audio, needs_lip_sync)
              if pipeline == PIPELINE_A else _etapes_b(needs_lip_sync))

    detail = []
    for etape in etapes:
        if etape.satisfied_without_provider:
            detail.append({
                "stage": etape.name, "state": SANS_FOURNISSEUR,
                "provider_id": None,
                "reason": (
                    "L'enregistrement fourni est conservé : rien n'est généré, "
                    "donc rien n'est à router. C'est la seule étape de la "
                    "chaîne qu'une absence de travail satisfait, et c'est ce "
                    "que §22 demande."
                ),
            })
            continue

        exigences = RoutingNeed(
            capabilities=tuple(dict.fromkeys(
                (need.capabilities if need else ()) + etape.capabilities)),
            strict=need.strict if need else (),
            available_vram_gb=need.available_vram_gb if need else None,
        )
        resultat = route(
            registry, CreativeRequest(task=etape.task, commercial=commercial),
            exigences,
        )
        detail.append({
            "stage": etape.name,
            "state": REALISABLE if resultat["status"] == CHOISI else BLOQUE,
            "provider_id": resultat.get("provider_id"),
            "task": etape.task,
            "reason": resultat.get("reason", ""),
        })

    bloquees = [e["stage"] for e in detail if e["state"] == BLOQUE]
    return {
        "pipeline": pipeline,
        "state": BLOQUE if bloquees else REALISABLE,
        "stages": detail,
        "blocked": bloquees,
        "first_block": bloquees[0] if bloquees else None,
        "preserves_original_audio": (
            pipeline == PIPELINE_A and preserve_original_audio
        ),
    }


def compare_pipelines(
    registry: ProviderRegistry, **options: Any,
) -> Dict[str, Any]:
    """
    Planifie les deux architectures et refuse d'en désigner une.

    Args:
        registry: Les fournisseurs déclarés.
        **options: Les mêmes options que `plan_pipeline`.

    Returns:
        Les deux plans, celles qui sont réalisables, et **aucun gagnant**. §43
        interdit de supposer une supériorité universelle ; désigner un défaut
        ici en installerait une par la porte de derrière, et personne ne la
        rediscuterait ensuite.

        Ce qui est rapporté à la place est la différence qui décide vraiment :
        A peut préserver la voix de la personne, B la régénère par
        construction.
    """
    plans = {
        nom: plan_pipeline(registry, nom, **options) for nom in PIPELINES
    }
    realisables = [nom for nom, plan in plans.items()
                   if plan["state"] == REALISABLE]

    return {
        "plans": plans,
        "feasible": realisables,
        "recommended": None,
        "note": (
            "Aucune architecture recommandée par défaut (§43). Elles échouent "
            "sur des choses différentes : A compose des briques remplaçables "
            "et paie la synchronisation labiale ; B produit image et son "
            "ensemble et paie de ne plus pouvoir remplacer l'une sans l'autre."
        ),
        "decisive_difference": {
            PIPELINE_A: (
                "Peut conserver l'enregistrement de la personne — "
                "prononciation, accent, hésitations. Pour une langue peu "
                "dotée, c'est la seule option fidèle disponible aujourd'hui "
                "(§26)."
            ),
            PIPELINE_B: (
                "Régénère la voix par construction. La synchronisation est "
                "interne au modèle, ce qui supprime une étape — et supprime "
                "aussi la possibilité de garder la voix d'origine."
            ),
        },
    }


def choose_pipeline(
    registry: ProviderRegistry, by: str = "", **options: Any,
) -> Dict[str, Any]:
    """
    Choisit une architecture **seulement** sur un critère mesuré.

    Args:
        registry: Les fournisseurs déclarés.
        by: La dimension de départage, parmi `CLASSABLES`. Vide, aucune
            architecture n'est retenue et le retour le dit.
        **options: Les mêmes options que `plan_pipeline`.

    Returns:
        L'architecture retenue, ou `UNRANKED` avec la raison. Une seule
        réalisable est retenue sans critère : il n'y a rien à départager.

    Raises:
        RoutingRefused: Dimension non classable — la qualité n'a pas de mesure
            ici, et §43 dit précisément de choisir « selon une capacité
            mesurable ».
    """
    comparaison = compare_pipelines(registry, **options)
    realisables = comparaison["feasible"]

    if not realisables:
        return {
            "status": AUCUN, "pipeline": None, "comparison": comparaison,
            "reason": (
                "Aucune des deux architectures n'est réalisable avec les "
                "fournisseurs déclarés. Chaque plan nomme l'étape où il "
                "s'arrête."
            ),
        }

    if len(realisables) == 1:
        return {
            "status": CHOISI, "pipeline": realisables[0],
            "comparison": comparaison,
            "reason": "Une seule architecture réalisable : rien à départager.",
        }

    if not by:
        return {
            "status": NON_CLASSE, "pipeline": None, "comparison": comparaison,
            "reason": (
                "Les deux architectures sont réalisables et aucun critère "
                "mesuré n'a été donné. §43 refuse de supposer une supériorité "
                "universelle : le choix revient au demandeur, avec la "
                "différence décisive sous les yeux."
            ),
        }

    if by not in CLASSABLES:
        raise RoutingRefused(
            f"Départage « {by} » non classable. Classables : "
            f"{sorted(CLASSABLES)}. Choisir une architecture sur la qualité "
            "supposerait une mesure qui n'existe pas ici."
        )

    valeurs: Dict[str, float] = {}
    manquants = []
    for nom in realisables:
        total = 0.0
        complet = True
        for etape in comparaison["plans"][nom]["stages"]:
            identifiant = etape.get("provider_id")
            if identifiant is None:
                continue  # étape sans fournisseur : elle ne coûte rien
            fournisseur = registry.get(identifiant)
            valeur = getattr(fournisseur, by, None) if fournisseur else None
            if valeur is None:
                complet = False
                break
            total += float(valeur)
        if complet:
            valeurs[nom] = total
        else:
            manquants.append(nom)

    if manquants:
        return {
            "status": NON_CLASSE, "pipeline": None, "comparison": comparaison,
            "dimension": by, "missing": manquants,
            "reason": (
                f"{manquants} ne déclare(nt) pas « {by} » sur toutes leurs "
                "étapes. Sommer ce qui existe et ignorer le reste ferait "
                "gagner l'architecture la moins documentée."
            ),
        }

    retenue = min(valeurs, key=lambda nom: valeurs[nom])
    return {
        "status": CHOISI, "pipeline": retenue, "comparison": comparaison,
        "dimension": by, "totals": valeurs,
        "reason": (
            f"Départagées sur « {by} », additionné le long des étapes de "
            "chacune. C'est une comparaison de chiffres déclarés, pas un "
            "jugement de qualité."
        ),
    }


def pipelines_report() -> Dict[str, Any]:
    """
    Les deux architectures et les règles qui les gouvernent.

    Returns:
        De quoi juger sans lire le code.
    """
    return {
        "pipelines": list(PIPELINES),
        "states": [REALISABLE, BLOQUE, SANS_FOURNISSEUR],
        "rankable": sorted(CLASSABLES),
        "rules": [
            "Aucune architecture n'est recommandée par défaut (§43) : elles "
            "échouent sur des choses différentes.",
            "L'étape audio de A est satisfaite **sans fournisseur** quand "
            "l'enregistrement est conservé (§22) — la traiter comme une étape "
            "à fournisseur obligatoire pousserait vers B là où B est le "
            "mauvais choix.",
            "`BLOCKED` nomme la **première** étape qui bloque : les suivantes "
            "ne sont pas prêtes, on ne les atteint pas.",
            "Un départage n'a lieu que sur une dimension mesurée, et seulement "
            "si toutes les étapes des deux architectures la portent.",
        ],
    }
