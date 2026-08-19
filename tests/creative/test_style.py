"""
Tests for the style registry (C19, directive V4 §46).

This volet exists because §46 slipped through the forty-three-phase plan: the
PHASE 0 audit classified StyleEngine as `EXTENSION_REQUIRED` and no phase was
ever allocated to it. Measured before the module was written, the creative
representation tracked `domain`, `duration_seconds` and `aspect` and nothing
else — "une scène en style anime" lost the word "anime" between the request and
the render.

Three properties carry these tests.

**A style is data.** Adding one must not be a commit, because §46 ends its list
with "future styles" and visual fashion moves faster than this repository.

**A style is never part of the world.** The same street, the same people, the
same shop can be photoreal or cartoon. Style inside `WorldState` would make the
first continuity check compare a documentary against a drawing and report a
break that does not exist.

**No style is ever chosen for the author.** A request naming none stays without
one, and a request naming two is an author's hesitation — resolving it at random
decides in their place.
"""

import pytest

from src.creative.representation import DECLARE, from_request
from src.creative.style import (
    CHAMP,
    StyleRegistryError,
    apply_style,
    known_styles,
    load_styles,
    resolve_style,
    style_record,
    style_report,
    world_is_style_free,
)
from src.creative.world import WorldState


def _registre(tmp_path, contenu):
    """Écrit un registre de test et rend son chemin."""
    chemin = tmp_path / "styles.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return str(chemin)


class TestRegistre:
    """Un style est une ligne de données, et le fichier est vérifié."""

    def test_les_familles_de_la_directive_sont_couvertes(self):
        styles = known_styles()
        for attendu in ("photorealistic", "cinematic", "documentary",
                        "commercial", "realistic_3d", "stylised_3d", "anime",
                        "cartoon", "fantasy", "experimental"):
            assert attendu in styles, f"§46 nomme « {attendu} »."

    def test_ajouter_un_style_ne_touche_aucun_code(self, tmp_path):
        chemin = _registre(tmp_path, """
families: [graphic]
styles:
  - {id: vaporwave, name: vaporwave, family: graphic, aliases: [vapo]}
""")
        registre = load_styles(chemin)
        assert list(registre) == ["vaporwave"]
        assert resolve_style("un clip vapo", chemin).style_id == "vaporwave"

    def test_une_famille_non_declaree_est_refusee(self, tmp_path):
        chemin = _registre(tmp_path, """
families: [graphic]
styles:
  - {id: x, name: x, family: inventee}
""")
        with pytest.raises(StyleRegistryError) as erreur:
            load_styles(chemin)
        assert "non " in str(erreur.value)

    def test_un_alias_partage_est_refuse(self, tmp_path):
        """Le rendu dépendrait de l'ordre de lecture du fichier."""
        chemin = _registre(tmp_path, """
families: [graphic]
styles:
  - {id: a, name: a, family: graphic, aliases: [manga]}
  - {id: b, name: b, family: graphic, aliases: [manga]}
""")
        with pytest.raises(StyleRegistryError) as erreur:
            load_styles(chemin)
        assert "ordre de lecture" in str(erreur.value)

    def test_un_registre_vide_est_refuse(self, tmp_path):
        with pytest.raises(StyleRegistryError):
            load_styles(_registre(tmp_path, "families: [graphic]\nstyles: []\n"))

    def test_un_registre_absent_est_refuse(self, tmp_path):
        with pytest.raises(StyleRegistryError) as erreur:
            load_styles(str(tmp_path / "nulle-part.yaml"))
        assert "introuvable" in str(erreur.value)

    def test_un_style_inconnu_n_est_pas_devine(self):
        with pytest.raises(StyleRegistryError) as erreur:
            style_record("steampunk")
        assert "styles.yaml" in str(erreur.value)


class TestResolution:
    """Ce qui est nommé est retenu ; rien d'autre ne l'est."""

    def test_un_style_nomme_est_retenu(self):
        assert resolve_style("une scène en style anime").style_id == "anime"

    def test_les_alias_francais_fonctionnent(self):
        """Les utilisateurs de cette plateforme écrivent en français."""
        assert resolve_style("du photoréaliste").style_id == "photorealistic"
        assert resolve_style("un documentaire").style_id == "documentary"

    def test_l_accent_ne_decide_pas(self):
        assert resolve_style("en animé").style_id == \
               resolve_style("en anime").style_id

    def test_l_enonce_le_plus_long_gagne(self):
        """« dessin animé » contient « animé » : les compter tous deux ferait
        passer une demande claire pour une hésitation."""
        assert resolve_style("un dessin animé").style_id == "cartoon"

    def test_aucun_style_nomme_rend_none(self):
        """`None` est une réponse : une production sans style reste sans style."""
        assert resolve_style("une vidéo de trente secondes") is None

    def test_deux_styles_nommes_ne_tranchent_pas(self):
        """Trancher l'hésitation de l'auteur revient à décider à sa place."""
        assert resolve_style("en anime ou en cartoon") is None

    def test_un_mot_proche_n_est_pas_rattache(self):
        """« rétro » n'est pas « fantastique »."""
        assert resolve_style("un clip rétro") is None

    def test_une_sous_chaine_ne_declenche_pas(self):
        """« bd » ne doit pas s'allumer dans « abdomen »."""
        assert resolve_style("une radiographie de l'abdomen") is None


class TestApplication:
    """Le style vient de la personne, pas d'un module."""

    def test_le_style_est_pose_comme_declare_jamais_deduit(self):
        representation = from_request("une scène en style anime")
        assert apply_style(representation)["applied"] is True
        champ = representation.field(CHAMP)
        assert champ.value == "anime"
        assert champ.provenance == DECLARE, (
            "En `INFERRED`, le style paraîtrait choisi par un module."
        )

    def test_sans_style_rien_n_est_pose(self):
        representation = from_request("une vidéo de trente secondes")
        resultat = apply_style(representation)
        assert resultat["applied"] is False
        assert "état légitime" in resultat["reason"]

    def test_l_absence_de_style_n_est_pas_un_manque_a_combler(self):
        """Sinon toute demande sans style serait déclarée incomplète."""
        from src.creative.representation import CHAMPS_REQUIS
        assert CHAMP not in CHAMPS_REQUIS
        assert style_report()["required"] is False


class TestSeparationDuMonde:
    """§46 : le style n'entre pas dans `WorldState`."""

    def test_un_monde_neuf_ne_porte_aucun_style(self):
        constat = world_is_style_free(WorldState(environment="Dakar"))
        assert constat["style_free"] is True
        assert constat["attributes"] == []

    def test_un_style_dans_le_monde_est_detecte(self):
        """La règle est facile à respecter tant qu'on y pense ; le module
        suivant qui ajoutera « juste un champ » n'y pensera pas."""
        monde = WorldState()
        monde.style = "anime"
        constat = world_is_style_free(monde)
        assert constat["style_free"] is False
        assert "style" in constat["attributes"]
        assert "documentaire" in constat["reason"]


class TestRapport:
    """Ce que nommer un style ne dit pas."""

    def test_nommer_n_est_pas_produire(self):
        refus = " ".join(style_report()["does_not"])
        assert "capacité" in refus

    def test_une_famille_regroupe_et_ne_classe_pas(self):
        regles = " ".join(style_report()["rules"])
        assert "n'est pas au-dessous" in regles

    def test_le_rapport_dit_que_le_style_n_est_pas_dans_le_monde(self):
        assert any("WorldState" in regle for regle in style_report()["rules"])
