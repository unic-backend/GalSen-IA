"""
Tests for the creative representation (§5) and the voice scene (§21–§26, §33).

Two properties carry the weight. A field the user did not state can never
become indistinguishable from one they did — which is what makes a delivery
arguable months later. And a recording is never replaced by default: for the
languages this platform starts from, the speaker's own voice is the best
available answer, not a fallback.
"""

import pytest

from src.creative.reference.consent import ConsentScope
from src.creative.reference.entity import ReferenceEntity
from src.creative.representation import (
    CHAMPS_REQUIS,
    CLARIFICATION_REQUISE,
    DEDUIT,
    NON_PRECISE,
    PRETE,
    CreativeRepresentation,
    EntityRef,
    Field,
    RepresentationRefused,
    from_request,
    representation_report,
)
from src.creative.voice.scene import (
    CONFIANCE_FAIBLE,
    CONNU,
    INCONNU,
    AudioSegment,
    VoiceSceneRefused,
    build_scene,
    language_capabilities,
    original_audio_exists,
    pipeline_state,
    voice_plan,
    voice_scene_report,
)


# --------------------------------------------------------------------------
# La représentation créative
# --------------------------------------------------------------------------


def test_une_intention_vide_est_refusee():
    with pytest.raises(RepresentationRefused) as erreur:
        CreativeRepresentation(intent="   ")
    assert "ni planifiée ni jugée" in str(erreur.value)


def test_un_champ_non_precise_porte_une_question_pas_une_valeur():
    representation = CreativeRepresentation(intent="Fais quelque chose")
    champ = representation.field("duration_seconds")
    assert champ.provenance == NON_PRECISE
    assert champ.value is None
    assert champ.question


def test_un_champ_non_precise_sans_question_est_refuse():
    with pytest.raises(RepresentationRefused) as erreur:
        Field(name="duration_seconds")
    # Un manque sans question se remplit tout seul.
    assert "par un défaut que personne n'a choisi" in str(erreur.value)


def test_une_valeur_qui_se_dit_non_precisee_est_refusee():
    with pytest.raises(RepresentationRefused) as erreur:
        Field(name="aspect", value="9:16", provenance=NON_PRECISE,
              question="?")
    assert "L'un des deux est faux" in str(erreur.value)


def test_une_deduction_anonyme_est_refusee():
    with pytest.raises(RepresentationRefused) as erreur:
        Field(name="aspect", value="9:16", provenance=DEDUIT)
    assert "indiscernable d'une demande" in str(erreur.value)


def test_ce_qui_est_demande_reste_distinct_de_ce_qui_est_deduit():
    representation = CreativeRepresentation(intent="Un documentaire")
    representation.state("domain", "documentary")
    representation.infer("aspect", "16:9", source="règle de plateforme")

    resume = representation.as_dict()
    assert resume["stated"] == ["domain"]
    assert resume["inferred"] == ["aspect"]
    # C'est cette différence qui permet d'arbitrer une livraison.
    assert "duration_seconds" in resume["unspecified"]


def test_une_representation_avec_des_questions_n_est_pas_executable():
    representation = CreativeRepresentation(intent="Rends ça joli")
    etat = representation.ready()
    assert etat["status"] == CLARIFICATION_REQUISE
    assert {q["field"] for q in etat["clarifications"]} == set(CHAMPS_REQUIS)


def test_une_representation_complete_est_executable():
    representation = CreativeRepresentation(intent="Un documentaire")
    for nom, valeur in (("domain", "documentary"), ("duration_seconds", 120.0),
                        ("aspect", "9:16")):
        representation.state(nom, valeur)
    assert representation.ready()["status"] == PRETE


def test_l_analyse_du_langage_vient_du_module_existant():
    representation = from_request(
        "Fais-moi un documentaire vertical de 2 minutes en wolof.")
    assert representation.ready()["status"] == PRETE
    assert representation.field("domain").value == "documentary"
    assert representation.field("duration_seconds").value == 120.0
    assert representation.field("aspect").value == "9:16"
    # La source nomme le module : un second analyseur divergerait du premier.
    assert "intent.py" in representation.field("domain").source


