"""
Politique de routage des modèles (VOLET 30 — ADR-014).

Trois choses étaient fausses, et deux d'entre elles mentaient à l'appelant :

1. **La règle de raisonnement complexe ne pouvait plus jamais s'appliquer.**
   `SimpleModelSelector` filtrait sur `OPENAI_GPT4`, `ANTHROPIC_CLAUDE3_OPUS` et
   `GOOGLE_GEMINI_PRO` ; depuis ADR-014 ces fournisseurs ne sont plus inscrits.
   La branche donnait l'impression d'un routage soigné et ne s'exécutait jamais.
2. **`max_cost` et `required_capabilities` étaient acceptés puis ignorés**, avec
   un `pass` commenté « dans une implémentation réelle ». Poser un plafond de
   coût qui n'existe pas est pire que ne pas en proposer.
3. **La politique vivait en dur** dans `ProviderSelector.TASK_REQUIREMENTS`,
   alors qu'elle dépend des modèles installés sur la machine.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.model_selector import SimpleModelSelector  # noqa: E402
from src.model_engine.routing_policy import (  # noqa: E402
    RoutingPolicy,
    reset_policy,
    shared_policy,
)
from src.model_engine.types import (  # noqa: E402
    ModelItem,
    ModelPriority,
    ModelStatus,
    ModelType,
)


def _modele(nom: str, cout=None, features=None, model_type=ModelType.LOCAL_OLLAMA) -> ModelItem:
    """Construit un modèle enregistré, avec ou sans tarif déclaré."""
    return ModelItem(
        model_id=f"id-{nom}",
        model_type=model_type,
        provider="local",
        name=nom,
        version="1",
        priority=ModelPriority.MEDIUM,
        status=ModelStatus.ACTIVE,
        context_window=32000,
        max_output_tokens=2048,
        supported_features=features or ["text"],
        metadata=({"pricing_per_1k_tokens": {"input": cout}} if cout is not None else {}),
    )


@pytest.fixture(autouse=True)
def politique_neuve():
    """La politique partagée ne doit pas fuir d'un test à l'autre."""
    reset_policy()
    yield
    reset_policy()


# ----------------------------------------------------------------------
# La politique vient de la configuration
# ----------------------------------------------------------------------

def test_la_politique_est_lue_dans_la_configuration():
    """Elle vivait en dur ; elle dépend des modèles installés, donc du déploiement."""
    politique = RoutingPolicy()

    assert "code_generation" in politique.task_types()
    assert "conversation" in politique.task_types()
    assert set(politique.families()) == {"samp", "top"}


def test_une_politique_illisible_ne_bloque_pas_le_routage(tmp_path, caplog):
    """Mieux vaut router prudemment que refuser de router — mais il faut le dire."""
    with caplog.at_level("WARNING"):
        politique = RoutingPolicy(str(tmp_path / "absent.yaml"))

    decision = politique.decide({"task_type": "reasoning"})

    assert decision.requirements["min_context_window"] >= 4096
    assert "secours" in caplog.text


def test_le_type_de_tache_choisit_la_famille():
    """SamP raisonne et parle, ToP code et voit (ADR-014)."""
    politique = RoutingPolicy()

    assert politique.decide({"task_type": "reasoning"}).family == "samp"
    assert politique.decide({"task_type": "code_generation"}).family == "top"
    assert politique.decide({"task_type": "vision"}).family == "top"


def test_une_famille_absente_est_annoncee_et_non_maquillee():
    """
    SamP et ToP n'existent pas encore (VOLET 33).

    Router en silence vers un modèle générique ferait croire à l'appelant qu'il
    parle à SamP, et il tirerait de fausses conclusions de la réponse.
    """
    politique = RoutingPolicy()

    decision = politique.decide(
        {"task_type": "code_generation"}, available_models=["llama3", "mistral"]
    )

    assert decision.family == "top"
    assert decision.family_available is False
    assert "top" in decision.reason and "repli" in decision.reason


def test_une_famille_presente_est_reconnue():
    """Le contre-test : le jour où ToP existe, la politique doit le voir."""
    politique = RoutingPolicy()

    decision = politique.decide(
        {"task_type": "code_generation"}, available_models=["top-1-7b-instruct"]
    )

    assert decision.family_available is True
    assert politique.family_of("top-1-7b-instruct") == "top"
    assert politique.family_of("samp-1-7b") == "samp"
    assert politique.family_of("llama3") is None


def test_une_question_simple_ne_justifie_pas_le_gros_modele():
    """La règle « question simple → petit modèle » du cahier des charges."""
    politique = RoutingPolicy()

    assert politique.decide({"task_type": "conversation"}).requirements["prefer_cheapest"]
    assert politique.decide({"task_type": "analysis"}).requirements["prefer_cheapest"] is False


def test_la_complexite_releve_le_contexte_sans_jamais_l_abaisser():
    """Une tâche annoncée complexe ne doit pas finir sur un modèle plus court."""
    politique = RoutingPolicy()

    simple = politique.decide({"task_type": "reasoning", "complexity": "simple"})
    complexe = politique.decide({"task_type": "reasoning", "complexity": "very_high"})

    # `reasoning` exige 8192 ; « simple » vaut 4096 et ne doit pas gagner.
    assert simple.requirements["min_context_window"] == 8192
    assert complexe.requirements["min_context_window"] == 100000


def test_ce_que_l_appelant_exige_prime_sur_la_configuration():
    """Il en sait plus qu'un fichier sur sa propre requête."""
    politique = RoutingPolicy()

    decision = politique.decide({
        "task_type": "conversation",
        "min_context_window": 64000,
        "requires_vision": True,
        "required_capabilities": ["code_generation"],
    })

    assert decision.requirements["min_context_window"] == 64000
    assert decision.requirements["requires_vision"] is True
    assert decision.requirements["preferred_features"] == ["code_generation"]


