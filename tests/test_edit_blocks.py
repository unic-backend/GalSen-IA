"""
Tests des blocs d'édition (VOLET OSS, phase 6.1).

Ce module écrit sur le disque à partir d'un texte produit par un modèle. C'est
la seule partie de la plateforme dans ce cas, et c'est ce qui fixe l'ordre des
priorités de ces tests.

1. **Le confinement.** Un chemin est vite forgé : `../`, un chemin absolu, un
   lien symbolique qui sort. Aucun de ces trois ne doit écrire quoi que ce soit.
2. **Le refus de deviner.** Zéro correspondance veut dire que le modèle a
   inventé le texte ; deux veut dire qu'il ne dit pas laquelle. Remplacer au
   mauvais endroit coûte plus cher qu'échouer.
3. **L'atomicité.** Un lot à moitié appliqué laisse un dépôt dans un état dont
   personne ne sait revenir.

Le reste — lecture du format, fins de ligne, création de fichier — vient après.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.code_edit.edit_blocks import (  # noqa: E402
    EditBlock,
    apply_edit_blocks,
    apply_response,
    parse_edit_blocks,
)


def _bloc(chemin: str, recherche: str, remplacement: str) -> str:
    """Rend le texte d'un bloc d'édition tel qu'un modèle l'écrirait."""
    return (
        f"{chemin}\n"
        f"<<<<<<< SEARCH\n"
        f"{recherche}"
        f"=======\n"
        f"{remplacement}"
        f">>>>>>> REPLACE\n"
    )


@pytest.fixture
def projet(tmp_path):
    """Un petit dépôt de travail, avec un fichier à modifier."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "exemple.py").write_text(
        "def ancienne():\n    return 1\n", encoding="utf-8"
    )
    return tmp_path


class TestLectureDuFormat:
    """Extraire les blocs d'une réponse, sans se laisser distraire par la prose."""

    def test_un_bloc_simple(self):
        """Le cas nominal : sans lui, le reste des tests ne dit rien."""
        blocs, fautes = parse_edit_blocks(_bloc("src/a.py", "avant\n", "après\n"))
        assert fautes == []
        assert blocs == [EditBlock(path="src/a.py", search="avant\n", replace="après\n")]

    def test_la_prose_autour_est_ignoree(self):
        """Un modèle explique toujours son geste avant de le faire."""
        texte = (
            "Je vais renommer la fonction.\n\n"
            + _bloc("src/a.py", "avant\n", "après\n")
            + "\nVoilà, c'est fait."
        )
        blocs, fautes = parse_edit_blocks(texte)
        assert len(blocs) == 1
        assert fautes == []

    def test_les_delimiteurs_markdown_sont_traverses(self):
        """Le chemin est au-dessus de la clôture, pas collé au marqueur."""
        texte = "src/a.py\n```python\n" + _bloc("", "avant\n", "après\n").lstrip("\n") + "```\n"
        blocs, _ = parse_edit_blocks(texte)
        assert blocs[0].path == "src/a.py"

    def test_plusieurs_blocs_sont_lus_dans_l_ordre(self):
        """Une réponse porte couramment trois ou quatre modifications."""
        texte = _bloc("a.py", "x\n", "y\n") + _bloc("b.py", "z\n", "w\n")
        blocs, fautes = parse_edit_blocks(texte)
        assert [b.path for b in blocs] == ["a.py", "b.py"]
        assert fautes == []

    def test_un_chemin_decore_est_nettoye(self):
        """Les modèles écrivent volontiers `**src/a.py**` ou entre accents graves."""
        blocs, _ = parse_edit_blocks(_bloc("**`src/a.py`**", "x\n", "y\n"))
        assert blocs[0].path == "src/a.py"

    def test_un_bloc_sans_chemin_est_une_faute(self):
        """Appliquer un bloc sans savoir où serait pire que de le refuser."""
        blocs, fautes = parse_edit_blocks("<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE\n")
        assert blocs == []
        assert any("chemin" in faute for faute in fautes)

    def test_une_phrase_ne_passe_pas_pour_un_chemin(self):
        """« Voici le fichier : » n'est pas un chemin, et l'espace le trahit."""
        texte = "Voici le fichier à modifier :\n<<<<<<< SEARCH\nx\n=======\ny\n>>>>>>> REPLACE\n"
        blocs, fautes = parse_edit_blocks(texte)
        assert blocs == []
        assert fautes

    def test_un_bloc_non_ferme_est_une_faute_pas_un_bloc_partiel(self):
        """Un bloc tronqué appliqué à moitié écrirait n'importe quoi."""
        blocs, fautes = parse_edit_blocks("a.py\n<<<<<<< SEARCH\nx\n=======\ny\n")
        assert blocs == []
        assert any("non terminé" in faute for faute in fautes)

    def test_un_separateur_manquant_est_une_faute(self):
        """Sans séparateur, on ne sait pas où finit le texte cherché."""
        blocs, fautes = parse_edit_blocks("a.py\n<<<<<<< SEARCH\nx\n>>>>>>> REPLACE\n")
        assert blocs == []
        assert fautes

    def test_un_texte_sans_bloc_ne_produit_rien(self):
        """Un modèle qui répond en prose n'a rien proposé : ce n'est pas une faute."""
        assert parse_edit_blocks("Je ne vois rien à changer.") == ([], [])

    def test_une_section_de_recherche_vide_cree_un_fichier(self):
        """C'est la convention du format pour un nouveau fichier."""
        blocs, _ = parse_edit_blocks(_bloc("nouveau.py", "", "contenu\n"))
        assert blocs[0].creates_file is True


