"""
Ce qu'il faut avant d'entraîner SamP et ToP (VOLET 33).

Le brief demandait de l'entraînement distribué et du RLHF. La mesure a renversé
l'ordre : en QLoRA un modèle de 7–8 milliards de paramètres tient sur un seul
GPU, et n'a besoin d'aucune distribution. Les vrais obstacles sont l'absence de
données, l'absence de mesure, et le signal que personne ne capture — le seul dont
le coût augmente chaque jour, parce qu'une correction non enregistrée est perdue.

Ces tests portent sur les trois choses vérifiables sans GPU : la capture, la
mesure et la lignée.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.training.evaluation import (  # noqa: E402
    EvalCase,
    EvalResult,
    compare,
    evaluate_retrieval,
    load_cases,
)
from src.training.feedback import (  # noqa: E402
    Feedback,
    FeedbackKind,
    SQLiteFeedbackStore,
    scrub,
)
from src.training.lineage import LineageRegistry, ModelVersion  # noqa: E402


@pytest.fixture
def magasin(tmp_path):
    """Magasin de retours isolé."""
    return SQLiteFeedbackStore(str(tmp_path / "feedback.sqlite"))


# ----------------------------------------------------------------------
# Capture du signal
# ----------------------------------------------------------------------

def test_une_correction_est_conservee(magasin):
    """Le signal qui vaut le plus : l'utilisateur a réécrit la réponse."""
    identifiant = magasin.record(Feedback(
        prompt="Quand semer le mil ?", response="En décembre.",
        kind=FeedbackKind.CORRECTION, correction="À l'arrivée des pluies.",
        consent_to_train=True, subject="moussa",
    ))

    retours = magasin.list_feedback()
    assert len(retours) == 1
    assert retours[0].id == identifiant
    assert retours[0].correction == "À l'arrivée des pluies."


def test_les_donnees_personnelles_sont_retirees_a_l_ecriture(magasin):
    """
    Filtrer à l'export voudrait dire que le numéro a été écrit sur le disque,
    sauvegardé, et copié hors site.
    """
    magasin.record(Feedback(
        prompt="Mon numéro est 77 123 45 67 et mon mail awa@exemple.sn",
        response="Noté.", consent_to_train=True,
    ))

    conserve = magasin.list_feedback()[0].prompt

    assert "77 123 45 67" not in conserve
    assert "awa@exemple.sn" not in conserve
    assert "[téléphone]" in conserve and "[courriel]" in conserve


def test_le_nettoyage_ne_detruit_pas_le_texte_utile():
    """Un filtre trop large rendrait la correction inutilisable."""
    texte = scrub("Le mil se sème à l'arrivée des pluies, vers juin.")

    assert texte == "Le mil se sème à l'arrivée des pluies, vers juin."


def test_sans_consentement_le_retour_reste_hors_du_jeu(magasin):
    """Un retour appartient à qui l'a écrit (ADR-010)."""
    magasin.record(Feedback(prompt="q1", response="r1", consent_to_train=False))
    magasin.record(Feedback(prompt="q2", response="r2", consent_to_train=True))

    assert len(magasin.list_feedback()) == 2
    assert len(magasin.list_feedback(consent_only=True)) == 1


@pytest.fixture
def portillon():
    """Un moteur d'approbation réel, en mémoire."""
    from src.approval_engine.approval_manager import ApprovalManagerImpl
    return ApprovalManagerImpl()


def _approuver(magasin, portillon, par="responsable"):
    """Ouvre une demande sur le contenu courant et l'accorde. Retourne son id."""
    from src.training.feedback import request_export_approval
    demande = request_export_approval(magasin, requested_by=par, approvals=portillon)
    assert portillon.approve(demande.id, decided_by=par)
    return demande.id


def test_l_export_exige_une_approbation(magasin, portillon):
    """
    Sortir le texte de vraies personnes vers un jeu de données est une décision
    humaine (ADR-006), pas un effet de bord.
    """
    magasin.record(Feedback(
        prompt="q", response="mauvaise", correction="bonne", consent_to_train=True,
    ))

    with pytest.raises(PermissionError, match="approbation"):
        magasin.export_pairs()

    identifiant = _approuver(magasin, portillon)
    paires = magasin.export_pairs(identifiant, approvals=portillon)
    assert paires == [{"prompt": "q", "chosen": "bonne", "rejected": "mauvaise"}]


