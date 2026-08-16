"""
Turning reference media into observations — and refusing to turn it into more.

This is the module where a reference system usually starts lying, and it does it
by being helpful. Given three photos, the obvious thing to produce is a filled-in
description: build, hair, distinguishing features, a similarity vector. All of it
would run here. Almost none of it would be *measured*.

What this machine can actually do to an image was measured, not assumed:
`image_analysis` is `AVAILABLE` (OpenCV 5.0, Pillow 12.3), so dimensions,
aspect and dominant colours are real observations. **Face detection is not
available** — `HaarCascadeFaceDetector.is_available()` is `False`, because
headless OpenCV no longer ships cascade files. Video decoding is `DEGRADED`.
There is no GPU and no `torch`.

So ingestion produces:

- **measured observations** for what the tools genuinely report, each naming the
  tool that produced it;
- **declared absences** for everything identity-related, each naming the
  capability that would enable it.

§10 asks for multi-image evidence to be combined "when technically possible" and
adds: *do not assume perfect 3D reconstruction, do not fabricate hidden
geometry, confidence must be represented.* Combining here means **agreement
across sources raises confidence and disagreement lowers it** — never that two
frontal photos produce a profile.

§11 asks that video not be treated as unrelated frames. It is not treated as
anything yet: decoding is degraded, so a video reference is registered with its
hash and reported unanalysed, with the reason. That is the honest state, and it
is one probe away from changing.
"""

from __future__ import annotations

import os
import statistics
import uuid
from typing import Any, Dict, List, Sequence

from ...integration.degradation import DISPONIBLE
from ...media.core.capabilities import probe
from .entity import (
    ABSENT,
    MESURE,
    Observation,
    ReferenceEntity,
    ReferenceRefused,
    SourceMedium,
    file_digest,
)

#: Les champs qu'on sait mesurer ici, avec l'outil qui les mesure.
CHAMPS_MESURABLES = {
    "dimensions": "Pillow",
    "aspect_ratio": "Pillow",
    "dominant_colours": "Pillow",
}

#: Les champs qu'on ne sait **pas** mesurer, avec la capacité qui manque. Ils
#: sont déclarés ici plutôt que laissés vides : un champ absent d'un rapport se
#: lit comme un champ sans objet, et celui-ci a un objet très précis.
CHAMPS_BLOQUES = {
    "facial_characteristics": (
        "face_detection",
        "Aucune cascade de détection de visages n'est disponible "
        "(`HaarCascadeFaceDetector.is_available()` est faux : les "
        "distributions OpenCV sans interface ne livrent plus les fichiers de "
        "cascade). Sans elle, rien de facial n'est mesurable.",
    ),
    "body_characteristics": (
        "pose_estimation",
        "Aucun estimateur de pose n'existe dans ce dépôt ni dans cet "
        "environnement.",
    ),
    "geometry": (
        "depth_or_multiview_reconstruction",
        "Aucune reconstruction. §10 l'interdit explicitement : une géométrie "
        "cachée déduite de trois photos de face est inventée.",
    ),
    "motion_characteristics": (
        "video_decode",
        "Le décodage vidéo est dégradé sur cette machine ; aucun mouvement "
        "n'a été observé.",
    ),
    "voice_reference": (
        "audio_decode",
        "Aucun décodeur audio disponible : la piste n'a pas été lue.",
    ),
    "identity": (
        "identity_verification",
        "Aucune mesure d'identité n'existe ici, et ADR-026 refuse d'en "
        "inventer une : un score composite se lirait comme une vérité "
        "d'identité.",
    ),
}

#: Nombre de couleurs dominantes relevées. Trois : assez pour caractériser une
#: image, assez peu pour que la mesure reste stable d'une photo à l'autre.
COULEURS_DOMINANTES = 3


def _lire_image(chemin: str) -> Any:
    """Ouvre une image, ou refuse en nommant la cause."""
    try:
        from PIL import Image
    except ImportError as erreur:  # pragma: no cover - Pillow est déclaré
        raise ReferenceRefused(
            "Pillow est absent : aucune image ne peut être lue."
        ) from erreur
    try:
        return Image.open(chemin)
    except Exception as erreur:
        raise ReferenceRefused(
            f"« {chemin} » n'a pas pu être lu comme une image : "
            f"{type(erreur).__name__}. Une extension n'est pas une preuve de "
            "format."
        ) from erreur


