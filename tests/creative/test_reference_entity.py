"""
Tests for reference entities, their consent and their ingestion
(ADR-025, directive §6–§13, §58).

Three properties carry the weight: a reference with no consent scope cannot be
used at all, nothing about identity is fabricated from media that only shows
pixels, and a revocation names what it reaches instead of deleting quietly.
"""

import pytest
from PIL import Image

from src.creative.reference.consent import (
    ACTIF,
    CONSERVATION_DUREE,
    PORTEE_COMPTE,
    PORTEE_PROJET,
    REVOQUE,
    ConsentRefused,
    ConsentScope,
    authorize,
    consent_report,
    is_platform_identity,
)
from src.creative.reference.entity import (
    ABSENT,
    DERIVE,
    MESURE,
    Observation,
    ReferenceEntity,
    ReferenceRefused,
    SourceMedium,
    file_digest,
    reference_report,
)
from src.creative.reference.ingestion import (
    CHAMPS_BLOQUES,
    analyse_image,
    blocked_observations,
    combine,
    ingest,
    ingestion_report,
)
from src.creative.reference.memory import (
    PARTAGEE,
    PRIVEE,
    ReferenceMemory,
    ReferenceMemoryRefused,
    reference_memory_report,
)


@pytest.fixture
def photos(tmp_path):
    """Trois images réelles, de rapports très proches."""
    chemins = []
    for index, taille in enumerate([(800, 600), (802, 600), (1200, 900)]):
        chemin = tmp_path / f"photo{index}.jpg"
        Image.new("RGB", taille, (30 + index * 20, 90, 140)).save(chemin)
        chemins.append(str(chemin))
    return chemins


def _consentement(**kwargs):
    """Un consentement valide, réglable."""
    defauts = dict(granted_by="Mariama Diop", subject="Mariama Diop",
                   permitted_uses=("project:demo",), evidence="formulaire signé")
    defauts.update(kwargs)
    return ConsentScope(**defauts)


# --------------------------------------------------------------------------
# Consentement
# --------------------------------------------------------------------------


def test_une_reference_sans_consentement_est_inutilisable():
    reference = ReferenceEntity(entity_type="human")
    verdict = reference.usable("project:demo")
    assert verdict["allowed"] is False
    # L'absence de portée est l'absence de permission.
    assert "absence de permission" in verdict["reason"]


def test_un_usage_hors_liste_est_refuse_en_le_nommant():
    reference = ReferenceEntity(entity_type="human")
    reference.grant(_consentement())
    verdict = reference.usable("commercial")
    assert verdict["allowed"] is False
    assert "commercial" in verdict["reason"]
    assert "liste est blanche" in verdict["reason"]


def test_une_portee_ne_s_elargit_pas():
    reference = ReferenceEntity(entity_type="human")
    reference.grant(_consentement(scope=PORTEE_PROJET))
    assert reference.usable("project:demo", PORTEE_PROJET)["allowed"] is True
    verdict = reference.usable("project:demo", PORTEE_COMPTE)
    assert verdict["allowed"] is False
    assert "plus large" in verdict["reason"]


def test_la_plateforme_ne_consent_pas_a_la_place_de_quelqu_un():
    with pytest.raises(ConsentRefused) as erreur:
        _consentement(granted_by="GalSen IA")
    assert "plateforme" in str(erreur.value)


def test_l_identite_de_plateforme_est_comparee_par_mots_entiers():
    # « ia » est à l'intérieur de « Mariama » : une comparaison par
    # sous-chaîne refuserait le consentement d'une personne réelle.
    assert is_platform_identity("Mariama Diop") is False
    assert is_platform_identity("galsen ia") is True
    assert is_platform_identity("GalSen-IA") is True


def test_un_consentement_sans_usage_nomme_est_refuse():
    with pytest.raises(ConsentRefused) as erreur:
        _consentement(permitted_uses=())
    assert "autorisation générale" in str(erreur.value)


