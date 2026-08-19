"""
Choosing a generator on measurements, and refusing when none fits.

Directive §10 lists what provider selection must weigh — task, GPU, VRAM,
resolution, duration, image-to-video, text-to-video, latency, cost — and §35
adds that a new model must be integrable without rewriting the core. Both are
satisfied by the same thing: a provider **declares** what it can do, and the
selector compares those declarations against what this machine actually has.

The failure this closes is the helpful selector. Asked for 1080p and finding
only a 720p provider, it returns the 720p one — reasonably, and silently. The
caller receives a video that is not what they asked for and has no way to tell
that a substitution happened. So `select_provider()` returns a refusal listing
**why each provider was excluded**, and never a nearest match. A downgrade is a
decision, and decisions belong to whoever is making the film.

Three declarations are deliberately nullable, and `None` never means zero:

- **`min_vram_gb = None`** means the provider needs no GPU, which is different
  from needing 0 GB.
- **`cost_per_second = None`** means the cost is unknown. A selector sorting by
  cost must *exclude* unknowns rather than treat them as free — ranking an
  unpriced provider first is how a bill arrives.
- **`typical_latency_s = None`** means nobody measured it. Inventing a plausible
  latency is how a queue estimate becomes a promise nobody can keep (§33: never
  invent benchmark results).

Capabilities that must exist for a provider to run are named from M01's probe
list, so "this provider is unavailable" always resolves to a measured reason
rather than an opinion.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from ..core.capabilities import DISPONIBLE, probe

#: Les tâches génératives déclarées (§10). Une tâche absente de cette liste
#: n'est pas « proche » d'une autre : générer une vidéo depuis une image et
#: depuis un texte sont deux capacités différentes.
TACHES = (
    "text_to_video",
    "image_to_video",
    "video_to_video",
    "text_to_image",
    "upscale",
    "interpolate",
    # Composer un montage à partir de rushes **récupérés**, pas générés
    # (ADR-030). C'est une tâche distincte de `text_to_video`, et les
    # confondre serait une erreur de catégorie aux conséquences réelles :
    # un routeur choisirait un assembleur pour « génère une scène avec mon
    # ami » et rendrait des rushes d'un inconnu. Le sélecteur refuse déjà de
    # servir autre chose que ce qui est demandé ; encore faut-il que les deux
    # actes portent deux noms.
    "stock_assembly",
)

#: Ce qu'une sélection peut donner.
CHOISI = "SELECTED"
AUCUN = "NO_PROVIDER"


class ProviderRefused(RuntimeError):
    """Une génération demandée qu'aucun fournisseur déclaré ne peut servir."""


@dataclass(frozen=True)
class ProviderCapability:
    """
    Ce qu'un fournisseur déclare savoir faire.

    Attributes:
        provider_id: Son identifiant stable.
        tasks: Les tâches qu'il sert.
        max_width: Largeur maximale, en pixels.
        max_height: Hauteur maximale.
        max_duration_s: Durée maximale d'un plan généré.
        min_vram_gb: VRAM minimale. `None` signifie **aucun GPU requis**, ce qui
            n'est pas « 0 Go ».
        requires: Les capacités de `core.capabilities` dont il dépend.
        deterministic: Si deux appels identiques rendent le même résultat.
        cost_per_second: Coût par seconde produite. `None` = **inconnu**, jamais
            gratuit.
        typical_latency_s: Latence observée. `None` = personne ne l'a mesurée.
        licence: La licence du modèle ou du backend, si elle a été vérifiée.
    """

    provider_id: str
    tasks: FrozenSet[str]
    max_width: int = 0
    max_height: int = 0
    max_duration_s: float = 0.0
    min_vram_gb: Optional[float] = None
    requires: Tuple[str, ...] = ()
    deterministic: bool = False
    cost_per_second: Optional[float] = None
    typical_latency_s: Optional[float] = None
    licence: Optional[str] = None

    def __post_init__(self) -> None:
        inconnues = sorted(set(self.tasks) - set(TACHES))
        if inconnues:
            raise ProviderRefused(
                f"Tâches non déclarées : {inconnues}. Les tâches connues sont "
                f"{list(TACHES)} — générer depuis une image et depuis un texte "
                "sont deux capacités différentes, pas deux nuances d'une même."
            )

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "provider_id": self.provider_id, "tasks": sorted(self.tasks),
            "max_width": self.max_width, "max_height": self.max_height,
            "max_duration_s": self.max_duration_s,
            "min_vram_gb": self.min_vram_gb, "requires": list(self.requires),
            "deterministic": self.deterministic,
            "cost_per_second": self.cost_per_second,
            "typical_latency_s": self.typical_latency_s,
            "licence": self.licence,
        }


