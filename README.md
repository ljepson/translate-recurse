# Code Translator

**Fast, local LLM-powered code translation for understanding foreign codebases.**

Translate Chinese (or other foreign language) comments, docstrings, and optionally string literals to English using local language models via Ollama. Built for individual developers who need to quickly understand codebases written in languages they don't speak.

## Why Code Translator?

- **100% Local** - No API costs, no rate limits, works offline
- **Fast** - Optimized for speed with small models (<3B params) and parallel processing
- **Safe** - Comments/docstrings only by default, won't break your code
- **Smart** - Syntax-aware parsing for Python, JavaScript, Java, Go, Rust, C/C++
- **Flexible** - CLI flags, config files, dry-run mode

## Features

✓ Translate comments and docstrings while preserving code functionality
✓ Syntax-aware parsing for multiple languages
✓ Parallel processing for speed
✓ Dry-run mode to preview changes
✓ Optional aggressive mode (translate strings and identifiers - use with caution!)
✓ Configurable via CLI or config file
✓ Rich terminal output with progress and statistics

## Installation

### Prerequisites

1. **Python 3.11+**
   ```bash
   python --version  # Should be 3.11 or higher
   ```

2. **Ollama** - Install from [ollama.ai](https://ollama.ai)
   ```bash
   # Install Ollama, then pull a translation model
   ollama pull qwen2.5:1.5b  # Recommended: fast, good at Chinese
   # OR
   ollama pull aya:1.3b      # Alternative: multilingual-optimized
   ```

### Install Code Translator

```bash
# Clone the repository
git clone https://github.com/yourusername/code-translator.git
cd code-translator

# Install in development mode
pip install -e .

# Or install dependencies manually
pip install -r requirements.txt
```

## Quick Start

```bash
# Make sure Ollama is running
ollama serve

# Translate current directory (dry run first!)
code-translator --dry-run

# Translate for real
code-translator

# Translate specific directory
code-translator /path/to/chinese/codebase

# Use different model
code-translator --model aya:1.3b

# Translate with more workers (faster)
code-translator --workers 8
```

## Usage

### Basic Commands

```bash
# Dry run (see what would be translated)
code-translator --dry-run

# Translate comments and docstrings (safe)
code-translator

# Translate EVERYTHING including strings (RISKY!)
code-translator --translate-all

# Translate specific directory
code-translator /path/to/code

# Use specific model
code-translator --model qwen2.5:1.5b

# Show available models
code-translator --list-models

# See all options
code-translator --help
```

### Command-Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `PATH` | Directory to translate | Current directory |
| `--model, -m` | Ollama model to use | `qwen2.5:1.5b` |
| `--source-lang, -s` | Source language | `Chinese` |
| `--target-lang, -t` | Target language | `English` |
| `--translate-all` | Translate strings and identifiers (risky!) | `False` |
| `--dry-run, -n` | Preview without modifying files | `False` |
| `--workers, -w` | Number of parallel workers | `4` |
| `--recursive/--no-recursive` | Process subdirectories | `True` |
| `--config, -c` | Path to config file | Auto-detect |
| `--list-models` | List available models and exit | - |

### Configuration File

Create `.code-translator.toml` in your project root:

```toml
[translation]
model = "qwen2.5:1.5b"
source_lang = "Chinese"
target_lang = "English"
temperature = 0.3

[processing]
translate_all = false
max_workers = 4
recursive = true

[filters]
skip_dirs = [".git", "node_modules", "venv", "__pycache__"]
skip_extensions = [".pyc", ".so", ".dll", ".jpg", ".png"]

[git]
auto_create_branch = false
branch_prefix = "translation/"
```

Config file settings are overridden by command-line arguments.

## Supported Languages

Code Translator can parse and translate:

- **Python** (`.py`) - Comments, docstrings
- **JavaScript/TypeScript** (`.js`, `.jsx`, `.ts`, `.tsx`) - Line/block comments
- **Java** (`.java`) - Comments, Javadoc
- **Go** (`.go`) - Comments, doc comments
- **Rust** (`.rs`) - Comments, doc comments
- **C/C++** (`.c`, `.cpp`, `.h`, `.hpp`) - Comments

More languages coming soon!

## Recommended Models

For best results with local LLMs:

| Model | Size | Speed | Quality | Best For |
|-------|------|-------|---------|----------|
| `qwen2.5:1.5b` | ~900MB | ⚡⚡⚡ | ★★★ | Chinese code, fast translation |
| `aya:1.3b` | ~800MB | ⚡⚡⚡ | ★★★ | Multilingual, general purpose |
| `gemma2:2b` | ~1.6GB | ⚡⚡ | ★★★★ | Better quality, slower |
| `qwen2.5-coder:3b` | ~1.9GB | ⚡⚡ | ★★★★★ | Best quality (just over 3B) |

**Recommendation:** Start with `qwen2.5:1.5b` for speed, upgrade to `qwen2.5-coder:3b` if you need better quality.

## Examples

### Example 1: Quick Code Review

```bash
# You found a Chinese Python library on GitHub
git clone https://github.com/someone/chinese-ml-library.git
cd chinese-ml-library

# Quick dry run to see what's translatable
code-translator --dry-run

# Translate just to read the code (don't commit)
code-translator
```

### Example 2: Multilingual Project

```bash
# Translate Japanese comments to English
code-translator --source-lang Japanese --target-lang English /path/to/jp/code

# Or Korean to English
code-translator --source-lang Korean /path/to/korean/project
```

### Example 3: Configuration-Based Workflow

```bash
# Create config in your project
cat > .code-translator.toml <<EOF
[translation]
model = "aya:1.3b"
source_lang = "Chinese"

[processing]
max_workers = 8
EOF

# Now just run without args
code-translator
```

## Safety & Best Practices

### What Gets Translated?

**Default (Safe):**
- ✓ Comments (`# comment`, `// comment`)
- ✓ Docstrings (`"""docstring"""`)
- ✗ String literals (preserved)
- ✗ Variable names (preserved)
- ✗ Function names (preserved)

**With `--translate-all` (Risky!):**
- ✓ Everything above, PLUS:
- ✓ String literals (may break i18n, error messages)
- ✗ Variable/function names (not yet implemented - would break code)

### Before You Translate

1. **Always run `--dry-run` first**
2. **Commit your code** or work on a branch
3. **Test after translation** to ensure nothing broke
4. **Start with small projects** to verify quality

### Limitations

- Translation quality depends on the model (local LLMs are decent but not perfect)
- Very technical/domain-specific terms may not translate well
- Doesn't understand context across files (translates file-by-file)
- `--translate-all` may break string literals used in code logic

## Troubleshooting

### "Error initializing translator"

Make sure Ollama is running:
```bash
ollama serve
```

Pull the model:
```bash
ollama pull qwen2.5:1.5b
```

### "Model not found"

List available models:
```bash
code-translator --list-models
```

Pull the model you want:
```bash
ollama pull model-name
```

### Translation Quality is Poor

Try a better (larger) model:
```bash
code-translator --model qwen2.5-coder:3b
```

Or adjust temperature (lower = more deterministic):
```toml
[translation]
temperature = 0.1  # More conservative translations
```

### Too Slow

Increase workers:
```bash
code-translator --workers 8
```

Use a smaller/faster model:
```bash
code-translator --model qwen2.5:1.5b
```

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest
```

### Code Quality

```bash
# Format
black src/

# Lint
ruff check src/
```

## Roadmap

- [ ] Support for more languages (Kotlin, Swift, PHP, Ruby)
- [ ] Batch API calls for faster translation
- [ ] Git integration (auto-create branches)
- [ ] Translation memory / caching
- [ ] Variable/function name translation (optional, experimental)
- [ ] Web UI for reviewing translations
- [ ] Support for other local LLM backends (llama.cpp, etc.)

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- Built with [Ollama](https://ollama.ai) for local LLM inference
- Inspired by the need to understand amazing open-source projects in any language
- Thanks to the open-source community for building accessible LLMs

---

**Made for developers who believe great code shouldn't have language barriers.**
