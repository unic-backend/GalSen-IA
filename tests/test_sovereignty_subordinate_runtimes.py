"""
La souveraineté d'ADR-014 vue depuis un **runtime subordonné**.

`tests/test_model_sovereignty.py` éprouve le chemin de modèle de GalSen IA : le
registre n'inscrit aucun fournisseur hébergé, même avec les trois clés
renseignées. Cette garantie est réelle et elle est **aveugle à un second
runtime** — un moteur de codage, un greffon, un harnais externe — qui parlerait
à un fournisseur hébergé sans jamais passer par `ModelRouter`. Le registre
resterait souverain, son test resterait vert, et la plateforme serait redevenue
locataire par la porte d'à côté.

Deux audits externes ont relevé ce trou indépendamment (ADR-034 pour OpenClaw,
ADR-035 pour DeepSeek Harness). **Deux projets, le même angle mort : il est
ici.** Ce fichier écrit ce que personne n'affirmait.

Ce qu'il établit :

1. Le seul canal par lequel une clé peut atteindre un runtime subordonné est
   `ModelSpec.api_key_env`, et **aucun modèle joignable en mode souverain n'en
   déclare**.
2. L'environnement d'un sous-processus n'hérite d'aucune clé hébergée.
3. **La protection n'est pas dans l'adaptateur** — un `ModelSpec` fabriqué à la
   main est transmis tel quel. C'est la sélection qui garde la porte, et ce
   fichier le dit au lieu de laisser croire à une seconde barrière.
4. Aucun adaptateur ne porte son propre magasin d'identifiants.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.coding_engine.adapters.aider_adapter import (  # noqa: E402
    _traduire_modele as _traduire_aider,
)
from src.coding_engine.adapters.swe_agent_adapter import (  # noqa: E402
    _traduire_modele as _traduire_swe,
)
from src.coding_engine.manager import VARIABLE_MOTEURS, CodingEngineManager  # noqa: E402
from src.coding_engine.types import ModelSpec  # noqa: E402
from src.coding_engine.workspace import sanitized_environment  # noqa: E402
from src.model_engine.providers.provider_registry import (  # noqa: E402
    SOVEREIGN_MODE_VARIABLE,
    ProviderRegistry,
)

#: Les trois clés qu'ADR-014 refuse de laisser gouverner la plateforme.
CLES_HEBERGEES = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY")

#: Une valeur reconnaissable : si elle ressort quelque part, elle vient d'ici.
VALEUR_TEMOIN = "cle-hebergee-qui-fonctionnerait-0dd1"

#: Les moteurs livrés. ADR-035 en propose un quatrième (`dsh`) et n'autorise pas
#: son implémentation ; le jour où il entre, ce fichier doit le couvrir.
MOTEURS_COUVERTS = {"aider", "openhands", "swe_agent"}


@pytest.fixture
def souverain_avec_cles(monkeypatch):
    """Mode souverain par défaut, et les trois clés hébergées bien présentes."""
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    monkeypatch.delenv(VARIABLE_MOTEURS, raising=False)
    for cle in CLES_HEBERGEES:
        monkeypatch.setenv(cle, VALEUR_TEMOIN)


# ----------------------------------------------------------------------
# 1. Le seul canal, et il est vide
# ----------------------------------------------------------------------

def test_aucun_modele_joignable_ne_declare_de_variable_de_cle(souverain_avec_cles):
    """
    La garantie qui manquait, énoncée là où elle se rompt.

    Un runtime subordonné ne reçoit de clé que par `ModelSpec.api_key_env`, dont
    la valeur est lue dans `os.environ` par les trois adaptateurs. Si aucun
    modèle joignable ne nomme de variable, **aucune clé ne peut sortir** — et
    c'est vrai avec les trois clés hébergées renseignées, pas seulement en leur
    absence.
    """
    registre = ProviderRegistry()

    declarees = []
    for fournisseur in registre.list_providers():
        for modele in fournisseur.list_models():
            metadonnees = getattr(modele, "metadata", None) or {}
            nom = metadonnees.get("api_key_env")
            if nom:
                declarees.append((getattr(modele, "model_name", modele), nom))

    assert declarees == [], (
        "Un modèle joignable en mode souverain déclare une variable de clé : "
        f"{declarees}. Si elle nomme une clé hébergée, un moteur de codage la "
        "transmettra à son sous-processus, et le test de souveraineté du "
        "registre continuera de passer."
    )


def test_la_garde_mord_quand_un_modele_declare_une_cle(souverain_avec_cles, monkeypatch):
    """
    Un garde qu'on n'a pas vu refuser ne garde rien.

    Le test précédent passerait aussi si `list_models()` rendait vide ou si
    `metadata` n'était jamais lu. Ici un modèle joignable se met à déclarer
    `OPENAI_API_KEY`, et la lecture doit le voir.
    """
    registre = ProviderRegistry()
    local = registre.get("local")
    modeles = local.list_models()
    monkeypatch.setattr(modeles[0], "metadata", {"api_key_env": "OPENAI_API_KEY"},
                        raising=False)
    monkeypatch.setattr(local, "list_models", lambda: modeles)

    declarees = [
        (getattr(m, "model_name", m), (getattr(m, "metadata", None) or {})["api_key_env"])
        for f in registre.list_providers()
        for m in f.list_models()
        if (getattr(m, "metadata", None) or {}).get("api_key_env")
    ]

    assert declarees, "La lecture ne voit pas une variable de clé pourtant déclarée."


# ----------------------------------------------------------------------
# 2. L'environnement du sous-processus
# ----------------------------------------------------------------------

def test_l_environnement_d_un_sous_processus_n_herite_d_aucune_cle(souverain_avec_cles):
    """
    Un fils hérite de tout par défaut ; la liste blanche est ce qui l'empêche.

    Le test porte sur les **valeurs** autant que sur les noms : une clé recopiée
    sous un autre nom fuirait tout autant.
    """
    environnement = sanitized_environment()

    for cle in CLES_HEBERGEES:
        assert cle not in environnement
    assert VALEUR_TEMOIN not in environnement.values()


def test_une_valeur_fournie_explicitement_passe_quand_meme(souverain_avec_cles):
    """
    Le contre-test, et il dit exactement où s'arrête la protection.

    `sanitized_environment` filtre l'**héritage**, pas l'injection : l'appelant
    qui fournit une clé la voit arriver. Croire l'inverse ferait prendre la
    liste blanche pour une barrière qu'elle n'est pas.
    """
    environnement = sanitized_environment({"OPENAI_API_KEY": VALEUR_TEMOIN})

    assert environnement["OPENAI_API_KEY"] == VALEUR_TEMOIN


# ----------------------------------------------------------------------
# 3. Où la protection n'est pas
# ----------------------------------------------------------------------

def test_l_adaptateur_aider_transmet_la_cle_qu_on_lui_nomme(souverain_avec_cles):
    """
    Constat, pas défaut : la garde est en amont.

    Si un jour un modèle joignable déclarait `OPENAI_API_KEY`, aider recevrait
    la clé. C'est le premier test de ce fichier qui l'empêche, et lui seul.
    """
    _, variables, _ = _traduire_aider(
        ModelSpec(provider_id="openai", model_name="gpt-4o",
                  api_key_env="OPENAI_API_KEY")
    )

    assert variables["OPENAI_API_KEY"] == VALEUR_TEMOIN


def test_l_adaptateur_swe_agent_transmet_la_cle_qu_on_lui_nomme(souverain_avec_cles):
    """Même constat pour SWE-agent, par un chemin différent."""
    _, cle, _ = _traduire_swe(
        ModelSpec(provider_id="anthropic", model_name="claude",
                  api_key_env="ANTHROPIC_API_KEY")
    )

    assert cle == VALEUR_TEMOIN


def test_un_modele_sans_variable_ne_transmet_rien(souverain_avec_cles):
    """L'état réel d'aujourd'hui : `api_key_env` vaut `None` partout."""
    _, variables, _ = _traduire_aider(
        ModelSpec(provider_id="local", model_name="qwen2.5-coder:14b")
    )
    _, cle, _ = _traduire_swe(
        ModelSpec(provider_id="local", model_name="qwen2.5-coder:14b")
    )

    assert VALEUR_TEMOIN not in variables.values()
    assert cle is None


