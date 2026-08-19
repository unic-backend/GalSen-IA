"""
Tests de l'état de préparation et des scénarios exécutables
(L13.2 et L14.1, ADR-033, §8, §31 à §36).

Les deux tests qui comptent sont `test_le_verdict_change_avec_la_mesure` — un
rapport dont la conclusion est une constante dit la même chose le jour où ça
marche et le jour où ça ne marche pas — et
`test_chaque_module_cite_existe_sur_le_disque`.

**Aucun test n'épingle le verdict de cette machine.** Il changerait sur un poste
avec un micro, et ce serait le comportement voulu.
"""

import pytest

import src.live_context.readiness as readiness_module
from src.live_context.golden import (
    BLOQUE as G_BLOQUE,
)
from src.live_context.golden import (
    CAS,
    VERDICTS,
    VERIFIE,
    run_all,
)
from src.live_context.readiness import (
    ABSENT,
    BLOQUE,
    ETAPES,
    PERCEVOIR,
    PRET,
    REPRESENTER,
    Stage,
    coverage_map,
    readiness,
    readiness_report,
    stage_state,
)


class TestEtapes:
    """Chaque étape est mesurée, jamais affirmée."""

    def test_chaque_module_cite_existe_sur_le_disque(self):
        """En citer un qui n'existe pas publierait une chaîne qui n'existe pas."""
        for entree in readiness()["stages"]:
            if entree["module"]:
                assert entree["state"] != ABSENT or "introuvable" not in \
                    entree["reason"], entree["stage"]

    def test_un_module_declare_et_introuvable_est_absent(self):
        fantome = Stage("FANTOME", REPRESENTER, "src/live_context/inexistant.py")

        etat = stage_state(fantome)

        assert etat["state"] == ABSENT
        assert "introuvable" in etat["reason"]

    def test_une_etape_sans_module_porte_sa_raison(self):
        for etape in ETAPES:
            if not etape.module:
                assert len(etape.absent_reason.strip()) > 30, etape.name

    def test_chaque_etape_declare_sa_nature(self):
        for etape in ETAPES:
            assert etape.nature in (PERCEVOIR, REPRESENTER)

    def test_un_manque_de_module_python_est_nomme(self):
        etape = Stage("X", PERCEVOIR, "src/live_context/state.py",
                      requires_modules=("bibliotheque_absente",))

        etat = stage_state(etape)

        assert etat["state"] == BLOQUE
        assert any("bibliotheque_absente" in m["name"] for m in etat["missing"])

    def test_un_manque_d_entree_est_nomme_avec_son_constat(self):
        etape = Stage("X", PERCEVOIR, "src/live_context/state.py",
                      requires_inputs=("camera",))

        etat = stage_state(etape)

        for manque in etat["missing"]:
            assert manque["reason"].strip()

    def test_une_etape_sans_besoin_est_prete(self):
        etape = Stage("X", REPRESENTER, "src/live_context/state.py")

        assert stage_state(etape)["state"] == PRET


class TestVerdictCalcule:
    """Un verdict constant dirait la même chose dans tous les cas."""

    def test_le_verdict_change_avec_la_mesure(self, monkeypatch):
        """La preuve qu'il est calculé et non écrit."""
        avant = readiness()["state"]

        monkeypatch.setattr(readiness_module, "ETAPES",
                            (Stage("X", REPRESENTER,
                                   "src/live_context/state.py"),))
        apres = readiness()["state"]

        assert avant != apres

    def test_le_rapport_declare_que_le_verdict_n_est_pas_ecrit(self):
        assert readiness_report()["verdict_is_written"] is False

    def test_les_deux_natures_sont_comptees_separement(self):
        """Une moyenne entre tout représenter et ne rien percevoir ne dit rien."""
        par_nature = readiness()["by_nature"]

        assert set(par_nature) == {PERCEVOIR, REPRESENTER}
        for comptes in par_nature.values():
            assert set(comptes) == {PRET, BLOQUE, ABSENT}

    def test_les_comptes_couvrent_toutes_les_etapes(self):
        mesure = readiness()

        assert sum(mesure["counts"].values()) == len(ETAPES)

    def test_absent_et_bloque_sont_distincts_dans_le_verdict(self):
        """Le second s'installe, le premier s'écrit."""
        regles = " ".join(readiness_report()["rules"])

        assert "ABSENT n'est pas BLOCKED" in regles

    def test_les_manques_sont_nommes_avec_leur_nature(self):
        for manque in readiness()["missing"]:
            assert manque.startswith(("input:", "python_module:"))