def test_pour_toujours_n_est_pas_une_politique_de_conservation():
    with pytest.raises(ConsentRefused) as erreur:
        _consentement(retention=CONSERVATION_DUREE, expires_at=None)
    assert "illimitée déguisée" in str(erreur.value)


def test_un_consentement_expire_ne_se_prolonge_pas():
    consentement = _consentement(retention=CONSERVATION_DUREE, expires_at=1.0)
    verdict = authorize(consentement, "project:demo", state=ACTIF, now=2.0)
    assert verdict["allowed"] is False
    assert "expiré" in verdict["reason"]


def test_le_rapport_de_consentement_nomme_ce_qu_il_refuse():
    refus = " ".join(consent_report()["does_not"]).lower()
    assert "téléversement" in refus
    assert "élargir" in refus


# --------------------------------------------------------------------------
# La référence
# --------------------------------------------------------------------------


def test_le_type_d_entite_est_ouvert_et_declare():
    for type_entite in ("human", "animal", "vehicle", "product", "environment"):
        assert ReferenceEntity(entity_type=type_entite).entity_type == type_entite
    with pytest.raises(ReferenceRefused) as erreur:
        ReferenceEntity(entity_type="chose")
    assert "boutique comme une personne" in str(erreur.value)


def test_un_media_sans_empreinte_est_refuse():
    with pytest.raises(ReferenceRefused) as erreur:
        SourceMedium(medium_id="m1", kind="image", path="/x.jpg", sha256="")
    # Sans empreinte, « supprimez ce que j'ai envoyé » est invérifiable.
    assert "invérifiable" in str(erreur.value)


def test_une_mesure_sans_outil_est_refusee():
    with pytest.raises(ReferenceRefused) as erreur:
        Observation(field_name="dimensions", value=[1, 2], origin=MESURE)
    assert "n'est pas une mesure" in str(erreur.value)


def test_une_absence_sans_raison_est_refusee():
    with pytest.raises(ReferenceRefused) as erreur:
        Observation(field_name="geometry", origin=ABSENT)
    assert "appellent des actions différentes" in str(erreur.value)


def test_un_champ_jamais_observe_rend_une_absence_declaree():
    reference = ReferenceEntity(entity_type="human")
    observation = reference.observation("geometry")
    assert observation.origin == ABSENT
    # Pas `None` : un appelant finirait par le lire comme une valeur vide.
    assert "personne n'a regardé" in observation.reason


def test_une_observation_remplacee_est_conservee():
    reference = ReferenceEntity(entity_type="product")
    reference.observe(Observation(field_name="aspect_ratio", value=1.0,
                                  origin=MESURE, measured_by="Pillow"))
    reference.observe(Observation(field_name="aspect_ratio", value=1.5,
                                  origin=MESURE, measured_by="Pillow"))
    assert reference.observation("aspect_ratio").value == 1.5
    assert len(reference.versions) == 1
    assert reference.versions[0]["superseded"]["value"] == 1.0


def test_ce_qu_un_modele_a_propose_est_liste_a_part():
    reference = ReferenceEntity(entity_type="human")
    reference.observe(Observation(field_name="dimensions", value=[8, 6],
                                  origin=MESURE, measured_by="Pillow"))
    reference.observe(Observation(field_name="clothing", value="boubou bleu",
                                  origin=DERIVE))
    manifeste = reference.manifest()
    assert manifeste["measured_fields"] == ["dimensions"]
    assert manifeste["ai_derived_fields"] == ["clothing"]


def test_aucune_methode_ne_supprime_une_reference():
    # Une suppression gardée finit par être appelée avec le bon argument.
    assert not [nom for nom in dir(ReferenceEntity)
                if "delete" in nom or "supprim" in nom]


def test_une_revocation_est_terminale_et_conservee():
    reference = ReferenceEntity(entity_type="human")
    reference.grant(_consentement())
    reference.revoke(by="Mariama Diop", reason="changement d'avis",
                     derived=("shot-1", "shot-2"))

    assert reference.state == REVOQUE
    assert reference.usable("project:demo")["allowed"] is False
    assert reference.revocation.propagated_to == ("shot-1", "shot-2")
    with pytest.raises(ReferenceRefused):
        reference.grant(_consentement())
    with pytest.raises(ReferenceRefused):
        reference.add_medium(SourceMedium(medium_id="m", kind="image",
                                          path="/x.jpg", sha256="abc"))


