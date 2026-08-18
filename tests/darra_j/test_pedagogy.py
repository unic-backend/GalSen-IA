"""
Expliquer un fait officiel sans en devenir l'auteur
(VOLET 8 de Darra J).

La directive XIII demande cinq niveaux d'explication. La phrase qui compte est
celle qui suit : *le fait de curriculum sous-jacent doit rester identique.* Une
couche pédagogique capable d'atteindre le titre officiel finira par l'améliorer,
et un titre officiel amélioré n'est plus officiel.

Ce que ces tests gardent :

1. **L'explication ne rend que du texte** — il n'existe aucune forme dans
   laquelle elle pourrait renvoyer un champ officiel modifié.
2. **Le fait est réattaché depuis l'original**, jamais depuis la sortie du
   modèle.
3. **Une explication qui échoue est une absence**, pas un repli générique.
4. **Les cinq niveaux sont déclarés** : deviner un niveau non défini produirait
   un enseignement différent d'une école à l'autre.
5. **Un plan de rattrapage est généré, et il le dit** — sans durée inventée.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.darra_j.pedagogy import (  # noqa: E402
    CHAMPS_INTOUCHABLES,
    NIVEAUX,
    PedagogyRefused,
    catch_up_plan,
    describe_level,
    explain,
    pedagogy_report,
)

FAIT = {
    "official_title": "Les fractions",
    "official_description": "Comparer et additionner des fractions simples.",
    "competencies": ["Comparer deux fractions"],
    "objectives": ["Additionner deux fractions de même dénominateur"],
    "prerequisites": ["La division euclidienne"],
    "activities": [],
    "evaluation_requirements": [],
    "content_hash": "abc123",
}


def _texte(sortie="Une fraction, c'est une part d'un tout."):
    """Un générateur qui retient ce qu'il a reçu."""
    recus = []

    def generateur(contexte):
        recus.append(contexte)
        return sortie

    generateur.recus = recus
    return generateur


# ----------------------------------------------------------------------
# 1. Les cinq niveaux sont déclarés
# ----------------------------------------------------------------------

def test_les_cinq_niveaux_existent():
    """Ni quatre, ni six : la directive XIII en nomme cinq."""
    assert sorted(NIVEAUX) == [1, 2, 3, 4, 5]


def test_chaque_niveau_dit_son_public_et_sa_consigne():
    """Un niveau sans consigne laisserait le modèle décider du ton."""
    for niveau in NIVEAUX:
        details = describe_level(niveau)
        assert details["name"] and details["audience"] and details["instruction"]


def test_un_niveau_non_declare_est_refuse():
    """Deviner « niveau 9 » produirait un enseignement différent par école."""
    with pytest.raises(PedagogyRefused) as refus:
        describe_level(9)

    assert "une école à l'autre" in str(refus.value)


def test_le_niveau_change_l_explication_pas_le_fait():
    """Cinq présentations, un seul fait."""
    simple = explain(FAIT, level=1, generator=_texte("Simple."))
    expert = explain(FAIT, level=5, generator=_texte("Expert."))

    assert simple["canonical"] == expert["canonical"] == FAIT
    assert simple["explanation"] != expert["explanation"]
    assert (simple["level_name"], expert["level_name"]) == ("very_simple", "expert")


# ----------------------------------------------------------------------
# 2. Le fait reste intact
# ----------------------------------------------------------------------

def test_le_generateur_recoit_une_copie_pas_l_original():
    """S'il modifiait ce qu'il reçoit, il modifierait le fait de l'appelant."""
    def saboteur(contexte):
        contexte["canonical"]["official_title"] = "Les fractions, version claire"
        return "…"

    reponse = explain(FAIT, generator=saboteur)

    assert FAIT["official_title"] == "Les fractions"
    assert reponse["canonical"]["official_title"] == "Les fractions"


def test_le_fait_est_reattache_depuis_l_original():
    """
    Le cas qu'une réattache depuis la sortie du modèle manquerait.

    Le générateur ne rend que du texte : même en y recopiant un titre réécrit,
    il n'a aucune forme dans laquelle le faire remonter dans le champ officiel.
    """
    reponse = explain(
        FAIT,
        generator=_texte('official_title = "Les fractions, réécrites"'),
    )

    assert reponse["canonical"]["official_title"] == "Les fractions"
    assert "réécrites" in reponse["explanation"]


def test_l_explication_est_separee_du_fait():
    """Les fondre rendrait indistinguable ce que le ministère a dit."""
    reponse = explain(FAIT, generator=_texte())

    assert reponse["canonical"]["objectives"] == FAIT["objectives"]
    assert reponse["explanation"] == "Une fraction, c'est une part d'un tout."


def test_le_generateur_recoit_la_consigne_du_niveau():
    """Sans elle, les cinq niveaux ne seraient qu'un entier passé au modèle."""
    generateur = _texte()

    explain(FAIT, level=3, generator=generateur)

    contexte = generateur.recus[0]
    assert contexte["level"] == 3
    assert contexte["level_name"] == "detailed"
    assert contexte["instruction"] == NIVEAUX[3]["instruction"]


def test_les_champs_intouchables_sont_ceux_du_fait_officiel():
    """La liste sert au rapport ; elle doit correspondre à ce qui est rendu."""
    assert set(CHAMPS_INTOUCHABLES) <= set(FAIT)


# ----------------------------------------------------------------------
# 3. Une explication absente reste une absence
# ----------------------------------------------------------------------

