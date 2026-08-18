"""
Le registre des sources devient mondial (phase 51.1).

`corpus/sources/senegal.yaml` était **le** registre : un chemin unique en dur.
Un registre mondial dans ce même fichier ferait de toute relecture d'un domaine
national un diff de mille lignes, et mélangerait deux relectures qui n'ont ni
les mêmes lecteurs ni la même autorité.

Le répertoire `corpus/sources/` est donc chargé en entier. Le Sénégal devient un
registre parmi d'autres, et n'a rien perdu.

Ce que ces tests gardent :

1. **Un domaine n'appartient qu'à un registre.** Déclaré deux fois, la
   plateforme répondrait selon l'ordre de chargement — le pire désaccord, celui
   que personne ne voit. Le chargement refuse, en nommant les deux fichiers.
2. **Un refus déclaré quelque part vaut partout.** C'est le sens sûr de la
   fusion.
3. **Chaque source sait d'où elle vient**, sans quoi relire une déclaration
   demanderait de chercher dans quel fichier.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge_engine.source_registry import (  # noqa: E402
    REPERTOIRE_DES_REGISTRES,
    SourceRefused,
    check_source,
    load_registry,
    registry_report,
)
from src.knowledge_engine.types import SourceCategory  # noqa: E402

UN_REGISTRE = """
sources:
  - name: "Institut d'exemple"
    scope: country:fr
    subjects: [science]
    category: government
    base_url: https://exemple-institut.fr
deny:
  - domain: exemple-refuse.test
    reason: "Contenu anonyme : on ne peut pas savoir qui affirme."
"""

UN_AUTRE = """
sources:
  - name: "Agence d'exemple"
    scope: global
    subjects: [economics]
    category: institutional
    base_url: https://exemple-agence.org
"""


def _ecrire(repertoire, nom, contenu):
    """Écrit un registre dans un répertoire temporaire."""
    chemin = repertoire / nom
    chemin.write_text(contenu, encoding="utf-8")
    return chemin


# ----------------------------------------------------------------------
# 1. Plusieurs registres, un seul ensemble
# ----------------------------------------------------------------------

def test_tous_les_registres_du_repertoire_sont_charges(tmp_path):
    """Le point de la phase : le Sénégal n'est plus le seul fichier."""
    _ecrire(tmp_path, "a.yaml", UN_REGISTRE)
    _ecrire(tmp_path, "b.yaml", UN_AUTRE)

    registre = load_registry(str(tmp_path))

    noms = sorted(source["name"] for source in registre["sources"])
    assert noms == ["Agence d'exemple", "Institut d'exemple"]
    assert len(registre["files"]) == 2


def test_chaque_source_sait_de_quel_registre_elle_vient(tmp_path):
    """Sinon relire une déclaration demande de chercher dans quel fichier."""
    _ecrire(tmp_path, "a.yaml", UN_REGISTRE)
    _ecrire(tmp_path, "b.yaml", UN_AUTRE)

    origines = {
        source["name"]: source["registry_file"]
        for source in load_registry(str(tmp_path))["sources"]
    }

    assert origines["Institut d'exemple"] == "a.yaml"
    assert origines["Agence d'exemple"] == "b.yaml"


def test_un_chemin_de_fichier_ne_charge_que_celui_la(tmp_path):
    """Ce que faisaient les appels existants, et qui ne doit pas changer."""
    fichier = _ecrire(tmp_path, "a.yaml", UN_REGISTRE)
    _ecrire(tmp_path, "b.yaml", UN_AUTRE)

    registre = load_registry(str(fichier))

    assert [s["name"] for s in registre["sources"]] == ["Institut d'exemple"]


def test_un_repertoire_vide_refuse_encore_les_categories_d_autorite(tmp_path):
    """Perdre les fichiers ne doit pas ouvrir la porte."""
    registre = load_registry(str(tmp_path))

    verdict = check_source(
        "https://inconnu.test/x", SourceCategory.GOVERNMENT, registre=registre,
    )

    assert registre["loaded"] is False
    assert verdict["allowed"] is False
    assert "affirme une autorité" in verdict["reason"]


# ----------------------------------------------------------------------
# 2. Un domaine n'appartient qu'à un registre
# ----------------------------------------------------------------------

def test_un_domaine_declare_deux_fois_refuse_le_chargement(tmp_path):
    """
    La plateforme répondrait sinon selon l'ordre de chargement : le pire
    désaccord est celui que personne ne voit.
    """
    _ecrire(tmp_path, "a.yaml", UN_REGISTRE)
    _ecrire(tmp_path, "b.yaml", UN_REGISTRE.replace(
        "Institut d'exemple", "Le même domaine, sous un autre nom",
    ))

    with pytest.raises(SourceRefused, match="déclaré deux fois"):
        load_registry(str(tmp_path))


def test_le_refus_nomme_les_deux_fichiers(tmp_path):
    """Sans les deux noms, il faudrait chercher lequel corriger."""
    _ecrire(tmp_path, "a.yaml", UN_REGISTRE)
    _ecrire(tmp_path, "z.yaml", UN_REGISTRE)

    with pytest.raises(SourceRefused) as refus:
        load_registry(str(tmp_path))

    assert "a.yaml" in str(refus.value)
    assert "z.yaml" in str(refus.value)


