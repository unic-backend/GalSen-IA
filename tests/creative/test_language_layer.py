"""
Tests for the multilingual layer (C13, §24–§26) and language knowledge (C14, §27–§33).

Four properties carry the weight of these two volets, and each one exists
because breaking it is easy and silent.

**A language is data, not code.** Adding Bambara must not be a commit. The
registry is loaded from `corpus/creative/languages.yaml`, and the tests here
build their own file to prove the loader — not the repository's data — is what
enforces the rules.

**Declared is not supported.** Nineteen rows in a YAML file must never read as
nineteen languages understood. `language_matrix` keeps five separate columns
for exactly that reason, and `speakable` is empty everywhere.

**Frequency stops at CORROBORATED.** No number of observations produces
`VALIDATED`. This is tested with an absurd count on purpose: if a threshold is
ever added above the ceiling, this test is what fails.

**Private never leaks.** The default read excludes the private space, and the
only path out of it is `publish()` with a named consenter and a written consent.
"""

import pytest

from src.creative.language.knowledge import (
    KnowledgeRefused,
    LanguageKnowledgeBase,
    merge_correction,
)
from src.creative.language.loop import (
    CONDITIONS_ENTRAINEMENT,
    LoopRefused,
    clarification_question,
    loop_report,
    observe_from_interaction,
    pending_validation,
    training_status,
)
from src.creative.language.observation import (
    CANDIDAT,
    CORROBORE,
    GLOBAL,
    OBSERVE,
    OFFICIEL,
    PRIVE,
    VALIDE,
    ObservationRefused,
    corroborate,
    ladder_report,
    mark_official,
    new_observation,
    promote_by_frequency,
    validate,
)
from src.creative.language.registry import (
    LanguageRegistryError,
    coverage_report,
    is_declared,
    known_codes,
    language_matrix,
    language_record,
    load_registry,
)
from src.creative.language.switching import (
    detect_switches,
    language_spans,
    switching_report,
)
from src.creative.voice.scene import AudioSegment, VoiceSceneRefused


def _segment(**champs):
    """Un segment minimal, audio d'origine compris."""
    base = {"segment_id": "s", "start": 0.0, "end": 1.0,
            "original_audio_path": "/tmp/a.wav"}
    base.update(champs)
    return AudioSegment(**base)


def _registre(tmp_path, contenu):
    """Écrit un registre de test et rend son chemin."""
    chemin = tmp_path / "languages.yaml"
    chemin.write_text(contenu, encoding="utf-8")
    return str(chemin)


# --------------------------------------------------------------------------
# C13 phase 13.1 — le registre
# --------------------------------------------------------------------------


