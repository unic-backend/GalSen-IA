"""
The structured scene — and the one field in it that invites a lie.

Directive §4 specifies the record: start, end, transcript, visual summary,
detected objects and actions, `importance_score`, audio quality, semantic tags.
Eight of those are descriptions. One is a number, and it is the dangerous one.

`importance_score` is dangerous precisely because it is so easy to produce.
Every implementation reaches for `0.5` as a default, or asks a model for a float
between 0 and 1, and either way a number appears that reads like a measurement
and is not one. Downstream, the auto-editor sorts by it and drops the scenes at
the bottom. A director then asks why their best take was cut, and the honest
answer is: because a default value sorted it last.

So importance here is **composed of named measured signals or it does not
exist**. Each contributing signal is declared with its weight; a signal that was
not measured contributes nothing rather than contributing zero — those are
different, and treating an absence as a low value is exactly how a good scene
gets ranked badly. When no signal is available at all, the score is `None` with
the reason, and the caller must decide what to do rather than sort on a
fabrication.

The rest of the record follows the same discipline as `inspect.py`: every field
declares its **origin** — measured, AI-derived, or absent — because a viewer
must be able to tell what a machine observed from what a machine guessed. A
`visual_summary` written by a model and a `detected_objects` list produced by a
detector are not the same kind of claim, and merging them into one "analysis"
blob destroys the distinction permanently.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

#: D'où vient une information de scène. La distinction est celle du pare-feu de
#: Darra J, appliquée à l'image : un lecteur doit pouvoir séparer ce qu'une
#: machine a **observé** de ce qu'elle a **supposé**.
MESURE = "MEASURED"
DERIVE_IA = "AI_DERIVED"
ABSENT = "ABSENT"

#: Les signaux qui composent une importance, avec leur poids. Déclarés donc
#: contestables ; un poids implicite est un jugement que personne ne peut
#: discuter. Chacun doit être **mesurable** — aucun n'est une opinion de modèle.
SIGNAUX_IMPORTANCE = {
    "speech_ratio": 0.4,
    "visual_change": 0.3,
    "duration_share": 0.2,
    "audio_quality": 0.1,
}


class SceneRefused(ValueError):
    """Une scène qui ne peut pas être construite telle qu'elle est décrite."""


@dataclass(frozen=True)
class Scene:
    """
    Un plan et ce qu'on en sait, champ par champ, avec l'origine de chacun.

    Attributes:
        scene_id: Son identité.
        start_frame: Première trame, incluse.
        end_frame: Dernière trame, exclue.
        start_time: Début en secondes, **si** une cadence a été mesurée.
        end_time: Fin en secondes, aux mêmes conditions.
        transcript: Ce qui est dit, si une transcription existe.
        visual_summary: Ce qu'un modèle décrit de l'image.
        detected_objects: Ce qu'un détecteur a trouvé.
        detected_actions: Les actions détectées.
        audio_quality: La qualité audio mesurée, de 0 à 1.
        semantic_tags: Les étiquettes proposées par un modèle.
        origins: L'origine de chaque champ renseigné.
    """

    scene_id: str
    start_frame: int
    end_frame: int
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    transcript: Optional[str] = None
    visual_summary: Optional[str] = None
    detected_objects: Tuple[str, ...] = ()
    detected_actions: Tuple[str, ...] = ()
    audio_quality: Optional[float] = None
    semantic_tags: Tuple[str, ...] = ()
    origins: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.end_frame <= self.start_frame:
            raise SceneRefused(
                f"Scène « {self.scene_id} » vide ou inversée "
                f"({self.start_frame} → {self.end_frame}). Une scène sans trame "
                "n'a rien à montrer, et l'accepter la ferait apparaître dans un "
                "montage sans contenu."
            )
        # Les temps vont par deux. En rendre un seul laisserait un appelant
        # calculer une durée à partir d'une borne inventée.
        if (self.start_time is None) != (self.end_time is None):
            raise SceneRefused(
                f"Scène « {self.scene_id} » : une seule borne temporelle. Les "
                "temps vont par deux, sinon une durée se calcule sur une borne "
                "inventée."
            )

    @property
    def frames(self) -> int:
        """Le nombre de trames du plan."""
        return self.end_frame - self.start_frame

    @property
    def duration(self) -> Optional[float]:
        """
        La durée en secondes, ou `None` si aucune cadence n'a été mesurée.

        `None` veut dire **non mesurée**, jamais zéro : une scène de durée nulle
        et une scène dont personne n'a lu la durée ne se traitent pas pareil.
        """
        if self.start_time is None or self.end_time is None:
            return None
        return round(self.end_time - self.start_time, 4)

    def origin_of(self, champ: str) -> str:
        """L'origine d'un champ : mesuré, dérivé d'une IA, ou absent."""
        return self.origins.get(champ, ABSENT)

    @property
    def ai_derived_fields(self) -> Tuple[str, ...]:
        """
        Les champs produits par un modèle.

        Rendus séparément pour qu'une interface puisse les montrer autrement :
        fondre une description de modèle et une détection dans un même bloc
        « analyse » détruit la distinction pour de bon.
        """
        return tuple(sorted(
            nom for nom, origine in self.origins.items() if origine == DERIVE_IA
        ))

    def as_dict(self) -> Dict[str, Any]:
        """Représentation sérialisable, origines comprises."""
        return {
            "scene_id": self.scene_id,
            "start_frame": self.start_frame, "end_frame": self.end_frame,
            "frames": self.frames,
            "start_time": self.start_time, "end_time": self.end_time,
            "duration": self.duration,
            "transcript": self.transcript,
            "visual_summary": self.visual_summary,
            "detected_objects": list(self.detected_objects),
            "detected_actions": list(self.detected_actions),
            "audio_quality": self.audio_quality,
            "semantic_tags": list(self.semantic_tags),
            "origins": dict(self.origins),
            "ai_derived_fields": list(self.ai_derived_fields),
        }


