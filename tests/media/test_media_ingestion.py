"""
Identifier un fichier par ses octets, puis mesurer — ou dire qu'on ne sait pas
(VOLET M03 du moteur média).

Deux tentations sont fermées ici, et chacune produit une erreur qui **ressemble
à un fait**.

La première est de croire l'extension. Elle est fausse pour la correction — un
fichier renommé une fois par un humain bien intentionné est mal étiqueté pour
toujours — et fausse pour la sécurité : le nom est une entrée externe, donc une
chaîne qui route par l'extension route par ce qu'un attaquant choisit.

La seconde est de remplir les champs manquants avec des valeurs par défaut.
`duration = 0.0` et `fps = 25` se lisent exactement comme des mesures, et le
planificateur de montage ne peut pas faire la différence : il placerait une
coupe à la douzième seconde d'un fichier dont personne n'a lu la durée.

Ce que ces tests gardent :

1. **Les octets décident**, le nom est enregistré comme une prétention.
2. **Un désaccord est rapporté**, jamais tranché en silence.
3. **Un champ est mesuré ou inconnu**, jamais entre les deux.
4. **`require_for_editing()` refuse** au lieu de calculer sur une absence.
"""

import os
import sys

import pytest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.ingestion.identify import (  # noqa: E402
    FORMAT_INCONNU,
    IdentificationRefused,
    claimed_format,
    detect_format,
    identification_report,
    identify_bytes,
    identify_file,
    supported_formats,
)
from src.media.ingestion.inspect import (  # noqa: E402
    CHAMPS,
    InspectionRefused,
    MediaInfo,
    inspect_media,
    inspection_report,
    require_for_editing,
)


def _image(chemin, format_pillow, taille=(32, 18)):
    """Écrit une vraie image — la preuve, pas des octets écrits de mémoire."""
    Image.new("RGB", taille, (12, 34, 56)).save(chemin, format=format_pillow)
    return chemin


# ----------------------------------------------------------------------
# 1. Les octets décident
# ----------------------------------------------------------------------

@pytest.mark.parametrize("format_pillow,attendu", [
    ("PNG", "png"), ("JPEG", "jpeg"), ("GIF", "gif"), ("WEBP", "webp"),
])
def test_une_image_reelle_est_reconnue(tmp_path, format_pillow, attendu):
    """Produite par Pillow, pas par une signature recopiée de mémoire."""
    chemin = _image(tmp_path / f"essai.{attendu}", format_pillow)

    assert identify_file(str(chemin))["format"] == attendu


def test_les_conteneurs_riff_ne_se_confondent_pas():
    """WebP, WAV et AVI partagent `RIFF` : c'est la marque qui les sépare."""
    assert detect_format(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "webp"
    assert detect_format(b"RIFF\x00\x00\x00\x00WAVEfmt ") == "wav"
    assert detect_format(b"RIFF\x00\x00\x00\x00AVI LIST") == "avi"


def test_mp4_et_mov_partagent_ftyp_et_se_distinguent():
    """Les deux se lisent différemment malgré un en-tête commun."""
    assert detect_format(b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00") == "mp4"
    assert detect_format(b"\x00\x00\x00\x14ftypqt  \x00\x00\x02\x00") == "mov"


def test_webm_et_matroska_se_distinguent_par_le_type_de_document():
    """
    Ils partagent la signature EBML.

    Les confondre annoncerait un WebM là où un Matroska attend d'autres codecs.
    """
    assert detect_format(b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"webm") == "webm"
    assert detect_format(b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"matroska") == \
        "matroska"


def test_un_ebml_sans_type_declare_n_est_pas_devine():
    """Deviner reviendrait à choisir un codec pour l'appelant."""
    assert detect_format(b"\x1a\x45\xdf\xa3" + b"\x00" * 40) is None


def test_un_svg_est_reconnu_bien_qu_il_n_ait_pas_de_signature():
    """C'est du texte : il faut le lire, pas chercher des octets magiques."""
    assert detect_format(b'<svg xmlns="http://www.w3.org/2000/svg"></svg>') == "svg"
    assert detect_format(b'<?xml version="1.0"?>\n<svg width="10"></svg>') == "svg"


def test_un_contenu_inconnu_n_est_pas_range_dans_une_famille():
    """« Sans doute une vidéo » ferait tourner le mauvais outil."""
    resultat = identify_bytes(b"ceci n'est rien du tout", "video.mp4")

    assert resultat["format"] == FORMAT_INCONNU
    assert resultat["family"] is None
    assert resultat["identified"] is False


# ----------------------------------------------------------------------
# 2. Le nom est une prétention
# ----------------------------------------------------------------------

def test_un_desaccord_entre_le_nom_et_le_contenu_est_rapporte(tmp_path):
    """
    Le cas central.

    Croire le nom rend la chaîne exploitable ; l'écraser en silence cache une
    corruption réelle. Les deux sont donc rendus.
    """
    chemin = tmp_path / "sequence.mp4"
    _image(chemin, "PNG")

    resultat = identify_file(str(chemin))

    assert resultat["format"] == "png"
    assert resultat["claimed_format"] == "mp4"
    assert resultat["mismatch"] is True
    assert "exploitable" in resultat["reason"]


def test_un_accord_ne_leve_aucun_desaccord(tmp_path):
    """Le cas nominal ne doit pas crier au loup."""
    chemin = _image(tmp_path / "image.png", "PNG")

    assert identify_file(str(chemin))["mismatch"] is False


def test_le_format_pretendu_vient_de_l_extension_seule():
    """Il est enregistré, jamais cru — aucun octet n'est lu ici."""
    assert claimed_format("film.MP4") == "mp4"
    assert claimed_format("archive.tar.gz") is None
    assert claimed_format("sans_extension") is None


def test_un_fichier_vide_n_est_pas_identifie(tmp_path):
    """L'identifier ferait démarrer une production sur rien."""
    vide = tmp_path / "vide.mp4"
    vide.write_bytes(b"")

    with pytest.raises(IdentificationRefused) as refus:
        identify_file(str(vide))

    assert "sur rien" in str(refus.value)


def test_un_fichier_absent_est_refuse(tmp_path):
    """Un chemin qui n'existe pas n'est pas un format inconnu."""
    with pytest.raises(IdentificationRefused):
        identify_file(str(tmp_path / "jamais_ecrit.mp4"))


# ----------------------------------------------------------------------
# 3. Mesuré, ou inconnu — jamais entre les deux
# ----------------------------------------------------------------------

def test_les_dimensions_d_une_image_sont_reellement_mesurees(tmp_path):
    """Ce qui est mesurable ici l'est exactement, et dit par quoi."""
    chemin = _image(tmp_path / "image.png", "PNG", taille=(64, 36))

    info = inspect_media(str(chemin))

    assert info.get("width") == 64
    assert info.get("height") == 36
    assert info.measured_by["width"] == "pillow"
    assert info.is_complete is True


def test_un_champ_non_mesure_rend_none_pas_zero(tmp_path):
    """Un appelant qui confondrait les deux calculerait sur une absence."""
    chemin = tmp_path / "film.mp4"
    chemin.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64)

    info = inspect_media(str(chemin))

    assert info.get("duration") is None
    assert info.get("fps") is None
    assert 0 not in (info.measured.get("duration"), info.measured.get("fps"))


def test_un_champ_inconnu_nomme_la_capacite_qui_le_fournirait(tmp_path):
    """Dire « inconnu » sans dire par quoi laisse chercher au hasard."""
    chemin = tmp_path / "film.mp4"
    chemin.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 64)

    info = inspect_media(str(chemin))

    assert "duration" in info.unknown_fields
    assert "media_probe" in info.unknown["duration"]


