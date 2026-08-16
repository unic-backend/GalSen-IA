"""
Sous-titres découpés sur des mots mesurés, et un logo qui ne se redessine pas
(VOLETs M11 et M12 du moteur média).

La directive §15 nomme le wolof et l'arabe, et chacun apporte une contrainte que
ce dépôt connaît déjà.

`ë`, `ñ` et `ŋ` sont des **lettres** du standard CLAD, pas des variantes
accentuées. Darra J a payé exactement cette erreur : la table d'alias ne gardait
que la forme repliée, donc `translate()` — une fonction d'affichage — rendait
`mbey` pour `mbéy`. Un sous-titre est de l'affichage par définition.

L'arabe se lit de droite à gauche, et le sens est **déclaré par la langue**, pas
reniflé sur le texte : une phrase arabe contenant un nom propre latin
basculerait sur une heuristique et tiendrait sur une déclaration.

La §16 ajoute une règle qui ressemble à une note de style sans en être une :
*ne recrée jamais un logo reconnaissable par une image générée quand un asset
officiel existe.* Un logo presque juste passe la relecture, est livré, et
atteint la seule personne qui le connaît par cœur — pendant que le fichier de la
marque était dans le registre.

Ce que ces tests gardent :

1. **Aucune coupe au milieu d'un mot**, aucun sous-titre à cheval sur une coupe.
2. **Une vitesse de lecture dépassée est signalée, pas corrigée en étirant.**
3. **Le sens de lecture est déclaré**, jamais deviné.
4. **Un logo n'est jamais généré.**
5. **Rien n'entre sans source.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.assets.registry import (  # noqa: E402
    DROITS_CONNUS,
    DROITS_INCONNUS,
    NATURES_PROTEGEES,
    Asset,
    AssetRefused,
    AssetRegistry,
    asset_report,
    file_hash,
)
from src.media.core.project import (  # noqa: E402
    ORIGINE_GENEREE,
    ORIGINE_INCONNUE,
    ORIGINE_SOURCEE,
)
from src.media.subtitles.cues import (  # noqa: E402
    CPS_MAXIMUM,
    LANGUES,
    Cue,
    SubtitleRefused,
    build_cues,
    check_cue,
    preserves_script,
    subtitle_report,
)
from src.media.transcription.words import (  # noqa: E402
    WordTiming,
    WordTimingUnavailable,
    words_from_segments,
)


def _mots(paires):
    """Des mots avec des temps mesurés."""
    return [WordTiming(word=m, start=a, end=b) for m, a, b in paires]


@pytest.fixture
def phrase():
    """Une phrase de neuf mots, temps mesurés."""
    return _mots([
        ("Il", 0.0, 0.2), ("faut", 0.25, 0.5), ("comparer", 0.55, 1.1),
        ("deux", 1.15, 1.35), ("fractions", 1.4, 2.0),
        ("avant", 2.4, 2.7), ("de", 2.75, 2.85), ("les", 2.9, 3.05),
        ("additionner", 3.1, 3.9),
    ])


def _officiel(**extra):
    """Un logo officiel complet."""
    champs = {"asset_id": "logo-sonatel", "kind": "logo", "brand": "Sonatel",
              "origin": ORIGINE_SOURCEE, "source": "https://exemple/brand.svg",
              "licence": "usage-autorise", "rights": DROITS_CONNUS,
              "sha256": "ab" * 32}
    champs.update(extra)
    return Asset(**champs)


# ----------------------------------------------------------------------
# 1. Découpé sur des mots mesurés
# ----------------------------------------------------------------------

def test_les_sous_titres_ne_coupent_jamais_un_mot(phrase):
    """Le mot entier est dans un sous-titre ou dans l'autre, jamais entre."""
    resultat = build_cues(phrase, max_chars=30)

    tous = " ".join(c["text"] for c in resultat["cues"]).split()
    assert tous == [mot.word for mot in phrase]


def test_un_sous_titre_ne_traverse_pas_un_changement_de_scene(phrase):
    """Une légende qui survit à une coupe appartient au plan qu'elle ne
    recouvre plus."""
    resultat = build_cues(phrase, scene_boundaries=[2.2])

    for cue in resultat["cues"]:
        assert not (cue["start"] < 2.2 < cue["end"])


def test_des_temps_estimes_sont_refuses():
    """Un sous-titre qui apparaît au milieu d'une syllabe est le défaut le
    plus visible de la chaîne."""
    estimes = words_from_segments(
        [{"text": "il faut comparer", "start": 0.0, "end": 1.2}],
        interpolate=True,
    )["words"]

    with pytest.raises(WordTimingUnavailable) as refus:
        build_cues(estimes)

    assert "milieu d'une syllabe" in str(refus.value)


def test_sans_mot_aucun_sous_titre_n_est_produit():
    """Un sous-titre vide apparaîtrait à l'écran sans raison."""
    with pytest.raises(SubtitleRefused) as refus:
        build_cues([])

    assert "sans raison" in str(refus.value)


