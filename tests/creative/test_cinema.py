"""
Tests de la couche cinéma (K06.1, §10).

Les deux tests qui comptent sont `TestCeQuiN_EstPasCalcule` — c'est là que ce
module diverge de l'implémentation de référence auditée en K01 — et
`TestContradiction`, qui attrape le mouvement que personne n'a demandé.
"""

import pytest

from src.creative.cinema import (
    AXES_DE_MOUVEMENT,
    FAMILLES_D_OBJECTIF,
    FORMATS_DE_CAPTEUR,
    INCONNU,
    CameraSpec,
    CinemaRefused,
    STRUCTURE,
    TEXTE_RENDU,
    LensSpec,
    MotionSpec,
    ShotSpec,
    cinema_report,
    depth_of_field_estimate,
    horizontal_field_of_view,
    render_for_provider,
)
from src.creative.direction import ADJECTIFS_SANS_DECISION, DirectorSpec


def _plan(movement: str = "static", lens_mm=None, **kwargs) -> DirectorSpec:
    return DirectorSpec(shot_size="medium", movement=movement, lens_mm=lens_mm,
                        **kwargs)


class TestBoitier:
    """Ce qui est déclaré du boîtier, et ce qui est refusé."""

    def test_un_format_inconnu_est_refuse(self):
        with pytest.raises(CinemaRefused, match="non déclaré"):
            CameraSpec(sensor_format="imax_digital")

    def test_un_format_vide_est_permis(self):
        """Ne pas décider du format est légitime ; ce n'est pas un manque."""
        assert CameraSpec().sensor_format == ""

    def test_une_largeur_negative_est_refusee(self):
        with pytest.raises(CinemaRefused, match="impossible"):
            CameraSpec(sensor_width_mm=-24.0)

    def test_un_angle_d_obturation_au_dela_du_tour_est_refuse(self):
        with pytest.raises(CinemaRefused, match="tour complet"):
            CameraSpec(shutter_angle=400)

    def test_le_nom_du_format_ne_porte_aucune_dimension(self):
        """Nommer super35 ne pose pas sa largeur : elle reste non déclarée."""
        camera = CameraSpec(sensor_format="super35")

        assert camera.sensor_width_mm is None


class TestObjectif:
    """L'ouverture est un nombre, et la focale n'est pas ici."""

    def test_l_ouverture_est_un_nombre(self):
        assert LensSpec(aperture_f=1.4).aperture_f == 1.4

    def test_une_ouverture_negative_est_refusee(self):
        with pytest.raises(CinemaRefused, match="impossible"):
            LensSpec(aperture_f=0)

    def test_une_famille_inconnue_est_refusee(self):
        with pytest.raises(CinemaRefused, match="non déclarée"):
            LensSpec(family="swirl_bokeh")

    def test_l_objectif_ne_porte_pas_de_focale(self):
        """La focale vit dans DirectorSpec ; deux endroits divergeraient."""
        assert "focal" not in LensSpec().as_dict()
        assert "lens_mm" not in LensSpec().as_dict()

    def test_le_nom_de_l_objectif_ne_decide_rien(self):
        objectif = LensSpec(name="Classic Anamorphic", family="spherical")

        assert objectif.family == "spherical"


class TestMouvement:
    """Quatre axes signés, bornés, entiers."""

    def test_les_quatre_axes_sont_ceux_declares(self):
        assert set(MotionSpec().as_dict()) == set(AXES_DE_MOUVEMENT)

    def test_zero_partout_est_un_plan_fixe(self):
        assert MotionSpec().is_static is True
        assert MotionSpec().moving_axes() == {}

    def test_les_axes_non_nuls_sont_rendus_signes(self):
        mouvement = MotionSpec(pan=-40, dolly=25)

        assert mouvement.moving_axes() == {"pan": -40, "dolly": 25}

    def test_une_amplitude_hors_bornes_est_refusee(self):
        with pytest.raises(CinemaRefused, match="hors bornes"):
            MotionSpec(pan=150)

    def test_une_amplitude_non_entiere_est_refusee(self):
        with pytest.raises(CinemaRefused, match="entier"):
            MotionSpec(tilt=12.5)

    def test_un_booleen_n_est_pas_une_amplitude(self):
        with pytest.raises(CinemaRefused, match="entier"):
            MotionSpec(zoom=True)


class TestContradiction:
    """Le mouvement catégoriel et les axes doivent dire la même chose."""

    def test_un_plan_fixe_qui_bouge_est_refuse(self):
        """Le cas LENS_MOTION_PRESET : un panoramique que rien n'a demandé."""
        with pytest.raises(CinemaRefused, match="static"):
            ShotSpec(direction=_plan("static"), motion=MotionSpec(pan=50))

    def test_un_mouvement_annonce_sans_axe_est_refuse(self):
        with pytest.raises(CinemaRefused, match="sans être décrit"):
            ShotSpec(direction=_plan("pan"), motion=MotionSpec())

    def test_un_plan_coherent_passe(self):
        plan = ShotSpec(direction=_plan("pan"), motion=MotionSpec(pan=50))

        assert plan.motion.moving_axes() == {"pan": 50}

    def test_un_plan_fixe_coherent_passe(self):
        plan = ShotSpec(direction=_plan("static"))

        assert plan.motion.is_static is True