def test_une_image_illisible_n_a_pas_de_taille_nulle(tmp_path):
    """`(0, 0)` ferait diviser par zéro plus loin."""
    tronquee = tmp_path / "cassee.png"
    tronquee.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 40)

    info = inspect_media(str(tronquee))

    assert info.get("width") is None
    assert "illisible" in info.unknown["width"]


def test_les_champs_attendus_dependent_de_la_famille(tmp_path):
    """Demander une cadence à une image produirait une absence permanente."""
    chemin = _image(tmp_path / "image.png", "PNG")

    info = inspect_media(str(chemin))

    assert "fps" not in info.unknown_fields
    assert "duration" not in info.unknown_fields


def test_le_desaccord_de_nom_survit_a_l_inspection(tmp_path):
    """Il doit rester visible jusqu'au bout de la chaîne."""
    chemin = tmp_path / "sequence.mp4"
    _image(chemin, "PNG")

    info = inspect_media(str(chemin))

    assert info.mismatch is True
    assert info.format == "png"


# ----------------------------------------------------------------------
# 4. Refuser plutôt que calculer sur une absence
# ----------------------------------------------------------------------

def test_le_montage_est_refuse_sans_duree_mesuree():
    """
    C'est le point où un moteur ordinaire prendrait `0.0`.

    Une coupe placée sur une durée que personne n'a lue est exactement l'échec
    que ce moteur existe pour empêcher.
    """
    info = MediaInfo(path="/x/film.mp4", format="mp4", family="video",
                     unknown={"duration": "Non mesuré.", "fps": "Non mesuré."})

    with pytest.raises(InspectionRefused) as refus:
        require_for_editing(info)

    assert "duration" in str(refus.value)
    assert "personne n'a lu la durée" in str(refus.value)


def test_le_montage_passe_quand_les_mesures_existent():
    """Le cas nominal existe."""
    info = MediaInfo(path="/x/film.mp4", format="mp4", family="video",
                     measured={"duration": 12.5, "fps": 25.0})

    require_for_editing(info)


def test_les_champs_requis_sont_choisis_par_l_appelant():
    """Un montage sur la seule durée est légitime ; l'imposer ne l'est pas."""
    info = MediaInfo(path="/x/son.wav", format="wav", family="audio",
                     measured={"duration": 3.0},
                     unknown={"fps": "Sans objet pour de l'audio."})

    require_for_editing(info, fields=["duration"])


# ----------------------------------------------------------------------
# 5. Ce que l'ingestion ne fait pas
# ----------------------------------------------------------------------

def test_les_formats_de_la_directive_sont_declares():
    """Un format absent de la table est inconnu du moteur, quelle qu'en soit la popularité."""
    familles = supported_formats()

    assert {"mp4", "mov", "matroska", "webm", "avi"} <= set(familles["video"])
    assert {"wav", "mp3", "aac", "flac"} <= set(familles["audio"])
    assert {"png", "jpeg", "webp", "gif"} <= set(familles["image"])
    assert "svg" in familles["vector"]


def test_le_rapport_refuse_de_deviner_depuis_l_extension():
    """Les règles sont écrites là où elles sont appliquées."""
    interdits = " ".join(identification_report()["does_not"])

    assert "Deviner un format depuis son extension" in interdits
    assert "sans le dire" in interdits
    assert "Identifier un fichier vide" in interdits


def test_le_rapport_d_inspection_refuse_les_valeurs_par_defaut():
    """Une valeur par défaut se lit exactement comme une mesure."""
    rapport = inspection_report()

    interdits = " ".join(rapport["does_not"])
    assert "par défaut" in interdits
    assert "taille nulle" in interdits
    assert set(rapport["fields"]) == set(CHAMPS)
