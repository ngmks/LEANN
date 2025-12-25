"""Tests for leann list command performance improvements.

This module tests the limited-depth search functionality that prevents
leann list from scanning all files in large directories like $HOME.
See: https://github.com/yichuan-w/LEANN/issues/122
"""

import json
from pathlib import Path
from unittest.mock import patch


class TestLimitedDepthSearch:
    """Test the _find_meta_files_limited method for performance."""

    def test_find_meta_files_respects_max_depth(self, tmp_path: Path):
        """Meta files beyond max_depth should not be found."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create a deep directory structure
        # depth 0: tmp_path
        # depth 1: level1
        # depth 2: level2
        # depth 3: level3
        # depth 4: level4 (beyond default max_depth=3)
        level1 = tmp_path / "level1"
        level2 = level1 / "level2"
        level3 = level2 / "level3"
        level4 = level3 / "level4"

        level4.mkdir(parents=True)

        # Create meta files at different depths
        (tmp_path / "root.leann.meta.json").touch()
        (level1 / "l1.leann.meta.json").touch()
        (level2 / "l2.leann.meta.json").touch()
        (level3 / "l3.leann.meta.json").touch()
        (level4 / "l4.leann.meta.json").touch()

        # Find with max_depth=3 (should find root, l1, l2, l3 but not l4)
        found = list(cli._find_meta_files_limited(tmp_path, max_depth=3))
        found_names = {f.name for f in found}

        assert "root.leann.meta.json" in found_names
        assert "l1.leann.meta.json" in found_names
        assert "l2.leann.meta.json" in found_names
        assert "l3.leann.meta.json" in found_names
        assert "l4.leann.meta.json" not in found_names

    def test_find_meta_files_skips_node_modules(self, tmp_path: Path):
        """Meta files inside node_modules should be skipped."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create a meta file inside node_modules
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "pkg.leann.meta.json").touch()

        # Create a normal meta file
        (tmp_path / "normal.leann.meta.json").touch()

        found = list(cli._find_meta_files_limited(tmp_path, max_depth=3))
        found_names = {f.name for f in found}

        assert "normal.leann.meta.json" in found_names
        assert "pkg.leann.meta.json" not in found_names

    def test_find_meta_files_skips_hidden_dirs(self, tmp_path: Path):
        """Meta files inside hidden directories (except .leann) should be skipped."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create meta files in hidden directories
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "hidden.leann.meta.json").touch()

        # .leann should NOT be skipped
        leann_dir = tmp_path / ".leann"
        leann_dir.mkdir()
        (leann_dir / "leann.leann.meta.json").touch()

        # Normal file
        (tmp_path / "normal.leann.meta.json").touch()

        found = list(cli._find_meta_files_limited(tmp_path, max_depth=3))
        found_names = {f.name for f in found}

        assert "normal.leann.meta.json" in found_names
        assert "leann.leann.meta.json" in found_names
        assert "hidden.leann.meta.json" not in found_names

    def test_find_meta_files_skips_venv(self, tmp_path: Path):
        """Meta files inside .venv and venv should be skipped."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create meta files in virtual env directories
        for venv_name in [".venv", "venv", ".env", "env"]:
            venv_dir = tmp_path / venv_name
            venv_dir.mkdir()
            (venv_dir / f"{venv_name}.leann.meta.json").touch()

        # Normal file
        (tmp_path / "normal.leann.meta.json").touch()

        found = list(cli._find_meta_files_limited(tmp_path, max_depth=3))
        found_names = {f.name for f in found}

        assert "normal.leann.meta.json" in found_names
        assert ".venv.leann.meta.json" not in found_names
        assert "venv.leann.meta.json" not in found_names
        assert ".env.leann.meta.json" not in found_names
        assert "env.leann.meta.json" not in found_names

    def test_find_meta_files_skips_build_dirs(self, tmp_path: Path):
        """Meta files inside build/dist directories should be skipped."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create meta files in build directories
        for build_name in ["build", "dist", "__pycache__", ".cache"]:
            build_dir = tmp_path / build_name
            build_dir.mkdir()
            (build_dir / f"{build_name}.leann.meta.json").touch()

        # Normal file
        (tmp_path / "normal.leann.meta.json").touch()

        found = list(cli._find_meta_files_limited(tmp_path, max_depth=3))
        found_names = {f.name for f in found}

        assert "normal.leann.meta.json" in found_names
        assert "build.leann.meta.json" not in found_names
        assert "dist.leann.meta.json" not in found_names
        assert "__pycache__.leann.meta.json" not in found_names
        assert ".cache.leann.meta.json" not in found_names


class TestRegistryLimitedSearch:
    """Test the registry limited search functionality."""

    def test_has_app_indexes_limited_respects_depth(self, tmp_path: Path):
        """Should not find indexes beyond max_depth."""
        from leann.registry import _has_app_indexes_limited

        # Create a deep directory structure
        level4 = tmp_path / "l1" / "l2" / "l3" / "l4"
        level4.mkdir(parents=True)

        # Only create a file beyond depth 3
        (level4 / "deep.leann.meta.json").touch()

        # Should not find it with max_depth=3
        assert not _has_app_indexes_limited(tmp_path, max_depth=3)

        # Create one at depth 2
        (tmp_path / "l1" / "l2" / "shallow.leann.meta.json").touch()

        # Now should find it
        assert _has_app_indexes_limited(tmp_path, max_depth=3)

    def test_has_app_indexes_limited_skips_node_modules(self, tmp_path: Path):
        """Should skip node_modules directory."""
        from leann.registry import _has_app_indexes_limited

        # Create a meta file inside node_modules
        node_modules = tmp_path / "node_modules"
        node_modules.mkdir()
        (node_modules / "pkg.leann.meta.json").touch()

        # Should not find it
        assert not _has_app_indexes_limited(tmp_path, max_depth=3)

        # Create a normal meta file
        (tmp_path / "normal.leann.meta.json").touch()

        # Now should find it
        assert _has_app_indexes_limited(tmp_path, max_depth=3)


class TestDiscoverIndexesPerformance:
    """Test that _discover_indexes_in_project uses limited search."""

    def test_discover_indexes_skips_deep_directories(self, tmp_path: Path):
        """Should not scan directories beyond max_depth."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create a CLI format index (should always be found)
        cli_indexes = tmp_path / ".leann" / "indexes" / "my-index"
        cli_indexes.mkdir(parents=True)
        (cli_indexes / "documents.leann.meta.json").touch()

        # Create an app format index at depth 4 (should not be found)
        deep_dir = tmp_path / "a" / "b" / "c" / "d"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.leann.meta.json").touch()

        indexes = cli._discover_indexes_in_project(tmp_path)

        # Should find the CLI index
        assert any(idx["name"] == "my-index" for idx in indexes)

        # Should NOT find the deep app index
        assert not any(idx["name"] == "d" for idx in indexes)

    def test_discover_indexes_respects_custom_max_depth(self, tmp_path: Path):
        """Should find deeper indexes when max_depth is increased."""
        from leann.cli import LeannCLI

        cli = LeannCLI()

        # Create an app format index at depth 5
        deep_dir = tmp_path / "a" / "b" / "c" / "d" / "e"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep.leann.meta.json").touch()

        # With default max_depth=3, should NOT find it
        indexes_shallow = cli._discover_indexes_in_project(tmp_path, max_depth=3)
        assert not any(idx["name"] == "e" for idx in indexes_shallow)

        # With max_depth=5, should find it
        indexes_deep = cli._discover_indexes_in_project(tmp_path, max_depth=5)
        assert any(idx["name"] == "e" for idx in indexes_deep)


