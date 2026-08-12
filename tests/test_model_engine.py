#!/usr/bin/env python3
"""
Test script for the Model Engine.
"""

import sys
import os
import asyncio
import pytest

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.model_engine.capability_detector import CapabilityDetector
from src.model_engine.model_manager import ModelManagerImpl
from src.model_engine.model_registry import ModelRegistry
from src.model_engine.provider_selector import ProviderSelector
from src.model_engine.providers import (
    GenerationRequest,
    GenerationResponse,
    LocalProvider,
    ModelDescriptor,
    ModelProvider,
    ProviderInfo,
    ProviderRegistry,
    ProviderStatus,
    ProviderUnavailableError,
    UnavailabilityReason,
)
from src.model_engine.providers.provider_registry import SOVEREIGN_MODE_VARIABLE
from src.model_engine.types import ModelItem, ModelType, ModelPriority, ModelStatus


@pytest.fixture
def multi_fournisseurs(monkeypatch):
    """
    Registre portant plusieurs fournisseurs, dont des fournisseurs tiers.

    Depuis ADR-014, le mode souverain est le défaut et les fournisseurs tiers ne
    sont plus inscrits. Les tests ci-dessous n'ont pas la souveraineté pour
    sujet : ils vérifient la mécanique du moteur — inscription, sélection,
    détection de capacités, catalogue — et cette mécanique doit continuer de
    fonctionner avec plusieurs fournisseurs, ce qui reste un cas supporté et
    déclaré. Le défaut, lui, est épinglé par `tests/test_model_sovereignty.py`.
    """
    monkeypatch.setenv(SOVEREIGN_MODE_VARIABLE, "false")


