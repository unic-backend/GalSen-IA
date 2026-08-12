"""
Les trois agents personnels du brief (VOLET 34, ch. 11).

Un par danger distinct :

1. **`organizer`** — il peut déplacer des fichiers. Le test qui compte n'est pas
   qu'il range bien, c'est qu'il **ne range rien** sans décision humaine.
2. **`project_manager`** — il peut inventer un avancement. Le test qui compte est
   qu'il distingue « pas encore commencé » de « fait ».
3. **`opportunity`** — il peut fabriquer une analyse de marché complète et
   crédible sur laquelle quelqu'un dépenserait de l'argent. Le test qui compte
   est qu'il **refuse** quand aucune source ne dit rien.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.opportunity.agent import NON_PRODUIT, OpportunityAnalystAgent  # noqa: E402
from agents.organizer.agent import CATEGORIES, FileOrganizerAgent  # noqa: E402
from agents.project_manager.agent import ProjectManagerAgent  # noqa: E402
from src.agent.context import AgentContext  # noqa: E402
from src.storage.roots import VARIABLE  # noqa: E402


# ----------------------------------------------------------------------
# Outils du test
# ----------------------------------------------------------------------


@pytest.fixture
def racine(tmp_path, monkeypatch):
    """Une racine inscriptible, avec des fichiers en vrac à sa surface."""
    dossier = tmp_path / "documents"
    dossier.mkdir()
    for nom in ("rapport.pdf", "photo.jpg", "notes.md", "archive.zip", "inconnu.xyz"):
        (dossier / nom).write_text("contenu", encoding="utf-8")
    # Un fichier déjà rangé : personne ne doit le déplacer.
    (dossier / "projets").mkdir()
    (dossier / "projets" / "plan.pdf").write_text("contenu", encoding="utf-8")
    monkeypatch.setenv(VARIABLE, f"documents:{dossier}:rw")
    return dossier


def contexte(requete: str = "ranger mes fichiers", **kwargs) -> AgentContext:
    """Contexte d'agent minimal."""
    return AgentContext(request=requete, agent_id="test", **kwargs)


# ----------------------------------------------------------------------
# 1. L'organisateur de fichiers
# ----------------------------------------------------------------------


def test_l_organisateur_ne_deplace_rien_en_proposant(racine):
    """
    Le cœur de cet agent : proposer n'est pas ranger.

    Le mauvais scénario n'est pas une mauvaise suggestion — c'est cent fichiers
    déplacés dans des dossiers que personne n'a demandés.
    """
    avant = sorted(os.listdir(racine))

    resultat = FileOrganizerAgent().perform(contexte())

    assert resultat["status"] == "planned"
    assert resultat["applied"] is False
    assert sorted(os.listdir(racine)) == avant


def test_l_organisateur_classe_par_extension(racine):
    destinations = {
        proposition["source"]: proposition["destination"]
        for proposition in FileOrganizerAgent().perform(contexte())["proposals"]
    }
    assert destinations["documents/rapport.pdf"] == "documents/documents/rapport.pdf"
    assert destinations["documents/photo.jpg"] == "documents/images/photo.jpg"
    assert destinations["documents/archive.zip"] == "documents/archives/archive.zip"


def test_un_fichier_sans_categorie_n_est_pas_range(racine):
    """
    Un dossier « divers » reproduirait le désordre qu'on prétend corriger.
    """
    sources = [p["source"] for p in FileOrganizerAgent().perform(contexte())["proposals"]]
    assert "documents/inconnu.xyz" not in sources


def test_un_fichier_deja_range_n_est_pas_touche(racine):
    """Déplacer un fichier posé dans un dossier défait un choix humain."""
    sources = [p["source"] for p in FileOrganizerAgent().perform(contexte())["proposals"]]
    assert all("projets" not in source for source in sources)


def test_sans_racine_declaree_l_agent_dit_comment_en_declarer_une(monkeypatch):
    """Un plan vide se lirait « rien à ranger », ce qui serait faux."""
    monkeypatch.delenv(VARIABLE, raising=False)

    resultat = FileOrganizerAgent().perform(contexte())

    assert resultat["status"] == "no_roots"
    assert VARIABLE in resultat["example"]
    assert resultat["proposals"] == []


def test_une_racine_en_lecture_seule_est_refusee(tmp_path, monkeypatch):
    """Déclarer un répertoire et vouloir y écrire sont deux intentions (ch. 07)."""
    dossier = tmp_path / "lecture"
    dossier.mkdir()
    (dossier / "rapport.pdf").write_text("x", encoding="utf-8")
    monkeypatch.setenv(VARIABLE, f"lecture:{dossier}:ro")

    resultat = FileOrganizerAgent().perform(contexte())

    assert resultat["status"] == "read_only"
    assert resultat["proposals"] == []


