"""Tests for the config module."""

import pytest
from pathlib import Path
from code_translator.config import Config


class TestConfig:
    """Test Config class."""

    def test_default_config(self):
        """Test default configuration values."""
        config = Config()

        assert config.model == "qwen2.5:1.5b"
        assert config.source_lang == "Chinese"
        assert config.target_lang == "English"
        assert config.temperature == 0.3
        assert config.translate_all is False
        assert config.dry_run is False
        assert config.max_workers == 4
        assert config.recursive is True

    def test_custom_config(self):
        """Test creating config with custom values."""
        config = Config(
            model="test:1b",
            source_lang="Japanese",
            translate_all=True,
            max_workers=8,
        )

        assert config.model == "test:1b"
        assert config.source_lang == "Japanese"
        assert config.translate_all is True
        assert config.max_workers == 8

    def test_skip_dirs_default(self):
        """Test default skip directories."""
        config = Config()

        assert ".git" in config.skip_dirs
        assert "__pycache__" in config.skip_dirs
        assert "node_modules" in config.skip_dirs
        assert "venv" in config.skip_dirs

    def test_skip_extensions_default(self):
        """Test default skip extensions."""
        config = Config()

        assert ".pyc" in config.skip_extensions
        assert ".jpg" in config.skip_extensions
        assert ".exe" in config.skip_extensions

    def test_from_file(self, sample_config_toml):
        """Test loading config from TOML file."""
        config = Config.from_file(sample_config_toml)

        assert config.model == "test-model:1b"
        assert config.source_lang == "Japanese"
        assert config.target_lang == "English"
        assert config.temperature == 0.5
        assert config.translate_all is True
        assert config.max_workers == 8

    def test_from_file_nonexistent(self, temp_dir):
        """Test loading from nonexistent file returns defaults."""
        nonexistent = temp_dir / "does-not-exist.toml"
        config = Config.from_file(nonexistent)

        # Should return default config
        assert config.model == "qwen2.5:1.5b"

    def test_from_file_invalid_toml(self, temp_dir):
        """Test handling of invalid TOML file."""
        invalid_toml = temp_dir / "invalid.toml"
        invalid_toml.write_text("this is not valid toml [[[")

        with pytest.raises(Exception):
            Config.from_file(invalid_toml)

    def test_merge_with_args(self):
        """Test merging config with command-line arguments."""
        config = Config(model="default:1b", source_lang="Chinese")

        merged = config.merge_with_args(
            model="override:2b",
            translate_all=True,
            workers=8,
        )

        # Should prefer CLI args
        assert merged.model == "override:2b"
        assert merged.translate_all is True
        assert merged.max_workers == 8
        # Should keep original for non-overridden
        assert merged.source_lang == "Chinese"

    def test_merge_with_args_none_values(self):
        """Test that None values in args don't override config."""
        config = Config(model="default:1b", max_workers=4)

        merged = config.merge_with_args(
            model=None,
            workers=None,
        )

        # Should keep original values when args are None
        assert merged.model == "default:1b"
        assert merged.max_workers == 4

    def test_find_config_in_current_dir(self, temp_dir, monkeypatch):
        """Test finding config in current directory."""
        config_file = temp_dir / ".code-translator.toml"
        config_file.write_text("""[translation]
model = "found:1b"
""")

        # Change to temp dir
        monkeypatch.chdir(temp_dir)

        config = Config.find_config()
        assert config.model == "found:1b"

    def test_find_config_not_found(self, temp_dir):
        """Test that find_config returns defaults when not found."""
        # Search in empty temp dir
        config = Config.find_config(temp_dir)

        # Should return default config
        assert config.model == "qwen2.5:1.5b"

    def test_find_config_in_parent_dir(self, temp_dir):
        """Test finding config in parent directory."""
        # Create config in temp_dir
        config_file = temp_dir / ".code-translator.toml"
        config_file.write_text("""[translation]
model = "parent:1b"
""")

        # Create subdirectory
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        # Search from subdirectory
        config = Config.find_config(subdir)
        assert config.model == "parent:1b"

    def test_config_file_sections(self, temp_dir):
        """Test loading config with all sections."""
        config_file = temp_dir / ".code-translator.toml"
        config_file.write_text("""[translation]
model = "test:1b"
source_lang = "Korean"
target_lang = "Spanish"

[processing]
translate_all = true
max_workers = 16

[filters]
skip_dirs = ["custom_dir"]

[git]
auto_create_branch = true
branch_prefix = "i18n/"
""")

        config = Config.from_file(config_file)

        assert config.model == "test:1b"
        assert config.source_lang == "Korean"
        assert config.target_lang == "Spanish"
        assert config.translate_all is True
        assert config.max_workers == 16
