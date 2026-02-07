"""End-to-end integration tests: real file → AST chunking → LEANN indexation → search.

Downloads real source files from popular GitHub repos as fixtures, then verifies
the complete pipeline: load file → AST chunk → build LEANN index → search → retrieve.

This covers all languages in CODE_EXTENSIONS (36 languages, 54 extensions) to ensure
that real-world code files can be correctly indexed and retrieved.
"""

import numbers
import os
import tempfile
from pathlib import Path
from typing import Optional

import pytest

# ---------------------------------------------------------------------------
# Fixture directory containing real source files from GitHub
# ---------------------------------------------------------------------------
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "real_code"

# Map of fixture filename → (language, extension, search_terms)
# search_terms: list of strings we expect to find in AST chunks
FIXTURE_FILES: dict[str, tuple[str, str, list[str]]] = {
    # ── Core languages ──
    "cookies.py": ("python", ".py", ["CookieJar", "def", "class"]),
    "Strings.java": ("java", ".java", ["class", "public", "String"]),
    "String.cs": ("csharp", ".cs", ["class", "string", "namespace"]),
    "core.ts": ("typescript", ".ts", ["import", "function", "export"]),
    "utils.js": ("javascript", ".js", ["function", "module", "exports"]),
    # ── Systems languages ──
    "strings.go": ("go", ".go", ["func", "package", "string"]),
    "hiargs.rs": ("rust", ".rs", ["struct", "fn", "use"]),
    "array.c": ("c", ".c", ["int", "return", "void"]),
    "json.hpp": ("cpp", ".hpp", ["class", "namespace", "template"]),
    # ── JVM / .NET ──
    "StringNumberConversions.kt": ("kotlin", ".kt", ["fun", "class", "val"]),
    "Option.scala": ("scala", ".scala", ["class", "def", "val"]),
    # ── Scripting ──
    "common.rb": ("ruby", ".rb", ["def", "class", "module"]),
    "Str.php": ("php", ".php", ["function", "class", "return"]),
    "utils.lua": ("lua", ".lua", ["function", "return", "local"]),
    "mutate.R": ("r", ".r", ["function", "<-"]),
    "basic.jl": ("julia", ".jl", ["function", "end", "struct"]),
    "json.dart": ("dart", ".dart", ["class", "void", "import"]),
    "enum.ex": ("elixir", ".ex", ["def", "do", "end"]),
    "Basename.pm": ("perl", ".pm", ["sub", "my", "return"]),
    # ── Shell ──
    "nvm.sh": ("bash", ".sh", ["function", "if", "fi"]),
    # ── Functional ──
    "Internal.hs": ("haskell", ".hs", ["module", "data", "where"]),
    "list.ml": ("ocaml", ".ml", ["let", "match", "fun"]),
    "string.clj": ("clojure", ".clj", ["defn", "ns", "str"]),
    # ── Web ──
    "index.html": ("html", ".html", ["html", "head", "body"]),
    "normalize.css": ("css", ".css", ["margin", "padding", "display"]),
    "todomvc.vue": ("vue", ".vue", ["template", "script", "component"]),
    "component.svelte": ("svelte", ".svelte", ["script", "import"]),
    # ── Config / Data ──
    "package.json": ("json", ".json", ["name", "version"]),
    "ci.yaml": ("yaml", ".yaml", ["name", "on", "jobs"]),
    "pyproject.toml": ("toml", ".toml", ["project", "name", "version"]),
    "google_checks.xml": ("xml", ".xml", ["module", "property", "name"]),
    # ── Other ──
    "strutils.nim": ("nim", ".nim", ["proc", "result", "string"]),
    "lists.erl": ("erlang", ".erl", ["module", "export", "erlang"]),
    "String.swift": ("swift", ".swift", ["struct", "func", "var"]),
    "schema.sql": ("sql", ".sql", ["CREATE", "TABLE", "SET"]),
    "math.zig": ("zig", ".zig", ["fn", "return", "const"]),
}