def test_les_temps_viennent_des_mots_pas_d_un_arrondi(phrase):
    """Le premier sous-titre commence exactement au premier mot."""
    resultat = build_cues(phrase, max_chars=30)

    assert resultat["cues"][0]["start"] == phrase[0].start


# ----------------------------------------------------------------------
# 2. Trop rapide est signalé, pas étiré
# ----------------------------------------------------------------------

def test_une_vitesse_de_lecture_depassee_est_signalee():
    """
    L'étirer désynchroniserait le sous-titre de la parole qu'il porte.

    On échangerait un problème visible contre un problème invisible.
    """
    rapide = Cue(index=1, start=0.0, end=1.0,
                 text="Une phrase beaucoup trop longue pour une seule seconde")

    verdict = check_cue(rapide)

    types = {probleme["kind"] for probleme in verdict["problems"]}
    assert "too_fast" in types
    assert rapide.cps > CPS_MAXIMUM


def test_un_sous_titre_correct_ne_declenche_rien():
    """Le cas nominal ne doit pas crier au loup."""
    correct = Cue(index=1, start=0.0, end=3.0, text="Il faut comparer")

    assert check_cue(correct)["ok"] is True


def test_un_sous_titre_trop_court_est_signale():
    """L'œil n'a pas le temps."""
    bref = Cue(index=1, start=0.0, end=0.2, text="Oui")

    types = {p["kind"] for p in check_cue(bref)["problems"]}
    assert "too_short" in types


def test_une_duree_nulle_n_a_pas_de_vitesse_de_lecture():
    """`None` n'est pas zéro : elle a un défaut, pas une vitesse."""
    vide = Cue(index=1, start=2.0, end=2.0, text="Texte")

    assert vide.cps is None
    assert {p["kind"] for p in check_cue(vide)["problems"]} == {"empty_interval"}


def test_le_texte_est_reparti_sans_couper_de_mot():
    """Une ligne coupée au milieu d'un mot se lit deux fois."""
    long = Cue(index=1, start=0.0, end=5.0,
               text="Il faut comparer deux fractions avant de les additionner "
                    "correctement")

    for ligne in long.lines:
        assert not ligne.startswith(" ") and not ligne.endswith(" ")
    assert " ".join(long.lines) == long.text


# ----------------------------------------------------------------------
# 3. Le sens de lecture et l'orthographe
# ----------------------------------------------------------------------

def test_l_arabe_est_declare_de_droite_a_gauche():
    """Deviner sur le texte ferait basculer une phrase avec un nom latin."""
    arabe = Cue(index=1, start=0.0, end=3.0, text="مرحبا", language="ar")

    assert arabe.direction == "rtl"
    assert LANGUES["ar"]["direction"] == "rtl"


def test_une_langue_non_declaree_est_refusee():
    """Deviner son sens afficherait de l'arabe à l'envers."""
    with pytest.raises(SubtitleRefused) as refus:
        build_cues(_mots([("mot", 0.0, 1.0)]), language="zz")

    assert "à l'envers" in str(refus.value)


def test_les_lettres_clad_survivent_a_l_affichage():
    """
    Ce dépôt a déjà payé cette erreur une fois.

    La table d'alias ne gardait que la forme repliée, donc une fonction
    d'affichage rendait `mbey` pour `mbéy`.
    """
    resultat = build_cues(
        _mots([("Mbéy", 0.0, 0.6), ("ñu", 0.7, 1.0), ("ŋ", 1.1, 1.3)]),
        language="wo",
    )

    texte = resultat["cues"][0]["text"]
    assert "é" in texte and "ñ" in texte and "ŋ" in texte


def test_un_texte_wolof_replie_est_detecte():
    """`mbey` sans lettre CLAD est du wolof faux à l'écran."""
    verdict = preserves_script("mbey ci tool bi", "wo")

    assert verdict["looks_folded"] is True
    assert "déjà payé cette erreur" in verdict["reason"]


def test_le_controle_clad_ne_s_applique_qu_au_wolof():
    """L'appliquer au français signalerait chaque phrase sans accent."""
    assert preserves_script("hello world", "en")["checked"] is False


def test_les_mots_a_souligner_sont_reperes(phrase):
    """La §15 autorise l'emphase sur des mots stratégiques."""
    resultat = build_cues(phrase, max_chars=200, emphasis=["fractions"])

    assert "fractions" in resultat["cues"][0]["emphasis"]


# ----------------------------------------------------------------------
# 4. Un logo ne se redessine pas
# ----------------------------------------------------------------------

def test_un_logo_absent_du_registre_ne_peut_pas_etre_genere():
    """
    Il faut le demander à la marque.

    Un logo presque juste passe la relecture, est livré, et atteint la seule
    personne qui le connaît par cœur.
    """
    verdict = AssetRegistry().resolve("Sonatel", kind="logo")

    assert verdict["found"] is False
    assert verdict["may_generate"] is False
    assert "connaît par cœur" in verdict["reason"]


