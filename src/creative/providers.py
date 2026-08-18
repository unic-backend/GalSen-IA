"""
One provider contract for the whole creative surface, and the two things it
refuses to let a router forget.

Directive §34 lists twenty provider interfaces to create. Its next sentence
forbids duplicating abstractions that already exist, and ADR-024 resolves the
tension: **tasks are declared data, not subclasses.** Twenty abstract classes
whose only difference is a method name is a taxonomy, not a design — and every
one of them becomes a place where the registry and the router can disagree.

What this module adds to `src/media/providers/base.py`, which it extends rather
than replaces:

**Licence is a routing input.** Not metadata, not a footnote in a comparison
table — a field the selector reads and refuses on. C01–C02 measured why: eight
of nine candidate weight licences are `UNKNOWN` because `huggingface.co` has no
route from this container, and one candidate is copyleft. A router that cannot
see a licence will, sooner or later, route a paying customer's job to a model
nobody is allowed to use commercially. §40 says the distinction matters; this is
where it is enforced instead of remembered.

**A declaration is not an availability.** What a provider *claims* it can do and
what this machine can *reach* are different facts and both are needed. Today
every probe answers `UNAVAILABLE` — no GPU, no `torch` — and that is the honest
state, not a defect. A provider that cannot run reports it; it never returns a
plausible result.

**Invocation mode is declared.** Calling a GPL-3.0 tool as an isolated process
is not the same act as linking it into this repository, and the difference has
legal consequences. `OUT_OF_PROCESS` is therefore a property of the provider,
visible where the decision is made.

Nothing here selects a provider for real work. Selection needs a licence
cleared and a capability measured, and as of this writing neither exists for any
candidate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Tuple

from ..integration.degradation import DISPONIBLE
from ..media.core.capabilities import CAPACITES, probe

#: Les tâches créatives déclarées (§34). Ce sont des **valeurs**, pas des
#: classes : l'écosystème invente une tâche par trimestre, et une valeur
#: s'ajoute là où une interface se propage.
TACHES_CREATIVES: Tuple[str, ...] = (
    # Vidéo
    "text_to_video", "image_to_video", "video_to_video",
    "audio_to_video", "character_animation",
    # Image
    "text_to_image", "image_to_image", "upscale", "interpolate",
    # Audio et parole
    "speech_recognition", "speaker_diarization", "voice_conversion",
    "speech_synthesis", "audio_generation", "music_generation",
    # Compréhension
    "multimodal_understanding", "scene_understanding", "reference_analysis",
    # Post-production
    "lip_sync", "video_editing", "identity_verification",
)

#: Comment un fournisseur est appelé. `OUT_OF_PROCESS` n'est pas un détail de
#: déploiement : c'est ce qui sépare *appeler* un outil copyleft de *l'intégrer*.
DANS_LE_PROCESSUS = "IN_PROCESS"
HORS_PROCESSUS = "OUT_OF_PROCESS"
PAR_API = "API"
MODES_D_INVOCATION = (DANS_LE_PROCESSUS, HORS_PROCESSUS, PAR_API)

#: Le droit commercial, repris **tel quel** du dossier de recherche. Aucun de
#: ces états ne se déduit d'une licence de dépôt.
COMMERCIAL_AUTORISE = "ALLOWED"
COMMERCIAL_RESTREINT = "RESTRICTED"
COMMERCIAL_PARTIEL = "PARTIAL"
COMMERCIAL_INCONNU = "UNKNOWN"
ETATS_COMMERCIAUX = (COMMERCIAL_AUTORISE, COMMERCIAL_RESTREINT,
                     COMMERCIAL_PARTIEL, COMMERCIAL_INCONNU)

#: L'état d'un fournisseur au registre. Repris de `degradation.py` pour les
#: trois premiers ; deux s'ajoutent parce qu'ils disent autre chose.
EXPERIMENTAL = "EXPERIMENTAL"
DESACTIVE = "DISABLED"

#: Ce qu'une sélection peut donner.
CHOISI = "SELECTED"
AUCUN = "NO_PROVIDER"


class ProviderRefused(ValueError):
    """Une déclaration ou une sélection impossible, avec sa raison."""


@dataclass(frozen=True)
class LicenceRecord:
    """
    Ce qu'on sait du droit d'usage — et ce qu'on n'en sait pas.

    Attributes:
        repository: La licence du dépôt, si elle a été lue.
        weights: La licence des poids, si elle a été lue. `UNKNOWN` est le cas
            normal, pas l'exception.
        dataset: La licence des données d'entraînement.
        commercial: L'état commercial, parmi `ETATS_COMMERCIAUX`.
        verified_from: L'URL réellement lue. Sans elle, rien n'est vérifié.
        restrictions: Les restrictions connues, en clair.
    """

    repository: str = COMMERCIAL_INCONNU
    weights: str = COMMERCIAL_INCONNU
    dataset: str = COMMERCIAL_INCONNU
    commercial: str = COMMERCIAL_INCONNU
    verified_from: str = ""
    restrictions: str = ""

    def __post_init__(self) -> None:
        if self.commercial not in ETATS_COMMERCIAUX:
            raise ProviderRefused(
                f"État commercial « {self.commercial} » non déclaré. "
                f"Déclarés : {list(ETATS_COMMERCIAUX)}."
            )
        if self.commercial == COMMERCIAL_AUTORISE and not self.verified_from.strip():
            # La règle que `src/creative/research.py` tient sur le dossier de
            # recherche, tenue une seconde fois là où la décision se prend.
            raise ProviderRefused(
                "Un usage commercial `ALLOWED` sans source vérifiée. Une "
                "licence de dépôt permissive n'est pas une permission d'usage "
                "des poids — c'est la confusion que §40 existe pour empêcher."
            )

    @property
    def usable_commercially(self) -> bool:
        """Vrai seulement si le droit a été **établi**, jamais supposé."""
        return self.commercial == COMMERCIAL_AUTORISE

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable."""
        return {
            "repository": self.repository, "weights": self.weights,
            "dataset": self.dataset, "commercial": self.commercial,
            "verified_from": self.verified_from,
            "restrictions": self.restrictions,
            "usable_commercially": self.usable_commercially,
        }


