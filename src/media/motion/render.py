"""
Turning a described scene into real frames, and real frames into a real file.

Directive §9 asks for a browser-rendered animation pipeline and then adds the
constraint that matters: *this must be one backend, not the entire engine.* A
media engine welded to Chromium can only animate what a browser can draw, and
inherits every one of a browser's non-determinisms — font substitution,
subpixel antialiasing, GPU rasterisation differing between machines. That is a
poor foundation for a system whose quality control works by comparing two
renders.

So backends are a registry, each declaring what it can do, and the one written
here draws with Pillow: no browser, no network, no GPU, and the same bytes on
every run. The browser backend is declared and reports `DEGRADED` on this
machine — Chromium is present, no driver is installed to steer it — which is
exactly how a capability that does not exist is supposed to look.

The encode path is the one measured in M01 and it is not the obvious one. This
machine's `ffmpeg` reads frames only from **stdin** (`image2pipe`, not
`image2`), and decodes **MJPEG but not PNG** despite carrying a PNG encoder. So
frames are piped, in the format `frame_pipe_format()` reports, and a mismatch
there fails at the last step after all the rendering work — which is why the
format is asked for rather than assumed.

Nothing here declares a render successful because the encoder exited zero. §21
is enforced at the seam: `render_video()` reports what was written and its size,
and the verification of *content* belongs to the quality control that reads the
file back.
"""

from __future__ import annotations

import io
import os
import subprocess
from typing import Any, Dict, Iterator, Optional

from ..core.capabilities import DISPONIBLE, find_ffmpeg, frame_pipe_format, probe
from .scene import MotionScene, VisualIdentity

#: Les backends déclarés. `pillow` dessine sans navigateur ni GPU et rend les
#: mêmes octets à chaque exécution ; les autres sont nommés pour que leur
#: absence soit visible plutôt que sous-entendue.
BACKENDS = {
    "pillow": {
        "deterministic": True,
        "needs": ("image_analysis",),
        "note": "Dessin logiciel. Aucun navigateur, aucun réseau, aucun GPU.",
    },
    "browser": {
        "deterministic": False,
        "needs": ("browser_render",),
        "note": (
            "HTML/CSS/SVG/Canvas rendus par un navigateur (§9). Non "
            "déterministe par nature : substitution de police, anticrénelage "
            "sous-pixel et rastérisation GPU diffèrent d'une machine à l'autre."
        ),
    },
}

#: Qualité JPEG des trames envoyées à l'encodeur. Élevée : ces trames sont un
#: format de transport, pas une livraison, et perdre du détail ici se voit
#: après le ré-encodage en vidéo.
QUALITE_TRAME = 95


class RenderRefused(RuntimeError):
    """Un rendu qui ne peut pas être fait sur cette machine."""


def available_backends() -> Dict[str, Any]:
    """
    Les backends et leur état réel, mesuré par les sondes du VOLET M01.

    Returns:
        Chaque backend avec son état, ses besoins et son déterminisme. Un
        backend est **disponible** quand toutes les capacités qu'il exige le
        sont : l'annoncer autrement ferait échouer un rendu au dernier moment.
    """
    resultat: Dict[str, Any] = {}
    for nom, details in BACKENDS.items():
        sondes = {besoin: probe(besoin) for besoin in details["needs"]}
        pret = all(sonde["state"] == DISPONIBLE for sonde in sondes.values())
        resultat[nom] = {
            "available": pret,
            "deterministic": details["deterministic"],
            "requires": list(details["needs"]),
            "capability_states": {
                besoin: sonde["state"] for besoin, sonde in sondes.items()
            },
            "note": details["note"],
        }
    return resultat


