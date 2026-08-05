"""
Tests for the embeddings tool.
"""

from importlib.util import find_spec
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.tools.embeddings.tool import EmbeddingsTool

# `sentence-transformers` est une dépendance optionnelle (requirements-optional.txt).
# Les tests qui simulent le vrai modèle doivent pouvoir l'importer pour le patcher :
# ils sont ignorés quand elle est absente. Le comportement du tool sans la dépendance
# reste couvert par test_embeddings_tool_missing_sentence_transformer.
requires_sentence_transformers = pytest.mark.skipif(
    find_spec("sentence_transformers") is None,
    reason="sentence-transformers n'est pas installé (dépendance optionnelle)",
)


@pytest.fixture
def embeddings_tool():
    """Return an EmbeddingsTool instance with default configuration."""
    return EmbeddingsTool()


def test_embeddings_tool_initialization(embeddings_tool):
    """Test that the tool initializes with default configuration."""
    assert embeddings_tool.model_name == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    assert embeddings_tool.device is None
    assert embeddings_tool.normalize_embeddings is True
    assert embeddings_tool._model is None


def test_embeddings_tool_initialization_with_config():
    """Test initialization with custom configuration."""
    config = {
        "model_name": "test-model",
        "device": "cpu",
        "normalize_embeddings": False,
    }
    tool = EmbeddingsTool(config)
    assert tool.model_name == "test-model"
    assert tool.device == "cpu"
    assert tool.normalize_embeddings is False


@requires_sentence_transformers
def test_embeddings_tool_embed_single_text(embeddings_tool):
    """Test embedding a single string."""
    # We need to mock the SentenceTransformer class and its encode method
    with patch("sentence_transformers.SentenceTransformer") as mock_st:
        mock_instance = mock_st.return_value
        # The encode method returns a numpy array when convert_to_numpy=True
        mock_instance.encode.return_value = np.array([[0.1, 0.2, 0.3]])

        result = embeddings_tool.execute("embed", "Hello world")

        # Check that the model's encode method was called
        mock_instance.encode.assert_called_once()
        args, kwargs = mock_instance.encode.call_args
        # The first argument should be a list containing the single string
        assert args[0] == ["Hello world"]
        # Check that normalize_embeddings was passed
        assert kwargs.get("normalize_embeddings") is True
        # The result should be a list of embeddings (list of list of floats)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], list)
        assert result[0] == [0.1, 0.2, 0.3]


@requires_sentence_transformers
def test_embeddings_tool_embed_multiple_texts(embeddings_tool):
    """Test embedding a list of strings."""
    with patch("sentence_transformers.SentenceTransformer") as mock_st:
        mock_instance = mock_st.return_value
        mock_instance.encode.return_value = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])

        result = embeddings_tool.execute(
            "embed", ["Hello world", "Goodbye world"]
        )

        mock_instance.encode.assert_called_once()
        args, kwargs = mock_instance.encode.call_args
        assert args[0] == ["Hello world", "Goodbye world"]
        assert kwargs.get("normalize_embeddings") is True
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0] == [0.1, 0.2, 0.3]
        assert result[1] == [0.4, 0.5, 0.6]


@requires_sentence_transformers
def test_embeddings_tool_embed_with_normalize_false():
    """Test embedding with normalization disabled."""
    config = {"normalize_embeddings": False}
    tool = EmbeddingsTool(config)
    with patch("sentence_transformers.SentenceTransformer") as mock_st:
        mock_instance = mock_st.return_value
        mock_instance.encode.return_value = np.array([[0.1, 0.2, 0.3]])

        result = tool.execute("embed", "Test")

        mock_instance.encode.assert_called_once()
        args, kwargs = mock_instance.encode.call_args
        assert kwargs.get("normalize_embeddings") is False
        assert result == [[0.1, 0.2, 0.3]]


def test_embeddings_tool_missing_sentence_transformer():
    """Test that an ImportError is raised when sentence-transformers is not installed."""
    # We'll mock the import inside the _get_model method to raise ImportError
    def mock_import(name, *args, **kwargs):
        if name == "sentence_transformers":
            raise ImportError("No module named 'sentence_transformers'")
        # For other imports, use the real import
        return __import__(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        tool = EmbeddingsTool()
        with pytest.raises(ImportError, match="sentence_transformers"):
            tool._get_model()


def test_embeddings_tool_unknown_operation(embeddings_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue"):
        embeddings_tool.execute("unknown")