@dataclass(frozen=True)
class CreativeProvider:
    """
    Un fournisseur déclaré : ce qu'il prétend faire, ce qu'il exige, son droit.

    Attributes:
        provider_id: Son identité stable.
        version: La version du modèle ou du dépôt.
        tasks: Les tâches servies, parmi `TACHES_CREATIVES`.
        input_modalities: Ce qu'il accepte — `text`, `image`, `video`, `audio`.
        output_modalities: Ce qu'il produit.
        requires: Les capacités machine nécessaires (`core.capabilities`).
        min_vram_gb: VRAM minimale. `None` = **aucun GPU requis**, pas « 0 Go ».
        licence: Ce qu'on sait du droit d'usage.
        invocation: Comment il est appelé.
        runs_locally: Déclare que le fournisseur ne demande **rien** au-delà
            de Python. Faux par défaut : ne rien exiger est presque toujours le
            signe que personne n'a déclaré les exigences, pas qu'il n'y en a
            pas.
        deterministic: Si deux appels identiques rendent le même résultat.
        cost_per_second: `None` = **inconnu**, jamais gratuit.
        typical_latency_s: `None` = personne ne l'a mesurée.
        capability_status: Par champ, ce que le fournisseur supporte (§9).
        limitations: Ce qu'il ne fait pas, écrit plutôt que sous-entendu.
    """

    provider_id: str
    version: str = ""
    tasks: FrozenSet[str] = frozenset()
    input_modalities: Tuple[str, ...] = ()
    output_modalities: Tuple[str, ...] = ()
    requires: Tuple[str, ...] = ()
    min_vram_gb: Optional[float] = None
    licence: LicenceRecord = field(default_factory=LicenceRecord)
    invocation: str = DANS_LE_PROCESSUS
    runs_locally: bool = False
    deterministic: bool = False
    cost_per_second: Optional[float] = None
    typical_latency_s: Optional[float] = None
    capability_status: Dict[str, str] = field(default_factory=dict)
    limitations: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not str(self.provider_id or "").strip():
            raise ProviderRefused("Un fournisseur sans identité ne peut être cité.")
        inconnues = sorted(set(self.tasks) - set(TACHES_CREATIVES))
        if inconnues:
            raise ProviderRefused(
                f"« {self.provider_id} » déclare des tâches inconnues : "
                f"{inconnues}. Générer depuis un texte et depuis un audio sont "
                "deux capacités différentes, pas deux nuances d'une même."
            )
        if self.invocation not in MODES_D_INVOCATION:
            raise ProviderRefused(
                f"Mode d'invocation « {self.invocation} » non déclaré. "
                f"Déclarés : {list(MODES_D_INVOCATION)}."
            )
        capacites_inconnues = sorted(set(self.requires) - set(CAPACITES))
        if capacites_inconnues:
            raise ProviderRefused(
                f"« {self.provider_id} » exige des capacités non déclarées : "
                f"{capacites_inconnues}. Une capacité inventée au moment de "
                "s'en servir n'apparaît dans aucun rapport."
            )

    def serves(self, task: str) -> bool:
        """Indique si le fournisseur déclare servir cette tâche."""
        return task in self.tasks

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, absences comprises."""
        return {
            "provider_id": self.provider_id, "version": self.version,
            "tasks": sorted(self.tasks),
            "input_modalities": list(self.input_modalities),
            "output_modalities": list(self.output_modalities),
            "requires": list(self.requires),
            "min_vram_gb": self.min_vram_gb,
            "licence": self.licence.as_dict(),
            "invocation": self.invocation,
            "runs_locally": self.runs_locally,
            "deterministic": self.deterministic,
            "cost_per_second": self.cost_per_second,
            "typical_latency_s": self.typical_latency_s,
            "capability_status": dict(self.capability_status),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class CreativeRequest:
    """
    Ce qu'on demande, y compris les contraintes qui ne sont pas techniques.

    Attributes:
        task: La tâche voulue.
        commercial: Si le résultat sera exploité commercialement. C'est une
            contrainte de sélection, pas une préférence.
        require_deterministic: Exiger un fournisseur reproductible.
        allow_out_of_process: Autoriser un fournisseur appelé hors processus.
        max_cost_per_second: Plafond de coût, si le demandeur en pose un.
    """

    task: str
    commercial: bool = False
    require_deterministic: bool = False
    allow_out_of_process: bool = True
    max_cost_per_second: Optional[float] = None

    def __post_init__(self) -> None:
        if self.task not in TACHES_CREATIVES:
            raise ProviderRefused(
                f"Tâche « {self.task} » non déclarée. Déclarées : "
                f"{list(TACHES_CREATIVES)}."
            )


def availability(provider: CreativeProvider) -> Dict[str, Any]:
    """
    Ce que **cette machine** peut atteindre, mesuré par les sondes.

    Args:
        provider: Le fournisseur déclaré.

    Returns:
        Son état et ce qui lui manque. Une déclaration dit ce qu'un fournisseur
        prétend ; une sonde dit ce qui est joignable. Les confondre fait router
        un travail vers un modèle qui n'existe pas ici.
    """
    if not provider.requires and provider.min_vram_gb is None \
            and not provider.runs_locally:
        # Le défaut trouvé en exécutant : sans exigence déclarée, la sonde ne
        # trouve rien à reprocher et rend « disponible » — pour un modèle de
        # 14 milliards de paramètres sur une machine sans GPU. Ne rien exiger
        # n'est pas tourner partout : c'est n'avoir rien déclaré.
        return {
            "provider_id": provider.provider_id,
            "state": "UNKNOWN",
            "missing": [],
            "reason": (
                "Aucune exigence déclarée et `runs_locally` non affirmé. Une "
                "sonde ne peut rien constater : l'état est inconnu, pas "
                "disponible."
            ),
        }

    manquantes = []
    for capacite in provider.requires:
        resultat = probe(capacite)
        if resultat["state"] != DISPONIBLE:
            manquantes.append({"capability": capacite,
                               "state": resultat["state"],
                               "reason": resultat["reason"]})

    if provider.min_vram_gb is not None:
        from ..media.providers.base import measured_vram_gb

        vram = measured_vram_gb()
        if vram is None:
            manquantes.append({
                "capability": "gpu_compute", "state": "UNAVAILABLE",
                "reason": (
                    "VRAM non mesurée. Ce n'est pas « peut-être assez » : un "
                    "fournisseur qui exige de la VRAM sur une machine où "
                    "personne ne peut la lire est indisponible."
                ),
            })
        elif vram < provider.min_vram_gb:
            manquantes.append({
                "capability": "gpu_compute", "state": "UNAVAILABLE",
                "reason": f"{vram} Go mesurés pour {provider.min_vram_gb} Go exigés.",
            })

    return {
        "provider_id": provider.provider_id,
        "state": DISPONIBLE if not manquantes else "UNAVAILABLE",
        "missing": manquantes,
        "reason": "" if not manquantes else "Capacités absentes de cette machine.",
    }


def evaluate(provider: CreativeProvider,
             request: CreativeRequest) -> Dict[str, Any]:
    """
    Dit si un fournisseur peut servir cette demande, et sinon **pourquoi pas**.

    Args:
        provider: Le fournisseur déclaré.
        request: Ce qui est demandé.

    Returns:
        L'éligibilité et la liste des obstacles. Un refus sans raison fait
        chercher au mauvais endroit.
    """
    obstacles: List[str] = []

    if not provider.serves(request.task):
        obstacles.append(f"ne sert pas la tâche « {request.task} »")

    if request.commercial and not provider.licence.usable_commercially:
        obstacles.append(
            f"droit commercial « {provider.licence.commercial} » : un usage "
            "commercial exige un droit **établi**, pas l'absence d'interdiction "
            f"connue{f' ({provider.licence.restrictions})' if provider.licence.restrictions else ''}"
        )

    if request.require_deterministic and not provider.deterministic:
        obstacles.append("non déterministe alors que la demande l'exige")

    if not request.allow_out_of_process and provider.invocation == HORS_PROCESSUS:
        obstacles.append(
            "appelé hors processus alors que la demande ne l'autorise pas"
        )

    if request.max_cost_per_second is not None:
        if provider.cost_per_second is None:
            obstacles.append(
                "coût inconnu alors qu'un plafond est posé — un coût inconnu "
                "n'est pas un coût nul"
            )
        elif provider.cost_per_second > request.max_cost_per_second:
            obstacles.append(
                f"coût {provider.cost_per_second} au-dessus du plafond "
                f"{request.max_cost_per_second}"
            )

    etat = availability(provider)
    if etat["state"] == "UNKNOWN":
        obstacles.append(
            "disponibilité inconnue : aucune exigence déclarée, donc rien à "
            "sonder. Un inconnu n'est pas un feu vert."
        )
    elif etat["state"] != DISPONIBLE:
        obstacles.append(
            "indisponible ici : "
            + ", ".join(m["capability"] for m in etat["missing"])
        )

    return {
        "provider_id": provider.provider_id,
        "eligible": not obstacles,
        "obstacles": obstacles,
        "availability": etat,
    }


class ProviderRegistry:
    """
    Le catalogue des fournisseurs déclarés.

    Il ne remplace pas `src/model_engine/providers/` ni `src/multimodal/` : ces
    familles gardent leurs interfaces et leurs tests, et sont **adaptées** ici
    (ADR-024). Réécrire du code qui marche pour une symétrie dont personne
    n'avait besoin serait la destruction que §75 interdit.
    """

    def __init__(self) -> None:
        self._fournisseurs: Dict[str, CreativeProvider] = {}
        self._etats: Dict[str, str] = {}

    def register(self, provider: CreativeProvider,
                 state: str = "") -> CreativeProvider:
        """
        Inscrit un fournisseur.

        Args:
            provider: Le fournisseur déclaré.
            state: `EXPERIMENTAL` ou `DISABLED` pour marquer un fournisseur qui
                ne doit pas être choisi malgré sa déclaration. Vide = l'état
                vient de la sonde.

        Raises:
            ProviderRefused: Sur un identifiant déjà pris — écraser
                silencieusement ferait disparaître une déclaration que
                quelqu'un a écrite.
        """
        if provider.provider_id in self._fournisseurs:
            raise ProviderRefused(
                f"« {provider.provider_id} » est déjà inscrit. L'écraser ferait "
                "disparaître une déclaration sans que personne le voie."
            )
        if state and state not in (EXPERIMENTAL, DESACTIVE):
            raise ProviderRefused(
                f"État « {state} » non déclaré. Déclarés : "
                f"{[EXPERIMENTAL, DESACTIVE]}, ou vide pour laisser la sonde décider."
            )
        self._fournisseurs[provider.provider_id] = provider
        if state:
            self._etats[provider.provider_id] = state
        return provider

    def get(self, provider_id: str) -> Optional[CreativeProvider]:
        """Un fournisseur par son identité."""
        return self._fournisseurs.get(provider_id)

    def providers(self) -> List[CreativeProvider]:
        """Tous les fournisseurs inscrits."""
        return list(self._fournisseurs.values())

    def for_task(self, task: str) -> List[CreativeProvider]:
        """Ceux qui déclarent servir cette tâche."""
        return [f for f in self._fournisseurs.values() if f.serves(task)]

    def state_of(self, provider_id: str) -> str:
        """
        L'état d'un fournisseur : déclaré s'il l'a été, mesuré sinon.

        Un `DISABLED` déclaré l'emporte sur une sonde disponible : quelqu'un a
        décidé de l'écarter, et une sonde ne contredit pas une décision.
        """
        fournisseur = self._fournisseurs.get(provider_id)
        if fournisseur is None:
            raise ProviderRefused(f"Fournisseur « {provider_id} » inconnu.")
        declare = self._etats.get(provider_id)
        if declare:
            return declare
        return availability(fournisseur)["state"]

    def select(self, request: CreativeRequest) -> Dict[str, Any]:
        """
        Choisit un fournisseur, ou refuse en disant pourquoi chacun est écarté.

        Returns:
            Le fournisseur retenu, ou `NO_PROVIDER` avec les obstacles de
            chacun. **Aucun repli sur le plus proche** : servir autre chose que
            ce qui est demandé est une substitution silencieuse, et le demandeur
            n'a aucun moyen de s'en apercevoir.
        """
        evaluations = []
        eligibles = []
        for fournisseur in self._fournisseurs.values():
            if self._etats.get(fournisseur.provider_id) == DESACTIVE:
                evaluations.append({
                    "provider_id": fournisseur.provider_id, "eligible": False,
                    "obstacles": ["désactivé par déclaration"],
                })
                continue
            verdict = evaluate(fournisseur, request)
            evaluations.append(verdict)
            if verdict["eligible"]:
                eligibles.append(fournisseur)

        if not eligibles:
            return {
                "status": AUCUN,
                "task": request.task,
                "commercial": request.commercial,
                "evaluations": evaluations,
                "reason": (
                    "Aucun fournisseur déclaré ne sert cette demande. Aucun "
                    "repli n'est proposé : servir autre chose que ce qui est "
                    "demandé est une substitution silencieuse."
                ),
            }

        return {
            "status": CHOISI,
            "provider_id": eligibles[0].provider_id,
            "task": request.task,
            "evaluations": evaluations,
            "note": (
                "Premier éligible dans l'ordre d'inscription. Un classement par "
                "coût ou latence exigerait des chiffres mesurés ; aucun n'existe."
            ),
        }

    def report(self) -> Dict[str, Any]:
        """L'état du registre, sans rien arrondir."""
        fournisseurs = self.providers()
        return {
            "count": len(fournisseurs),
            "tasks_served": sorted({t for f in fournisseurs for t in f.tasks}),
            "tasks_unserved": sorted(set(TACHES_CREATIVES)
                                     - {t for f in fournisseurs for t in f.tasks}),
            "commercially_usable": [
                f.provider_id for f in fournisseurs
                if f.licence.usable_commercially
            ],
            "by_state": {
                f.provider_id: self.state_of(f.provider_id)
                for f in fournisseurs
            },
            "note": (
                "`tasks_unserved` est la liste utile : elle dit ce que la "
                "plateforme ne peut pas faire, au lieu de laisser croire que "
                "l'absence de fournisseur est une absence de besoin."
            ),
        }


