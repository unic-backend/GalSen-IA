"""
La bibliothèque de compétences — ce qu'elle range, et ce qu'elle refuse.

L'idée vient d'Odyssey (`zju-vipa/Odyssey`, MIT). Ce qui est éprouvé ici est
l'écart délibéré avec elle : **Odyssey range ce que l'agent a écrit, cette
bibliothèque range ce dont on sait d'où ça vient et si ça a marché.**
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.skills import (  # noqa: E402
    BibliothequeCompetences,
    Competence,
    CompetenceRefusee,
)


def _competence(**surcharges) -> Competence:
    """Une compétence valide, que chaque test abîme à sa façon."""
    base = {
        "nom": "resumer_un_texte",
        "description": "Réduit un texte long à ses points principaux.",
        "contenu": "def resumer(texte): ...",
        "origine": "agent:coder",
    }
    base.update(surcharges)
    return Competence(**base)


@pytest.fixture
def bibliotheque(tmp_path):
    """Une bibliothèque sur disque jetable, sans fournisseur d'embeddings."""
    return BibliothequeCompetences(chemin=str(tmp_path / "competences.json"))


class TestCeQuiEstRefuse:
    """
    Les quatre refus. Ce sont des exceptions, pas des avertissements : une
    bibliothèque qui accepte tout devient un tas où plus rien ne se retrouve.
    """

    def test_une_competence_sans_nom_est_introuvable(self, bibliotheque):
        with pytest.raises(CompetenceRefusee):
            bibliotheque.ajouter(_competence(nom="  "))

    def test_une_competence_sans_description_est_irrecuperable(self, bibliotheque):
        """Sans description, rien ne permet de la retrouver par le sens."""
        with pytest.raises(CompetenceRefusee):
            bibliotheque.ajouter(_competence(description=""))

    def test_une_competence_sans_origine_est_une_affirmation_sans_auteur(self, bibliotheque):
        """
        La même règle que le corpus : rien n'entre sans qu'on sache d'où ça
        vient. C'est l'écart principal avec Odyssey, qui range ce que le modèle
        a produit sans en garder la trace.
        """
        with pytest.raises(CompetenceRefusee):
            bibliotheque.ajouter(_competence(origine=""))

    def test_une_verification_sans_preuve_est_refusee(self, bibliotheque):
        """
        Se dire vérifiée sans dire par quoi, c'est affirmer. Le champ existe
        pour porter un identifiant d'exécution ou un test — pas une intention.
        """
        with pytest.raises(CompetenceRefusee):
            bibliotheque.ajouter(_competence(verifiee=True, preuve=""))

    def test_une_verification_avec_preuve_passe(self, bibliotheque):
        c = bibliotheque.ajouter(
            _competence(verifiee=True, preuve="run:2026-08-24T01:00Z")
        )
        assert c.verifiee is True


class TestRangerEtRetrouver:
    """Le comportement utile."""

    def test_une_competence_rangee_se_retrouve(self, bibliotheque):
        bibliotheque.ajouter(_competence())
        trouvees, info = bibliotheque.retrouver("résumer un long document")
        assert [c.nom for c in trouvees] == ["resumer_un_texte"]
        assert info["method"], "la récupération doit dire par quel chemin elle a classé"

    def test_le_chemin_de_classement_est_toujours_dit(self, bibliotheque):
        """
        Sans fournisseur d'embeddings, le classement est lexical — et le dire
        est l'essentiel. Un classement par mots présenté comme sémantique est
        exactement ce que cette plateforme refuse ailleurs.
        """
        bibliotheque.ajouter(_competence())
        _, info = bibliotheque.retrouver("résumer")
        assert info["method"] == "lexical", "aucun encodeur n'est branché ici"

    def test_une_bibliotheque_vide_le_dit_au_lieu_de_se_taire(self, bibliotheque):
        trouvees, info = bibliotheque.retrouver("n'importe quoi")
        assert trouvees == []
        assert info["method"] == "empty"
        assert info["reason"]

    def test_on_peut_ne_demander_que_les_verifiees(self, bibliotheque):
        bibliotheque.ajouter(_competence(nom="jamais_eprouvee"))
        bibliotheque.ajouter(
            _competence(nom="eprouvee", verifiee=True, preuve="test:xyz")
        )
        trouvees, _ = bibliotheque.retrouver(
            "resumer texte eprouvee jamais", verifiees_seulement=True
        )
        assert all(c.verifiee for c in trouvees)
        assert "jamais_eprouvee" not in [c.nom for c in trouvees]

    def test_remplacer_une_competence_garde_ce_qu_elle_a_servi(self, bibliotheque):
        """
        Le compteur de réutilisations survit au remplacement : ce qui a servi a
        servi, et une nouvelle version ne fait pas oublier l'usage.
        """
        bibliotheque.ajouter(_competence())
        bibliotheque.retrouver("résumer un texte")
        avant = bibliotheque._competences["resumer_un_texte"].reutilisations
        assert avant > 0

        bibliotheque.ajouter(_competence(contenu="def resumer(texte): # v2"))
        assert bibliotheque._competences["resumer_un_texte"].reutilisations == avant
        assert "v2" in bibliotheque._competences["resumer_un_texte"].contenu


class TestPersistance:
    """Une bibliothèque qui s'oublie au redémarrage n'apprend rien."""

    def test_elle_survit_a_un_redemarrage(self, tmp_path):
        chemin = str(tmp_path / "c.json")
        BibliothequeCompetences(chemin=chemin).ajouter(_competence())
        assert BibliothequeCompetences(chemin=chemin).compter() == 1

    def test_un_fichier_illisible_laisse_une_bibliotheque_vide(self, tmp_path):
        """
        Et non une plateforme qui refuse de démarrer. Une bibliothèque vide est
        un état ; une exception au démarrage empêche de servir.
        """
        chemin = tmp_path / "c.json"
        chemin.write_text("{ ceci n'est pas du JSON", encoding="utf-8")
        assert BibliothequeCompetences(chemin=str(chemin)).compter() == 0

    def test_une_entree_invalide_du_fichier_est_ecartee(self, tmp_path):
        """Une compétence sans origine, glissée dans le fichier, n'entre pas."""
        chemin = tmp_path / "c.json"
        chemin.write_text(json.dumps({"competences": [
            {"nom": "sans_origine", "description": "d", "contenu": "c", "origine": ""},
            {"nom": "correcte", "description": "d", "contenu": "c", "origine": "agent:x"},
        ]}), encoding="utf-8")
        b = BibliothequeCompetences(chemin=str(chemin))
        assert b.compter() == 1


class TestEtat:
    """Ce que la bibliothèque dit d'elle-même."""

    def test_l_etat_avoue_l_absence_d_embeddings(self, bibliotheque):
        """
        Sans fournisseur, la récupération marche encore — par les mots. L'état
        le dit, plutôt que de laisser le découvrir sur un mauvais résultat.
        """
        assert bibliotheque.etat()["semantique"] is False

    def test_l_etat_compte_separement_les_verifiees(self, bibliotheque):
        bibliotheque.ajouter(_competence(nom="a"))
        bibliotheque.ajouter(_competence(nom="b", verifiee=True, preuve="t:1"))
        etat = bibliotheque.etat()
        assert etat["total"] == 2
        assert etat["verifiees"] == 1
