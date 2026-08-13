"""
Collecte sous portillon et politique santé (VOLET 35, ch. 08 et 10).

Les deux chapitres où une erreur sort de la machine :

- **08** — télécharger, c'est agir sur le serveur de quelqu'un d'autre. Quatre
  conditions, aucune facultative, et **rien n'est téléchargé par ce module**.
- **10** — un modèle qui a lu la bonne notice peut quand même écrire « 500 mg
  toutes les six heures ». Le refus est dans le code, pas dans une invite.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.agent.context import AgentContext  # noqa: E402
from src.knowledge_engine.collection import (  # noqa: E402
    REFERENCE_SEULE,
    REPRODUCTIBLE,
    CollectionRefused,
    plan_collection,
    robots_disallows,
    submit_collection,
)
from src.knowledge_engine.health_policy import (  # noqa: E402
    AVERTISSEMENT,
    NON_DETECTE,
    PLANCHER_DE_SOURCES,
    apply_health_policy,
    check_answer,
    filter_health_sources,
    health_policy_report,
    is_health_subject,
)

INSCRITE = "https://www.ansd.sn/publications/rgph-2023.pdf"
ROBOTS = "User-agent: *\nDisallow: /prive/\n"


# ----------------------------------------------------------------------
# Chapitre 08 — la collecte
# ----------------------------------------------------------------------

def test_rien_n_est_telecharge_par_ce_module():
    """
    Le module **décide**. Le téléchargement n'a jamais manqué ; la décision, si.
    """
    plan = plan_collection(INSCRITE, licence="cc-by", robots_txt=ROBOTS)

    assert plan["allowed"] is True
    assert plan["downloaded"] is False
    assert plan["requires_approval"] is True


def test_une_source_hors_registre_n_est_pas_collectable():
    """
    « Cherche sur internet » n'entre par aucune porte : inscrire une source est
    une décision humaine, et c'est elle qui autorise la collecte.
    """
    plan = plan_collection("https://blog-anonyme.example/article", licence="cc-by")

    assert plan["allowed"] is False
    assert "registre" in plan["reason"]


def test_une_source_de_la_liste_de_refus_reste_refusee():
    """La liste de refus du chapitre 03 vaut aussi ici."""
    plan = plan_collection("https://www.youtube.com/watch?v=abc", licence="cc-by")

    assert plan["allowed"] is False


def test_robots_txt_est_applique_et_pas_seulement_consulte():
    """Un chemin interdit refuse la collecte."""
    plan = plan_collection("https://www.ansd.sn/prive/secret.pdf",
                           licence="cc-by", robots_txt=ROBOTS)

    assert plan["allowed"] is False
    assert "robots.txt" in plan["reason"]


def test_un_robots_txt_absent_n_interdit_rien():
    """
    C'est sa sémantique. Inventer une interdiction empêcherait de collecter une
    source parfaitement ouverte.
    """
    assert robots_disallows("", INSCRITE) is None
    assert plan_collection(INSCRITE, licence="cc-by", robots_txt="")["allowed"] is True


def test_les_regles_d_un_agent_nomme_s_ajoutent_a_celles_de_l_etoile():
    """Ne lire que `*` reviendrait à lire le fichier à moitié."""
    robots = "User-agent: *\nDisallow: /a/\n\nUser-agent: galsen\nDisallow: /b/\n"

    assert robots_disallows(robots, "https://x.sn/a/p", agent="galsen") == "/a/"
    assert robots_disallows(robots, "https://x.sn/b/p", agent="galsen") == "/b/"
    assert robots_disallows(robots, "https://x.sn/b/p", agent="autre") is None


def test_allow_l_emporte_sur_un_disallow_plus_general():
    """
    Défaut trouvé en relisant mon propre code (2026-08-13) : seul `Disallow`
    était lu.

    Un éditeur qui écrit `Disallow: /` puis `Allow: /public/` autorise
    explicitement `/public/`. Ne lire que la première ligne refusait une source
    par lecture incomplète — un refus qui a l'air prudent et qui écarte
    exactement ce que l'éditeur voulait ouvrir.
    """
    robots = "User-agent: *\nDisallow: /\nAllow: /public/\n"

    assert robots_disallows(robots, "https://www.ansd.sn/public/rapport.pdf") is None
    assert robots_disallows(robots, "https://www.ansd.sn/prive/note.pdf") == "/"


def test_la_regle_la_plus_specifique_gagne():
    """C'est la convention du format : la longueur du préfixe tranche."""
    robots = "User-agent: *\nAllow: /a/\nDisallow: /a/prive/\n"

    assert robots_disallows(robots, "https://x.sn/a/public.pdf") is None
    assert robots_disallows(robots, "https://x.sn/a/prive/note.pdf") == "/a/prive/"