def test_l_empreinte_d_un_fichier_absent_est_refusee(tmp_path):
    with pytest.raises(ReferenceRefused) as erreur:
        file_digest(str(tmp_path / "jamais.jpg"))
    assert "deux absences se ressembleraient" in str(erreur.value)


# --------------------------------------------------------------------------
# Ingestion
# --------------------------------------------------------------------------


def test_une_image_est_mesuree_et_nomme_son_outil(photos):
    observations = {o.field_name: o for o in analyse_image(photos[0], "m1")}
    assert observations["dimensions"].value == [800, 600]
    assert observations["dimensions"].measured_by == "Pillow"
    assert observations["aspect_ratio"].origin == MESURE
    assert len(observations["dominant_colours"].value) <= 3


def test_rien_qui_touche_a_l_identite_n_est_produit(photos):
    champs = {o.field_name for o in analyse_image(photos[0], "m1")}
    assert champs.isdisjoint(CHAMPS_BLOQUES)


def test_les_champs_non_mesurables_sont_declares_avec_leur_capacite():
    absences = {o.field_name: o for o in blocked_observations()}
    assert "facial_characteristics" in absences
    assert absences["facial_characteristics"].origin == ABSENT
    # La raison nomme la capacité qui manque, pas seulement le manque.
    assert "face_detection" in absences["facial_characteristics"].reason
    assert "geometry" in absences and "inventée" in absences["geometry"].reason


def test_combiner_augmente_la_confiance_sans_creer_d_information(photos):
    observations = [analyse_image(p, f"m{i}")[1] for i, p in enumerate(photos)]
    combinee = combine(observations, "aspect_ratio")
    assert combinee.origin == MESURE
    assert combinee.confidence is not None and combinee.confidence > 0.9
    assert len(combinee.observed_from) == 3
    # Trois photos de face ne produisent pas un profil.
    assert combinee.field_name == "aspect_ratio"


def test_combiner_du_vide_ne_produit_pas_une_valeur():
    resultat = combine([], "aspect_ratio")
    assert resultat.origin == ABSENT
    assert "Combiner du vide" in resultat.reason


def test_l_ingestion_rattache_mesure_et_declare(photos):
    reference = ReferenceEntity(entity_type="human")
    resultat = ingest(reference, photos, uploaded_by="awa")

    assert len(resultat["attached"]) == 3
    assert resultat["measured_fields"] == ["aspect_ratio", "dimensions",
                                           "dominant_colours"]
    assert len(resultat["blocked_fields"]) == len(CHAMPS_BLOQUES)
    assert all(m["sha256"] for m in resultat["attached"])


def test_une_video_est_rattachee_avec_son_empreinte_et_non_analysee(tmp_path):
    video = tmp_path / "rush.mp4"
    video.write_bytes(b"pas une vraie video")
    reference = ReferenceEntity(entity_type="human")
    resultat = ingest(reference, [str(video)])

    assert resultat["measured_fields"] == []
    assert resultat["not_analysed"][0]["kind"] == "video"
    # L'empreinte suffit à la révoquer plus tard.
    assert resultat["attached"][0]["sha256"]


def test_un_genre_de_fichier_inconnu_est_refuse(tmp_path):
    inconnu = tmp_path / "chose.xyz"
    inconnu.write_bytes(b"x")
    with pytest.raises(ReferenceRefused) as erreur:
        ingest(ReferenceEntity(entity_type="object"), [str(inconnu)])
    assert "n'est pas deviné" in str(erreur.value)


def test_le_rapport_d_ingestion_nomme_ce_qu_il_refuse():
    rapport = ingestion_report()
    assert rapport["image_analysis_available"] is True
    assert rapport["blocked"]["identity"]["capability"] == "identity_verification"
    refus = " ".join(rapport["does_not"]).lower()
    assert "visage" in refus


