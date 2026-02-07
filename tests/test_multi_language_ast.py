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
    "zig": """\
const Calculator = struct {
    fn add(a: i32, b: i32) i32 {
        return a + b;
    }

    fn subtract(a: i32, b: i32) i32 {
        return a - b;
    }
};
""",
    "nim": """\
type Calculator = object

proc add(a, b: int): int =
  return a + b

proc subtract(a, b: int): int =
  return a - b
""",
    "perl": """\
package Calculator;

sub add {
    my ($a, $b) = @_;
    return $a + $b;
}

sub subtract {
    my ($a, $b) = @_;
    return $a - $b;
}
""",
    "r": """\
Calculator <- list(
  add = function(a, b) {
    return(a + b)
  },

  subtract = function(a, b) {
    return(a - b)
  }
)
""",
    "julia": """\
struct Calculator end

function add(c::Calculator, a, b)
    return a + b
end

function subtract(c::Calculator, a, b)
    return a - b
end
""",
    "dart": """\
class Calculator {
  int add(int a, int b) {
    return a + b;
  }

  int subtract(int a, int b) {
    return a - b;
  }
}
""",
    "elixir": """\
defmodule Calculator do
  def add(a, b) do
    a + b
  end

  def subtract(a, b) do
    a - b
  end
end
""",
    "erlang": """\
-module(calculator).
-export([add/2, subtract/2]).

add(A, B) ->
    A + B.

subtract(A, B) ->
    A - B.
""",
    "haskell": """\
module Calculator where

add :: Int -> Int -> Int
add a b = a + b

subtract :: Int -> Int -> Int
subtract a b = a - b
""",
    "ocaml": """\
let add a b = a + b

let subtract a b = a - b
""",
    "clojure": """\
(ns calculator)

(defn add [a b]
  (+ a b))

(defn subtract [a b]
  (- a b))
""",
    "html": """\
<!DOCTYPE html>
<html>
<head>
    <title>Calculator</title>
</head>
<body>
    <div class="calculator">
        <input type="text" id="result">
    </div>
</body>
</html>
""",
    "css": """\
.calculator {
    display: flex;
    flex-direction: column;
    padding: 20px;
}

.calculator input {
    font-size: 16px;
    margin: 5px 0;
}
""",
    "vue": """\
<template>
  <div class="calculator">
    <input v-model="result" />
  </div>
</template>

<script>
export default {
  data() {
    return {
      result: 0
    }
  }
}
</script>
""",
    "svelte": """\
<script>
  let result = 0;

  function add(a, b) {
    return a + b;
  }
</script>

<div class="calculator">
  <input bind:value={result} />
</div>
""",
    "sql": """\
CREATE TABLE calculator (
    id INT PRIMARY KEY,
    value INT
);

SELECT a + b AS result
FROM numbers;
""",
    "json": """\
{
    "name": "leann",
    "version": "1.0",
    "dependencies": {
        "numpy": ">=1.0",
        "faiss": ">=1.7"
    }
}
""",
    "yaml": """\
name: leann
version: "1.0"
dependencies:
  numpy: ">=1.0"
  faiss: ">=1.7"
""",
    "toml": """\
[project]
name = "leann"
version = "1.0"

[project.dependencies]
numpy = ">=1.0"
faiss = ">=1.7"
""",
    "xml": """\
<project>
  <name>leann</name>
  <version>1.0</version>
  <dependencies>
    <dep name="numpy">1.0</dep>
    <dep name="faiss">1.7</dep>
  </dependencies>
</project>
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
    "zig": ["Calculator", "fn add", "fn subtract"],
    "nim": ["Calculator", "proc add", "proc subtract"],
    "perl": ["Calculator", "sub add", "sub subtract"],
    "r": ["Calculator", "function", "add", "subtract"],
    "julia": ["Calculator", "function add", "function subtract"],
    "dart": ["class Calculator", "int add", "int subtract"],
    "elixir": ["Calculator", "def add", "def subtract"],
    "erlang": ["calculator", "add", "subtract"],
    "haskell": ["Calculator", "add", "subtract"],
    "ocaml": ["let add", "let subtract"],
    "clojure": ["defn add", "defn subtract"],
    "html": ["<html>", "<div", "calculator"],
    "css": [".calculator", "display", "padding"],
    "vue": ["<template>", "calculator"],
    "svelte": ["<script>", "function add"],
    "sql": ["CREATE TABLE", "calculator"],
    "json": ["leann", "dependencies", "numpy"],
    "yaml": ["leann", "dependencies", "numpy"],
    "toml": ["project", "leann", "dependencies"],
    "xml": ["<project>", "leann", "numpy"],
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
        alias_pairs = [
            ("go", "golang"),
            ("csharp", "c_sharp"),
            ("cpp", "c++"),
            ("bash", "shell"),
            ("typescript", "tsx"),
            ("javascript", "jsx"),
        ]
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

    def test_c_ancestors(self):
        """C: functions and structs should have struct_specifier ancestor."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="c", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["c"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.c"},
        )
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "struct Calculator" in combined

    def test_cpp_ancestors(self):
        """C++: methods inside class should have class_specifier ancestor."""
        builder = ASTChunkBuilder(max_chunk_size=50, language="cpp", metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES["cpp"],
            chunk_expansion=True,
            repo_level_metadata={"filepath": "calc.cpp"},
        )
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "class Calculator" in combined

    @pytest.mark.parametrize(
        "language",
        ["javascript", "csharp", "kotlin", "swift", "php", "scala", "bash", "lua"],
    )
    def test_expansion_produces_chunks(self, language):
        """chunk_expansion=True should produce non-empty chunks for each language."""
        builder = ASTChunkBuilder(max_chunk_size=50, language=language, metadata_template="default")
        chunks = builder.chunkify(
            CODE_SAMPLES[language],
            chunk_expansion=True,
            repo_level_metadata={"filepath": f"test.{language}"},
        )
        assert len(chunks) > 0, f"No chunks with expansion for {language}"
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert len(combined.strip()) > 0, f"Empty expanded chunks for {language}"

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
        assert get_language_from_extension("test.nim") == "nim"
        assert get_language_from_extension("test.erl") == "erlang"
        assert get_language_from_extension("test.ml") == "ocaml"
        assert get_language_from_extension("test.clj") == "clojure"
        assert get_language_from_extension("test.html") == "html"
        assert get_language_from_extension("test.css") == "css"
        assert get_language_from_extension("test.vue") == "vue"
        assert get_language_from_extension("test.svelte") == "svelte"
        assert get_language_from_extension("config.json") == "json"
        assert get_language_from_extension("config.yaml") == "yaml"
        assert get_language_from_extension("config.yml") == "yaml"
        assert get_language_from_extension("config.toml") == "toml"
        assert get_language_from_extension("config.xml") == "xml"
        assert get_language_from_extension("test.unknown") is None


