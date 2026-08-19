"""
Tests de la rétention et de l'écriture en mémoire (L11, ADR-033, §14 et §28).

Deux tests portent tout le volet : `test_un_consentement_ne_leve_pas_adr_018`
— le consentement est nécessaire, jamais suffisant — et
`test_une_inconnue_n_entre_pas_en_memoire`, parce qu'une inconnue relue dans six
mois ressemble à ce qui a été appris.
"""

import time

import pytest

from src.creative.reference.consent import (
    CONSERVATION_DUREE,
    CONSERVATION_JUSQU_A_REVOCATION,
    PORTEE_COMPTE,
    PORTEE_ORGANISATION,
    REVOQUE,
    ConsentScope,
)
from src.live_context.memory import (
    ACTES_D_ECRITURE,
    may_write,
    memory_report,
    write_observation,
)
from src.live_context.retention import (
    ACTES,
    MODALITES_SANS_SORTIE,
    RetentionRefused,
    authorize_act,
    retention_bound,
    retention_report,
    session_policy,
)
from src.live_context.state import MESURE, Observation, absent, unknown


def _consentement(**kwargs) -> ConsentScope:
    defauts = dict(granted_by="Awa Diop", subject="Awa Diop",
                   permitted_uses=ACTES, evidence="formulaire signé")
    defauts.update(kwargs)
    return ConsentScope(**defauts)


def _obs(**kwargs) -> Observation:
    defauts = dict(subject="transcript", status=MESURE, modality="audio",
                   value="le budget est de 12 M")
    defauts.update(kwargs)
    return Observation(**defauts)


class TestCinqActes:
    """Aucun n'est interdit par nature ; aucun ne se fait en silence."""

    def test_les_cinq_actes_sont_declares(self):
        assert set(ACTES) == {"record", "retain", "upload", "index", "share"}

    def test_un_acte_inconnu_est_refuse_bruyamment(self):
        with pytest.raises(RetentionRefused, match="non déclaré"):
            authorize_act("stream", _consentement())

    def test_chaque_acte_dit_ce_qu_il_fait(self):
        for acte in ACTES:
            assert authorize_act(acte, _consentement())["act_means"].strip()

    def test_une_autorisation_produit_toujours_sa_trace(self):
        decision = authorize_act("record", _consentement(), modality="audio")

        assert decision["allowed"] is True
        assert decision["silent"] is False
        assert decision["decided_at"] > 0

    def test_un_refus_produit_aussi_sa_trace(self):
        decision = authorize_act("record", None)

        assert decision["allowed"] is False
        assert decision["silent"] is False
        assert decision["reason"].strip()


class TestLeConsentementEstNecessaireJamaisSuffisant:
    """ADR-018 ne prévoit aucune exception pour quelqu'un qui accepterait."""

    def test_un_consentement_ne_leve_pas_adr_018(self):
        accord = _consentement(permitted_uses=("upload", "share", "record"))

        decision = authorize_act("upload", accord, modality="screen")

        assert decision["allowed"] is False
        assert decision["unconditional_refusal"] is True

    def test_le_refus_inconditionnel_precede_le_consentement(self):
        """Une portée valide ne doit jamais apparaître comme une autorisation."""
        decision = authorize_act("share", _consentement(), modality="screen")

        assert decision["basis"].startswith("ADR-018")

    def test_l_ecran_reste_utilisable_sans_sortir_de_la_machine(self):
        """Le refus porte sur la sortie, pas sur l'écran lui-même."""
        decision = authorize_act("record", _consentement(), modality="screen")

        assert decision["allowed"] is True

    def test_les_modalites_sans_sortie_sont_nominatives(self):
        assert "screen" in MODALITES_SANS_SORTIE
        for raison in MODALITES_SANS_SORTIE.values():
            assert "ADR-018" in raison


class TestAbsenceEtPortee:
    """L'absence de portée est l'absence de permission."""

    def test_sans_consentement_tout_est_refuse(self):
        politique = session_policy(None)

        assert politique["allowed"] == []
        assert len(politique["refused"]) == 5

    def test_un_usage_hors_liste_est_refuse(self):
        accord = _consentement(permitted_uses=("record",))

        assert authorize_act("index", accord)["allowed"] is False

    def test_une_portee_plus_large_n_est_pas_accordee(self):
        accord = _consentement(scope=PORTEE_COMPTE)

        decision = authorize_act("index", accord, at_scope=PORTEE_ORGANISATION)

        assert decision["allowed"] is False

    def test_un_consentement_revoque_refuse(self):
        decision = authorize_act("record", _consentement(), state=REVOQUE)

        assert decision["allowed"] is False
        assert "évoqu" in decision["reason"]


class TestConservation:
    """« Pour toujours » n'est pas une politique."""

    def test_une_duree_ecoulee_ne_se_prolonge_pas(self):
        expire = _consentement(retention=CONSERVATION_DUREE,
                               expires_at=time.time() - 10)

        assert authorize_act("retain", expire)["allowed"] is False

    def test_jusqu_a_revocation_est_borne_par_une_decision(self):
        accord = _consentement(retention=CONSERVATION_JUSQU_A_REVOCATION)

        borne = retention_bound(accord)

        assert borne["bounded"] is True
        assert borne["ends_when"] == "une révocation"

    def test_jusqu_a_revocation_n_a_pas_d_instant_d_expiration(self):
        """Une durée inconnue n'est pas une durée infinie."""
        assert retention_bound(_consentement())["expires_at"] is None

    def test_sans_consentement_il_n_y_a_pas_de_politique(self):
        borne = retention_bound(None)

        assert borne["bounded"] is False
        assert borne["policy"] is None