@dataclass(frozen=True)
class GenerationRequest:
    """
    Ce qu'on demande à produire.

    Attributes:
        task: La tâche voulue.
        width: Largeur demandée.
        height: Hauteur demandée.
        duration_s: Durée demandée.
        require_deterministic: Exiger un fournisseur reproductible.
    """

    task: str
    width: int
    height: int
    duration_s: float
    require_deterministic: bool = False

    def __post_init__(self) -> None:
        if self.task not in TACHES:
            raise ProviderRefused(
                f"Tâche « {self.task} » non déclarée. Connues : {list(TACHES)}."
            )
        if self.width <= 0 or self.height <= 0 or self.duration_s <= 0:
            raise ProviderRefused(
                "Une demande doit porter une taille et une durée positives : "
                "sinon aucun fournisseur ne peut être comparé à elle."
            )


def measured_vram_gb() -> Optional[float]:
    """
    La VRAM réellement disponible, ou `None` si personne ne peut la lire.

    Returns:
        La mémoire du premier GPU, en Go. `None` signifie **non mesurée** — un
        fournisseur qui exige de la VRAM est alors indisponible, pas « peut-être
        possible ». Supposer une valeur ferait accepter une génération qui
        s'arrête sur un manque de mémoire après plusieurs minutes.
    """
    sonde = probe("gpu_compute")
    if sonde["state"] != DISPONIBLE:
        return None
    try:
        import torch

        propriete = torch.cuda.get_device_properties(0)
        return round(propriete.total_memory / (1024 ** 3), 2)
    except Exception:
        return None


def evaluate(
    capability: ProviderCapability, request: GenerationRequest,
) -> Dict[str, Any]:
    """
    Dit si un fournisseur peut servir cette demande, et sinon pourquoi.

    Args:
        capability: Ce que le fournisseur déclare.
        request: Ce qui est demandé.

    Returns:
        `eligible` et la liste des **obstacles nommés**. Un fournisseur écarté
        sans raison force à tout relire ; un fournisseur écarté avec sa raison
        se corrige.
    """
    obstacles: List[str] = []

    if request.task not in capability.tasks:
        obstacles.append(
            f"ne sert pas « {request.task} » (sert : {sorted(capability.tasks)})"
        )
    if capability.max_width and request.width > capability.max_width:
        obstacles.append(
            f"largeur {request.width} > {capability.max_width}"
        )
    if capability.max_height and request.height > capability.max_height:
        obstacles.append(
            f"hauteur {request.height} > {capability.max_height}"
        )
    if capability.max_duration_s and request.duration_s > capability.max_duration_s:
        obstacles.append(
            f"durée {request.duration_s} s > {capability.max_duration_s} s"
        )
    if request.require_deterministic and not capability.deterministic:
        obstacles.append("non déterministe alors que la demande l'exige")

    for besoin in capability.requires:
        sonde = probe(besoin)
        if sonde["state"] != DISPONIBLE:
            obstacles.append(f"capacité « {besoin} » {sonde['state']}")

    if capability.min_vram_gb is not None:
        disponible = measured_vram_gb()
        if disponible is None:
            obstacles.append(
                f"exige {capability.min_vram_gb} Go de VRAM, et la VRAM n'est "
                "pas mesurable ici — la supposer ferait échouer la génération "
                "après plusieurs minutes"
            )
        elif disponible < capability.min_vram_gb:
            obstacles.append(
                f"exige {capability.min_vram_gb} Go de VRAM, {disponible} Go "
                "mesurés"
            )

    return {
        "provider_id": capability.provider_id,
        "eligible": not obstacles,
        "blockers": obstacles,
    }


