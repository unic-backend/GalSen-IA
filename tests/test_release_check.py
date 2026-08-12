"""
Tests de la liste de contrôle de publication (VOLET_04 ch. 03).

Ce script décide si une version peut sortir. Un contrôle qui répond « ok » sans
rien vérifier est pire que pas de contrôle du tout : il transforme une vérification
en formalité. Ces tests portent donc surtout sur les cas d'**échec** — chaque
contrôle doit savoir dire non.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts import release_check  # noqa: E402
from scripts.release_check import (  # noqa: E402
    ALERTE,
    ECHEC,
    OK,
    controler_changelog,
    controler_demarrage,
    controler_documentation,
    controler_etiquette,
    controler_secrets,
    controler_suite,
    controler_version,
    controles,
    main,
)


class TestVersion:
    """Le contrôle de version est le premier rempart contre une divergence."""

    def test_version_coherente(self):
        """L'état actuel du dépôt doit passer."""
        assert controler_version().niveau == OK

    def test_divergence_dockerfile_refusee(self, monkeypatch):
        """C'est la divergence réelle qui a motivé src/version.py : 0.1.0 / 0.2.0."""
        monkeypatch.setattr(release_check, "_lire", lambda _: "ARG GALSEN_VERSION=9.9.9\n")
        resultat = controler_version()
        assert resultat.niveau == ECHEC
        assert "9.9.9" in resultat.detail

    def test_dockerfile_sans_argument_refuse(self, monkeypatch):
        """Sans l'argument, l'étiquette redeviendrait une seconde source."""
        monkeypatch.setattr(release_check, "_lire", lambda _: "FROM python:3.11-slim\n")
        assert controler_version().niveau == ECHEC

    def test_version_mal_formee_refusee(self, monkeypatch):
        """« 1.0 » n'est pas comparable : le versionnage sémantique exige trois nombres."""
        monkeypatch.setattr(release_check, "__version__", "1.0")
        assert controler_version().niveau == ECHEC

    def test_majeure_non_nulle_refusee_pour_un_prototype(self, monkeypatch):
        """Annoncer 1.0.0 engage la compatibilité : un prototype ne le peut pas."""
        monkeypatch.setattr(release_check, "__version__", "1.0.0")
        monkeypatch.setattr(release_check, "__release_type__", "prototype")
        # Le Dockerfile doit suivre, sinon c'est la divergence qui est signalée
        # en premier et le test ne prouverait pas ce qu'il annonce.
        monkeypatch.setattr(release_check, "_lire", lambda _: "ARG GALSEN_VERSION=1.0.0\n")
        resultat = controler_version()
        assert resultat.niveau == ECHEC
        assert "majeure" in resultat.detail


class TestEtiquette:
    """Republier une version déjà étiquetée détruit la traçabilité."""

    def test_version_libre(self, monkeypatch):
        """Une version non encore étiquetée passe le contrôle.

        Les étiquettes du dépôt sont remplacées : ce test affirmait « aucune
        étiquette n'existe encore », ce qui a cessé d'être vrai le jour où
        `v0.1.0` a été posée. Un test qui dépend de l'état du dépôt mesure le
        dépôt, pas le contrôle.
        """
        monkeypatch.setattr(release_check, "_git", lambda *_: "v0.0.1\nv0.0.2")
        assert controler_etiquette().niveau == OK

    def test_l_etiquette_de_la_version_courante_existe_bien(self):
        """La v0.1.0 a été publiée : le contrôle doit la voir dans le dépôt.

        Ce test échouait en CI pour **deux** raisons distinctes, et seule la
        première a été corrigée ici : le checkout ne récupérait aucune étiquette
        (`fetch-depth: 0` désormais). La seconde reste vraie et doit le rester —
        **l'étiquette n'a jamais été poussée** ; elle n'existe que dans le clone
        de l'auteur. Le message le dit, pour que l'échec envoie au bon endroit
        au lieu de faire chercher une régression.
        """
        etiquettes = release_check._git("tag", "--list")
        if etiquettes is None:  # git indisponible : rien à prouver ici
            pytest.skip("git indisponible")
        assert "v0.1.0" in etiquettes.splitlines(), (
            "L'étiquette v0.1.0 est absente de ce clone. Si la suite tourne en "
            "CI, c'est qu'elle n'a jamais été poussée : `git push origin v0.1.0` "
            "depuis un clone normal (le mandataire de l'environnement de "
            "développement refuse les étiquettes)."
        )

    def test_version_deja_etiquetee_refusee(self, monkeypatch):
        """Si `v0.1.0` existe, il faut incrémenter avant de publier."""
        monkeypatch.setattr(
            release_check, "_git",
            lambda *a: f"v{release_check.__version__}" if a[0] == "tag" else "",
        )
        resultat = controler_etiquette()
        assert resultat.niveau == ECHEC
        assert "existe déjà" in resultat.detail

    def test_git_absent_alerte_sans_bloquer(self, monkeypatch):
        """Un git indisponible n'est pas une raison de refuser : c'est une réserve."""
        monkeypatch.setattr(release_check, "_git", lambda *a: None)
        assert controler_etiquette().niveau == ALERTE


