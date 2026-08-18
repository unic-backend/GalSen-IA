"""
Cohérence entre le cache, le magasin et la recherche (VOLET 21, chapitre 03).

Le chapitre range la validation d'intégrité et la vérification de cohérence
sémantique parmi ses contrôles qualité. Mesuré avant correction, trois vues
d'une même connaissance ne disaient pas la même chose : `get_knowledge()`
rendait un contenu que le magasin avait refusé d'écrire.
"""

import pytest

from src.knowledge_engine.knowledge_manager import KnowledgeManagerImpl
from src.knowledge_engine.types import KnowledgeDomain, KnowledgeItem


@pytest.fixture
def base():
    """Base de connaissances isolée."""
    return KnowledgeManagerImpl()


def _connaissance(contenu="Le mil se sème en juin au Sénégal."):
    """Construit une connaissance opérationnelle."""
    return KnowledgeItem(content=contenu, domain=KnowledgeDomain.OPERATIONAL)


def test_un_contenu_identique_ne_cree_pas_deux_connaissances(base):
    """L'identifiant est l'empreinte du contenu : le doublon exact est structurel."""
    identifiants = [base.add_knowledge(_connaissance()) for _ in range(3)]

    assert len(set(identifiants)) == 1
    assert base.quality_report()["duplicates"]["redundant_items"] == 0


def test_les_trois_vues_disent_la_meme_chose(base):
    """
    Le défaut mesuré : le cache portait « juillet », le magasin « juin ».

    `add_knowledge()` mettait en cache l'objet qu'on lui avait soumis, sans
    regarder si le magasin l'avait accepté. Un appelant relisait donc sa propre
    soumission et croyait l'avoir enregistrée.
    """
    identifiant = base.add_knowledge(_connaissance("Le mil se sème en juin."))

    refusee = _connaissance("Le mil se sème en juillet.")
    refusee.id, refusee.version = identifiant, 1
    base.add_knowledge(refusee)

    depuis_le_cache = base.get_knowledge(identifiant).content
    depuis_le_magasin = base.get_store().get(identifiant).content
    depuis_la_recherche = [i.content for i in base.search_knowledge("mil")]

    assert depuis_le_cache == depuis_le_magasin == "Le mil se sème en juin."
    assert depuis_la_recherche == ["Le mil se sème en juin."]


def test_le_refus_d_ecriture_est_dit(base, caplog):
    """
    « Créé », « inchangé » et « refusé » étaient indiscernables : la méthode
    retourne un identifiant dans les trois cas. Le refus est au moins journalisé,
    avec la marche à suivre.
    """
    identifiant = base.add_knowledge(_connaissance("Le mil se sème en juin."))
    refusee = _connaissance("Le mil se sème en juillet.")
    refusee.id, refusee.version = identifiant, 1

    with caplog.at_level("WARNING"):
        base.add_knowledge(refusee)

    assert "non écrite" in caplog.text
    assert "update_knowledge" in caplog.text


def test_un_ajout_normal_ne_declenche_aucun_avertissement(base, caplog):
    """Le contre-test : sans lui, avertir toujours ferait passer le précédent."""
    with caplog.at_level("WARNING"):
        base.add_knowledge(_connaissance())

    assert "non écrite" not in caplog.text


def test_la_correction_passe_par_update_knowledge(base):
    """La voie que l'avertissement indique doit fonctionner."""
    identifiant = base.add_knowledge(_connaissance("Le mil se sème en juin."))
    item = base.get_knowledge(identifiant)
    item.content = "Le mil se sème en juillet."
    item.version += 1

    assert base.update_knowledge(item) is True
    assert base.get_knowledge(identifiant).content == "Le mil se sème en juillet."
    assert base.get_store().get(identifiant).content == "Le mil se sème en juillet."
