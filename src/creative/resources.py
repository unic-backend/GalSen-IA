"""
Ce que la machine a vraiment, et ce qu'on refuse d'en supposer (C16, §52).

## Le piège de ce chapitre

§52 demande de suivre GPU, VRAM, processeur, mémoire, stockage, file d'attente,
chargement et déchargement de modèles, concurrence. La façon confortable de le
faire est d'écrire des valeurs par défaut — 8 Gio de VRAM, quatre travaux en
parallèle — et de router dessus. Le code tourne, les tests passent, et la
première exécution réelle se fait tuer par le noyau.

Ici, **une ressource non mesurée vaut `None`, jamais zéro et jamais un défaut**.
La distinction porte tout le module : `0 Gio de VRAM` veut dire « il n'y en a
pas », `None` veut dire « personne n'a regardé ». La première autorise à
conclure, la seconde l'interdit.

## Ce qui est mesurable ici, et ce qui ne l'est pas

Le processeur, la mémoire vive et le disque se lisent depuis le système, et sont
donc mesurés. Le GPU passe par la sonde `gpu_compute` déjà présente
(`src/media/core/capabilities.py`) — pas par un second détecteur : deux
vocabulaires pour un même geste dérivent, et ce dépôt l'a déjà payé.

Sur cette machine, la sonde répond indisponible. **La VRAM n'est donc pas
`0` : elle est inconnue.** Un fournisseur qui exige 24 Gio n'est ni accepté ni
refusé — la question n'a pas pu être posée, et le rapporter ainsi est la seule
réponse vraie.

## Ne pas charger ce dont on n'a pas besoin

§52 le dit en une ligne et c'est la seule règle de résidence ici : un modèle
reste chargé tant qu'il sert, et le déchargement est **un acte explicite**.
Rien ne décharge en silence pour faire de la place — un déchargement silencieux
transforme une exécution en attente inexpliquée, et c'est le genre de latence
que personne ne retrouve ensuite.
"""

from __future__ import annotations

import os
import shutil
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..integration.degradation import DISPONIBLE
from ..media.core.capabilities import probe
from .providers import CreativeProvider
from .routing import INDETERMINE, NON_SATISFAIT, SATISFAIT

#: Ce qu'une mesure vaut quand elle n'a pas eu lieu. Nommé, parce que `None`
#: seul se confond trop vite avec « zéro » à la lecture d'un rapport.
NON_MESURE = "NOT_MEASURED"

#: Un octet, en gibioctets. Les tailles déclarées par les fournisseurs sont en
#: Gio ; les mesures système en octets. Une seule conversion, ici.
GIO = 1024 ** 3


class ResourceRefused(ValueError):
    """Une opération de ressource impossible, avec sa raison."""


