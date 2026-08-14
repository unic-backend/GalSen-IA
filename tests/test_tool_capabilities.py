"""
Les capacités d'outils : ce qu'un outil touche, ce qu'il change, qui peut le lancer.

Ce que ces tests gardent, dans l'ordre d'importance :

1. **« Non déclaré » n'est pas « inoffensif ».** Un outil sans déclaration est
   refusé, avec sa raison — jamais autorisé par omission.
2. **Une déclaration incohérente ne se charge pas.** Exiger un humain et
   affirmer qu'il n'y en a pas est une erreur de configuration, pas un cas
   limite à trancher à l'exécution.
3. **Donnée privée plus sortie de la machine ne tourne jamais seul.** C'est la
   définition d'un chemin d'exfiltration.
4. **Les 22 outils du registre réel sont couverts**, et la couverture est
   mesurée, pas supposée.
"""

import os
import sys

import pytest
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tool.capabilities import (  # noqa: E402
    CapabilityError,
    CapabilityRegistry,
    DataScope,
    Effect,
    capability_report,
    load_capabilities,
    may_reach,
    may_run_unattended,
    parse_capability,
    undeclared,
)


def _ecrire_registre(tmp_path, outils):
    """Écrit un registre d'outils minimal et retourne son chemin."""
    chemin = tmp_path / "tools.yaml"
    chemin.write_text(
        yaml.safe_dump({"version": "1.0", "tools": outils}, allow_unicode=True),
        encoding="utf-8",
    )
    return str(chemin)


# ----------------------------------------------------------------------
# 1. L'absence de déclaration
# ----------------------------------------------------------------------

def test_un_outil_sans_declaration_est_refuse_avec_sa_raison():
    """Le défaut est le refus : c'est la raison d'être de tout ce module."""
    capacite = undeclared("inconnu")

    assert capacite.declared is False
    assert capacite.requires_approval is True
    assert capacite.unattended is False
    assert "n'est pas" in capacite.reason


def test_un_outil_absent_du_registre_recoit_le_meme_refus(tmp_path):
    """Absent et non déclaré demandent la même prudence."""
    registre = load_capabilities(_ecrire_registre(tmp_path, []))

    autorise, raison = may_run_unattended("jamais_vu", registre)

    assert autorise is False
    assert "non déclarée" in raison


def test_un_registre_absent_rend_la_couche_muette_pas_permissive(tmp_path):
    """Perdre le fichier ne doit pas ouvrir les vannes."""
    registre = load_capabilities(str(tmp_path / "absent.yaml"))

    assert registre.capabilities == {}
    assert may_run_unattended("git", registre)[0] is False


def test_un_outil_declare_sans_bloc_capacite_reste_non_declare(tmp_path):
    """Être au registre ne vaut pas déclaration de capacité."""
    chemin = _ecrire_registre(tmp_path, [{"id": "nu", "enabled": True}])

    registre = load_capabilities(chemin)

    assert registre.undeclared_ids() == ["nu"]
    assert registre.declared_ids() == []


# ----------------------------------------------------------------------
# 2. Les incohérences refusées au chargement
# ----------------------------------------------------------------------

def test_approbation_et_absence_d_humain_sont_incompatibles():
    """Sans cette règle, une routine s'auto-approuve."""
    with pytest.raises(CapabilityError, match="incompatibles"):
        parse_capability("contradictoire", {
            "capability": {
                "effects": ["read"],
                "data_scope": "public",
                "requires_approval": True,
                "unattended": True,
            }
        })


def test_donnee_privee_plus_sortie_de_machine_ne_tourne_jamais_seule():
    """La combinaison qui définit un chemin d'exfiltration."""
    with pytest.raises(CapabilityError, match="exfiltration"):
        parse_capability("fuite", {
            "capability": {
                "effects": ["read", "external"],
                "data_scope": "user_private",
                "requires_approval": False,
                "unattended": True,
            }
        })


@pytest.mark.parametrize("bloc,motif", [
    ({"effects": [], "data_scope": "public"}, "liste non vide"),
    ({"effects": ["read"], "data_scope": "confidentiel"}, "portée de données inconnue"),
    ({"effects": ["supprimer"], "data_scope": "public"}, "effet inconnu"),
    ({"effects": "read", "data_scope": "public"}, "liste non vide"),
])
def test_une_declaration_mal_formee_est_refusee(bloc, motif):
    """Un nom inventé ne doit pas être accepté au plus proche."""
    with pytest.raises(CapabilityError, match=motif):
        parse_capability("malforme", {"capability": bloc})


def test_un_bloc_qui_n_est_pas_un_bloc_est_refuse():
    """Une chaîne à la place d'un bloc est une erreur, pas une absence."""
    with pytest.raises(CapabilityError, match="doit être un bloc"):
        parse_capability("liste", {"capability": ["read"]})


def test_une_incoherence_arrete_le_chargement_du_registre_entier(tmp_path):
    """Charger neuf outils sur dix en silence cacherait la faute."""
    chemin = _ecrire_registre(tmp_path, [
        {"id": "sain", "capability": {"effects": ["read"], "data_scope": "public"}},
        {"id": "fautif", "capability": {
            "effects": ["read"], "data_scope": "public",
            "requires_approval": True, "unattended": True,
        }},
    ])

    with pytest.raises(CapabilityError):
        load_capabilities(chemin)


