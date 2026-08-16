"""
Ce que cette machine sait vraiment faire d'un média — demandé, jamais supposé
(VOLET M01 du moteur média).

Chaque étape de la production dépend d'un outil qui peut manquer, et la façon
habituelle de traiter ça est un booléen : `ffmpeg` est-il dans le `PATH` ? Ce
booléen s'est révélé faux **dans les deux sens** ici.

Il n'y a pas d'`ffmpeg` dans le `PATH` — le booléen dirait donc « aucun travail
média possible ». Mais l'outillage navigateur en embarque un, et si on ajoutait
son chemin le booléen dirait « oui » en se trompant tout autant : ce binaire est
construit `--disable-everything`. Il ne lit aucun MP4, ne touche à aucun audio,
et **ne décode même pas le PNG** dont il porte pourtant l'encodeur.

Ce que ces tests gardent :

1. **Une capacité est mesurée en interrogeant l'outil**, pas déduite de sa
   présence.
2. **Encoder n'est pas décoder**, et `image2` n'est pas `image2pipe`.
3. **Une sonde qui tombe est rapportée**, jamais propagée.
4. **`require()` refuse** au lieu de produire « quelque chose quand même ».
"""

import io
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.integration.degradation import (  # noqa: E402
    DEGRADE,
    DISPONIBLE,
    INDISPONIBLE,
)
from src.media.core import capabilities as caps  # noqa: E402
from src.media.core.capabilities import (  # noqa: E402
    CAPACITES,
    CONSEQUENCES,
    SONDES,
    MediaCapabilityError,
    capability_report,
    ffmpeg_support,
    find_ffmpeg,
    frame_pipe_format,
    probe,
    require,
)


# ----------------------------------------------------------------------
# 1. Chaque capacité déclarée est sondée
# ----------------------------------------------------------------------

def test_chaque_capacite_declaree_a_une_sonde():
    """Une capacité sans sonde est une capacité que personne ne mesure."""
    assert set(CAPACITES) == set(SONDES)


def test_chaque_capacite_dit_ce_que_son_absence_empeche():
    """« Indisponible » sans conséquence ne dit pas s'il faut s'en inquiéter."""
    for nom in CAPACITES:
        assert CONSEQUENCES[nom].strip(), nom


def test_une_capacite_inconnue_est_refusee():
    """Deviner rendrait « disponible » pour toujours."""
    with pytest.raises(KeyError):
        probe("teleportation")
    with pytest.raises(KeyError):
        capability_report(["teleportation"])


def test_les_etats_sont_ceux_de_la_plateforme():
    """Un second vocabulaire serait une chose de plus à garder alignée."""
    rapport = capability_report()

    assert rapport["state"] in (DISPONIBLE, DEGRADE, INDISPONIBLE)
    for entree in rapport["capabilities"].values():
        assert entree["state"] in (DISPONIBLE, DEGRADE, INDISPONIBLE)


def test_le_rapport_range_chaque_capacite_dans_une_seule_liste():
    """Une capacité comptée deux fois fausserait toute lecture du rapport."""
    rapport = capability_report()
    rangees = rapport["available"] + rapport["degraded"] + rapport["unavailable"]

    assert sorted(rangees) == sorted(CAPACITES)
    assert len(rangees) == len(set(rangees))


# ----------------------------------------------------------------------
# 2. Une sonde qui tombe est rapportée, pas propagée
# ----------------------------------------------------------------------

def test_une_sonde_qui_leve_ne_renverse_pas_le_rapport(monkeypatch):
    """
    Le cas que ce module existe pour tenir.

    Un rapport de capacités renversé par ce qu'il observe serait exactement la
    panne qu'il doit empêcher.
    """
    def _tombe():
        raise OSError("disque absent")

    monkeypatch.setitem(SONDES, "media_probe", _tombe)

    resultat = probe("media_probe")

    assert resultat["state"] == INDISPONIBLE
    assert "OSError" in resultat["reason"]
    assert capability_report()["state"] in (DEGRADE, INDISPONIBLE)


def test_un_binaire_muet_ne_fait_pas_tomber_l_introspection(monkeypatch):
    """Un binaire qui ne répond pas est une absence de capacité, pas un plantage."""
    monkeypatch.setattr(caps, "_demander", lambda binaire, question: "")

    support = ffmpeg_support("/bin/true")

    assert support["found"] is True
    assert support["encodes_h264"] is False
    assert support["handles_audio"] is False


# ----------------------------------------------------------------------
# 3. Encoder n'est pas décoder ; image2 n'est pas image2pipe
# ----------------------------------------------------------------------

def test_les_noms_sont_lus_par_jeton_pas_par_sous_chaine():
    """
    `image2` et `image2pipe` sont deux choses différentes.

    L'un lit une suite de fichiers numérotés, l'autre reçoit des trames sur son
    entrée standard. Une recherche de sous-chaîne les confond et fait construire
    une commande qui n'ouvrira jamais son entrée.
    """
    sortie = " D  image2pipe      piped image2 sequence\n"

    noms = caps._noms(sortie)

    assert "image2pipe" in noms
    assert "image2" not in noms


