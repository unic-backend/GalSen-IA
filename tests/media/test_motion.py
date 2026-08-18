"""
Une animation décrite en données, rendue de façon déterministe
(VOLET M08 du moteur média).

La directive §8 demande un motion design produit à partir de descriptions
structurées, et que le style ne soit pas codé en dur. Ce sont deux façons de
demander la même chose : si la description est une donnée et le style aussi,
alors un rendu est une **fonction pure** de l'un et de l'autre, et deux rendus
identiques donnent les mêmes octets. C'est cette propriété qui rend tout le
reste vérifiable — un contrôle qualité incapable de re-rendre la même chose n'a
rien à comparer.

La §9 ajoute la contrainte qui compte : le rendu navigateur doit être **un**
backend, pas le moteur entier. Un moteur soudé à Chromium ne sait animer que ce
qu'un navigateur dessine, et hérite de tous ses indéterminismes.

Ce que ces tests gardent :

1. **Le même rendu deux fois donne les mêmes octets.**
2. **Deux identités visuelles donnent des pixels différents**, même structure.
3. **Aucune horloge n'est lue** : la trame `n` est à `n / fps`, calculé.
4. **Ce qui n'est pas implémenté est nommé**, pas sous-entendu.
5. **Un encodage réussi n'est pas une conformité.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.core.capabilities import find_ffmpeg  # noqa: E402
from src.media.motion.render import (  # noqa: E402
    BACKENDS,
    RenderRefused,
    available_backends,
    frames,
    render_frame,
    render_report,
    render_video,
)
from src.media.motion.scene import (  # noqa: E402
    COURBES,
    NON_IMPLEMENTE,
    PRIMITIVES,
    Element,
    MotionRefused,
    MotionScene,
    Track,
    VisualIdentity,
    motion_report,
)


@pytest.fixture
def scene():
    """Un rectangle qui traverse l'écran, et un titre fixe."""
    return MotionScene(width=160, height=90, fps=24, frames=12, elements=(
        Element(kind="rect", props={"y": 40, "width": 30, "height": 20},
                tracks=(Track("x", 0, 11, 5, 120, easing="ease_in_out"),), z=1),
        Element(kind="text", props={"x": 8, "y": 8, "text": "GalSen IA"}, z=2),
    ))


# ----------------------------------------------------------------------
# 1. Le rendu est déterministe
# ----------------------------------------------------------------------

def test_deux_rendus_de_la_meme_trame_donnent_les_memes_octets(scene):
    """
    La propriété qui rend tout le reste vérifiable.

    Un contrôle qualité incapable de re-rendre la même chose n'a rien à
    comparer.
    """
    premier = render_frame(scene, 5).tobytes()
    second = render_frame(scene, 5).tobytes()

    assert premier == second


def test_deux_trames_differentes_different(scene):
    """Sinon « déterministe » serait garanti par une animation immobile."""
    assert render_frame(scene, 0).tobytes() != render_frame(scene, 11).tobytes()


def test_une_trame_hors_de_la_scene_est_refusee(scene):
    """Elle produirait une image que rien ne décrit."""
    with pytest.raises(RenderRefused) as refus:
        render_frame(scene, 12)

    assert "que rien ne décrit" in str(refus.value)


def test_les_trames_sont_produites_paresseusement(scene):
    """Trois minutes en 1080p tiennent des gigaoctets si on les accumule."""
    flux = frames(scene)

    assert next(flux) is not None
    assert sum(1 for _ in flux) == scene.frames - 1


# ----------------------------------------------------------------------
# 2. Le style est une donnée
# ----------------------------------------------------------------------

def test_deux_identites_donnent_des_pixels_differents(scene):
    """C'est ce que « supporter plusieurs identités » doit vouloir dire."""
    sombre = VisualIdentity(name="sombre", background=(10, 10, 12))
    clair = VisualIdentity(name="clair", background=(245, 245, 240),
                           primary=(20, 90, 200))

    assert render_frame(scene, 3, sombre).tobytes() != \
        render_frame(scene, 3, clair).tobytes()


def test_la_structure_ne_change_pas_avec_l_identite(scene):
    """Le style habille la scène ; il ne la redéfinit pas."""
    avant = scene.as_dict()

    render_frame(scene, 3, VisualIdentity(name="autre", primary=(1, 2, 3)))

    assert scene.as_dict() == avant


def test_le_rendu_dit_sous_quelle_identite_il_a_ete_fait(tmp_path, scene):
    """Sans cela, on ne peut pas refaire le même rendu plus tard."""
    if find_ffmpeg() is None:
        pytest.skip("aucun ffmpeg dans cet environnement")

    resultat = render_video(scene, str(tmp_path / "s.webm"),
                            identity=VisualIdentity(name="marque-a"))

    assert resultat["identity"] == "marque-a"


# ----------------------------------------------------------------------
# 3. Le temps est calculé, pas lu
# ----------------------------------------------------------------------

def test_la_trame_n_arrive_a_n_sur_fps(scene):
    """Un rendu qui consulte l'heure donne une vidéo différente à chaque fois."""
    assert scene.time_of(0) == 0.0
    assert scene.time_of(12) == 0.5
    assert scene.duration == 0.5


def test_une_piste_tient_sa_valeur_hors_de_son_intervalle():
    """Elle ne « disparaît » pas : elle garde sa dernière valeur."""
    piste = Track("x", start_frame=10, end_frame=20, start_value=0.0,
                  end_value=100.0)

    assert piste.value_at(0) == 0.0
    assert piste.value_at(30) == 100.0
    assert piste.value_at(15) == 50.0


def test_une_courbe_non_declaree_est_refusee():
    """Deviner ferait bouger deux scènes différemment sans décision."""
    with pytest.raises(MotionRefused) as refus:
        Track("x", 0, 10, 0.0, 1.0, easing="rebond_elastique")

    assert "sans que personne l'ait décidé" in str(refus.value)


