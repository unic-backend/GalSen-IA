"""
Le récupérateur : poli, véridique, borné (ADR-021, étape 3).

**Aucun hôte tiers n'est appelé par ces tests.** Ils montent un serveur sur la
boucle locale : c'est la seule façon d'exercer vraiment HTTP — codes, en-têtes,
redirections, 304 — sans faire porter les tests par l'institution d'en face.
"""

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.acquisition.fetcher import (  # noqa: E402
    MARQUES_DE_DEGUISEMENT,
    FetchRefused,
    HostRateLimiter,
    fetch,
    fetch_robots,
    fetcher_report,
    user_agent,
)

ROBOTS = b"User-agent: *\nDisallow: /prive/\nAllow: /prive/public/\n"
PDF = b"%PDF-1.4 contenu de test " + b"x" * 500


class _Handler(BaseHTTPRequestHandler):
    """Sert juste assez pour exercer chaque règle du récupérateur."""

    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # noqa: D102 — silence pendant les tests
        pass

    def _repondre(self, code: int, corps: bytes = b"", type_mime: str = "", **entetes):
        self.send_response(code)
        if type_mime:
            self.send_header("Content-Type", type_mime)
        self.send_header("Content-Length", str(len(corps)))
        for nom, valeur in entetes.items():
            self.send_header(nom.replace("_", "-"), valeur)
        self.end_headers()
        if corps:
            self.wfile.write(corps)

    def do_GET(self):  # noqa: N802 — imposé par http.server
        chemin = self.path
        self.server.agents_recus.append(self.headers.get("User-Agent", ""))

        if chemin == "/robots.txt":
            return self._repondre(200, ROBOTS, "text/plain")
        if chemin == "/rapport.pdf":
            if self.headers.get("If-None-Match") == '"v1"':
                return self._repondre(304)
            return self._repondre(200, PDF, "application/pdf", ETag='"v1"')
        if chemin == "/page.html":
            return self._repondre(200, b"<html>ok</html>", "text/html")
        if chemin == "/enorme.pdf":
            return self._repondre(200, b"y" * 40000, "application/pdf")
        if chemin == "/prive/secret.pdf":
            return self._repondre(200, PDF, "application/pdf")
        if chemin == "/ailleurs":
            hote = "localhost" if "127.0.0.1" in self.headers.get("Host", "") else "127.0.0.1"
            return self._repondre(302, b"", "", Location=f"http://{hote}:{self.server.server_port}/page.html")
        if chemin == "/interne":
            return self._repondre(302, b"", "", Location="/page.html")
        return self._repondre(404, b"", "text/plain")


@pytest.fixture
def serveur():
    """Un serveur local, arrêté à la fin du test."""
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    httpd.agents_recus = []
    fil = threading.Thread(target=httpd.serve_forever, daemon=True)
    fil.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def base(serveur):
    """L'adresse du serveur local."""
    return f"http://127.0.0.1:{serveur.server_port}"


@pytest.fixture(autouse=True)
def debit_rapide(monkeypatch):
    """Les tests n'ont pas à attendre la politesse ; la règle est testée à part."""
    monkeypatch.setattr("src.acquisition.fetcher.DEBIT_PAR_DEFAUT", 1000.0)


# ----------------------------------------------------------------------
# L'agent — le défaut que cette étape corrige
# ----------------------------------------------------------------------

@pytest.mark.parametrize("deguisement", [
    "Mozilla/5.0 (Windows NT 10.0) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 Firefox/120",
    "GalSen/1.0 AppleWebKit/537",
])
def test_un_agent_qui_se_deguise_en_navigateur_est_refuse(monkeypatch, deguisement, base):
    """
    Le cœur de l'étape. Un site ne peut pas appliquer une règle à un agent
    déguisé : `robots.txt` devient un mot vide avant même d'être lu.
    """
    monkeypatch.setenv("GALSEN_ACQUISITION_USER_AGENT", deguisement)

    with pytest.raises(FetchRefused) as echec:
        fetch(f"{base}/rapport.pdf", allowed_content_types=["pdf"], rate_limit_rps=1000)

    assert "navigateur" in str(echec.value)


def test_l_agent_par_defaut_dit_ce_qu_il_est_et_ou_ecrire(base, serveur):
    """Véridique par construction : un nom, une version, un contact."""
    fetch(f"{base}/rapport.pdf", allowed_content_types=["pdf"], rate_limit_rps=1000)

    annonce = serveur.agents_recus[-1]
    assert annonce == user_agent()
    assert "GalSenIA" in annonce and "+http" in annonce
    assert not any(marque in annonce.lower() for marque in MARQUES_DE_DEGUISEMENT)


# ----------------------------------------------------------------------
# robots.txt — récupéré avant, appliqué
# ----------------------------------------------------------------------

def test_robots_est_recupere_avant_la_page_et_applique(base):
    """
    Non fourni, il est **récupéré**, jamais supposé permissif. Et il est
    appliqué : un chemin interdit refuse la collecte.
    """
    with pytest.raises(FetchRefused) as echec:
        fetch(f"{base}/prive/secret.pdf", allowed_content_types=["pdf"], rate_limit_rps=1000)

    assert "robots.txt" in str(echec.value)


