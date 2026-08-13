"""
Métadonnées et détection de langue (ADR-021, étape 6).

Ce que ces tests gardent : rien n'est deviné. Une date ambiguë rend `unknown`
avec sa raison, une langue sans liste relue rend `unknown` plutôt qu'un voisin
plausible, et le désaccord entre déclaré et détecté part en quarantaine au lieu
d'être tranché par une machine.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.language import (  # noqa: E402
    INCONNU,
    MOTS_MINIMUM,
    detect_language,
    detection_report,
    known_detectable_languages,
    reconcile,
)
from src.acquisition.metadata import (  # noqa: E402
    apply_to,
    extract,
    from_html,
    from_pdf,
    metadata_report,
    normalize_date,
)
from src.acquisition.record import AcquiredDocument  # noqa: E402

PAGE = """<html><head>
<title>Titre de repli</title>
<meta name="DC.title" content="Annuaire statistique 2024">
<meta name="dc.date.issued" content="2024-03-15">
<meta name="dc.publisher" content="Agence nationale">
<meta name="dc.language" content="FR">
<link rel="canonical" href="https://www.ansd.sn/annuaire-2024">
</head><body>Contenu</body></html>""".encode("utf-8")

FRANCAIS = (
    "Le rapport présente les résultats de l'enquête menée dans les régions du pays. "
    "Les données sont issues des services statistiques et ont été collectées par les "
    "équipes sur le terrain avec les partenaires qui participent à cette opération."
)

ANGLAIS = (
    "The report presents the results of the survey which was carried out in the "
    "regions of the country. The data are from the statistical services and have "
    "been collected by the teams with their partners during this operation."
)


# ----------------------------------------------------------------------
# Les dates — la règle qui compte
# ----------------------------------------------------------------------

def test_une_date_iso_est_lue_telle_quelle():
    """Le cas simple doit marcher, sinon la prudence du reste ne sert à rien."""
    assert normalize_date("2024-03-15T10:00:00Z")["date"] == "2024-03-15"


def test_une_date_ambigue_rend_inconnu_avec_sa_raison():
    """
    `03/04/2024` est mars pour un lecteur et avril pour un autre. Deviner
    produirait un classement chronologique faux, et un classement faux ne se
    voit jamais.
    """
    verdict = normalize_date("03/04/2024")

    assert verdict["date"] == INCONNU
    assert "ambiguë" in verdict["reason"]


def test_une_date_dont_l_ordre_est_leve_est_acceptee():
    """La contrepartie : refuser `15/03/2024` serait de la prudence inutile."""
    assert normalize_date("15/03/2024")["date"] == "2024-03-15"


def test_une_annee_seule_reste_une_annee_seule():
    """Compléter au 1er janvier inventerait un jour et un mois."""
    verdict = normalize_date("Publié en 2019")

    assert verdict["date"] == "2019"
    assert "jour et le mois restent inconnus" in verdict["reason"]


# ----------------------------------------------------------------------
# HTML et PDF
# ----------------------------------------------------------------------

def test_le_dublin_core_passe_devant_la_balise_titre():
    """`<title>` porte souvent le nom du site ; `DC.title` porte celui du document."""
    metadonnees = from_html(PAGE)

    assert metadonnees["document_title"] == "Annuaire statistique 2024"
    assert metadonnees["publication_date"] == "2024-03-15"
    assert metadonnees["publisher"] == "Agence nationale"
    assert metadonnees["canonical_url"] == "https://www.ansd.sn/annuaire-2024"
    assert metadonnees["language_declared"] == "fr"


def test_une_page_sans_metadonnees_rend_des_inconnus_pas_des_valeurs_plausibles():
    """Une valeur plausible serait crue ; `unknown` ne l'est pas."""
    metadonnees = from_html(b"<html><body>rien</body></html>")

    assert metadonnees["document_title"] == INCONNU
    assert metadonnees["publication_date"] == INCONNU
    assert metadonnees["publisher"] == INCONNU


