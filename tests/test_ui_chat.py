"""
Tests de la page de conversation (VOLET chat-first, ch. 03).

Ce qui est épinglé ici tient en une phrase : **la page ne doit pas mentir sur ce
qu'elle sait**. Le reste — la couleur d'une bulle, la taille d'un titre — est du
design, il changera, et un test qui le fige empêcherait de le changer.
"""

import os
import re
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

RACINE = os.path.join(os.path.dirname(__file__), "..")
PAGE = os.path.join(RACINE, "src", "web", "static", "index.html")
STYLE = os.path.join(RACINE, "src", "web", "static", "css", "chat.css")


@pytest.fixture(scope="module")
def client():
    import src.api.server as serveur
    return TestClient(serveur.app)


def _lire(chemin: str) -> str:
    with open(chemin, encoding="utf-8") as fichier:
        return fichier.read()


def _code_sans_commentaires(chemin: str) -> str:
    """
    Le JavaScript privé de ses commentaires.

    Nécessaire parce que ce fichier **documente** le défaut qu'il a corrigé, en
    citant la forme fautive. Chercher cette forme dans le fichier entier
    trouverait l'explication et non le code — un test qui échoue sur sa propre
    documentation apprend à supprimer la documentation.
    """
    texte = _lire(chemin)
    texte = re.sub(r"/\*.*?\*/", "", texte, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", texte, flags=re.MULTILINE)


class TestServie:
    """La page arrive, et sa feuille de style aussi."""

    def test_la_page_est_servie(self, client):
        reponse = client.get("/ui/")
        assert reponse.status_code == 200
        assert "text/html" in reponse.headers["content-type"]

    def test_la_feuille_de_style_est_servie(self, client):
        assert client.get("/ui/css/chat.css").status_code == 200


class TestHonnetete:
    """Ce que la page promet doit exister derrière elle."""

    def test_aucune_cle_n_est_ecrite_dans_la_page(self):
        """
        Une clé servie dans le HTML serait lisible par quiconque ouvre la page.

        Le champ existe ; sa valeur n'est jamais posée côté serveur.
        """
        page = _lire(PAGE)
        assert 'id="cle-api"' in page
        assert not re.search(r'id="cle-api"[^>]*\svalue=', page)

    def test_aucune_ressource_distante(self):
        """
        Aucune police ni script téléchargé depuis un tiers.

        Sur une connexion lente — le cas courant ici — une police distante
        retarde l'affichage du texte, et le texte est ce qu'on vient lire. Cela
        évite aussi qu'un tiers voie qui consulte la plateforme.
        """
        for chemin in (PAGE, STYLE):
            assert "https://" not in _lire(chemin), chemin

    def test_la_page_prepare_les_trois_issues_d_ancrage(self):
        """
        `GROUNDED`, `UNGROUNDED`, `NOT_CHECKED` — trois états, jamais deux.

        Le style doit pouvoir peindre les trois. S'il n'en prévoit que deux,
        l'un des trois s'affichera comme un autre, et « personne n'a vérifié »
        finira teint comme « c'est fondé ».
        """
        style = _lire(STYLE)
        for classe in (".jeton.ancre", ".jeton.sans-ancre", ".jeton.non-verifie"):
            assert classe in style, classe

    def test_le_manque_d_ancrage_n_est_pas_peint_en_rouge(self):
        """
        Ocre, pas rouge : une base vide n'est pas une erreur.

        L'agent `senegal` dit lui-même « ce n'est pas une réponse négative ».
        Peindre son refus comme une panne contredirait la seule phrase que la
        plateforme tient à faire comprendre.
        """
        style = _lire(STYLE)
        assert "--sans-ancre: #9a6700" in style


class TestAccessibilite:
    """Le minimum, et il n'est pas négociable."""

    def test_chaque_champ_porte_une_etiquette(self):
        page = _lire(PAGE)
        for identifiant in ("cle-api", "message"):
            assert f'for="{identifiant}"' in page, identifiant

    def test_les_reponses_sont_annoncees(self):
        """Sans `aria-live`, un lecteur d'écran ne dit jamais la réponse."""
        assert 'aria-live="polite"' in _lire(PAGE)

    def test_l_animation_d_attente_se_desactive(self):
        """Pour certaines personnes, une pulsation continue est un symptôme."""
        assert "prefers-reduced-motion" in _lire(STYLE)


class TestJetonAncrage:
    """
    Le lien entre le statut rendu par l'API et la couleur affichée.

    **Ce test existe parce que son absence a laissé passer le défaut.** La
    première version de `chat.js` fabriquait la classe par
    `` `jeton.${statut.toLowerCase()}` ``, produisant `jeton.grounded` — un nom
    de classe contenant un point, qui ne correspondait à aucune règle CSS.

    Le jeton le plus important de la page s'est donc affiché sans sa couleur
    pendant tout le chapitre 04, et rien ne l'a signalé : `GROUNDED` reste rare
    tant que le corpus est vide, et un jeton gris parmi des jetons gris ne se
    remarque pas. Un défaut qu'on ne voit qu'en lisant le code est exactement
    celui qu'un test doit tenir.
    """

    def test_les_trois_statuts_ont_une_classe_qui_existe(self):
        """Chaque classe nommée par le script doit exister dans la feuille."""
        script = _lire(os.path.join(RACINE, "src", "web", "static", "js", "chat.js"))
        style = _lire(STYLE)

        for statut in ("GROUNDED", "UNGROUNDED", "NOT_CHECKED"):
            trouve = re.search(
                rf"{statut}:\s*{{\s*classe:\s*\"([a-z-]+)\"", script
            )
            assert trouve, f"{statut} n'a pas d'entrée dans la table ANCRAGE"
            classe = trouve.group(1)
            assert f".jeton.{classe}" in style, (
                f"{statut} pointe vers .jeton.{classe}, absente de chat.css"
            )

    def test_aucune_classe_fabriquee_par_interpolation(self):
        """
        Une classe construite à la volée depuis le statut se casse en silence.

        C'est la forme exacte du défaut d'origine : elle produit un nom
        syntaxiquement invalide sans lever la moindre erreur.
        """
        script = _code_sans_commentaires(
            os.path.join(RACINE, "src", "web", "static", "js", "chat.js")
        )
        assert "jeton.${" not in script

    def test_la_raison_de_l_ancrage_est_affichee(self):
        """
        « UNGROUNDED » sans sa raison n'aide personne à corriger quoi que ce soit.

        L'agent `senegal` écrit lui-même ce qui manque et ce qui trancherait ;
        garder le seul statut jetterait la partie utile.
        """
        script = _lire(os.path.join(RACINE, "src", "web", "static", "js", "chat.js"))
        assert "grounding.reason" in script

    def test_un_statut_inconnu_ne_passe_pas_pour_fonde(self):
        """
        Si le serveur ajoute une quatrième issue, la page ne doit pas la peindre
        en vert. Le repli est l'issue la plus prudente, jamais la plus flatteuse.
        """
        script = _lire(os.path.join(RACINE, "src", "web", "static", "js", "chat.js"))
        trouve = re.search(r"ANCRAGE\[statut\]\s*\|\|\s*ANCRAGE\.([A-Z_]+)", script)
        assert trouve, "aucun repli explicite pour un statut inconnu"
        assert trouve.group(1) == "NOT_CHECKED"