# ----------------------------------------------------------------------
# 4. Aucun magasin d'identifiants propre
# ----------------------------------------------------------------------

def test_aucun_adaptateur_ne_porte_son_propre_magasin_d_identifiants(souverain_avec_cles):
    """
    Ce qu'ADR-034 et ADR-035 refusent à un runtime externe, la plateforme se
    l'applique : un adaptateur construit avec les trois clés présentes n'en
    retient aucune.
    """
    gestionnaire = CodingEngineManager()

    porteurs = []
    for identifiant in gestionnaire.engine_ids:
        adaptateur = gestionnaire.get(identifiant)
        for nom, valeur in vars(adaptateur).items():
            if isinstance(valeur, str) and VALEUR_TEMOIN in valeur:
                porteurs.append(f"{identifiant}.{nom}")

    assert porteurs == [], (
        f"Un adaptateur retient une clé hébergée : {porteurs}. Un runtime "
        "subordonné portant ses propres identifiants sort du chemin de "
        "`ModelRouter`, et la souveraineté ne serait plus qu'une déclaration."
    )


def test_le_fichier_couvre_tous_les_moteurs_declares(monkeypatch):
    """
    Une couverture qui ne se maintient pas toute seule se périme.

    ADR-035 place DeepSeek Harness en quatrième adaptateur sans autoriser son
    implémentation. Le jour où il est déclaré, ce test échoue — et c'est la
    seule chose qui obligera à vérifier qu'il ne porte pas sa propre clé.
    """
    monkeypatch.delenv(VARIABLE_MOTEURS, raising=False)

    declares = set(CodingEngineManager().engine_ids)

    assert declares == MOTEURS_COUVERTS, (
        f"Moteurs déclarés : {sorted(declares)}, couverts ici : "
        f"{sorted(MOTEURS_COUVERTS)}. Un moteur nouveau doit être ajouté à ce "
        "fichier avant d'être considéré comme sûr vis-à-vis d'ADR-014."
    )
