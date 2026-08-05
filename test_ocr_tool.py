"""
Tests for the OCR tool.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.ocr.tool import OCRTool


@pytest.fixture
def ocr_tool():
    """Return an OCRTool instance with default configuration."""
    return OCRTool()


def test_ocr_tool_initialization(ocr_tool):
    """Test that the tool initializes with default configuration."""
    assert ocr_tool.default_lang == "eng"
    assert ocr_tool.tesseract_cmd is None


def test_ocr_tool_initialization_with_config():
    """Test initialization with custom configuration."""
    config = {"lang": "fra", "tesseract_cmd": "/usr/local/bin/tesseract"}
    tool = OCRTool(config)
    assert tool.default_lang == "fra"
    assert tool.tesseract_cmd == "/usr/local/bin/tesseract"


def test_ocr_tool_missing_dependencies():
    """Test that an ImportError is raised when Pillow or pytesseract is missing."""
    # Simulate missing dependencies by patching the modules
    with patch.dict("sys.modules", {"PIL": None, "pytesseract": None}):
        from src.tools.ocr import tool as ocr_tool_module
        # Force the flag to False (simulate missing)
        ocr_tool_module.OCR_AVAILABLE = False
        tool = OCRTool()
        with pytest.raises(ImportError, match="Pillow.*pytesseract"):
            tool._check_availability()


def test_ocr_tool_extract_text(ocr_tool):
    """Test extracting text from an image (mocked)."""
    with patch("src.tools.ocr.tool.Image") as mock_image, \
         patch("src.tools.ocr.tool.pytesseract") as mock_ocr, \
         patch("src.tools.ocr.tool.OCR_AVAILABLE", True):
        # Mock Image.open
        mock_img = MagicMock()
        mock_image.open.return_value = mock_img

        # Mock pytesseract outputs
        mock_ocr.image_to_string.return_value = "Bonjour le monde"
        mock_ocr.image_to_data.return_value = {
            "conf": ["45", "78", "-1", "90"],
            "left": [10, 20, 30, 40],
            "top": [10, 20, 30, 40],
            "width": [10, 10, 10, 10],
            "height": [10, 10, 10, 10],
            "text": ["Bonjour", "le", "", "monde"],
        }

        result = ocr_tool.execute("extract_text", "fake/path.png")

        # Verify calls
        mock_image.open.assert_called_once_with("fake/path.png")
        mock_ocr.image_to_string.assert_called_once()
        args, kwargs = mock_ocr.image_to_string.call_args
        assert args[0] == mock_img
        assert kwargs.get("lang") == "eng"
        assert kwargs.get("config") == ""

        # Verify result
        assert result["text"] == "Bonjour le monde"
        assert result["lang"] == "eng"
        # Average of 45, 78, 90 (ignore -1) = (45+78+90)/3 = 71.0
        assert abs(result["confidence"] - 71.0) < 0.001
        assert isinstance(result["boxes"], list)
        # Should have 3 boxes (excluding the -1 confidence)
        assert len(result["boxes"]) == 3


def test_ocr_tool_extract_text_with_lang(ocr_tool):
    """Test extracting text with language override."""
    with patch("src.tools.ocr.tool.Image") as mock_image, \
         patch("src.tools.ocr.tool.pytesseract") as mock_ocr, \
         patch("src.tools.ocr.tool.OCR_AVAILABLE", True):
        mock_img = MagicMock()
        mock_image.open.return_value = mock_img
        mock_ocr.image_to_string.return_value = "Hello"
        mock_ocr.image_to_data.return_value = {
            "conf": ["85"],
            "left": [0],
            "top": [0],
            "width": [10],
            "height": [10],
            "text": ["Hello"],
        }

        result = ocr_tool.execute(
            "extract_text", "fake/path.png", lang="fra+eng", config="--psm 6"
        )

        args, kwargs = mock_ocr.image_to_string.call_args
        assert kwargs.get("lang") == "fra+eng"
        assert kwargs.get("config") == "--psm 6"

        assert result["text"] == "Hello"
        assert result["lang"] == "fra+eng"


def test_ocr_tool_extract_text_bytes(ocr_tool):
    """Test extracting text from image bytes."""
    with patch("src.tools.ocr.tool.Image") as mock_image, \
         patch("src.tools.ocr.tool.pytesseract") as mock_ocr, \
         patch("src.tools.ocr.tool.OCR_AVAILABLE", True):
        mock_img = MagicMock()
        mock_image.open.return_value = mock_img
        # No need to patch io; we can use real BytesIO
        mock_ocr.image_to_string.return_value = "Test"
        mock_ocr.image_to_data.return_value = {
            "conf": ["80"],
            "left": [0],
            "top": [0],
            "width": [10],
            "height": [10],
            "text": ["Test"],
        }

        result = ocr_tool.execute("extract_text", b"fake bytes")

        # Verify that Image.open was called with a BytesIO instance
        mock_image.open.assert_called_once()
        args = mock_image.open.call_args[0]
        # First arg should be a BytesIO-like object (we don't need to inspect further)
        assert hasattr(args[0], 'read')
        assert result["text"] == "Test"


def test_ocr_tool_unknown_operation(ocr_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue"):
        ocr_tool.execute("unknown")