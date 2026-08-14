"""
Le pilote de bout en bout (ADR-021, étape 10).

Ce test fait tourner **les neuf étapes enchaînées** contre un serveur de la
boucle locale : découverte, décision, approbation, récupération, barrière,
contrôles, proposition. Aucun hôte tiers n'est appelé.

Ce qu'il garde surtout : le pilote **ne s'approuve pas lui-même**, et il
**n'ingère rien**.
"""

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from scripts.acquisition_pilot import phase_plan, phase_run  # noqa: E402
from src.approval_engine.approval_manager import ApprovalManagerImpl  # noqa: E402
from src.knowledge_engine.source_registry import load_registry  # noqa: E402

CORPS = ("La production de mil dans la région de Kaolack a progressé pendant la "
         "campagne agricole. Les services de l'agriculture ont relevé une hausse "
         "des surfaces emblavées et une amélioration des rendements sur les "
         "parcelles suivies par les équipes du ministère. ")

PAGE_A = (f"<html><head><title>Note sur le mil</title>"
          f"<meta name=\"dc.date.issued\" content=\"2024-03-15\">"
          f"</head><body><p>{CORPS * 3}</p></body></html>").encode("utf-8")

PAGE_B = (f"<html><head><title>Note sur l'arachide</title>"
          f"<meta name=\"dc.date.issued\" content=\"2024-06-01\">"
          f"</head><body><p>{CORPS.replace('mil', 'arachide') * 3}"
          f"<span>Les surfaces de cette filière sont suivies séparément par les "
          f"services régionaux compétents depuis la dernière campagne.</span>"
          f"</p></body></html>").encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    """Une institution minimale : un robots.txt, un plan de site, deux notes."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: D102 — silence pendant les tests
        pass

    def _repondre(self, code, corps=b"", mime=""):
        self.send_response(code)
        if mime:
            self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(corps)))
        self.end_headers()
        if corps:
            self.wfile.write(corps)

    def do_GET(self):  # noqa: N802 — imposé par http.server
        base = f"http://127.0.0.1:{self.server.server_port}"
        if self.path == "/robots.txt":
            return self._repondre(
                200,
                f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n".encode("utf-8"),
                "text/plain",
            )
        if self.path == "/sitemap.xml":
            plan = (
                '<?xml version="1.0"?><urlset '
                'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"<url><loc>{base}/mil.html</loc></url>"
                f"<url><loc>{base}/arachide.html</loc></url>"
                "<url><loc>https://ailleurs.example/copie.html</loc></url>"
                "</urlset>"
            ).encode("utf-8")
            return self._repondre(200, plan, "application/xml")
        if self.path == "/mil.html":
            return self._repondre(200, PAGE_A, "text/html")
        if self.path == "/arachide.html":
            return self._repondre(200, PAGE_B, "text/html")
        return self._repondre(404, b"", "text/plain")


@pytest.fixture
def serveur():
    """L'institution de test, arrêtée à la fin."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def registre(tmp_path, serveur):
    """Un registre d'une source **activée**, pointant sur le serveur local."""
    chemin = tmp_path / "registre.yaml"
    chemin.write_text(
        "sources:\n"
        '  - name: "Institut de test"\n'
        f"    base_url: http://127.0.0.1:{serveur.server_port}\n"
        "    scope: country:sn\n"
        "    subjects: [agriculture]\n"
        "    category: government\n"
        "    tier: TIER_A_PRIMARY_OFFICIAL\n"
        "    allowed_content_types: [html, xml]\n"
        "    access_policy:\n"
        "      rate_limit_rps: 1000.0\n"
        '    last_verified: "2026-08-14"\n'
        "    enabled: true\n"
        "deny: []\n",
        encoding="utf-8",
    )
    return load_registry(str(chemin))


@pytest.fixture
def manager(monkeypatch, tmp_path):
    """Gestionnaire d'approbations isolé."""
    monkeypatch.setenv("GALSEN_STORAGE_BACKEND", "in-memory")
    monkeypatch.setenv("GALSEN_DATA_DIR", str(tmp_path))
    return ApprovalManagerImpl()


# ----------------------------------------------------------------------
# Le chemin complet
# ----------------------------------------------------------------------

def test_le_pilote_va_de_la_decouverte_a_la_proposition(registre, manager):
    """
    Les neuf étapes enchaînées. C'est la démonstration que la chaîne existe —
    pas qu'elle passe à l'échelle.
    """
    plan = phase_plan(registre, manager)

    assert plan["ready"] is True
    assert plan["candidates"] == 2, "Le lien hors domaine aurait dû être écarté"
    assert any("ailleurs.example" in e["url"] for e in plan["dropped_at_discovery"])

    manager.approve(plan["approval_id"], decided_by="proprietaire")
    resultat = phase_run(registre, manager, plan["approval_id"])

    assert resultat["ready"] is True
    assert resultat["fetched"] == 2
    assert resultat["manifest"]["proposed"] >= 1
    assert resultat["ingested"] == 0, "Le pilote a ingéré quelque chose"