def render_frame(
    scene: MotionScene, frame: int, identity: Optional[VisualIdentity] = None,
) -> Any:
    """
    Dessine une trame, entièrement déterminée par la scène et l'identité.

    Args:
        scene: La scène décrite.
        frame: L'index de la trame.
        identity: Le style. Le défaut est déclaré, jamais codé en dur ailleurs.

    Returns:
        Une image Pillow. Aucune horloge n'est lue et aucun aléa n'est tiré :
        deux appels identiques rendent les mêmes octets, ce qui est la seule
        raison pour laquelle un contrôle qualité peut comparer deux rendus.

    Raises:
        RenderRefused: Si la trame est hors de la scène — rendre une trame qui
            n'existe pas produirait une image que rien ne décrit.
    """
    if not 0 <= frame < scene.frames:
        raise RenderRefused(
            f"Trame {frame} hors de la scène (0 à {scene.frames - 1}). La "
            "rendre produirait une image que rien ne décrit."
        )
    from PIL import Image, ImageDraw

    style = identity or VisualIdentity()
    image = Image.new("RGB", (scene.width, scene.height), style.background)
    pinceau = ImageDraw.Draw(image)

    for element, etat in scene.draw_order(frame):
        _dessiner(pinceau, image, element.kind, etat, style)
    return image


def _dessiner(pinceau: Any, image: Any, kind: str, etat: Dict[str, Any],
              style: VisualIdentity) -> None:
    """Dessine une primitive dans son état courant."""
    couleur = tuple(etat.get("color") or style.primary)
    x = int(etat.get("x", 0))
    y = int(etat.get("y", 0))

    if kind == "rect":
        largeur = int(etat.get("width", 10))
        hauteur = int(etat.get("height", 10))
        pinceau.rectangle([x, y, x + largeur, y + hauteur], fill=couleur)
    elif kind == "line":
        pinceau.line(
            [x, y, int(etat.get("x2", x)), int(etat.get("y2", y))],
            fill=couleur, width=int(etat.get("thickness", 2)),
        )
    elif kind == "text":
        pinceau.text(
            (x, y), str(etat.get("text", "")),
            fill=tuple(etat.get("color") or style.text_color),
        )
    elif kind == "image":
        chemin = str(etat.get("path", ""))
        if chemin and os.path.isfile(chemin):
            from PIL import Image as _Image

            with _Image.open(chemin) as source:
                image.paste(source.convert("RGB"), (x, y))


def frames(
    scene: MotionScene, identity: Optional[VisualIdentity] = None,
) -> Iterator[Any]:
    """
    Les trames de la scène, dans l'ordre, une à la fois.

    Générées paresseusement : une scène de trois minutes en 1080p tient des
    gigaoctets en mémoire si on les accumule, et le seul but de ces trames est
    d'être envoyées à un encodeur.
    """
    for index in range(scene.frames):
        yield render_frame(scene, index, identity)


