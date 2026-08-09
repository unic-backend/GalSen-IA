"""
Tests du modèle d'identité (VOLET_16, ADR-010).

Ce que l'ADR décide : **une clé appartient à un sujet**. La déclaration gagne un
troisième champ facultatif, `RBACContext` gagne `subject`, et rien d'autre ne
change — surtout pas la propriété qui rend le dispositif actuel sûr et bon
marché : la plateforme ne conserve aucun secret à elle.

Ces tests protègent trois choses, dans cet ordre d'importance :

1. **La compatibilité.** Une clé déclarée sans sujet doit continuer de
   fonctionner. Un déploiement existant ne doit rien changer.
2. **L'absence de secret.** Le sujet est un identifiant, pas un mot de passe :
   il peut apparaître dans un inventaire d'administration ; la clé, jamais.
3. **L'honnêteté du sujet anonyme.** Une clé que personne n'a attribuée doit le
   dire, et non se voir inventer un nom — c'est l'alternative que l'ADR rejette
   explicitement.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.api.rbac import (  # noqa: E402
    ANONYMOUS_SUBJECT,
    KeyIdentity,
    RBACContext,
    RBACManager,
    Role,
    hash_api_key,
    parse_api_key_mappings,
)


@pytest.fixture
def declaration(monkeypatch):
    """Déclare des clés et rend un gestionnaire construit dessus."""

    def _declarer(valeur: str) -> RBACManager:
        monkeypatch.setenv("GALSEN_API_KEYS", valeur)
        return RBACManager()

    return _declarer


class TestLecture:
    """Le troisième champ est lu, et son absence reste valide."""

    def test_sujet_declare(self, declaration):
        """Le champ après le rôle nomme le porteur de la clé."""
        contexte = declaration("cle-a:admin:awa").authenticate("cle-a")
        assert contexte.subject == "awa"
        assert contexte.role is Role.ADMIN

    def test_sujet_absent_reste_valide(self, declaration):
        """Compatibilité : c'est le format qu'utilisent les déploiements actuels."""
        contexte = declaration("cle-a:admin").authenticate("cle-a")
        assert contexte.subject == ANONYMOUS_SUBJECT
        assert contexte.role is Role.ADMIN

    def test_ni_role_ni_sujet(self, declaration):
        """La forme la plus ancienne — une clé seule — doit encore ouvrir."""
        contexte = declaration("cle-a").authenticate("cle-a")
        assert contexte.role is Role.USER
        assert contexte.subject == ANONYMOUS_SUBJECT

    def test_sujet_vide_vaut_anonyme(self, declaration):
        """`cle:admin:` ne doit pas produire un sujet vide, qui ne nomme rien."""
        assert declaration("cle-a:admin:").authenticate("cle-a").subject == ANONYMOUS_SUBJECT

    def test_espaces_ignores(self, declaration):
        """Une déclaration lisible reste une déclaration valide."""
        assert declaration(" cle-a : admin : awa ").authenticate("cle-a").subject == "awa"

    def test_plusieurs_cles(self, declaration):
        """Chaque clé porte son propre sujet."""
        gestionnaire = declaration("cle-a:admin:awa,cle-b:user:moussa,cle-c:readonly")
        assert gestionnaire.authenticate("cle-a").subject == "awa"
        assert gestionnaire.authenticate("cle-b").subject == "moussa"
        assert gestionnaire.authenticate("cle-c").subject == ANONYMOUS_SUBJECT

    def test_deux_cles_un_meme_sujet(self, declaration):
        """Une personne peut avoir plusieurs clés : c'est le cas de la rotation."""
        gestionnaire = declaration("cle-ancienne:user:awa,cle-neuve:user:awa")
        assert gestionnaire.authenticate("cle-ancienne").subject == "awa"
        assert gestionnaire.authenticate("cle-neuve").subject == "awa"


class TestAucunSecretExpose:
    """Le sujet est un identifiant ; la clé reste hors de portée."""

    def test_le_mapping_ne_contient_aucune_cle_en_clair(self, monkeypatch):
        """La clé disparaît avec la variable locale, seul le condensé subsiste."""
        monkeypatch.setenv("GALSEN_API_KEYS", "cle-secrete:admin:awa")
        mapping = parse_api_key_mappings()
        assert "cle-secrete" not in mapping
        assert hash_api_key("cle-secrete") in mapping

    def test_l_inventaire_nomme_le_sujet_sans_la_cle(self, declaration):
        """Un administrateur doit savoir à qui appartient une clé, pas laquelle."""
        entrees = declaration("cle-secrete:admin:awa").list_keys()
        assert entrees[0]["subject"] == "awa"
        assert "cle-secrete" not in str(entrees)

    def test_le_contexte_ne_porte_pas_la_cle(self, declaration):
        """Un contexte finit dans un journal : rien de rejouable ne doit s'y trouver."""
        contexte = declaration("cle-secrete:admin:awa").authenticate("cle-secrete")
        assert "cle-secrete" not in str(vars(contexte))