def test_un_retour_sans_deux_cotes_ne_fait_pas_une_paire(magasin, portillon):
    """Sans réponse rejetée, il n'y a pas de préférence — seulement une réponse."""
    magasin.record(Feedback(
        prompt="q", response="r", kind=FeedbackKind.RATING, rating=5, consent_to_train=True,
    ))

    identifiant = _approuver(magasin, portillon)
    assert magasin.export_pairs(identifiant, approvals=portillon) == []


class TestApprobationDuContenu:
    """
    L'approbation porte sur ce qui sort, pas sur le geste de sortir.

    Le défaut d'origine : `export_pairs("oui")` passait. L'identifiant n'était
    jamais vérifié, et même une vraie approbation n'aurait couvert qu'un acte —
    or le jeu grossit chaque jour.
    """

    def _remplir(self, magasin, combien, decalage=0):
        for index in range(combien):
            magasin.record(Feedback(
                prompt=f"q{index + decalage}", response="mauvaise",
                correction="bonne", consent_to_train=True,
            ))

    def test_une_chaine_inventee_n_est_pas_une_approbation(self, magasin, portillon):
        """Le cœur du constat n°3."""
        self._remplir(magasin, 1)
        with pytest.raises(PermissionError, match="n'existe"):
            magasin.export_pairs("oui", approvals=portillon)

    def test_une_demande_en_attente_n_est_pas_une_decision(self, magasin, portillon):
        from src.training.feedback import request_export_approval
        self._remplir(magasin, 1)
        demande = request_export_approval(magasin, "moi", approvals=portillon)
        with pytest.raises(PermissionError, match="pending"):
            magasin.export_pairs(demande.id, approvals=portillon)

    def test_une_demande_refusee_ne_laisse_rien_sortir(self, magasin, portillon):
        from src.training.feedback import request_export_approval
        self._remplir(magasin, 1)
        demande = request_export_approval(magasin, "moi", approvals=portillon)
        portillon.reject(demande.id, decided_by="responsable")
        with pytest.raises(PermissionError, match="rejected"):
            magasin.export_pairs(demande.id, approvals=portillon)

    def test_une_paire_ajoutee_apres_l_approbation_la_rend_caduque(
        self, magasin, portillon,
    ):
        """
        Douze paires approuvées n'en autorisent pas treize.

        C'est la moitié du constat que l'ancien code ne voyait pas : le jeu
        grossit, l'approbation ne suivait pas.
        """
        self._remplir(magasin, 12)
        identifiant = _approuver(magasin, portillon)
        self._remplir(magasin, 1, decalage=100)
        with pytest.raises(PermissionError, match="contenu a changé"):
            magasin.export_pairs(identifiant, approvals=portillon)

    def test_le_refus_dit_combien_avait_ete_approuve(self, magasin, portillon):
        """Un refus qu'on ne peut pas expliquer sera contourné."""
        self._remplir(magasin, 2)
        identifiant = _approuver(magasin, portillon)
        self._remplir(magasin, 5, decalage=100)
        with pytest.raises(PermissionError) as erreur:
            magasin.export_pairs(identifiant, approvals=portillon)
        assert "2 paire(s) approuvée(s)" in str(erreur.value)
        assert "7" in str(erreur.value)

    def test_un_texte_change_a_nombre_egal_est_detecte(self):
        """
        Compter les paires n'aurait pas suffi.

        Remplacer un retour par un autre laisse le compte identique et change
        entièrement ce qui sort. L'empreinte porte sur le texte.
        """
        from src.training.feedback import dataset_fingerprint
        avant = [{"prompt": "q", "chosen": "bonne", "rejected": "mauvaise"}]
        apres = [{"prompt": "tout autre chose", "chosen": "bonne",
                  "rejected": "mauvaise"}]
        assert len(avant) == len(apres)
        assert dataset_fingerprint(avant) != dataset_fingerprint(apres)

    def test_un_deplacement_de_texte_entre_champs_est_detecte(self):
        """
        Sans séparateur, « ab » + « c » et « a » + « bc » auraient la même
        empreinte. C'est le genre de collision qu'on ne voit qu'en la cherchant.
        """
        from src.training.feedback import dataset_fingerprint
        assert dataset_fingerprint([{"prompt": "ab", "chosen": "c", "rejected": ""}]) \
            != dataset_fingerprint([{"prompt": "a", "chosen": "bc", "rejected": ""}])

    def test_une_approbation_sans_empreinte_est_refusee(self, magasin, portillon):
        """
        Une demande ouverte à la main, sur l'acte, ne couvre aucun contenu.

        C'est exactement l'état d'avant : approuver « exporter » sans savoir
        quoi.
        """
        from src.approval_engine.types import ApprovalRequest
        self._remplir(magasin, 1)
        demande = ApprovalRequest(
            agent_id="training", request_id=None, action="training_dataset_export",
        )
        portillon.submit(demande)
        portillon.approve(demande.id, decided_by="responsable")
        with pytest.raises(PermissionError, match="empreinte"):
            magasin.export_pairs(demande.id, approvals=portillon)

    def test_sans_moteur_d_approbation_rien_ne_sort(self, magasin, monkeypatch):
        """
        L'absence de vérificateur n'accorde rien.

        C'est la règle d'ADR-018 reprise ici : une approbation n'est jamais
        accordée par l'absence de quelqu'un pour la refuser.
        """
        import src.training.feedback as module
        monkeypatch.setattr(module, "_portillon", lambda: None)
        self._remplir(magasin, 1)
        with pytest.raises(PermissionError, match="indisponible"):
            magasin.export_pairs("appr_quelconque")
        with pytest.raises(PermissionError, match="indisponible"):
            module.request_export_approval(magasin, "moi")

    def test_la_demande_nomme_son_demandeur(self, magasin, portillon):
        from src.training.feedback import CLE_NOMBRE, request_export_approval
        self._remplir(magasin, 3)
        demande = request_export_approval(magasin, "aminata", approvals=portillon)
        assert demande.metadata["requested_by"] == "aminata"
        assert demande.metadata[CLE_NOMBRE] == 3

    def test_une_demande_sans_demandeur_est_refusee(self, magasin, portillon):
        from src.training.feedback import request_export_approval
        with pytest.raises(PermissionError, match="demandeur"):
            request_export_approval(magasin, "   ", approvals=portillon)

    def test_la_demande_decrit_ce_qui_sort_pas_le_geste(self, magasin, portillon):
        """La file d'approbation est lue par un humain qui ne lira pas le code."""
        from src.training.feedback import request_export_approval
        self._remplir(magasin, 4)
        demande = request_export_approval(magasin, "moi", approvals=portillon)
        assert "4 paire(s)" in demande.description
        assert "vraies personnes" in demande.description

    def test_un_export_inchange_repasse(self, magasin, portillon):
        """La borne ferme un changement, elle ne ferme pas l'export."""
        self._remplir(magasin, 3)
        identifiant = _approuver(magasin, portillon)
        assert len(magasin.export_pairs(identifiant, approvals=portillon)) == 3
        # Deux fois : l'approbation n'est pas consommée par la première lecture.
        assert len(magasin.export_pairs(identifiant, approvals=portillon)) == 3


