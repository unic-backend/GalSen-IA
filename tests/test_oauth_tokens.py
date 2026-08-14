"""
Le magasin de jetons OAuth : chiffré, ou refusé (phase 43.2).

La plateforme avait déjà un chiffrement au repos, et ce module s'en sert au lieu
d'en faire pousser un second. Ce qu'il ajoute est une **politique**, et c'est
toute la différence : là-bas le chiffrement est facultatif — une ligne d'audit
en clair est regrettable, pas dangereuse — ici il est obligatoire. Un jeton OAuth
en clair lit le courrier de quelqu'un pour qui trouve le fichier.

Ce que ces tests gardent :

1. **Sans clé, rien n'est écrit.** Pas de repli en clair, pas d'écriture
   « en attendant ».
2. **Ce qui est conservé est illisible**, vérifié sur l'octet stocké et non sur
   la confiance faite au module.
3. **Aucun jeton dans un `repr`, un dictionnaire ou un rapport.** Une exception
   non rattrapée mettrait sinon un jeton de rafraîchissement dans une trace.
4. **L'effacement ne demande pas la clé.** Détruire un chiffré n'a jamais exigé
   de le lire, et un magasin incapable d'oublier quelqu'un serait la pire panne.
"""

import os
import sys
import time

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.connectors.lifecycle import AuthorizationState  # noqa: E402
from src.connectors.oauth.tokens import (  # noqa: E402
    MARGE_D_EXPIRATION_SECONDES,
    StoredToken,
    TokenStorageUnavailable,
    TokenStore,
    require_encryption,
)
from src.storage import encryption  # noqa: E402

ACCES = "ya29.a0AfB-JETON-D-ACCES-SECRET"
RAFRAICHISSEMENT = "1//04-JETON-DE-RAFRAICHISSEMENT-SECRET"


@pytest.fixture
def chiffrement(monkeypatch):
    """Une clé de chiffrement valable, propre à ce test."""
    monkeypatch.setenv(encryption.KEY_VARIABLE, Fernet.generate_key().decode("ascii"))
    return encryption.KEY_VARIABLE


@pytest.fixture
def sans_clef(monkeypatch):
    """Aucune clé : l'état par défaut de cet environnement."""
    monkeypatch.delenv(encryption.KEY_VARIABLE, raising=False)


def _jeton(expires_at=None, sujet="fatou"):
    """Des jetons de test pour une personne."""
    return StoredToken(
        provider_id="google",
        subject=sujet,
        access_token=ACCES,
        refresh_token=RAFRAICHISSEMENT,
        expires_at=expires_at,
        scopes=["https://www.googleapis.com/auth/gmail.readonly"],
    )


# ----------------------------------------------------------------------
# 1. Sans clé, rien
# ----------------------------------------------------------------------

def test_sans_cle_l_ecriture_est_refusee(sans_clef):
    """Pas de repli en clair. C'est la seule règle qui compte ici."""
    magasin = TokenStore()

    with pytest.raises(TokenStorageUnavailable, match=encryption.KEY_VARIABLE):
        magasin.save(_jeton())


def test_le_refus_n_ecrit_rien_du_tout(sans_clef):
    """Refuser après avoir écrit ne serait pas refuser."""
    magasin = TokenStore()

    with pytest.raises(TokenStorageUnavailable):
        magasin.save(_jeton())

    assert magasin.subjects("google") == []
    assert magasin.raw_entry("google", "fatou") is None


def test_le_message_de_refus_ne_contient_aucune_cle(monkeypatch):
    """Une clé invalide ne doit pas être recopiée dans le message qui la refuse."""
    monkeypatch.setenv(encryption.KEY_VARIABLE, "cle-invalide-mais-secrete")

    with pytest.raises(TokenStorageUnavailable) as refus:
        require_encryption()

    assert "cle-invalide-mais-secrete" not in str(refus.value)
    assert encryption.KEY_VARIABLE in str(refus.value)


