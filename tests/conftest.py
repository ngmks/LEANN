"""Shared test fixtures and helpers for DiskANN availability detection."""

from pathlib import Path

import pytest


def diskann_importable() -> bool:
    """Check whether the DiskANN backend Python package is installed."""
    try:
        import leann_backend_diskann  # noqa: F401

        return True
    except ImportError:
        return False


def diskann_partitioner_available() -> bool:
    """Check whether the DiskANN graph partitioner C++ executable is compiled.

    The partitioner is a separate C++ binary that must be built manually via
    ``third_party/DiskANN/graph_partition/build.sh``.  It is required only for
    tests that use ``is_recompute=True`` (graph partitioning mode).
    """
    if not diskann_importable():
        return False
    import leann_backend_diskann

    module_dir = Path(leann_backend_diskann.__file__).parent
    partitioner = (
        module_dir.parent
        / "third_party"
        / "DiskANN"
        / "graph_partition"
        / "build"
        / "release"
        / "graph_partition"
        / "partitioner"
    )
    return partitioner.exists()


requires_diskann = pytest.mark.skipif(
    not diskann_importable(),
    reason="DiskANN backend not installed",
)

# DiskANN's C++ StaticDiskFloatIndex crashes with SIGABRT when a LeannSearcher
# is created after cleanup() on a previous one (disk-index lifecycle bug).
# The crash is in pybind11 batch_search and cannot be caught by Python.
# Apply this marker to tests that use the cleanup → re-creation sequence.
skip_diskann_search = pytest.mark.skip(
    reason="DiskANN SIGABRT on searcher cleanup + re-creation sequence (upstream C++ bug)",
)

requires_diskann_partitioner = pytest.mark.skipif(
    not diskann_partitioner_available(),
    reason="DiskANN graph partitioner executable not compiled (run third_party/DiskANN/graph_partition/build.sh)",
)