def test_le_meme_domaine_deux_fois_dans_un_seul_fichier_est_aussi_refuse(tmp_path):
    """Un fichier n'est pas plus fiable parce qu'il est seul."""
    _ecrire(tmp_path, "a.yaml", """
sources:
  - name: "Institut d'exemple"
    scope: country:fr
    subjects: [science]
    category: government
    base_url: https://exemple-institut.fr
  - name: "Encore le même domaine"
    scope: country:fr
    subjects: [science]
    category: institutional
    base_url: https://exemple-institut.fr
""")

    with pytest.raises(SourceRefused, match="déclaré deux fois"):
        load_registry(str(tmp_path))


# ----------------------------------------------------------------------
# 3. Les refus fusionnent
# ----------------------------------------------------------------------

def test_un_refus_declare_dans_un_registre_vaut_pour_tous(tmp_path):
    """Le sens sûr de la fusion."""
    _ecrire(tmp_path, "a.yaml", UN_REGISTRE)
    _ecrire(tmp_path, "b.yaml", UN_AUTRE)
    registre = load_registry(str(tmp_path))

    verdict = check_source(
        "https://exemple-refuse.test/page", SourceCategory.INSTITUTIONAL,
        registre=registre,
    )

    assert verdict["allowed"] is False
    assert "anonyme" in verdict["reason"]


def test_un_refus_sait_aussi_d_ou_il_vient(tmp_path):
    """Le même besoin que pour une source."""
    _ecrire(tmp_path, "a.yaml", UN_REGISTRE)

    refus = load_registry(str(tmp_path))["deny"][0]

    assert refus["registry_file"] == "a.yaml"


# ----------------------------------------------------------------------
# 4. Le dépôt réel
# ----------------------------------------------------------------------

def test_le_registre_reel_se_charge_sans_doublon():
    """
    Le test qui compte : les registres du dépôt sont chargés ensemble, et
    aucun domaine n'y est déclaré deux fois.
    """
    registre = load_registry()

    assert registre["loaded"] is True
    domaines = [source["domain"] for source in registre["sources"]]
    assert len(domaines) == len(set(domaines))


def test_le_rapport_dit_quels_registres_il_a_lus():
    """Un compte global sans ventilation n'aide personne à relire."""
    rapport = registry_report()

    assert "senegal.yaml" in rapport["files"]
    assert sum(rapport["by_registry"].values()) == rapport["sources"]


def test_le_repertoire_des_registres_est_celui_du_depot():
    """La constante et la réalité, confrontées."""
    assert os.path.isdir(
        os.path.join(os.path.dirname(__file__), "..", REPERTOIRE_DES_REGISTRES)
    )


# ----------------------------------------------------------------------
# 5. Le registre mondial, et ce qu'il ne prétend pas (phase 51.2)
# ----------------------------------------------------------------------

def test_aucune_source_mondiale_ne_pretend_au_droit_ni_a_l_administration():
    """
    **La garde qui compte.** Un texte de loi n'a d'existence que sur son
    territoire, les démarches sont nationales, et le wolof ne s'explique pas
    par une grammaire générale. Une entrée mondiale qui déclarerait ces sujets
    ferait répondre une organisation internationale à la place du Journal
    officiel d'un pays.
    """
    from src.knowledge_engine.scope import NATIONAL_SUBJECTS

    nationaux = {sujet.value for sujet in NATIONAL_SUBJECTS}
    fautives = [
        source["name"]
        for source in load_registry()["sources"]
        if source["scope"] == "global" and set(source["subjects"]) & nationaux
    ]

    assert fautives == [], (
        f"Sources mondiales déclarant un sujet national : {fautives}"
    )


def test_le_registre_mondial_est_peuple_et_entierement_desactive():
    """Inscrire n'est pas activer : la règle vaut aussi pour ce qui est mondial."""
    mondiales = [
        source for source in load_registry()["sources"]
        if source["registry_file"] == "global.yaml"
    ]

    assert len(mondiales) >= 12
    assert all(source["enabled"] is False for source in mondiales)
    assert all(source["last_verified"] == "unknown" for source in mondiales)


def test_les_sources_mondiales_declarent_leur_rang():
    """
    Un rang replié depuis la catégorie est un rang que personne n'a relu. Pour
    un registre écrit d'un bloc, le déclarer est la relecture.
    """
    mondiales = [
        source for source in load_registry()["sources"]
        if source["registry_file"] == "global.yaml"
    ]

    assert all(source["tier_defaulted"] is False for source in mondiales)


def test_une_encyclopedie_et_des_preprints_restent_des_pistes():
    """
    Rang D : ils peuvent faire *chercher* quelque chose, ils n'entrent jamais
    comme fondement d'une affirmation. Les inscrire au rang qui leur revient
    vaut mieux que de les laisser hors registre, où celui qui ingère pourrait
    leur attribuer une catégorie d'autorité.
    """
    par_domaine = {
        source["domain"]: source["tier"].value
        for source in load_registry()["sources"]
    }

    assert par_domaine["wikipedia.org"] == "TIER_D_DISCOVERY_ONLY"
    assert par_domaine["arxiv.org"] == "TIER_D_DISCOVERY_ONLY"


def test_une_source_mondiale_a_quitte_le_registre_du_pays():
    """
    La FAO et l'OMS étaient déclarées dans `senegal.yaml` avec `scope: global`.
    Une source mondiale n'appartient pas au registre d'un pays — et le
    chargement refuse désormais qu'elle soit dans les deux.
    """
    origines = {
        source["domain"]: source["registry_file"]
        for source in load_registry()["sources"]
    }

    assert origines["fao.org"] == "global.yaml"
    assert origines["who.int"] == "global.yaml"