def test_un_generateur_qui_echoue_ne_declenche_pas_de_repli():
    """Substituer une leçon générique est l'invention qu'on veut empêcher."""
    def casse(contexte):
        raise RuntimeError("modèle indisponible")

    reponse = explain(FAIT, generator=casse)

    assert reponse["explanation"] is None
    assert reponse["explanation_available"] is False
    assert "RuntimeError" in reponse["reason"]


def test_sans_generateur_le_fait_sort_quand_meme():
    """Directive XXXV : le fait reste consultable sans le modèle."""
    reponse = explain(FAIT, generator=None)

    assert reponse["canonical"]["official_title"] == "Les fractions"
    assert reponse["explanation"] is None


def test_l_absence_rend_la_meme_forme_que_le_cas_nominal():
    """
    Sinon un appelant échouerait précisément quand l'explication a manqué.

    Lire `language` ou `level_name` ne doit pas dépendre de la réussite du
    modèle : c'est au pire moment que la réponse doit rester lisible.
    """
    def casse(contexte):
        raise RuntimeError("modèle indisponible")

    nominal = explain(FAIT, level=3, generator=_texte(), language="wo")
    absent = explain(FAIT, level=3, generator=casse, language="wo")
    sans = explain(FAIT, level=3, generator=None, language="wo")

    commun = {"canonical", "explanation", "level", "level_name", "language",
              "explanation_available"}
    assert commun <= set(nominal) & set(absent) & set(sans)
    assert absent["level_name"] == sans["level_name"] == "detailed"
    assert absent["language"] == sans["language"] == "wo"


def test_une_explication_vide_est_signalee_comme_indisponible():
    """Une chaîne vide n'est pas une explication."""
    reponse = explain(FAIT, generator=_texte("   "))

    assert reponse["explanation_available"] is False


def test_expliquer_sans_fait_est_refuse():
    """Une explication sans fait est une leçon inventée."""
    with pytest.raises(PedagogyRefused) as refus:
        explain({}, generator=_texte())

    assert "pare-feu" in str(refus.value)


def test_un_niveau_inconnu_est_refuse_avant_toute_generation():
    """Le modèle n'est pas appelé pour un niveau que personne n'a défini."""
    generateur = _texte()

    with pytest.raises(PedagogyRefused):
        explain(FAIT, level=0, generator=generateur)

    assert generateur.recus == []


# ----------------------------------------------------------------------
# 4. Le plan de rattrapage
# ----------------------------------------------------------------------

def _unite(unit_id, titre, semaine, prerequis=()):
    """Une unité manquée, telle que le registre la rend."""
    return {
        "unit_id": unit_id, "official_title": titre,
        "period": {"academic_year": "2026-2027", "week": semaine},
        "prerequisites": list(prerequis),
    }


def test_l_ordre_suit_la_sequence_officielle():
    """L'ordre vient du curriculum, pas d'une difficulté que nul n'a mesurée."""
    plan = catch_up_plan([
        _unite("u-12", "Les décimaux", 12),
        _unite("u-09", "La division", 9),
        _unite("u-10", "Les fractions", 10),
    ])

    assert plan["order"] == ["u-09", "u-10", "u-12"]
    assert plan["sequence_source"] == "official_curriculum_period_then_prerequisites"


def test_les_prerequis_manques_sont_signales_comme_bloquants():
    """Rattraper les fractions avant la division ne sert à rien."""
    plan = catch_up_plan([
        _unite("u-09", "La division", 9),
        _unite("u-10", "Les fractions", 10, prerequis=["La division"]),
    ])

    assert plan["blocking"] == [{"unit_id": "u-10", "blocked_by": ["La division"]}]


def test_un_prerequis_deja_acquis_ne_bloque_pas():
    """Seul ce qui manque **aussi** bloque."""
    plan = catch_up_plan([
        _unite("u-10", "Les fractions", 10, prerequis=["La division euclidienne"]),
    ])

    assert plan["blocking"] == []


def test_le_plan_dit_qu_il_est_genere():
    """Un plan qui se ferait passer pour officiel serait un faux."""
    plan = catch_up_plan([_unite("u-10", "Les fractions", 10)])

    assert plan["content_type"] == "AI_GENERATED"
    assert "ni la classe ni l'enseignant" in plan["note"]


def test_aucune_duree_n_est_estimee():
    """Une estimation que personne n'a mesurée se lirait comme une promesse."""
    plan = catch_up_plan([_unite("u-10", "Les fractions", 10)], available_hours=6.0)

    assert plan["hours_estimate"] is None
    assert plan["available_hours"] == 6.0


# ----------------------------------------------------------------------
# 5. Ce que la couche ne fait pas
# ----------------------------------------------------------------------

def test_le_rapport_nomme_les_niveaux_et_les_champs_intouchables():
    """Une interface doit pouvoir montrer ce qui est protégé."""
    rapport = pedagogy_report()

    assert sorted(rapport["levels"]) == [1, 2, 3, 4, 5]
    assert "official_title" in rapport["untouchable_fields"]


def test_le_rapport_refuse_de_reformuler_un_champ_officiel():
    """Même « pour le rendre plus clair » : la clarté est le travail d'à côté."""
    interdits = " ".join(pedagogy_report()["does_not"])

    assert "Reformuler un champ officiel" in interdits
    assert "Estimer une durée" in interdits
