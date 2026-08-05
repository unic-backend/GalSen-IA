"""
Tests unitaires de l'outil GitHub.

Aucun appel réseau n'est fait : `urllib.request.urlopen` est simulé. Les tests
couvrent la lecture du jeton depuis l'environnement (jamais depuis le code ni la
configuration), la résolution du dépôt visé, la mise en forme des réponses, et
la traduction des erreurs HTTP en messages exploitables — notamment le
dépassement de quota, que GitHub présente comme un simple 403.
"""

import io
import json
import time
import urllib.error
from unittest.mock import patch

import pytest

from src.tools.github.tool import GitHubTool


@pytest.fixture(autouse=True)
def environnement_sans_jeton(monkeypatch):
    """Retire tout jeton hérité de l'environnement réel."""
    for variable in GitHubTool.TOKEN_ENVIRONMENT_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


@pytest.fixture
def outil():
    """Outil GitHub avec un dépôt par défaut."""
    return GitHubTool({"default_repository": "unic-backend/galsen-ia"})


def _reponse(charge_utile):
    """Construit une réponse HTTP simulée, utilisable en gestionnaire de contexte."""
    corps = json.dumps(charge_utile).encode("utf-8")

    class ReponseSimulee(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exception):
            self.close()
            return False

    return ReponseSimulee(corps)


def _erreur_http(code, headers=None):
    """Construit une HTTPError simulée."""
    return urllib.error.HTTPError(
        url="https://api.github.com/test",
        code=code,
        msg="erreur",
        hdrs=headers or {},
        fp=io.BytesIO(b"{}"),
    )


class TestJeton:
    """Vérifie que le jeton vient de l'environnement et de nulle part ailleurs."""

    def test_aucun_jeton_par_defaut(self, outil):
        """Sans variable d'environnement, l'outil doit se déclarer anonyme."""
        assert outil.has_token() is False
        assert outil.execute("authenticated")["authenticated"] is False

    def test_jeton_lu_dans_l_environnement(self, outil, monkeypatch):
        """Un jeton présent dans GITHUB_TOKEN doit être détecté."""
        monkeypatch.setenv("GITHUB_TOKEN", "jeton-de-test")
        assert outil.has_token() is True
        etat = outil.execute("authenticated")
        assert etat["authenticated"] is True
        assert etat["token_environment_variable"] == "GITHUB_TOKEN"

    def test_variable_alternative_reconnue(self, outil, monkeypatch):
        """GH_TOKEN doit être accepté comme source de jeton."""
        monkeypatch.setenv("GH_TOKEN", "jeton-de-test")
        assert outil.has_token() is True

    def test_variable_personnalisee(self, monkeypatch):
        """Une variable déclarée en configuration doit primer."""
        monkeypatch.setenv("MON_JETON", "jeton-de-test")
        outil = GitHubTool({"token_env_var": "MON_JETON"})
        assert outil.has_token() is True

    def test_jeton_envoye_en_en_tete(self, outil, monkeypatch):
        """Le jeton doit partir en en-tête Authorization, jamais dans l'URL."""
        monkeypatch.setenv("GITHUB_TOKEN", "jeton-de-test")
        with patch("urllib.request.urlopen", return_value=_reponse({"resources": {}})) as appel:
            outil.execute("rate_limit")
        requete = appel.call_args[0][0]
        assert requete.get_header("Authorization") == "Bearer jeton-de-test"
        assert "jeton-de-test" not in requete.full_url

    def test_aucun_en_tete_authorization_sans_jeton(self, outil):
        """Sans jeton, aucune en-tête d'authentification ne doit être envoyée."""
        with patch("urllib.request.urlopen", return_value=_reponse({"resources": {}})) as appel:
            outil.execute("rate_limit")
        assert appel.call_args[0][0].get_header("Authorization") is None

    def test_authenticated_ne_fait_aucun_appel_reseau(self, outil):
        """L'état d'authentification doit être connu sans consommer de quota."""
        with patch("urllib.request.urlopen") as appel:
            outil.execute("authenticated")
        appel.assert_not_called()


class TestResolutionDuDepot:
    """Vérifie la validation du dépôt visé."""

    def test_depot_par_defaut_utilise(self, outil):
        """Sans argument, le dépôt configuré doit être interrogé."""
        with patch("urllib.request.urlopen", return_value=_reponse({"full_name": "x/y"})) as appel:
            outil.execute("repository")
        assert "/repos/unic-backend/galsen-ia" in appel.call_args[0][0].full_url

    def test_depot_absent_refuse(self):
        """Sans dépôt configuré ni fourni, l'appel doit être refusé."""
        with pytest.raises(ValueError, match="Aucun dépôt indiqué"):
            GitHubTool().execute("repository")

    @pytest.mark.parametrize("invalide", ["sans-slash", "trop/de/slashs", "/nom", "proprietaire/"])
    def test_format_de_depot_invalide(self, outil, invalide):
        """Un dépôt mal formé doit être refusé avant tout appel réseau."""
        with pytest.raises(ValueError, match="Dépôt invalide"):
            outil.execute("repository", invalide)