def test_un_logo_enregistre_est_rendu_et_la_generation_reste_refusee():
    """Le fichier officiel était dans le registre pendant tout ce temps."""
    registre = AssetRegistry()
    registre.register(_officiel())

    verdict = registre.resolve("Sonatel")

    assert verdict["found"] is True
    assert verdict["usable"] is True
    assert verdict["may_generate"] is False


def test_un_logo_aux_droits_inconnus_ne_debloque_pas_la_generation():
    """En générer un ne réglerait pas le problème de droits — il en créerait
    un second."""
    registre = AssetRegistry()
    registre.register(_officiel(rights=DROITS_INCONNUS))

    verdict = registre.resolve("Sonatel")

    assert verdict["usable"] is False
    assert verdict["may_generate"] is False
    assert "second" in verdict["reason"]


def test_une_nature_non_protegee_peut_etre_generee():
    """Refuser tout serait aussi faux que tout autoriser."""
    verdict = AssetRegistry().resolve("Quelqu'un", kind="icon")

    assert verdict["may_generate"] is True


def test_un_logo_sans_marque_nommee_est_refuse():
    """Il ne pourrait pas être retrouvé quand on demandera « le logo de X »."""
    with pytest.raises(AssetRefused) as refus:
        Asset(asset_id="x", kind="logo", brand="")

    assert "fait redessiner un logo" in str(refus.value)


@pytest.mark.parametrize("nature", NATURES_PROTEGEES)
def test_chaque_nature_protegee_refuse_la_generation(nature):
    """La liste est courte et doit le rester visiblement."""
    assert AssetRegistry().resolve("Marque", kind=nature)["may_generate"] is False


# ----------------------------------------------------------------------
# 5. Rien n'entre sans source
# ----------------------------------------------------------------------

def test_un_asset_source_sans_provenance_est_incomplet():
    """Jamais « probablement bon »."""
    partiel = Asset(asset_id="a", kind="image", origin=ORIGINE_SOURCEE,
                    source="https://exemple/x.png")

    assert set(partiel.missing_fields) == {"licence", "sha256"}
    assert partiel.usable is False


def test_un_asset_genere_reste_employable_mais_garde_son_origine():
    """Personne d'autre n'en détient les droits ; ce qu'il garde, c'est
    l'origine."""
    genere = Asset(asset_id="g", kind="image", origin=ORIGINE_GENEREE)

    assert genere.usable is True
    assert genere.as_dict()["origin"] == ORIGINE_GENEREE


def test_une_origine_inconnue_est_incomplete():
    """`UNKNOWN_ORIGIN` est un aveu, pas un laissez-passer."""
    assert "origin" in Asset(asset_id="i", kind="image",
                             origin=ORIGINE_INCONNUE).missing_fields


def test_ecraser_un_asset_existant_est_refuse():
    """Cela changerait sans trace ce qu'une production passée a employé."""
    registre = AssetRegistry()
    registre.register(_officiel())

    with pytest.raises(AssetRefused) as refus:
        registre.register(_officiel(source="https://autre/brand.svg"))

    assert "sans trace" in str(refus.value)


def test_reenregistrer_le_meme_asset_est_permis():
    """Un import idempotent est le cas normal d'une reprise."""
    registre = AssetRegistry()
    registre.register(_officiel())
    registre.register(_officiel())

    assert registre.report()["count"] == 1


def test_aucune_suppression_n_est_exposee():
    """Un asset retiré est un asset qu'une production passée ne peut plus
    justifier."""
    noms = dir(AssetRegistry)

    assert not [n for n in noms if "delete" in n or "remove" in n or "purge" in n]


def test_une_empreinte_illisible_est_refusee(tmp_path):
    """Une empreinte vide ferait passer deux fichiers différents pour le même."""
    with pytest.raises(AssetRefused):
        file_hash(str(tmp_path / "jamais_ecrit.png"))


def test_une_empreinte_reelle_est_calculee(tmp_path):
    """Le cas nominal existe, et il est déterministe."""
    fichier = tmp_path / "x.bin"
    fichier.write_bytes(b"GalSen")

    assert file_hash(str(fichier)) == file_hash(str(fichier))
    assert len(file_hash(str(fichier))) == 64


# ----------------------------------------------------------------------
# 6. Ce que les deux volets refusent
# ----------------------------------------------------------------------

def test_le_rapport_des_sous_titres_refuse_d_etirer():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(subtitle_report()["does_not"])

    assert "Couper au milieu d'un mot" in interdits
    assert "Étirer un sous-titre" in interdits
    assert "wolof replié" in interdits


def test_le_rapport_des_assets_refuse_de_generer_un_logo():
    """C'est la première phrase de la directive §16."""
    rapport = asset_report()

    interdits = " ".join(rapport["does_not"])
    assert "Générer un logo" in interdits
    assert "droits sont inconnus" in interdits
    assert set(rapport["protected_kinds"]) == set(NATURES_PROTEGEES)