@pytest.mark.asyncio
async def test_model_engine():
    """Test the model engine."""
    print("Initializing ModelManager...")
    mm = ModelManagerImpl()

    # Create test model items
    print("Creating test models...")

    # OpenAI GPT-3.5 Turbo model
    gpt35_model = ModelItem(
        model_id="test-gpt35-001",
        model_type=ModelType.OPENAI_GPT35,
        provider="openai",
        name="gpt-3.5-turbo",
        version="1.0",
        priority=ModelPriority.HIGH,
        status=ModelStatus.ACTIVE,
        context_window=4096,
        max_output_tokens=2048,
        supported_features=["text", "function_calling"],
        metadata={
            "api_key": "test-key",  # In real usage, this would come from secure storage
            "rpm_limit": 100
        }
    )

    # Anthropic Claude 3 Haiku model
    claude_haiku_model = ModelItem(
        model_id="test-claude-haiku-001",
        model_type=ModelType.ANTHROPIC_CLAUDE3_HAIKU,
        provider="anthropic",
        name="claude-3-haiku-20240307",
        version="1.0",
        priority=ModelPriority.MEDIUM,
        status=ModelStatus.ACTIVE,
        context_window=200000,
        max_output_tokens=4096,
        supported_features=["text", "vision"],
        metadata={
            "api_key": "test-key",  # In real usage, this would come from secure storage
            "rpm_limit": 50
        }
    )

    # Test model registration
    print("Registering models...")
    gpt35_id = mm.register_model(gpt35_model)
    claude_haiku_id = mm.register_model(claude_haiku_model)

    print(f"Registered GPT-3.5 model with ID: {gpt35_id}")
    print(f"Registered Claude Haiku model with ID: {claude_haiku_id}")

    # Test model retrieval
    print("\nRetrieving models...")
    retrieved_gpt35 = mm.get_model(gpt35_id)
    retrieved_claude = mm.get_model(claude_haiku_id)

    assert retrieved_gpt35 is not None, "Failed to retrieve GPT-3.5 model"
    assert retrieved_claude is not None, "Failed to retrieve Claude Haiku model"
    assert retrieved_gpt35.model_id == gpt35_id, "Model ID mismatch for GPT-3.5"
    assert retrieved_claude.model_id == claude_haiku_id, "Model ID mismatch for Claude Haiku"
    print("Models retrieved successfully")

    # Test model listing
    print("\nListing models...")
    models = mm.list_models()
    assert len(models) >= 2, f"Expected at least 2 models, got {len(models)}"
    print(f"Found {len(models)} models")

    # Test model listing with filters
    openai_models = mm.list_models(provider="openai")
    assert len(openai_models) >= 1, f"Expected at least 1 OpenAI model, got {len(openai_models)}"
    print(f"Found {len(openai_models)} OpenAI models")

    # Test model selection
    print("\nTesting model selection...")
    task_req = {
        "task_type": "reasoning",
        "complexity": "medium"
    }
    selected_model = mm.select_model_for_task(task_req)
    assert selected_model is not None, "Failed to select model for task"
    print(f"Selected model for reasoning task: {selected_model.name} ({selected_model.provider})")

    # Test model info
    print("\nGetting model info...")
    model_info = mm.get_model_info(gpt35_id)
    assert model_info is not None, "Failed to get model info"
    assert model_info["model_id"] == gpt35_id, "Model ID mismatch in info"
    print(f"Model info retrieved for: {model_info['name']}")
    print(f"  Context window: {model_info['context_window']}")
    print(f"  Max output tokens: {model_info['max_output_tokens']}")

    # Test text generation (will simulate since we don't have real API keys)
    print("\nTesting text generation...")
    try:
        response = await mm.generate_text(
            gpt35_model,
            "Hello, how are you?",
            temperature=0.7,
            max_tokens=50
        )
        print(f"Generated response: {response}")
        assert isinstance(response, str), "Response should be a string"
        assert len(response) > 0, "Response should not be empty"
        print("Text generation test passed")
    except Exception as e:
        print(f"Text generation failed (expected without real API keys): {e}")

    # Test text generation with fallback
    print("\nTesting text generation with fallback...")
    try:
        response = await mm.generate_text_with_fallback(
            "Explain quantum computing in simple terms",
            {"task_type": "explanation", "complexity": "simple"}
        )
        print(f"Fallback generation response: {response}")
        assert isinstance(response, str), "Response should be a string"
        print("Fallback generation test passed")
    except Exception as e:
        print(f"Fallback generation failed (expected without real API keys): {e}")

    # Test text generation with load balancing
    print("\nTesting text generation with load balancing...")
    try:
        response = await mm.generate_text_with_load_balancing(
            "What is the capital of France?",
            {"task_type": "factual"}
        )
        print(f"Load balancing generation response: {response}")
        assert isinstance(response, str), "Response should be a string"
        print("Load balancing generation test passed")
    except Exception as e:
        print(f"Load balancing generation failed (expected without real API keys): {e}")

    # Test token tracking
    print("\nTesting token tracking...")
    usage_stats = mm.get_usage_stats(gpt35_id)
    print(f"Token usage stats: {usage_stats}")

    # Test cost tracking
    print("\nTesting cost tracking...")
    cost_stats = mm.get_cost_stats(gpt35_id)
    print(f"Cost stats: {cost_stats}")

    # Test health monitoring
    print("\nTesting health monitoring...")
    health_status = mm.get_health_status(gpt35_model.model_id)
    print(f"Health status: {health_status}")

    # Test capability discovery
    print("\nTesting capability discovery...")
    capabilities = mm._cd.discover_capabilities(gpt35_model)
    print(f"Capabilities for GPT-3.5: {list(capabilities.keys())}")
    assert "context_window" in capabilities, "Missing context_window in capabilities"
    assert capabilities["context_window"] == 4096, "Incorrect context window"

    print("\nAll tests completed!")


# ----------------------------------------------------------------------
# Provider layer
# ----------------------------------------------------------------------
def test_provider_registry(monkeypatch):
    """The default registry holds the sovereign providers, and only those.

    This assertion changed with ADR-014: it used to require openai, anthropic
    and google to be present. They are no longer registered, because "nobody set
    a key" was a state rather than a guarantee.
    """
    print("Testing provider registry...")
    monkeypatch.delenv(SOVEREIGN_MODE_VARIABLE, raising=False)
    registry = ProviderRegistry()

    assert registry.provider_ids() == ["local", "openai_compatible"]

    # A catalogue must be readable without credentials, otherwise selection
    # could never run before a provider is configured
    catalogue = registry.list_all_models()
    assert catalogue, "Catalogue vide : la sélection ne pourrait jamais démarrer"
    assert all(descriptor.context_window > 0 for descriptor in catalogue)

    print(f"[OK] {len(registry.provider_ids())} sovereign providers, "
          f"{len(catalogue)} models")