@pytest.mark.parametrize("courbe", sorted(COURBES))
def test_chaque_courbe_declaree_part_de_zero_et_finit_a_un(courbe):
    """Une courbe qui ne finit pas le mouvement laisserait un objet en chemin."""
    piste = Track("x", 0, 10, 0.0, 100.0, easing=courbe)

    assert piste.value_at(0) == 0.0
    assert piste.value_at(10) == 100.0


def test_une_piste_ecrase_la_valeur_fixe():
    """Un élément immobile devient animable sans être réécrit."""
    element = Element(kind="rect", props={"x": 999},
                      tracks=(Track("x", 0, 10, 0.0, 50.0),))

    assert element.state_at(0)["x"] == 0.0


# ----------------------------------------------------------------------
# 4. Ce qui n'est pas fait est nommé
# ----------------------------------------------------------------------

def test_une_primitive_non_rendue_est_refusee_avec_la_liste():
    """Prétendre la rendre parce que la directive la cite serait une fabrication."""
    with pytest.raises(MotionRefused) as refus:
        Element(kind="particles")

    assert "Non implémentées et nommées" in str(refus.value)


def test_chaque_capacite_absente_porte_sa_raison():
    """« Non implémenté » sans raison ne dit pas s'il faut l'attendre."""
    for nom, raison in NON_IMPLEMENTE.items():
        assert raison.strip(), nom

    assert set(NON_IMPLEMENTE) & {"particles", "masks", "3d"}


def test_les_primitives_rendues_le_sont_reellement(scene):
    """Une primitive déclarée mais non dessinée serait pire qu'absente."""
    rendu = motion_report()

    assert set(rendu["primitives"]) == set(PRIMITIVES)
    assert not set(rendu["primitives"]) & set(NON_IMPLEMENTE)


def test_une_scene_sans_trame_est_refusee():
    """Elle ferait rendre un fichier vide qui s'encode sans erreur."""
    with pytest.raises(MotionRefused) as refus:
        MotionScene(width=10, height=10, fps=24, frames=0)

    assert "s'encode sans erreur" in str(refus.value)


def test_une_cadence_nulle_est_refusee():
    """Sans cadence positive, l'instant d'une trame n'est pas défini."""
    with pytest.raises(MotionRefused):
        MotionScene(width=10, height=10, fps=0, frames=5)


# ----------------------------------------------------------------------
# 5. Les backends, et le rendu réel
# ----------------------------------------------------------------------

def test_le_backend_navigateur_est_declare_et_mesure():
    """
    La §9 demande **un** backend, pas le moteur entier.

    Chromium est présent sur cette machine et aucun pilote ne le conduit : le
    backend est donc déclaré et indisponible, ce qui est exactement l'allure
    qu'une capacité absente doit avoir.
    """
    etats = available_backends()

    assert set(etats) == set(BACKENDS)
    assert etats["browser"]["deterministic"] is False
    assert etats["pillow"]["deterministic"] is True


def test_un_backend_est_disponible_seulement_si_ses_capacites_le_sont():
    """L'annoncer autrement ferait échouer un rendu au dernier moment."""
    for nom, etat in available_backends().items():
        attendu = all(
            valeur == "AVAILABLE"
            for valeur in etat["capability_states"].values()
        )
        assert etat["available"] is attendu, nom


def test_une_video_reelle_est_produite(tmp_path, scene):
    """
    Le volet doit produire de la vidéo, pas la décrire.

    `frame_encode` est la seule capacité mesurée disponible sur cette machine ;
    ce test l'exerce de bout en bout.
    """
    if find_ffmpeg() is None:
        pytest.skip("aucun ffmpeg dans cet environnement")

    sortie = tmp_path / "animation.webm"
    resultat = render_video(scene, str(sortie))

    assert sortie.exists()
    assert resultat["bytes"] > 0
    assert resultat["frames_sent"] == scene.frames
    assert resultat["complete"] is True
    assert resultat["frame_format"] in ("mjpeg", "png")


def test_le_fichier_produit_est_reconnu_comme_une_video(tmp_path, scene):
    """
    Le rendu est relu par l'identification du VOLET M03.

    Deux volets se vérifient l'un l'autre : si l'un des deux se trompait, ce
    test tomberait au lieu de laisser passer un fichier mal formé.
    """
    if find_ffmpeg() is None:
        pytest.skip("aucun ffmpeg dans cet environnement")

    from src.media.ingestion.identify import identify_file

    sortie = tmp_path / "animation.webm"
    render_video(scene, str(sortie))

    assert identify_file(str(sortie))["format"] == "webm"


def test_le_rendu_ne_declare_aucune_conformite(tmp_path, scene):
    """
    La distinction de la directive §21.

    Un encodeur qui sort en zéro ne dit rien de ce que le fichier contient.
    """
    if find_ffmpeg() is None:
        pytest.skip("aucun ffmpeg dans cet environnement")

    resultat = render_video(scene, str(tmp_path / "s.webm"))

    assert "verdict" not in resultat
    assert "conform" not in str(resultat.keys()).lower()
    assert "ne vérifie rien du contenu" in resultat["note"]


def test_le_rapport_refuse_de_confondre_encodage_et_conformite():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(render_report()["does_not"])

    assert "sorti en zéro" in interdits
    assert "Supposer le format de trame" in interdits
    assert "Accumuler toutes les trames" in interdits


def test_le_rapport_de_motion_refuse_l_horloge():
    """Un rendu qui lit l'heure n'est pas reproductible."""
    interdits = " ".join(motion_report()["does_not"])

    assert "Lire l'horloge" in interdits
    assert "style en dur" in interdits
