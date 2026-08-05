#!/usr/bin/env python3
"""
Test suite for the Document Intelligence Engine.
"""

import os
import sys
import tempfile
import json
import csv
import zipfile
from pathlib import Path

# Add the src directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from document_intelligence_engine.document_manager import DocumentManagerImpl
from document_intelligence_engine.document_loader_factory import DocumentLoaderFactory
from document_intelligence_engine.keyword_qa_engine import SimpleQAEngine
from document_intelligence_engine.lru_document_cache import LRUDocumentCache
from document_intelligence_engine.types import DocumentItem, DocumentType


def test_document_manager_initialization():
    """Test that the document manager initializes correctly."""
    print("Testing document manager initialization...")
    manager = DocumentManagerImpl()
    assert manager is not None
    print("[OK] Document manager initialized successfully")


def test_text_document_loading():
    """Test loading a text document."""
    print("Testing text document loading...")
    manager = DocumentManagerImpl()

    # Create a temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test document.\nIt has multiple lines.\n")
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Verify the document was loaded correctly
        assert doc is not None
        assert doc.document_type == DocumentType.TXT
        assert "This is a test document." in doc.content
        assert doc.title == os.path.basename(temp_file).replace('.txt', '')

        # Verify it was registered
        retrieved_doc = manager.get_document(doc.document_id)
        assert retrieved_doc is not None
        assert retrieved_doc.document_id == doc.document_id

        print("[OK] Text document loaded successfully")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_markdown_document_loading():
    """Test loading a markdown document."""
    print("Testing markdown document loading...")
    manager = DocumentManagerImpl()

    # Create a temporary markdown file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write("# Test Document\n\nThis is a **test** markdown file.")
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Verify the document was loaded correctly
        assert doc is not None
        assert doc.document_type == DocumentType.MARKDOWN
        assert "# Test Document" in doc.content
        assert doc.title == os.path.basename(temp_file).replace('.md', '')

        print("[OK] Markdown document loaded successfully")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_csv_document_loading():
    """Test loading a CSV document."""
    print("Testing CSV document loading...")
    manager = DocumentManagerImpl()

    # Create a temporary CSV file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['Name', 'Age', 'City'])
        writer.writerow(['Alice', '30', 'New York'])
        writer.writerow(['Bob', '25', 'Los Angeles'])
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Verify the document was loaded correctly
        assert doc is not None
        assert doc.document_type == DocumentType.CSV
        assert 'Name,Age,City' in doc.content
        assert 'Alice,30,New York' in doc.content
        assert doc.title == os.path.basename(temp_file).replace('.csv', '')

        print("[OK] CSV document loaded successfully")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_json_document_loading():
    """Test loading a JSON document."""
    print("Testing JSON document loading...")
    manager = DocumentManagerImpl()

    # Create a temporary JSON file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        data = {"name": "John", "age": 30, "city": "New York"}
        json.dump(data, f)
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Verify the document was loaded correctly
        assert doc is not None
        assert doc.document_type == DocumentType.TXT  # JSON is treated as text
        assert '"name": "John"' in doc.content
        assert doc.title == os.path.basename(temp_file).replace('.json', '')

        print("[OK] JSON document loaded successfully")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_chunking():
    """Test document chunking functionality."""
    print("Testing document chunking...")
    manager = DocumentManagerImpl()

    # Create a temporary text file with enough content to be chunked
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # Write enough text to ensure it gets chunked
        f.write("This is the first paragraph. " * 50)  # About 1000 characters
        f.write("\n\n")
        f.write("This is the second paragraph. " * 50)  # About 1000 characters
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Chunk the document
        chunks = manager.chunk_document(doc.document_id, chunk_size=500, overlap=50)

        # Verify we got chunks
        assert len(chunks) > 0
        assert all(chunk.document_id == doc.document_id for chunk in chunks)
        assert all(len(chunk.content) <= 550 for chunk in chunks)  # Allowing for word boundary adjustment

        print(f"[OK] Document chunked into {len(chunks)} pieces")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_indexing_and_search():
    """Test document indexing and search functionality."""
    print("Testing document indexing and search...")
    manager = DocumentManagerImpl()

    # Create two temporary text files with different content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f1:
        f1.write("The quick brown fox jumps over the lazy dog.")
        file1 = f1.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
        f2.write("A quick brown dog outpaces a quick fox.")
        file2 = f2.name

    try:
        # Load the documents
        doc1 = manager.load_document(file1)
        doc2 = manager.load_document(file2)

        # Index the documents
        manager.index_document(doc1.document_id)
        manager.index_document(doc2.document_id)

        # Search for a term that should be in both documents
        results = manager.search_documents("quick brown", limit=2)

        # Verify we got results
        assert len(results) > 0
        # Both documents should contain "quick brown" so both should appear in results
        doc_ids = [doc.document_id for doc, score in results]
        assert doc1.document_id in doc_ids
        assert doc2.document_id in doc_ids

        # Search for a term that should be only in the first document
        results = manager.search_documents("lazy dog", limit=1)
        assert len(results) == 1
        assert results[0][0].document_id == doc1.document_id

        print("[OK] Document indexing and search working correctly")
    finally:
        # Clean up
        os.unlink(file1)
        os.unlink(file2)


