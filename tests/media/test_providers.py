"""
Choisir un générateur sur des mesures, et refuser quand aucun ne convient
(VOLET M09 du moteur média).

La directive §10 liste ce que la sélection doit peser — tâche, GPU, VRAM,
résolution, durée, latence, coût — et la §35 ajoute qu'un nouveau modèle doit
s'intégrer sans réécrire le cœur. Les deux tiennent par la même chose : un
fournisseur **déclare** ce qu'il sait faire, et le sélecteur compare ces
déclarations à ce que la machine porte réellement.

Le défaut fermé ici est le sélecteur serviable. À qui demande du 1080p et ne
trouve que du 720p, il rend le 720p — raisonnablement, et en silence. Le
demandeur reçoit autre chose que ce qu'il a demandé sans aucun moyen de s'en
apercevoir.

Ce que ces tests gardent :

1. **Aucun repli sur le plus proche.**
2. **Chaque fournisseur écarté l'est avec ses obstacles nommés.**
3. **`None` n'est jamais zéro** : coût inconnu, latence non mesurée.
4. **WanGP est un adaptateur, pas une intégration**, et le dit.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.media.providers import wangp  # noqa: E402
from src.media.providers.base import (  # noqa: E402
    AUCUN,
    CHOISI,
    TACHES,
    GenerationRequest,
    ProviderCapability,
    ProviderRefused,
    evaluate,
    select_provider,
    selection_report,
)


def _capacite(nom, **extra):
    """Un fournisseur sans dépendance matérielle, pour isoler la sélection."""
    champs = {
        "provider_id": nom,
        "tasks": frozenset({"text_to_video"}),
        "max_width": 1920, "max_height": 1080, "max_duration_s": 10.0,
        "min_vram_gb": None, "requires": (),
    }
    champs.update(extra)
    return ProviderCapability(**champs)


def _demande(**extra):
    """Une demande de 1080p, 5 secondes."""
    champs = {"task": "text_to_video", "width": 1920, "height": 1080,
              "duration_s": 5.0}
    champs.update(extra)
    return GenerationRequest(**champs)


# ----------------------------------------------------------------------
# 1. Aucun repli sur le plus proche
# ----------------------------------------------------------------------

def test_un_fournisseur_trop_petit_n_est_pas_choisi_par_defaut():
    """
    Le défaut central.

    Rendre du 720p à qui demande du 1080p est une substitution silencieuse, et
    le demandeur n'a aucun moyen de s'en apercevoir.
    """
    resultat = select_provider(
        _demande(), [_capacite("petit", max_width=1280, max_height=720)],
    )

    assert resultat["status"] == AUCUN
    assert "substitution silencieuse" in resultat["reason"]


def test_une_tache_voisine_ne_remplace_pas_la_tache_demandee():
    """Générer depuis une image et depuis un texte sont deux capacités."""
    resultat = select_provider(
        _demande(task="image_to_video"),
        [_capacite("texte", tasks=frozenset({"text_to_video"}))],
    )

    assert resultat["status"] == AUCUN


def test_le_cas_nominal_existe():
    """Refuser tout serait aussi faux que substituer."""
    resultat = select_provider(_demande(), [_capacite("complet")])

    assert resultat["status"] == CHOISI
    assert resultat["provider_id"] == "complet"


def test_une_tache_non_declaree_est_refusee_a_la_construction():
    """Une tâche inconnue n'est pas « proche » d'une tâche connue."""
    with pytest.raises(ProviderRefused):
        _capacite("bizarre", tasks=frozenset({"text_to_hologram"}))
    with pytest.raises(ProviderRefused):
        _demande(task="text_to_hologram")


def test_une_demande_sans_taille_ni_duree_est_refusee():
    """Aucun fournisseur ne peut être comparé à elle."""
    with pytest.raises(ProviderRefused):
        _demande(width=0)


# ----------------------------------------------------------------------
# 2. Chaque exclusion porte sa raison
# ----------------------------------------------------------------------

def test_chaque_obstacle_est_nomme():
    """Un refus sans raison force à tout relire."""
    verdict = evaluate(
        _capacite("petit", max_width=1280, max_height=720, max_duration_s=2.0),
        _demande(),
    )

    assert verdict["eligible"] is False
    joint = " ".join(verdict["blockers"])
    assert "largeur" in joint and "hauteur" in joint and "durée" in joint


def test_une_capacite_manquante_est_nommee_avec_son_etat():
    """L'obstacle vient d'une mesure du VOLET M01, pas d'une opinion."""
    verdict = evaluate(_capacite("gpu", requires=("gpu_compute",)), _demande())

    assert any("gpu_compute" in obstacle for obstacle in verdict["blockers"])


def test_le_determinisme_exige_ecarte_un_fournisseur_qui_ne_l_est_pas():
    """Une demande reproductible n'est pas servie par un modèle aléatoire."""
    verdict = evaluate(_capacite("aleatoire", deterministic=False),
                       _demande(require_deterministic=True))

    assert "non déterministe" in " ".join(verdict["blockers"])


def test_le_refus_liste_l_evaluation_de_chacun():
    """Corriger une sélection demande de voir tous les écarts d'un coup."""
    resultat = select_provider(_demande(), [
        _capacite("a", max_width=640, max_height=360),
        _capacite("b", tasks=frozenset({"upscale"})),
    ])

    assert len(resultat["evaluations"]) == 2
    assert all(v["eligible"] is False for v in resultat["evaluations"])