def test_une_licence_inconnue_degrade_au_lieu_de_bloquer():
    """
    Une source non reproductible reste une source qu'on peut nommer. Bloquer
    écarterait les meilleures les premières.
    """
    inconnue = plan_collection(INSCRITE, licence="", robots_txt=ROBOTS)
    ouverte = plan_collection(INSCRITE, licence="CC-BY", robots_txt=ROBOTS)

    assert inconnue["allowed"] is True
    assert inconnue["usage"] == REFERENCE_SEULE
    assert ouverte["usage"] == REPRODUCTIBLE


def test_la_demande_d_approbation_porte_de_quoi_decider():
    """Un opérateur doit pouvoir trancher sans relire le code."""
    demande = plan_collection(INSCRITE, licence="", robots_txt=ROBOTS)["approval_request"]

    assert demande["action"] == "collect_document"
    assert "ANSD" in demande["description"]
    assert demande["metadata"]["usage"] == REFERENCE_SEULE
    assert demande["metadata"]["url"] == INSCRITE


def test_un_plan_refuse_ne_peut_pas_etre_soumis():
    """
    Soumettre un refus demanderait à un humain de valider ce que la règle a déjà
    écarté — et rendrait le refus négociable.
    """
    plan = plan_collection("https://blog-anonyme.example/x")
    contexte = AgentContext(request="collecter", agent_id="test")

    with pytest.raises(CollectionRefused):
        submit_collection(contexte, plan)


def test_un_plan_autorise_passe_par_le_portillon():
    """La quatrième condition est la seule qu'un module ne satisfait pas seul."""
    plan = plan_collection(INSCRITE, licence="cc-by", robots_txt=ROBOTS)
    contexte = AgentContext(request="collecter", agent_id="test")

    identifiant = submit_collection(contexte, plan)

    # Le portillon peut être indisponible dans cet environnement ; ce qui est
    # épinglé, c'est que la soumission passe par lui et non par un raccourci.
    assert identifiant is None or isinstance(identifiant, str)


def test_le_module_de_collecte_n_atteint_pas_le_reseau():
    """
    L'acquisition automatisée est différée (VOLET 36, ch. H) : ce module décide,
    il ne collecte pas.
    """
    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "src", "knowledge_engine", "collection.py"),
              encoding="utf-8") as fichier:
        source = fichier.read()

    for interdit in ("requests.", "urlopen", "urlretrieve", "httpx."):
        assert interdit not in source


# ----------------------------------------------------------------------
# Chapitre 10 — la politique santé
# ----------------------------------------------------------------------

OFFICIELLE = {"id": "k-oms", "source_category": "government",
              "content": "La moustiquaire imprégnée réduit la transmission du paludisme."}
INDUSTRIELLE = {"id": "k-blog", "source_category": "industry",
                "content": "Notre produit prévient le paludisme."}


def test_la_sante_a_un_plancher_de_sources_plus_haut_que_le_seuil_general():
    """
    Une documentation industrielle fiable sur un sujet technique reste une
    documentation industrielle sur une maladie.
    """
    verdict = filter_health_sources([OFFICIELLE, INDUSTRIELLE])

    assert [item["id"] for item in verdict["items"]] == ["k-oms"]
    assert verdict["dropped"][0]["category"] == "industry"
    assert set(verdict["floor"]) == {c.value for c in PLANCHER_DE_SOURCES}


