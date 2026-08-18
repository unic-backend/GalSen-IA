"""
L'isolation des données utilisateur : à qui est la donnée, et où elle a le droit d'aller.

Le défaut que ce module supprime est **structurel**, pas accidentel : le dépôt
portait déjà un `user_id` sur les éléments de mémoire, mais comme **filtre
facultatif**. `search_memory(query)` sans `user_id` rend les mémoires de tout le
monde. Le défaut était donc la fuite, et l'isolation quelque chose qu'un
appelant devait penser à demander. Ce genre de conception ne tombe jamais par
une attaque : elle tombe par un oubli.

Ce que ces tests gardent :

1. **Il n'existe pas d'audience « non précisée ».** Lire pour personne est une
   audience réelle, qui ne voit la donnée de personne.
2. **L'appelant ne choisit pas le propriétaire** : il est déduit de la portée
   déclarée de la source.
3. **Une portée non déclarée n'est pas supposée publique.**
4. **Une écriture qui traverse la frontière lève**, elle ne rend pas `False` que
   quelqu'un pourrait ignorer.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.security.isolation import (  # noqa: E402
    Audience,
    IsolationError,
    Owner,
    OwnerKind,
    Visibility,
    check_store,
    isolation_report,
    may_read,
    may_store,
    owner_for,
    visible_to,
)
from src.tool.authorization import Actor  # noqa: E402
from src.tool.capabilities import DataScope  # noqa: E402


# ----------------------------------------------------------------------
# 1. Le propriétaire est déduit, jamais choisi
# ----------------------------------------------------------------------

def test_une_source_privee_produit_de_la_donnee_privee():
    """
    Le point qui tient toute la frontière : un connecteur déclaré
    `user_private` ne peut pas rendre de la donnée étiquetée publique,
    quoi qu'il en pense.
    """
    proprietaire = owner_for(DataScope.USER_PRIVATE, subject="fatou")

    assert proprietaire.kind is OwnerKind.USER
    assert proprietaire.subject == "fatou"


@pytest.mark.parametrize("portee", [DataScope.PUBLIC, DataScope.SYSTEM])
def test_une_source_non_privee_produit_de_la_donnee_de_plateforme(portee):
    """La symétrie : tout ce qui n'est pas privé est partageable."""
    assert owner_for(portee, subject="fatou").kind is OwnerKind.PLATFORM


def test_une_portee_non_declaree_n_est_pas_supposee_publique():
    """
    Des deux sens possibles, « public » est le plus dangereux. Une portée
    absente est donc un refus, pas un défaut permissif.
    """
    with pytest.raises(IsolationError, match="non déclarée"):
        owner_for(None)


def test_une_donnee_privee_sans_sujet_est_refusee():
    """
    Elle n'est protégeable par personne : l'attribuer à « quelqu'un » revient
    à ne pas la protéger, avec l'air de l'avoir fait.
    """
    with pytest.raises(IsolationError, match="obligatoire"):
        owner_for(DataScope.USER_PRIVATE, subject=None)

    with pytest.raises(IsolationError, match="obligatoire"):
        Owner.user("   ")


# ----------------------------------------------------------------------
# 2. L'écriture
# ----------------------------------------------------------------------

def test_une_donnee_privee_n_entre_pas_dans_un_magasin_partage():
    """
    La règle absolue de la vague des connecteurs : un courriel n'entre pas
    dans la base de connaissance. Une fois entré, aucun filtre postérieur ne
    l'en retire.
    """
    autorise, raison = may_store(Owner.user("fatou"), Visibility.SHARED)

    assert autorise is False
    assert "aucun filtre postérieur" in raison


def test_la_meme_donnee_entre_dans_le_magasin_de_son_proprietaire():
    """Isoler n'est pas interdire : la donnée a un endroit où aller."""
    autorise, _ = may_store(Owner.user("fatou"), Visibility.PRIVATE)

    assert autorise is True


def test_une_donnee_de_plateforme_entre_partout():
    """Ce qui est public ou acquis n'a pas de frontière à traverser."""
    for destination in Visibility:
        assert may_store(Owner.platform(), destination)[0] is True


def test_une_ecriture_interdite_leve_au_lieu_de_rendre_faux():
    """
    Un appelant peut ignorer un booléen sans le vouloir. Il ne peut pas
    ignorer une exception.
    """
    with pytest.raises(IsolationError):
        check_store(Owner.user("fatou"), Visibility.SHARED)

    check_store(Owner.user("fatou"), Visibility.PRIVATE)
    check_store(Owner.platform(), Visibility.SHARED)


# ----------------------------------------------------------------------
# 3. La lecture — le défaut que `user_id=None` laissait passer
# ----------------------------------------------------------------------

def test_une_lecture_sans_sujet_n_atteint_la_donnee_de_personne():
    """
    Le test central de cette phase. `user_id=None` voulait dire « tout le
    monde » ; `Audience.platform()` veut dire « personne en particulier », et
    cette audience-là ne lit le courrier de personne.
    """
    autorise, raison = may_read(Audience.platform(), Owner.user("fatou"))

    assert autorise is False
    assert "sans sujet" in raison