def test_le_compte_utile_est_distingue_du_total(magasin):
    """
    Un total qui mélange consentis et non consentis ferait croire à un jeu de
    données qui n'existe pas.
    """
    magasin.record(Feedback(prompt="a", response="b", consent_to_train=False))
    magasin.record(Feedback(prompt="c", response="d", consent_to_train=True))
    magasin.record(Feedback(
        prompt="e", response="f", correction="g", consent_to_train=True,
    ))

    etat = magasin.stats()

    assert etat["total"] == 3
    assert etat["with_consent"] == 2
    assert etat["trainable_pairs"] == 1


# ----------------------------------------------------------------------
# Mesurer avant d'entraîner
# ----------------------------------------------------------------------

def test_le_jeu_d_evaluation_du_depot_est_lisible():
    """Le jeu par défaut porte sur la documentation, vérifiable ligne à ligne."""
    cas = load_cases()

    assert len(cas) >= 10
    assert all(element.expected_source for element in cas)


def test_le_taux_de_recuperation_se_mesure_sans_jugement_humain():
    """
    La propriété qui rend cette mesure utilisable aujourd'hui : le passage
    attendu est retrouvé, ou il ne l'est pas. Aucun humain, aucun modèle.
    """
    cas = [
        EvalCase(question="q1", expected_source="a.md"),
        EvalCase(question="q2", expected_source="b.md"),
    ]

    resultat = evaluate_retrieval(
        lambda question: [{"location": "a.md"}] if question == "q1" else [{"location": "z.md"}],
        cases=cas, method="factice",
    )

    assert resultat.cases == 2
    assert resultat.hit_rate == 0.5
    assert resultat.misses[0]["expected"] == "b.md"


def test_un_jeu_vide_ne_vaut_pas_un_sans_faute():
    """Zéro sur zéro n'est pas 100 % — ce serait le pire des faux positifs."""
    assert evaluate_retrieval(lambda q: [], cases=[]).hit_rate == 0.0