def select_provider(
    request: GenerationRequest,
    capabilities: List[ProviderCapability],
    prefer: str = "declared_order",
) -> Dict[str, Any]:
    """
    Choisit un fournisseur, ou refuse en disant pourquoi chacun a été écarté.

    Args:
        request: Ce qui est demandé.
        capabilities: Les fournisseurs déclarés.
        prefer: `declared_order` (le premier éligible), `cheapest` ou
            `fastest`. Les deux derniers **excluent** les fournisseurs dont le
            coût ou la latence est inconnu.

    Returns:
        Le fournisseur retenu, ou `NO_PROVIDER` avec les obstacles de chacun.
        Aucun repli sur le plus proche : rendre du 720p à qui demande du 1080p
        est une substitution silencieuse, et le demandeur n'a aucun moyen de
        s'en apercevoir. Une dégradation est une décision, et une décision
        appartient à qui fait le film.
    """
    evaluations = [evaluate(capacite, request) for capacite in capabilities]
    eligibles = [
        capacite for capacite, verdict in zip(capabilities, evaluations)
        if verdict["eligible"]
    ]

    if not eligibles:
        return {
            "status": AUCUN,
            "request": {
                "task": request.task, "width": request.width,
                "height": request.height, "duration_s": request.duration_s,
            },
            "evaluations": evaluations,
            "reason": (
                "Aucun fournisseur déclaré ne sert cette demande. Aucun repli "
                "n'est proposé : rendre autre chose que ce qui est demandé est "
                "une substitution silencieuse, et le demandeur n'a aucun moyen "
                "de s'en apercevoir."
            ),
        }

    if prefer == "cheapest":
        connus = [c for c in eligibles if c.cost_per_second is not None]
        retenu = min(connus, key=lambda c: c.cost_per_second) if connus else None
    elif prefer == "fastest":
        connus = [c for c in eligibles if c.typical_latency_s is not None]
        retenu = min(connus, key=lambda c: c.typical_latency_s) if connus else None
    else:
        connus = eligibles
        retenu = eligibles[0]

    if retenu is None:
        return {
            "status": AUCUN,
            "evaluations": evaluations,
            "eligible_but_unranked": [c.provider_id for c in eligibles],
            "reason": (
                f"Des fournisseurs conviennent, mais aucun ne déclare son "
                f"{'coût' if prefer == 'cheapest' else 'temps de réponse'}. Un "
                "inconnu n'est pas un zéro : le classer premier est la façon "
                "dont une facture arrive."
            ),
        }

    return {
        "status": CHOISI,
        "provider_id": retenu.provider_id,
        "preference": prefer,
        "capability": retenu.as_dict(),
        "evaluations": evaluations,
        "excluded_for_unknown_metric": [
            c.provider_id for c in eligibles if c not in connus
        ],
        "reason": f"« {retenu.provider_id} » sert la demande sans obstacle.",
    }


def selection_report() -> Dict[str, Any]:
    """
    Ce que la sélection garantit, et ce qu'elle refuse.

    Returns:
        Les tâches déclarées et les règles tenues.
    """
    return {
        "tasks": list(TACHES),
        "states": [CHOISI, AUCUN],
        "preferences": ["declared_order", "cheapest", "fastest"],
        "rules": [
            "Un fournisseur **déclare** ce qu'il sait faire ; le sélecteur "
            "compare ces déclarations à ce que la machine porte réellement.",
            "Aucun repli sur le plus proche : rendre du 720p à qui demande du "
            "1080p est une substitution silencieuse. Une dégradation est une "
            "décision, et elle appartient à qui fait le film.",
            "Chaque fournisseur écarté l'est avec ses **obstacles nommés** — "
            "un refus sans raison force à tout relire.",
            "`None` n'est jamais zéro : coût inconnu, latence non mesurée, "
            "aucun GPU requis. Classer un coût inconnu au premier rang est la "
            "façon dont une facture arrive.",
            "La VRAM exigée est comparée à la VRAM **mesurée** ; non mesurable "
            "rend le fournisseur indisponible, pas « peut-être possible ».",
        ],
        "does_not": [
            "Substituer un fournisseur proche à celui qui est demandé.",
            "Traiter un coût ou une latence inconnus comme nuls.",
            "Supposer une quantité de VRAM.",
            "Inventer une latence typique (§33).",
        ],
    }