def test_une_demande_incomplete_reste_incomplete():
    representation = from_request("Rends cette vidéo plus jolie.")
    assert representation.ready()["status"] == CLARIFICATION_REQUISE


def test_une_reference_sans_consentement_n_est_pas_rattachee():
    representation = CreativeRepresentation(intent="Un documentaire")
    reference = ReferenceEntity(entity_type="human")
    verdict = representation.attach_reference(reference, "project:demo")
    assert verdict["allowed"] is False
    assert representation.references == ()


def test_une_reference_consentie_est_rattachee():
    representation = CreativeRepresentation(intent="Un documentaire")
    reference = ReferenceEntity(entity_type="human")
    reference.grant(ConsentScope(granted_by="Awa Ndiaye", subject="Awa Ndiaye",
                                 permitted_uses=("project:demo",)))
    assert representation.attach_reference(
        reference, "project:demo")["allowed"] is True
    assert len(representation.references) == 1


def test_un_objet_incapable_de_repondre_sur_son_consentement_est_refuse():
    representation = CreativeRepresentation(intent="Un documentaire")
    with pytest.raises(RepresentationRefused) as erreur:
        representation.attach_reference(object(), "project:demo")
    assert "impossible de vérifier" in str(erreur.value)


def test_une_entite_declare_sa_fidelite():
    representation = CreativeRepresentation(intent="Une scène de rue")
    representation.add_entity(EntityRef(entity_id="e1", entity_type="human",
                                        fidelity="HERO"))
    representation.add_entity(EntityRef(entity_id="e2", entity_type="vehicle",
                                        fidelity="BACKGROUND"))
    assert [e.fidelity for e in representation.entities] == ["HERO",
                                                             "BACKGROUND"]


def test_le_rapport_de_representation_nomme_ce_qu_il_refuse():
    refus = " ".join(representation_report()["does_not"]).lower()
    assert "à la place du demandeur" in refus
    assert "réimplémenter" in refus


# --------------------------------------------------------------------------
# La scène vocale
# --------------------------------------------------------------------------


def _segment(**kwargs):
    """Un segment valide, réglable."""
    defauts = dict(segment_id="s1", start=0.0, end=2.0,
                   original_audio_path="/tmp/enregistrement.wav")
    defauts.update(kwargs)
    return AudioSegment(**defauts)


def test_un_segment_sans_audio_d_origine_est_refuse():
    with pytest.raises(VoiceSceneRefused) as erreur:
        _segment(original_audio_path="")
    # La garantie de §22 tient à ce que le fichier existe encore à la fin.
    assert "§22" in str(erreur.value)


def test_une_transcription_non_mesuree_est_refusee():
    with pytest.raises(VoiceSceneRefused) as erreur:
        _segment(transcript="bonjour", transcript_source="ABSENT")
    assert "dans la bouche de quelqu'un" in str(erreur.value)


def test_une_langue_non_declaree_est_refusee():
    """Un code que le registre ne porte pas reste refusé.

    Ce test utilisait `es` jusqu'à C13. L'espagnol est désormais **déclaré**
    (`corpus/creative/languages.yaml`, §24), et le fixer ici ferait échouer le
    test pour la raison inverse de celle qu'il vérifie. L'assertion n'est pas
    affaiblie : un code inconnu est toujours refusé, avec le même message.
    """
    with pytest.raises(VoiceSceneRefused) as erreur:
        _segment(language="zz")
    assert "l'envers" in str(erreur.value)


def test_les_langues_des_tests_d_or_sont_exprimables():
    """Sérère et lingala sont les tests d'or 5 et 6 de §63.

    Avant C13 la couche vocale validait contre les quatre langues du moteur de
    sous-titres, et ces deux enregistrements étaient **refusés** — les
    scénarios que la directive demande de valider n'étaient pas exprimables.
    """
    assert _segment(language="srr").language == "srr"
    assert _segment(language="ln").language == "ln"


def test_l_etat_d_une_langue_depend_de_sa_confiance():
    assert _segment().language_state == INCONNU
    assert _segment(language="wo", language_confidence=0.9).language_state == CONNU
    # Traduire depuis une langue identifiée à 0,3 traduit depuis la mauvaise.
    assert _segment(language="wo",
                    language_confidence=0.3).language_state == CONFIANCE_FAIBLE
    assert _segment(language="wo").language_state == CONFIANCE_FAIBLE