class TestMaxDepthCliOption:
    """Test the --max-depth CLI option for leann list."""

    def test_max_depth_argument_is_parsed(self):
        """The --max-depth argument should be properly parsed."""
        from leann.cli import LeannCLI

        cli = LeannCLI()
        parser = cli.create_parser()

        # Test default value
        args = parser.parse_args(["list"])
        assert args.max_depth == 3

        # Test custom value
        args = parser.parse_args(["list", "--max-depth", "5"])
        assert args.max_depth == 5

        # Test another custom value
        args = parser.parse_args(["list", "--max-depth", "10"])
        assert args.max_depth == 10


class TestGlobalIndexRegistry:
    """Test the global index registry for O(1) index discovery."""

    def test_register_and_list_index(self, tmp_path: Path):
        """Should register an index and list it from the registry."""
        from leann.registry import (
            GLOBAL_INDEX_REGISTRY_PATH,
            _load_index_registry,
            _save_index_registry,
            register_index,
            list_registered_indexes,
            unregister_index,
        )

        # Use a temporary registry file
        test_registry = tmp_path / "indexes.json"
        with patch("leann.registry.GLOBAL_INDEX_REGISTRY_PATH", test_registry):
            # Register an index
            index_path = tmp_path / ".leann" / "indexes" / "test-index" / "documents.leann"
            index_path.parent.mkdir(parents=True)
            index_path.touch()
            (index_path.parent / "documents.leann.meta.json").touch()

            result = register_index(
                name="test-index",
                path=str(index_path),
                index_type="cli",
            )
            assert result is True

            # List indexes
            indexes = list_registered_indexes(validate=True)
            assert len(indexes) == 1
            assert indexes[0]["name"] == "test-index"
            assert indexes[0]["index_type"] == "cli"

            # Unregister
            result = unregister_index(str(index_path))
            assert result is True

            # Should be empty now
            indexes = list_registered_indexes(validate=False)
            assert len(indexes) == 0

    def test_registry_validates_stale_entries(self, tmp_path: Path):
        """Should remove entries for indexes that no longer exist."""
        from leann.registry import (
            _save_index_registry,
            list_registered_indexes,
        )

        test_registry = tmp_path / "indexes.json"
        with patch("leann.registry.GLOBAL_INDEX_REGISTRY_PATH", test_registry):
            # Create a registry with a stale entry
            stale_entry = {
                "name": "stale-index",
                "path": str(tmp_path / "nonexistent" / "documents.leann"),
                "index_type": "cli",
                "created_at": "2024-01-01T00:00:00+00:00",
            }
            _save_index_registry([stale_entry])

            # List with validation should remove the stale entry
            indexes = list_registered_indexes(validate=True)
            assert len(indexes) == 0

    def test_register_index_updates_existing(self, tmp_path: Path):
        """Should update an existing entry instead of duplicating."""
        from leann.registry import (
            register_index,
            list_registered_indexes,
        )

        test_registry = tmp_path / "indexes.json"
        with patch("leann.registry.GLOBAL_INDEX_REGISTRY_PATH", test_registry):
            # Create the index files
            index_path = tmp_path / "test.leann"
            index_path.touch()
            (tmp_path / "test.leann.meta.json").touch()

            # Register twice with different names
            register_index(name="first-name", path=str(index_path), index_type="app")
            register_index(name="second-name", path=str(index_path), index_type="app")

            # Should only have one entry with the updated name
            indexes = list_registered_indexes(validate=True)
            assert len(indexes) == 1
            assert indexes[0]["name"] == "second-name"


class TestListIndexesWithRegistry:
    """Test that list_indexes uses the global registry when available."""

    def test_list_indexes_uses_registry_when_available(self, tmp_path: Path, capsys):
        """Should use O(1) registry lookup when indexes are registered."""
        from leann.cli import LeannCLI
        from leann.registry import register_index

        test_registry = tmp_path / "indexes.json"

        # Create an index
        index_dir = tmp_path / ".leann" / "indexes" / "my-index"
        index_dir.mkdir(parents=True)
        index_path = index_dir / "documents.leann"
        index_path.touch()
        (index_dir / "documents.leann.meta.json").touch()

        with patch("leann.registry.GLOBAL_INDEX_REGISTRY_PATH", test_registry):
            with patch("leann.cli.list_registered_indexes") as mock_list:
                # Mock the registry to return our index
                mock_list.return_value = [
                    {
                        "name": "my-index",
                        "path": str(index_path),
                        "index_type": "cli",
                        "created_at": "2024-01-01T00:00:00+00:00",
                    }
                ]

                cli = LeannCLI()
                cli.list_indexes()

                captured = capsys.readouterr()
                assert "O(1) lookup" in captured.out or "global registry" in captured.out.lower()
