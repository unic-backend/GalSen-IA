"""
Le masquage des secrets, et la garde qui l'impose aux connecteurs (phase 42.2).

Un jeton qui atteint un fichier de journal a quitté la plateforme. Un journal se
copie, part chez un agrégateur, se colle dans un rapport de bogue, et se lit par
des gens à qui personne n'a accordé l'accès que ce jeton porte. Contrairement à
une ligne de base de données, **personne ne revient effacer une ligne du journal
du mois dernier**.

Ce que ces tests gardent :

1. **Une seule liste de noms sensibles**, partagée. La deuxième copie est
   l'endroit où deux listes commencent à diverger.
2. **Le masquage est récursif** : un jeton rangé sous `credentials.access_token`
   est aussi dangereux qu'à la racine, et c'est là qu'il se trouve en pratique.
3. **Aucun module de connecteur ne journalise une variable sensible** — vérifié
   sur l'arbre syntaxique, pas sur le texte.
4. **Le masquage se voit.** Un champ qui disparaît en silence est indiscernable
   d'un champ jamais renseigné.
"""

import ast
import os
import pathlib
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.security.redaction import (  # noqa: E402
    MASQUE,
    NOMS_CERTAINEMENT_SECRETS,
    NOMS_SENSIBLES,
    is_certainly_secret,
    is_sensitive,
    redact_mapping,
    redact_pairs,
    redaction_report,
)

RACINE = pathlib.Path(__file__).resolve().parent.parent
JETON = "ya29.a0AfB_SECRET"


# ----------------------------------------------------------------------
# 1. La liste
# ----------------------------------------------------------------------

@pytest.mark.parametrize("nom", [
    "password", "access_token", "refresh_token", "client_secret",
    "api_key", "Authorization", "COOKIE", "private_key", "mot_de_passe",
])
def test_les_noms_qui_trahissent_un_secret_sont_reconnus(nom):
    """La liste est large à dessein : les deux erreurs ne coûtent pas pareil."""
    assert is_sensitive(nom) is True


@pytest.mark.parametrize("nom", ["subject", "connector_id", "latency_ms", "title"])
def test_les_noms_anodins_ne_sont_pas_masques(nom):
    """Masquer tout reviendrait à ne rien publier."""
    assert is_sensitive(nom) is False


def test_la_liste_est_partagee_et_non_recopiee():
    """
    Elle vivait dans `AgentContext`, privée à une classe. La deuxième copie est
    l'endroit où deux listes commencent à diverger.
    """
    from src.agent.context import AgentContext

    assert set(AgentContext._SENSITIVE_ARG_NAMES) == set(NOMS_SENSIBLES)


@pytest.mark.parametrize("nom", ["key", "object_key", "session_id"])
def test_la_garde_est_plus_etroite_que_le_masquage(nom):
    """
    Le connecteur de stockage journalise sa `key`, qui est un chemin d'objet.
    Elle reste masquée à l'écriture ; elle n'est plus une faute à la lecture.
    Une garde qui crie à tort finit par être désactivée.
    """
    assert is_sensitive(nom) is True
    assert is_certainly_secret(nom) is False


def test_la_liste_de_la_garde_est_incluse_dans_celle_du_masquage():
    """
    Deux questions, pas deux vérités : tout ce que la garde accuse doit être
    masqué, l'inverse n'a pas à être vrai.
    """
    non_masques = [
        nom for nom in NOMS_CERTAINEMENT_SECRETS if not is_sensitive(nom)
    ]

    assert non_masques == []


def test_le_rapport_dit_ce_que_la_couche_ne_fait_pas():
    """
    Elle ne reconnaît pas un secret dans une chaîne, et le dit : un détecteur
    qui marche à peu près est pire qu'aucun, parce qu'on lui fait confiance.
    """
    rapport = redaction_report()

    assert rapport["marker"] == MASQUE
    assert "pire qu'aucun" in rapport["limitation"]
    assert len(rapport["names"]) == len(NOMS_SENSIBLES)


# ----------------------------------------------------------------------
# 2. Le masquage
# ----------------------------------------------------------------------

def test_un_bloc_entier_de_secrets_est_masque_d_un_bloc():
    """
    `credentials` est lui-même un nom sensible : tout le bloc part, sans être
    parcouru. C'est plus sûr que de masquer champ par champ, où un champ
    inconnu du jour passerait.
    """
    masque = redact_mapping({
        "connector_id": "gmail",
        "credentials": {"access_token": JETON, "expires_in": 3600},
    })

    assert masque["credentials"] == MASQUE
    assert masque["connector_id"] == "gmail"
    assert JETON not in str(masque)


