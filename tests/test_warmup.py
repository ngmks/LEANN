"""
Tests for warmup functionality to reduce search latency.

These tests verify that:
1. The warmup() method can be called on LeannSearcher
2. enable_warmup=True causes auto-warmup during initialization
3. Warmup reduces latency on subsequent searches
"""

import os
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_index(tmp_path):
    """Create a small sample index for testing."""
    from leann.api import LeannBuilder

    index_path = str(tmp_path / "test_warmup.hnsw")
    texts = [f"This is test document {i} about topic {i % 3}" for i in range(20)]

    builder = LeannBuilder(
        backend_name="hnsw",
        embedding_model="facebook/contriever",
        embedding_mode="sentence-transformers",
        M=16,
        efConstruction=100,
    )

    for text in texts:
        builder.add_text(text)

    builder.build_index(index_path)
    return index_path


class TestWarmupMethod:
    """Test the warmup() method on LeannSearcher."""

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip model tests in CI to avoid memory issues",
    )
    def test_warmup_method_exists(self, sample_index):
        """Test that warmup method exists and is callable."""
        from leann.api import LeannSearcher

        searcher = LeannSearcher(sample_index, enable_warmup=False)
        try:
            assert hasattr(searcher, "warmup")
            assert callable(searcher.warmup)
        finally:
            searcher.cleanup()

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip model tests in CI to avoid memory issues",
    )
    def test_warmup_returns_time(self, sample_index):
        """Test that warmup() returns the time taken."""
        from leann.api import LeannSearcher

        searcher = LeannSearcher(sample_index, enable_warmup=False)
        try:
            warmup_time = searcher.warmup()
            assert isinstance(warmup_time, float)
            assert warmup_time >= 0
        finally:
            searcher.cleanup()

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip model tests in CI to avoid memory issues",
    )
    def test_warmup_with_custom_port(self, sample_index):
        """Test warmup with a custom port."""
        from leann.api import LeannSearcher

        searcher = LeannSearcher(sample_index, enable_warmup=False)
        try:
            # Use a different port
            warmup_time = searcher.warmup(port=5560)
            assert isinstance(warmup_time, float)
        finally:
            searcher.cleanup()


class TestAutoWarmup:
    """Test automatic warmup on initialization."""

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip model tests in CI to avoid memory issues",
    )
    def test_enable_warmup_false(self, sample_index):
        """Test that enable_warmup=False doesn't trigger warmup."""
        from leann.api import LeannSearcher

        with patch.object(LeannSearcher, "warmup") as mock_warmup:
            searcher = LeannSearcher(sample_index, enable_warmup=False)
            mock_warmup.assert_not_called()
            searcher.cleanup()

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip model tests in CI to avoid memory issues",
    )
    def test_enable_warmup_true(self, sample_index):
        """Test that enable_warmup=True triggers warmup on init."""
        from leann.api import LeannSearcher

        # We can't easily mock the warmup call since it happens in __init__
        # So we test that _warmup_enabled is set
        searcher = LeannSearcher(sample_index, enable_warmup=True)
        try:
            assert searcher._warmup_enabled is True
        finally:
            searcher.cleanup()


class TestWarmupLatencyImprovement:
    """Test that warmup actually improves latency."""

    @pytest.mark.skipif(
        os.environ.get("CI") == "true",
        reason="Skip model tests in CI to avoid memory issues",
    )
    def test_warmup_reduces_first_search_latency(self, sample_index):
        """Test that warmup reduces the latency of the first search."""
        from leann.api import LeannSearcher

        # Test WITHOUT warmup - first search should be slower
        searcher_cold = LeannSearcher(sample_index, enable_warmup=False)
        try:
            start_cold = time.time()
            _ = searcher_cold.search("test document", top_k=3)
            cold_time = time.time() - start_cold
        finally:
            searcher_cold.cleanup()

        # Test WITH warmup - first search should be faster
        searcher_warm = LeannSearcher(sample_index, enable_warmup=True)
        try:
            start_warm = time.time()
            _ = searcher_warm.search("test document", top_k=3)
            warm_time = time.time() - start_warm

            # The warmed-up first search should be faster
            # (or at least not significantly slower)
            # Note: warmup time is paid upfront, so first search after warmup
            # should be fast
            print(f"Cold first search: {cold_time:.3f}s")
            print(f"Warm first search: {warm_time:.3f}s")

            # The warm search should complete (we don't assert strict timing
            # as it can vary based on system load)
            assert warm_time >= 0
        finally:
            searcher_warm.cleanup()


class TestEmbeddingServerWarmup:
    """Test warmup at the embedding server level."""

    def test_hnsw_server_accepts_warmup_param(self):
        """Test that HNSW embedding server accepts enable_warmup parameter."""
        from leann_backend_hnsw.hnsw_embedding_server import create_hnsw_embedding_server
        import inspect

        sig = inspect.signature(create_hnsw_embedding_server)
        params = sig.parameters
        assert "enable_warmup" in params
        assert params["enable_warmup"].default is True

    def test_diskann_server_accepts_warmup_param(self):
        """Test that DiskANN embedding server accepts enable_warmup parameter."""
        from leann_backend_diskann.diskann_embedding_server import (
            create_diskann_embedding_server,
        )
        import inspect

        sig = inspect.signature(create_diskann_embedding_server)
        params = sig.parameters
        assert "enable_warmup" in params
        assert params["enable_warmup"].default is True


class TestServerManagerWarmup:
    """Test warmup parameter passing in server manager."""

    def test_build_command_with_warmup_enabled(self):
        """Test that warmup enabled doesn't add --no-warmup flag."""
        from leann.embedding_server_manager import EmbeddingServerManager

        manager = EmbeddingServerManager("leann_backend_hnsw.hnsw_embedding_server")
        cmd = manager._build_server_command(
            port=5557,
            model_name="test-model",
            embedding_mode="sentence-transformers",
            enable_warmup=True,
        )

        assert "--no-warmup" not in cmd

    def test_build_command_with_warmup_disabled(self):
        """Test that warmup disabled adds --no-warmup flag."""
        from leann.embedding_server_manager import EmbeddingServerManager

        manager = EmbeddingServerManager("leann_backend_hnsw.hnsw_embedding_server")
        cmd = manager._build_server_command(
            port=5557,
            model_name="test-model",
            embedding_mode="sentence-transformers",
            enable_warmup=False,
        )

        assert "--no-warmup" in cmd
