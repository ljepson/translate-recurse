"""Command-line interface for code-translator."""

import sys
from pathlib import Path
import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .config import Config
from .translator import LocalTranslator, TranslationConfig
from .processor import FileProcessor


console = Console()


def print_banner():
    """Print welcome banner."""
    banner = """
    ╔═══════════════════════════════════════╗
    ║     Code Translator v0.1.0            ║
    ║  Fast Local LLM Code Translation      ║
    ╚═══════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def print_stats(stats):
    """Print processing statistics."""
    table = Table(title="Translation Statistics", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green", justify="right")

    table.add_row("Files Scanned", str(stats.files_scanned))
    table.add_row("Files with Foreign Text", str(stats.files_with_foreign_text))
    table.add_row("Files Translated", str(stats.files_translated))
    table.add_row("Elements Translated", str(stats.elements_translated))
    table.add_row("Files Skipped", str(stats.files_skipped))
    table.add_row("Errors", str(len(stats.errors)))

    console.print(table)

    if stats.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in stats.errors[:10]:  # Show first 10
            console.print(f"  • {error}", style="red")
        if len(stats.errors) > 10:
            console.print(f"  ... and {len(stats.errors) - 10} more", style="red dim")


@click.command()
@click.argument('path', type=click.Path(exists=True, path_type=Path), default='.')
@click.option(
    '--model', '-m',
    default='qwen2.5:1.5b',
    help='Ollama model to use for translation (default: qwen2.5:1.5b)'
)
@click.option(
    '--source-lang', '-s',
    default='Chinese',
    help='Source language (default: Chinese)'
)
@click.option(
    '--target-lang', '-t',
    default='English',
    help='Target language (default: English)'
)
@click.option(
    '--translate-all',
    is_flag=True,
    help='Translate ALL elements including string literals and identifiers (RISKY!)'
)
@click.option(
    '--dry-run', '-n',
    is_flag=True,
    help='Show what would be translated without modifying files'
)
@click.option(
    '--workers', '-w',
    type=int,
    default=4,
    help='Number of parallel workers (default: 4)'
)
@click.option(
    '--recursive/--no-recursive',
    default=True,
    help='Recursively process subdirectories (default: recursive)'
)
@click.option(
    '--config', '-c',
    type=click.Path(exists=True, path_type=Path),
    help='Path to config file (.code-translator.toml)'
)
@click.option(
    '--list-models',
    is_flag=True,
    help='List available Ollama models and exit'
)
@click.version_option(version='0.1.0', prog_name='code-translator')
def main(
    path: Path,
    model: str,
    source_lang: str,
    target_lang: str,
    translate_all: bool,
    dry_run: bool,
    workers: int,
    recursive: bool,
    config: Optional[Path],
    list_models: bool,
):
    """
    Translate foreign codebases using local LLM.

    Translates comments and docstrings by default. Use --translate-all to
    include string literals (may break code!).

    Examples:

        # Translate current directory (dry run)
        code-translator --dry-run

        # Translate with specific model
        code-translator --model aya:1.3b

        # Translate specific directory
        code-translator /path/to/codebase

        # Translate everything including strings (RISKY!)
        code-translator --translate-all
    """
    print_banner()

    # Handle --list-models
    if list_models:
        try:
            import ollama
            models = ollama.list()
            console.print("\n[bold cyan]Available Ollama Models:[/bold cyan]")
            for model_info in models.get('models', []):
                name = model_info.get('name', 'unknown')
                size = model_info.get('size', 0) / (1024**3)  # Convert to GB
                console.print(f"  • {name} ({size:.1f} GB)")
            sys.exit(0)
        except Exception as e:
            console.print(f"[red]Error listing models: {e}[/red]")
            sys.exit(1)

    # Load configuration
    if config:
        app_config = Config.from_file(config)
    else:
        app_config = Config.find_config(path)

    # Merge CLI args with config
    app_config.merge_with_args(
        model=model,
        source_lang=source_lang,
        target_lang=target_lang,
        translate_all=translate_all,
        dry_run=dry_run,
        workers=workers,
        recursive=recursive,
    )

    # Show configuration
    config_panel = f"""
    [cyan]Model:[/cyan] {app_config.model}
    [cyan]Translation:[/cyan] {app_config.source_lang} → {app_config.target_lang}
    [cyan]Mode:[/cyan] {'Comments + Docstrings + Strings' if app_config.translate_all else 'Comments + Docstrings only'}
    [cyan]Dry Run:[/cyan] {'Yes' if app_config.dry_run else 'No'}
    [cyan]Workers:[/cyan] {app_config.max_workers}
    [cyan]Path:[/cyan] {path}
    """
    console.print(Panel(config_panel, title="Configuration", border_style="cyan"))

    if app_config.translate_all:
        console.print(
            "\n[bold yellow]⚠ WARNING:[/bold yellow] --translate-all will translate string literals.\n"
            "This may break your code! Use with caution.\n"
        )
        if not dry_run and not click.confirm("Continue?"):
            console.print("[yellow]Aborted.[/yellow]")
            sys.exit(0)

    # Initialize translator
    console.print("\n[cyan]Initializing translator...[/cyan]")
    try:
        trans_config = TranslationConfig(
            model=app_config.model,
            source_lang=app_config.source_lang,
            target_lang=app_config.target_lang,
            temperature=app_config.temperature,
        )
        translator = LocalTranslator(trans_config)
        console.print("[green]✓[/green] Translator ready\n")
    except Exception as e:
        console.print(f"[red]Error initializing translator: {e}[/red]")
        console.print("[yellow]Make sure Ollama is running: ollama serve[/yellow]")
        sys.exit(1)

    # Process files
    processor = FileProcessor(
        translator=translator,
        translate_all=app_config.translate_all,
        dry_run=app_config.dry_run,
        max_workers=app_config.max_workers,
    )

    try:
        with console.status("[cyan]Processing files...", spinner="dots"):
            stats = processor.process_directory(path, recursive=app_config.recursive)

        # Print results
        console.print()
        print_stats(stats)

        if app_config.dry_run:
            console.print("\n[yellow]Dry run complete. No files were modified.[/yellow]")
        else:
            console.print("\n[green]✓ Translation complete![/green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]Error: {e}[/red]")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