def adapt_declared(entries: Sequence[Dict[str, Any]]) -> List[CreativeProvider]:
    """
    Adapte des entrées du dossier de recherche en fournisseurs déclarés.

    Args:
        entries: Des candidats issus de `corpus/creative/providers.yaml`.

    Returns:
        Les fournisseurs correspondants. Le droit commercial est **repris tel
        quel** : un candidat dont la licence des poids est inconnue arrive ici
        avec `UNKNOWN`, et le sélecteur le refusera pour tout travail
        commercial. C'est le point de la chaîne où §40 cesse d'être une note de
        document et devient un refus.
    """
    fournisseurs = []
    for entree in entries:
        taches = frozenset(t for t in (entree.get("tasks") or [])
                           if t in TACHES_CREATIVES)
        licence = LicenceRecord(
            repository=entree.get("repository_license", COMMERCIAL_INCONNU),
            weights=entree.get("weight_license", COMMERCIAL_INCONNU),
            dataset=entree.get("dataset_license", COMMERCIAL_INCONNU),
            commercial=entree.get("commercial_status", COMMERCIAL_INCONNU),
            verified_from=entree.get("repository_license_source", ""),
            restrictions=entree.get("repository_license_note", ""),
        )
        fournisseurs.append(CreativeProvider(
            provider_id=entree["id"],
            tasks=taches,
            min_vram_gb=entree.get("vram_gb_min"),
            licence=licence,
            invocation=(HORS_PROCESSUS
                        if "GPL" in str(entree.get("repository_license", ""))
                        else DANS_LE_PROCESSUS),
            limitations=tuple(entree.get("limitations") or ()),
        ))
    return fournisseurs