def test_une_recherche_qui_leve_compte_comme_un_echec():
    """Une panne ne doit pas disparaître de la mesure."""
    resultat = evaluate_retrieval(
        lambda question: (_ for _ in ()).throw(RuntimeError("indisponible")),
        cases=[EvalCase(question="q", expected_source="a.md")],
    )

    assert resultat.hit_rate == 0.0
    assert "indisponible" in resultat.misses[0]["error"]


def test_une_regression_par_langue_annule_le_gain_global():
    """
    Un modèle qui progresse en français en régressant en wolof n'a pas progressé
    pour ce projet. Une moyenne le cacherait.
    """
    avant = EvalResult(cases=20, hits=10, by_language={
        "fr": {"cases": 10, "hits": 4}, "wo": {"cases": 10, "hits": 6},
    })
    apres = EvalResult(cases=20, hits=12, by_language={
        "fr": {"cases": 10, "hits": 9}, "wo": {"cases": 10, "hits": 3},
    })

    verdict = compare(avant, apres)

    assert verdict["delta"] > 0
    assert verdict["regressions"] == ["wo"]
    assert verdict["keep"] is False


def test_un_gain_sans_regression_est_gardable():
    """Le contre-test : la règle ne doit pas tout refuser."""
    avant = EvalResult(cases=10, hits=4, by_language={"fr": {"cases": 10, "hits": 4}})
    apres = EvalResult(cases=10, hits=7, by_language={"fr": {"cases": 10, "hits": 7}})

    assert compare(avant, apres)["keep"] is True


# ----------------------------------------------------------------------
# Lignée
# ----------------------------------------------------------------------

def test_une_version_est_inscrite_avec_sa_base_et_sa_licence(tmp_path):
    """Le jour où SamP dit une bêtise, la question sera « il a appris quoi ? »."""
    registre = LineageRegistry(str(tmp_path / "lineage.jsonl"))
    registre.record(ModelVersion(
        name="samp-1", family="samp", base_model="qwen2.5-7b",
        base_license="apache-2.0", data_hash="abc123",
        metrics={"hit_rate": 0.62}, kept=True,
    ))

    versions = registre.versions("samp")

    assert len(versions) == 1
    assert versions[0].base_model == "qwen2.5-7b"


def test_une_licence_non_permissive_empeche_la_publication(tmp_path):
    """
    ADR-014 écarte Llama parce que sa licence impose de porter « Llama » dans le
    nom. Ne pas noter la licence, c'est le découvrir le jour de la publication.
    """
    version = ModelVersion(
        name="samp-1", family="samp", base_model="llama-3-8b",
        base_license="llama-3-community", data_hash="abc", metrics={"hit_rate": 0.7},
    )

    problemes = version.issues()

    assert any("licence" in probleme for probleme in problemes)
    assert version.license_is_permissive() is False


def test_une_version_non_mesuree_est_signalee(tmp_path):
    """Un modèle non évalué ne peut pas être gardé pour une bonne raison."""
    version = ModelVersion(
        name="top-1", family="top", base_model="qwen2.5-coder-7b",
        base_license="apache-2.0", data_hash="def",
    )

    assert any("aucune mesure" in probleme for probleme in version.issues())


def test_un_entrainement_rate_reste_au_journal(tmp_path):
    """
    Un journal qui ne contient que des succès n'est pas un journal : l'essai
    raté serait refait.
    """
    registre = LineageRegistry(str(tmp_path / "lineage.jsonl"))
    registre.record(ModelVersion(
        name="samp-0", family="samp", base_model="qwen2.5-7b",
        base_license="apache-2.0", data_hash="a", metrics={"hit_rate": 0.3},
        kept=False, notes="pire que la base",
    ))
    registre.record(ModelVersion(
        name="samp-1", family="samp", base_model="qwen2.5-7b",
        base_license="apache-2.0", data_hash="b", metrics={"hit_rate": 0.62}, kept=True,
    ))

    assert len(registre.versions("samp")) == 2
    # Mais la version courante est la dernière **gardée**, jamais la dernière écrite.
    assert registre.latest("samp").name == "samp-1"


def test_sans_version_gardee_il_n_y_a_pas_de_version_courante(tmp_path):
    """Rendre un modèle rejeté comme courant serait le servir par accident."""
    registre = LineageRegistry(str(tmp_path / "lineage.jsonl"))
    registre.record(ModelVersion(
        name="samp-0", family="samp", base_model="q", base_license="apache-2.0",
        metrics={"hit_rate": 0.1}, kept=False,
    ))

    assert registre.latest("samp") is None