def test_un_encodeur_png_ne_vaut_pas_un_decodeur_png(monkeypatch):
    """
    Le défaut que l'exécution a trouvé.

    Le binaire embarqué porte `--enable-encoder=png` et aucun décodeur PNG :
    lui envoyer des trames PNG échoue. Déduire l'un de l'autre aurait produit
    une capacité qui tombe au dernier pas, après tout le travail de rendu.
    """
    def _faux(binaire, question):
        if question == "-encoders":
            return " V..... png             PNG image\n V..... libvpx          libvpx VP8\n"
        if question == "-decoders":
            return " V..... mjpeg           MJPEG\n"
        if question == "-demuxers":
            return " D  image2pipe      piped image2 sequence\n"
        return ""

    monkeypatch.setattr(caps, "_demander", _faux)

    support = ffmpeg_support("/bin/true")

    assert support["encodes_png"] is True
    assert support["decodes_png"] is False
    assert frame_pipe_format("/bin/true") == "mjpeg"


def test_sans_decodeur_de_trame_aucun_format_n_est_propose(monkeypatch):
    """Proposer un format que le binaire refuse serait pire que dire non."""
    def _faux(binaire, question):
        if question == "-encoders":
            return " V..... libvpx          libvpx VP8\n"
        if question == "-demuxers":
            return " D  image2pipe      piped image2 sequence\n"
        return ""

    monkeypatch.setattr(caps, "_demander", _faux)

    assert frame_pipe_format("/bin/true") is None


def test_sans_entree_par_tuyau_aucun_format_n_est_propose(monkeypatch):
    """Une suite de fichiers numérotés n'est pas une entrée standard."""
    def _faux(binaire, question):
        if question == "-decoders":
            return " V..... mjpeg           MJPEG\n"
        if question == "-demuxers":
            return " D  matroska        Matroska\n"
        return ""

    monkeypatch.setattr(caps, "_demander", _faux)

    assert frame_pipe_format("/bin/true") is None


# ----------------------------------------------------------------------
# 4. Un refus est un refus
# ----------------------------------------------------------------------

def test_require_refuse_une_capacite_absente(monkeypatch):
    """C'est le point où un moteur ordinaire produirait « quelque chose »."""
    monkeypatch.setitem(
        SONDES, "gpu_compute",
        lambda: {"state": INDISPONIBLE, "reason": "Pas de GPU.", "detail": {}},
    )

    with pytest.raises(MediaCapabilityError) as refus:
        require("gpu_compute")

    assert "gpu_compute" in str(refus.value)
    assert "Pas de GPU." in str(refus.value)


def test_require_refuse_aussi_une_capacite_degradee(monkeypatch):
    """
    Dégradé n'est pas disponible.

    Un `ffmpeg` sans H.264 encode encore quelque chose ; accepter une commande
    de master MP4 sur cette base produirait un fichier que personne ne peut lire.
    """
    monkeypatch.setitem(
        SONDES, "video_encode",
        lambda: {"state": DEGRADE, "reason": "Pas de H.264.", "detail": {}},
    )

    with pytest.raises(MediaCapabilityError):
        require("video_encode")


def test_require_laisse_passer_une_capacite_disponible(monkeypatch):
    """Le cas nominal existe."""
    monkeypatch.setitem(
        SONDES, "image_analysis",
        lambda: {"state": DISPONIBLE, "reason": "OK.", "detail": {}},
    )

    assert require("image_analysis")["state"] == DISPONIBLE


# ----------------------------------------------------------------------
# 5. La capacité annoncée fonctionne réellement
# ----------------------------------------------------------------------

@pytest.mark.skipif(find_ffmpeg() is None, reason="aucun ffmpeg dans cet environnement")
def test_le_chemin_de_trames_annonce_produit_vraiment_une_video(tmp_path):
    """
    Une capacité déclarée disponible doit l'être **en exécutant**.

    C'est ce test qui a trouvé que les trames PNG échouaient là où le MJPEG
    passait : la sonde disait « disponible » en se fondant sur les mauvais
    indices. Elle nomme désormais le format à produire, et ce test vérifie que
    ce format-là fonctionne.
    """
    from PIL import Image, ImageDraw

    sonde = probe("frame_encode")
    if sonde["state"] != DISPONIBLE:
        pytest.skip(f"frame_encode {sonde['state']} : {sonde['reason']}")

    format_trame = sonde["detail"]["frame_format"]
    sortie = tmp_path / "sortie.webm"
    binaire = find_ffmpeg()

    processus = subprocess.Popen(
        [binaire, "-y", "-f", "image2pipe", "-vcodec", format_trame,
         "-framerate", "24", "-i", "pipe:0", "-c:v", "libvpx", "-b:v", "300k",
         str(sortie)],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )

    donnees = b""
    for indice in range(12):
        image = Image.new("RGB", (160, 90), (10, 12, 20))
        ImageDraw.Draw(image).rectangle(
            [5 + indice * 5, 30, 40 + indice * 5, 60], fill=(220, 90, 40),
        )
        tampon = io.BytesIO()
        image.save(tampon, format="JPEG" if format_trame == "mjpeg" else "PNG")
        donnees += tampon.getvalue()

    _, erreur = processus.communicate(donnees, timeout=120)

    assert processus.returncode == 0, erreur.decode()[-500:]
    assert sortie.exists() and sortie.stat().st_size > 0


def test_le_rapport_dit_pourquoi_il_interroge_l_outil():
    """La règle est écrite là où elle est appliquée."""
    note = capability_report()["note"]

    assert "mesurée" in note
    assert "disable-everything" in note
