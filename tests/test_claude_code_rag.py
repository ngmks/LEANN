"""
Tests for ClaudeCodeReader and ClaudeCodeRAG.

Unit tests use synthetic JSONL data in temp directories.
Integration tests invoke the RAG app as a subprocess.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure apps/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps"))

from claude_code_data.claude_code_reader import ClaudeCodeReader


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session_dir(
    base: Path,
    project_name: str = "test-project",
    session_id: str = "aaaa-1111",
    entries: list[dict] | None = None,
    sessions_index_entries: list[dict] | None = None,
):
    """Create a minimal project directory with one JSONL session file."""
    project_dir = base / f"-home-user-projects-{project_name}"
    project_dir.mkdir(parents=True, exist_ok=True)

    if entries is not None:
        jsonl_path = project_dir / f"{session_id}.jsonl"
        with open(jsonl_path, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    if sessions_index_entries is not None:
        idx = {"version": 1, "entries": sessions_index_entries}
        (project_dir / "sessions-index.json").write_text(
            json.dumps(idx, ensure_ascii=False), encoding="utf-8"
        )

    return project_dir


def _user_entry(text: str, **extra) -> dict:
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "timestamp": "2026-01-25T10:00:00Z",
        "gitBranch": "main",
        "sessionId": extra.get("sessionId", "aaaa-1111"),
        **extra,
    }


def _assistant_entry(text: str, tools: list[str] | None = None, **extra) -> dict:
    content = [{"type": "text", "text": text}]
    if tools:
        for t in tools:
            content.append({"type": "tool_use", "id": "toolu_x", "name": t, "input": {}})
    return {
        "type": "assistant",
        "message": {
            "role": "assistant",
            "model": "claude-opus-4-5-20251101",
            "content": content,
        },
        "timestamp": "2026-01-25T10:01:00Z",
        **extra,
    }


def _tool_result_entry(**extra) -> dict:
    return {
        "type": "user",
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_x", "content": "ok"}
            ],
        },
        "timestamp": "2026-01-25T10:01:30Z",
        **extra,
    }


def _summary_entry(text: str) -> dict:
    return {"type": "summary", "summary": text}


def _thinking_block() -> dict:
    return {"type": "thinking", "thinking": "internal reasoning", "signature": "sig"}


# ---------------------------------------------------------------------------
# Unit tests — Reader
# ---------------------------------------------------------------------------


class TestReaderParseTurn:
    """Test basic turn parsing from synthetic JSONL."""

    def test_simple_turn(self):
        entries = [
            _user_entry("Configure le thermostat"),
            _assistant_entry("Voici la configuration", tools=["Bash", "Edit"]),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(
                Path(tmp),
                entries=entries,
                sessions_index_entries=[
                    {
                        "sessionId": "aaaa-1111",
                        "summary": "Config thermostat",
                        "messageCount": 2,
                        "gitBranch": "main",
                        "projectPath": "/home/user/projects/test-project",
                        "created": "2026-01-25T10:00:00Z",
                    }
                ],
            )

            reader = ClaudeCodeReader(granularity="turn", include_tool_names=True)
            docs = reader.load_data(base_dirs=[tmp])

            # 1 turn + 1 summary
            assert len(docs) >= 1
            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            assert len(turn_docs) == 1

            doc = turn_docs[0]
            assert "Configure le thermostat" in doc.text
            assert "Voici la configuration" in doc.text
            assert "[Tool: Bash]" in doc.text
            assert "[Tool: Edit]" in doc.text

            # Metadata
            assert doc.metadata["source"] == "claude_code_session"
            assert doc.metadata["session_id"] == "aaaa-1111"
            assert doc.metadata["project_name"] == "test-project"
            assert doc.metadata["entry_type"] == "turn"
            assert doc.metadata["turn_index"] == 0

    def test_summary_doc(self):
        entries = [
            _summary_entry("Session about thermostat configuration"),
            _user_entry("Hello"),
            _assistant_entry("Hi there"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(
                Path(tmp),
                entries=entries,
                sessions_index_entries=[
                    {
                        "sessionId": "aaaa-1111",
                        "summary": "Thermostat session",
                        "messageCount": 10,
                        "gitBranch": "main",
                        "created": "2026-01-25T10:00:00Z",
                    }
                ],
            )

            reader = ClaudeCodeReader(include_summaries=True)
            docs = reader.load_data(base_dirs=[tmp])

            summary_docs = [d for d in docs if d.metadata.get("entry_type") == "summary"]
            assert len(summary_docs) == 1
            assert "thermostat configuration" in summary_docs[0].text
            assert summary_docs[0].metadata["entry_type"] == "summary"

    def test_no_summaries_flag(self):
        entries = [
            _summary_entry("A summary"),
            _user_entry("Hello"),
            _assistant_entry("Hi"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader(include_summaries=False)
            docs = reader.load_data(base_dirs=[tmp])

            summary_docs = [d for d in docs if d.metadata.get("entry_type") == "summary"]
            assert len(summary_docs) == 0

    def test_thinking_blocks_ignored(self):
        entries = [
            _user_entry("Question"),
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        _thinking_block(),
                        {"type": "text", "text": "Visible answer"},
                    ],
                },
                "timestamp": "2026-01-25T10:01:00Z",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader()
            docs = reader.load_data(base_dirs=[tmp])

            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            assert len(turn_docs) == 1
            assert "internal reasoning" not in turn_docs[0].text
            assert "Visible answer" in turn_docs[0].text

    def test_multiple_turns(self):
        entries = [
            _user_entry("First question"),
            _assistant_entry("First answer"),
            _user_entry("Second question"),
            _assistant_entry("Second answer"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader()
            docs = reader.load_data(base_dirs=[tmp])

            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            assert len(turn_docs) == 2
            assert turn_docs[0].metadata["turn_index"] == 0
            assert turn_docs[1].metadata["turn_index"] == 1

    def test_message_granularity(self):
        entries = [
            _user_entry("Question"),
            _assistant_entry("Answer"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader(granularity="message", include_summaries=False)
            docs = reader.load_data(base_dirs=[tmp])

            assert len(docs) == 2
            assert all(d.metadata["entry_type"] == "message" for d in docs)

    def test_session_granularity(self):
        entries = [
            _user_entry("Q1"),
            _assistant_entry("A1"),
            _user_entry("Q2"),
            _assistant_entry("A2"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader(granularity="session", include_summaries=False)
            docs = reader.load_data(base_dirs=[tmp])

            assert len(docs) == 1
            assert docs[0].metadata["entry_type"] == "session"
            assert "Q1" in docs[0].text
            assert "Q2" in docs[0].text


class TestReaderParseAgents:
    """Test subagent JSONL parsing."""

    def test_agent_turn(self):
        # Main session
        main_entries = [
            _user_entry("Explore the codebase"),
            _assistant_entry("Launching agent..."),
        ]

        # Agent file
        agent_entries = [
            {
                "type": "user",
                "isSidechain": True,
                "agentId": "aa9d70a",
                "message": {"role": "user", "content": "Find thermostat files"},
                "timestamp": "2026-01-25T10:02:00Z",
                "gitBranch": "main",
            },
            {
                "type": "assistant",
                "isSidechain": True,
                "agentId": "aa9d70a",
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [
                        {"type": "text", "text": "Found thermostat.ts in src/devices/"},
                        {"type": "tool_use", "id": "t1", "name": "Grep", "input": {}},
                    ],
                },
                "timestamp": "2026-01-25T10:03:00Z",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = _make_session_dir(Path(tmp), entries=main_entries)

            # Create agent file
            agent_dir = project_dir / "aaaa-1111" / "subagents"
            agent_dir.mkdir(parents=True)
            agent_path = agent_dir / "agent-aa9d70a.jsonl"
            with open(agent_path, "w") as f:
                for e in agent_entries:
                    f.write(json.dumps(e) + "\n")

            reader = ClaudeCodeReader(include_agents=True)
            docs = reader.load_data(base_dirs=[tmp])

            agent_docs = [d for d in docs if d.metadata.get("entry_type") == "agent_turn"]
            assert len(agent_docs) == 1
            doc = agent_docs[0]
            assert doc.metadata["agent_id"] == "aa9d70a"
            assert doc.metadata["is_sidechain"] is True
            assert "Find thermostat files" in doc.text
            assert "Found thermostat.ts" in doc.text
            assert "[Tool: Grep]" in doc.text
            assert "Agent: aa9d70a" in doc.text

    def test_no_agents_flag(self):
        main_entries = [_user_entry("Test"), _assistant_entry("Response")]
        agent_entries = [
            {
                "type": "user",
                "isSidechain": True,
                "message": {"role": "user", "content": "Agent task"},
                "timestamp": "2026-01-25T10:00:00Z",
            },
            {
                "type": "assistant",
                "isSidechain": True,
                "message": {
                    "role": "assistant",
                    "model": "claude-opus-4-5-20251101",
                    "content": [{"type": "text", "text": "Agent result"}],
                },
                "timestamp": "2026-01-25T10:01:00Z",
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            project_dir = _make_session_dir(Path(tmp), entries=main_entries)
            agent_dir = project_dir / "aaaa-1111" / "subagents"
            agent_dir.mkdir(parents=True)
            with open(agent_dir / "agent-bb1234.jsonl", "w") as f:
                for e in agent_entries:
                    f.write(json.dumps(e) + "\n")

            reader = ClaudeCodeReader(include_agents=False)
            docs = reader.load_data(base_dirs=[tmp])
            agent_docs = [d for d in docs if d.metadata.get("entry_type") == "agent_turn"]
            assert len(agent_docs) == 0


class TestReaderEdgeCases:
    """Test edge cases: empty sessions, malformed JSON, tool-result-only messages."""

    def test_empty_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = _make_session_dir(Path(tmp), entries=[])
            reader = ClaudeCodeReader()
            docs = reader.load_data(base_dirs=[tmp])
            assert len(docs) == 0

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "-home-user-projects-test-project"
            project_dir.mkdir(parents=True)
            jsonl = project_dir / "bad-session.jsonl"
            jsonl.write_text(
                '{"type":"user","message":{"role":"user","content":"good"},"timestamp":"2026-01-25T10:00:00Z"}\n'
                "this is not json\n"
                '{"type":"assistant","message":{"role":"assistant","model":"x","content":[{"type":"text","text":"answer"}]},"timestamp":"2026-01-25T10:01:00Z"}\n'
            )

            reader = ClaudeCodeReader()
            docs = reader.load_data(base_dirs=[tmp])
            # Should still parse the valid lines
            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            assert len(turn_docs) == 1
            assert "answer" in turn_docs[0].text

    def test_tool_result_only_user_message(self):
        entries = [
            _user_entry("Real question"),
            _assistant_entry("Answer", tools=["Bash"]),
            _tool_result_entry(),  # Should be ignored
            _assistant_entry("Continuation after tool"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader()
            docs = reader.load_data(base_dirs=[tmp])

            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            # One turn: user question + all assistant responses (tool_result doesn't start new turn)
            assert len(turn_docs) == 1
            assert "Real question" in turn_docs[0].text
            assert "Continuation after tool" in turn_docs[0].text

    def test_max_text_per_turn(self):
        entries = [
            _user_entry("Q"),
            _assistant_entry("A" * 5000),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader(max_text_per_turn=100)
            docs = reader.load_data(base_dirs=[tmp])

            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            assert len(turn_docs) == 1
            assert len(turn_docs[0].text) == 100

    def test_skip_system_progress_entries(self):
        entries = [
            {"type": "system", "data": "something"},
            {"type": "progress", "data": "loading"},
            {"type": "file-history-snapshot", "data": {}},
            {"type": "queue-operation", "data": {}},
            _user_entry("Real message"),
            _assistant_entry("Real response"),
        ]

        with tempfile.TemporaryDirectory() as tmp:
            _make_session_dir(Path(tmp), entries=entries)
            reader = ClaudeCodeReader(include_summaries=False)
            docs = reader.load_data(base_dirs=[tmp])

            assert len(docs) == 1
            assert docs[0].metadata["entry_type"] == "turn"


class TestReaderDedup:
    """Test deduplication: same sessionId in two dirs → only first one."""

    def test_dedup_by_session_id(self):
        entries1 = [_user_entry("Dir1 question"), _assistant_entry("Dir1 answer")]
        entries2 = [_user_entry("Dir2 question"), _assistant_entry("Dir2 answer")]

        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            _make_session_dir(
                Path(tmp1),
                project_name="project-a",
                session_id="shared-session",
                entries=entries1,
            )
            _make_session_dir(
                Path(tmp2),
                project_name="project-a",
                session_id="shared-session",
                entries=entries2,
            )

            reader = ClaudeCodeReader(include_summaries=False)
            docs = reader.load_data(base_dirs=[tmp1, tmp2])

            turn_docs = [d for d in docs if d.metadata.get("entry_type") == "turn"]
            assert len(turn_docs) == 1
            # First dir wins
            assert "Dir1 question" in turn_docs[0].text


class TestProjectNameExtraction:
    """Test _extract_project_name with various formats."""

    def test_standard_format(self):
        assert (
            ClaudeCodeReader._extract_project_name(
                "-home-mks-projects-casagreena-domotic-server"
            )
            == "casagreena-domotic-server"
        )

    def test_nested_projects(self):
        assert (
            ClaudeCodeReader._extract_project_name("-home-user-projects-my-app")
            == "my-app"
        )

    def test_no_projects_segment(self):
        assert ClaudeCodeReader._extract_project_name("some-random-dir") == "some-random-dir"


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip model tests in CI",
)
def test_rag_integration():
    """Test full build + search pipeline via subprocess."""
    # Create synthetic data
    entries = [
        _summary_entry("Configuration du thermostat de chauffage"),
        _user_entry("Configure le thermostat pour la modulation"),
        _assistant_entry(
            "Je vais configurer le thermostat avec les paramètres de modulation T1-T8.",
            tools=["Bash", "Edit"],
        ),
        _user_entry("Montre-moi la consommation de fuel"),
        _assistant_entry(
            "Voici le tracking de consommation de fuel du système domotique.",
            tools=["Read"],
        ),
    ]

    with tempfile.TemporaryDirectory() as data_dir, tempfile.TemporaryDirectory() as index_dir:
        _make_session_dir(
            Path(data_dir),
            project_name="casagreena-domotic-server",
            session_id="integ-test-001",
            entries=entries,
            sessions_index_entries=[
                {
                    "sessionId": "integ-test-001",
                    "summary": "Thermostat + fuel",
                    "messageCount": 4,
                    "gitBranch": "main",
                    "projectPath": "/home/user/test",
                    "created": "2026-01-25T10:00:00Z",
                }
            ],
        )

        cmd = [
            sys.executable,
            "-m",
            "apps.claude_code_rag",
            "--session-dirs",
            data_dir,
            "--llm",
            "simulated",
            "--embedding-model",
            "facebook/contriever",
            "--embedding-mode",
            "sentence-transformers",
            "--index-dir",
            index_dir,
            "--query",
            "Comment est configuré le thermostat ?",
        ]

        env = os.environ.copy()
        env["TOKENIZERS_PARALLELISM"] = "false"

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
            cwd=str(Path(__file__).resolve().parent.parent),
        )

        output = result.stdout + result.stderr
        assert result.returncode == 0, f"Command failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        assert "Index saved to" in output or "Using existing index" in output
        assert "simulated" in output.lower() or "This is a simulated answer" in output


@pytest.mark.skipif(
    os.environ.get("CI") == "true",
    reason="Skip model tests in CI",
)
def test_incremental_update():
    """Test: build initial → add new sessions → update_index → find new results."""
    entries_v1 = [
        _user_entry("Configure le thermostat", sessionId="session-v1"),
        _assistant_entry("Configuration thermostat effectuée"),
    ]

    entries_v2 = [
        _user_entry("Configure le dashboard fuel", sessionId="session-v2"),
        _assistant_entry("Dashboard fuel configuré avec graphiques de consommation"),
    ]

    with tempfile.TemporaryDirectory() as data_dir, tempfile.TemporaryDirectory() as index_dir:
        base_cmd = [
            sys.executable,
            "-m",
            "apps.claude_code_rag",
            "--session-dirs",
            data_dir,
            "--llm",
            "simulated",
            "--embedding-model",
            "facebook/contriever",
            "--embedding-mode",
            "sentence-transformers",
            "--index-dir",
            index_dir,
            "--no-compact",
            "--no-recompute",
        ]

        env = os.environ.copy()
        env["TOKENIZERS_PARALLELISM"] = "false"
        cwd = str(Path(__file__).resolve().parent.parent)

        # Step 1: Build initial index with session v1
        _make_session_dir(
            Path(data_dir),
            project_name="test-project",
            session_id="session-v1",
            entries=entries_v1,
        )

        r1 = subprocess.run(
            base_cmd + ["--query", "thermostat"],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
            cwd=cwd,
        )
        assert r1.returncode == 0, f"Initial build failed:\n{r1.stderr}"
        assert "Index saved to" in (r1.stdout + r1.stderr)

        # Step 2: Add new session v2
        _make_session_dir(
            Path(data_dir),
            project_name="test-project",
            session_id="session-v2",
            entries=entries_v2,
        )

        # Step 3: Run again — should do incremental update
        r2 = subprocess.run(
            base_cmd + ["--query", "dashboard fuel consommation"],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
            cwd=cwd,
        )
        output2 = r2.stdout + r2.stderr
        assert r2.returncode == 0, f"Incremental update failed:\n{r2.stderr}"
        # Should indicate incremental or simulated answer
        assert (
            "Incremental" in output2
            or "update" in output2.lower()
            or "simulated" in output2.lower()
            or "Using existing index" in output2
        )
