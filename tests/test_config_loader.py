"""Tests for shared/config_loader.py."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared import config_loader


class TestEnvVarSubstitution:
    """Test environment variable substitution logic."""

    def test_simple_substitution(self):
        """Test basic ${VAR_NAME} substitution."""
        with patch.dict(os.environ, {"MY_VAR": "hello"}):
            result = config_loader._substitute_env_vars("${MY_VAR}")
            assert result == "hello"

    def test_substitution_in_string(self):
        """Test substitution within a larger string."""
        with patch.dict(os.environ, {"USER": "alice"}):
            result = config_loader._substitute_env_vars("Hello, ${USER}!")
            assert result == "Hello, alice!"

    def test_missing_var_keeps_literal(self):
        """Test that missing env vars keep the literal pattern."""
        with patch.dict(os.environ, {}, clear=True):
            result = config_loader._substitute_env_vars("${NONEXISTENT}")
            assert result == "${NONEXISTENT}"

    def test_multiple_vars(self):
        """Test multiple env vars in one string."""
        with patch.dict(os.environ, {"A": "foo", "B": "bar"}):
            result = config_loader._substitute_env_vars("${A}_${B}")
            assert result == "foo_bar"

    def test_default_value(self):
        """Test ${VAR:default} syntax."""
        with patch.dict(os.environ, {}, clear=True):
            result = config_loader._substitute_env_vars("${NONEXISTENT:default_val}")
            assert result == "default_val"

    def test_default_with_existing_var(self):
        """Test default is ignored when env var exists."""
        with patch.dict(os.environ, {"EXISTS": "real"}):
            result = config_loader._substitute_env_vars("${EXISTS:fallback}")
            assert result == "real"

    def test_non_string_passthrough(self):
        """Test that non-string values pass through unchanged."""
        result = config_loader._substitute_recursively(42)
        assert result == 42
        result = config_loader._substitute_recursively(True)
        assert result is True
        result = config_loader._substitute_recursively(None)
        assert result is None

    def test_nested_dict_substitution(self):
        """Test recursive substitution in nested dicts."""
        with patch.dict(os.environ, {"HOST": "localhost", "PORT": "5432"}):
            data = {
                "database": {
                    "host": "${HOST}",
                    "port": "${PORT}",
                    "name": "myapp",
                }
            }
            result = config_loader._substitute_recursively(data)
            assert result["database"]["host"] == "localhost"
            assert result["database"]["port"] == "5432"
            assert result["database"]["name"] == "myapp"

    def test_list_substitution(self):
        """Test recursive substitution in lists."""
        with patch.dict(os.environ, {"ITEM": "test"}):
            data = ["${ITEM}", "literal", "${NONEXISTENT}"]
            result = config_loader._substitute_recursively(data)
            assert result == ["test", "literal", "${NONEXISTENT}"]


class TestConfigLoader:
    """Test YAML config loading."""

    def test_load_nonexistent_file(self):
        """Test that loading a missing file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            config_loader.load_config("__nonexistent_config__")

    def test_load_empty_yaml(self, tmp_path):
        """Test loading an empty or comment-only YAML file."""
        # Point to a temp dir with empty YAML
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "empty.yaml"
        yaml_file.write_text("")

        with patch.object(config_loader, "_CONFIG_DIR", config_dir):
            result = config_loader.load_config("empty")
            assert result == {}

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid YAML config file."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "test_config.yaml"
        yaml_file.write_text("key: value\nnumber: 42\nlist:\n  - a\n  - b")

        with patch.object(config_loader, "_CONFIG_DIR", config_dir):
            result = config_loader.load_config("test_config")
            assert result == {"key": "value", "number": 42, "list": ["a", "b"]}

    def test_config_with_env_substitution(self, tmp_path):
        """Test that env vars are substituted in loaded config."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "env_config.yaml"
        yaml_file.write_text("host: ${TEST_HOST}\nport: ${TEST_PORT}")

        with patch.dict(os.environ, {"TEST_HOST": "localhost", "TEST_PORT": "8080"}):
            with patch.object(config_loader, "_CONFIG_DIR", config_dir):
                result = config_loader.load_config("env_config")
                assert result == {"host": "localhost", "port": "8080"}

    def test_caching_behaviour(self, tmp_path):
        """Test that config is cached after first load."""
        config_loader.clear_cache()
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "cached.yaml"
        yaml_file.write_text("value: original")

        with patch.object(config_loader, "_CONFIG_DIR", config_dir):
            # First load
            result1 = config_loader.load_config("cached")
            assert result1 == {"value": "original"}

            # Modify file behind the scenes
            yaml_file.write_text("value: modified")

            # Second load should still return cached version
            result2 = config_loader.load_config("cached")
            assert result2 == {"value": "original"}

    def test_bad_yaml_syntax(self, tmp_path):
        """Test that malformed YAML raises an error."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        yaml_file = config_dir / "bad.yaml"
        yaml_file.write_text("{{ invalid yaml ::: }")

        with patch.object(config_loader, "_CONFIG_DIR", config_dir):
            with pytest.raises(yaml.YAMLError):
                config_loader.load_config("bad")

    def test_shortcut_functions(self, tmp_path):
        """Test that shortcut functions call load_config correctly."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        for name in ["content_template", "platforms", "backup_trends"]:
            (config_dir / f"{name}.yaml").write_text(f"name: {name}")

        with patch.object(config_loader, "_CONFIG_DIR", config_dir):
            assert config_loader.get_content_template() == {"name": "content_template"}
            assert config_loader.get_platforms_config() == {"name": "platforms"}
            assert config_loader.get_backup_trends() == {"name": "backup_trends"}