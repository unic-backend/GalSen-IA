"""
Les couches de mémoire : une couche **est** une durée de vie (phase 60.1).

Les six types de mémoire existaient déjà, et chacun était employé correctement
pris isolément. Ce qui n'avait jamais été écrit, c'est la propriété qui en fait
un **système** : une couche est une durée de vie. La mémoire de session meurt
avec la session ; celle d'une personne lui survit ; celle d'un projet appartient
au projet ; la connaissance n'appartient à personne en particulier.

Se tromper là-dessus ne produit pas d'erreur. Cela produit une plateforme qui
retient ce qu'on ne lui a jamais demandé de garder — et la personne qui l'a dit
une fois se le voit citer des mois plus tard, depuis une couche qu'elle n'a
jamais choisie.

Ce que ces tests gardent :

1. **`null` veut dire « ne périme pas »** — écrit, donc décidé, jamais oublié.
2. **Promouvoir est explicite** : qui décide, et pourquoi.
3. **Rétrograder est gratuit** : raccourcir n'enlève de droit à personne.
4. **Une couche se décide par le type, jamais par le contenu.**
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.memory_engine.layers import (  # noqa: E402
    COUCHES,
    DURABILITE,
    LayerRefused,
    expires_at,
    is_promotion,
    layer_of,
    layers_report,
    move,
    survives_session,
)
from src.memory_engine.types import MemoryType  # noqa: E402


# ----------------------------------------------------------------------
# 1. Une couche est une durée de vie
# ----------------------------------------------------------------------

def test_chaque_type_de_memoire_declare_sa_couche():
    """
    Un type sans couche garderait tout pour toujours par accident : la
    déclaration est exhaustive, et un test le garde.
    """
    assert set(COUCHES) == set(MemoryType)


def test_une_memoire_de_session_expire():
    """Elle n'a de sens que dans la conversation en cours."""
    assert expires_at(MemoryType.SESSION, 0) == 43200.0
    assert survives_session(MemoryType.SESSION) is False


def test_ne_pas_perimer_est_une_decision_ecrite():
    """`null` n'est pas un oubli : c'est une valeur qui figure dans la table."""
    connaissance = layer_of(MemoryType.KNOWLEDGE)

    assert connaissance["lifetime_seconds"] is None
    assert expires_at(MemoryType.KNOWLEDGE, 0) is None


def test_un_type_inconnu_est_refuse_avec_la_liste_des_types():
    """Aucun défaut : deviner une couche reviendrait à deviner une durée."""
    with pytest.raises(LayerRefused, match="inconnu"):
        layer_of("permanent_absolu")


def test_la_memoire_d_une_personne_survit_a_la_session():
    """C'est ce qui la distingue de la mémoire de session."""
    assert survives_session(MemoryType.LONG_TERM) is True
    assert layer_of(MemoryType.LONG_TERM)["belongs_to"] == "user"


def test_la_memoire_d_un_projet_appartient_au_projet():
    """Pas à la personne qui l'a écrite."""
    assert layer_of(MemoryType.WORKSPACE)["belongs_to"] == "workspace"


# ----------------------------------------------------------------------
# 2. Promouvoir se décide, rétrograder est gratuit
# ----------------------------------------------------------------------

def test_promouvoir_sans_auteur_est_refuse():
    """
    Garder quelque chose plus longtemps que prévu est une décision, et une
    décision a quelqu'un derrière.
    """
    with pytest.raises(LayerRefused, match="sans auteur"):
        move(MemoryType.SESSION, MemoryType.LONG_TERM, "", "une raison")


def test_promouvoir_sans_raison_est_refuse():
    """
    Sans raison, une base se remplit de choses que personne n'a voulu garder,
    chacune individuellement plausible.
    """
    with pytest.raises(LayerRefused, match="dit pourquoi"):
        move(MemoryType.SESSION, MemoryType.LONG_TERM, "awa", "   ")


def test_une_promotion_tracee_est_acceptee():
    """La décision existe, elle est nommée, elle passe."""
    deplacement = move(
        MemoryType.SESSION, MemoryType.LONG_TERM, "awa",
        "la personne a demandé que ce soit retenu",
    )

    assert deplacement["promotion"] is True
    assert deplacement["decided_by"] == "awa"
    assert "plus longtemps" in deplacement["note"]


def test_retrograder_ne_demande_rien():
    """Raccourcir une durée de vie n'enlève de droit à personne."""
    deplacement = move(MemoryType.LONG_TERM, MemoryType.SESSION)

    assert deplacement["promotion"] is False
    assert deplacement["decided_by"] is None
    assert "Rien à justifier" in deplacement["note"]


def test_l_ordre_de_durabilite_couvre_toutes_les_couches():
    """Un type absent de l'ordre rendrait indécidable le sens d'un déplacement."""
    assert set(DURABILITE) == set(MemoryType)
    assert len(DURABILITE) == len(set(DURABILITE))


def test_le_sens_d_un_deplacement_suit_la_durabilite():
    """Et pas l'ordre alphabétique, ni l'ordre de déclaration."""
    assert is_promotion(MemoryType.SESSION, MemoryType.KNOWLEDGE) is True
    assert is_promotion(MemoryType.KNOWLEDGE, MemoryType.SESSION) is False
    assert is_promotion(MemoryType.SHORT_TERM, MemoryType.WORKSPACE) is True


# ----------------------------------------------------------------------
# 3. Rien n'est déduit du contenu
# ----------------------------------------------------------------------