class TestRegistre:
    """Nommer une langue est une donnée, et le registre refuse ce qu'il ne peut pas croire."""

    def test_les_langues_du_depot_se_chargent(self):
        codes = known_codes()
        assert "wo" in codes and "srr" in codes and "ln" in codes

    def test_une_langue_porte_son_sens_d_ecriture(self):
        assert language_record("ar").direction == "rtl"
        assert language_record("wo").direction == "ltr"

    def test_le_wolof_porte_sa_norme_orthographique(self):
        # `ë ñ ŋ` sont des lettres CLAD, pas des accents : la norme est nommée.
        assert language_record("wo").orthography == "CLAD"

    def test_un_code_inconnu_n_est_pas_devine(self):
        with pytest.raises(LanguageRegistryError) as erreur:
            language_record("klingon")
        assert "languages.yaml" in str(erreur.value)
        assert is_declared("klingon") is False

    def test_le_serere_declare_son_registre_iso_3(self):
        # Le sérère n'a pas de code à deux lettres. C'est le registre ISO qui
        # est incomplet, pas la langue qui est mineure.
        assert language_record("srr").register == "iso-639-3"

    def test_ajouter_une_langue_ne_touche_aucun_code(self, tmp_path):
        chemin = _registre(tmp_path, """
languages:
  - code: xyz
    register: iso-639-3
    name: inventée
    direction: ltr
validation_languages: [xyz]
""")
        registre, validation = load_registry(chemin)
        assert list(registre) == ["xyz"]
        assert validation == ("xyz",)

    def test_un_code_duplique_est_refuse(self, tmp_path):
        chemin = _registre(tmp_path, """
languages:
  - {code: wo, register: iso-639-1, name: wolof, direction: ltr}
  - {code: wo, register: iso-639-1, name: autre, direction: rtl}
""")
        with pytest.raises(LanguageRegistryError) as erreur:
            load_registry(chemin)
        assert "deux fois" in str(erreur.value)

    def test_un_sens_d_ecriture_invente_est_refuse(self, tmp_path):
        chemin = _registre(tmp_path, """
languages:
  - {code: wo, register: iso-639-1, name: wolof, direction: diagonal}
""")
        with pytest.raises(LanguageRegistryError) as erreur:
            load_registry(chemin)
        assert "l'envers" in str(erreur.value)

    def test_une_langue_de_validation_absente_est_refusee(self, tmp_path):
        """§64 nomme des scénarios ; déclarés et absents, ils seraient muets."""
        chemin = _registre(tmp_path, """
languages:
  - {code: wo, register: iso-639-1, name: wolof, direction: ltr}
validation_languages: [wo, srr]
""")
        with pytest.raises(LanguageRegistryError) as erreur:
            load_registry(chemin)
        assert "srr" in str(erreur.value)

    def test_un_registre_vide_est_refuse(self, tmp_path):
        with pytest.raises(LanguageRegistryError):
            load_registry(_registre(tmp_path, "languages: []\n"))

    def test_un_registre_absent_est_refuse(self, tmp_path):
        with pytest.raises(LanguageRegistryError) as erreur:
            load_registry(str(tmp_path / "nulle-part.yaml"))
        assert "introuvable" in str(erreur.value)


class TestDeclareeNEstPasSupportee:
    """La confusion la moins chère à écrire, et celle qui coûte le plus."""

    def test_aucune_langue_n_est_parlable(self):
        # Pas une dépendance absente : aucun module de synthèse n'existe ici.
        matrice = language_matrix()
        assert matrice["speakable"] == []
        assert all(entree["speakable"] is False
                   for entree in matrice["languages"])

    def test_la_raison_de_l_absence_de_voix_est_donnee(self):
        matrice = language_matrix()
        raison = matrice["languages"][0]["speaking_reason"]
        assert "n'a pas été écrit" in raison and "§26" in raison

    def test_les_cinq_capacites_restent_separees(self):
        entree = language_matrix()["languages"][0]
        assert {"nameable", "documentable", "subtitleable", "understood",
                "speakable"} <= set(entree)

    def test_nommable_partout_mais_pas_le_reste(self):
        """C'est l'écart que C13 rend visible, pas celui qu'il comble."""
        rapport = coverage_report()
        assert rapport["count"] == 15
        assert rapport["partially_carried"], (
            "Toutes les langues de validation seraient pleinement portées : "
            "c'est faux, et le prétendre annoncerait 15 langues supportées."
        )
        for ligne in rapport["validation_languages"]:
            assert ligne["nameable"] is True

    def test_une_lacune_dit_ce_qui_manque(self):
        rapport = coverage_report()
        partielles = [ligne for ligne in rapport["validation_languages"]
                      if ligne["gaps"]]
        assert all(ligne["gaps"] for ligne in partielles)
        assert any("sous-titre" in " ".join(ligne["gaps"])
                   for ligne in partielles)


# --------------------------------------------------------------------------
# C13 phase 13.2 — l'alternance codique
# --------------------------------------------------------------------------