class TestMalformedCodeResilience:
    """Verify ASTChunkBuilder handles malformed/poorly formatted code without crashing."""

    def test_empty_code(self):
        """Empty string should produce chunks without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        chunks = builder.chunkify("")
        assert isinstance(chunks, list)

    def test_whitespace_only(self):
        """Whitespace-only code should produce chunks without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        chunks = builder.chunkify("   \n\n\t\t\n   ")
        assert isinstance(chunks, list)

    def test_syntax_error_python(self):
        """Python with syntax errors should chunk without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        code = """\
class BrokenClass(
    def nested_function():
        return 42
"""
        chunks = builder.chunkify(code)
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "return 42" in combined

    def test_syntax_error_javascript(self):
        """JavaScript with missing braces should chunk without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="javascript", metadata_template="default")
        code = """\
function add(a, b) {
    return a + b;

function subtract(a, b) {
    return a - b;
}
"""
        chunks = builder.chunkify(code)
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "return" in combined

    def test_syntax_error_java(self):
        """Java with unclosed class should chunk without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="java", metadata_template="default")
        code = """\
public class Broken {
    public int add(int a, int b) {
        return a + b;
    }
"""
        chunks = builder.chunkify(code)
        assert len(chunks) > 0

    @pytest.mark.parametrize(
        "language,code",
        [
            ("python", "def foo("),
            ("java", "class Foo {"),
            ("rust", "fn main() {"),
            ("go", "func main() {"),
            ("typescript", "class Foo {"),
            ("c", "int main() {"),
        ],
    )
    def test_incomplete_statements(self, language, code):
        """Incomplete statements should chunk without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language=language, metadata_template="default")
        chunks = builder.chunkify(code)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_minified_javascript(self):
        """Minified JS (valid but ugly) should chunk correctly."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="javascript", metadata_template="default")
        code = 'class C{add(a,b){return a+b}subtract(a,b){return a-b}}'
        chunks = builder.chunkify(code)
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "return" in combined

    def test_no_indentation_python(self):
        """Python with broken indentation (syntax error) should not crash."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        code = """\
class Calculator:
def add(self, a, b):
return a + b
"""
        chunks = builder.chunkify(code)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_mixed_valid_invalid_code(self):
        """File with some valid and some broken code should chunk the valid parts."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        code = """\
def valid_function():
    return 42

class @@@ broken

def another_valid():
    return 99
"""
        chunks = builder.chunkify(code)
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "return 42" in combined
        assert "return 99" in combined

    def test_syntax_error_with_expansion(self):
        """Syntax errors with chunk_expansion=True should not crash."""
        builder = ASTChunkBuilder(max_chunk_size=30, language="python", metadata_template="default")
        code = """\
class Broken(:
    def method(self):
        return 1
"""
        chunks = builder.chunkify(
            code,
            chunk_expansion=True,
            repo_level_metadata={"filepath": "broken.py"},
        )
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_syntax_error_metadata_intact(self):
        """Metadata fields should be present even for malformed code."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        code = "def incomplete("
        chunks = builder.chunkify(code, repo_level_metadata={"filepath": "bad.py"})
        assert len(chunks) > 0
        for chunk in chunks:
            meta = chunk.get("metadata", {})
            assert "chunk_size" in meta
            assert "start_line_no" in meta
            assert "end_line_no" in meta

    def test_garbage_input(self):
        """Random non-code characters should not crash the chunker."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        chunks = builder.chunkify("@#$%^&*()!~`|\\")
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_unicode_identifiers(self):
        """Code with unicode identifiers should chunk correctly."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        code = """\
class Calculatrice:
    def ajouter(self, a, b):
        return a + b

    def soustraire(self, a, b):
        return a - b
"""
        chunks = builder.chunkify(code)
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "Calculatrice" in combined
        assert "ajouter" in combined

    def test_mixed_tabs_and_spaces(self):
        """Code with mixed tabs and spaces should chunk without crashing."""
        builder = ASTChunkBuilder(max_chunk_size=500, language="python", metadata_template="default")
        code = "class Foo:\n\tdef bar(self):\n\t    return 1\n"
        chunks = builder.chunkify(code)
        assert len(chunks) > 0
        combined = " ".join(chunk.get("content", chunk.get("text", "")) for chunk in chunks)
        assert "return 1" in combined