def test_la_langue_appartient_au_segment_pas_au_fichier():
    scene = build_scene([
        _segment(segment_id="s1", start=0.0, end=2.0, language="wo",
                 language_confidence=0.9),
        _segment(segment_id="s2", start=2.0, end=4.0, language="fr",
                 language_confidence=0.9),
    ])
    assert scene["languages"] == ["fr", "wo"]
    assert scene["code_switching"] is True


def test_des_segments_qui_se_chevauchent_sont_refuses():
    with pytest.raises(VoiceSceneRefused) as erreur:
        build_scene([
            _segment(segment_id="s1", start=0.0, end=3.0),
            _segment(segment_id="s2", start=2.0, end=4.0),
        ])
    assert "deux locuteurs" in str(erreur.value)


def test_une_scene_sans_segment_est_refusee():
    with pytest.raises(VoiceSceneRefused) as erreur:
        build_scene([])
    assert "qui n'a pas eu lieu" in str(erreur.value)


def test_ce_qui_manque_est_nomme_segment_par_segment():
    scene = build_scene([
        _segment(segment_id="s1", start=0.0, end=2.0, language="wo",
                 language_confidence=0.9, speaker_id="spk1"),
        _segment(segment_id="s2", start=2.0, end=4.0, language="fr",
                 language_confidence=0.4, speaker_id="spk2"),
        _segment(segment_id="s3", start=4.0, end=6.0),
    ], entities={"spk1": "ent-awa"})

    assert scene["segments_without_language"] == ["s3"]
    assert scene["segments_low_confidence"] == ["s2"]
    assert scene["segments_without_transcript"] == ["s1", "s2", "s3"]
    assert scene["unassigned_speakers"] == ["spk2"]


def test_la_voix_d_origine_est_le_chemin_par_defaut():
    scene = build_scene([_segment()])
    plan = voice_plan(scene)
    assert plan["path"] == "PRESERVE_ORIGINAL"
    # Par défaut, pas en repli.
    assert "pas un repli" in plan["reason"]


def test_une_synthese_demandee_est_rapportee_indisponible():
    scene = build_scene([_segment()])
    plan = voice_plan(scene, synthesise=True)
    assert plan["status"] == "NOT_AVAILABLE"
    assert "aucune installation" in plan["reason"]
    # L'enregistrement reste disponible.
    assert plan["original_audio"] == ["/tmp/enregistrement.wav"]


def test_comprendre_et_parler_sont_deux_capacites():
    capacites = language_capabilities(["wo", "fr"])
    assert capacites["speakable"] == []
    par_langue = {c["code"]: c for c in capacites["languages"]}
    assert "n'a pas été écrit" in par_langue["wo"]["speaking_reason"]
    assert "§26" in par_langue["wo"]["speaking_reason"]


def test_la_chaine_dit_ou_elle_s_arrete_reellement():
    etat = pipeline_state()
    assert etat["first_block"] == "audio_analysis"
    bloquees = {e["stage"]: e for e in etat["stages"]
                if e["state"] == "BLOCKED"}
    assert "speaker_diarization" in bloquees
    # Une étape bloquée dit quoi installer, ou qu'aucune installation ne suffit.
    assert "pyannote" in bloquees["speaker_diarization"]["reason"]


def test_la_preservation_de_l_audio_est_verifiee_sur_le_disque(tmp_path):
    fichier = tmp_path / "voix.wav"
    fichier.write_bytes(b"RIFF")
    presente = build_scene([_segment(original_audio_path=str(fichier))])
    assert original_audio_exists(presente)["preserved"] is True

    absente = build_scene([_segment(original_audio_path=str(tmp_path / "x.wav"))])
    resultat = original_audio_exists(absente)
    assert resultat["preserved"] is False
    # Une garantie qui ne regarde jamais le disque est une intention.
    assert "ne tient plus" in resultat["note"]


def test_le_rapport_vocal_nomme_ce_qu_il_refuse():
    rapport = voice_scene_report()
    refus = " ".join(rapport["does_not"]).lower()
    assert "inventer une traduction" in refus
    assert "par défaut" in refus
    assert rapport["confidence_threshold"] == 0.7