# ----------------------------------------------------------------------
# 3. Les questions posées par les couches suivantes
# ----------------------------------------------------------------------

def test_un_outil_qui_exige_une_approbation_ne_tourne_pas_sans_humain(tmp_path):
    """La question du moteur de routines, et sa réponse par défaut."""
    chemin = _ecrire_registre(tmp_path, [{
        "id": "portillon",
        "capability": {
            "effects": ["write"], "data_scope": "system",
            "requires_approval": True, "unattended": False,
        },
    }])
    registre = load_capabilities(chemin)

    autorise, raison = may_run_unattended("portillon", registre)

    assert autorise is False
    assert "approbation humaine" in raison


def test_un_refus_porte_toujours_sa_raison(tmp_path):
    """Un refus sans motif est indébogable."""
    chemin = _ecrire_registre(tmp_path, [{
        "id": "prudent",
        "capability": {
            "effects": ["read"], "data_scope": "system",
            "requires_approval": False, "unattended": False,
            "reason": "L'écran peut afficher une donnée privée.",
        },
    }])
    registre = load_capabilities(chemin)

    autorise, raison = may_run_unattended("prudent", registre)

    assert autorise is False
    assert raison == "L'écran peut afficher une donnée privée."


def test_une_portee_non_declaree_n_est_pas_accordee_au_plus_proche():
    """Demander une portée que l'outil ne déclare pas est un refus, pas un rabais."""
    registre = load_capabilities()

    autorise, raison = may_reach("web_search", DataScope.USER_PRIVATE, registre)

    assert autorise is False
    assert "'public'" in raison


def test_la_portee_declaree_est_accordee():
    """La symétrie du test précédent."""
    autorise, raison = may_reach("web_search", DataScope.PUBLIC, load_capabilities())

    assert autorise is True
    assert "public" in raison


# ----------------------------------------------------------------------
# 4. Le registre réel
# ----------------------------------------------------------------------

def test_les_vingt_deux_outils_declarent_leur_capacite():
    """
    Mesure, pas promesse. La couverture est publiée : un outil oublié
    apparaîtrait ici plutôt que de passer pour sûr.
    """
    rapport = capability_report()

    assert rapport["tools"] == 22
    assert rapport["undeclared"] == []
    assert rapport["coverage"] == 1.0


@pytest.mark.parametrize("outil", ["email", "calendar"])
def test_les_outils_qui_emportent_de_la_donnee_privee_dehors_sont_sous_portillon(outil):
    """
    La règle que la vague des connecteurs Google va reprendre telle quelle :
    un courriel parti ne revient pas.
    """
    capacite = load_capabilities().get(outil)

    assert capacite.touches(DataScope.USER_PRIVATE)
    assert capacite.has(Effect.EXTERNAL)
    assert capacite.requires_approval is True
    assert capacite.unattended is False


@pytest.mark.parametrize("outil", ["gui", "terminal", "api", "docker"])
def test_les_outils_qui_agissent_largement_exigent_une_approbation(outil):
    """Geste sur l'interface, commande, appel arbitraire, conteneur."""
    capacite = load_capabilities().get(outil)

    assert capacite.requires_approval is True
    assert capacite.unattended is False
    assert capacite.reason, f"{outil} refuse sans dire pourquoi"


def test_aucun_outil_executable_seul_ne_sort_avec_de_la_donnee_privee():
    """
    L'invariant du registre réel, vérifié sur les 22 outils et non sur un
    exemple choisi.
    """
    registre = load_capabilities()

    for tool_id in registre.unattended_ids():
        capacite = registre.get(tool_id)
        assert not (
            capacite.touches(DataScope.USER_PRIVATE)
            and capacite.has(Effect.EXTERNAL)
        ), f"{tool_id} peut exfiltrer sans témoin"


def test_tout_outil_qui_refuse_de_tourner_seul_dit_pourquoi():
    """Une colonne « non » sans raison serait inexploitable par le moteur de routines."""
    registre = load_capabilities()

    muets = []
    for tool_id in sorted(registre.capabilities):
        autorise, raison = may_run_unattended(tool_id, registre)
        if not autorise and not raison.strip():
            muets.append(tool_id)

    assert muets == [], f"Refus sans raison : {muets}"


def test_lire_une_capacite_n_execute_aucun_outil():
    """
    Une capacité se lit dans le registre. Importer le module de l'outil pour
    savoir s'il est dangereux serait l'exécuter pour le demander.
    """
    avant = set(sys.modules)

    load_capabilities()

    nouveaux = {m for m in set(sys.modules) - avant if m.startswith("src.tools.")}
    assert nouveaux == set(), f"Modules d'outils chargés : {nouveaux}"


def test_le_registre_expose_ses_index(tmp_path):
    """Les couches suivantes filtrent par effet et par portée, pas en relisant le YAML."""
    registre: CapabilityRegistry = load_capabilities()

    assert "email" in registre.with_effect(Effect.EXTERNAL)
    assert "email" in registre.with_scope(DataScope.USER_PRIVATE)
    assert "email" not in registre.unattended_ids()
