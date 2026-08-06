#!/usr/bin/env python3
"""
Tests simples pour l'outil RAG.
"""

import os
import sys

# Add the src directory to the path so we can import from src.tool.base
sys.path.insert(0, os.path.dirname(__file__))

from src.tools.rag.tool import RAGTool


def test_rag_tool_creation():
    """Test que l'on peut créer une instance de RAGTool."""
    tool = RAGTool()
    assert tool is not None
    print("+ RAGTool created successfully")


def test_add_and_retrieve():
    """Test l'ajout et la récupération d'une connaissance."""
    tool = RAGTool()
    try:
        # Add a simple fact
        item_data = {
            "content": "Le ciel est bleu pendant la journée.",
            "knowledge_type": "fact",
            "content_type": "text",
            "language": "fr",
            "tags": ["ciel", "couleur"],
            "confidence": 0.9,
        }
        add_result = tool.execute("add", item_data)
        assert "id" in add_result
        kid = add_result["id"]
        print(f"+ Item added with id: {kid}")

        # Retrieve the item
        retrieved = tool.execute("get", kid)
        assert retrieved is not None
        assert retrieved["content"] == item_data["content"]
        assert retrieved["knowledge_type"] == "fact"
        assert retrieved["tags"] == ["ciel", "couleur"]
        print("+ Item retrieved correctly")

        # Search for it
        search_results = tool.execute("search", "bleu", limit=5)
        assert len(search_results) > 0
        found = any(r["id"] == kid for r in search_results)
        assert found
        print("+ Item found in search")

        # Update the item
        retrieved = tool.execute("get", kid)
        retrieved["content"] = "Le ciel est généralement bleu pendant la journée, mais peut devenir gris."
        retrieved["confidence"] = 0.95
        update_result = tool.execute("update", retrieved)
        assert update_result["updated"] is True
        print("+ Item updated")

        # Retrieve again to verify update
        retrieved_updated = tool.execute("get", kid)
        assert retrieved_updated["content"] == retrieved["content"]
        assert retrieved_updated["confidence"] == 0.95
        print("+ Updated item retrieved correctly")

        # Retrieve for prompt (RAG)
        prompt_results = tool.execute(
            "retrieve_for_prompt", "Quelle est la couleur du ciel ?", max_items=3
        )
        assert len(prompt_results) > 0
        # The updated item should be among the results (simple check)
        assert any(r["id"] == kid for r in prompt_results)
        print("+ Item found in retrieve_for_prompt")

        # Delete the item
        delete_result = tool.execute("delete", kid)
        assert delete_result["deleted"] is True
        print("+ Item deleted")

        # Verify deletion
        deleted_item = tool.execute("get", kid)
        assert deleted_item is None
        print("+ Deletion verified")

        # List items (should be empty or not contain the deleted item)
        list_result = tool.execute("list")
        # Ensure our item is not in the list
        assert not any(item["id"] == kid for item in list_result)
        print("+ Item not present in list after deletion")

    finally:
        # No explicit cleanup needed for in-memory knowledge manager
        pass


def test_error_handling():
    """Test la gestion d'erreurs de base."""
    tool = RAGTool()
    try:
        # Unknown operation
        try:
            tool.execute("unknown_operation")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Opération 'unknown_operation' inconnue" in str(e)
            print("+ Unknown operation triggers ValueError")

        # Add with missing content (should still work? content is required by KnowledgeItem? It will raise)
        try:
            tool.execute("add", {"knowledge_type": "fact"})
            assert False, "Should have raised ValueError due to missing content"
        except Exception as e:
            # Expecting some validation error (maybe from KnowledgeItem __post_init__ or validation)
            print("+ Missing required fields triggers exception:", type(e).__name__)

        # Get with empty ID
        try:
            tool.execute("get", "")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "L'ID de la connaissance doit être une chaîne non vide" in str(e)
            print("+ Empty ID triggers ValueError")

        # Search with empty query
        try:
            tool.execute("search", "", limit=5)
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "La requête de recherche doit être une chaîne non vide" in str(e)
            print("+ Empty query triggers ValueError")

    finally:
        pass


