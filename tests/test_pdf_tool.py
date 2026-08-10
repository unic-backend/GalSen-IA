"""
Tests for the PDF tool.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.tools.pdf.tool import PDFTool


@pytest.fixture
def pdf_tool():
    """Return a PDFTool instance with default configuration."""
    return PDFTool()


def test_pdf_tool_initialization(pdf_tool):
    """Test that the tool initializes."""
    assert pdf_tool is not None


def test_pdf_tool_missing_dependencies():
    """Test that an ImportError is raised when PyPDF2 is missing."""
    with patch.dict("sys.modules", {"PyPDF2": None}):
        from src.tools.pdf import tool as pdf_tool_module

        # Temporarily set PDF_AVAILABLE to False
        original_pdf_available = pdf_tool_module.PDF_AVAILABLE
        pdf_tool_module.PDF_AVAILABLE = False
        pdf_tool_module.PyPDF2 = None

        try:
            tool = PDFTool()
            with pytest.raises(ImportError, match="PyPDF2"):
                tool._check_availability()
        finally:
            # Restore original values
            pdf_tool_module.PDF_AVAILABLE = original_pdf_available
            pdf_tool_module.PyPDF2 = __import__("PyPDF2") if original_pdf_available else None


def test_pdf_tool_extract_text(pdf_tool):
    """Test extracting text from a PDF (mocked)."""
    with patch("builtins.open", new_callable=lambda: MagicMock()) as mock_open, \
         patch("src.tools.pdf.tool.PyPDF2") as mock_pypdf, \
         patch("src.tools.pdf.tool.PDF_AVAILABLE", True):
        # Mock the file context manager
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        # Mock PdfReader and its pages
        mock_reader = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader
        mock_reader.pages.__len__.return_value = 2

        # Mock pages
        mock_page0 = MagicMock()
        mock_page0.extract_text.return_value = "Texte de la page 1"
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Texte de la page 2"
        mock_reader.pages.__getitem__.side_effect = lambda i: [mock_page0, mock_page1][i]

        result = pdf_tool.execute("extract_text", "fake/path.pdf")

        # Verify calls
        mock_open.assert_called_once_with("fake/path.pdf", "rb")
        mock_pypdf.PdfReader.assert_called_once_with(mock_file)
        assert mock_reader.pages.__len__.called
        # Check that extract_text was called on each page
        assert mock_page0.extract_text.called
        assert mock_page1.extract_text.called

        # Verify result
        assert result["text"] == "Texte de la page 1\n\nTexte de la page 2"
        assert result["num_pages"] == 2
        assert result["pages_extracted"] == [0, 1]


def test_pdf_tool_extract_specific_pages(pdf_tool):
    """Test extracting specific pages from a PDF."""
    with patch("builtins.open", new_callable=lambda: MagicMock()) as mock_open, \
         patch("src.tools.pdf.tool.PyPDF2") as mock_pypdf, \
         patch("src.tools.pdf.tool.PDF_AVAILABLE", True):
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        mock_reader = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader
        mock_reader.pages.__len__.return_value = 3

        mock_page0 = MagicMock()
        mock_page0.extract_text.return_value = "Page0"
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "Page1"
        mock_page2 = MagicMock()
        mock_page2.extract_text.return_value = "Page2"
        mock_reader.pages.__getitem__.side_effect = lambda i: [mock_page0, mock_page1, mock_page2][i]

        result = pdf_tool.execute("extract_text", "fake/path.pdf", pages=[0, 2])

        assert result["text"] == "Page0\n\nPage2"
        assert result["num_pages"] == 3
        assert result["pages_extracted"] == [0, 2]


def test_pdf_tool_extract_invalid_pages(pdf_tool):
    """Test that invalid page indices are ignored."""
    with patch("builtins.open", new_callable=lambda: MagicMock()) as mock_open, \
         patch("src.tools.pdf.tool.PyPDF2") as mock_pypdf, \
         patch("src.tools.pdf.tool.PDF_AVAILABLE", True):
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        mock_reader = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader
        mock_reader.pages.__len__.return_value = 2

        mock_page0 = MagicMock()
        mock_page0.extract_text.return_value = "P0"
        mock_page1 = MagicMock()
        mock_page1.extract_text.return_value = "P1"
        mock_reader.pages.__getitem__.side_effect = lambda i: [mock_page0, mock_page1][i]

        # Request pages 0, 5 (5 is out of range) and -1
        result = pdf_tool.execute("extract_text", "fake/path.pdf", pages=[0, 5, -1])

        # Only page 0 should be valid
        assert result["text"] == "P0"
        assert result["pages_extracted"] == [0]


def test_pdf_tool_extract_no_valid_pages(pdf_tool):
    """Test when no valid pages are requested."""
    with patch("builtins.open", new_callable=lambda: MagicMock()) as mock_open, \
         patch("src.tools.pdf.tool.PyPDF2") as mock_pypdf, \
         patch("src.tools.pdf.tool.PDF_AVAILABLE", True):
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        mock_reader = MagicMock()
        mock_pypdf.PdfReader.return_value = mock_reader
        mock_reader.pages.__len__.return_value = 2

        # Request pages out of range
        result = pdf_tool.execute("extract_text", "fake/path.pdf", pages=[5, 10])

        assert result["text"] == ""
        assert result["num_pages"] == 2
        assert result["pages_extracted"] == []


def test_pdf_tool_file_not_found(pdf_tool):
    """Test that FileNotFoundError is raised for missing file."""
    with patch("builtins.open", side_effect=FileNotFoundError), \
         patch("src.tools.pdf.tool.PDF_AVAILABLE", True):
        with pytest.raises(FileNotFoundError, match="Fichier PDF introuvable"):
            pdf_tool.execute("extract_text", "nonexistent.pdf")


def test_pdf_tool_invalid_path(pdf_tool):
    """Test that ValueError is raised for invalid path."""
    with patch("src.tools.pdf.tool.PDF_AVAILABLE", True):
        with pytest.raises(ValueError, match="chemin du fichier doit être une chaîne"):
            pdf_tool.execute("extract_text", "")
        with pytest.raises(ValueError, match="chemin du fichier doit être une chaîne"):
            pdf_tool.execute("extract_text", 123)


def test_pdf_tool_unknown_operation(pdf_tool):
    """Test that calling an unknown operation raises ValueError."""
    with pytest.raises(ValueError, match="Opération 'unknown' inconnue"):
        pdf_tool.execute("unknown")