def test_le_plafond_de_cout_est_retenu():
    """Il était accepté puis oublié."""
    decision = RoutingPolicy().decide({"task_type": "reasoning", "max_cost": 0.002})

    assert decision.requirements["max_input_cost"] == 0.002


def test_le_plafond_le_plus_strict_gagne():
    """Entre la politique et l'appelant, c'est la contrainte la plus forte qui vaut."""
    politique = RoutingPolicy()
    politique._politique["tasks"]["reasoning"]["max_input_cost"] = 0.01

    decision = politique.decide({"task_type": "reasoning", "max_cost": 0.001})

    assert decision.requirements["max_input_cost"] == 0.001


def test_la_politique_est_partagee():
    """Deux composants qui routent différemment feraient deux plateformes."""
    assert shared_policy() is shared_policy()


# ----------------------------------------------------------------------
# Le sélecteur applique enfin ce qu'on lui demande
# ----------------------------------------------------------------------

def test_le_plafond_de_cout_ecarte_vraiment_un_modele_trop_cher():
    """
    Le défaut mesuré : `max_cost` suivi d'un `pass`.

    L'appelant croyait poser une limite ; toute la sélection l'ignorait.
    """
    cher = _modele("modele-cher", cout=0.05)
    abordable = _modele("modele-abordable", cout=0.001)

    choisi = SimpleModelSelector().select_model(
        [cher, abordable], {"task_type": "reasoning", "max_cost": 0.002}
    )

    assert choisi.name == "modele-abordable"


def test_un_modele_sans_tarif_declare_reste_eligible():
    """
    Un tarif inconnu n'est pas un tarif infini.

    Un modèle local est gratuit et n'annonce rien : l'écarter faute de tarif
    éliminerait précisément les modèles souverains d'ADR-014.
    """
    local = _modele("modele-local")
    cher = _modele("modele-cher", cout=0.05)

    choisi = SimpleModelSelector().select_model(
        [cher, local], {"task_type": "reasoning", "max_cost": 0.002}
    )

    assert choisi.name == "modele-local"


def test_les_capacites_exigees_filtrent_vraiment():
    """Second paramètre accepté puis ignoré."""
    generaliste = _modele("generaliste", features=["text"])
    codeur = _modele("codeur", features=["text", "code_generation"])

    choisi = SimpleModelSelector().select_model(
        [generaliste, codeur],
        {"task_type": "code_generation", "required_capabilities": ["code_generation"]},
    )

    assert choisi.name == "codeur"


def test_la_famille_est_preferee_quand_elle_est_servie():
    """Router une tâche de code ailleurs que sur ToP ignorerait ADR-014."""
    generique = _modele("mistral-7b", features=["text", "code_generation"])
    de_la_famille = _modele("top-1-7b", features=["text", "code_generation"])

    choisi = SimpleModelSelector().select_model(
        [generique, de_la_famille], {"task_type": "code_generation"}
    )

    assert choisi.name == "top-1-7b"


def test_aucune_regle_ne_vide_la_selection():
    """
    Un filtre qui ne laisse rien ne doit pas rendre `None` : il doit s'effacer.

    Sinon une exigence trop stricte transformerait un modèle utilisable en
    absence de modèle, et la plateforme répondrait 503 avec un modèle sous la main.
    """
    seul = _modele("seul-modele", cout=0.05, features=["text"])

    choisi = SimpleModelSelector().select_model(
        [seul],
        {"task_type": "code_generation", "max_cost": 0.0001,
         "required_capabilities": ["vision"]},
    )

    assert choisi is not None
    assert choisi.name == "seul-modele"


# ----------------------------------------------------------------------
# Mesurer ce que chaque route coûte (ch. 02)
# ----------------------------------------------------------------------

def test_le_cout_est_ventile_par_route():
    """
    Le coût total répond à « combien » ; la ventilation répond à « pour quoi ».

    Le suiveur savait ventiler par `operation_type` depuis le début, et tout le
    monde lui passait la valeur par défaut : une politique de routage qu'on ne
    peut pas mesurer ne peut pas être améliorée.
    """
    from src.model_engine.cost_tracker import InMemoryCostTracker

    suiveur = InMemoryCostTracker()
    modele = _modele("modele-a", cout=0.001)

    suiveur.track_cost(modele, 1000, operation_type="route:code_generation")
    suiveur.track_cost(modele, 3000, operation_type="route:conversation")

    par_route = suiveur.cost_by_route()

    assert set(par_route) == {"route:code_generation", "route:conversation"}
    # La route la plus coûteuse arrive en tête : c'est celle qu'on regarde.
    assert list(par_route)[0] == "route:conversation"


def test_sans_generation_la_ventilation_est_vide_et_non_nulle():
    """Des zéros se liraient comme une mesure ; un dictionnaire vide dit l'absence."""
    from src.model_engine.cost_tracker import InMemoryCostTracker

    assert InMemoryCostTracker().cost_by_route() == {}