class TestSecrets:
    """Le contrôle de sécurité du chapitre 03, ramené à ce qui est vérifiable."""

    def test_depot_propre(self):
        """L'état actuel du dépôt ne suit ni secret ni base."""
        assert controler_secrets().niveau == OK

    @pytest.mark.parametrize(
        "fichier", [".env", "config/.env.production", "data/service_files.sqlite", "certs/tls.key"]
    )
    def test_fichier_interdit_detecte(self, monkeypatch, fichier):
        """Un `.env`, une base ou une clé suivis bloquent la publication."""
        monkeypatch.setattr(release_check, "_git", lambda *a: f"README.md\n{fichier}")
        resultat = controler_secrets()
        assert resultat.niveau == ECHEC
        assert fichier in resultat.detail

    def test_exemple_autorise(self, monkeypatch):
        """`.env.example` ne contient aucune valeur : il doit être suivi."""
        monkeypatch.setattr(release_check, "_git", lambda *a: "README.md\n.env.example")
        assert controler_secrets().niveau == OK


class TestChangelog:
    """Publier sans note de version rend l'historique inutilisable."""

    def test_section_presente_et_remplie(self):
        """Le journal actuel porte des entrées non publiées."""
        assert controler_changelog().niveau == OK

    def test_section_absente_refusee(self, monkeypatch):
        monkeypatch.setattr(release_check, "_lire", lambda _: "# Changelog\n")
        assert controler_changelog().niveau == ECHEC

    def test_section_vide_refusee(self, monkeypatch):
        """Rien à publier n'est pas une version : c'est un rien."""
        monkeypatch.setattr(
            release_check, "_lire", lambda _: "# Changelog\n\n## [Unreleased]\n\n## [0.0.1]\n- x\n"
        )
        resultat = controler_changelog()
        assert resultat.niveau == ECHEC
        assert "vide" in resultat.detail


class TestDocumentation:
    """Les documents que le chapitre exige à jour doivent au moins exister."""

    def test_documents_presents(self):
        assert controler_documentation().niveau == OK

    def test_document_manquant_refuse(self, monkeypatch):
        monkeypatch.setattr(release_check, "_lire", lambda _: "")
        resultat = controler_documentation()
        assert resultat.niveau == ECHEC
        assert "overview.md" in resultat.detail


class TestDemarrage:
    """Une version qui ne démarre pas ne se publie pas."""

    def test_l_application_demarre(self):
        """`degraded` est une alerte, pas un refus : aucun fournisseur n'est configuré."""
        assert controler_demarrage().niveau in (OK, ALERTE)


class TestSuite:
    """La suite est le contrôle des défauts critiques."""

    def test_ignoree_explicitement_alerte(self):
        """Sauter les tests ne doit jamais passer pour un succès."""
        resultat = controler_suite(ignorer=True)
        assert resultat.niveau == ALERTE
        assert "à lancer" in resultat.detail


class TestListe:
    """La liste elle-même, et son verdict."""

    def test_chaque_controle_est_rattache_a_une_exigence(self):
        """Un contrôle sans exigence du chapitre n'a pas à être là."""
        for controle in controles(sans_tests=True):
            assert controle.exigence.strip(), controle.nom
            assert controle.nom.strip()

    def test_les_points_humains_ne_sont_pas_cochables(self):
        """Ils sont affichés, jamais évalués : c'est le sujet de ce fichier."""
        assert release_check.CONFIRMATIONS_HUMAINES
        for titre, explication in release_check.CONFIRMATIONS_HUMAINES:
            assert titre and explication

    def test_un_echec_bloque_la_publication(self, monkeypatch, capsys):
        """Le code de sortie doit refléter le verdict, sinon un script CI l'ignore."""
        monkeypatch.setattr(sys, "argv", ["release_check.py", "--sans-tests"])
        monkeypatch.setattr(release_check, "_lire", lambda _: "")
        assert main() == 1
        assert "Publication bloquée" in capsys.readouterr().out

    def test_sortie_lisible(self, monkeypatch, capsys):
        """La sortie doit nommer la version, son type, et les points humains."""
        monkeypatch.setattr(sys, "argv", ["release_check.py", "--sans-tests"])
        main()
        sortie = capsys.readouterr().out
        assert release_check.__version__ in sortie
        assert release_check.__release_type__ in sortie
        assert "À confirmer par un humain" in sortie