def test_une_lecture_sans_cle_ne_ment_pas(chiffrement, monkeypatch):
    """
    Rendre `None` ferait croire que la personne n'a jamais accordé l'accès,
    alors que le chiffré est là et que c'est la clé qui manque.
    """
    magasin = TokenStore()
    magasin.save(_jeton())

    monkeypatch.delenv(encryption.KEY_VARIABLE, raising=False)

    with pytest.raises(TokenStorageUnavailable):
        magasin.get("google", "fatou")


# ----------------------------------------------------------------------
# 2. Ce qui est réellement conservé
# ----------------------------------------------------------------------

def test_aucun_jeton_en_clair_n_est_conserve(chiffrement):
    """Vérifié sur l'octet stocké, pas sur la parole du module."""
    magasin = TokenStore()
    magasin.save(_jeton())

    brut = magasin.raw_entry("google", "fatou")

    assert ACCES not in brut
    assert RAFRAICHISSEMENT not in brut
    assert brut.startswith(encryption.ENCRYPTED_PREFIX)


def test_le_jeton_relu_est_identique(chiffrement):
    """Chiffrer sans pouvoir relire serait chiffrer pour rien."""
    magasin = TokenStore()
    magasin.save(_jeton(expires_at=time.time() + 3600))

    relu = magasin.get("google", "fatou")

    assert relu.access_token == ACCES
    assert relu.refresh_token == RAFRAICHISSEMENT
    assert relu.scopes == ["https://www.googleapis.com/auth/gmail.readonly"]


def test_un_jeton_sans_rafraichissement_se_relit(chiffrement):
    """Le champ est facultatif ; le séparateur ne doit pas fabriquer une chaîne vide."""
    magasin = TokenStore()
    magasin.save(StoredToken(
        provider_id="google", subject="moussa", access_token=ACCES,
    ))

    relu = magasin.get("google", "moussa")

    assert relu.refresh_token is None
    assert relu.access_token == ACCES


def test_deux_personnes_ne_partagent_pas_leurs_jetons(chiffrement):
    """L'isolation par sujet, jusque dans le magasin."""
    magasin = TokenStore()
    magasin.save(_jeton(sujet="fatou"))

    assert magasin.get("google", "moussa") is None
    assert magasin.subjects("google") == ["fatou"]


def test_un_jeton_sans_sujet_n_est_pas_conservable(chiffrement):
    """Un jeton appartient à quelqu'un."""
    magasin = TokenStore()

    with pytest.raises(ValueError, match="obligatoire"):
        magasin.save(_jeton(sujet="   "))


def test_un_jeton_d_acces_vide_n_est_pas_conserve(chiffrement):
    """Rien à conserver n'est pas quelque chose à conserver."""
    magasin = TokenStore()

    with pytest.raises(ValueError, match="vide"):
        magasin.save(StoredToken(
            provider_id="google", subject="fatou", access_token="  ",
        ))


# ----------------------------------------------------------------------
# 3. Rien ne fuit par une représentation
# ----------------------------------------------------------------------

def test_le_repr_ne_montre_aucun_jeton():
    """
    Une `dataclass` imprime tous ses champs. Une exception non rattrapée dans
    un gestionnaire de requête mettrait sinon le jeton dans une trace, et les
    traces voyagent.
    """
    rendu = repr(_jeton())

    assert ACCES not in rendu
    assert RAFRAICHISSEMENT not in rendu
    assert "fatou" in rendu


def test_le_dictionnaire_ne_porte_aucun_jeton():
    """Il finit dans une réponse d'API."""
    serialise = _jeton(expires_at=time.time() + 3600).as_dict()

    assert ACCES not in str(serialise)
    assert RAFRAICHISSEMENT not in str(serialise)
    assert serialise["has_refresh_token"] is True