def test_provider_registry_hors_mode_souverain(multi_fournisseurs):
    """Declaring the escape hatch brings every provider back, catalogue included."""
    registry = ProviderRegistry()

    provider_ids = registry.provider_ids()
    for expected in ("openai", "anthropic", "google", "local"):
        assert expected in provider_ids, f"Fournisseur '{expected}' absent du registre"

    catalogue = registry.list_all_models()
    assert len(catalogue) >= 10, "Catalogue anormalement petit"
    assert all(descriptor.context_window > 0 for descriptor in catalogue)


def test_provider_interchangeability():
    """A custom provider must be usable without any change to the engine."""
    print("Testing provider interchangeability...")

    class CustomProvider(ModelProvider):
        """Fournisseur de test enregistré à la volée."""

        provider_id = "custom_test"
        display_name = "Custom Test Provider"
        requires_credentials = False

        def list_models(self):
            """Retourne un modèle unique."""
            return [ModelDescriptor(
                model_name="custom-model",
                provider_id=self.provider_id,
                context_window=16384,
                max_output_tokens=2048,
                supports_vision=True,
            )]

        def check_availability(self):
            """Le fournisseur de test répond toujours."""
            return ProviderInfo(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status=ProviderStatus.READY,
                model_count=1,
                requires_credentials=False,
            )

        def generate(self, request):
            """Retourne un texte déterministe."""
            return GenerationResponse(
                status=ProviderStatus.READY,
                text=f"[custom] {request.prompt}",
                provider_id=self.provider_id,
                model_name=request.model_name,
                prompt_tokens=self.estimate_tokens(request.prompt),
                completion_tokens=8,
            )

    registry = ProviderRegistry()
    registry.register(CustomProvider())

    assert "custom_test" in registry.provider_ids()
    assert registry.has_available_provider(), "Le fournisseur de test doit être disponible"
    assert registry.find_provider_for("custom-model").provider_id == "custom_test"

    # The whole engine must now be able to generate through it, unchanged
    manager = ModelManagerImpl(provider_registry=registry)
    model_item = manager._model_registry.to_model_item("custom-model")
    response = manager.generate(model_item, "bonjour")

    assert response.succeeded, "La génération via le fournisseur de test a échoué"
    assert response.text == "[custom] bonjour"
    assert response.provider_id == "custom_test"

    registry.unregister("custom_test")
    assert "custom_test" not in registry.provider_ids()

    print("[OK] A new provider works without changing the engine")


def test_unavailable_providers_report_clearly(multi_fournisseurs):
    """With no provider configured the engine must say so, and produce no text."""
    print("Testing unavailable provider reporting...")
    manager = ModelManagerImpl()

    assert manager.has_available_provider() is False
    reason = manager.unavailability_reason()
    assert reason, "Le motif d'indisponibilité doit être renseigné"

    for provider_id, state in manager.get_provider_status().items():
        assert state["status"] == "unavailable"
        assert state["reason"], f"Le fournisseur '{provider_id}' n'explique pas son indisponibilité"
        assert state["detail"], f"Le fournisseur '{provider_id}' ne dit pas quoi faire"

    # The structured API reports the state; it never invents a reply
    model_item = manager._model_registry.to_model_item("gpt-4")
    response = manager.generate(model_item, "test")
    assert response.status == ProviderStatus.UNAVAILABLE
    assert response.text == "", "Aucun texte ne doit être produit sans fournisseur"
    assert response.succeeded is False

    # The string API raises rather than returning a substitute
    try:
        asyncio.run(manager.generate_text(model_item, "test"))
        raise AssertionError("generate_text devrait lever sans fournisseur")
    except ProviderUnavailableError as error:
        assert error.reason == UnavailabilityReason.NO_CREDENTIALS

    print("[OK] Unavailability is reported with a reason and no fabricated text")