def test_l_absence_de_bibliotheque_pdf_est_dite_et_non_confondue_avec_un_pdf_vide():
    """
    Les deux situations demandent des actions différentes — installer un paquet,
    ou chercher la date ailleurs — et les confondre fait chercher au mauvais endroit.
    """
    verdict = from_pdf(b"%PDF-1.4 faux")

    assert verdict["available"] is False
    assert verdict["document_title"] == INCONNU
    assert "pypdf" in verdict["reason"] or "illisible" in verdict["reason"]


def test_un_type_non_pris_en_charge_ne_devine_rien():
    """Un extracteur absent est une absence, pas un document sans métadonnées."""
    verdict = extract(b"...", content_type="image/png")

    assert verdict["available"] is False
    assert verdict["document_title"] == INCONNU


def test_les_metadonnees_ne_remplacent_jamais_ce_que_dit_le_registre():
    """
    Un document qui se déclare « publication officielle » ne gagne rien à le
    dire : l'autorité vient du registre, et c'est toute la règle.
    """
    document = AcquiredDocument(
        source_url="https://www.ansd.sn/x.html", institution="ANSD",
        source_tier="TIER_A_PRIMARY_OFFICIAL", country="SN",
    )
    apply_to(document, from_html(PAGE))

    assert document.institution == "ANSD"
    assert document.source_tier == "TIER_A_PRIMARY_OFFICIAL"
    assert document.country == "SN"
    assert document.document_title == "Annuaire statistique 2024"


def test_la_date_de_publication_reste_inconnue_quand_le_document_n_en_donne_pas():
    """Elle n'est jamais reprise de la date de récupération."""
    document = AcquiredDocument(
        source_url="https://x.sn/a.html", retrieval_date="2026-08-13T10:00:00+00:00",
    )
    apply_to(document, from_html(b"<html><title>Note</title></html>"))

    assert document.publication_date == INCONNU
    assert document.publication_date != document.retrieval_date


# ----------------------------------------------------------------------
# La détection de langue
# ----------------------------------------------------------------------

def test_le_francais_et_l_anglais_sont_reconnus():
    """Les deux seules listes relues du fichier de marqueurs."""
    assert detect_language(FRANCAIS)["language"] == "fr"
    assert detect_language(ANGLAIS)["language"] == "en"


def test_un_texte_trop_court_ne_recoit_aucun_verdict():
    """Une langue « détectée » sur dix mots est un tirage au sort présenté en mesure."""
    verdict = detect_language("Le rapport est publié.")

    assert verdict["language"] == INCONNU
    assert str(MOTS_MINIMUM) in verdict["why"]


def test_le_serere_n_est_pas_detectable_et_ne_devient_pas_du_wolof():
    """
    Le cœur de l'étape. Aucune liste n'existe pour le sérère ; en inventer une
    produirait un détecteur qui se trompe avec assurance, et un sérère pris pour
    du wolof serait pire qu'une absence de réponse.
    """
    assert "srr" not in known_detectable_languages()
    assert detection_report()["not_detectable"] == ["srr"]


def test_une_langue_sans_liste_rend_inconnu_plutot_que_le_voisin_le_plus_proche():
    """Un texte dans une langue inconnue du fichier ne se voit pas attribuer une voisine."""
    verdict = detect_language("xolam ndaxit fuluwaa " * 20)

    assert verdict["language"] == INCONNU
    assert "seuil" in verdict["why"] or "coude à coude" in verdict["why"]


def test_un_verdict_issu_d_une_liste_non_relue_porte_sa_reserve(tmp_path):
    """
    Une liste écrite sans locuteur ne doit pas produire un résultat aussi
    affirmatif que le français. La réserve est dans le verdict, pas dans un
    commentaire que personne ne lit.
    """
    fichier = tmp_path / "markers.yaml"
    fichier.write_text(
        "languages:\n  wo:\n    reviewed: false\n    markers: [ak, ci, ngir, dafa, bu]\n",
        encoding="utf-8",
    )
    texte = "ak ci ngir dafa bu " * 10 + "mot " * 10

    verdict = detect_language(texte, chemin=str(fichier))

    assert verdict["language"] == "wo"
    assert verdict["reviewed"] is False
    assert "pas été relue par un locuteur" in verdict["caveat"]