# --------------------------------------------------------------------------
# Mémoire des références
# --------------------------------------------------------------------------


def test_une_reference_est_privee_par_defaut():
    memoire = ReferenceMemory()
    reference = memoire.add(ReferenceEntity(entity_type="human"))
    assert memoire.privacy_of(reference.reference_id) == PRIVEE


def test_partager_exige_un_consentement_qui_le_prevoit():
    memoire = ReferenceMemory()
    reference = ReferenceEntity(entity_type="human")
    reference.grant(_consentement(may_share=False))
    memoire.add(reference)
    with pytest.raises(ReferenceMemoryRefused) as erreur:
        memoire.share(reference.reference_id, by="awa")
    assert "élargirait une portée" in str(erreur.value)


def test_un_consentement_qui_prevoit_le_partage_l_autorise():
    memoire = ReferenceMemory()
    reference = ReferenceEntity(entity_type="product")
    reference.grant(_consentement(may_share=True))
    memoire.add(reference)
    assert memoire.share(reference.reference_id, by="awa")["privacy"] == PARTAGEE


def test_une_personne_peut_savoir_ce_qu_on_detient_d_elle():
    memoire = ReferenceMemory()
    for _ in range(2):
        reference = ReferenceEntity(entity_type="human")
        reference.grant(_consentement())
        memoire.add(reference)
    autre = ReferenceEntity(entity_type="human")
    autre.grant(_consentement(granted_by="Ousmane Sy", subject="Ousmane Sy"))
    memoire.add(autre)

    assert len(memoire.for_subject("Mariama Diop")) == 2
    assert len(memoire.for_subject("Ousmane Sy")) == 1


def test_une_revocation_nomme_ce_qu_elle_atteint_et_ne_supprime_rien():
    memoire = ReferenceMemory()
    reference = ReferenceEntity(entity_type="human")
    reference.grant(_consentement())
    memoire.add(reference)

    resultat = memoire.revoke_for_subject(
        "Mariama Diop", by="Mariama Diop", reason="retrait",
        derived={reference.reference_id: ("shot-1", "shot-2")},
    )
    assert resultat["revoked"] == [reference.reference_id]
    assert resultat["derived_reached"] == ["shot-1", "shot-2"]
    # Rien n'est supprimé : une suppression silencieuse serait invérifiable.
    assert resultat["deleted"] == []
    assert memoire.get(reference.reference_id) is not None


def test_une_reference_revoquee_reste_au_registre():
    memoire = ReferenceMemory()
    reference = ReferenceEntity(entity_type="human")
    reference.grant(_consentement())
    memoire.add(reference)
    memoire.revoke_for_subject("Mariama Diop", by="Mariama Diop")

    rapport = memoire.report()
    assert rapport["count"] == 1
    assert rapport["by_state"][REVOQUE] == [reference.reference_id]
    assert memoire.usable_for("project:demo") == []


def test_le_registre_dit_quand_il_n_est_pas_integre():
    memoire = ReferenceMemory()
    memoire.add(ReferenceEntity(entity_type="human"))
    rapport = memoire.report()
    assert rapport["integrated"] is False
    assert "rien n'est persisté" in rapport["note"]
    # Les références sans consentement sont la liste qui compte.
    assert len(rapport["without_consent"]) == 1


def test_le_registre_ecrit_dans_la_memoire_de_la_plateforme():
    from src.memory_engine.memory_manager import MemoryManager

    memoire = ReferenceMemory(memory_manager=MemoryManager())
    reference = ReferenceEntity(entity_type="human", created_by="awa")
    memoire.add(reference)
    rapport = memoire.report()

    assert rapport["integrated"] is True
    assert rapport["writes"] >= 1
    assert rapport["writes_failed"] == []


def test_les_rapports_nomment_ce_qu_ils_refusent():
    assert "Fabriquer une géométrie" in " ".join(reference_report()["does_not"])
    refus = " ".join(reference_memory_report()["does_not"]).lower()
    assert "concurrent" in refus
    assert "silence" in refus