def test_document_retrieval():
    """Test document retrieval functionality."""
    print("Testing document retrieval...")
    manager = DocumentManagerImpl()

    # Create a temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is a test document for retrieval testing.\n" * 10)
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Index the document
        manager.index_document(doc.document_id)

        # Retrieve relevant chunks for a query
        chunks = manager.retrieve_relevant_chunks("test document", limit=3)

        # Verify we got chunks
        assert len(chunks) > 0
        assert all(chunk.document_id == doc.document_id for chunk in chunks)
        assert all("test document" in chunk.content.lower() for chunk in chunks)

        print("[OK] Document retrieval working correctly")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_summarization():
    """Test document summarization functionality."""
    print("Testing document summarization...")
    manager = DocumentManagerImpl()

    # Create a temporary text file with multiple sentences
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("This is the first sentence. This is the second sentence. ")
        f.write("This is the third sentence. This is the fourth sentence. ")
        f.write("This is the fifth sentence.")
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Summarize the document (default should be 3 sentences)
        summary = manager.summarize_document(doc.document_id)

        # Verify we got a summary
        assert summary is not None
        assert len(summary) > 0
        # Should contain some of the original content
        assert "first sentence" in summary or "second sentence" in summary or "third sentence" in summary

        print("[OK] Document summarization working correctly")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_validation():
    """Test document validation functionality."""
    print("Testing document validation...")
    manager = DocumentManagerImpl()

    # Create a temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Valid document content.")
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Validate the document
        is_valid, errors = manager.validate_document(doc.document_id)

        # Verify it's valid
        assert is_valid == True
        assert len(errors) == 0

        print("[OK] Document validation working correctly")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_metadata_extraction():
    """Test document metadata extraction functionality."""
    print("Testing document metadata extraction...")
    manager = DocumentManagerImpl()

    # Create a temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Test content for metadata extraction.")
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)

        # Extract metadata
        metadata = manager.extract_metadata(doc.document_id)

        # Verify we got metadata
        assert metadata is not None
        assert hasattr(metadata, 'word_count')
        assert hasattr(metadata, 'character_count')
        assert hasattr(metadata, 'line_count')
        assert metadata.word_count > 0
        assert metadata.character_count > 0
        assert metadata.line_count >= 1

        print("[OK] Document metadata extraction working correctly")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_versioning():
    """Test document versioning functionality."""
    print("Testing document versioning...")
    manager = DocumentManagerImpl()

    # Create a temporary text file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("Original document content.")
        temp_file = f.name

    try:
        # Load the document
        doc = manager.load_document(temp_file)
        original_version = doc.version

        # Create a new version
        changes = {"content": "Updated document content."}
        new_doc = manager.create_version(doc.document_id, changes)

        # Verify the new version
        assert new_doc is not None
        assert new_doc.document_id != doc.document_id  # New ID
        assert new_doc.version == original_version + 1
        assert new_doc.content == "Updated document content."
        assert new_doc.parent_id == doc.document_id

        print("[OK] Document versioning working correctly")
    finally:
        # Clean up
        os.unlink(temp_file)


def test_document_comparison():
    """Test document comparison functionality."""
    print("Testing document comparison...")
    manager = DocumentManagerImpl()

    # Create two temporary text files
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f1:
        f1.write("The quick brown fox jumps over the lazy dog.")
        file1 = f1.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
        f2.write("The quick brown fox jumps over the lazy dog.")  # Same content
        file2 = f2.name

    try:
        # Load the documents
        doc1 = manager.load_document(file1)
        doc2 = manager.load_document(file2)

        # Compare the documents
        comparison = manager.compare_documents(doc1.document_id, doc2.document_id)

        # Verify the comparison results
        assert comparison is not None
        assert 'similarity' in comparison
        assert comparison['similarity'] == 1.0  # Should be identical

        print("[OK] Document comparison working correctly")
    finally:
        # Clean up
        os.unlink(file1)
        os.unlink(file2)


