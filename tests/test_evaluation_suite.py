"""
Les dix épreuves, et surtout ce qu'elles refusent de mesurer.

Ce fichier éprouve un harnais qui n'a **jamais atteint un modèle** sur cette
machine. Ce qui est donc vérifié ici, ce sont les refus : une réponse composée
par la plateforme n'est pas notée comme une réponse du modèle, une épreuve sans
vérité vérifiable n'invente pas de score, et un taux sur zéro exécution vaut
`None`.

Ce sont ces trois refus qui décident si un futur tableau de comparaison veut
dire quelque chose.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.evaluation_suite import (  # noqa: E402
    EPREUVES,
    FAIL,
    NON_EXECUTE,
    NON_VERIFIE,
    PASS,
    _nombres,
    evaluer,
    rapport_lisible,
)


def _reponse(texte: str, **surcharges):
    """Une charge `ChatResponse` plausible, que chaque test ajuste."""
    charge = {
        "answer": texte,
        "generated": True,
        "model_used": "modele-de-test",
        "grounding": {"status": "NOT_CHECKED"},
        "deliberation": {"retries": 0, "stop_reason": "verified",
                         "remaining_findings": []},
    }
    charge.update(surcharges)
    return charge


class TestLesDixEpreuves:
    """Leur forme, et les réponses attendues."""

    def test_il_y_en_a_dix(self):
        assert len(EPREUVES) == 10
        assert [e.identifiant for e in EPREUVES] == [f"TEST-{i:02d}" for i in range(1, 11)]

    def test_quatre_epreuves_n_ont_aucune_verite_verifiable(self):
        """
        Expliquer l'IA, bâtir une stratégie de chantier, citer une PME, écrire
        du wolof : aucune de ces quatre n'a de bonne réponse qu'une machine
        puisse trancher. Leur inventer un score fabriquerait une mesure.
        """
        sans_controle = [e.identifiant for e in EPREUVES if e.controle is None]
        assert sans_controle == ["TEST-01", "TEST-04", "TEST-08", "TEST-09"]

    @pytest.mark.parametrize(
        "identifiant, bonne, mauvaise",
        [
            ("TEST-02", "Il y a 5 enfants en tout.", "Il y a 8 enfants en tout."),
            ("TEST-03", "Le total est de 1 440 000 FCFA.", "Le total est de 1 400 000 FCFA."),
            ("TEST-07", "187 × 46 = 8 602.", "187 × 46 = 8 502."),
            ("TEST-10", "Il faut 14 ouvriers.", "Il faut 13 ouvriers."),
        ],
    )
    def test_les_controles_tranchent(self, identifiant, bonne, mauvaise):
        epreuve = next(e for e in EPREUVES if e.identifiant == identifiant)
        assert epreuve.controle(bonne) is True
        assert epreuve.controle(mauvaise) is False

    def test_la_soeur_partagee_est_le_piege_de_l_epreuve_logique(self):
        """
        « 4 fils, chacun a une sœur » : la sœur est commune. Répondre 8 est
        l'erreur classique, et l'épreuve existe pour l'attraper.
        """
        epreuve = next(e for e in EPREUVES if e.identifiant == "TEST-02")
        assert "5" in epreuve.attendu

    @pytest.mark.parametrize(
        "ecriture", ["1 440 000", "1.440.000", "1440000", "1,440,000"]
    )
    def test_les_separateurs_de_milliers_ne_font_pas_echouer(self, ecriture):
        """
        Une réponse juste ne doit pas échouer pour une question de typographie.
        """
        epreuve = next(e for e in EPREUVES if e.identifiant == "TEST-03")
        assert epreuve.controle(f"Le total est de {ecriture} FCFA.") is True

    def test_un_nombre_colle_a_un_mot_est_quand_meme_lu(self):
        assert 8602 in _nombres("Résultat:8602.")


class TestCeQuiEstRefuse:
    """Les trois refus qui rendent un futur tableau honnête."""

    def test_une_reponse_non_generee_n_est_pas_notee(self):
        """
        La plateforme compose parfois un texte à partir de ce que les agents ont
        rapporté. Le noter mesurerait le repli, pas le modèle — et une bonne
        note attribuée au repli ferait croire qu'un modèle a répondu.
        """
        charge = _reponse("Le total est de 1 440 000 FCFA.", generated=False,
                          generation_unavailable="aucun fournisseur")
        rapport = evaluer(lambda _m: charge, modele="absent")
        assert {r.issue for r in rapport.resultats} == {NON_EXECUTE}
        assert rapport.taux is None

    def test_une_epreuve_sans_verite_rend_non_verifie(self):
        rapport = evaluer(lambda _m: _reponse("Une explication quelconque."))
        par_id = {r.identifiant: r for r in rapport.resultats}
        assert par_id["TEST-01"].issue == NON_VERIFIE
        assert par_id["TEST-04"].issue == NON_VERIFIE

    def test_le_taux_ne_compte_que_les_epreuves_verifiables(self):
        """
        Rapporter un taux sur les dix compterait quatre `NOT_CHECKED` comme des
        échecs, ce qu'elles ne sont pas.
        """
        rapport = evaluer(lambda _m: _reponse("Une réponse sans aucun nombre."))
        assert len(rapport.verifiables) == 6
        assert rapport.taux == 0.0

    def test_un_taux_sur_zero_execution_vaut_none(self):
        charge = _reponse("peu importe", generated=False)
        assert evaluer(lambda _m: charge).taux is None

    def test_une_panne_d_appel_est_un_resultat_pas_une_exception(self):
        def tombe(_message):
            raise RuntimeError("la route a répondu 503")

        rapport = evaluer(tombe, modele="absent")
        assert len(rapport.resultats) == 10
        assert all(r.issue == NON_EXECUTE for r in rapport.resultats)
        assert "503" in rapport.resultats[0].motif


class TestCeQuiEstEnregistre:
    """Ce que le rapport garde, et qui permet de le relire plus tard."""

    def test_la_reponse_complete_est_conservee(self):
        """
        Quatre épreuves ne peuvent être jugées que par un humain : sans le texte
        entier, elles ne seraient jugeables par personne.
        """
        rapport = evaluer(lambda _m: _reponse("Une réponse assez longue à relire."))
        assert all(r.reponse for r in rapport.resultats)

    def test_le_modele_qui_a_repondu_est_nomme(self):
        rapport = evaluer(lambda _m: _reponse("x"), modele="attendu")
        assert rapport.resultats[0].modele == "modele-de-test"

    def test_la_deliberation_est_enregistree(self):
        """Combien de reprises, pourquoi l'arrêt, ce qui restait à reprocher."""
        charge = _reponse("Le total est 2 + 2 = 5.", deliberation={
            "retries": 1, "stop_reason": "iteration_budget_exhausted",
            "remaining_findings": [{"code": "arithmetic_error"}],
        })
        resultat = evaluer(lambda _m: charge).resultats[0]
        assert resultat.reprises == 1
        assert resultat.arret == "iteration_budget_exhausted"
        assert resultat.constats == ["arithmetic_error"]

    def test_le_rapport_porte_de_quoi_se_comparer(self):
        charge = evaluer(lambda _m: _reponse("x"), modele="m", backend="ollama",
                         quantisation="Q6_K", materiel="RTX A2000").to_dict()
        for champ in ("model", "backend", "quantization", "hardware",
                      "executed", "checkable", "not_checked", "pass_rate"):
            assert champ in charge

    def test_le_rapport_lisible_dit_non_mesurable_sans_execution(self):
        charge = _reponse("x", generated=False)
        assert "NON MESURABLE" in rapport_lisible(evaluer(lambda _m: charge))