def analyse_image(path: str, medium_id: str = "") -> List[Observation]:
    """
    Mesure ce qu'une image porte réellement.

    Args:
        path: Le fichier image.
        medium_id: L'identité du média, pour la traçabilité.

    Returns:
        Les observations **mesurées** — dimensions, rapport, couleurs
        dominantes — chacune nommant l'outil qui l'a produite. Rien qui touche
        à l'identité n'est produit ici : voir `CHAMPS_BLOQUES`.

    Raises:
        ReferenceRefused: Si le fichier n'est pas lisible comme image.
    """
    image = _lire_image(path)
    largeur, hauteur = image.size
    source = (medium_id,) if medium_id else ()

    petite = image.convert("RGB").resize((32, 32))
    # `tobytes()` plutôt que `getdata()` : ce dernier est déprécié et disparaît
    # dans Pillow 14, et une mesure qui cesse de fonctionner à une mise à jour
    # n'est pas une mesure sur laquelle bâtir.
    octets = petite.tobytes()
    couleurs: Dict[tuple, int] = {}
    for debut in range(0, len(octets), 3):
        arrondi = tuple((composante // 32) * 32
                        for composante in octets[debut:debut + 3])
        couleurs[arrondi] = couleurs.get(arrondi, 0) + 1
    dominantes = [list(couleur) for couleur, _ in sorted(
        couleurs.items(), key=lambda entree: -entree[1])[:COULEURS_DOMINANTES]]

    return [
        Observation(
            field_name="dimensions", value=[largeur, hauteur], origin=MESURE,
            measured_by=CHAMPS_MESURABLES["dimensions"], observed_from=source,
        ),
        Observation(
            field_name="aspect_ratio", value=round(largeur / hauteur, 4),
            origin=MESURE, measured_by=CHAMPS_MESURABLES["aspect_ratio"],
            observed_from=source,
        ),
        Observation(
            field_name="dominant_colours", value=dominantes, origin=MESURE,
            measured_by=CHAMPS_MESURABLES["dominant_colours"],
            observed_from=source,
        ),
    ]


def blocked_observations() -> List[Observation]:
    """
    Les champs qu'on ne peut pas mesurer ici, **déclarés** un par un.

    Returns:
        Une observation `ABSENT` par champ bloqué, portant la capacité qui
        manque. Les omettre ferait lire le manifeste comme si ces champs
        n'existaient pas ; les remplir serait la fabrication que §10 interdit.
    """
    return [
        Observation(
            field_name=champ, origin=ABSENT,
            reason=f"[{capacite}] {raison}",
        )
        for champ, (capacite, raison) in sorted(CHAMPS_BLOQUES.items())
    ]


def combine(observations: Sequence[Observation],
            field_name: str) -> Observation:
    """
    Combine plusieurs observations d'un même champ numérique.

    Args:
        observations: Les observations à combiner.
        field_name: Le champ concerné.

    Returns:
        Une observation dont la valeur est la **médiane** des valeurs mesurées
        et dont la confiance vient de leur **accord** : des sources qui disent
        la même chose renforcent, des sources qui divergent affaiblissent.

        Combiner ne crée jamais d'information : trois photos de face ne
        produisent pas un profil (§10). Ce qui augmente ici, c'est la confiance
        dans ce qui a été vu — pas la couverture de ce qui ne l'a pas été.
    """
    valeurs = [o.value for o in observations
               if o.origin == MESURE and isinstance(o.value, (int, float))]
    sources = tuple(sorted({s for o in observations for s in o.observed_from}))

    if not valeurs:
        return Observation(
            field_name=field_name, origin=ABSENT,
            reason=("Aucune observation numérique mesurée à combiner. "
                    "Combiner du vide ne produit pas une valeur."),
        )
    if len(valeurs) == 1:
        return Observation(
            field_name=field_name, value=valeurs[0], origin=MESURE,
            measured_by="combine(1 source)", observed_from=sources,
            confidence=None,
        )

    mediane = statistics.median(valeurs)
    etendue = max(valeurs) - min(valeurs)
    reference = abs(mediane) if mediane else 1.0
    # L'accord, borné à [0, 1] : un écart nul donne 1, un écart du même ordre
    # que la valeur donne 0. Ce n'est pas une probabilité et le nom le dit.
    accord = max(0.0, min(1.0, 1.0 - (etendue / reference)))

    return Observation(
        field_name=field_name, value=round(mediane, 6), origin=MESURE,
        measured_by=f"combine({len(valeurs)} sources, médiane)",
        observed_from=sources, confidence=round(accord, 4),
    )


def ingest(
    reference: ReferenceEntity, paths: Sequence[str],
    uploaded_by: str = "", declare_blocked: bool = True,
) -> Dict[str, Any]:
    """
    Rattache des médias à une référence et enregistre ce qui a pu être mesuré.

    Args:
        reference: La référence à enrichir.
        paths: Les fichiers fournis.
        uploaded_by: Qui les fournit.
        declare_blocked: Enregistrer aussi les champs non mesurables, avec la
            capacité qui manque. Vrai par défaut, parce qu'un champ absent d'un
            manifeste se lit comme un champ sans objet.

    Returns:
        Ce qui a été rattaché, ce qui a été mesuré, et ce qui ne l'a pas été
        avec la raison. Une vidéo est **rattachée et non analysée** tant que le
        décodage est dégradé : elle porte son empreinte, ce qui suffit à la
        révoquer plus tard.

    Raises:
        ReferenceRefused: Sur une référence révoquée, ou un fichier absent.
    """
    rattaches: List[Dict[str, Any]] = []
    mesurees: List[Observation] = []
    non_analyses: List[Dict[str, str]] = []
    par_champ: Dict[str, List[Observation]] = {}

    decodage = probe("video_decode")["state"]

    for chemin in paths:
        genre = _genre_de(chemin)
        media = SourceMedium(
            medium_id=f"med-{uuid.uuid4().hex[:10]}", kind=genre,
            path=chemin, sha256=file_digest(chemin), uploaded_by=uploaded_by,
        )

        if genre == "image":
            observations = analyse_image(chemin, media.medium_id)
            for observation in observations:
                par_champ.setdefault(observation.field_name, []).append(
                    observation)
            mesurees.extend(observations)
            media = SourceMedium(
                **{**media.as_dict(), "analysed": True,
                   "analysis_status": "mesuré : dimensions, rapport, couleurs"}
            )
        else:
            raison = (
                f"Décodage vidéo {decodage} sur cette machine."
                if genre == "video" else
                "Aucun décodeur audio disponible."
            )
            non_analyses.append({"path": chemin, "kind": genre,
                                 "reason": raison})
            media = SourceMedium(
                **{**media.as_dict(), "analysed": False,
                   "analysis_status": raison}
            )

        reference.add_medium(media)
        rattaches.append(media.as_dict())

    # Les champs vus par plusieurs images sont combinés ; les autres sont
    # enregistrés tels quels.
    for champ, observations in par_champ.items():
        if len(observations) > 1 and champ in ("aspect_ratio",):
            reference.observe(combine(observations, champ))
        else:
            reference.observe(observations[-1])

    if declare_blocked:
        for observation in blocked_observations():
            reference.observe(observation)

    return {
        "reference_id": reference.reference_id,
        "attached": rattaches,
        "measured_fields": sorted({o.field_name for o in mesurees}),
        "not_analysed": non_analyses,
        "blocked_fields": sorted(CHAMPS_BLOQUES) if declare_blocked else [],
        "note": (
            "Ce qui est mesuré nomme son outil ; ce qui ne l'est pas nomme la "
            "capacité qui manque. Rien de ce qui touche à l'identité n'est "
            "produit ici : une description remplie à partir de trois photos "
            "serait convaincante et inventée."
        ),
    }


def _genre_de(chemin: str) -> str:
    """Le genre d'un média, d'après son extension — une **présomption**."""
    extension = os.path.splitext(chemin)[1].lower()
    if extension in (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"):
        return "image"
    if extension in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
        return "video"
    if extension in (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"):
        return "audio"
    raise ReferenceRefused(
        f"Extension « {extension} » non reconnue pour « {chemin} ». Le genre "
        "n'est pas deviné : traiter un fichier inconnu comme une image le "
        "ferait échouer plus loin, sans dire pourquoi."
    )


def ingestion_report() -> Dict[str, Any]:
    """
    Ce que l'ingestion mesure, et ce qu'elle refuse de produire.

    Returns:
        Les champs mesurables, les champs bloqués avec leur capacité, et l'état
        des sondes concernées.
    """
    return {
        "measurable": dict(CHAMPS_MESURABLES),
        "blocked": {champ: {"capability": capacite, "reason": raison}
                    for champ, (capacite, raison) in CHAMPS_BLOQUES.items()},
        "probes": {
            nom: probe(nom)["state"]
            for nom in ("image_analysis", "video_decode", "audio_decode")
        },
        "image_analysis_available": probe("image_analysis")["state"] == DISPONIBLE,
        "rules": [
            "Ce qui est mesuré **nomme son outil** ; sans lui, ce n'est pas "
            "une mesure.",
            "Ce qui ne peut pas être mesuré est **déclaré absent avec la "
            "capacité qui manque** — l'omettre ferait croire que le champ n'a "
            "pas d'objet.",
            "Combiner plusieurs sources augmente la **confiance** dans ce qui "
            "a été vu ; cela ne crée jamais ce qui ne l'a pas été. Trois "
            "photos de face ne produisent pas un profil (§10).",
            "Une vidéo est rattachée avec son empreinte et rapportée non "
            "analysée tant que le décodage est dégradé : l'empreinte suffit à "
            "la révoquer plus tard.",
        ],
        "does_not": [
            "Décrire un visage, une carrure ou une géométrie.",
            "Produire une valeur d'identité.",
            "Deviner le genre d'un fichier inconnu.",
            "Traiter une vidéo comme une suite d'images sans lien.",
        ],
    }