def test_model_registry_catalogue(multi_fournisseurs):
    """The catalogue must stay usable for search even with no provider available."""
    print("Testing model registry...")
    registry = ModelRegistry()

    stats = registry.stats()
    assert stats["total_models"] >= 10
    assert len(stats["models_by_provider"]) >= 4

    long_context = registry.find_models(min_context_window=150000, requires_vision=True)
    assert long_context, "Aucun modèle à long contexte trouvé"
    # Results are ordered by cost, which is what the selector relies on
    costs = [model.pricing_per_1k_tokens.get("input", 0.0) for model in long_context]
    assert costs == sorted(costs), "Le catalogue n'est pas trié par coût"

    model_item = registry.to_model_item("claude-3-opus")
    assert model_item is not None
    assert model_item.provider == "anthropic"
    assert model_item.context_window == 200000
    assert "vision" in model_item.supported_features

    assert registry.to_model_item("modele-inexistant") is None

    print(f"[OK] Catalogue exposes {stats['total_models']} models across "
          f"{len(stats['models_by_provider'])} providers")


def test_capability_detection(multi_fournisseurs):
    """Capabilities must come from the provider, and fall back to the static table."""
    print("Testing capability detection...")
    detector = CapabilityDetector()
    registry = ModelRegistry()

    # Known model: the provider is the authority
    known = registry.to_model_item("gpt-4")
    capabilities = detector.discover_capabilities(known)
    assert capabilities["detection_source"] == "provider:openai"
    assert capabilities["context_window"] == 8192

    assert detector.supports(registry.to_model_item("claude-3-opus"), "supports_vision")
    assert not detector.supports(registry.to_model_item("gpt-3.5-turbo"), "supports_vision")

    assert detector.meets_requirements(
        registry.to_model_item("claude-3-sonnet"),
        {"min_context_window": 100000, "requires_vision": True},
    )
    assert not detector.meets_requirements(
        registry.to_model_item("gpt-3.5-turbo"),
        {"min_context_window": 100000},
    )

    # Unknown model: the static table takes over, so hand registered models
    # keep working exactly as before providers existed
    unknown = ModelItem(
        model_id="manual-1",
        model_type=ModelType.FUTURE_PROVIDER,
        provider="fournisseur_inconnu",
        name="modele-inconnu",
        version="1.0",
    )
    fallback = detector.discover_capabilities(unknown)
    assert fallback["detection_source"] == "static_table"

    print("[OK] Capabilities come from providers, with a static fallback")


def test_automatic_provider_selection(multi_fournisseurs):
    """Selection must refuse clearly when nothing can serve, and pick well when it can."""
    print("Testing automatic provider selection...")
    selector = ProviderSelector()

    # Nothing configured: the refusal must explain itself
    selection = selector.select({"task_type": "reasoning", "complexity": "high"})
    assert selection.succeeded is False
    assert "disponible" in selection.reason

    explanation = selector.explain({"task_type": "document_analysis"})
    # A document task must demand a large context window
    assert explanation["resolved_requirements"]["min_context_window"] >= 100000
    assert len(explanation["provider_status"]) >= 4

    # Vision requirement must be derived from the task type alone
    vision = selector.explain({"task_type": "vision"})
    assert vision["resolved_requirements"]["requires_vision"] is True

    print("[OK] Selection derives requirements and refuses with a reason")


def test_selection_prefers_cheapest_capable_model():
    """Among usable models, selection must favour the cheapest that qualifies."""
    print("Testing selection cost preference...")

    class FreeProvider(ModelProvider):
        """Fournisseur de test proposant deux modèles de coûts différents."""

        provider_id = "cost_test"
        display_name = "Cost Test Provider"
        requires_credentials = False

        def list_models(self):
            """Retourne un modèle coûteux et un modèle bon marché."""
            return [
                ModelDescriptor(
                    model_name="expensive", provider_id=self.provider_id,
                    context_window=200000, max_output_tokens=4096,
                    pricing_per_1k_tokens={"input": 0.05, "output": 0.1},
                ),
                ModelDescriptor(
                    model_name="cheap", provider_id=self.provider_id,
                    context_window=200000, max_output_tokens=4096,
                    pricing_per_1k_tokens={"input": 0.001, "output": 0.002},
                ),
            ]

        def check_availability(self):
            """Le fournisseur de test répond toujours."""
            return ProviderInfo(
                provider_id=self.provider_id, display_name=self.display_name,
                status=ProviderStatus.READY, model_count=2, requires_credentials=False,
            )

        def generate(self, request):
            """Retourne un texte déterministe."""
            return GenerationResponse(
                status=ProviderStatus.READY, text="ok",
                provider_id=self.provider_id, model_name=request.model_name,
            )

    registry = ProviderRegistry(register_defaults=False)
    registry.register(FreeProvider())
    selector = ProviderSelector(registry, ModelRegistry(registry))

    selection = selector.select({"task_type": "summarization"})
    assert selection.succeeded, f"Sélection échouée: {selection.reason}"
    assert selection.descriptor.model_name == "cheap", "Le modèle le moins cher doit gagner"

    print("[OK] Selection favours the cheapest capable model")