def test_appliquer_sans_approbation_leve(racine):
    """
    La faute que cet agent existe pour rendre impossible : elle lève, elle
    n'échoue pas en silence.
    """
    agent = FileOrganizerAgent()
    ctx = contexte()
    plan = agent.perform(ctx)["proposals"]

    with pytest.raises(PermissionError):
        agent.apply_plan(ctx, plan, "req_jamais_approuvee")

    assert (racine / "rapport.pdf").exists()


def test_l_agent_est_suspendu_par_le_portillon(racine):
    """`run()` ne rend jamais `success` pour cet agent : il attend une décision."""
    resultat = FileOrganizerAgent().run(contexte())

    assert resultat["status"] == "requires_approval"
    assert resultat["approval_request_id"]


def test_un_plan_approuve_range_et_reste_annulable(racine):
    """Le chemin nominal, de bout en bout, avec l'annulation vérifiée."""
    agent = FileOrganizerAgent()
    ctx = contexte()
    suspendu = agent.run(ctx)
    demande = suspendu["approval_request_id"]
    ctx.approve_approval(demande, reason="revu", decided_by="operateur")

    applique = agent.apply_plan(ctx, suspendu["result"]["proposals"], demande)

    assert applique["status"] == "applied"
    assert (racine / "images" / "photo.jpg").exists()
    assert not (racine / "photo.jpg").exists()

    from src.storage.reversible import ReversibleFiles
    from src.storage.roots import declared_roots

    ReversibleFiles(declared_roots()).undo(applique["undo"][0])
    assert len(applique["undo"]) == len(applique["moved"])


def test_l_agent_ne_supprime_jamais_rien(racine):
    """Le maximum qu'un organisateur fait d'un fichier, c'est l'archiver."""
    plan = FileOrganizerAgent().perform(contexte())["proposals"]
    assert all(proposition["destination"] for proposition in plan)
    assert all("corbeille" not in proposition["destination"] for proposition in plan)


def test_les_categories_ne_se_chevauchent_pas():
    """Une extension dans deux catégories rendrait la destination dépendante de l'ordre."""
    vues = set()
    for extensions in CATEGORIES.values():
        collision = vues & set(extensions)
        assert collision == set(), f"Extensions dans deux catégories : {collision}"
        vues |= set(extensions)


# ----------------------------------------------------------------------
# 2. Le chef de projet
# ----------------------------------------------------------------------

PLAN = [
    {"id": "task_1", "description": "Analyser", "assigned_agent": "researcher"},
    {"id": "task_2", "description": "Écrire", "assigned_agent": "coder",
     "depends_on": "task_1"},
    {"id": "task_3", "description": "Relire", "assigned_agent": "reviewer",
     "depends_on": "task_2"},
]


def _contexte_avec_plan(resultats=None) -> AgentContext:
    """Contexte portant un plan du planificateur et des résultats d'agents."""
    precedents = [{"agent": "planner", "status": "success", "result": {"tasks": PLAN}}]
    precedents.extend(resultats or [])
    return AgentContext(
        request="suivre le projet", agent_id="project_manager",
        previous_results=precedents,
    )


def test_sans_plan_le_chef_de_projet_le_dit(monkeypatch):
    """Un rapport vide se lirait « rien à faire », ce qui n'est pas la même chose."""
    resultat = ProjectManagerAgent().perform(contexte("où en est-on"))

    assert resultat["status"] == "no_plan"
    assert resultat["tasks"] == []


def test_une_tache_dont_l_agent_n_a_pas_tourne_n_est_pas_faite():
    """La distinction qui empêche un rapport optimiste."""
    resultat = ProjectManagerAgent().perform(_contexte_avec_plan())

    assert resultat["done"] == 0
    assert resultat["not_started"] == 3


def test_un_agent_en_echec_bloque_sa_tache():
    resultat = ProjectManagerAgent().perform(_contexte_avec_plan([
        {"agent": "researcher", "status": "success", "result": {}},
        {"agent": "coder", "status": "error", "error": "aucun modèle disponible"},
    ]))

    assert resultat["done"] == 1
    assert resultat["blocked"] == 1
    assert resultat["blockers"][0]["task"] == "task_2"
    assert "modèle" in resultat["blockers"][0]["reason"]


def test_une_approbation_en_attente_passe_avant_le_reste():
    """Elle arrête tout le reste : la signaler en second serait la manquer."""
    resultat = ProjectManagerAgent().perform(_contexte_avec_plan([
        {"agent": "researcher", "status": "error", "error": "panne"},
        {"agent": "coder", "status": "requires_approval", "result": {}},
    ]))

    assert resultat["awaiting_approval"] == 1
    assert "Décider" in resultat["next_action"]