class TestSujetAnonyme:
    """L'ADR refuse d'inventer une identité pour une clé qui n'en a pas."""

    def test_c_est_une_valeur_reelle(self):
        """`None` empêcherait de filtrer ; une valeur regroupe ce qui n'est pas attribué."""
        assert isinstance(ANONYMOUS_SUBJECT, str)
        assert ANONYMOUS_SUBJECT

    def test_le_sujet_ne_derive_pas_de_l_empreinte(self, declaration):
        """Un sujet dérivé de la clé nommerait personne tout en semblant attribué.

        C'est l'alternative que l'ADR-010 écarte : elle produirait une identité
        fabriquée, exactement le défaut que le VOLET_04 ch. 06 interdit.
        """
        contexte = declaration("cle-a:admin").authenticate("cle-a")
        assert contexte.subject == ANONYMOUS_SUBJECT
        assert contexte.key_fingerprint not in contexte.subject


class TestContrat:
    """La forme du type, puisque d'autres modules vont s'y appuyer."""

    def test_identite_par_defaut_anonyme(self):
        """Construire une identité sans sujet ne doit pas lever."""
        assert KeyIdentity(role=Role.USER).subject == ANONYMOUS_SUBJECT

    def test_contexte_par_defaut_anonyme(self):
        """Les appelants existants construisent `RBACContext` sans sujet."""
        contexte = RBACContext(key_fingerprint="abc123", role=Role.USER)
        assert contexte.subject == ANONYMOUS_SUBJECT
        # Les permissions restent dérivées du rôle, pas du sujet.
        assert contexte.permissions == RBACContext(
            key_fingerprint="def456", role=Role.USER, subject="awa"
        ).permissions

    def test_le_sujet_ne_change_pas_les_droits(self, declaration):
        """L'identité dit *qui*, le rôle dit *ce qui est permis*. Les deux restent séparés."""
        gestionnaire = declaration("cle-a:readonly:awa,cle-b:readonly")
        assert (
            gestionnaire.authenticate("cle-a").permissions
            == gestionnaire.authenticate("cle-b").permissions
        )


class TestRevocation:
    """Révoquer une clé ne doit pas dépendre de son sujet, ni l'effacer."""

    def test_revoquer_par_empreinte_fonctionne_toujours(self, declaration):
        """L'administrateur révoque une empreinte : il n'a jamais la clé."""
        gestionnaire = declaration("cle-a:admin:awa")
        empreinte = gestionnaire.list_keys()[0]["fingerprint"]
        assert gestionnaire.revoke(empreinte) is True

        with pytest.raises(PermissionError):
            gestionnaire.authenticate("cle-a")

    def test_une_cle_revoquee_garde_son_sujet_dans_l_inventaire(self, declaration):
        """Savoir *à qui* appartenait une clé coupée est le premier besoin d'un incident."""
        gestionnaire = declaration("cle-a:admin:awa")
        gestionnaire.revoke(gestionnaire.list_keys()[0]["fingerprint"])
        entree = gestionnaire.list_keys()[0]
        assert entree["revoked"] is True
        assert entree["subject"] == "awa"


class TestRouteWhoami:
    """`/auth/whoami` : la seule façon pour un porteur de clé de savoir qui il est."""

    @pytest.fixture
    def client(self, monkeypatch):
        """Application réelle, deux clés déclarées, état RBAC rendu ensuite."""
        from fastapi.testclient import TestClient

        import src.api.server as serveur
        from src.api.rate_limiter import set_valid_api_key_digests

        gestionnaire = serveur.rbac_manager
        ancien = dict(gestionnaire._key_role_map)
        anciennes = set(gestionnaire._revoked_digests)

        monkeypatch.setenv("GALSEN_API_KEYS", "cle-awa:user:awa,cle-anon:readonly")
        gestionnaire.reload()
        set_valid_api_key_digests(gestionnaire.active_key_digests())

        with TestClient(serveur.app) as instance:
            yield instance

        gestionnaire._key_role_map = ancien
        gestionnaire._revoked_digests = anciennes
        set_valid_api_key_digests(gestionnaire.active_key_digests())

    def test_repond_le_sujet_et_le_role(self, client):
        """Ce que l'appelant a besoin de vérifier avant d'agir."""
        corps = client.get("/auth/whoami", headers={"X-API-Key": "cle-awa"}).json()
        assert corps["subject"] == "awa"
        assert corps["role"] == "user"
        assert corps["permissions"]

    def test_une_cle_non_attribuee_le_dit(self, client):
        """Le sujet anonyme doit être visible, pas masqué derrière un nom inventé."""
        corps = client.get("/auth/whoami", headers={"X-API-Key": "cle-anon"}).json()
        assert corps["subject"] == ANONYMOUS_SUBJECT

    def test_aucune_cle_en_clair_dans_la_reponse(self, client):
        """La route décrit l'appelant, elle ne lui rend pas son secret."""
        import json

        corps = json.dumps(client.get("/auth/whoami", headers={"X-API-Key": "cle-awa"}).json())
        assert "cle-awa" not in corps

    def test_une_cle_absente_est_refusee(self, client):
        """La route n'a pas de permission propre, mais elle exige une identité."""
        assert client.get("/auth/whoami").status_code == 401