class TestConfinement:
    """La garde la plus importante : rien ne s'écrit hors du dossier confié."""

    @pytest.mark.parametrize("chemin", [
        "../dehors.py",
        "src/../../dehors.py",
        "~/dehors.py",
    ])
    def test_un_chemin_qui_sort_est_refuse(self, projet, chemin):
        """Le texte vient d'un modèle : un chemin est vite forgé."""
        rapport = apply_response(_bloc(chemin, "", "nuisible\n"), projet)
        assert rapport.ok is False
        assert not (projet.parent / "dehors.py").exists()

    def test_un_chemin_absolu_est_refuse(self, projet, tmp_path):
        """Refusé avant toute résolution, quel que soit l'endroit visé."""
        cible = tmp_path.parent / "absolu.py"
        rapport = apply_response(_bloc(str(cible), "", "nuisible\n"), projet)
        assert rapport.ok is False
        assert not cible.exists()

    def test_un_lien_symbolique_qui_sort_est_refuse(self, projet, tmp_path):
        """Un chemin relatif inoffensif peut mener dehors par un lien."""
        dehors = tmp_path.parent / "secret"
        dehors.mkdir(exist_ok=True)
        (dehors / "cle.txt").write_text("valeur d'origine\n", encoding="utf-8")
        try:
            (projet / "lien").symlink_to(dehors)
        except (OSError, NotImplementedError):  # pragma: no cover
            pytest.skip("Liens symboliques indisponibles sur cette plateforme.")

        rapport = apply_response(
            _bloc("lien/cle.txt", "valeur d'origine\n", "volée\n"), projet
        )
        assert rapport.ok is False
        assert (dehors / "cle.txt").read_text(encoding="utf-8") == "valeur d'origine\n"

    def test_le_motif_nomme_le_chemin_fautif(self, projet):
        """Un refus muet oblige l'appelant à deviner lequel des blocs a bloqué."""
        rapport = apply_response(_bloc("../dehors.py", "", "x\n"), projet)
        assert "dehors.py" in rapport.failures[0].reason


