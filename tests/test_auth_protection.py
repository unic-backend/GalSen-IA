"""
Tests for what ADR-029 still owed: lockout, password reset, breach disclosure.

ADR-029 chose option C — the platform keeps password hashes — and listed in its
own *Consequences* what remained owed. A debt written into an ADR and never
settled eventually reads as a decision.

One property runs through all three, and it is the one that is easy to lose:
**none of these mechanisms may reveal which accounts exist.** A lockout that
only counts real accounts is an existence oracle. A reset form that answers
differently for an unknown address is a directory. The tests below are mostly
about that.

The other property is about honesty: `breach_disclosure` computes what must be
said and to whom, and reports `NOT_SENT` while no channel is configured. A
module claiming to have notified people when nothing was sent would lie about
the only obligation that really matters in a breach.
"""

import pytest

from src.auth.protection import (
    NON_ENVOYE,
    PRET,
    LoginGuard,
    PasswordResetService,
    ProtectionRefused,
    breach_disclosure,
    protection_report,
)


class TestVerrouillage:
    """Compter les échecs sans dire qui existe."""

    def test_le_verrou_tombe_apres_le_seuil(self):
        garde = LoginGuard(max_failures=3, lock_seconds=60)
        for _ in range(2):
            assert garde.register_failure("awa@example.test")["locked"] is False
        assert garde.register_failure("awa@example.test")["locked"] is True

    def test_une_adresse_inconnue_compte_pareil(self):
        """Ne compter que les comptes réels ferait un oracle d'existence."""
        garde = LoginGuard(max_failures=2, lock_seconds=60)
        garde.register_failure("inconnu@example.test")
        etat = garde.register_failure("inconnu@example.test")
        assert etat["locked"] is True

    def test_l_etat_ne_dit_jamais_si_le_compte_existe(self):
        garde = LoginGuard()
        jamais_vue = garde.state("jamais@example.test")
        assert set(jamais_vue) == {"locked", "remaining_seconds", "failures"}
        assert jamais_vue == {"locked": False, "remaining_seconds": 0.0,
                              "failures": 0}

    def test_le_verrou_expire(self):
        garde = LoginGuard(max_failures=1, lock_seconds=10)
        garde.register_failure("awa@example.test", now=1000.0)
        assert garde.state("awa@example.test", now=1005.0)["locked"] is True
        assert garde.state("awa@example.test", now=1011.0)["locked"] is False

    def test_les_echecs_hors_fenetre_ne_comptent_pas(self):
        """Cinq échecs étalés sur une semaine ne sont pas une attaque."""
        garde = LoginGuard(max_failures=2, window_seconds=60)
        garde.register_failure("awa@example.test", now=1000.0)
        assert garde.register_failure("awa@example.test",
                                      now=2000.0)["locked"] is False

    def test_une_reussite_efface_les_echecs(self):
        garde = LoginGuard(max_failures=3)
        garde.register_failure("awa@example.test")
        garde.register_success("awa@example.test")
        assert garde.state("awa@example.test")["failures"] == 0

    def test_les_adresses_ne_sont_pas_gardees_en_clair(self):
        """Un vidage mémoire du garde ne doit pas rendre la liste des adresses."""
        garde = LoginGuard()
        garde.register_failure("awa@example.test")
        assert "awa@example.test" not in str(garde.__dict__)

    def test_un_seuil_sous_un_est_refuse(self):
        with pytest.raises(ProtectionRefused):
            LoginGuard(max_failures=0)

    def test_la_limite_du_magasin_est_ecrite(self):
        rapport = LoginGuard().report()
        assert rapport["persistence"] == "IN_MEMORY"
        assert "redémarrage" in rapport["limitation"]