class TestCritereC2:
    """Le critère de sortie C2, tel qu'écrit dans la roadmap.

    « Deux comptes ne peuvent pas voir les mémoires, fichiers ou notifications
    l'un de l'autre. » Avant l'ADR-010 ce test était impossible à écrire : il n'y
    avait pas de compte. Il porte ici sur la mémoire, la plus représentative des
    trois — le propriétaire y était un champ du corps de la requête.
    """

    @pytest.fixture
    def trois_sujets(self, monkeypatch):
        """Deux usagers et un administrateur, sur l'application réelle."""
        from fastapi.testclient import TestClient

        import src.api.server as serveur
        from src.api.rate_limiter import set_valid_api_key_digests

        gestionnaire = serveur.rbac_manager
        ancien = dict(gestionnaire._key_role_map)
        anciennes = set(gestionnaire._revoked_digests)

        monkeypatch.setenv(
            "GALSEN_API_KEYS", "cle-awa:user:awa,cle-mo:user:moussa,cle-adm:admin:chef"
        )
        gestionnaire.reload()
        set_valid_api_key_digests(gestionnaire.active_key_digests())

        with TestClient(serveur.app) as client:
            yield (
                client,
                {"X-API-Key": "cle-awa"},
                {"X-API-Key": "cle-mo"},
                {"X-API-Key": "cle-adm"},
            )

        gestionnaire._key_role_map = ancien
        gestionnaire._revoked_digests = anciennes
        set_valid_api_key_digests(gestionnaire.active_key_digests())

    @staticmethod
    def _ecrire(client, entetes, contenu="note privée", **extra):
        """Écrit une mémoire et retourne la réponse."""
        return client.post(
            "/memory/store",
            json={"content": contenu, "memory_type": "long_term", **extra},
            headers=entetes,
        )

    def test_le_proprietaire_est_le_sujet_authentifie(self, trois_sujets):
        """Réclamer l'identité d'un autre dans le corps ne doit rien changer.

        C'était le trou : `user_id` venait de la requête, donc n'importe quel
        porteur de clé pouvait écrire dans la mémoire d'autrui.
        """
        client, awa, _, _ = trois_sujets
        reponse = self._ecrire(client, awa, user_id="moussa")
        assert reponse.status_code == 200
        assert reponse.json()["user_id"] == "awa"

    def test_un_sujet_ne_lit_pas_la_memoire_d_un_autre(self, trois_sujets):
        """La définition même de C2."""
        client, awa, moussa, _ = trois_sujets
        identifiant = self._ecrire(client, awa).json()["id"]

        assert client.get(f"/memory/retrieve/{identifiant}", headers=awa).status_code == 200
        assert client.get(f"/memory/retrieve/{identifiant}", headers=moussa).status_code == 404

    def test_le_refus_est_indiscernable_d_une_absence(self, trois_sujets):
        """404 et non 403 : un 403 permettrait d'énumérer les identifiants d'autrui."""
        client, awa, moussa, _ = trois_sujets
        identifiant = self._ecrire(client, awa).json()["id"]

        refus = client.get(f"/memory/retrieve/{identifiant}", headers=moussa)
        inexistant = client.get("/memory/retrieve/identifiant-invente", headers=moussa)
        assert refus.status_code == inexistant.status_code == 404
        assert refus.json()["detail"] == inexistant.json()["detail"]

    def test_la_recherche_ne_traverse_pas_les_sujets(self, trois_sujets):
        """Interdire la lecture directe ne sert à rien si la recherche fuit."""
        client, awa, moussa, _ = trois_sujets
        self._ecrire(client, awa, contenu="récolte arachide")

        assert client.post("/memory/search?query=arachide", headers=moussa).json() == []
        assert client.post("/memory/search?query=arachide", headers=awa).json()

    def test_un_administrateur_voit_tout(self, trois_sujets):
        """L'exploitation resterait impossible sans cette exception."""
        client, awa, _, admin = trois_sujets
        identifiant = self._ecrire(client, awa).json()["id"]
        assert client.get(f"/memory/retrieve/{identifiant}", headers=admin).status_code == 200

    def test_un_administrateur_peut_designer_un_proprietaire(self, trois_sujets):
        """Amorcer des données ou en reprendre pour quelqu'un doit rester possible."""
        client, _, _, admin = trois_sujets
        reponse = self._ecrire(client, admin, user_id="moussa")
        assert reponse.json()["user_id"] == "moussa"


