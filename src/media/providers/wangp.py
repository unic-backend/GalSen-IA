"""
The WanGP adapter — declared, isolated, and honest about not being integrated.

Directive §11 asks for the WanGP ecosystem
(`https://github.com/deepbeepmeep/Wan2GP`) as an **optional execution backend**,
and states three constraints that shape this file more than the integration
itself:

- *Do not blindly copy the repository into GalSen AI.*
- *Keep WanGP isolated behind an adapter so that GalSen AI remains independent
  from it.*
- *If the repository license or implementation constraints prevent direct
  integration, document the limitation and implement an adapter architecture
  instead.*

That third clause is the one in force, and it is in force for measured reasons
rather than chosen ones.

**The licence could not be inspected.** Directive §36 requires inspecting a
candidate's licence before integrating it, and this environment's proxy refuses
GitHub repositories outside the session's declared scope — `api.github.com`
answers *"GitHub access to this repository is not enabled for this session"*.
So the licence is `UNKNOWN`, and `UNKNOWN` blocks integration by itself:
vendoring code whose terms nobody read is a legal decision taken by a machine.

**Nothing could run anyway.** `gpu_compute` is `UNAVAILABLE` here — no `torch`,
no CUDA. A WanGP backend on this machine would report a failure at the first
call, and shipping it as though it worked would be the fabrication the whole
repository refuses.

So what exists is the adapter *shape*: a declared capability, a health check
that reports precisely why it cannot serve, and a `generate()` that refuses
instead of returning a placeholder file. The moment a GPU and a reviewed licence
exist, this file gains an implementation and nothing else in the engine changes
— which is what "isolated behind an adapter" was for.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..core.capabilities import DISPONIBLE, probe
from .base import GenerationRequest, ProviderCapability, ProviderRefused

#: L'origine déclarée, jamais vendue dans ce dépôt.
DEPOT = "https://github.com/deepbeepmeep/Wan2GP"

#: L'état de l'intégration, mesuré et non choisi.
NON_INTEGRE = "ADAPTER_ONLY"

#: Ce qui empêche l'intégration aujourd'hui. Chaque entrée est un fait
#: vérifiable, pas une préférence.
BLOCAGES = {
    "licence_not_inspected": (
        "La directive §36 exige d'inspecter la licence avant d'intégrer. Le "
        "mandataire de cet environnement refuse les dépôts GitHub hors du "
        "périmètre de la session — `api.github.com` répond « GitHub access to "
        "this repository is not enabled for this session ». La licence est donc "
        "`UNKNOWN`, et `UNKNOWN` bloque à lui seul : embarquer du code dont "
        "personne n'a lu les termes est une décision juridique prise par une "
        "machine."
    ),
    "no_gpu": (
        "`gpu_compute` est INDISPONIBLE ici : ni `torch`, ni CUDA. Un backend "
        "WanGP échouerait au premier appel, et le livrer comme s'il "
        "fonctionnait serait la fabrication que ce dépôt refuse partout."
    ),
    "not_vendored": (
        "Le dépôt n'est pas copié dans `src/` — la directive §11 l'interdit "
        "explicitement, et §36 interdit d'importer un dépôt à l'aveugle."
    ),
}

#: Les capacités que WanGP porterait, **telles que sa documentation publique les
#: décrit**. Ce sont des attentes, pas des mesures : rien n'a tourné ici, donc
#: aucune n'est vérifiée. La distinction est portée par `verified=False`.
CAPACITE_ATTENDUE = ProviderCapability(
    provider_id="wangp",
    tasks=frozenset({"text_to_video", "image_to_video", "text_to_image"}),
    max_width=1280,
    max_height=720,
    max_duration_s=10.0,
    min_vram_gb=6.0,
    requires=("gpu_compute",),
    deterministic=False,
    cost_per_second=None,
    typical_latency_s=None,
    licence=None,
)


class WanGPUnavailable(ProviderRefused):
    """Une génération demandée à un backend qui n'est pas intégré."""