class TestRefusDeDeviner:
    """Zéro ou plusieurs correspondances : on refuse, on ne choisit pas."""

    def test_un_texte_introuvable_est_refuse(self, projet):
        """Le modèle a inventé le texte : le remplacer serait écrire au hasard."""
        rapport = apply_response(
            _bloc("src/exemple.py", "def jamais_ecrite():\n", "x\n"), projet
        )
        assert rapport.ok is False
        assert "introuvable" in rapport.failures[0].reason
        assert "def ancienne" in (projet / "src" / "exemple.py").read_text(encoding="utf-8")

    def test_un_texte_ambigu_est_refuse(self, projet):
        """Deux occurrences : le bloc ne dit pas laquelle, donc on n'en touche aucune."""
        (projet / "src" / "double.py").write_text("x = 1\nx = 1\n", encoding="utf-8")
        rapport = apply_response(_bloc("src/double.py", "x = 1\n", "x = 2\n"), projet)
        assert rapport.ok is False
        assert "2 fois" in rapport.failures[0].reason
        assert (projet / "src" / "double.py").read_text(encoding="utf-8") == "x = 1\nx = 1\n"

    def test_un_fichier_absent_est_refuse_avec_le_geste(self, projet):
        """Le motif doit dire comment créer, pas seulement que ça a échoué."""
        rapport = apply_response(_bloc("src/absent.py", "x\n", "y\n"), projet)
        assert rapport.ok is False
        assert "SEARCH vide" in rapport.failures[0].reason

    def test_une_creation_par_dessus_un_fichier_est_refusee(self, projet):
        """Un écrasement silencieux détruirait du travail sans trace."""
        rapport = apply_response(_bloc("src/exemple.py", "", "tout neuf\n"), projet)
        assert rapport.ok is False
        assert "existe déjà" in rapport.failures[0].reason
        assert "def ancienne" in (projet / "src" / "exemple.py").read_text(encoding="utf-8")


class TestAtomicite:
    """Un lot passe entièrement ou pas du tout."""

    def test_un_bloc_fautif_annule_tout_le_lot(self, projet):
        """Une application partielle laisse un dépôt à moitié modifié."""
        texte = (
            _bloc("src/exemple.py", "def ancienne():\n", "def nouvelle():\n")
            + _bloc("src/exemple.py", "texte absent\n", "x\n")
        )
        rapport = apply_response(texte, projet)
        assert rapport.ok is False
        assert rapport.applied_paths == []
        assert "def ancienne" in (projet / "src" / "exemple.py").read_text(encoding="utf-8")

    def test_le_bloc_valide_ne_se_dit_pas_applique(self, projet):
        """Confondre « valide » et « écrit » ferait croire à une écriture qui n'a pas eu lieu."""
        texte = (
            _bloc("src/exemple.py", "def ancienne():\n", "def nouvelle():\n")
            + _bloc("src/absent.py", "x\n", "y\n")
        )
        rapport = apply_response(texte, projet)
        valide = rapport.outcomes[0]
        assert valide.would_apply is True
        assert valide.applied is False
        assert "annulé" in valide.reason

    def test_une_faute_de_lecture_annule_aussi_le_lot(self, projet):
        """Un bloc perdu à la lecture peut être celui qui comptait."""
        texte = (
            _bloc("src/exemple.py", "def ancienne():\n", "def nouvelle():\n")
            + "src/autre.py\n<<<<<<< SEARCH\ntronqué\n"
        )
        rapport = apply_response(texte, projet)
        assert rapport.ok is False
        assert rapport.applied_paths == []