def test_le_rapport_dit_qu_aucun_contenu_n_est_lu():
    """
    Une inférence poserait une étiquette permanente sur ce qu'une personne a
    mentionné une fois.
    """
    rapport = layers_report()

    regles = " ".join(rapport["rules"])
    assert "jamais** par le contenu" in regles or "jamais par le contenu" in regles
    assert any("Lire le contenu" in ligne for ligne in rapport["does_not"])


def test_le_module_ne_promeut_rien_tout_seul():
    """Une promotion automatique est exactement ce qu'il empêche."""
    ne_fait_pas = " ".join(layers_report()["does_not"])

    assert "Promouvoir quoi que ce soit tout seul" in ne_fait_pas


def test_le_module_ne_supprime_pas():
    """Il décide des durées ; purger est un autre geste, avec d'autres risques."""
    assert any("il ne purge pas" in ligne for ligne in layers_report()["does_not"])


def test_le_rapport_liste_les_couches_dans_l_ordre_de_durabilite():
    """Un lecteur doit voir d'un coup ce qui dure le moins et ce qui dure le plus."""
    rapport = layers_report()

    assert [couche["memory_type"] for couche in rapport["layers"]] == [
        type_memoire.value for type_memoire in DURABILITE
    ]
    assert rapport["layers"][0]["memory_type"] == "session"
    assert rapport["layers"][-1]["memory_type"] == "knowledge"


# ----------------------------------------------------------------------
# 4. La couche s'applique réellement au magasin (phase 60.2)
# ----------------------------------------------------------------------

def _manager():
    """Un gestionnaire de mémoire en mémoire."""
    from src.memory_engine.memory_manager import MemoryManager

    return MemoryManager()


def _item(type_memoire, **extra):
    """Une mémoire d'un type donné."""
    from src.memory_engine.types import MemoryItem

    return MemoryItem(content="une note", memory_type=type_memoire, **extra)


def test_une_memoire_de_session_recoit_enfin_une_expiration():
    """
    **Le défaut refermé en 60.2.** `expires_at` existait, la lecture le
    respectait, le ménage le purgeait — et *rien ne le remplissait jamais*. Une
    mémoire de session écrite aujourd'hui était gardée pour toujours, et la
    durée de vie de sa couche ne changeait strictement rien.
    """
    memoire = _item(MemoryType.SESSION)

    _manager().save_memory(memoire)

    assert memoire.expires_at is not None
    assert round(memoire.expires_at - memoire.created_at) == 43200


def test_une_couche_qui_ne_perime_pas_ne_pose_aucune_expiration():
    """La connaissance n'a pas de date de péremption, et cela reste vrai."""
    memoire = _item(MemoryType.KNOWLEDGE)

    _manager().save_memory(memoire)

    assert memoire.expires_at is None


def test_une_expiration_plus_courte_est_respectee():
    """
    Raccourcir est gratuit : celui qui écrit sait parfois que sa note ne vaut
    qu'une heure.
    """
    import time

    memoire = _item(MemoryType.SESSION, expires_at=time.time() + 60)
    gestionnaire = _manager()

    gestionnaire.save_memory(memoire)

    assert round(memoire.expires_at - memoire.created_at) == 60
    assert gestionnaire.capped_expirations == 0


def test_une_expiration_plus_longue_est_ramenee_a_la_couche():
    """
    La rallonger ferait survivre la mémoire au-delà de ce que sa couche
    promet : c'est une promotion, et une promotion se décide avec un auteur et
    une raison — pas en passant un nombre plus grand.
    """
    import time

    memoire = _item(MemoryType.SESSION, expires_at=time.time() + 10_000_000)
    gestionnaire = _manager()

    gestionnaire.save_memory(memoire)

    assert round(memoire.expires_at - memoire.created_at) == 43200
    assert gestionnaire.capped_expirations == 1


def test_un_plafonnement_est_compte_jamais_tu():
    """Une demande silencieusement rognée ressemblerait à une demande honorée."""
    import time

    gestionnaire = _manager()
    for _ in range(3):
        gestionnaire.save_memory(
            _item(MemoryType.SHORT_TERM, expires_at=time.time() + 10_000_000)
        )

    assert gestionnaire.capped_expirations == 3


def test_l_expiration_effective_dit_pourquoi_elle_differe():
    """Un plafonnement sans raison se lirait comme un bogue."""
    from src.memory_engine.layers import effective_expiry

    retenue = effective_expiry(MemoryType.SESSION, 0.0, declared=10_000_000.0)

    assert retenue["capped"] is True
    assert retenue["requested"] == 10_000_000.0
    assert "promotion" in retenue["reason"]


def test_une_couche_sans_expiration_accepte_n_importe_quelle_demande():
    """Il n'y a pas de plafond à appliquer, donc rien à ramener."""
    from src.memory_engine.layers import effective_expiry

    retenue = effective_expiry(MemoryType.KNOWLEDGE, 0.0, declared=10_000_000.0)

    assert retenue["capped"] is False
    assert retenue["expires_at"] == 10_000_000.0


# ----------------------------------------------------------------------
# 5. La route (phase 60.3)
# ----------------------------------------------------------------------

def test_la_route_publie_les_couches_et_les_plafonnements(monkeypatch):
    """Un opérateur doit voir ce que la plateforme garde, et combien de temps."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests

    ancien = dict(server_module.rbac_manager._key_role_map)
    monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:admin:awa")
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())

    with TestClient(server_module.app) as client:
        rapport = client.get(
            "/memory/layers", headers={"X-API-Key": "cle-awa"},
        ).json()

    server_module.rbac_manager._key_role_map = ancien
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())

    assert rapport["layers"][0]["memory_type"] == "session"
    assert rapport["layers"][0]["lifetime_seconds"] == 43200
    assert "capped_expirations" in rapport
