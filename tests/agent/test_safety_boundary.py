"""
Ce qu'une réparation automatique n'a jamais le droit de toucher (phase 4).

Un moteur d'auto-réparation est un programme qui modifie des programmes. La
seule raison pour laquelle il est sûr de le laisser tourner est que certains
fichiers sont hors de sa portée — et cette garantie ne vaut que ce que vaut la
liste.

Ce que ces tests gardent :

1. **Le harnais n'est modifiable par aucune classification.** Un moteur qui peut
   affaiblir ce qui le retient n'est retenu par rien.
2. **La frontière de sécurité n'est ouverte qu'à une maintenance déclarée.**
   Modifier la règle n'est pas réparer le code.
3. **La liste est confrontée au dépôt**, et ce qui manque est nommé : une
   politique qui protège des noms disparus ne protège rien.
4. **Un fichier caché reste un secret.** `lstrip("./")` transformait `.env` en
   `env` ; le défaut a été trouvé en confrontant la politique au dépôt réel.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

from src.agent.policies import (  # noqa: E402
    HARNAIS,
    MAINTENANCE_SECURITE,
    REPARATION_ORDINAIRE,
    check_patch_scope,
    classify,
    may_modify,
    protected_paths,
)


# ----------------------------------------------------------------------
# 1. Le harnais est hors de portée, toujours
# ----------------------------------------------------------------------

@pytest.mark.parametrize("chemin", [
    "src/agent/policies/immutability.py",
    "src/agent/policies/integrity.py",
    "src/agent/tools/workspace.py",
    "src/agent/tools/commands.py",
    "src/agent/audit/journal.py",
    "src/agent/self_healer.py",
    "src/agent/guarded_editor.py",
])
def test_le_harnais_n_est_modifiable_par_aucune_classification(chemin):
    """C'est la règle 18 de la directive, et elle n'a pas d'exception."""
    for classe in (REPARATION_ORDINAIRE, MAINTENANCE_SECURITE):
        autorise, motif = may_modify(chemin, classe)

        assert autorise is False, f"{chemin} modifiable en {classe}"
        assert "retient" in motif


def test_la_politique_se_protege_elle_meme():
    """Le fichier qui décide ne doit pas pouvoir se réécrire."""
    assert classify("src/agent/policies/immutability.py")["family"] == "harness"


# ----------------------------------------------------------------------
# 2. La frontière : fermée par défaut, ouverte sur déclaration
# ----------------------------------------------------------------------

@pytest.mark.parametrize("chemin", [
    "src/security/trust.py",
    "src/security/isolation.py",
    "src/api/rbac.py",
    "src/approval_engine/approval_manager.py",
    "src/sandbox/runner.py",
    "src/tool/capabilities.py",
])
def test_une_reparation_ordinaire_ne_touche_pas_la_frontiere(chemin):
    """Modifier la règle n'est pas réparer le code."""
    autorise, motif = may_modify(chemin)

    assert autorise is False
    assert "frontière de sécurité" in motif
    assert MAINTENANCE_SECURITE in motif


def test_une_maintenance_de_securite_declaree_le_peut():
    """Quelqu'un doit pouvoir corriger un défaut de sécurité."""
    autorise, _ = may_modify("src/security/trust.py", MAINTENANCE_SECURITE)

    assert autorise is True


def test_un_fichier_ordinaire_reste_reparable():
    """Fermer tout ne serait pas une politique, mais un arrêt."""
    autorise, motif = may_modify("src/services/senegal/master_rag.py")

    assert autorise is True
    assert motif == ""


# ----------------------------------------------------------------------
# 3. Les secrets, y compris cachés
# ----------------------------------------------------------------------

@pytest.mark.parametrize("chemin", [".env", ".git/config", "config/secrets.yaml",
                                    "deploy/prod.key", "certs/serveur.pem"])
def test_un_secret_reste_hors_de_portee(chemin):
    """Aucune classification n'y donne accès."""
    assert may_modify(chemin, MAINTENANCE_SECURITE)[0] is False


def test_un_fichier_cache_n_est_pas_transforme_en_fichier_ordinaire():
    """
    Défaut réel : `lstrip("./")` retirait les caractères un à un et faisait
    de `.env` un `env` que plus rien ne reconnaissait.
    """
    assert classify(".env")["family"] == "secret"


# ----------------------------------------------------------------------
# 4. La portée d'un correctif, jugée en bloc
# ----------------------------------------------------------------------

def test_un_correctif_melangeant_ordinaire_et_frontiere_est_refuse():
    """Un seul fichier interdit suffit à refuser l'ensemble."""
    verdict = check_patch_scope(
        ["src/services/senegal/master_rag.py", "src/api/rbac.py"]
    )

    assert verdict["allowed"] is False
    assert verdict["refused"][0]["path"] == "src/api/rbac.py"


def test_le_verdict_nomme_chaque_refus_et_ne_s_arrete_pas_au_premier():
    """Un rapport complet vaut mieux qu'un arrêt au premier fichier."""
    verdict = check_patch_scope(["src/api/rbac.py", "src/agent/tools/workspace.py"])

    assert len(verdict["refused"]) == 2


def test_un_correctif_entierement_ordinaire_passe():
    """Le cas nominal existe aussi."""
    assert check_patch_scope(["src/services/senegal/master_rag.py"])["allowed"] is True


def test_les_regles_sont_ecrites_dans_le_verdict():
    """Un refus qu'on ne comprend pas est un refus qu'on contourne."""
    regles = " ".join(check_patch_scope(["x.py"])["rules"])

    assert "affaiblir ce qui le retient" in regles
    assert "moins chère" in regles


# ----------------------------------------------------------------------
# 5. La liste est confrontée au dépôt
# ----------------------------------------------------------------------

def test_les_chemins_proteges_existent_ou_sont_nommes_manquants():
    """Une politique qui protège des noms disparus ne protège rien."""
    rapport = protected_paths()

    # `missing` peut être non vide pendant la construction du harnais ; ce qui
    # compte est qu'il soit **rendu**, jamais tu.
    assert "missing" in rapport
    for famille in ("frontier", "harness", "protected_tests"):
        assert rapport["families"][famille]["present"], famille


def test_la_frontiere_reelle_du_depot_est_couverte():
    """Les modules de sécurité mesurés existent bien dans la liste."""
    rapport = protected_paths()
    presents = rapport["families"]["frontier"]["present"]

    assert "src/security/" in presents
    assert "src/api/rbac.py" in presents
    assert "src/sandbox/" in presents


def test_le_harnais_declare_couvre_ses_propres_repertoires():
    """Un répertoire du harnais oublié serait modifiable sans que rien ne le dise."""
    assert "src/agent/tools/" in HARNAIS
    assert "src/agent/policies/" in HARNAIS
    assert "src/agent/audit/" in HARNAIS