class TestAlternanceCodique:
    """Un enregistrement n'a pas de langue ; ses segments en ont une."""

    def _conversation(self):
        return [
            _segment(segment_id="s1", start=0.0, end=2.0, language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
            _segment(segment_id="s2", start=2.0, end=3.0, language="fr",
                     language_confidence=0.9, speaker_id="sp1"),
            _segment(segment_id="s3", start=3.0, end=5.0, language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
        ]

    def test_les_plages_suivent_les_langues(self):
        plages = language_spans(self._conversation())
        assert [p.language for p in plages] == ["wo", "fr", "wo"]
        assert plages[1].duration == 1.0

    def test_une_bascule_chez_le_meme_locuteur_est_de_l_alternance(self):
        bascules = detect_switches(self._conversation())
        assert len(bascules) == 2
        assert all(b.same_speaker for b in bascules)

    def test_deux_locuteurs_de_langues_differentes_ne_sont_pas_une_alternance(self):
        bascules = detect_switches([
            _segment(segment_id="a", start=0.0, end=1.0, language="wo",
                     language_confidence=0.9, speaker_id="sp1"),
            _segment(segment_id="b", start=1.0, end=2.0, language="fr",
                     language_confidence=0.9, speaker_id="sp2"),
        ])
        assert bascules[0].same_speaker is False

    def test_une_bascule_peu_sure_est_marquee_supposee(self):
        rapport = switching_report([
            _segment(segment_id="a", start=0.0, end=1.0, language="wo",
                     language_confidence=0.9),
            _segment(segment_id="b", start=1.0, end=2.0, language="fr",
                     language_confidence=0.3),
        ])
        assert rapport["assumed_switches"], (
            "Une bascule fondée sur une langue identifiée à 0,3 est supposée."
        )

    def test_un_segment_sans_langue_forme_sa_propre_plage(self):
        """Le fondre dans la plage voisine étendrait une langue à de la parole
        que personne n'a identifiée."""
        plages = language_spans([
            _segment(segment_id="a", start=0.0, end=1.0, language="wo",
                     language_confidence=0.9),
            _segment(segment_id="b", start=1.0, end=2.0),
        ])
        assert [p.language for p in plages] == ["wo", None]

    def test_une_plage_n_est_pas_plus_sure_que_son_maillon_le_plus_faible(self):
        plages = language_spans([
            _segment(segment_id="a", start=0.0, end=1.0, language="wo",
                     language_confidence=0.95),
            _segment(segment_id="b", start=1.0, end=2.0, language="wo",
                     language_confidence=0.42),
        ])
        assert plages[0].lowest_confidence == 0.42

    def test_l_alternance_intra_segment_reste_inconnue(self):
        """La détecter demanderait une transcription, indisponible ici."""
        rapport = switching_report(self._conversation())
        assert rapport["intra_segment_switching"] == "UNKNOWN"
        assert "transcription" in rapport["intra_segment_reason"]

    def test_aucune_langue_dominante_n_est_calculee(self):
        """§25 refuse la réduction ; la calculer inviterait à s'en servir."""
        rapport = switching_report(self._conversation())
        assert "dominant_language" not in rapport
        assert "file_language" not in rapport

    def test_le_silence_n_a_pas_d_alternance(self):
        with pytest.raises(VoiceSceneRefused):
            switching_report([])


class TestChampsDeSegment:
    """§25 : dialecte, région et prononciation vivent au segment."""

    def test_le_dialecte_distingue_pulaar_et_fulfulde(self):
        # ISO 639-1 n'a que `ff` ; la distinction que §24 nomme vit ici.
        segment = _segment(language="ff", dialect="pulaar", region="Fouta")
        assert segment.as_dict()["dialect"] == "pulaar"
        assert segment.as_dict()["region"] == "Fouta"

    def test_un_dialecte_sans_langue_est_refuse(self):
        with pytest.raises(VoiceSceneRefused) as erreur:
            _segment(dialect="pulaar")
        assert "ne désigne rien" in str(erreur.value)

    def test_la_prononciation_est_une_note_pas_une_norme(self):
        segment = _segment(language="wo", pronunciation="dëkk, ë long")
        assert segment.as_dict()["pronunciation"] == "dëkk, ë long"


# --------------------------------------------------------------------------
# C14 phase 14.1 — l'échelle de validation
# --------------------------------------------------------------------------


class TestEchelle:
    """La fréquence monte jusqu'à CORROBORATED et s'arrête là."""

    def _observation(self, **champs):
        return new_observation("wo", "dëkk", by="awa", meaning="habiter",
                               **champs)

    def test_une_observation_commence_au_premier_echelon(self):
        observation = self._observation()
        assert observation.status == OBSERVE
        assert observation.privacy == PRIVE
        assert observation.observed_count == 1

    def test_la_repetition_monte_jusqu_a_corrobore(self):
        observation = self._observation()
        for observateur in ("moussa", "fatou", "ibou"):
            observation = corroborate(observation, by=observateur)
        assert observation.status == CORROBORE

    def test_aucun_compte_ne_produit_valide(self):
        """L'invariant d'ADR-027 point 6, éprouvé au-delà du raisonnable.

        Si un seuil est un jour ajouté au-dessus du plafond, c'est ce test qui
        tombe — et c'est exactement son rôle.
        """
        for compte in (1, 2, 4, 10, 100, 10_000, 1_000_000):
            assert promote_by_frequency(compte) in (OBSERVE, CANDIDAT, CORROBORE)
            assert promote_by_frequency(compte) != VALIDE
            assert promote_by_frequency(compte) != OFFICIEL

    def test_mille_observations_d_une_erreur_restent_une_erreur(self):
        observation = self._observation()
        for numero in range(1000):
            observation = corroborate(observation, by=f"locuteur-{numero}")
        assert observation.observed_count == 1001
        assert observation.status == CORROBORE

    def test_valider_exige_un_humain_nomme(self):
        with pytest.raises(ObservationRefused) as erreur:
            validate(self._observation(), by="")
        assert "humain nommé" in str(erreur.value)

    def test_la_plateforme_ne_se_valide_pas_elle_meme(self):
        for identite in ("galsen", "system", "bot", "agent", "GalSen-IA"):
            with pytest.raises(ObservationRefused) as erreur:
                validate(self._observation(), by=identite)
            assert "est la plateforme" in str(erreur.value)

    def test_une_validation_porte_le_nom_de_qui_valide(self):
        valide = validate(self._observation(), by="Awa Diop",
                          meaning="habiter / résider")
        assert valide.status == VALIDE
        assert valide.validated_by == "Awa Diop"
        assert valide.meaning == "habiter / résider"
        assert valide.history[-1].action == "validated"

    def test_officiel_exige_une_autorite_exterieure(self):
        valide = validate(self._observation(), by="Awa Diop")
        with pytest.raises(ObservationRefused) as erreur:
            mark_official(valide, authority="galsen", reference="décret")
        assert "est la plateforme" in str(erreur.value)

    def test_officiel_exige_une_reference_a_relire(self):
        valide = validate(self._observation(), by="Awa Diop")
        with pytest.raises(ObservationRefused) as erreur:
            mark_official(valide, authority="CLAD", reference="")
        assert "invérifiable" in str(erreur.value)

    def test_une_entree_validee_n_est_pas_retrogradee_par_la_frequence(self):
        valide = validate(self._observation(), by="Awa Diop")
        renforcee = corroborate(valide, by="moussa")
        assert renforcee.status == VALIDE
        assert renforcee.observed_count == 2

    def test_une_observation_sans_observateur_est_refusee(self):
        with pytest.raises(ObservationRefused) as erreur:
            new_observation("wo", "dëkk", by="  ")
        assert "sans observateur" in str(erreur.value)

    def test_une_langue_non_declaree_est_refusee(self):
        with pytest.raises(ObservationRefused) as erreur:
            new_observation("klingon", "nuqneH", by="awa")
        assert "non déclarée" in str(erreur.value)

    def test_l_echelle_est_lisible_sans_lire_le_code(self):
        rapport = ladder_report()
        assert VALIDE not in rapport["reachable_by_frequency"]
        assert rapport["requires_named_human"] == [VALIDE]
        assert rapport["requires_external_authority"] == [OFFICIEL]


# --------------------------------------------------------------------------
# C14 phase 14.2 — la base et sa frontière
# --------------------------------------------------------------------------


class TestFrontierePriveGlobal:
    """§58 : un seul passage, et il se décide."""

    def _base(self):
        base = LanguageKnowledgeBase()
        observation = observe_from_interaction(
            base, "wo", "dëkk", by="awa", meaning="habiter")
        return base, observation

    def test_une_interaction_reste_privee(self):
        _, observation = self._base()
        assert observation.privacy == PRIVE

    def test_la_lecture_ordinaire_ne_voit_pas_le_prive(self):
        base, _ = self._base()
        assert base.hypotheses("wo", "dëkk") == []
        assert len(base.hypotheses("wo", "dëkk", include_private=True)) == 1

    def test_publier_exige_un_consentant_nomme(self):
        base, observation = self._base()
        with pytest.raises(KnowledgeRefused) as erreur:
            base.publish(observation.observation_id, by="", consent="oui")
        assert "sans consentant" in str(erreur.value)

    def test_la_plateforme_ne_consent_pour_personne(self):
        base, observation = self._base()
        with pytest.raises(KnowledgeRefused) as erreur:
            base.publish(observation.observation_id, by="system", consent="oui")
        assert "est la plateforme" in str(erreur.value)

    def test_publier_exige_un_consentement_qui_se_relit(self):
        base, observation = self._base()
        with pytest.raises(KnowledgeRefused) as erreur:
            base.publish(observation.observation_id, by="Awa", consent="   ")
        assert "ne se relit pas" in str(erreur.value)

    def test_le_consentement_reste_dans_l_histoire(self):
        base, observation = self._base()
        publiee = base.publish(observation.observation_id, by="Awa Diop",
                               consent="accepte l'entrée dans la base globale")
        assert publiee.privacy == GLOBAL
        assert publiee.history[-1].action == "published"
        assert "globale" in publiee.history[-1].detail

    def test_rien_ne_remonte_le_prive_tout_seul(self):
        """Ni la fréquence, ni la validation ne publient."""
        base, observation = self._base()
        for observateur in ("moussa", "fatou", "ibou"):
            observe_from_interaction(base, "wo", "dëkk", by=observateur,
                                     meaning="habiter")
        courante = base.get(observation.observation_id)
        assert courante.status == CORROBORE
        assert courante.privacy == PRIVE
        assert base.hypotheses("wo", "dëkk") == []


class TestHypothesesConcurrentes:
    """§32 : le contexte est une preuve, pas un arbitre."""

    def test_deux_sens_coexistent(self):
        base = LanguageKnowledgeBase()
        observe_from_interaction(base, "wo", "dëkk", by="awa",
                                 meaning="habiter")
        observe_from_interaction(base, "wo", "dëkk", by="ndeye",
                                 meaning="village")
        assert len(base.hypotheses("wo", "dëkk", include_private=True)) == 2

    def test_le_meme_sens_corrobore_au_lieu_de_dupliquer(self):
        base = LanguageKnowledgeBase()
        premiere = observe_from_interaction(base, "wo", "dëkk", by="awa",
                                            meaning="habiter")
        observe_from_interaction(base, "wo", "dëkk", by="moussa",
                                 meaning="habiter")
        assert len(base.hypotheses("wo", "dëkk", include_private=True)) == 1
        assert base.get(premiere.observation_id).observed_count == 2

    def test_une_correction_est_une_observation_pas_un_ecrasement(self):
        """ADR-027 point 7 : sinon la dernière personne à parler fait autorité."""
        base = LanguageKnowledgeBase()
        origine = observe_from_interaction(base, "wo", "dëkk", by="awa",
                                           meaning="habiter")
        correction = merge_correction(base, origine.observation_id,
                                      by="ndeye", meaning="village")
        assert correction.observation_id != origine.observation_id
        assert base.get(origine.observation_id).meaning == "habiter"
        assert correction.status == OBSERVE
        assert "corrige" in correction.history[-1].detail

    def test_le_rapport_signale_les_expressions_disputees(self):
        base = LanguageKnowledgeBase()
        observe_from_interaction(base, "wo", "dëkk", by="awa",
                                 meaning="habiter")
        observe_from_interaction(base, "wo", "dëkk", by="ndeye",
                                 meaning="village")
        assert "wo:dëkk" in base.report()["competing_hypotheses"]

    def test_l_histoire_ne_se_reecrit_pas(self):
        base = LanguageKnowledgeBase()
        observation = observe_from_interaction(base, "wo", "dëkk", by="awa",
                                               meaning="habiter")
        autre = new_observation("wo", "autre", by="moussa", meaning="autre",
                                observation_id=observation.observation_id)
        with pytest.raises(KnowledgeRefused) as erreur:
            base.add(autre)
        assert "auditable" in str(erreur.value)


# --------------------------------------------------------------------------
# C14 phase 14.3 — la boucle, et ce qu'elle n'est pas
# --------------------------------------------------------------------------


class TestBoucle:
    """§31 : une seule étape ne s'automatise pas, et c'est la bonne."""

    def test_la_question_porte_toutes_les_hypotheses(self):
        base = LanguageKnowledgeBase()
        observe_from_interaction(base, "wo", "dëkk", by="awa",
                                 meaning="habiter")
        observe_from_interaction(base, "wo", "dëkk", by="ndeye",
                                 meaning="village")
        question = clarification_question(
            base.hypotheses("wo", "dëkk", include_private=True))
        assert question["ask"] is True
        assert "habiter" in question["question"]
        assert "village" in question["question"]

    def test_une_seule_hypothese_ne_se_demande_pas(self):
        """Proposer un sens unique fait acquiescer."""
        observation = new_observation("wo", "dëkk", by="awa",
                                      meaning="habiter")
        question = clarification_question([observation])
        assert question["ask"] is False
        assert "acquiescer" in question["reason"]

    def test_sans_expression_il_n_y_a_rien_a_demander(self):
        with pytest.raises(LoopRefused):
            clarification_question([])

    def test_la_file_de_validation_dit_sur_quoi_elle_bute(self):
        base = LanguageKnowledgeBase()
        for observateur in ("awa", "moussa", "fatou", "ibou"):
            observe_from_interaction(base, "wo", "dëkk", by=observateur,
                                     meaning="habiter")
        attente = pending_validation(base)
        assert len(attente) == 1
        assert "humain nommé" in attente[0]["blocked_on"]

    def test_la_validation_est_la_seule_etape_manuelle(self):
        base = LanguageKnowledgeBase()
        rapport = loop_report(base)
        assert rapport["manual_stages"] == ["human validation"]
        assert "human validation" not in rapport["automatic_stages"]


class TestAucunEntrainement:
    """§27, §31, §45 : la colonne de droite n'a pas lieu, et c'est vérifiable."""

    def test_rien_n_est_entraine_sur_les_conversations(self):
        etat = training_status()
        assert etat["trains_on_conversations"] is False
        assert etat["weights_modified"] is False
        assert etat["model_training"] == "NONE"

    def test_les_sept_conditions_de_la_directive_sont_nommees(self):
        etat = training_status()
        nommees = {c["condition"] for c in etat["conditions_for_future_training"]}
        assert nommees == set(CONDITIONS_ENTRAINEMENT)
        assert all(c["state"] == "NOT_MET"
                   for c in etat["conditions_for_future_training"])

    def test_la_difference_entre_les_deux_actes_est_ecrite(self):
        difference = training_status()["difference"]
        assert "auditable" in difference["KNOWLEDGE_ACQUISITION"]
        assert "irréversible" in difference["MODEL_TRAINING"]