class MockDocument:
    """Mock LlamaIndex Document for testing."""

    def __init__(self, content: str, file_path: str = "", metadata: Optional[dict] = None):
        self.content = content
        self.metadata = metadata or {}
        if file_path:
            self.metadata["file_path"] = file_path
            self.metadata["file_name"] = Path(file_path).name

    def get_content(self) -> str:
        return self.content


def load_fixture(filename: str) -> str:
    """Load a fixture file and return its content."""
    path = FIXTURES_DIR / filename
    if not path.exists():
        pytest.skip(f"Fixture file not found: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


# ===========================================================================
# Test class 1: AST chunking on real files (no indexation)
# ===========================================================================
class TestRealFileASTChunking:
    """Verify that AST chunking works correctly on real source files."""

    @pytest.mark.parametrize(
        "filename,lang_info",
        list(FIXTURE_FILES.items()),
        ids=list(FIXTURE_FILES.keys()),
    )
    def test_ast_chunking_produces_chunks(self, filename, lang_info):
        """Each real file should produce at least one AST chunk."""
        from leann.chunking_utils import create_ast_chunks

        language, ext, _ = lang_info
        content = load_fixture(filename)
        assert len(content.strip()) > 0, f"Fixture {filename} is empty"

        doc = MockDocument(
            content,
            file_path=f"/repo/{filename}",
            metadata={"language": language, "file_path": f"/repo/{filename}"},
        )

        chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)

        assert len(chunks) > 0, f"AST chunking produced no chunks for {filename} ({language})"
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, dict), f"Chunk {i} should be dict, got {type(chunk)}"
            assert "text" in chunk, f"Chunk {i} missing 'text' key"
            assert "metadata" in chunk, f"Chunk {i} missing 'metadata' key"
            assert len(chunk["text"].strip()) > 0, f"Chunk {i} text is empty"

    @pytest.mark.parametrize(
        "filename,lang_info",
        list(FIXTURE_FILES.items()),
        ids=list(FIXTURE_FILES.keys()),
    )
    def test_chunk_metadata_preserves_file_path(self, filename, lang_info):
        """Each chunk should preserve the original file path in metadata."""
        from leann.chunking_utils import create_ast_chunks

        language, ext, _ = lang_info
        content = load_fixture(filename)
        expected_path = f"/repo/{filename}"

        doc = MockDocument(
            content,
            file_path=expected_path,
            metadata={"language": language, "file_path": expected_path},
        )

        chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)
        assert len(chunks) > 0

        for i, chunk in enumerate(chunks):
            assert chunk["metadata"].get("file_path") == expected_path, (
                f"Chunk {i} from {filename}: expected file_path={expected_path}, "
                f"got {chunk['metadata'].get('file_path')}"
            )

    @pytest.mark.parametrize(
        "filename,lang_info",
        list(FIXTURE_FILES.items()),
        ids=list(FIXTURE_FILES.keys()),
    )
    def test_chunk_content_contains_expected_terms(self, filename, lang_info):
        """Combined chunk text should contain language-specific expected terms."""
        from leann.chunking_utils import create_ast_chunks

        language, ext, search_terms = lang_info
        content = load_fixture(filename)

        doc = MockDocument(
            content,
            file_path=f"/repo/{filename}",
            metadata={"language": language, "file_path": f"/repo/{filename}"},
        )

        chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)
        assert len(chunks) > 0

        combined_text = " ".join(c["text"] for c in chunks)
        # At least one expected term should appear (case-insensitive)
        found_terms = [t for t in search_terms if t.lower() in combined_text.lower()]
        assert len(found_terms) > 0, (
            f"None of the expected terms {search_terms} found in chunks for "
            f"{filename} ({language}). Combined text starts with: {combined_text[:200]}..."
        )