def provider_report() -> Dict[str, Any]:
    """
    Ce que le contrat de fournisseur garantit, et ce qu'il refuse.

    Returns:
        Le vocabulaire déclaré et les règles tenues.
    """
    return {
        "tasks": list(TACHES_CREATIVES),
        "invocation_modes": list(MODES_D_INVOCATION),
        "commercial_states": list(ETATS_COMMERCIAUX),
        "rules": [
            "Les tâches sont des **valeurs**, pas des classes : vingt "
            "interfaces dont la seule différence est un nom de méthode font "
            "vingt endroits où le registre et le routeur peuvent diverger.",
            "La licence est une **entrée de routage** : un travail commercial "
            "exige un droit établi, jamais l'absence d'interdiction connue.",
            "Une déclaration n'est pas une disponibilité : ce qu'un "
            "fournisseur prétend et ce que la machine atteint sont deux faits.",
            "Le mode d'invocation est déclaré : appeler un outil copyleft hors "
            "processus n'est pas l'intégrer.",
            "Un coût ou une latence inconnus **excluent** d'un classement ; "
            "un inconnu n'est pas un zéro.",
            "Aucun repli sur le plus proche : servir autre chose que ce qui "
            "est demandé est une substitution silencieuse.",
        ],
        "does_not": [
            "Remplacer `model_engine` ou `multimodal` : ils sont adaptés.",
            "Déduire un droit commercial d'une licence de dépôt.",
            "Choisir un fournisseur dont la capacité n'est pas atteignable.",
            "Classer sur des chiffres que personne n'a mesurés.",
        ],
    }