def test_la_proposition_porte_ce_que_le_registre_declare(registre, manager):
    """L'autorité vient du registre, jusque dans le manifeste proposé."""
    plan = phase_plan(registre, manager)
    manager.approve(plan["approval_id"], decided_by="proprietaire")

    entrees = phase_run(registre, manager, plan["approval_id"])["manifest"]["entries"]

    assert entrees, "Aucune entrée proposée"
    entree = entrees[0]
    assert entree["author"] == "Institut de test"
    assert entree["scope"] == "country:sn"
    assert entree["subject"] == "agriculture"
    assert entree["status"] == "DRAFT"
    assert entree["language"] == "fr"


# ----------------------------------------------------------------------
# Ce que le pilote ne peut pas faire
# ----------------------------------------------------------------------

def test_sans_approbation_rien_n_est_recupere(registre, manager):
    """Le portillon est entre les deux commandes, et il tient."""
    plan = phase_plan(registre, manager)

    resultat = phase_run(registre, manager, plan["approval_id"])

    assert resultat["ready"] is False
    assert "pending" in resultat["reason"]


def test_le_pilote_ne_s_approuve_pas_lui_meme():
    """
    La garantie la plus importante du script : il ne touche jamais au statut
    d'une demande. Cherché dans l'arbre syntaxique, pas dans le texte.
    """
    import ast

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "scripts", "acquisition_pilot.py"), encoding="utf-8") as f:
        arbre = ast.parse(f.read())

    appels = {
        noeud.func.attr for noeud in ast.walk(arbre)
        if isinstance(noeud, ast.Call) and isinstance(noeud.func, ast.Attribute)
    }

    assert "approve" not in appels
    assert "reject" not in appels


def test_le_pilote_n_ingere_rien():
    """Il s'arrête sur une proposition en DRAFT ; l'ingestion est un autre geste."""
    import ast

    racine = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(racine, "scripts", "acquisition_pilot.py"), encoding="utf-8") as f:
        arbre = ast.parse(f.read())

    noms = {
        noeud.attr if isinstance(noeud, ast.Attribute) else noeud.id
        for noeud in ast.walk(arbre)
        if isinstance(noeud, (ast.Attribute, ast.Name))
    }

    for interdit in ("ingest_file", "ingest_directory", "DocumentIngestor"):
        assert interdit not in noms, f"Le pilote ingère via {interdit}"


def test_une_approbation_ne_couvre_pas_un_lot_qui_a_change(registre, manager, serveur):
    """
    La raison pour laquelle `run` refait la découverte au lieu de relire un état
    sur disque : si le site a publié entre-temps, l'accord ne porte plus sur ce
    qu'on s'apprête à récupérer.
    """
    plan = phase_plan(registre, manager)
    manager.approve(plan["approval_id"], decided_by="proprietaire")

    # Le site publie un troisième document entre les deux commandes.
    original = _Handler.do_GET

    def _avec_un_document_de_plus(self):
        base = f"http://127.0.0.1:{self.server.server_port}"
        if self.path == "/sitemap.xml":
            plan_xml = (
                '<?xml version="1.0"?><urlset '
                'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
                f"<url><loc>{base}/mil.html</loc></url>"
                f"<url><loc>{base}/arachide.html</loc></url>"
                f"<url><loc>{base}/nouveau.html</loc></url>"
                "</urlset>"
            ).encode("utf-8")
            return self._repondre(200, plan_xml, "application/xml")
        return original(self)

    _Handler.do_GET = _avec_un_document_de_plus
    try:
        resultat = phase_run(registre, manager, plan["approval_id"])
    finally:
        _Handler.do_GET = original

    assert resultat["ready"] is False
    assert "ne porte pas sur ce lot" in resultat["reason"]


# ----------------------------------------------------------------------
# L'état réel du dépôt
# ----------------------------------------------------------------------

def test_sur_le_vrai_registre_le_pilote_s_arrete_faute_de_source_activee(manager):
    """
    Ce n'est pas une panne : c'est « inscrire n'est pas activer » qui s'applique,
    et le message dit quoi faire.
    """
    rapport = phase_plan(load_registry(), manager)

    assert rapport["ready"] is False
    assert rapport["acquirable"] == 0
    assert rapport["registered"] == 23
    assert "enabled: true" in rapport["reason"]