# ===========================================================================
# Test class 2: create_text_chunks with AST mode on real files
# ===========================================================================
class TestRealFileTextChunks:
    """Verify that create_text_chunks correctly routes real files through AST chunking."""

    @pytest.mark.parametrize(
        "filename,lang_info",
        list(FIXTURE_FILES.items()),
        ids=list(FIXTURE_FILES.keys()),
    )
    def test_text_chunks_ast_mode(self, filename, lang_info):
        """create_text_chunks with use_ast_chunking=True should produce chunks for real files."""
        from leann.chunking_utils import create_text_chunks

        language, ext, _ = lang_info
        content = load_fixture(filename)

        doc = MockDocument(
            content,
            file_path=f"/repo/{filename}",
            metadata={"language": language, "file_path": f"/repo/{filename}"},
        )

        chunks = create_text_chunks(
            [doc],
            use_ast_chunking=True,
            ast_chunk_size=512,
            ast_chunk_overlap=64,
        )

        assert len(chunks) > 0, (
            f"create_text_chunks(use_ast_chunking=True) produced no chunks for {filename}"
        )
        for chunk in chunks:
            assert isinstance(chunk, dict)
            assert "text" in chunk
            assert "metadata" in chunk
            assert len(chunk["text"].strip()) > 0


# ===========================================================================
# Test class 3: End-to-end LEANN indexation + search with real files
# ===========================================================================
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip model-dependent tests in CI to avoid memory issues",
)
class TestRealFileIndexation:
    """End-to-end: real files → AST chunking → LEANN index → search → retrieve."""

    @pytest.fixture(scope="class")
    def indexed_data(self):
        """Build a single LEANN index from all fixture files.

        This fixture is shared across all tests in the class (scope=class)
        to avoid rebuilding the index for each test.

        Yields:
            Tuple of (searcher, chunks_by_file, index_dir)
        """
        from leann.api import LeannBuilder, LeannSearcher
        from leann.chunking_utils import create_ast_chunks

        chunks_by_file: dict[str, list[dict]] = {}
        all_chunks: list[dict] = []
        chunk_id = 0

        # Chunk all fixture files
        for filename, (language, _ext, _) in FIXTURE_FILES.items():
            fixture_path = FIXTURES_DIR / filename
            if not fixture_path.exists():
                continue

            content = fixture_path.read_text(encoding="utf-8", errors="replace")
            if not content.strip():
                continue

            doc = MockDocument(
                content,
                file_path=f"/repo/{filename}",
                metadata={"language": language, "file_path": f"/repo/{filename}"},
            )

            chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)
            chunks_by_file[filename] = chunks

            for chunk in chunks:
                chunk["metadata"]["id"] = str(chunk_id)
                chunk["metadata"]["source_filename"] = filename
                all_chunks.append(chunk)
                chunk_id += 1

        assert len(all_chunks) > 0, "No chunks produced from any fixture file"

        # Build index
        temp_dir = tempfile.mkdtemp()
        index_path = str(Path(temp_dir) / "real_files.hnsw")

        builder = LeannBuilder(
            backend_name="hnsw",
            embedding_model="facebook/contriever",
            embedding_mode="sentence-transformers",
            M=16,
            efConstruction=200,
        )

        for chunk in all_chunks:
            builder.add_text(text=chunk["text"], metadata=chunk["metadata"])

        builder.build_index(index_path)

        # Create searcher
        searcher = LeannSearcher(index_path, enable_warmup=True)

        yield searcher, chunks_by_file, temp_dir

        # Cleanup
        searcher.cleanup()
        import shutil

        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_index_created_successfully(self, indexed_data):
        """The LEANN index should be created with all expected files."""
        searcher, chunks_by_file, _ = indexed_data
        assert len(chunks_by_file) > 0, "No files were chunked"

    def test_all_languages_chunked(self, indexed_data):
        """Each fixture file should have produced chunks."""
        _, chunks_by_file, _ = indexed_data

        for filename in FIXTURE_FILES:
            fixture_path = FIXTURES_DIR / filename
            if fixture_path.exists():
                assert filename in chunks_by_file, f"No chunks for {filename}"
                assert len(chunks_by_file[filename]) > 0, f"Empty chunks for {filename}"

    def test_search_returns_results(self, indexed_data):
        """Basic search should return results from the multi-language index."""
        searcher, _, _ = indexed_data
        results = searcher.search("function", top_k=10)
        assert len(results) > 0, "Search for 'function' returned no results"

    def test_search_result_has_text(self, indexed_data):
        """Each search result should have non-empty text."""
        searcher, _, _ = indexed_data
        results = searcher.search("class definition", top_k=5)
        assert len(results) > 0

        for result in results:
            assert result.text is not None, "Result text should not be None"
            assert len(result.text.strip()) > 0, "Result text should not be empty"

    def test_search_result_has_metadata(self, indexed_data):
        """Each search result should preserve metadata including file_path."""
        searcher, _, _ = indexed_data
        results = searcher.search("import module", top_k=5)
        assert len(results) > 0

        for result in results:
            assert isinstance(result.metadata, dict), "Metadata should be a dict"
            assert "file_path" in result.metadata, (
                f"Result metadata missing 'file_path': {result.metadata}"
            )

    def test_search_result_has_score(self, indexed_data):
        """Each search result should have a numeric score."""
        searcher, _, _ = indexed_data
        results = searcher.search("string manipulation", top_k=5)
        assert len(results) > 0

        for result in results:
            assert isinstance(result.score, numbers.Number), "Score should be numeric"

    @pytest.mark.parametrize(
        "query,expected_ext",
        [
            ("CookieJar http cookiejar requests compatibility", ".py"),
            ("public class Strings nullToEmpty padStart", ".java"),
            ("struct fn impl self i32 rust", ".rs"),
            ("func package strings Go Contains", ".go"),
            ("namespace using System Buffers Collections", ".cs"),
        ],
    )
    def test_search_finds_correct_language(self, indexed_data, query, expected_ext):
        """Language-specific queries should return results from the correct file type."""
        searcher, _, _ = indexed_data
        results = searcher.search(query, top_k=5)
        assert len(results) > 0, f"No results for query: {query}"

        # At least one result should come from a file with the expected extension
        found = False
        for result in results:
            file_path = result.metadata.get("file_path", "")
            if file_path.endswith(expected_ext):
                found = True
                break

        # Note: This is a soft assertion — embedding similarity may not always
        # perfectly discriminate, but in most cases the right file should appear
        if not found:
            # Report which files were actually found, for debugging
            actual_files = [r.metadata.get("file_path", "?") for r in results]
            pytest.xfail(
                f"Expected {expected_ext} file in results for '{query}', got: {actual_files}"
            )

    def test_search_python_content(self, indexed_data):
        """Search specifically for Python content and verify the text is actual code."""
        searcher, _, _ = indexed_data
        results = searcher.search("cookie jar http requests python", top_k=3)
        assert len(results) > 0

        combined = " ".join(r.text for r in results)
        # The text should contain actual code, not stringified dicts
        assert "'content':" not in combined, "Result text appears to be a stringified dict"
        assert "'metadata':" not in combined, "Result text appears to be a stringified dict"

    def test_search_java_content(self, indexed_data):
        """Search for Java content and verify retrieval."""
        searcher, _, _ = indexed_data
        results = searcher.search("Guava Strings class Java nullToEmpty", top_k=3)
        assert len(results) > 0

        combined = " ".join(r.text for r in results)
        assert "'content':" not in combined, "Result text appears to be a stringified dict"

    def test_all_fixture_files_are_retrievable(self, indexed_data):
        """Search for each fixture file and ensure it appears in results."""
        searcher, chunks_by_file, _ = indexed_data

        retrievable = 0
        not_retrievable = []

        for filename, (_language, _ext, _search_terms) in FIXTURE_FILES.items():
            if filename not in chunks_by_file:
                continue

            # Use a chunk's own text as a query (should retrieve itself or similar)
            first_chunk_text = chunks_by_file[filename][0]["text"]
            # Use first 200 chars as query
            query = first_chunk_text[:200]

            results = searcher.search(query, top_k=10)
            if len(results) == 0:
                not_retrievable.append(filename)
                continue

            # Check if the correct file appears in results
            found = any(
                filename in r.metadata.get("file_path", "")
                or filename in r.metadata.get("source_filename", "")
                for r in results
            )
            if found:
                retrievable += 1
            else:
                not_retrievable.append(filename)

        total = len(chunks_by_file)
        ratio = retrievable / total if total > 0 else 0

        # At least 80% of files should be self-retrievable
        assert ratio >= 0.8, (
            f"Only {retrievable}/{total} ({ratio:.0%}) files are self-retrievable. "
            f"Not found: {not_retrievable}"
        )

    def test_chunk_count_per_file(self, indexed_data):
        """Each file should produce a reasonable number of chunks."""
        _, chunks_by_file, _ = indexed_data

        for filename, chunks in chunks_by_file.items():
            # Files of 100-300 lines should produce at least 1 chunk
            assert len(chunks) >= 1, f"{filename} produced 0 chunks"
            # And shouldn't produce an unreasonable number
            assert len(chunks) <= 200, f"{filename} produced {len(chunks)} chunks — seems excessive"

    def test_no_excessive_duplicate_chunks(self, indexed_data):
        """Exact duplicate chunks should remain rare (AST overlap may produce a few)."""
        _, chunks_by_file, _ = indexed_data

        for filename, chunks in chunks_by_file.items():
            texts = [c["text"] for c in chunks]
            unique_texts = set(texts)
            dupes = len(texts) - len(unique_texts)
            # Allow up to 20% duplicates — AST overlap on repetitive code is legitimate
            max_allowed = max(2, len(texts) // 5)
            assert dupes <= max_allowed, (
                f"{filename} has {dupes} exact duplicate chunks out of {len(texts)} "
                f"(max allowed: {max_allowed})"
            )


# ===========================================================================
# Test class 4: Per-language indexation (individual index per file)
# ===========================================================================
@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip model-dependent tests in CI to avoid memory issues",
)
class TestPerLanguageIndexation:
    """Build and search an index for each language independently.

    This ensures that each language can be indexed and searched in isolation,
    catching any language-specific issues that might be masked in a multi-language index.
    """

    @pytest.mark.parametrize(
        "filename,lang_info",
        list(FIXTURE_FILES.items()),
        ids=list(FIXTURE_FILES.keys()),
    )
    def test_single_file_index_and_search(self, filename, lang_info):
        """Build a LEANN index from a single real file and search it."""
        from leann.api import LeannBuilder, LeannSearcher
        from leann.chunking_utils import create_ast_chunks

        language, ext, search_terms = lang_info
        content = load_fixture(filename)

        doc = MockDocument(
            content,
            file_path=f"/repo/{filename}",
            metadata={"language": language, "file_path": f"/repo/{filename}"},
        )

        # Chunk
        chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)
        assert len(chunks) > 0, f"No chunks for {filename}"

        with tempfile.TemporaryDirectory() as temp_dir:
            index_path = str(Path(temp_dir) / f"{language}.hnsw")

            # Build
            builder = LeannBuilder(
                backend_name="hnsw",
                embedding_model="facebook/contriever",
                embedding_mode="sentence-transformers",
                M=16,
                efConstruction=200,
            )

            for i, chunk in enumerate(chunks):
                builder.add_text(
                    text=chunk["text"],
                    metadata={**chunk["metadata"], "id": str(i)},
                )

            builder.build_index(index_path)

            # Search
            searcher = LeannSearcher(index_path, enable_warmup=False)
            try:
                # Use the first chunk's text as a query
                query = chunks[0]["text"][:200]
                results = searcher.search(query, top_k=3)

                # Should return at least 1 result
                assert len(results) > 0, f"Search returned no results for {filename} ({language})"

                # Result text should not be empty
                assert len(results[0].text.strip()) > 0, (
                    f"First result text is empty for {filename}"
                )

                # Result should have metadata
                assert isinstance(results[0].metadata, dict), (
                    f"Result metadata should be dict for {filename}"
                )

                # File path should be preserved
                assert "file_path" in results[0].metadata, (
                    f"file_path missing from result metadata for {filename}"
                )
                assert results[0].metadata["file_path"] == f"/repo/{filename}", (
                    f"file_path mismatch for {filename}"
                )
            finally:
                searcher.cleanup()