# ----------------------------------------------------------------------
# 3. `None` n'est jamais zéro
# ----------------------------------------------------------------------

def test_un_cout_inconnu_n_est_pas_classe_premier():
    """
    Un inconnu n'est pas un zéro.

    Le classer premier est la façon dont une facture arrive.
    """
    resultat = select_provider(
        _demande(),
        [_capacite("inconnu", cost_per_second=None),
         _capacite("connu", cost_per_second=0.5)],
        prefer="cheapest",
    )

    assert resultat["provider_id"] == "connu"
    assert "inconnu" in resultat["excluded_for_unknown_metric"]


def test_sans_aucun_cout_declare_la_selection_refuse():
    """Choisir au hasard vaudrait moins qu'un refus explicite."""
    resultat = select_provider(
        _demande(), [_capacite("a"), _capacite("b")], prefer="cheapest",
    )

    assert resultat["status"] == AUCUN
    assert set(resultat["eligible_but_unranked"]) == {"a", "b"}
    assert "n'est pas un zéro" in resultat["reason"]


def test_une_latence_non_mesuree_ecarte_du_classement_par_vitesse():
    """Inventer une latence typique ferait d'une estimation une promesse (§33)."""
    resultat = select_provider(
        _demande(),
        [_capacite("sans_mesure"), _capacite("mesure", typical_latency_s=12.0)],
        prefer="fastest",
    )

    assert resultat["provider_id"] == "mesure"


def test_aucun_gpu_requis_n_est_pas_zero_go():
    """Les deux sont différents, et seul le second se compare à une mesure."""
    sans_gpu = evaluate(_capacite("cpu", min_vram_gb=None), _demande())
    avec_gpu = evaluate(_capacite("gpu", min_vram_gb=6.0), _demande())

    assert sans_gpu["eligible"] is True
    assert any("VRAM" in obstacle for obstacle in avec_gpu["blockers"])


def test_une_vram_non_mesurable_rend_le_fournisseur_indisponible():
    """La supposer ferait échouer la génération après plusieurs minutes."""
    verdict = evaluate(_capacite("gros", min_vram_gb=24.0), _demande())

    assert "pas mesurable" in " ".join(verdict["blockers"])


# ----------------------------------------------------------------------
# 4. WanGP : un adaptateur, pas une intégration
# ----------------------------------------------------------------------

def test_l_adaptateur_declare_ne_pas_etre_integre():
    """
    La clause de repli de la §11, appliquée pour des raisons **mesurées**.

    « Prêt, en attente de configuration » laisserait croire qu'une clé
    suffirait.
    """
    etat = wangp.health()

    assert etat["integration"] == "ADAPTER_ONLY"
    assert etat["vendored"] is False
    assert etat["capabilities_verified"] is False


def test_la_licence_non_lue_bloque_a_elle_seule():
    """Embarquer du code dont personne n'a lu les termes est une décision
    juridique prise par une machine."""
    etat = wangp.health()

    assert etat["licence"] == "UNKNOWN"
    assert etat["licence_verified"] is False
    assert "licence_not_inspected" in etat["blockers"]


def test_l_absence_de_gpu_est_un_blocage_distinct():
    """Les deux conditions sont indépendantes : ni l'une ni l'autre ne suffit."""
    etat = wangp.health()

    assert "no_gpu" in etat["blockers"]
    assert etat["gpu_state"] != "AVAILABLE"
    assert wangp.is_available() is False


def test_generer_refuse_au_lieu_d_ecrire_un_marbre_noir(tmp_path):
    """
    Un fichier de remplacement s'encode sans erreur.

    Il descend la chaîne, passe les contrôles de durée, et n'échoue que devant
    un spectateur.
    """
    sortie = tmp_path / "generee.webm"

    with pytest.raises(wangp.WanGPUnavailable) as refus:
        wangp.generate(_demande(), str(sortie))

    assert not sortie.exists()
    assert "marbre noir" in str(refus.value)


def test_les_capacites_annoncees_sont_des_attentes_pas_des_mesures():
    """Rien n'a tourné ici ; la distinction doit être portée par l'objet."""
    etat = wangp.health()

    assert etat["expected_capability"]["provider_id"] == "wangp"
    assert etat["expected_capability"]["licence"] is None
    assert "attentes, pas des mesures" in etat["note"]


def test_le_depot_n_est_pas_copie_dans_le_projet():
    """La directive §11 l'interdit, et §36 interdit d'importer à l'aveugle."""
    racine = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))

    assert not os.path.exists(os.path.join(racine, "src", "media", "wan2gp"))
    assert not os.path.exists(os.path.join(racine, "Wan2GP"))
    assert wangp.integration_report()["status"] == "ADAPTER_ONLY"


def test_le_rapport_refuse_de_declarer_une_licence_non_lue():
    """La règle est écrite là où elle est appliquée."""
    interdits = " ".join(wangp.integration_report()["does_not"])

    assert "licence qui n'a pas été lue" in interdits
    assert "Copier un dépôt tiers" in interdits
    assert "fichier de remplacement" in interdits


def test_le_rapport_de_selection_refuse_la_substitution():
    """Une dégradation appartient à qui fait le film."""
    rapport = selection_report()

    interdits = " ".join(rapport["does_not"])
    assert "Substituer un fournisseur proche" in interdits
    assert "Inventer une latence typique" in interdits
    assert set(rapport["tasks"]) == set(TACHES)