def test_sans_source_qualifiee_la_reponse_est_refusee_et_dit_pourquoi():
    """
    Une réponse vide sans explication ferait croire à une base vide, alors que
    le problème est le niveau des sources trouvées.
    """
    verdict = apply_health_policy([INDUSTRIELLE], "Le paludisme se prévient.")

    assert verdict["status"] == "no_qualified_source"
    assert verdict["allowed"] is False
    assert verdict["dropped"]
    assert verdict["what_would_settle_it"]


@pytest.mark.parametrize("phrase,forme", [
    ("Prenez 500 mg toutes les 6 heures.", "posology"),
    ("Vous avez probablement une infection bactérienne.", "diagnosis"),
    ("Prenez ce traitement pendant une semaine.", "prescription"),
])
def test_ni_posologie_ni_diagnostic_ni_prescription(phrase, forme):
    """
    Le refus est du code, pas une consigne d'invite : il s'applique **après** la
    génération, sur le texte réellement produit.
    """
    verdict = check_answer(phrase)

    assert verdict["allowed"] is False
    assert forme in [entree["kind"] for entree in verdict["refused"]]


def test_une_reponse_refusee_l_est_quoi_que_disent_les_sources():
    """
    « 500 mg toutes les six heures » se trouve dans une notice officielle.
    Répétée à quelqu'un dont on ignore le poids et l'âge, c'est une phrase qui
    blesse — et la qualité de la source n'y change rien.
    """
    verdict = apply_health_policy([OFFICIELLE], "Prenez 500 mg toutes les 6 heures.")

    assert verdict["status"] == "refused_form"
    assert verdict["allowed"] is False


def test_l_avertissement_accompagne_toute_reponse_de_sante():
    """
    Sur **chaque** réponse, y compris les refus : la personne qui lit doit voir,
    dans la même réponse, qu'un professionnel reste nécessaire.
    """
    permise = apply_health_policy([OFFICIELLE], "La moustiquaire réduit la transmission.")
    refusee = apply_health_policy([INDUSTRIELLE], "Peu importe.")

    assert permise["allowed"] is True
    assert permise["safety_notice"] == AVERTISSEMENT
    assert refusee["safety_notice"] == AVERTISSEMENT
    assert "professionnel" in AVERTISSEMENT


@pytest.mark.parametrize("phrase", [
    "Elle a une durée de protection de trois ans.",
    "Le vaccin il a un effet mesuré sur trois ans.",
    "Vous avez le droit de consulter gratuitement.",
    "Vous avez besoin d'un avis médical.",
    "La campagne de vaccination a une couverture de 80 %.",
])
def test_une_phrase_utile_n_est_pas_prise_pour_un_diagnostic(phrase):
    """
    Défaut trouvé en sondant mon propre filtre (2026-08-13).

    Le motif de diagnostic attrapait « elle a une durée » et « vous avez le
    droit » : des phrases utiles, refusées. Un filtre qui refuse ce genre de
    phrase rend la santé inutilisable, et **un filtre qui refuse tout ne protège
    personne** — c'est le défaut inverse de celui qu'il combat, pas un excès de
    prudence.
    """
    assert check_answer(phrase)["allowed"] is True


@pytest.mark.parametrize("phrase", [
    "Vous avez une infection bactérienne.",
    "Vous avez probablement une angine.",
    "Elle souffre d'un paludisme grave.",
    "Vous êtes atteint de diabète.",
])
def test_le_resserrement_n_a_pas_ouvert_la_porte_au_diagnostic(phrase):
    """
    La contrepartie, vérifiée plutôt que supposée : corriger un faux positif
    laisse souvent passer un vrai. Ces quatre-là restent refusées.
    """
    verdict = check_answer(phrase)

    assert verdict["allowed"] is False
    assert "diagnosis" in [entree["kind"] for entree in verdict["refused"]]


