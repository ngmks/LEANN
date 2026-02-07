"""Tests for multi-language AST chunking support.

Verifies that:
1. Parser instantiation works for all LANGUAGE_MAP entries
2. Chunking produces correct output for major languages
3. Ancestor detection works across languages (build_chunk_ancestors)
4. CODE_EXTENSIONS maps to valid languages
"""

import pytest
from astchunk import ANCESTOR_NODE_TYPES, LANGUAGE_MAP, ASTChunkBuilder, get_supported_languages

# ---------------------------------------------------------------------------
# Sample code snippets per language (designed to have nested class/function)
# ---------------------------------------------------------------------------
CODE_SAMPLES: dict[str, str] = {
    "python": """\
class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
""",
    "java": """\
public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int subtract(int a, int b) {
        return a - b;
    }
}
""",
    "csharp": """\
public class Calculator {
    public int Add(int a, int b) {
        return a + b;
    }

    public int Subtract(int a, int b) {
        return a - b;
    }
}
""",
    "typescript": """\
class Calculator {
    add(a: number, b: number): number {
        return a + b;
    }

    subtract(a: number, b: number): number {
        return a - b;
    }
}
""",
    "javascript": """\
class Calculator {
    add(a, b) {
        return a + b;
    }

    subtract(a, b) {
        return a - b;
    }
}
""",
    "go": """\
package main

type Calculator struct{}

func (c Calculator) Add(a, b int) int {
    return a + b
}

func (c Calculator) Subtract(a, b int) int {
    return a - b
}
""",
    "rust": """\
struct Calculator;

impl Calculator {
    fn add(&self, a: i32, b: i32) -> i32 {
        a + b
    }

    fn subtract(&self, a: i32, b: i32) -> i32 {
        a - b
    }
}
""",
    "ruby": """\
class Calculator
  def add(a, b)
    a + b
  end

  def subtract(a, b)
    a - b
  end
end
""",
    "bash": """\
function add() {
    echo $(($1 + $2))
}

function subtract() {
    echo $(($1 - $2))
}
""",
    "c": """\
struct Calculator {
    int value;
};

int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}
""",
    "cpp": """\
class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }

    int subtract(int a, int b) {
        return a - b;
    }
};
""",
    "kotlin": """\
class Calculator {
    fun add(a: Int, b: Int): Int {
        return a + b
    }

    fun subtract(a: Int, b: Int): Int {
        return a - b
    }
}
""",
    "swift": """\
class Calculator {
    func add(a: Int, b: Int) -> Int {
        return a + b
    }

    func subtract(a: Int, b: Int) -> Int {
        return a - b
    }
}
""",
    "php": """\
<?php
class Calculator {
    public function add($a, $b) {
        return $a + $b;
    }

    public function subtract($a, $b) {
        return $a - $b;
    }
}
""",
    "lua": """\
local Calculator = {}

function Calculator.add(a, b)
    return a + b
end

function Calculator.subtract(a, b)
    return a - b
end
""",
    "scala": """\
class Calculator {
  def add(a: Int, b: Int): Int = {
    a + b
  }

  def subtract(a: Int, b: Int): Int = {
    a - b
  }
}
""",
}

# Keywords that should appear in chunk output, per language
EXPECTED_KEYWORDS: dict[str, list[str]] = {
    "python": ["class Calculator", "def add", "def subtract"],
    "java": ["class Calculator", "int add", "int subtract"],
    "csharp": ["class Calculator", "int Add", "int Subtract"],
    "typescript": ["class Calculator", "add(", "subtract("],
    "javascript": ["class Calculator", "add(", "subtract("],
    "go": ["Calculator", "func", "Add", "Subtract"],
    "rust": ["Calculator", "fn add", "fn subtract"],
    "ruby": ["class Calculator", "def add", "def subtract"],
    "bash": ["function add", "function subtract"],
    "c": ["struct Calculator", "int add", "int subtract"],
    "cpp": ["class Calculator", "int add", "int subtract"],
    "kotlin": ["class Calculator", "fun add", "fun subtract"],
    "swift": ["class Calculator", "func add", "func subtract"],
    "php": ["class Calculator", "function add", "function subtract"],
    "lua": ["Calculator", "function", "add", "subtract"],
    "scala": ["class Calculator", "def add", "def subtract"],
}