def importance(
    scene: Scene,
    visual_change: Optional[float] = None,
    speech_ratio: Optional[float] = None,
    duration_share: Optional[float] = None,
    weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Compose une importance à partir des signaux **mesurés**, ou refuse d'en faire une.

    Args:
        scene: La scène.
        visual_change: Écart visuel mesuré, de 0 à 1.
        speech_ratio: Part de parole mesurée, de 0 à 1.
        duration_share: Part de la durée totale, de 0 à 1.
        weights: Les poids, si l'on veut discuter ceux par défaut.

    Returns:
        Le score, **les signaux qui l'ont composé**, ceux qui manquaient, et le
        détail du calcul. Quand aucun signal n'est mesurable, le score vaut
        `None` avec la raison : un `0.5` par défaut se lit comme une mesure, et
        le montage automatique trierait dessus. Un réalisateur demanderait alors
        pourquoi sa meilleure prise a été coupée, et la réponse honnête serait :
        parce qu'une valeur par défaut l'a classée dernière.

    Raises:
        SceneRefused: Si un signal fourni sort de [0, 1] — une part hors de cet
            intervalle n'est pas une part.
    """
    poids = dict(weights or SIGNAUX_IMPORTANCE)
    disponibles = {
        "speech_ratio": speech_ratio,
        "visual_change": visual_change,
        "duration_share": duration_share,
        "audio_quality": scene.audio_quality,
    }

    for nom, valeur in disponibles.items():
        if valeur is not None and not 0.0 <= float(valeur) <= 1.0:
            raise SceneRefused(
                f"Signal « {nom} » = {valeur} hors de [0, 1] : une part hors de "
                "cet intervalle n'est pas une part."
            )

    # Un signal non mesuré **ne contribue pas**. Le compter pour zéro
    # reviendrait à traiter une absence comme une valeur basse, ce qui est
    # exactement la façon dont une bonne scène finit mal classée.
    mesures = {nom: float(v) for nom, v in disponibles.items() if v is not None}
    manquants = sorted(set(disponibles) - set(mesures))

    if not mesures:
        return {
            "score": None,
            "used_signals": [],
            "missing_signals": manquants,
            "reason": (
                "Aucun signal mesurable. Un score par défaut se lirait comme "
                "une mesure, et le montage automatique trierait dessus."
            ),
        }

    total_poids = sum(poids.get(nom, 0.0) for nom in mesures)
    if total_poids <= 0:
        return {
            "score": None,
            "used_signals": sorted(mesures),
            "missing_signals": manquants,
            "reason": "Les signaux mesurés portent un poids total nul.",
        }

    # Renormalisé sur les seuls signaux présents : sinon une scène dont deux
    # signaux sur quatre manquent plafonnerait mécaniquement à la moitié du
    # score, ce qui punirait l'absence de mesure au lieu de la signaler.
    score = sum(poids.get(nom, 0.0) * valeur for nom, valeur in mesures.items())
    score /= total_poids

    return {
        "score": round(score, 4),
        "used_signals": sorted(mesures),
        "missing_signals": manquants,
        "weights": {nom: poids.get(nom, 0.0) for nom in sorted(mesures)},
        "contributions": {
            nom: round(poids.get(nom, 0.0) * valeur / total_poids, 4)
            for nom, valeur in sorted(mesures.items())
        },
        "partial": bool(manquants),
        "reason": (
            f"Composé de {len(mesures)} signal/signaux mesuré(s), "
            f"renormalisé sur eux. "
            + (f"Manquants, sans contribution : {', '.join(manquants)}."
               if manquants else "Tous les signaux déclarés étaient mesurables.")
        ),
    }


def scenes_from_shots(
    shots: List[Dict[str, Any]],
    fps: Optional[float] = None,
    prefix: str = "scene",
) -> List[Scene]:
    """
    Construit des scènes à partir des plans détectés.

    Args:
        shots: Les plans rendus par `detect_cuts`.
        fps: La cadence **mesurée**. Absente, les scènes n'ont pas de temps.
        prefix: Le préfixe des identifiants.

    Returns:
        Une scène par plan, avec les bornes en trames toujours, et en secondes
        seulement si la cadence a été mesurée. Les champs descriptifs restent
        vides : ce module découpe, il ne décrit pas.
    """
    scenes: List[Scene] = []
    for rang, plan in enumerate(shots, start=1):
        debut, fin = plan["start"], plan["end"]
        temps = (round(debut / fps, 4), round(fin / fps, 4)) if fps else (None, None)
        scenes.append(Scene(
            scene_id=f"{prefix}-{rang:02d}",
            start_frame=debut, end_frame=fin,
            start_time=temps[0], end_time=temps[1],
            origins={
                "start_frame": MESURE, "end_frame": MESURE,
                **({"start_time": MESURE, "end_time": MESURE} if fps else {}),
            },
        ))
    return scenes


def describe(
    scene: Scene, summary: str = "", tags: Optional[List[str]] = None,
) -> Scene:
    """
    Attache une description de modèle à une scène, **étiquetée comme telle**.

    Args:
        scene: La scène.
        summary: Le résumé visuel produit par un modèle.
        tags: Les étiquettes sémantiques proposées.

    Returns:
        Une nouvelle scène — l'originale est figée — dont les champs ajoutés
        portent l'origine `AI_DERIVED`. Les mesures existantes gardent la leur :
        une description n'a jamais transformé une observation en supposition, ni
        l'inverse.
    """
    from dataclasses import replace

    origines = dict(scene.origins)
    if summary:
        origines["visual_summary"] = DERIVE_IA
    if tags:
        origines["semantic_tags"] = DERIVE_IA

    return replace(
        scene,
        visual_summary=summary or scene.visual_summary,
        semantic_tags=tuple(tags) if tags else scene.semantic_tags,
        origins=origines,
    )


def scene_report() -> Dict[str, Any]:
    """
    Ce que la représentation de scène garantit, et ce qu'elle refuse.

    Returns:
        Les origines, les signaux d'importance, et les règles tenues.
    """
    return {
        "origins": [MESURE, DERIVE_IA, ABSENT],
        "importance_signals": dict(SIGNAUX_IMPORTANCE),
        "rules": [
            "Chaque champ déclare son **origine** : un lecteur doit pouvoir "
            "séparer ce qu'une machine a observé de ce qu'elle a supposé.",
            "L'importance est composée de signaux **mesurés** et nommés, ou "
            "elle n'existe pas. Un `0.5` par défaut se lit comme une mesure.",
            "Un signal non mesuré **ne contribue pas** — le compter pour zéro "
            "traiterait une absence comme une valeur basse.",
            "Le score est renormalisé sur les signaux présents : sinon une "
            "scène à deux signaux sur quatre plafonnerait mécaniquement, ce qui "
            "punirait l'absence de mesure au lieu de la signaler.",
            "Les temps vont par deux, et n'existent que si une cadence a été "
            "mesurée.",
            "Une durée `None` n'est pas une durée nulle.",
        ],
        "does_not": [
            "Produire un score d'importance par défaut.",
            "Demander une importance à un modèle.",
            "Fondre une description de modèle et une détection dans un même "
            "bloc « analyse ».",
            "Accepter une scène sans trame.",
        ],
    }