class TestPolitiqueDeSession:
    """Aucun verdict global de conformité."""

    def test_aucun_booleen_de_conformite(self):
        assert session_policy(_consentement())["compliant"] is None

    def test_les_actes_permis_et_refuses_sont_nommes(self):
        politique = session_policy(_consentement(), modality="screen")

        assert set(politique["unconditionally_refused"]) == {"upload", "share"}
        assert set(politique["allowed"]) == {"record", "retain", "index"}

    def test_les_cinq_actes_sont_toujours_decides(self):
        assert len(session_policy(None)["acts"]) == 5


class TestEcritureEnMemoire:
    """Trois refus, et le premier est le moins évident."""

    def test_une_inconnue_n_entre_pas_en_memoire(self):
        decision = may_write(unknown("language", "audio"), "Awa Diop",
                             _consentement())

        assert decision["allowed"] is False
        assert "six mois" in decision["reason"]

    def test_une_absence_n_entre_pas_non_plus(self):
        decision = may_write(absent("screen", "screen", "DISPLAY vide"),
                             "Awa Diop", _consentement())

        assert decision["allowed"] is False

    def test_sans_lien_declare_il_n_y_a_pas_de_permission(self):
        decision = may_write(_obs(), "  ", _consentement())

        assert decision["allowed"] is False
        assert "n'a pas été créé" in decision["reason"]

    def test_un_consentement_d_un_autre_sujet_ne_couvre_pas(self):
        accord = _consentement(subject="Moussa Fall")

        decision = may_write(_obs(), "Awa Diop", accord)

        assert decision["allowed"] is False
        assert "quelqu'un d'autre" in decision["reason"]

    def test_l_ecriture_declenche_conserver_et_indexer(self):
        decision = may_write(_obs(), "Awa Diop", _consentement())

        assert [d["act"] for d in decision["acts"]] == list(ACTES_D_ECRITURE)

    def test_accepter_de_garder_n_est_pas_accepter_d_indexer(self):
        accord = _consentement(permitted_uses=("record", "retain"))

        decision = may_write(_obs(), "Awa Diop", accord)

        assert decision["allowed"] is False
        assert "index" in decision["reason"]

    def test_une_ecriture_autorisee_porte_sa_charge(self):
        decision = may_write(_obs(), "Awa Diop", _consentement())

        assert decision["allowed"] is True
        assert decision["payload"]["content"] == "le budget est de 12 M"
        assert decision["payload"]["subject"] == "Awa Diop"


class TestRienN_EstEcritParDefaut:
    """Ne jamais prétendre avoir écrit là où il n'y avait rien pour écrire."""

    def test_sans_magasin_rien_n_est_ecrit(self):
        decision = write_observation(_obs(), "Awa Diop", _consentement())

        assert decision["allowed"] is True
        assert decision["written"] is False
        assert "aucun magasin" in decision["reason"]

    def test_aucun_identifiant_n_est_fabrique(self):
        decision = write_observation(_obs(), "Awa Diop", _consentement())

        assert "memory_id" not in decision

    def test_avec_un_magasin_l_ecriture_a_lieu(self):
        class _Magasin:
            def __init__(self):
                self.items = []

            def save_memory(self, item):
                self.items.append(item)
                return "mem_1"

        magasin = _Magasin()

        decision = write_observation(_obs(), "Awa Diop", _consentement(),
                                     memory=magasin, session_id="s1")

        assert decision["written"] is True
        assert decision["memory_id"] == "mem_1"
        assert magasin.items[0].user_id == "Awa Diop"

    def test_un_refus_n_ecrit_rien_meme_avec_un_magasin(self):
        class _Magasin:
            def save_memory(self, item):
                raise AssertionError("écriture refusée, magasin appelé")

        decision = write_observation(unknown("language", "audio"), "Awa Diop",
                                     _consentement(), memory=_Magasin())

        assert decision["written"] is False


class TestRapports:
    """Ce qui est réutilisé, et ce qui est refusé."""

    def test_la_retention_declare_qu_un_consentement_ne_leve_pas_une_adr(self):
        assert retention_report()["consent_can_lift_adr"] is False

    def test_aucun_chemin_silencieux(self):
        assert retention_report()["silent_paths"] == 0

    def test_la_memoire_n_ecrit_pas_par_defaut(self):
        assert memory_report()["writes_by_default"] is False

    def test_les_modules_reutilises_sont_nommes(self):
        reutilises = " ".join(retention_report()["reused"]
                              + memory_report()["reused"])

        assert "consent.py" in reutilises
        assert "memory_engine/" in reutilises

    def test_les_regles_qui_comptent_sont_ecrites(self):
        regles = " ".join(retention_report()["rules"] + memory_report()["rules"])

        assert "nécessaire, jamais suffisant" in regles
        assert "Pour toujours" in regles
        assert "aucune n'a été" in regles