def test_document_duplicate_detection():
    """Test document duplicate detection functionality."""
    print("Testing document duplicate detection...")
    manager = DocumentManagerImpl()

    # Create two temporary text files with identical content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f1:
        f1.write("Identical content for both files.")
        file1 = f1.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
        f2.write("Identical content for both files.")
        file2 = f2.name

    # Create a third file with different content
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f3:
        f3.write("Different content for this file.")
        file3 = f3.name

    try:
        # Load the documents
        doc1 = manager.load_document(file1)
        doc2 = manager.load_document(file2)
        doc3 = manager.load_document(file3)

        # Detect duplicates with a high threshold
        duplicates = manager.detect_duplicates(threshold=0.9)

        # Verify we found the duplicate pair
        assert len(duplicates) > 0
        # Check that doc1 and doc2 are identified as duplicates
        doc_ids = [d[0].document_id for d in duplicates] + [d[1].document_id for d in duplicates]
        assert doc1.document_id in doc_ids
        assert doc2.document_id in doc_ids

        print("[OK] Document duplicate detection working correctly")
    finally:
        # Clean up
        os.unlink(file1)
        os.unlink(file2)
        os.unlink(file3)


def test_html_document_loading():
    """Test loading an HTML document."""
    print("Testing HTML document loading...")
    manager = DocumentManagerImpl()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(
            "<html><head><title>Rapport Senegal</title></head>"
            "<body><script>var ignored = 1;</script>"
            "<p>Le rapport annuel.</p><img src=\"figures/carte.png\"></body></html>"
        )
        temp_file = f.name

    try:
        doc = manager.load_document(temp_file)

        assert doc.document_type == DocumentType.HTML
        assert doc.title == "Rapport Senegal"
        # Text is extracted, script bodies are not part of the readable content
        assert "Le rapport annuel." in doc.content
        assert "var ignored" not in doc.content

        # Images are declared in the source markup, not in the extracted text
        images = manager.extract_images(doc.document_id)
        assert len(images) == 1
        assert images[0]["name"] == "carte.png"
        assert images[0]["origin"] == "reference"

        print("[OK] HTML document loaded successfully")
    finally:
        os.unlink(temp_file)


def test_question_answering():
    """Test the keyword based question answering engine."""
    print("Testing question answering...")
    manager = DocumentManagerImpl()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(
            "Dakar is the capital of Senegal. "
            "The Senegalese economy relies on agriculture and fishing. "
            "Wolof is widely spoken in the country."
        )
        temp_file = f.name

    try:
        doc = manager.load_document(temp_file)

        answer, sources = manager.answer_question_with_sources("What is the capital of Senegal?")
        assert "Dakar" in answer
        assert len(sources) > 0
        assert all(chunk.document_id == doc.document_id for chunk in sources)

        # A question with no lexical overlap must not invent an answer
        empty_answer = manager.answer_question("Quelle est la recette du couscous royal ?")
        assert empty_answer == SimpleQAEngine.NO_ANSWER_MESSAGE

        print("[OK] Question answering working correctly")
    finally:
        os.unlink(temp_file)


def test_table_extraction():
    """Test table extraction from a document."""
    print("Testing table extraction...")
    manager = DocumentManagerImpl()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write("# Report\n\n")
        f.write("| Region | Population |\n")
        f.write("| Dakar | 3800000 |\n")
        f.write("| Thies | 2000000 |\n")
        temp_file = f.name

    try:
        doc = manager.load_document(temp_file)
        tables = manager.extract_tables(doc.document_id)

        assert len(tables) == 1
        table = tables[0]
        assert table["separator"] == "|"
        assert table["headers"] == ["Region", "Population"]
        assert table["column_count"] == 2
        assert table["row_count"] == 2
        assert table["rows"][0] == ["Dakar", "3800000"]

        print("[OK] Table extraction working correctly")
    finally:
        os.unlink(temp_file)


def test_version_history():
    """Test that the version history follows the whole document lineage."""
    print("Testing version history...")
    manager = DocumentManagerImpl()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write("First revision.")
        temp_file = f.name

    try:
        original = manager.load_document(temp_file)
        second = manager.create_version(original.document_id, {"content": "Second revision."})
        third = manager.create_version(second.document_id, {"content": "Third revision."})

        # Every version is a document in its own right, retrievable by ID
        assert manager.get_document(second.document_id) is not None
        assert third.version == 3
        assert third.parent_id == second.document_id

        # The history is the same whichever version is used as entry point
        history = manager.get_version_history(third.document_id)
        assert [doc.document_id for doc in history] == [
            original.document_id, second.document_id, third.document_id
        ]
        assert manager.get_version_history(original.document_id) == history

        print("[OK] Version history working correctly")
    finally:
        os.unlink(temp_file)