def test_mesurer_ne_deplace_pas_ce_qu_on_mesure(monkeypatch):
    """
    Chercher incrémente le compteur de consultations, qui alimente le critère de
    popularité du classement : une même base mesurée deux fois ne rendait pas le
    même score. Constaté sur le corpus du dépôt — 0,4 sur une base neuve, 0,5
    après quelques passages, sans qu'une ligne de code ait changé.

    Un barème qui dérive à l'usage ne peut arbitrer aucun entraînement.
    """
    from src.knowledge_engine.knowledge_manager import TRACK_ACCESS_VARIABLE

    monkeypatch.setenv(TRACK_ACCESS_VARIABLE, "true")
    vu = []

    def rechercher(question):
        vu.append(os.environ.get(TRACK_ACCESS_VARIABLE))
        return [{"location": "a.md"}]

    evaluate_retrieval(rechercher, cases=[EvalCase(question="q", expected_source="a.md")])

    assert vu == ["false"], "Le compteur doit être coupé pendant la mesure"
    # Et l'environnement est rendu tel qu'il était : une mesure ne reconfigure
    # pas la plateforme derrière elle.
    assert os.environ[TRACK_ACCESS_VARIABLE] == "true"


class TestScriptDEntrainement:
    """
    Le même trou existait dans `scripts/training/train_adapter.py`.

    Il refusait un identifiant vide et acceptait n'importe quel fichier de
    paires avec n'importe quel identifiant non vide. Les chemins éprouvés ici
    sont ceux qui s'exécutent **avant** l'import de PyTorch — le reste demande
    un GPU que cette machine n'a pas.
    """

    def _script(self):
        import importlib.util
        import pathlib
        chemin = pathlib.Path(__file__).parent.parent / "scripts" / "training" / "train_adapter.py"
        spec = importlib.util.spec_from_file_location("train_adapter", chemin)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _options(self, **champs):
        import types
        base = {"famille": "samp", "base": "b", "licence": "apache-2.0",
                "paires": "", "nom": "n", "sortie": "s", "approbation": "",
                "empreinte": ""}
        base.update(champs)
        return types.SimpleNamespace(**base)

    def _ecrire(self, tmp_path, paires):
        import json
        chemin = tmp_path / "pairs.jsonl"
        chemin.write_text(
            "\n".join(json.dumps(paire, ensure_ascii=False) for paire in paires),
            encoding="utf-8",
        )
        return str(chemin)

    def test_sans_approbation_le_script_refuse(self):
        script = self._script()
        assert script.entrainer(self._options()) == 2

    def test_sans_empreinte_le_script_refuse(self, tmp_path):
        """Le cœur du constat n°3, côté script."""
        script = self._script()
        fichier = self._ecrire(tmp_path, [
            {"prompt": "q", "chosen": "b", "rejected": "m"}])
        code = script.entrainer(
            self._options(approbation="appr_x", paires=fichier))
        assert code == 2

    def test_une_empreinte_qui_ne_correspond_pas_refuse(self, tmp_path):
        script = self._script()
        fichier = self._ecrire(tmp_path, [
            {"prompt": "q", "chosen": "b", "rejected": "m"}])
        code = script.entrainer(self._options(
            approbation="appr_x", paires=fichier, empreinte="0" * 64))
        assert code == 2

    def test_l_empreinte_du_fichier_est_celle_de_l_export(self, tmp_path):
        """
        Une seconde implémentation aurait dérivé de la première.

        Le script réutilise `dataset_fingerprint` ; ce test le prouve plutôt que
        de le supposer.
        """
        from src.training.feedback import dataset_fingerprint
        script = self._script()
        paires = [{"prompt": "q", "chosen": "b", "rejected": "m"},
                  {"prompt": "q2", "chosen": "b2", "rejected": "m2"}]
        fichier = self._ecrire(tmp_path, paires)
        assert script.empreinte_du_fichier(fichier) == dataset_fingerprint(paires)

    def test_une_empreinte_juste_laisse_passer_jusqu_a_l_environnement(
        self, tmp_path,
    ):
        """
        La borne ferme un contenu, elle ne ferme pas l'entraînement.

        Le code 1 est celui de « PyTorch absent ici » : la vérification de
        contenu a donc été franchie, et c'est tout ce que ce test affirme.
        """
        from src.training.feedback import dataset_fingerprint
        script = self._script()
        paires = [{"prompt": "q", "chosen": "b", "rejected": "m"}]
        fichier = self._ecrire(tmp_path, paires)
        code = script.entrainer(self._options(
            approbation="appr_x", paires=fichier,
            empreinte=dataset_fingerprint(paires)))
        assert code == 1