class TestApplication:
    """Ce que le module doit réellement savoir faire."""

    def test_un_remplacement_aboutit(self, projet):
        """La capacité que l'agent `coder` n'avait pas : modifier un fichier."""
        rapport = apply_response(
            _bloc("src/exemple.py", "    return 1\n", "    return 42\n"), projet
        )
        assert rapport.ok is True
        assert rapport.applied_paths == ["src/exemple.py"]
        assert (projet / "src" / "exemple.py").read_text(encoding="utf-8") == (
            "def ancienne():\n    return 42\n"
        )

    def test_un_fichier_est_cree(self, projet):
        """Section SEARCH vide : le format prévoit la création."""
        rapport = apply_response(_bloc("src/nouveau.py", "", "print('bonjour')\n"), projet)
        assert rapport.ok is True
        assert rapport.outcomes[0].created is True
        assert (projet / "src" / "nouveau.py").read_text(encoding="utf-8") == "print('bonjour')\n"

    def test_les_dossiers_manquants_sont_crees(self, projet):
        """Un nouveau module vit souvent dans un paquet qui n'existe pas encore."""
        assert apply_response(_bloc("src/paquet/mod.py", "", "x = 1\n"), projet).ok is True
        assert (projet / "src" / "paquet" / "mod.py").is_file()

    def test_deux_blocs_sur_le_meme_fichier_s_enchainent(self, projet):
        """Le second doit chercher dans le résultat du premier, pas dans l'ancien texte.

        Sans cet enchaînement, une réponse qui modifie deux endroits du même
        fichier n'en appliquerait qu'un — et l'autre échouerait sans raison
        compréhensible.
        """
        texte = (
            _bloc("src/exemple.py", "def ancienne():\n", "def nouvelle():\n")
            + _bloc("src/exemple.py", "    return 1\n", "    return 2\n")
        )
        rapport = apply_response(texte, projet)
        assert rapport.ok is True
        assert (projet / "src" / "exemple.py").read_text(encoding="utf-8") == (
            "def nouvelle():\n    return 2\n"
        )

    def test_creer_puis_modifier_dans_le_meme_lot(self, projet):
        """Un fichier créé par le lot doit être modifiable par le bloc suivant."""
        texte = (
            _bloc("src/neuf.py", "", "a = 1\n")
            + _bloc("src/neuf.py", "a = 1\n", "a = 2\n")
        )
        assert apply_response(texte, projet).ok is True
        assert (projet / "src" / "neuf.py").read_text(encoding="utf-8") == "a = 2\n"

    def test_les_fins_de_ligne_windows_sont_respectees(self, projet):
        """Un modèle écrit en \\n ; un fichier Windows est en \\r\\n.

        Sans adaptation, aucune recherche n'aboutirait sur un tel fichier, et
        le motif « texte introuvable » enverrait chercher une faute
        d'indentation inexistante.
        """
        chemin = projet / "src" / "windows.py"
        with open(chemin, "w", encoding="utf-8", newline="") as fichier:
            fichier.write("a = 1\r\nb = 2\r\n")

        rapport = apply_response(_bloc("src/windows.py", "a = 1\n", "a = 9\n"), projet)
        assert rapport.ok is True
        with open(chemin, encoding="utf-8", newline="") as fichier:
            assert fichier.read() == "a = 9\r\nb = 2\r\n"


class TestVerificationABlanc:
    """Vérifier sans écrire : ce qui permet de proposer avant d'agir."""

    def test_rien_n_est_ecrit(self, projet):
        """C'est toute la promesse du mode."""
        rapport = apply_response(
            _bloc("src/exemple.py", "    return 1\n", "    return 42\n"), projet, dry_run=True
        )
        assert rapport.ok is True
        assert rapport.applied_paths == []
        assert "return 1" in (projet / "src" / "exemple.py").read_text(encoding="utf-8")

    def test_un_bloc_fautif_est_signale_sans_ecriture(self, projet):
        """Le mode sert justement à voir les refus avant de s'engager."""
        rapport = apply_response(_bloc("src/exemple.py", "absent\n", "x\n"), projet, dry_run=True)
        assert rapport.ok is False
        assert rapport.dry_run is True

    def test_le_resume_dit_l_essentiel(self, projet):
        """Un appelant qui ne lit pas le détail doit savoir quoi faire."""
        resume = apply_response(
            _bloc("src/exemple.py", "    return 1\n", "    return 3\n"), projet
        ).summary()
        assert resume == {
            "ok": True, "applied": 1, "failed": 0,
            "paths": ["src/exemple.py"], "errors": [], "dry_run": False,
        }


class TestEntreeDirecte:
    """`apply_edit_blocks` reste utilisable sans passer par le texte d'un modèle."""

    def test_des_blocs_construits_a_la_main(self, projet):
        """Un appelant qui a déjà les blocs ne doit pas les resérialiser."""
        blocs = [EditBlock(path="src/exemple.py", search="    return 1\n", replace="    return 7\n")]
        assert apply_edit_blocks(blocs, projet).ok is True
        assert "return 7" in (projet / "src" / "exemple.py").read_text(encoding="utf-8")

    def test_une_liste_vide_reussit_sans_rien_faire(self, projet):
        """Aucune proposition n'est pas un échec."""
        rapport = apply_edit_blocks([], projet)
        assert rapport.ok is True
        assert rapport.applied_paths == []