def test_le_rapport_du_magasin_ne_porte_aucun_jeton(chiffrement):
    """Le dernier endroit par lequel un secret pourrait sortir."""
    magasin = TokenStore()
    magasin.save(_jeton())

    rapport = magasin.report()

    assert ACCES not in str(rapport)
    assert rapport["entries"] == 1
    assert rapport["encryption"]["enabled"] is True
    assert "jamais dégradée" in rapport["encryption"]["policy"]


def test_une_exception_de_sauvegarde_ne_recopie_pas_le_jeton(sans_clef):
    """Le message d'un refus est lu par quelqu'un ; il ne doit rien porter."""
    magasin = TokenStore()

    with pytest.raises(TokenStorageUnavailable) as refus:
        magasin.save(_jeton())

    assert ACCES not in str(refus.value)


# ----------------------------------------------------------------------
# 4. L'effacement
# ----------------------------------------------------------------------

def test_l_effacement_ne_demande_pas_la_cle(chiffrement, monkeypatch):
    """
    Le point qui compte. Un magasin incapable de vous oublier parce que sa clé
    est mal configurée serait la pire panne possible.
    """
    magasin = TokenStore()
    magasin.save(_jeton())
    monkeypatch.delenv(encryption.KEY_VARIABLE, raising=False)

    assert magasin.delete("google", "fatou") is True
    assert magasin.raw_entry("google", "fatou") is None


def test_effacer_ce_qui_n_existe_pas_n_est_pas_une_erreur(sans_clef):
    """C'est un `False`, pas une exception."""
    assert TokenStore().delete("google", "personne") is False


# ----------------------------------------------------------------------
# 5. L'expiration
# ----------------------------------------------------------------------

def test_un_jeton_qui_expire_dans_dix_secondes_est_deja_perime():
    """Le temps d'un appel réseau, il le sera."""
    jeton = _jeton(expires_at=time.time() + 10)

    assert jeton.expired() is True
    assert jeton.state() is AuthorizationState.EXPIRED


def test_un_jeton_valable_une_heure_est_utilisable():
    """La symétrie : la marge ne doit pas tout périmer."""
    jeton = _jeton(expires_at=time.time() + 3600)

    assert jeton.expired() is False
    assert jeton.state() is AuthorizationState.AUTHORIZED


def test_un_jeton_sans_date_est_cru_sur_parole():
    """
    Le seul cas où la plateforme fait confiance sans date — c'est ce que le
    fournisseur dit, et l'inventer une expiration serait pire.
    """
    assert _jeton(expires_at=None).expired() is False


def test_l_etat_se_lit_sans_dechiffrer(chiffrement, monkeypatch):
    """
    Une interface doit pouvoir montrer l'état sans jamais toucher au secret.
    Vérifié en retirant la clé après l'écriture.
    """
    magasin = TokenStore()
    magasin.save(_jeton(expires_at=time.time() + 3600))
    monkeypatch.delenv(encryption.KEY_VARIABLE, raising=False)

    assert magasin.state("google", "fatou") is AuthorizationState.AUTHORIZED


def test_une_personne_inconnue_n_a_jamais_accorde_l_acces(chiffrement):
    """`NOT_AUTHORIZED`, et non « périmé » : les deux appellent des suites différentes."""
    assert TokenStore().state("google", "personne") is AuthorizationState.NOT_AUTHORIZED


def test_la_marge_d_expiration_est_appliquee_a_la_seconde(chiffrement):
    """Une marge annoncée et non appliquée serait une fausse sécurité."""
    magasin = TokenStore()
    expiration = time.time() + 3600
    magasin.save(_jeton(expires_at=expiration))

    juste_avant = expiration - MARGE_D_EXPIRATION_SECONDES - 1
    juste_apres = expiration - MARGE_D_EXPIRATION_SECONDES + 1

    assert magasin.state("google", "fatou", now=juste_avant) is AuthorizationState.AUTHORIZED
    assert magasin.state("google", "fatou", now=juste_apres) is AuthorizationState.EXPIRED