def test_cache_expiration():
    """Test the LRU cache eviction and time to live."""
    print("Testing document cache...")
    cache = LRUDocumentCache(capacity=2)

    cache.set("a", "value-a")
    cache.set("b", "value-b")
    # Reading "a" makes "b" the least recently used entry
    assert cache.get("a") == "value-a"
    cache.set("c", "value-c")

    assert cache.get("b") is None
    assert cache.get("a") == "value-a"
    assert cache.get("c") == "value-c"

    # An entry past its time to live is reported as absent
    cache.clear()
    cache.set("short", "value", ttl=-1)
    assert cache.get("short") is None

    cache.set("keep", "value")
    assert cache.delete("keep") is True
    assert cache.delete("keep") is False

    print("[OK] Document cache working correctly")


def test_chunking_respects_chunk_size():
    """Test that no chunk ever exceeds the requested size."""
    print("Testing chunk size limits...")
    manager = DocumentManagerImpl()

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        # A single very long word cannot be split on a word boundary
        f.write("A" * 300 + " " + "short words here " * 20)
        temp_file = f.name

    try:
        doc = manager.load_document(temp_file)
        chunks = manager.chunk_document(doc.document_id, chunk_size=100, overlap=20)

        assert len(chunks) > 0
        assert all(len(chunk.content) <= 100 for chunk in chunks)
        # Chunks must cover the document from start to end
        assert chunks[0].start_index == 0
        assert chunks[-1].end_index == len(doc.content)

        print(f"[OK] Chunk size respected across {len(chunks)} chunks")
    finally:
        os.unlink(temp_file)


def test_ooxml_image_extraction():
    """Test image extraction from an Office archive."""
    print("Testing OOXML image extraction...")
    manager = DocumentManagerImpl()

    # An Office file is a ZIP archive: images live under word/media for DOCX.
    # Building the archive directly keeps the test free of optional dependencies.
    temp_file = os.path.join(tempfile.gettempdir(), f"galsen_test_{os.getpid()}.docx")
    with zipfile.ZipFile(temp_file, 'w') as archive:
        archive.writestr("word/document.xml", "<document/>")
        archive.writestr("word/media/image1.png", b"fake-png-bytes")
        archive.writestr("word/media/image2.jpeg", b"fake-jpeg-bytes")

    try:
        document = DocumentItem(
            document_id="",
            document_type=DocumentType.DOCX,
            title="Archive test",
            content="Contenu du document.",
            metadata={"source": temp_file},
        )
        doc_id = manager.register_document(document)

        images = manager.extract_images(doc_id)
        assert len(images) == 2
        assert {image["name"] for image in images} == {"image1.png", "image2.jpeg"}
        assert all(image["origin"] == "embedded" for image in images)
        # Binary data stays out of the result unless explicitly requested
        assert "data" not in images[0]

        with_data = manager.extract_images(doc_id, include_data=True)
        assert with_data[0]["data"] == b"fake-png-bytes"

        print("[OK] OOXML image extraction working correctly")
    finally:
        os.unlink(temp_file)


def test_validation_rejects_invalid_document():
    """Test that the validator reports problems on a malformed document."""
    print("Testing validation of invalid documents...")
    manager = DocumentManagerImpl()

    invalid = DocumentItem(
        document_id="",
        document_type=DocumentType.TXT,
        title="   ",
        content="",
    )
    doc_id = manager.register_document(invalid)

    is_valid, errors = manager.validate_document(doc_id)
    assert is_valid is False
    assert len(errors) == 2  # empty title and empty content

    print("[OK] Validation reports invalid documents correctly")


def run_all_tests():
    """Run all tests for the Document Intelligence Engine."""
    print("=" * 60)
    print("Running Document Intelligence Engine Tests")
    print("=" * 60)

    try:
        test_document_manager_initialization()
        test_text_document_loading()
        test_markdown_document_loading()
        test_csv_document_loading()
        test_json_document_loading()
        test_document_chunking()
        test_document_indexing_and_search()
        test_document_retrieval()
        test_document_summarization()
        test_document_validation()
        test_document_metadata_extraction()
        test_document_versioning()
        test_document_comparison()
        test_document_duplicate_detection()
        test_html_document_loading()
        test_question_answering()
        test_table_extraction()
        test_version_history()
        test_cache_expiration()
        test_chunking_respects_chunk_size()
        test_ooxml_image_extraction()
        test_validation_rejects_invalid_document()

        print("=" * 60)
        print("[PASS] All tests passed!")
        print("=" * 60)
        return True
    except Exception as e:
        print("=" * 60)
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)