class TestCeQuiN_EstPasCalcule:
    """Une question sans ses données rend UNKNOWN, et nomme ce qui manque."""

    def test_le_champ_de_vision_sans_largeur_est_inconnu(self):
        plan = ShotSpec(direction=_plan(lens_mm=35.0),
                        camera=CameraSpec(sensor_format="super35"))

        resultat = horizontal_field_of_view(plan)

        assert resultat["status"] == INCONNU
        assert resultat["degrees"] is None
        assert resultat["missing"] == ["sensor_width_mm"]

    def test_le_champ_de_vision_sans_focale_est_inconnu(self):
        plan = ShotSpec(direction=_plan(),
                        camera=CameraSpec(sensor_width_mm=24.89))

        resultat = horizontal_field_of_view(plan)

        assert resultat["status"] == INCONNU
        assert resultat["missing"] == ["lens_mm"]

    def test_le_champ_de_vision_se_calcule_quand_les_deux_sont_declares(self):
        plan = ShotSpec(direction=_plan(lens_mm=50.0),
                        camera=CameraSpec(sensor_width_mm=36.0))

        resultat = horizontal_field_of_view(plan)

        assert resultat["status"] == "MEASURED"
        assert resultat["degrees"] == pytest.approx(39.6, abs=0.1)

    def test_la_profondeur_de_champ_n_est_jamais_chiffree(self):
        """Même avec les quatre entrées : le cercle de confusion manque."""
        plan = ShotSpec(direction=_plan(lens_mm=50.0, depth_of_field="shallow"),
                        camera=CameraSpec(sensor_width_mm=36.0),
                        lens=LensSpec(aperture_f=1.4))

        resultat = depth_of_field_estimate(plan, subject_distance_m=2.0)

        assert resultat["status"] == INCONNU
        assert resultat["meters"] is None
        assert resultat["missing"] == []

    def test_la_profondeur_de_champ_nomme_ce_qui_manque(self):
        plan = ShotSpec(direction=_plan())

        resultat = depth_of_field_estimate(plan)

        assert set(resultat["missing"]) == {
            "aperture_f", "lens_mm", "sensor_width_mm", "subject_distance_m",
        }

    def test_l_intention_est_rendue_mais_n_est_pas_une_mesure(self):
        plan = ShotSpec(direction=_plan(depth_of_field="deep"))

        resultat = depth_of_field_estimate(plan)

        assert resultat["intent"] == "deep"
        assert resultat["meters"] is None


class TestRenduAuBord:
    """La structure reste la spécification ; le texte n'est qu'un rendu."""

    def _plan_complet(self) -> ShotSpec:
        return ShotSpec(
            direction=_plan("pan", lens_mm=35.0, depth_of_field="shallow"),
            camera=CameraSpec(sensor_format="super35", sensor_width_mm=24.89,
                              frame_rate=24, shutter_angle=180),
            lens=LensSpec(aperture_f=1.4, family="anamorphic",
                          name="Classic Anamorphic"),
            motion=MotionSpec(pan=50),
        )

    def test_un_fournisseur_qui_lit_la_structure_ne_recoit_pas_de_prose(self):
        rendu = render_for_provider(self._plan_complet(),
                                    accepts_camera_control=True)

        assert rendu["mode"] == STRUCTURE
        assert rendu["text"] == ""
        assert rendu["not_conveyed"] == []

    def test_la_structure_est_rendue_dans_les_deux_cas(self):
        plan = self._plan_complet()

        structure = render_for_provider(plan, True)["fields"]
        texte = render_for_provider(plan, False)["fields"]

        assert structure == texte == plan.as_dict()

    def test_le_texte_porte_les_valeurs_declarees(self):
        rendu = render_for_provider(self._plan_complet(), False)

        assert rendu["mode"] == TEXTE_RENDU
        assert "35mm" in rendu["text"]
        assert "f/1.4" in rendu["text"]
        assert "anamorphic lens" in rendu["text"]
        assert "24 fps" in rendu["text"]

    def test_l_amplitude_est_un_nombre_pas_un_adjectif(self):
        rendu = render_for_provider(self._plan_complet(), False)

        assert "pan left-to-right" in rendu["text"]
        assert "amplitude 50 of 100" in rendu["text"]

    def test_un_plan_fixe_le_dit(self):
        rendu = render_for_provider(ShotSpec(direction=_plan("static")), False)

        assert "locked-off camera" in rendu["text"]

    def test_ce_que_le_texte_ne_porte_pas_est_nomme(self):
        rendu = render_for_provider(self._plan_complet(), False)

        assert set(rendu["not_conveyed"]) == {
            "sensor_format", "sensor_width_mm", "shutter_angle", "lens.name",
            "depth_of_field",
        }

    def test_aucun_adjectif_d_ambiance_n_est_ajoute(self):
        """`cinematic` et `professional` sont ceux que l'implémentation
        auditée en K01 ajoute à chaque requête."""
        rendu = render_for_provider(self._plan_complet(), False)
        texte = rendu["text"].lower()

        for adjectif in ADJECTIFS_SANS_DECISION:
            assert adjectif not in texte

    def test_le_texte_ne_contient_pas_de_valeur_non_declaree(self):
        """Un plan sans focale ni ouverture ne les invente pas."""
        rendu = render_for_provider(ShotSpec(direction=_plan("static")), False)

        assert "mm" not in rendu["text"]
        assert "f/" not in rendu["text"]
        assert "fps" not in rendu["text"]


class TestRapport:
    """Le rapport dit ce qui est tenu."""

    def test_le_rapport_donne_les_vocabulaires(self):
        rapport = cinema_report()

        assert rapport["lens_families"] == list(FAMILLES_D_OBJECTIF)
        assert rapport["sensor_formats"] == list(FORMATS_DE_CAPTEUR)
        assert rapport["motion_axes"] == list(AXES_DE_MOUVEMENT)

    def test_le_rapport_dit_ou_vit_la_focale(self):
        assert cinema_report()["focal_length_lives_in"].endswith("lens_mm")

    def test_le_rapport_nomme_ce_qui_n_est_jamais_calcule(self):
        assert cinema_report()["never_computed"] == ["depth_of_field"]
