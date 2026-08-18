"""
Tests de la validation de configuration au démarrage (VOLET 03, chapitre 05).

Le chapitre exige de valider les variables d'environnement au démarrage. Deux
choses comptent : signaler une variable présente et inexploitable, et ne jamais
reprocher une absence — la plupart des variables sont optionnelles et leur
absence désactive proprement une capacité.
"""

import logging
import re
from pathlib import Path

import pytest

from src.config.environment import (
    CONTROLES, ProblemeConfiguration, log_environment_problems, validate_environment,
)

RACINE = Path(__file__).resolve().parent.parent


def test_environnement_vide_ne_pose_aucun_probleme():
    """Aucune variable définie : rien à signaler, la plateforme démarre normalement."""
    assert validate_environment({}) == []


def test_variable_vide_n_est_pas_un_probleme():
    """Une variable déclarée mais vide vaut « non configurée »."""
    assert validate_environment({"GALSEN_STORAGE_BACKEND": "   "}) == []


def test_backend_mal_orthographie_est_signale():
    """Le cas qui a motivé ce contrôle : « sqllite » repartait en mémoire en silence."""
    problemes = validate_environment({"GALSEN_STORAGE_BACKEND": "sqllite"})
    assert len(problemes) == 1
    assert problemes[0].variable == "GALSEN_STORAGE_BACKEND"
    assert "sqlite" in problemes[0].raison
    # La conséquence dit ce que l'opérateur perd, pas seulement la règle violée.
    assert "persist" in problemes[0].consequence


def test_valeurs_valides_acceptees():
    """Les valeurs légitimes passent, casse et espaces compris."""
    assert validate_environment({
        "GALSEN_STORAGE_BACKEND": " SQLite ",
        "GALSEN_RATE_LIMIT_ENABLED": "TRUE",
        "GALSEN_RATE_LIMIT_AUTHENTICATED_RPM": "120",
        "GALSEN_RATE_LIMIT_BURST_MULTIPLIER": "1.5",
        "GALSEN_SMTP_SECURITY": "starttls",
        "GALSEN_KNOWLEDGE_REVALIDATION_DAYS": "90",
    }) == []


@pytest.mark.parametrize("variable, valeur", [
    ("GALSEN_RATE_LIMIT_AUTHENTICATED_RPM", "beaucoup"),
    ("GALSEN_RATE_LIMIT_AUTHENTICATED_RPM", "0"),
    ("GALSEN_RATE_LIMIT_AUTHENTICATED_RPM", "-5"),
    ("GALSEN_LOG_MAX_BYTES", "5Mo"),
    ("GALSEN_KNOWLEDGE_REVALIDATION_DAYS", "0"),
    ("GALSEN_SMTP_PORT", "port"),
    ("GALSEN_SMTP_SECURITY", "tls-maison"),
    ("GALSEN_RATE_LIMIT_ENABLED", "peut-être"),
    ("GALSEN_RATE_LIMIT_BURST_MULTIPLIER", "-1"),
])
def test_valeurs_inexploitables_signalees(variable, valeur):
    """Chaque contrôle refuse ce qu'il ne sait pas appliquer."""
    problemes = validate_environment({variable: valeur})
    assert [p.variable for p in problemes] == [variable]
    assert problemes[0].raison and problemes[0].consequence


def test_un_secret_n_est_jamais_recopie():
    """La valeur d'un secret ne doit pas atterrir dans un journal."""
    probleme = ProblemeConfiguration(
        variable="GALSEN_ENCRYPTION_KEY", valeur="clef-en-clair",
        raison="peu importe", consequence="peu importe",
    )
    assert probleme.to_dict()["value"] == "***"


def test_les_problemes_sont_journalises(caplog):
    """Le démarrage journalise chaque problème, avec sa conséquence."""
    with caplog.at_level(logging.WARNING):
        import os
        ancien = os.environ.get("GALSEN_STORAGE_BACKEND")
        os.environ["GALSEN_STORAGE_BACKEND"] = "sqllite"
        try:
            problemes = log_environment_problems(logging.getLogger("test.config"))
        finally:
            if ancien is None:
                del os.environ["GALSEN_STORAGE_BACKEND"]
            else:
                os.environ["GALSEN_STORAGE_BACKEND"] = ancien

    assert len(problemes) == 1
    assert "GALSEN_STORAGE_BACKEND" in caplog.text


def test_toute_variable_lue_par_le_code_est_documentee():
    """`.env.example` doit décrire ce que le code lit, sinon la variable est invisible.

    Huit variables manquaient, dont trois ajoutées le jour même par les VOLETs 05
    et 14 : documenter après coup est exactement ce qui ne se fait jamais.
    """
    utilisees = set()
    for chemin in (RACINE / "src").rglob("*.py"):
        utilisees |= set(re.findall(r"GALSEN_[A-Z_]+", chemin.read_text(encoding="utf-8")))

    documentees = set(re.findall(
        r"^(GALSEN_[A-Z_]+)=", (RACINE / ".env.example").read_text(encoding="utf-8"), re.M))

    manquantes = sorted(utilisees - documentees)
    assert manquantes == [], "Variables lues par src/ et absentes de .env.example : " + ", ".join(manquantes)


def test_toute_variable_controlee_existe_dans_le_code():
    """Un contrôle sur une variable que personne ne lit protège du vide."""
    lues = set()
    for chemin in (RACINE / "src").rglob("*.py"):
        lues |= set(re.findall(r"GALSEN_[A-Z_]+", chemin.read_text(encoding="utf-8")))
    orphelins = sorted(set(CONTROLES) - lues)
    assert orphelins == [], "Contrôles portant sur des variables inutilisées : " + ", ".join(orphelins)