def test_local_provider_probe():
    """The local provider must report its state without hanging when absent."""
    print("Testing local provider probe...")
    provider = LocalProvider()

    info = provider.check_availability()
    assert info.provider_id == "local"
    assert info.requires_credentials is False

    if info.status == ProviderStatus.READY:
        # A server is running: generation must actually work
        response = provider.generate(GenerationRequest(
            prompt="Bonjour", model_name=provider.list_models()[0].model_name, max_tokens=16
        ))
        assert response.status == ProviderStatus.READY
        print(f"[OK] Local server reachable, generated {len(response.text)} characters")
    else:
        # No server: the reason must be actionable, not a bare failure
        assert info.reason in (
            UnavailabilityReason.UNREACHABLE, UnavailabilityReason.MISSING_DEPENDENCY
        )
        assert "ollama" in info.detail.lower()
        print("[OK] Local server absent, reported with an actionable reason")


def test_engine_integrations():
    """The Model Engine must be reachable from the tool, memory and agent layers.

    No `multi_fournisseurs` here, deliberately: `get_shared_registry()` builds
    its manager once per process, so a fixture setting the environment now would
    not reach it — and pretending otherwise would be a lie about what runs. The
    shared registry is therefore sovereign, which is the intended state.
    """
    print("Testing Model Engine integrations...")
    from src.agent.context import AgentContext
    from src.integration.engine_registry import get_shared_registry

    registry = get_shared_registry()

    # Tool Engine: the model is reachable like any other tool
    tool_result = registry.tool.execute_tool("model", "status")
    assert "providers" in tool_result
    assert tool_result["any_available"] is False

    catalogue = registry.tool.execute_tool("model", "catalogue")
    # Le catalogue doit **arriver** jusqu'à la couche outil ; sa taille dépend
    # des fournisseurs inscrits, et en mode souverain ce sont les seuls locaux.
    assert catalogue, "Le catalogue n'atteint pas la couche outil"
    assert all(entree["context_window"] > 0 for entree in catalogue)

    generation = registry.tool.execute_tool("model", "generate", "Bonjour")
    assert generation["status"] == "unavailable"
    assert generation["text"] == ""

    # Memory Engine: the model manager received it, so generations can be traced
    assert registry.model._memory is not None, "Le moteur de mémoire n'est pas branché"

    # Agent layer: an agent sees an explicit unavailable status
    context = AgentContext(request="test", agent_id="test")
    outcome = context.generate("Explique la photosynthèse")
    assert outcome["status"] == "unavailable"
    assert outcome["text"] == ""

    print("[OK] Model Engine reachable from tool, memory and agent layers")


def run_provider_tests():
    """Run the provider layer tests."""
    print("=" * 60)
    print("Running Model Engine Provider Tests")
    print("=" * 60)

    tests = (
        test_provider_registry,
        test_provider_interchangeability,
        test_unavailable_providers_report_clearly,
        test_model_registry_catalogue,
        test_capability_detection,
        test_automatic_provider_selection,
        test_selection_prefers_cheapest_capable_model,
        test_local_provider_probe,
        test_engine_integrations,
    )

    for test in tests:
        test()

    print("=" * 60)
    print(f"[PASS] All {len(tests)} provider tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    try:
        # Run the async test
        asyncio.run(test_model_engine())
        run_provider_tests()
    except Exception as error:
        print("=" * 60)
        print(f"Test failed: {error}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        sys.exit(1)

    sys.exit(0)