class TestCouverture:
    """Citer un fichier de tests inexistant publierait une couverture fausse."""

    def test_chaque_fichier_cite_est_verifie(self):
        couverture = coverage_map()

        for domaine in couverture["domains"].values():
            assert domaine["found"] == domaine["declared"]

    def test_les_domaines_declares_sont_comptes(self):
        couverture = coverage_map()

        assert couverture["covered_count"] == couverture["declared_count"]

    def test_un_fichier_absent_serait_signale(self, monkeypatch):
        monkeypatch.setitem(readiness_module.COUVERTURE, "fantome",
                            ("tests/live_context/test_inexistant.py",))

        couverture = coverage_map()

        assert couverture["domains"]["fantome"]["covered"] is False


class TestScenariosExecutables:
    """Le programme peut dire ce qu'il tient, pas seulement lancer sa suite."""

    def test_les_trente_scenarios_du_paragraphe_35_s_executent(self):
        resultat = run_all()

        assert resultat["count"] == 30
        assert resultat["count"] == len(CAS)

    def test_les_deux_moities_du_programme_sont_couvertes(self):
        """Les quinze premiers cas lisent l'état, les quinze suivants les gardes."""
        titres = " ".join(c.title for c in CAS)

        assert "ABSENT n'est pas UNKNOWN" in titres
        assert "Un consentement ne lève pas une ADR" in titres
        assert "L'état d'ensemble est calculé" in titres

    def test_aucun_cas_n_echoue(self):
        resultat = run_all()

        assert resultat["failed"] == [], resultat["failed"]

    def test_chaque_cas_rend_un_verdict_declare(self):
        for cas in run_all()["cases"]:
            assert cas["verdict"] in VERDICTS

    def test_les_numeros_sont_uniques_et_continus(self):
        numeros = [c.number for c in CAS]

        assert numeros == list(range(1, len(CAS) + 1))

    def test_chaque_cas_porte_son_invariant(self):
        for cas in CAS:
            assert len(cas.invariant.strip()) > 20

    def test_un_cas_bloque_nomme_ce_qui_manque(self):
        """BLOCKED est une assertion, pas un test sauté."""
        bloques = [c for c in run_all()["cases"] if c["verdict"] == G_BLOQUE]

        for cas in bloques:
            assert cas["missing"].strip()
            assert cas["reported"].strip()

    def test_un_cas_verifie_porte_sa_preuve(self):
        verifies = [c for c in run_all()["cases"] if c["verdict"] == VERIFIE]

        assert verifies
        for cas in verifies:
            assert cas["evidence"]

    def test_les_comptes_couvrent_tous_les_cas(self):
        resultat = run_all()

        assert sum(resultat["counts"].values()) == resultat["count"]

    def test_un_cas_qui_echoue_est_rapporte_pas_masque(self, monkeypatch):
        from src.live_context.golden import GoldenCase

        def _casse():
            raise AssertionError("invariant rompu")

        monkeypatch.setattr(
            "src.live_context.golden.CAS",
            [GoldenCase(1, "cas de contrôle",
                        "un invariant volontairement rompu pour ce test",
                        _casse)])

        resultat = run_all()

        assert resultat["failed"] == [1]
        assert resultat["cases"][0]["verdict"] == "FAILED"


def test_le_rapport_de_readiness_porte_la_mesure():
    rapport = readiness_report()

    assert "measured" in rapport
    assert rapport["declared_stages"] == [e.name for e in ETAPES]


def test_aucun_cas_n_ouvre_de_peripherique():
    """Un scénario qui en aurait besoin rendrait BLOCKED."""
    try:
        run_all()
    except OSError as erreur:  # pragma: no cover - le test est l'assertion
        pytest.fail(f"accès système inattendu : {erreur}")