class TestLeScriptTraverseLaChaineReelle:
    """
    Le script appelle l'application réelle, pas un double. Sur cette machine il
    doit donc atteindre le vrai motif de blocage — l'absence de fournisseur —
    et non une erreur d'authentification ou d'import.
    """

    def test_il_atteint_l_absence_de_modele_et_le_dit(self):
        racine = os.path.join(os.path.dirname(__file__), "..")
        sortie = subprocess.run(
            [sys.executable, "scripts/models/evaluate.py", "--modele", "qwen3.5:9b"],
            cwd=racine, capture_output=True, text=True, timeout=900,
        )
        assert "exécutées    : 0/10" in sortie.stdout
        assert "fournisseur" in sortie.stdout
        assert "401" not in sortie.stdout, "l'authentification doit être satisfaite"
        assert "NON MESURABLE" in sortie.stdout

    def test_aucune_cle_n_est_affichee(self):
        """Une clé jetable reste jetable : elle ne doit apparaître nulle part."""
        racine = os.path.join(os.path.dirname(__file__), "..")
        sortie = subprocess.run(
            [sys.executable, "scripts/models/evaluate.py", "--modele", "qwen3.5:9b"],
            cwd=racine, capture_output=True, text=True, timeout=900,
        )
        assert "X-API-Key" not in sortie.stdout
        assert "GALSEN_API_KEYS" not in sortie.stdout


class TestLIssuePassEstAtteignable:
    """
    Un harnais qui ne peut rendre que `FAIL` ou `NOT_EXECUTED` ne prouverait
    rien le jour où un modèle répondra bien.
    """

    def test_de_bonnes_reponses_donnent_pass(self):
        bonnes = {
            "TEST-02": "Il y a 5 enfants.",
            "TEST-03": "Total : 1 440 000 FCFA.",
            "TEST-05": "def cout_total(plaques, prix): return plaques * prix",
            "TEST-06": "Le Sénégal compte 14 régions, d'après geoBoundaries.",
            "TEST-07": "187 × 46 = 8 602.",
            "TEST-10": "Il faut 14 ouvriers.",
        }
        index = {"n": 0}

        def repondre(message):
            epreuve = EPREUVES[index["n"]]
            index["n"] += 1
            return _reponse(bonnes.get(epreuve.identifiant, "Une réponse libre."))

        rapport = evaluer(repondre, modele="parfait")
        assert rapport.taux == 1.0
        assert {r.issue for r in rapport.resultats} == {PASS, NON_VERIFIE}

    def test_de_mauvaises_reponses_donnent_fail(self):
        rapport = evaluer(lambda _m: _reponse("Je ne sais pas."), modele="mauvais")
        assert FAIL in {r.issue for r in rapport.resultats}
        assert rapport.taux == 0.0