def test_la_regle_allow_la_plus_specifique_gagne(base):
    """
    `Allow: /prive/public/` bat `Disallow: /prive/`. Lire le fichier à moitié
    refuserait une ressource explicitement ouverte.
    """
    interdit = fetch_robots(base)

    assert "Disallow: /prive/" in interdit
    # Le chemin autorisé passe le filtre : il échoue en 404, pas en refus.
    with pytest.raises(FetchRefused) as echec:
        fetch(f"{base}/prive/public/x.pdf", allowed_content_types=["pdf"], rate_limit_rps=1000)
    assert "robots.txt" not in str(echec.value)


def test_un_robots_absent_n_interdit_rien(base, monkeypatch):
    """C'est sa sémantique : inventer une interdiction fermerait une source ouverte."""
    resultat = fetch(
        f"{base}/page.html", allowed_content_types=["html"],
        robots_txt="", rate_limit_rps=1000,
    )

    assert resultat.status == 200


# ----------------------------------------------------------------------
# Les bornes
# ----------------------------------------------------------------------

def test_un_type_non_declare_est_refuse(base):
    """Une liste vide veut dire « rien n'est permis », pas « tout »."""
    with pytest.raises(FetchRefused) as vide:
        fetch(f"{base}/page.html", allowed_content_types=[], robots_txt="", rate_limit_rps=1000)
    assert "rien n'est permis" in str(vide.value)

    with pytest.raises(FetchRefused) as mauvais:
        fetch(f"{base}/page.html", allowed_content_types=["pdf"], robots_txt="", rate_limit_rps=1000)
    assert "non autorisé" in str(mauvais.value)


def test_un_document_trop_gros_est_refuse_pas_tronque(base):
    """Un document tronqué ment sur son contenu ; le refuser dit la vérité."""
    with pytest.raises(FetchRefused) as echec:
        fetch(
            f"{base}/enorme.pdf", allowed_content_types=["pdf"], robots_txt="",
            max_bytes=1000, rate_limit_rps=1000,
        )

    assert "plafond" in str(echec.value)


def test_une_redirection_hors_du_domaine_est_refusee(base):
    """
    Sans cette règle, la limite « même domaine » se franchit sans qu'aucune ligne
    du projet ne la franchisse : le serveur redirige, la bibliothèque suit.
    """
    with pytest.raises(FetchRefused) as echec:
        fetch(f"{base}/ailleurs", allowed_content_types=["html"], robots_txt="", rate_limit_rps=1000)

    assert "hors du domaine" in str(echec.value)


def test_une_redirection_interne_est_suivie(base):
    """La contrepartie : refuser toute redirection casserait des sites ordinaires."""
    resultat = fetch(
        f"{base}/interne", allowed_content_types=["html"], robots_txt="", rate_limit_rps=1000
    )

    assert resultat.status == 200
    assert b"ok" in resultat.body


def test_http_en_clair_est_refuse_hors_boucle_locale():
    """L'exception est bornée par l'adresse, pas par un drapeau d'appelant."""
    with pytest.raises(FetchRefused) as echec:
        fetch("http://www.ansd.sn/x.pdf", allowed_content_types=["pdf"], robots_txt="")

    assert "HTTPS" in str(echec.value)


# ----------------------------------------------------------------------
# Le GET conditionnel et le débit
# ----------------------------------------------------------------------

def test_un_document_inchange_coute_un_304_et_rien_d_autre(base):
    """C'est ce qui rend la ré-acquisition supportable pour le site d'en face."""
    premier = fetch(
        f"{base}/rapport.pdf", allowed_content_types=["pdf"], robots_txt="", rate_limit_rps=1000
    )
    second = fetch(
        f"{base}/rapport.pdf", allowed_content_types=["pdf"], robots_txt="",
        etag=premier.etag, rate_limit_rps=1000,
    )

    assert premier.status == 200 and premier.size == len(PDF)
    assert second.status == 304
    assert second.unchanged is True
    assert second.body == b""


def test_le_debit_est_par_hote_et_non_global():
    """
    Un débit global ralentirait tout le monde pour ménager un seul site. Ce test
    mesure l'attente réelle, il ne lit pas la configuration.
    """
    limiteur = HostRateLimiter()

    assert limiteur.wait("a.sn", 1000.0) == 0.0, "La première requête ne doit pas attendre"
    assert limiteur.wait("b.sn", 1000.0) == 0.0, "Un autre hôte n'hérite pas de l'attente"
    assert limiteur.wait("a.sn", 1000.0) > 0.0, "Le même hôte doit attendre"


def test_un_debit_nul_refuse_au_lieu_de_boucler():
    """Zéro requête par seconde n'est pas « très lent » : c'est un refus."""
    with pytest.raises(FetchRefused):
        HostRateLimiter().wait("a.sn", 0.0)


def test_le_rapport_dit_ce_qui_est_applique():
    """Vérifiable sans lire le code — et l'agent y figure tel qu'il sera annoncé."""
    rapport = fetcher_report()

    assert rapport["https_required"] is True
    assert rapport["cross_domain_redirects"] == "refused"
    assert "fetched before the page" in rapport["robots_txt"]
    assert "GalSenIA" in rapport["user_agent"]