def test_un_jeton_imbrique_sous_un_nom_anodin_est_masque():
    """C'est là qu'il se trouve en pratique, pas à la racine."""
    masque = redact_mapping({
        "session": {"access_token": JETON, "expires_in": 3600},
    })

    assert masque["session"]["access_token"] == MASQUE
    assert masque["session"]["expires_in"] == 3600
    assert JETON not in str(masque)


def test_un_jeton_dans_une_liste_de_blocs_est_masque():
    """Les jetons voyagent souvent par lots — un compte, plusieurs sessions."""
    masque = redact_mapping({
        "sessions": [{"subject": "fatou", "token": JETON}],
    })

    assert masque["sessions"][0]["token"] == MASQUE
    assert masque["sessions"][0]["subject"] == "fatou"


def test_le_masquage_se_voit():
    """Un champ disparu en silence est indiscernable d'un champ jamais renseigné."""
    masque = redact_mapping({"api_key": JETON})

    assert "api_key" in masque
    assert masque["api_key"] == MASQUE


def test_l_original_n_est_pas_modifie():
    """Masquer pour journaliser ne doit pas casser l'appelant."""
    origine = {"token": JETON}

    redact_mapping(origine)

    assert origine["token"] == JETON


def test_une_structure_trop_profonde_n_est_pas_publiee_en_confiance():
    """Trop profonde pour être parcourue, trop profonde pour être publiée."""
    profond = {"a": {"b": {"c": {"d": {"token": JETON}}}}}

    masque = redact_mapping(profond, depth=2)

    assert JETON not in str(masque)


def test_les_couples_de_journal_sont_masques():
    """La forme utilisée dans un message de journal."""
    rendu = redact_pairs([("subject", "fatou"), ("access_token", JETON)])

    assert "subject=fatou" in rendu
    assert f"access_token={MASQUE}" in rendu
    assert JETON not in rendu


def test_une_valeur_longue_est_tronquee():
    """Un journal reste lisible ; une valeur de dix mille caractères, non."""
    rendu = redact_pairs([("body", "x" * 5000)], limit=100)

    assert len(rendu) < 200
    assert "..." in rendu


# ----------------------------------------------------------------------
# 3. La garde sur les connecteurs
# ----------------------------------------------------------------------

def _appels_de_journal(arbre):
    """Retourne les appels `logger.<niveau>(...)` d'un arbre syntaxique."""
    niveaux = {"debug", "info", "warning", "error", "exception", "critical"}
    for noeud in ast.walk(arbre):
        if (isinstance(noeud, ast.Call)
                and isinstance(noeud.func, ast.Attribute)
                and noeud.func.attr in niveaux):
            yield noeud


def _noms_cites(noeud):
    """Retourne les noms d'attributs et de variables cités dans un appel."""
    for sous in ast.walk(noeud):
        if isinstance(sous, ast.Attribute):
            yield sous.attr
        elif isinstance(sous, ast.Name):
            yield sous.id
        elif isinstance(sous, ast.Constant) and isinstance(sous.value, str):
            # Une chaîne de format peut nommer le champ qu'elle va rendre.
            yield sous.value


def test_aucun_module_de_connecteur_ne_journalise_un_secret():
    """
    Vérifié sur l'arbre syntaxique, pas sur le texte : un commentaire qui parle
    de jetons ne doit pas faire échouer la garde, et une variable nommée
    `access_token` passée à un journal doit la faire échouer.
    """
    fautes = []
    for chemin in sorted((RACINE / "src" / "connectors").glob("*.py")):
        arbre = ast.parse(chemin.read_text(encoding="utf-8"))
        for appel in _appels_de_journal(arbre):
            for nom in _noms_cites(appel):
                if is_certainly_secret(str(nom)):
                    fautes.append(f"{chemin.name}:{appel.lineno} → {nom}")

    assert fautes == [], f"Secrets journalisés : {fautes}"


def test_la_garde_attrape_une_vraie_faute(tmp_path):
    """
    Une garde qu'on n'a jamais vue échouer ne prouve rien. Celle-ci est
    confrontée à un module qui journalise vraiment un jeton.
    """
    fautif = tmp_path / "fautif.py"
    fautif.write_text(
        "import logging\n"
        "logger = logging.getLogger(__name__)\n"
        "def f(access_token):\n"
        "    logger.info('jeton reçu : %s', access_token)\n",
        encoding="utf-8",
    )

    arbre = ast.parse(fautif.read_text(encoding="utf-8"))
    fautes = [
        nom for appel in _appels_de_journal(arbre)
        for nom in _noms_cites(appel) if is_certainly_secret(str(nom))
    ]

    assert fautes, "La garde ne détecte pas un jeton journalisé"