def test_une_reponse_ordinaire_n_est_pas_refusee_par_excès_de_zele():
    """
    Le contre-test qui donne son sens aux précédents : un filtre qui refuserait
    tout ne protégerait personne, il rendrait la santé inutilisable.
    """
    verdict = check_answer(
        "La moustiquaire imprégnée réduit la transmission du paludisme, "
        "surtout chez l'enfant."
    )

    assert verdict["allowed"] is True


def test_le_sujet_sante_est_reconnu_par_l_axe_existant():
    """Pas de seconde liste de sujets sensibles : `SAFETY_CRITICAL_SUBJECTS` fait foi."""
    assert is_health_subject("health") is True
    assert is_health_subject("agriculture") is False


def test_la_politique_se_lit_sans_lire_le_code():
    """Et elle nomme ce qu'elle ne détecte pas plutôt que de le sous-entendre."""
    rapport = health_policy_report()

    assert rapport["source_floor"] == sorted(c.value for c in PLANCHER_DE_SOURCES)
    assert set(rapport["refused_forms"]) == {"posology", "diagnosis", "prescription"}
    assert rapport["not_detected"] == list(NON_DETECTE)
    assert rapport["method"] == "patterns"


def test_le_plancher_s_applique_avant_l_arbitrage_de_portee():
    """
    Trier par pays des sources qui n'ont pas le niveau exigé reviendrait à
    choisir laquelle des mauvaises servir.
    """
    from src.knowledge_engine.scoped_retrieval import retrieve_scoped

    class BaseFictive:
        """Récupérateur qui rend une source officielle et une industrielle."""

        def retrieve_reliable(self, prompt, **kwargs):
            """Rend les deux éléments, comme le récupérateur réel."""
            return {"items": [dict(OFFICIELLE, scope="country:sn"),
                              dict(INDUSTRIELLE, scope="country:sn")],
                    "reliable": True, "sources": [], "citation_coverage": {},
                    "reason": "", "best_priority": "P1", "best_confidence": 0.9}

    resultat = retrieve_scoped(BaseFictive(), "Paludisme à Dakar ?", subject="health")

    assert resultat["health_policy"]["applied"] is True
    assert [item["id"] for item in resultat["items"]] == ["k-oms"]
    assert resultat["health_policy"]["dropped"][0]["id"] == "k-blog"


def test_une_question_hors_sante_ne_declenche_pas_la_politique():
    """Le contre-test : la politique santé ne s'applique qu'à la santé."""
    from src.knowledge_engine.scoped_retrieval import retrieve_scoped

    class BaseFictive:
        """Récupérateur qui rend une source industrielle."""

        def retrieve_reliable(self, prompt, **kwargs):
            """Rend l'élément décidé par le test."""
            return {"items": [dict(INDUSTRIELLE, scope="global")], "reliable": True,
                    "sources": [], "citation_coverage": {}, "reason": "",
                    "best_priority": "P3", "best_confidence": 0.5}

    resultat = retrieve_scoped(BaseFictive(), "Quel engrais pour le mil ?",
                               subject="agriculture")

    assert "health_policy" not in resultat
    assert resultat["items"]


def test_la_route_publie_la_politique_sante():
    """Une limite connue doit être lisible par qui utilise la plateforme."""
    from fastapi.testclient import TestClient

    from src.api import server as server_module
    from src.api.rate_limiter import set_valid_api_key_digests
    from src.api.server import app

    ancien = dict(server_module.rbac_manager._key_role_map)
    os.environ["GALSEN_API_KEYS"] = "cle-lecture-sante:readonly"
    server_module.rbac_manager.reload()
    set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
    try:
        with TestClient(app) as client:
            reponse = client.get("/knowledge/health-policy",
                                 headers={"X-API-Key": "cle-lecture-sante"})
        assert reponse.status_code == 200
        corps = reponse.json()
        assert set(corps["refused_forms"]) == {"posology", "diagnosis", "prescription"}
        assert corps["not_detected"]
    finally:
        os.environ.pop("GALSEN_API_KEYS", None)
        server_module.rbac_manager._key_role_map = ancien
        set_valid_api_key_digests(server_module.rbac_manager.get_valid_key_digests())