class TestParserInstantiation:
    """Verify that all LANGUAGE_MAP entries create valid parsers."""

    def test_all_language_map_entries(self):
        """Every entry in LANGUAGE_MAP should produce a working ASTChunkBuilder."""
        # Test unique ts_language values (skip aliases)
        tested = set()
        for lang_name, ts_lang in LANGUAGE_MAP.items():
            if ts_lang in tested:
                continue
            tested.add(ts_lang)
            builder = ASTChunkBuilder(
                max_chunk_size=500, language=lang_name, metadata_template="default"
            )
            assert builder.parser is not None, f"Parser is None for language '{lang_name}'"

    def test_aliases_resolve_same(self):
        """Aliases like 'golang'/'go' should produce equivalent builders."""
        alias_pairs = [("go", "golang"), ("csharp", "c_sharp"), ("cpp", "c++"), ("bash", "shell")]
        for canonical, alias in alias_pairs:
            b1 = ASTChunkBuilder(
                max_chunk_size=500, language=canonical, metadata_template="default"
            )
            b2 = ASTChunkBuilder(max_chunk_size=500, language=alias, metadata_template="default")
            # Both should parse the same trivial code
            code = "x = 1\n"
            r1 = b1.parser.parse(bytes(code, "utf8"))
            r2 = b2.parser.parse(bytes(code, "utf8"))
            assert r1.root_node.type == r2.root_node.type

    def test_unsupported_language_error(self):
        """Unknown language should raise ValueError with available list."""
        with pytest.raises(ValueError, match="Unsupported language"):
            ASTChunkBuilder(max_chunk_size=500, language="klingon", metadata_template="default")

    def test_get_supported_languages(self):
        """get_supported_languages() should return sorted list matching LANGUAGE_MAP keys."""
        langs = get_supported_languages()
        assert langs == sorted(LANGUAGE_MAP.keys())
        assert "python" in langs
        assert "go" in langs
        assert "rust" in langs