def render_video(
    scene: MotionScene,
    output_path: str,
    identity: Optional[VisualIdentity] = None,
    bitrate: str = "800k",
) -> Dict[str, Any]:
    """
    Rend la scène en un fichier vidéo réel.

    Args:
        scene: La scène décrite.
        output_path: Le fichier à écrire.
        identity: Le style employé.
        bitrate: Le débit visé.

    Returns:
        Ce qui a été écrit : chemin, taille, trames envoyées, format de trame
        et encodeur. **Pas un verdict de conformité** : un encodeur qui sort en
        zéro ne dit rien de ce que le fichier contient, et cette distinction est
        la directive §21.

    Raises:
        RenderRefused: Si aucun `ffmpeg` utilisable n'existe, ou si aucun format
            de trame n'est accepté par celui qui existe.
    """
    binaire = find_ffmpeg()
    if not binaire:
        raise RenderRefused(
            "Aucun `ffmpeg` : les trames peuvent être dessinées, pas "
            "assemblées. Écrire un fichier vide qui s'encode sans erreur serait "
            "pire que ce refus."
        )

    format_trame = frame_pipe_format(binaire)
    if not format_trame:
        raise RenderRefused(
            "Ce `ffmpeg` n'accepte aucune trame sur son entrée standard. "
            "Mesuré en l'interrogeant : porter un encodeur PNG ne suffit pas, "
            "c'est le **décodeur** qui décide de ce qu'on peut lui envoyer."
        )

    dossier = os.path.dirname(output_path)
    if dossier:
        os.makedirs(dossier, exist_ok=True)

    commande = [
        binaire, "-y", "-f", "image2pipe", "-vcodec", format_trame,
        "-framerate", str(scene.fps), "-i", "pipe:0",
        "-c:v", "libvpx", "-b:v", bitrate, output_path,
    ]
    processus = subprocess.Popen(
        commande, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    envoyees = 0
    try:
        for image in frames(scene, identity):
            tampon = io.BytesIO()
            if format_trame == "mjpeg":
                image.save(tampon, format="JPEG", quality=QUALITE_TRAME)
            else:
                image.save(tampon, format="PNG")
            processus.stdin.write(tampon.getvalue())
            envoyees += 1
        processus.stdin.close()
    except BrokenPipeError:
        # L'encodeur est tombé avant la fin. Son message est la seule chose
        # utile ici ; le taire laisserait un fichier tronqué sans explication.
        pass

    erreur = processus.stderr.read().decode("utf-8", errors="replace")
    code = processus.wait()

    if code != 0 or not os.path.isfile(output_path):
        raise RenderRefused(
            f"L'encodage a échoué (code {code}). "
            f"{erreur.strip().splitlines()[-1] if erreur.strip() else ''}"
        )

    return {
        "path": output_path,
        "bytes": os.path.getsize(output_path),
        "frames_sent": envoyees,
        "expected_frames": scene.frames,
        "frame_format": format_trame,
        "encoder": "libvpx",
        "fps": scene.fps,
        "identity": (identity or VisualIdentity()).name,
        "complete": envoyees == scene.frames,
        "note": (
            "Ceci décrit ce qui a été **écrit**, pas ce que le fichier dit. Un "
            "encodeur qui sort en zéro ne vérifie rien du contenu — c'est la "
            "distinction de la directive §21, et la vérification appartient au "
            "contrôle qualité qui relit le fichier."
        ),
    }


def render_report() -> Dict[str, Any]:
    """
    Ce que le rendu garantit, et ce qu'il refuse.

    Returns:
        Les backends, leur état mesuré, et les règles tenues.
    """
    return {
        "backends": available_backends(),
        "frame_quality": QUALITE_TRAME,
        "rules": [
            "Les backends sont un **registre** : un moteur soudé à un "
            "navigateur ne sait animer que ce qu'un navigateur dessine, et "
            "hérite de tous ses indéterminismes.",
            "Le backend `pillow` est déterministe — aucune horloge, aucun "
            "aléa — ce qui est la seule raison pour laquelle un contrôle "
            "qualité peut comparer deux rendus.",
            "Le format des trames envoyées est **demandé à l'encodeur**, jamais "
            "supposé : ici il décode le MJPEG et pas le PNG, dont il porte "
            "pourtant l'encodeur.",
            "Un encodage réussi n'est **pas** une conformité : le rapport "
            "décrit ce qui a été écrit, et la vérification du contenu revient "
            "au contrôle qualité (§21).",
            "Un backend est annoncé disponible seulement si toutes ses "
            "capacités le sont — sinon le rendu échouerait au dernier moment.",
        ],
        "does_not": [
            "Déclarer un rendu conforme parce que l'encodeur est sorti en zéro.",
            "Supposer le format de trame accepté par un `ffmpeg`.",
            "Rendre une trame qui n'existe pas dans la scène.",
            "Accumuler toutes les trames en mémoire avant d'encoder.",
        ],
    }


__all__ = [
    "BACKENDS",
    "QUALITE_TRAME",
    "RenderRefused",
    "available_backends",
    "frames",
    "render_frame",
    "render_report",
    "render_video",
]