def health() -> Dict[str, Any]:
    """
    L'état réel de l'adaptateur, mesuré.

    Returns:
        L'état d'intégration, les blocages nommés, et l'état des capacités dont
        il dépend. Rien n'est arrondi : un adaptateur qui se déclarerait « prêt,
        en attente de configuration » laisserait croire qu'une clé suffirait.
    """
    sonde = probe("gpu_compute")
    return {
        "provider_id": CAPACITE_ATTENDUE.provider_id,
        "integration": NON_INTEGRE,
        "repository": DEPOT,
        "vendored": False,
        "licence": "UNKNOWN",
        "licence_verified": False,
        "capabilities_verified": False,
        "blockers": dict(BLOCAGES),
        "gpu_state": sonde["state"],
        "gpu_reason": sonde["reason"],
        "expected_capability": CAPACITE_ATTENDUE.as_dict(),
        "note": (
            "Adaptateur **seul**. Les capacités listées sont celles que la "
            "documentation publique décrit : ce sont des attentes, pas des "
            "mesures — rien n'a tourné ici. Le jour où un GPU et une licence "
            "relue existent, ce fichier gagne une implémentation et **rien "
            "d'autre ne change dans le moteur**, ce qui est le but d'un "
            "adaptateur isolé."
        ),
    }


def is_available() -> bool:
    """
    Vrai seulement si l'adaptateur pourrait réellement servir.

    Les deux conditions sont indépendantes : un GPU sans licence relue reste un
    refus, et une licence relue sans GPU aussi.
    """
    return (
        probe("gpu_compute")["state"] == DISPONIBLE
        and health()["licence_verified"]
    )


def generate(
    request: GenerationRequest, output_path: str,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Refuse, en disant exactement ce qui manque.

    Args:
        request: Ce qui est demandé.
        output_path: Où le fichier serait écrit.
        options: Les réglages du backend, ignorés tant qu'il n'existe pas.

    Raises:
        WanGPUnavailable: Toujours, dans cet état. Un fichier vide, un
            marbre noir ou une image de remplacement seraient pires qu'un
            refus : ils descendent la chaîne, s'encodent sans erreur, passent
            les contrôles de durée et n'échouent que devant un spectateur.
    """
    etat = health()
    raisons = " ".join(f"[{nom}] {texte}" for nom, texte in etat["blockers"].items())
    raise WanGPUnavailable(
        f"WanGP n'est pas intégré ({etat['integration']}). {raisons} "
        f"Aucun fichier n'est écrit en « {output_path} » : un marbre noir "
        "descendrait la chaîne, s'encoderait sans erreur, passerait les "
        "contrôles de durée, et n'échouerait que devant un spectateur."
    )


def integration_report() -> Dict[str, Any]:
    """
    Ce que l'adaptateur est, et ce qu'il n'est pas.

    Returns:
        L'état d'intégration et les règles tenues.
    """
    return {
        "status": NON_INTEGRE,
        "repository": DEPOT,
        "blockers": dict(BLOCAGES),
        "rules": [
            "Le dépôt n'est **pas** copié : la directive §11 l'interdit, et "
            "§36 interdit d'importer un dépôt à l'aveugle.",
            "La licence n'a pas pu être inspectée depuis cet environnement, "
            "donc elle vaut `UNKNOWN` — et `UNKNOWN` bloque à lui seul : "
            "embarquer du code dont personne n'a lu les termes est une décision "
            "juridique prise par une machine.",
            "Les capacités listées viennent de la documentation publique : ce "
            "sont des **attentes**, marquées non vérifiées, pas des mesures.",
            "`generate()` refuse au lieu d'écrire un fichier de remplacement : "
            "un marbre noir s'encode sans erreur et n'échoue que devant un "
            "spectateur.",
            "Le moteur ne dépend de rien de WanGP : le jour où l'intégration "
            "devient possible, ce fichier change et rien d'autre.",
        ],
        "does_not": [
            "Copier un dépôt tiers dans `src/`.",
            "Déclarer une licence qui n'a pas été lue.",
            "Présenter une capacité documentée comme une capacité mesurée.",
            "Écrire un fichier de remplacement quand la génération est "
            "impossible.",
        ],
    }