@dataclass(frozen=True)
class Resources:
    """
    Ce que la machine offre, mesuré.

    Attributes:
        cpu_count: Cœurs logiques, ou `None` si le système ne le dit pas.
        ram_gb: Mémoire vive totale, en Gio. `None` si non lisible.
        free_disk_gb: Espace libre sur le dossier de travail, en Gio.
        gpu_available: Si la sonde `gpu_compute` répond disponible.
        vram_gb: VRAM totale. **`None` ici est le cas normal** : sans GPU, la
            question n'a pas de réponse, et `0` en serait une fausse.
        gpu_reason: Ce que la sonde a dit, quand elle a dit non.
    """

    cpu_count: Optional[int] = None
    ram_gb: Optional[float] = None
    free_disk_gb: Optional[float] = None
    gpu_available: bool = False
    vram_gb: Optional[float] = None
    gpu_reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences nommées."""
        return {
            "cpu_count": self.cpu_count if self.cpu_count is not None else NON_MESURE,
            "ram_gb": self.ram_gb if self.ram_gb is not None else NON_MESURE,
            "free_disk_gb": (self.free_disk_gb if self.free_disk_gb is not None
                             else NON_MESURE),
            "gpu_available": self.gpu_available,
            "vram_gb": self.vram_gb if self.vram_gb is not None else NON_MESURE,
            "gpu_reason": self.gpu_reason,
        }


def _memoire_totale() -> Optional[float]:
    """La mémoire vive totale en Gio, ou `None` si le système ne la dit pas."""
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        taille = os.sysconf("SC_PAGE_SIZE")
    except (ValueError, OSError, AttributeError):
        # Plateforme sans `sysconf` : non mesuré, et surtout pas estimé.
        return None
    if pages < 0 or taille < 0:
        return None
    return round(pages * taille / GIO, 2)


def measure(workdir: str = ".") -> Resources:
    """
    Mesure les ressources de cette machine.

    Args:
        workdir: Le dossier dont on regarde l'espace libre.

    Returns:
        Les ressources. Tout ce qui n'a pas pu être lu vaut `None` — jamais une
        valeur par défaut. Le GPU passe par la sonde existante, jamais par une
        seconde détection.
    """
    sonde = probe("gpu_compute")
    disponible = sonde["state"] == DISPONIBLE
    try:
        libre = round(shutil.disk_usage(workdir).free / GIO, 2)
    except OSError:
        libre = None

    return Resources(
        cpu_count=os.cpu_count(),
        ram_gb=_memoire_totale(),
        free_disk_gb=libre,
        gpu_available=disponible,
        # Aucune VRAM déduite de la disponibilité : une sonde qui répond
        # « disponible » ne dit pas combien il y en a.
        vram_gb=sonde.get("vram_gb"),
        gpu_reason="" if disponible else sonde.get("reason", ""),
    )


def fits(provider: CreativeProvider, resources: Resources) -> Dict[str, Any]:
    """
    Dit si un fournisseur tient dans ce que la machine offre.

    Args:
        provider: Le fournisseur déclaré.
        resources: Ce qui a été mesuré.

    Returns:
        Un verdict par ressource, dans le vocabulaire du routeur — `MET`,
        `UNMET`, `UNKNOWN`. Un besoin déclaré confronté à une mesure absente
        est `UNKNOWN`, jamais `MET` : conclure qu'il tient sans avoir mesuré
        est exactement la supposition qui se fait tuer par le noyau.
    """
    verdicts = []

    if provider.min_vram_gb is None:
        verdicts.append({"resource": "vram", "verdict": INDETERMINE,
                         "reason": "Le fournisseur ne déclare aucun besoin."})
    elif resources.vram_gb is None:
        verdicts.append({
            "resource": "vram", "verdict": INDETERMINE,
            "required_gb": provider.min_vram_gb,
            "reason": (
                f"{provider.min_vram_gb} Gio demandés, VRAM non mesurée "
                f"({resources.gpu_reason or 'aucun GPU détecté'}). La question "
                "n'a pas pu être posée ; y répondre « oui » ou « non » serait "
                "inventé."
            ),
        })
    else:
        tient = provider.min_vram_gb <= resources.vram_gb
        verdicts.append({
            "resource": "vram",
            "verdict": SATISFAIT if tient else NON_SATISFAIT,
            "required_gb": provider.min_vram_gb,
            "available_gb": resources.vram_gb,
            "reason": "" if tient else (
                f"{provider.min_vram_gb} Gio demandés, "
                f"{resources.vram_gb} Gio disponibles."
            ),
        })

    if "gpu_compute" in provider.requires:
        verdicts.append({
            "resource": "gpu",
            "verdict": SATISFAIT if resources.gpu_available else NON_SATISFAIT,
            "reason": "" if resources.gpu_available else (
                resources.gpu_reason or "La sonde `gpu_compute` répond indisponible."
            ),
        })

    refuses = [v["resource"] for v in verdicts if v["verdict"] == NON_SATISFAIT]
    inconnus = [v["resource"] for v in verdicts if v["verdict"] == INDETERMINE]
    return {
        "provider_id": provider.provider_id,
        "verdicts": verdicts,
        "unmet": refuses,
        "unknown": inconnus,
        "loadable": not refuses,
        "note": (
            "`loadable` veut dire « rien ne s'y oppose de façon mesurée ». "
            "Ce n'est pas « ça tiendra » : les ressources listées sous "
            "`unknown` n'ont pas été vérifiées."
        ) if inconnus else "",
    }


@dataclass
class ResidencySet:
    """
    Les modèles chargés, et ce qui décide d'en charger un de plus.

    Rien ne se décharge tout seul. §52 demande d'éviter de charger des modèles
    inutiles ; il ne demande pas de les faire disparaître sous les pieds d'une
    exécution en cours. Un déchargement silencieux transforme un travail en
    attente inexpliquée, et cette latence-là ne se retrouve jamais.

    Attributes:
        max_resident: Combien de modèles peuvent rester chargés. `None` veut
            dire « aucune limite déclarée » — et non « autant qu'on veut » :
            `admit()` le rapporte alors comme non borné plutôt que de choisir
            un nombre.
    """

    max_resident: Optional[int] = None
    _charges: Dict[str, float] = field(default_factory=dict)

    def loaded(self) -> List[str]:
        """Les modèles chargés, du plus ancien usage au plus récent."""
        return [nom for nom, _ in sorted(self._charges.items(),
                                         key=lambda couple: couple[1])]

    def touch(self, provider_id: str) -> None:
        """Note qu'un modèle vient de servir."""
        if provider_id not in self._charges:
            raise ResourceRefused(
                f"« {provider_id} » n'est pas chargé : il ne peut pas servir."
            )
        self._charges[provider_id] = time.time()

    def admit(
        self, provider: CreativeProvider, resources: Resources,
    ) -> Dict[str, Any]:
        """
        Décide si un modèle peut être chargé, et ce qu'il faudrait libérer.

        Args:
            provider: Le fournisseur à charger.
            resources: Ce qui a été mesuré.

        Returns:
            La décision. Quand la limite de résidence est atteinte, le retour
            **nomme** ce qu'il faudrait décharger — le moins récemment utilisé
            — sans le faire. La décision de libérer appartient à l'appelant,
            qui seul sait si ce modèle sert encore.
        """
        if provider.provider_id in self._charges:
            return {"decision": "ALREADY_RESIDENT",
                    "provider_id": provider.provider_id,
                    "loaded": self.loaded()}

        tenue = fits(provider, resources)
        if not tenue["loadable"]:
            return {"decision": "REFUSED", "provider_id": provider.provider_id,
                    "fit": tenue, "loaded": self.loaded(),
                    "reason": f"Ressources insuffisantes : {tenue['unmet']}."}

        if self.max_resident is None:
            return {"decision": "ADMITTED", "provider_id": provider.provider_id,
                    "fit": tenue, "loaded": self.loaded(),
                    "residency_limit": NON_MESURE,
                    "reason": (
                        "Aucune limite de résidence déclarée. Ce n'est pas "
                        "« autant qu'on veut » : c'est un chiffre que "
                        "personne n'a posé, et l'admission ne s'appuie donc "
                        "que sur les ressources."
                    )}

        if len(self._charges) < self.max_resident:
            return {"decision": "ADMITTED", "provider_id": provider.provider_id,
                    "fit": tenue, "loaded": self.loaded()}

        candidats = self.loaded()
        return {
            "decision": "EVICTION_REQUIRED",
            "provider_id": provider.provider_id,
            "fit": tenue,
            "loaded": candidats,
            "would_evict": candidats[0],
            "reason": (
                f"{len(self._charges)} modèles chargés pour une limite de "
                f"{self.max_resident}. Le moins récemment utilisé est nommé, "
                "et **rien n'est déchargé ici** : seul l'appelant sait si ce "
                "modèle sert encore à une exécution en cours."
            ),
        }

    def load(self, provider_id: str) -> None:
        """Enregistre un chargement décidé par l'appelant."""
        self._charges[provider_id] = time.time()

    def unload(self, provider_id: str) -> None:
        """
        Décharge un modèle, explicitement.

        Raises:
            ResourceRefused: Modèle non chargé — décharger ce qui n'est pas là
                masquerait une erreur de comptage de l'appelant.
        """
        if provider_id not in self._charges:
            raise ResourceRefused(
                f"« {provider_id} » n'est pas chargé. Décharger ce qui n'est "
                "pas là masquerait une erreur de comptage."
            )
        del self._charges[provider_id]