def test_une_personne_ne_lit_pas_la_donnee_d_une_autre():
    """L'isolation entre sujets, dans les deux sens."""
    assert may_read(Audience.user("moussa"), Owner.user("fatou"))[0] is False
    assert may_read(Audience.user("fatou"), Owner.user("moussa"))[0] is False


def test_une_personne_lit_sa_propre_donnee():
    """Isoler n'est pas priver son propriétaire."""
    autorise, raison = may_read(Audience.user("fatou"), Owner.user("fatou"))

    assert autorise is True
    assert "son propriétaire" in raison


def test_tout_le_monde_lit_la_donnee_de_la_plateforme():
    """La connaissance acquise reste commune."""
    for audience in (Audience.platform(), Audience.user("fatou")):
        assert may_read(audience, Owner.platform())[0] is True


def test_tout_refus_de_lecture_porte_sa_raison():
    """Un refus sans motif est indébogable."""
    cas = [
        (Audience.platform(), Owner.user("fatou")),
        (Audience.user("moussa"), Owner.user("fatou")),
    ]

    for audience, proprietaire in cas:
        _, raison = may_read(audience, proprietaire)
        assert raison.strip() != ""


# ----------------------------------------------------------------------
# 4. Le filtrage d'une suite
# ----------------------------------------------------------------------

def _elements():
    """Trois éléments : la plateforme, Fatou, Moussa."""
    return [
        {"texte": "Le franc CFA est la monnaie du Sénégal", "owner": Owner.platform()},
        {"texte": "Rendez-vous vendredi", "owner": Owner.user("fatou")},
        {"texte": "Facture à payer", "owner": Owner.user("moussa")},
    ]


def test_le_filtre_rend_a_chacun_ce_qui_est_a_lui():
    """Le cas d'usage réel : une recherche croise plusieurs propriétaires."""
    visibles = visible_to(
        Audience.user("fatou"), _elements(), lambda item: item["owner"]
    )

    textes = [item["texte"] for item in visibles]
    assert "Rendez-vous vendredi" in textes
    assert "Le franc CFA est la monnaie du Sénégal" in textes
    assert "Facture à payer" not in textes


def test_une_tache_de_fond_ne_voit_que_le_commun():
    """Une routine tourne pour la plateforme, pas pour une personne."""
    visibles = visible_to(
        Audience.platform(), _elements(), lambda item: item["owner"]
    )

    assert len(visibles) == 1
    assert visibles[0]["owner"].kind is OwnerKind.PLATFORM


def test_le_filtre_conserve_l_ordre_recu():
    """Le classement de la recherche ne doit pas être réordonné par le filtre."""
    elements = _elements() + [{"texte": "Autre", "owner": Owner.platform()}]

    visibles = visible_to(
        Audience.user("fatou"), elements, lambda item: item["owner"]
    )

    assert [item["texte"] for item in visibles] == [
        "Le franc CFA est la monnaie du Sénégal", "Rendez-vous vendredi", "Autre",
    ]


def test_le_rapport_compte_ce_qui_est_retire_sans_le_nommer():
    """Nommer ce qui est caché reviendrait à le divulguer à moitié."""
    rapport = isolation_report(
        Audience.user("fatou"), _elements(), lambda item: item["owner"]
    )

    assert rapport["candidates"] == 3
    assert rapport["visible"] == 2
    assert rapport["withheld"] == 1
    serialise = str(rapport)
    assert "Facture" not in serialise
    assert "moussa" not in serialise


# ----------------------------------------------------------------------
# 5. Le pont avec la couche d'autorisation
# ----------------------------------------------------------------------

def test_un_acteur_nomme_devient_son_audience():
    """L'identité vient de la clé API (ADR-010), pas d'un paramètre de requête."""
    acteur = Actor(subject="fatou", role="user", permissions=frozenset())

    audience = Audience.from_actor(acteur)

    assert audience.owner.subject == "fatou"


def test_un_acteur_anonyme_ne_possede_rien():
    """
    Un sujet anonyme ne désigne personne : lui attribuer des données privées
    les rendrait accessibles à toute clé sans sujet déclaré.
    """
    for sujet in ("anonymous", "", "   "):
        acteur = Actor(subject=sujet, role="user", permissions=frozenset())
        audience = Audience.from_actor(acteur)

        assert audience.owner.kind is OwnerKind.PLATFORM
        assert may_read(audience, Owner.user("fatou"))[0] is False


def test_l_audience_ne_porte_aucun_secret():
    """Un rapport d'isolation finit dans l'audit."""
    audience = Audience.from_actor(
        Actor(subject="fatou", role="admin", permissions=frozenset({"tool:execute"}))
    )

    assert audience.owner.as_dict() == {"kind": "user", "subject": "fatou"}
    assert "tool:execute" not in str(audience.owner.as_dict())
