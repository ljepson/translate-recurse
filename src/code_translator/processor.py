"""File processing logic for translating codebases."""

import os
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from .parser import CodeParser, CodeElement, ElementType
from .translator import LocalTranslator, TranslationConfig


@dataclass
class ProcessingStats:
    """Statistics from processing."""
    files_scanned: int = 0
    files_with_foreign_text: int = 0
    files_translated: int = 0
    elements_translated: int = 0
    files_skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class FileProcessor:
    """Process files for translation."""

    # Skip these directories
    SKIP_DIRS = {'.git', '.svn', '.hg', '__pycache__', 'node_modules', 'venv', '.venv', 'dist', 'build'}

    # Skip these file extensions
    SKIP_EXTENSIONS = {
        '.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', '.obj',
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', '.svg',
        '.mp3', '.mp4', '.avi', '.mov', '.wav',
        '.zip', '.tar', '.gz', '.rar', '.7z',
        '.pdf', '.doc', '.docx',
    }

    def __init__(
        self,
        translator: LocalTranslator,
        translate_all: bool = False,
        dry_run: bool = False,
        max_workers: int = 4,
    ):
        self.translator = translator
        self.translate_all = translate_all
        self.dry_run = dry_run
        self.max_workers = max_workers
        self.stats = ProcessingStats()

    def should_skip_file(self, file_path: Path) -> tuple[bool, Optional[str]]:
        """
        Check if file should be skipped.

        Returns:
            (should_skip, reason)
        """
        # Check extension
        if file_path.suffix.lower() in self.SKIP_EXTENSIONS:
            return True, "binary/media file"

        # Check if we support the language
        if not CodeParser.detect_language(file_path):
            return True, "unsupported file type"

        # Check file size (skip very large files > 1MB)
        try:
            if file_path.stat().st_size > 1024 * 1024:
                return True, "file too large (>1MB)"
        except OSError:
            return True, "cannot stat file"

        return False, None

    def process_file(self, file_path: Path) -> Optional[dict]:
        """
        Process a single file.

        Returns:
            Dictionary with processing results, or None if skipped
        """
        self.stats.files_scanned += 1

        # Check if should skip
        should_skip, reason = self.should_skip_file(file_path)
        if should_skip:
            self.stats.files_skipped += 1
            return None

        try:
            # Read file
            content = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError) as e:
            self.stats.files_skipped += 1
            self.stats.errors.append(f"{file_path}: {e}")
            return None

        # Detect language
        language = CodeParser.detect_language(file_path)
        if not language:
            self.stats.files_skipped += 1
            return None

        # Extract translatable elements
        if self.translate_all:
            elements = CodeParser.extract_all_translatable(content, language)
        else:
            elements = CodeParser.extract_comments_and_docstrings(content, language)

        if not elements:
            return None

        self.stats.files_with_foreign_text += 1

        # Translate elements
        translated_elements = []
        for element in elements:
            context = element.type.value
            translated_text = self.translator.translate(element.text, context)
            translated_elements.append((element, translated_text))
            self.stats.elements_translated += 1

        # Reconstruct file
        new_content = self._reconstruct_file(content, translated_elements)

        # Write back if not dry run
        if not self.dry_run:
            try:
                file_path.write_text(new_content, encoding='utf-8')
                self.stats.files_translated += 1
            except OSError as e:
                self.stats.errors.append(f"{file_path}: Failed to write - {e}")
                return None

        return {
            'file': file_path,
            'elements_count': len(elements),
            'original_size': len(content),
            'new_size': len(new_content),
        }

    def _reconstruct_file(
        self,
        original_content: str,
        translated_elements: list[tuple[CodeElement, str]]
    ) -> str:
        """
        Reconstruct file with translated elements.

        This is a simple replacement strategy - we replace text by position.
        """
        lines = original_content.split('\n')

        # Sort elements by line number in reverse to avoid offset issues
        sorted_elements = sorted(translated_elements, key=lambda x: x[0].start_line, reverse=True)

        for element, translation in sorted_elements:
            if element.type == ElementType.COMMENT:
                # Replace comment text
                line_idx = element.start_line
                if line_idx < len(lines):
                    line = lines[line_idx]
                    # Find comment marker and replace after it
                    if '#' in line:  # Python
                        prefix = line[:line.find('#') + 1]
                        lines[line_idx] = f"{prefix} {translation}"
                    elif '//' in line:  # C-style
                        prefix = line[:line.find('//') + 2]
                        lines[line_idx] = f"{prefix} {translation}"

            elif element.type == ElementType.DOCSTRING:
                # Replace docstring content
                # This is simplified - just replace the text between the markers
                start_line = element.start_line
                end_line = element.end_line

                if start_line < len(lines):
                    # Handle multi-line docstrings
                    if start_line == end_line:
                        # Single line docstring
                        line = lines[start_line]
                        if '"""' in line:
                            lines[start_line] = f'    """{translation}"""'
                        elif "'''" in line:
                            lines[start_line] = f"    '''{translation}'''"
                    else:
                        # Multi-line - replace middle content
                        # Keep first and last lines (with quotes), replace middle
                        translated_lines = translation.split('\n')
                        lines[start_line:end_line+1] = [
                            lines[start_line].split('"""')[0] + '"""',
                            *[f"    {line}" for line in translated_lines],
                            '    """'
                        ]

            elif element.type == ElementType.STRING_LITERAL:
                # Replace string literal
                line_idx = element.start_line
                if line_idx < len(lines):
                    line = lines[line_idx]
                    # Simple replacement - find the string and replace it
                    # This is naive and might break for complex cases
                    lines[line_idx] = line.replace(element.text, translation)

        return '\n'.join(lines)

    def process_directory(
        self,
        directory: Path,
        recursive: bool = True,
        file_patterns: Optional[list[str]] = None
    ) -> ProcessingStats:
        """
        Process all files in a directory.

        Args:
            directory: Root directory to process
            recursive: Whether to recurse into subdirectories
            file_patterns: Optional list of glob patterns to match

        Returns:
            Processing statistics
        """
        files_to_process = []

        if recursive:
            for root, dirs, files in os.walk(directory):
                # Remove skip dirs
                dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS]

                for file in files:
                    file_path = Path(root) / file
                    files_to_process.append(file_path)
        else:
            files_to_process = list(directory.glob('*'))

        # Filter by patterns if provided
        if file_patterns:
            filtered = []
            for pattern in file_patterns:
                filtered.extend(directory.glob(pattern))
            files_to_process = filtered

        # Process files in parallel
        print(f"Processing {len(files_to_process)} files...")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self.process_file, file_path): file_path
                for file_path in files_to_process
            }

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result = future.result()
                    if result:
                        print(f"✓ {file_path}: {result['elements_count']} elements translated")
                except Exception as e:
                    self.stats.errors.append(f"{file_path}: {e}")
                    print(f"✗ {file_path}: {e}")

        return self.stats