def test_la_prochaine_action_est_la_premiere_tache_non_commencee():
    resultat = ProjectManagerAgent().perform(_contexte_avec_plan([
        {"agent": "researcher", "status": "success", "result": {}},
    ]))

    assert "task_2" in resultat["next_action"]


def test_le_chef_de_projet_ne_produit_ni_delai_ni_pourcentage():
    """
    Aucun de ces chiffres n'existe dans la plateforme : les produire reviendrait
    à fabriquer un état de projet.
    """
    resultat = ProjectManagerAgent().perform(_contexte_avec_plan())

    serialise = str(resultat)
    assert "deadline" not in serialise and "percent" not in serialise
    assert len(resultat["not_reported"]) == 2


def test_une_tache_sans_agent_est_signalee():
    contexte_ = AgentContext(
        request="suivre", agent_id="project_manager",
        previous_results=[{
            "agent": "planner", "status": "success",
            "result": {"tasks": [{"id": "task_1", "description": "orpheline"}]},
        }],
    )

    resultat = ProjectManagerAgent().perform(contexte_)

    assert resultat["unassigned"] == ["task_1"]


# ----------------------------------------------------------------------
# 3. L'analyste d'opportunités
# ----------------------------------------------------------------------


class ContexteSourced(AgentContext):
    """Contexte dont les recherches rendent ce que le test décide."""

    def __init__(self, connaissances=None, web=None, **kwargs):
        super().__init__(request=kwargs.pop("request", "irrigation solaire au Sénégal"),
                         agent_id="opportunity", **kwargs)
        self._connaissances = connaissances or []
        self._web = web or []

    def search_knowledge(self, query, limit=5, role=None):
        """Rend les connaissances décidées par le test."""
        return self._connaissances

    def search_web(self, query, max_results=5, search_type="web"):
        """Rend les résultats web décidés par le test."""
        return self._web


def test_sans_aucune_source_l_analyste_refuse_de_conclure():
    """
    Le test le plus important du chapitre.

    Un agent d'analyse d'opportunités peut toujours produire une réponse
    assurée, structurée et entièrement inventée. Ici, l'absence de source
    produit un refus explicite, pas un paragraphe prudent qui ressemble à une
    analyse.
    """
    resultat = OpportunityAnalystAgent().perform(ContexteSourced())

    assert resultat["status"] == "insufficient_evidence"
    assert resultat["signals"] == []
    assert resultat["what_would_settle_it"]


def test_un_signal_porte_toujours_sa_source():
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(
        connaissances=[{"id": "kn_1", "content": "La filière maraîchère croît.",
                        "confidence": 0.8, "status": "approved", "domain": "agriculture"}],
    ))

    assert resultat["status"] == "grounded"
    assert resultat["signals"][0]["source"]["reference"] == "kn_1"
    assert resultat["signals"][0]["source"]["origin"] == "knowledge"


def test_une_connaissance_sans_identifiant_est_ecartee_et_comptee():
    """
    Citer sans permettre la vérification, c'est affirmer. L'écart est compté
    plutôt que silencieux.
    """
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(
        connaissances=[{"content": "Affirmation sans provenance."}],
    ))

    assert resultat["status"] == "insufficient_evidence"
    assert resultat["dropped_unsourced"] == 1


def test_un_resultat_web_sans_url_est_ecarte():
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(
        web=[{"title": "Un titre sans lien"}],
    ))

    assert resultat["dropped_unsourced"] == 1
    assert resultat["signals"] == []


def test_aucune_confiance_n_est_attribuee_a_un_resultat_web():
    """La plateforme n'a aucun moyen d'évaluer un site ; un score serait pris pour une mesure."""
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(
        web=[{"title": "Rapport 2026", "url": "https://exemple.sn/rapport"}],
    ))

    signal = resultat["signals"][0]
    assert signal["source"]["reference"] == "https://exemple.sn/rapport"
    assert signal["confidence_reported_by_source"] is None


def test_corrobore_veut_dire_plusieurs_origines_distinctes():
    """Et rien d'autre — surtout pas « c'est vrai »."""
    une_seule = OpportunityAnalystAgent().perform(ContexteSourced(
        connaissances=[{"id": "kn_1", "content": "Un fait."}],
    ))
    deux = OpportunityAnalystAgent().perform(ContexteSourced(
        connaissances=[{"id": "kn_1", "content": "Un fait."}],
        web=[{"title": "Le même fait", "url": "https://exemple.sn/a"}],
    ))

    assert une_seule["corroborated"] is False
    assert deux["corroborated"] is True


