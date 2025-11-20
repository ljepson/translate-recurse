"""File processing logic for translating codebases."""

import os
import threading
from pathlib import Path
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .parser import CodeParser, CodeElement, ElementType
from .translator import LocalTranslator


@dataclass
class ProcessingStats:
    """Thread-safe statistics from processing."""
    files_scanned: int = 0
    files_with_foreign_text: int = 0
    files_translated: int = 0
    elements_translated: int = 0
    files_skipped: int = 0
    errors: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment_scanned(self):
        """Thread-safe increment of scanned files."""
        with self._lock:
            self.files_scanned += 1

    def increment_with_foreign_text(self):
        """Thread-safe increment of files with foreign text."""
        with self._lock:
            self.files_with_foreign_text += 1

    def increment_translated(self):
        """Thread-safe increment of translated files."""
        with self._lock:
            self.files_translated += 1

    def increment_elements_translated(self, count: int = 1):
        """Thread-safe increment of translated elements."""
        with self._lock:
            self.elements_translated += count

    def increment_skipped(self):
        """Thread-safe increment of skipped files."""
        with self._lock:
            self.files_skipped += 1

    def add_error(self, error: str):
        """Thread-safe error logging."""
        with self._lock:
            self.errors.append(error)


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
        self.stats.increment_scanned()

        # Check if should skip
        should_skip, reason = self.should_skip_file(file_path)
        if should_skip:
            self.stats.increment_skipped()
            return None

        try:
            # Read file
            content = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError) as e:
            self.stats.increment_skipped()
            self.stats.add_error(f"{file_path}: {e}")
            return None

        # Detect language
        language = CodeParser.detect_language(file_path)
        if not language:
            self.stats.increment_skipped()
            return None

        # Extract translatable elements
        if self.translate_all:
            elements = CodeParser.extract_all_translatable(content, language)
        else:
            elements = CodeParser.extract_comments_and_docstrings(content, language)

        if not elements:
            return None

        self.stats.increment_with_foreign_text()

        # Translate elements
        translated_elements = []
        for element in elements:
            context = element.type.value
            translated_text = self.translator.translate(element.text, context)
            translated_elements.append((element, translated_text))

        self.stats.increment_elements_translated(len(translated_elements))

        # Reconstruct file
        new_content = self._reconstruct_file(content, translated_elements)

        # Write back if not dry run
        if not self.dry_run:
            try:
                file_path.write_text(new_content, encoding='utf-8')
                self.stats.increment_translated()
            except OSError as e:
                self.stats.add_error(f"{file_path}: Failed to write - {e}")
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
        Reconstruct file with translated elements using position-aware replacement.
        """
        lines = original_content.split('\n')

        # Sort elements by line number in reverse to avoid offset issues
        sorted_elements = sorted(translated_elements, key=lambda x: x[0].start_line, reverse=True)

        for element, translation in sorted_elements:
            if element.type == ElementType.COMMENT:
                # Position-aware comment replacement using start_col
                line_idx = element.start_line
                if line_idx < len(lines):
                    line = lines[line_idx]
                    # Use the element's start_col to find the actual comment marker
                    # This handles cases where the comment text itself contains # or //
                    comment_start = element.start_col

                    # Find the comment marker (# or //) at or near start_col
                    if comment_start < len(line):
                        if line[comment_start:comment_start+2] == '//':
                            prefix = line[:comment_start + 2]
                            lines[line_idx] = f"{prefix} {translation}"
                        elif line[comment_start] == '#':
                            prefix = line[:comment_start + 1]
                            lines[line_idx] = f"{prefix} {translation}"
                        else:
                            # Fallback: try to find marker near start_col
                            if '#' in line[max(0, comment_start-2):comment_start+3]:
                                idx = line.rfind('#', 0, comment_start+3)
                                prefix = line[:idx + 1]
                                lines[line_idx] = f"{prefix} {translation}"
                            elif '//' in line[max(0, comment_start-2):comment_start+4]:
                                idx = line.rfind('//', 0, comment_start+4)
                                prefix = line[:idx + 2]
                                lines[line_idx] = f"{prefix} {translation}"

            elif element.type == ElementType.DOCSTRING:
                # Preserve original docstring delimiters and indentation
                start_line = element.start_line
                end_line = element.end_line

                if start_line < len(lines):
                    original_start_line = lines[start_line]

                    # Detect quote style and indentation
                    quote_style = '"""'
                    if "'''" in original_start_line:
                        quote_style = "'''"
                    elif '"""' in original_start_line:
                        quote_style = '"""'

                    # Detect indentation from original line
                    indent = len(original_start_line) - len(original_start_line.lstrip())
                    indent_str = original_start_line[:indent]

                    if start_line == end_line:
                        # Single line docstring - preserve style and indentation
                        lines[start_line] = f'{indent_str}{quote_style}{translation}{quote_style}'
                    else:
                        # Multi-line docstring - preserve quote style and indentation
                        translated_lines = translation.split('\n')

                        # Extract prefix before opening quotes
                        prefix = original_start_line[:original_start_line.find(quote_style)]

                        lines[start_line:end_line+1] = [
                            f'{prefix}{quote_style}',
                            *[f'{indent_str}{line}' if line.strip() else '' for line in translated_lines],
                            f'{indent_str}{quote_style}'
                        ]

            elif element.type == ElementType.STRING_LITERAL:
                # Position-aware string replacement using start_col and end_col
                line_idx = element.start_line
                if line_idx < len(lines):
                    line = lines[line_idx]
                    # Only replace at the specific position, not all occurrences
                    if hasattr(element, 'start_col') and hasattr(element, 'end_col'):
                        # Slice and reconstruct to replace only the specific occurrence
                        before = line[:element.start_col]
                        after = line[element.end_col:]
                        # Preserve the quote character
                        quote_char = line[element.start_col] if element.start_col < len(line) else '"'
                        lines[line_idx] = f'{before}{quote_char}{translation}{quote_char}{after}'
                    else:
                        # Fallback: replace only first occurrence
                        lines[line_idx] = line.replace(element.text, translation, 1)

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