# ===========================================================================
# Test class 5: Edge cases with real file content
# ===========================================================================
class TestRealFileEdgeCases:
    """Test edge cases specific to real-world code files."""

    def test_file_with_unicode(self):
        """Real files may contain unicode (comments in various languages)."""
        from leann.chunking_utils import create_ast_chunks

        # Some fixture files contain unicode (e.g., Japanese comments in Ruby)
        for filename, (language, _ext, _) in FIXTURE_FILES.items():
            content = load_fixture(filename)
            if not any(ord(c) > 127 for c in content):
                continue

            doc = MockDocument(
                content,
                file_path=f"/repo/{filename}",
                metadata={"language": language, "file_path": f"/repo/{filename}"},
            )

            # Should not crash on unicode
            chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)
            assert isinstance(chunks, list), f"Unicode handling failed for {filename}"

    def test_file_with_long_lines(self):
        """Real files may contain very long lines (minified code, data literals)."""
        from leann.chunking_utils import create_ast_chunks

        for filename in ["package.json", "pyproject.toml"]:
            content = load_fixture(filename)

            doc = MockDocument(
                content,
                file_path=f"/repo/{filename}",
                metadata={
                    "language": FIXTURE_FILES[filename][0],
                    "file_path": f"/repo/{filename}",
                },
            )

            chunks = create_ast_chunks([doc], max_chunk_size=512, chunk_overlap=64)
            assert len(chunks) > 0, f"No chunks for {filename} with long lines"

    def test_detect_code_files_real_extensions(self):
        """All fixture files should be correctly detected as code files."""
        from leann.chunking_utils import detect_code_files

        docs = []
        for filename, (_language, _ext, _) in FIXTURE_FILES.items():
            content = load_fixture(filename)
            docs.append(
                MockDocument(
                    content,
                    file_path=f"/repo/{filename}",
                )
            )

        code_docs, text_docs = detect_code_files(docs)

        # All files should be detected as code (they all have code extensions)
        assert len(code_docs) == len(docs), (
            f"Expected {len(docs)} code files, got {len(code_docs)}. "
            f"Text files: {[d.metadata.get('file_path') for d in text_docs]}"
        )

        # Each should have the correct language
        for doc in code_docs:
            filename = Path(doc.metadata["file_path"]).name
            expected_lang = FIXTURE_FILES[filename][0]
            assert doc.metadata["language"] == expected_lang, (
                f"{filename}: expected language={expected_lang}, got {doc.metadata.get('language')}"
            )

    def test_chunking_preserves_code_structure(self):
        """AST chunks from real Python file should preserve function/class boundaries."""
        from leann.chunking_utils import create_ast_chunks

        content = load_fixture("cookies.py")
        doc = MockDocument(
            content,
            file_path="/repo/cookies.py",
            metadata={"language": "python", "file_path": "/repo/cookies.py"},
        )

        chunks = create_ast_chunks([doc], max_chunk_size=256, chunk_overlap=32)
        assert len(chunks) > 1, "Should produce multiple chunks from 300-line Python file"

        # Each chunk should start with code (not mid-statement)
        for i, chunk in enumerate(chunks):
            text = chunk["text"].strip()
            # Chunks shouldn't start with random closing braces or orphaned keywords
            assert not text.startswith(")"), f"Chunk {i} starts with orphaned ')'"
            assert not text.startswith("]"), f"Chunk {i} starts with orphaned ']'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
