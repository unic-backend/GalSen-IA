"""
Tests de l'exécuteur des dix-huit cas de STEP 12 (R09.2).

Le test qui compte est `test_aucun_cas_n_echoue` : l'exécuteur affirme des
invariants contre le code vivant, et un échec ici est un vrai défaut.
"""

from src.research.golden import CAS, SANS_OBJET, VERDICTS, VERIFIE, run_all


class TestExecuteur:
    """Les dix-huit cas s'exécutent et rendent un verdict déclaré."""

    def test_les_dix_huit_cas_sont_declares(self):
        assert len(CAS) == 18
        assert [c.number for c in CAS] == list(range(1, 19))

    def test_aucun_cas_n_echoue(self):
        resultat = run_all()

        assert resultat["failed"] == []

    def test_chaque_verdict_est_declare(self):
        for cas in run_all()["cases"]:
            assert cas["verdict"] in VERDICTS, cas

    def test_les_comptes_couvrent_tous_les_cas(self):
        resultat = run_all()

        assert sum(resultat["counts"].values()) == resultat["count"] == 18

    def test_chaque_cas_porte_son_invariant(self):
        for cas in run_all()["cases"]:
            assert cas["invariant"].strip()


class TestVerdictsMesures:
    """Ce que l'exécuteur mesure aujourd'hui, et qui doit changer un jour."""

    def test_les_deux_candidats_sont_bloques(self):
        par_numero = {c["number"]: c for c in run_all()["cases"]}

        assert par_numero[4]["verdict"] == "BLOCKED"
        assert par_numero[5]["verdict"] == "BLOCKED"

    def test_un_cas_bloque_dit_ce_qui_manque_et_ce_qui_est_rapporte(self):
        par_numero = {c["number"]: c for c in run_all()["cases"]}

        assert par_numero[4]["missing"]
        assert par_numero[4]["reported"]

    def test_le_delai_d_attente_est_sans_objet_avec_sa_raison(self):
        par_numero = {c["number"]: c for c in run_all()["cases"]}

        assert par_numero[13]["verdict"] == SANS_OBJET
        assert "injectée" in par_numero[13]["reason"]

    def test_la_securite_est_verifiee(self):
        """SSRF, contenu malveillant et isolation des secrets."""
        par_numero = {c["number"]: c for c in run_all()["cases"]}

        for numero in (10, 11, 12):
            assert par_numero[numero]["verdict"] == VERIFIE

    def test_la_note_dit_ce_que_bloque_signifie(self):
        note = run_all()["note"]

        assert "pas un test sauté" in note
        assert "réseau" in note