class TestMiseEnForme:
    """Vérifie que les réponses de l'API sont réduites à l'essentiel."""

    def test_repository_resume_les_champs_utiles(self, outil):
        """Seuls les champs utiles doivent être retournés."""
        charge = {
            "full_name": "unic-backend/galsen-ia",
            "description": "Plateforme IA",
            "default_branch": "main",
            "language": "Python",
            "stargazers_count": 12,
            "forks_count": 3,
            "open_issues_count": 4,
            "private": False,
            "html_url": "https://github.com/unic-backend/galsen-ia",
            "updated_at": "2026-08-05T10:00:00Z",
            "champ_inutile": "ignoré",
        }
        with patch("urllib.request.urlopen", return_value=_reponse(charge)):
            resultat = outil.execute("repository")
        assert resultat["full_name"] == "unic-backend/galsen-ia"
        assert resultat["stars"] == 12
        assert "champ_inutile" not in resultat

    def test_issues_ecarte_les_pull_requests(self, outil):
        """L'API mélange issues et pull requests : ces dernières doivent être exclues."""
        charge = [
            {"number": 1, "title": "Vrai ticket"},
            {"number": 2, "title": "Une PR", "pull_request": {"url": "..."}},
        ]
        with patch("urllib.request.urlopen", return_value=_reponse(charge)):
            resultats = outil.execute("issues")
        assert len(resultats) == 1
        assert resultats[0]["number"] == 1

    def test_issues_transmet_les_filtres(self, outil):
        """L'état et la limite demandés doivent partir dans la requête."""
        with patch("urllib.request.urlopen", return_value=_reponse([])) as appel:
            outil.execute("issues", state="closed", limit=5)
        url = appel.call_args[0][0].full_url
        assert "state=closed" in url
        assert "per_page=5" in url

    def test_limite_plafonnee_a_cent(self, outil):
        """Une limite excessive doit être ramenée au maximum de l'API."""
        with patch("urllib.request.urlopen", return_value=_reponse([])) as appel:
            outil.execute("issues", limit=5000)
        assert "per_page=100" in appel.call_args[0][0].full_url

    def test_commits_extrait_la_premiere_ligne_du_message(self, outil):
        """Le message de commit doit être réduit à son sujet."""
        charge = [{
            "sha": "abc123",
            "html_url": "https://github.com/x/y/commit/abc123",
            "commit": {
                "message": "feat: ajoute le moteur\n\nDescription longue",
                "author": {"name": "Awa", "date": "2026-08-05T10:00:00Z"},
            },
        }]
        with patch("urllib.request.urlopen", return_value=_reponse(charge)):
            commits = outil.execute("commits")
        assert commits[0]["message"] == "feat: ajoute le moteur"
        assert commits[0]["author"] == "Awa"

    def test_rate_limit(self, outil):
        """Le quota doit être extrait de la ressource `core`."""
        charge = {"resources": {"core": {"limit": 60, "remaining": 42, "reset": 1785900000}}}
        with patch("urllib.request.urlopen", return_value=_reponse(charge)):
            quota = outil.execute("rate_limit")
        assert quota["limit"] == 60
        assert quota["remaining"] == 42
        assert quota["authenticated"] is False

    def test_search_repositories_refuse_une_requete_vide(self, outil):
        """Une recherche vide doit être refusée avant l'appel réseau."""
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            outil.execute("search_repositories", "   ")


class TestErreurs:
    """Vérifie la traduction des erreurs réseau en messages exploitables."""

    def test_404_devient_ressource_introuvable(self, outil):
        """Un 404 doit dire ce qui est introuvable."""
        with patch("urllib.request.urlopen", side_effect=_erreur_http(404)):
            with pytest.raises(RuntimeError, match="introuvable"):
                outil.execute("repository")

    def test_401_signale_un_jeton_invalide(self, outil):
        """Un 401 doit pointer le jeton, pas les droits."""
        with patch("urllib.request.urlopen", side_effect=_erreur_http(401)):
            with pytest.raises(RuntimeError, match="Jeton GitHub invalide"):
                outil.execute("repository")

    def test_403_avec_quota_epuise_est_distingue(self, outil):
        """Un dépassement de quota ne doit pas être confondu avec un refus d'accès."""
        reset = {"X-RateLimit-Reset": str(int(time.time()) + 120)}
        with patch("urllib.request.urlopen", side_effect=_erreur_http(403, reset)):
            with pytest.raises(RuntimeError, match="Quota GitHub dépassé"):
                outil.execute("repository")

    def test_403_sans_quota_reste_un_refus(self, outil):
        """Un 403 sans en-tête de quota doit rester un refus d'accès."""
        with patch("urllib.request.urlopen", side_effect=_erreur_http(403)):
            with pytest.raises(RuntimeError, match="Accès GitHub refusé"):
                outil.execute("repository")

    def test_panne_reseau(self, outil):
        """Une panne réseau doit être signalée sans trace technique brute."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("réseau coupé")):
            with pytest.raises(RuntimeError, match="Appel GitHub impossible"):
                outil.execute("repository")

    def test_reponse_illisible(self, outil):
        """Une réponse non JSON doit être signalée comme illisible."""

        class ReponseCassee(io.BytesIO):
            def __enter__(self):
                return self

            def __exit__(self, *exception):
                return False

        with patch("urllib.request.urlopen", return_value=ReponseCassee(b"pas du json")):
            with pytest.raises(RuntimeError, match="illisible"):
                outil.execute("repository")


class TestContratOutil:
    """Vérifie le contrat commun et l'absence d'opérations d'écriture."""

    def test_operation_inconnue(self, outil):
        """Une opération inconnue doit lister les opérations disponibles."""
        with pytest.raises(ValueError, match="Opérations disponibles"):
            outil.execute("supprimer_le_depot")

    def test_operation_manquante(self, outil):
        """Appeler l'outil sans opération doit être refusé."""
        with pytest.raises(ValueError, match="Une opération est requise"):
            outil.execute()

    def test_aucune_operation_d_ecriture(self, outil):
        """L'outil doit rester en lecture seule : écrire sur GitHub reste humain."""
        operations = set(outil.available_operations())
        interdites = {"create_issue", "merge", "close_issue", "comment", "delete"}
        assert operations & interdites == set()
        assert {"repository", "issues", "pull_requests", "commits"} <= operations