def test_l_analyste_ne_produit_ni_taille_de_marche_ni_projection():
    """Ce qu'il refuse est écrit dans la réponse, pour que l'absence soit une décision."""
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(
        connaissances=[{"id": "kn_1", "content": "Un fait sourcé."}],
    ))

    import re

    assert resultat["not_produced"] == list(NON_PRODUIT)
    serialise = str(resultat).lower()
    # Bornes de mot : sans elles, « roi » se trouve dans « croissance », et le
    # test échouait sur sa propre liste de refus.
    for interdit in ("market_size", "taille_de_marche", "revenue_projection", "roi", "tam"):
        assert re.search(rf"\b{interdit}\b", serialise) is None, f"« {interdit} » produit"


def test_le_mot_choisi_est_signal_et_non_opportunite():
    """
    Le vocabulaire est délibéré : l'agent rend ce que les sources disent, et
    laisse la conclusion à quelqu'un qui peut les peser.
    """
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(
        connaissances=[{"id": "kn_1", "content": "Un fait sourcé."}],
    ))

    assert "signals" in resultat
    assert "opportunities" not in resultat
    assert "pas une opportunité établie" in resultat["note"]


def test_une_demande_vide_ne_produit_pas_d_analyse():
    resultat = OpportunityAnalystAgent().perform(ContexteSourced(request="   "))

    assert resultat["status"] == "no_subject"


# ----------------------------------------------------------------------
# 4. Les trois sont réellement intégrés
# ----------------------------------------------------------------------


def test_les_trois_agents_sont_declares_au_registre():
    """Un agent absent du registre n'est joignable par aucun chemin."""
    import yaml

    racine_depot = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine_depot, "agents", "registry.yaml"), encoding="utf-8") as f:
        registre = yaml.safe_load(f)

    declares = {agent["id"]: agent for agent in registre["agents"]}
    for agent_id in ("organizer", "project_manager", "opportunity"):
        assert agent_id in declares, f"« {agent_id} » absent de agents/registry.yaml"
        assert declares[agent_id]["enabled"] is True
        assert declares[agent_id]["module"] == f"agents.{agent_id}.agent"


def test_les_trois_agents_repondent_par_leur_point_d_entree():
    """Le point d'entrée historique est ce que le répartiteur appelle."""
    import importlib

    for agent_id, attendu in (
        ("project_manager", "success"),
        ("opportunity", "success"),
        ("organizer", "requires_approval"),
    ):
        module = importlib.import_module(f"agents.{agent_id}.agent")
        resultat = module.execute("état du projet")
        assert resultat["agent"] == agent_id
        assert resultat["status"] == attendu, f"{agent_id} : {resultat.get('error')}"


# ----------------------------------------------------------------------
# 5. Joignables par le routeur, et pas seulement déclarés
# ----------------------------------------------------------------------


def test_le_workflow_suivi_enchaine_le_plan_puis_son_rapport():
    """
    L'ordre est une dépendance, pas une préférence : sans le plan, le chef de
    projet n'a rien à rapporter.
    """
    from src.router.router_engine import RouterEngine

    resultat = RouterEngine().process_request(
        "construire une page de contact", workflow_id="suivi"
    )

    agents = [(r.get("agent"), r.get("status")) for r in resultat["agent_results"]]
    assert agents == [("planner", "success"), ("project_manager", "success")]
    rapport = resultat["agent_results"][1]["result"]
    assert rapport["status"] == "reported"
    assert rapport["task_count"] > 0


def test_le_workflow_rangement_suspend_le_pipeline(racine):
    """
    Un agent qui déplace des fichiers arrête la chaîne tant qu'aucune personne
    n'a décidé — c'est ADR-006 appliqué au disque de quelqu'un.
    """
    from src.router.router_engine import RouterEngine

    resultat = RouterEngine().process_request("ranger mes fichiers", workflow_id="rangement")

    assert resultat["status"] == "requires_approval"
    assert sorted(os.listdir(racine)) == sorted(
        ["rapport.pdf", "photo.jpg", "notes.md", "archive.zip", "inconnu.xyz", "projets"]
    )


def test_un_chemin_absent_du_plan_est_refuse_meme_avec_une_approbation(racine, tmp_path):
    """
    L'approbation porte sur ce que l'agent propose, pas sur « l'agent range ».

    Sans cette borne, un appelant présentait une demande approuvée et lui
    faisait déplacer n'importe quel chemin — l'approbation devenait un blanc-seing.
    """
    agent = FileOrganizerAgent()
    ctx = contexte()
    suspendu = agent.run(ctx)
    demande = suspendu["approval_request_id"]
    ctx.approve_approval(demande, reason="revu", decided_by="operateur")

    applique = agent.apply_plan(ctx, [
        {"source": "documents/notes.md", "destination": "documents/ailleurs/notes.md"},
    ], demande)

    assert applique["moved"] == []
    assert "approbation ne couvre pas" in applique["refused"][0]["reason"]
    assert (racine / "notes.md").exists()
