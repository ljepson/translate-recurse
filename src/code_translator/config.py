"""Configuration management."""

import tomllib  # Python 3.11+ standard library
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Configuration for code-translator."""

    # Translation settings
    model: str = "qwen2.5:1.5b"
    source_lang: str = "Chinese"
    target_lang: str = "English"
    temperature: float = 0.3

    # Processing settings
    translate_all: bool = False
    dry_run: bool = False
    max_workers: int = 4
    recursive: bool = True

    # File filters
    skip_dirs: list[str] = field(default_factory=lambda: [
        '.git', '.svn', '.hg', '__pycache__', 'node_modules',
        'venv', '.venv', 'dist', 'build', 'target'
    ])
    skip_extensions: list[str] = field(default_factory=lambda: [
        '.pyc', '.pyo', '.so', '.dll', '.exe', '.bin',
        '.jpg', '.jpeg', '.png', '.gif', '.svg',
        '.mp3', '.mp4', '.zip', '.tar', '.gz'
    ])
    file_patterns: Optional[list[str]] = None

    # Git settings
    auto_create_branch: bool = False
    branch_prefix: str = "translation/"

    @classmethod
    def from_file(cls, config_path: Path) -> 'Config':
        """Load configuration from TOML file."""
        if not config_path.exists():
            return cls()

        with open(config_path, 'rb') as f:
            data = tomllib.load(f)

        # Extract relevant sections
        config_dict = {}

        if 'translation' in data:
            config_dict.update(data['translation'])

        if 'processing' in data:
            config_dict.update(data['processing'])

        if 'filters' in data:
            config_dict.update(data['filters'])

        if 'git' in data:
            config_dict.update(data['git'])

        return cls(**{k: v for k, v in config_dict.items() if hasattr(cls, k)})

    @classmethod
    def find_config(cls, start_dir: Path = None) -> Optional['Config']:
        """
        Find and load config file by searching up the directory tree.

        Looks for .code-translator.toml in current dir and parent dirs.
        """
        if start_dir is None:
            start_dir = Path.cwd()

        current = start_dir.resolve()

        # Search up to root
        while current != current.parent:
            config_file = current / '.code-translator.toml'
            if config_file.exists():
                return cls.from_file(config_file)
            current = current.parent

        # Not found, return defaults
        return cls()

    def merge_with_args(self, **kwargs) -> 'Config':
        """
        Create a new Config with command-line arguments merged in.

        This is a pure function that returns a new Config object without
        modifying the original. CLI arguments take precedence over config file values.

        Returns:
            New Config object with merged values
        """
        # Start with a copy of current config values
        merged_values = {
            'model': kwargs.get('model') or self.model,
            'source_lang': kwargs.get('source_lang') or self.source_lang,
            'target_lang': kwargs.get('target_lang') or self.target_lang,
            'temperature': self.temperature,
            'translate_all': kwargs.get('translate_all', self.translate_all),
            'dry_run': kwargs.get('dry_run', self.dry_run),
            'max_workers': kwargs.get('workers') or self.max_workers,
            'recursive': kwargs.get('recursive', self.recursive),
            'skip_dirs': self.skip_dirs,
            'skip_extensions': self.skip_extensions,
            'file_patterns': self.file_patterns,
            'auto_create_branch': self.auto_create_branch,
            'branch_prefix': self.branch_prefix,
        }

        # Create and return new Config object
        return Config(**merged_values)