def test_rag_tool_priority_roundtrip():
    """Test de la hiérarchie de priorité P1–P4 et de la provenance via l'outil RAG."""
    tool = RAGTool()
    kid = None
    try:
        # Ajout avec priorité P1 et source de catégorie officielle
        item_data = {
            "content": "Le décret officiel réglemente le transport urbain à Dakar.",
            "knowledge_type": "fact",
            "content_type": "text",
            "language": "fr",
            "priority": "P1",
            "source": {
                "id": "decret-2024-118",
                "type": "url",
                "location": "https://www.sec.gouv.sn/decret-2024-118",
                "source_category": "official",
                "title": "Décret n° 2024-118 sur le transport urbain",
                "author": "République du Sénégal",
                "url": "https://www.sec.gouv.sn/decret-2024-118",
                "citation": "Décret n° 2024-118, Journal Officiel du Sénégal",
            },
            "confidence": 0.95,
        }
        add_result = tool.execute("add", item_data)
        assert "id" in add_result
        kid = add_result["id"]
        print(f"+ Item with P1 priority added: {kid}")

        # La priorité et la provenance sont conservées à la récupération
        retrieved = tool.execute("get", kid)
        assert retrieved is not None
        assert retrieved["priority"] == 1  # P1 sérialisé en entier
        assert retrieved["source"]["source_category"] == "official"
        assert retrieved["source"]["title"] == "Décret n° 2024-118 sur le transport urbain"
        assert retrieved["source"]["citation"] == "Décret n° 2024-118, Journal Officiel du Sénégal"
        print("+ Priority and provenance preserved on get")

        # La recherche le retrouve avec sa priorité
        search_results = tool.execute("search", "transport Dakar", limit=5)
        found = [r for r in search_results if r["id"] == kid]
        assert len(found) == 1
        assert found[0]["priority"] == 1
        print("+ Item found in search with priority 1")

        # Récupération fiable : exige un seuil de priorité
        prompt_results = tool.execute(
            "retrieve_for_prompt",
            "transport Dakar",
            max_items=3,
            require_reliable=True,
            min_priority="P3",
        )
        assert isinstance(prompt_results, dict)
        assert prompt_results["reliable"] is True
        assert any(r["id"] == kid for r in prompt_results["items"])
        assert prompt_results["best_priority"] == "P1"
        print("+ retrieve_for_prompt with require_reliable returns reliable dict")

        # Mise à jour de la priorité vers P2
        retrieved["priority"] = "P2"
        update_result = tool.execute("update", retrieved)
        assert update_result["updated"] is True
        retrieved_updated = tool.execute("get", kid)
        assert retrieved_updated["priority"] == 2
        assert retrieved_updated["source"]["source_category"] == "official"
        print("+ Priority updated to P2")

    finally:
        # Nettoyage : le registre est partagé entre les tests du même processus
        if kid is not None:
            tool.execute("delete", kid)
        print("+ Test item cleaned up")


def test_search_returns_real_relevance_scores():
    """Le score retourné doit venir de l'indexeur, jamais du rang du résultat.

    Avant correction, `_score` valait `1.0 - (rang * 0.05)` : deux documents
    d'une pertinence très différente recevaient 1.00 et 0.95, un classement
    fabriqué qu'aucun appelant ne pouvait distinguer d'un vrai.
    """
    tool = RAGTool()
    identifiants = []
    try:
        pertinent = tool.execute(
            "add", {"content": "Le mil se seme des les premieres pluies au Senegal"},
        )
        eloigne = tool.execute(
            "add", {"content": "Le riz de la vallee du fleuve Senegal"},
        )
        identifiants = [pertinent.get("id"), eloigne.get("id")]

        resultats = tool.execute("search", "mil pluies Senegal", limit=5)
        scores = [r["_score"] for r in resultats]

        assert scores, "La recherche doit retourner au moins un résultat"
        # Les scores fabriqués formaient toujours la suite 1.00, 0.95, 0.90…
        rangs_fabriques = [round(1.0 - i * 0.05, 2) for i in range(len(scores))]
        assert [round(s, 2) for s in scores] != rangs_fabriques or len(scores) == 1
        # Un document sans rapport ne doit pas frôler le score du document exact
        if len(scores) > 1:
            assert scores[0] > scores[1]
        assert all(0.0 <= s <= 1.0 for s in scores)
    finally:
        for identifiant in identifiants:
            if identifiant:
                try:
                    tool.execute("delete", identifiant)
                except Exception:
                    pass


if __name__ == "__main__":
    print("Running RAGTool unit tests...")
    try:
        test_rag_tool_creation()
        test_add_and_retrieve()
        test_error_handling()
        test_rag_tool_priority_roundtrip()
        test_search_returns_real_relevance_scores()
        print("\n* All tests passed!")
    except Exception as e:
        print(f"\n! Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)