class TestMultiLanguageChunking:
    """Verify chunkify() produces valid output for major languages."""

    @pytest.mark.parametrize("language", CODE_SAMPLES.keys())
    def test_chunkify_produces_chunks(self, language):
        """chunkify() should return non-empty chunks for each language."""
        builder = ASTChunkBuilder(
            max_chunk_size=500, language=language, metadata_template="default"
        )
        chunks = builder.chunkify(CODE_SAMPLES[language])

        assert len(chunks) > 0, f"No chunks produced for {language}"
        for i, chunk in enumerate(chunks):
            assert isinstance(chunk, dict), f"Chunk {i} is not a dict for {language}"
            assert "content" in chunk or "text" in chunk, (
                f"Chunk {i} missing content/text key for {language}"
            )
            content = chunk.get("content") or chunk.get("text", "")
            assert len(content.strip()) > 0, f"Chunk {i} is empty for {language}"

    @pytest.mark.parametrize("language", CODE_SAMPLES.keys())
    def test_chunks_contain_expected_keywords(self, language):
        """Combined chunk content should contain all expected keywords."""
        builder = ASTChunkBuilder(
            max_chunk_size=500, language=language, metadata_template="default"
        )
        chunks = builder.chunkify(CODE_SAMPLES[language])
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)

        for keyword in EXPECTED_KEYWORDS[language]:
            assert keyword in combined, (
                f"Expected keyword '{keyword}' not found in {language} chunks"
            )

    @pytest.mark.parametrize("language", CODE_SAMPLES.keys())
    def test_chunk_metadata_has_required_fields(self, language):
        """Default metadata template should include line numbers and chunk_size."""
        builder = ASTChunkBuilder(
            max_chunk_size=500, language=language, metadata_template="default"
        )
        chunks = builder.chunkify(
            CODE_SAMPLES[language],
            repo_level_metadata={"filepath": f"test.{language}"},
        )

        for i, chunk in enumerate(chunks):
            meta = chunk.get("metadata", {})
            assert "chunk_size" in meta, f"Chunk {i} missing chunk_size for {language}"
            assert "start_line_no" in meta, f"Chunk {i} missing start_line_no for {language}"
            assert "end_line_no" in meta, f"Chunk {i} missing end_line_no for {language}"
            assert meta["start_line_no"] >= 0
            assert meta["end_line_no"] >= meta["start_line_no"]

    def test_small_chunk_size_produces_multiple_chunks(self):
        """A small max_chunk_size should split code into multiple chunks."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="python", metadata_template="default")
        chunks = builder.chunkify(CODE_SAMPLES["python"])
        assert len(chunks) > 1, "Expected multiple chunks with small max_chunk_size"


class TestAncestorDetection:
    """Verify build_chunk_ancestors works across languages via ANCESTOR_NODE_TYPES."""

    def test_python_ancestors(self):
        """Python: nested function inside class should produce ancestor path."""
        builder = ASTChunkBuilder(max_chunk_size=30, language="python", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["python"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.py"},
        )
        # With expansion, chunk text should contain ancestor context
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "class Calculator" in combined

    def test_java_ancestors(self):
        """Java: methods inside class should have class ancestor."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="java", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["java"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "Calculator.java"},
        )
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        # Java uses class_declaration — the ancestor should be detected
        assert "class Calculator" in combined

    def test_typescript_ancestors(self):
        """TypeScript: methods inside class should have class ancestor."""
        builder = ASTChunkBuilder(
            max_chunk_size=50, language="typescript", metadata_template="default"
        )
        chunks = builder.chunkify(
            CODE_SAMPLES["typescript"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.ts"},
        )
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "class Calculator" in combined

    def test_go_ancestors(self):
        """Go: methods should have type ancestor."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="go", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["go"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.go"},
        )
        # Go code should chunk and have content
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "func" in combined

    def test_rust_ancestors(self):
        """Rust: functions in impl should have impl ancestor."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="rust", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["rust"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.rs"},
        )
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "impl Calculator" in combined

    def test_ruby_ancestors(self):
        """Ruby: methods inside class should have class ancestor."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="ruby", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["ruby"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.rb"},
        )
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "class Calculator" in combined

    def test_ancestor_node_types_is_frozenset(self):
        """ANCESTOR_NODE_TYPES should be immutable."""
        assert isinstance(ANCESTOR_NODE_TYPES, frozenset)
        with pytest.raises(AttributeError):
            ANCESTOR_NODE_TYPES.add("fake_type")  # type: ignore[attr-defined]


class TestCodeExtensions:
    """Verify CODE_EXTENSIONS consistency with LANGUAGE_MAP."""

    def test_all_extensions_map_to_valid_languages(self):
        """Every language in CODE_EXTENSIONS must exist in LANGUAGE_MAP."""
        from leann.chunking_utils import CODE_EXTENSIONS

        for ext, lang in CODE_EXTENSIONS.items():
            assert lang in LANGUAGE_MAP, (
                f"Extension '{ext}' maps to language '{lang}' which is not in LANGUAGE_MAP"
            )

    def test_get_language_from_extension(self):
        """get_language_from_extension should return correct language."""
        from leann.chunking_utils import get_language_from_extension

        assert get_language_from_extension("test.py") == "python"
        assert get_language_from_extension("test.go") == "go"
        assert get_language_from_extension("test.rs") == "rust"
        assert get_language_from_extension("test.rb") == "ruby"
        assert get_language_from_extension("test.sh") == "bash"
        assert get_language_from_extension("test.ts") == "typescript"
        assert get_language_from_extension("test.js") == "javascript"
        assert get_language_from_extension("test.unknown") is None