def test_un_fichier_de_marqueurs_absent_ne_produit_pas_de_verdicts_inventes(tmp_path):
    """Perdre la donnée doit rendre le détecteur muet, pas imaginatif."""
    verdict = detect_language(FRANCAIS, chemin=str(tmp_path / "absent.yaml"))

    assert verdict["language"] == INCONNU
    assert "aucune langue" in verdict["why"]


# ----------------------------------------------------------------------
# Détecté contre déclaré
# ----------------------------------------------------------------------

def test_un_desaccord_part_en_quarantaine_au_lieu_d_etre_tranche():
    """
    Un document bilingue, une déclaration erronée et un détecteur trompé se
    ressemblent : seule une personne les distingue.
    """
    verdict = reconcile(detect_language(FRANCAIS), declared="en")

    assert verdict["agreement"] == "disagree"
    assert verdict["quarantine"] is True


@pytest.mark.parametrize("declaree,texte,attendu", [
    ("fr", FRANCAIS, "agree"),
    ("", FRANCAIS, "undeclared"),
    ("wo", "trop court", "undetected"),
])
def test_les_trois_cas_qui_ne_sont_pas_des_desaccords(declaree, texte, attendu):
    """Ne pas détecter n'est pas contredire : `unknown` ne met rien en quarantaine."""
    verdict = reconcile(detect_language(texte), declared=declaree)

    assert verdict["agreement"] == attendu
    assert verdict["quarantine"] is False


def test_le_rapport_dit_quelles_listes_ne_sont_pas_relues():
    """Une page qui n'afficherait que « 4 langues détectables » serait fausse."""
    rapport = detection_report()

    assert set(rapport["reviewed"]) == {"fr", "en"}
    assert set(rapport["unreviewed"]) == {"wo", "ff"}
    assert any("sérère" in ligne for ligne in rapport["not_detected"])


def test_le_rapport_des_metadonnees_nomme_ce_qui_n_est_jamais_deduit():
    """Les règles se vérifient sans lire le code."""
    rapport = metadata_report()

    assert any("retrieval_date" in ligne for ligne in rapport["never_inferred"])
    assert any("registre" in ligne for ligne in rapport["never_inferred"])
    assert rapport["ambiguous_dates"] == "unknown, avec la raison"


# ----------------------------------------------------------------------
# Le rapport de capacités dit désormais la vérité
# ----------------------------------------------------------------------

def test_le_rapport_de_capacites_reflete_la_detection_reelle():
    """
    `languages.py` disait « aucun détecteur n'existe, pour aucune langue ».
    C'était vrai ; ça ne l'est plus, et le verdict est **mesuré sur le fichier
    de marqueurs** au lieu d'être recopié — sinon il vieillirait à la première
    liste ajoutée.
    """
    from src.knowledge_engine.languages import language_support

    assert language_support("fr")["capabilities"]["detection"]["support"] == "yes"
    assert language_support("wo")["capabilities"]["detection"]["support"] == "partial"
    assert language_support("ff")["capabilities"]["detection"]["support"] == "partial"


def test_le_serere_reste_non_detectable_dans_le_rapport_de_capacites():
    """
    La capacité la plus facile à annoncer à tort. Elle dit `no`, avec ce qui la
    débloquerait — une liste écrite par un locuteur.
    """
    verdict = language_support_srr()

    assert verdict["support"] == "no"
    assert "locuteur" in verdict["blocked_on"]
    assert "déclarable et stockable" in verdict["evidence"]


def language_support_srr():
    """Raccourci lisible pour le verdict de détection du sérère."""
    from src.knowledge_engine.languages import language_support

    return language_support("srr")["capabilities"]["detection"]