class TestCritereC2Complet:
    """C2 sur les trois magasins que la roadmap nomme : mémoire, fichiers, notifications."""

    @pytest.fixture
    def trois_sujets(self, monkeypatch):
        """Deux usagers et un administrateur, sur l'application réelle."""
        from fastapi.testclient import TestClient

        import src.api.server as serveur
        from src.api.rate_limiter import set_valid_api_key_digests

        gestionnaire = serveur.rbac_manager
        ancien = dict(gestionnaire._key_role_map)
        anciennes = set(gestionnaire._revoked_digests)

        monkeypatch.setenv(
            "GALSEN_API_KEYS", "cle-awa:user:awa,cle-mo:user:moussa,cle-adm:admin:chef"
        )
        gestionnaire.reload()
        set_valid_api_key_digests(gestionnaire.active_key_digests())

        with TestClient(serveur.app) as client:
            yield (
                client,
                {"X-API-Key": "cle-awa"},
                {"X-API-Key": "cle-mo"},
                {"X-API-Key": "cle-adm"},
            )

        gestionnaire._key_role_map = ancien
        gestionnaire._revoked_digests = anciennes
        set_valid_api_key_digests(gestionnaire.active_key_digests())

    @staticmethod
    def _televerser(client, entetes, nom="note.txt", **extra):
        """Téléverse un petit fichier et retourne la réponse."""
        import base64

        return client.post(
            "/file/upload",
            json={
                "name": nom,
                "content_type": "text/plain",
                "data": base64.b64encode(b"contenu prive").decode(),
                **extra,
            },
            headers=entetes,
        )

    def test_le_televerseur_est_le_sujet_authentifie(self, trois_sujets):
        """`uploaded_by` venait du corps : n'importe qui pouvait déposer au nom d'un autre."""
        client, awa, _, admin = trois_sujets
        identifiant = self._televerser(client, awa, uploaded_by="moussa").json()["file_id"]
        depose = client.get(f"/file/{identifiant}", headers=admin).json()
        assert depose["uploaded_by"] == "awa"

    def test_un_sujet_ne_lit_pas_le_fichier_d_un_autre(self, trois_sujets):
        client, awa, moussa, _ = trois_sujets
        identifiant = self._televerser(client, awa).json()["file_id"]
        assert client.get(f"/file/{identifiant}", headers=awa).status_code == 200
        assert client.get(f"/file/{identifiant}", headers=moussa).status_code == 404

    def test_la_liste_de_fichiers_ne_traverse_pas_les_sujets(self, trois_sujets):
        """Demander explicitement le filtre d'un autre ne doit pas l'accorder."""
        client, awa, moussa, _ = trois_sujets
        self._televerser(client, awa)
        assert client.post("/file/list", json={"uploaded_by": "awa"}, headers=moussa).json()["total"] == 0
        assert client.post("/file/list", json={}, headers=awa).json()["total"] >= 1

    def test_les_notifications_d_autrui_restent_invisibles(self, trois_sujets):
        """Ici la contrainte porte sur la lecture : `recipient` est le destinataire."""
        client, awa, moussa, admin = trois_sujets
        client.post(
            "/notification/send",
            json={"notification_type": "info", "title": "Bonjour", "message": "pour awa",
                  "recipient": "awa"},
            headers=admin,
        )
        assert client.post("/notification/list", json={}, headers=moussa).json()["total"] == 0
        assert client.post("/notification/list", json={}, headers=awa).json()["total"] >= 1

    def test_on_ne_vide_pas_la_boite_d_un_autre(self, trois_sujets):
        """`mark-all-read` acceptait un destinataire arbitraire."""
        client, awa, moussa, admin = trois_sujets
        client.post(
            "/notification/send",
            json={"notification_type": "info", "title": "Bonjour", "message": "pour awa",
                  "recipient": "awa"},
            headers=admin,
        )
        client.post("/notification/mark-all-read?recipient=awa", headers=moussa)
        restantes = client.post(
            "/notification/list", json={"unread_only": True}, headers=awa
        ).json()["total"]
        assert restantes >= 1

    def test_envoyer_a_autrui_reste_permis(self, trois_sujets):
        """La contrainte ne doit pas casser la notification légitime.

        Le moteur d'approbation sollicite un opérateur : lier le destinataire à
        l'auteur rendrait cette fonction impossible.
        """
        client, _, _, admin = trois_sujets
        reponse = client.post(
            "/notification/send",
            json={"notification_type": "approval_request", "title": "Validation",
                  "message": "à valider", "recipient": "moussa"},
            headers=admin,
        )
        assert reponse.status_code == 200