class TestReinitialisation:
    """Le formulaire « mot de passe oublié » ne doit pas être un annuaire."""

    def test_la_reponse_est_la_meme_pour_un_compte_inconnu(self):
        service = PasswordResetService()
        connu = service.request_reset("awa@example.test", "u-1")
        inconnu = service.request_reset("fantome@example.test", None)
        assert connu["accepted"] == inconnu["accepted"] is True
        assert inconnu["ticket"] is None
        assert connu["note"] == inconnu["note"]

    def test_un_jeton_ne_sert_qu_une_fois(self):
        service = PasswordResetService()
        billet = service.request_reset("awa@example.test", "u-1")["ticket"]
        assert service.consume(billet.token) == "u-1"
        with pytest.raises(ProtectionRefused) as erreur:
            service.consume(billet.token)
        assert "déjà utilisé" in str(erreur.value)

    def test_un_jeton_expire_est_refuse(self):
        service = PasswordResetService(ttl_seconds=60)
        billet = service.request_reset("awa@example.test", "u-1",
                                       now=1000.0)["ticket"]
        with pytest.raises(ProtectionRefused) as erreur:
            service.consume(billet.token, now=1100.0)
        assert "expiré" in str(erreur.value)

    def test_une_seconde_demande_invalide_la_premiere(self):
        """Deux jetons vivants doublent la surface d'attaque sans rien apporter."""
        service = PasswordResetService()
        premier = service.request_reset("awa@example.test", "u-1")["ticket"]
        second = service.request_reset("awa@example.test", "u-1")["ticket"]
        with pytest.raises(ProtectionRefused):
            service.consume(premier.token)
        assert service.consume(second.token) == "u-1"

    def test_un_jeton_inconnu_est_refuse(self):
        with pytest.raises(ProtectionRefused):
            PasswordResetService().consume("jeton-invente")

    def test_le_service_ne_connait_pas_l_annuaire(self):
        """C'est l'appelant qui a fait la recherche — le service ne cherche pas."""
        regles = " ".join(PasswordResetService().report()["rules"])
        assert "ne connaît pas l'annuaire" in regles

    def test_une_duree_de_vie_nulle_est_refusee(self):
        with pytest.raises(ProtectionRefused):
            PasswordResetService(ttl_seconds=0)


class TestNotificationDeFuite:
    """Ne jamais rapporter un envoi qui n'a pas eu lieu."""

    def test_sans_canal_rien_n_est_envoye(self):
        dossier = breach_disclosure(["u-1", "u-2"], ["password_hash"], 1000.0)
        assert dossier["state"] == NON_ENVOYE
        assert "rien n'est parti" in dossier["reason"]

    def test_avec_un_canal_le_dossier_est_pret_pas_envoye(self):
        """`READY` ne veut pas dire « les personnes ont été prévenues »."""
        dossier = breach_disclosure(["u-1"], ["email"], 1000.0,
                                    delivery_channel="smtp")
        assert dossier["state"] == PRET
        assert "ne veut pas dire" in dossier["note"]

    def test_ce_qui_doit_etre_dit_est_enumere(self):
        obligations = breach_disclosure(["u-1"], ["password_hash"], 1000.0)
        assert len(obligations["must_disclose"]) == 4
        assert any("sans le minimiser" in ligne
                   for ligne in obligations["must_disclose"])

    def test_l_expose_est_repris_tel_quel(self):
        dossier = breach_disclosure(["u-1"], ["password_hash", "email"], 1000.0)
        assert dossier["exposed"] == ["password_hash", "email"]

    def test_une_notification_sans_destinataire_est_refusee(self):
        with pytest.raises(ProtectionRefused) as erreur:
            breach_disclosure([], ["password_hash"], 1000.0)
        assert "analyse n'est pas finie" in str(erreur.value)

    def test_une_notification_sans_objet_est_refusee(self):
        """« On ne sait pas encore » s'écrit, ne se laisse pas vide."""
        with pytest.raises(ProtectionRefused) as erreur:
            breach_disclosure(["u-1"], [], 1000.0)
        assert "pas à laisser vide" in str(erreur.value)


class TestDetteDeLAdr:
    """Ce qui reste ouvert est écrit, pas oublié."""

    def test_les_trois_obligations_sont_traitees(self):
        rapport = protection_report()
        items = {e["item"] for e in rapport["owed_by_adr_029"]}
        assert items == {"lockout after repeated failures", "password reset",
                         "breach notification"}

    def test_la_notification_n_est_pas_annoncee_comme_envoyee(self):
        etats = {e["item"]: e["state"] for e in
                 protection_report()["owed_by_adr_029"]}
        assert etats["breach notification"] == "PREPARED_NOT_SENT"

    def test_ce_qui_reste_ouvert_est_nomme(self):
        ouvert = " ".join(protection_report()["still_open"])
        assert "GALSEN_STORAGE_BACKEND=sqlite" in ouvert