def resources_report(workdir: str = ".") -> Dict[str, Any]:
    """
    Ce que la machine offre et ce que la plateforme refuse d'en déduire.

    Returns:
        Les mesures, et les règles. Sur cette machine, la VRAM est
        `NOT_MEASURED` et non `0` — la différence décide de tout ce qui suit.
    """
    mesures = measure(workdir)
    return {
        "measured": mesures.as_dict(),
        "tracked": ["cpu", "ram", "disk", "gpu", "vram", "residency"],
        "not_tracked": [
            {"resource": "queue depth",
             "reason": "Le système de travaux existe déjà ; la phase 16.2 s'y "
                       "raccorde au lieu d'en compter un second."},
        ],
        "rules": [
            "Une ressource non mesurée vaut `None`, jamais `0` et jamais un "
            "défaut : `0 Gio` conclut, `None` interdit de conclure.",
            "Un besoin déclaré confronté à une mesure absente est `UNKNOWN`, "
            "jamais `MET` — c'est la supposition qui se fait tuer par le noyau.",
            "Le GPU passe par la sonde `gpu_compute` existante, jamais par un "
            "second détecteur.",
            "Rien ne se décharge en silence : `admit()` **nomme** ce qu'il "
            "faudrait libérer, l'appelant décide.",
            "Aucune limite de résidence déclarée n'est « pas de limite » : "
            "c'est un chiffre que personne n'a posé, et le rapport le dit.",
        ],
    }
