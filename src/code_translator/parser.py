"""Syntax-aware code parsing to extract translatable elements."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from enum import Enum


class ElementType(Enum):
    """Types of code elements that can be translated."""
    COMMENT = "comment"
    DOCSTRING = "docstring"
    STRING_LITERAL = "string_literal"
    IDENTIFIER = "identifier"


@dataclass
class CodeElement:
    """A translatable element in source code."""
    type: ElementType
    text: str
    start_line: int
    end_line: int
    start_col: int
    end_col: int
    original_text: str  # Full original line(s) for reconstruction


class CodeParser:
    """Extract translatable elements from source code."""

    # Regex patterns for different languages
    PATTERNS = {
        'python': {
            'line_comment': re.compile(r'#(.*)$', re.MULTILINE),
            'docstring': re.compile(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', re.DOTALL),
            # Match single and double quoted strings (excluding newlines)
            # Triple-quoted strings are handled by docstring pattern above
            'string': re.compile(r'"([^"\\\n]|\\.)*"|\'([^\'\\\n]|\\.)*\''),
        },
        'javascript': {
            'line_comment': re.compile(r'//(.*)$', re.MULTILINE),
            'block_comment': re.compile(r'/\*(.*?)\*/', re.DOTALL),
            'string': re.compile(r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'|`([^`\\]|\\.)*`'),
        },
        'java': {
            'line_comment': re.compile(r'//(.*)$', re.MULTILINE),
            'block_comment': re.compile(r'/\*(.*?)\*/', re.DOTALL),
            'javadoc': re.compile(r'/\*\*(.*?)\*/', re.DOTALL),
            'string': re.compile(r'"([^"\\]|\\.)*"'),
        },
        'go': {
            'line_comment': re.compile(r'//(.*)$', re.MULTILINE),
            'block_comment': re.compile(r'/\*(.*?)\*/', re.DOTALL),
            'string': re.compile(r'"([^"\\]|\\.)*"|`([^`])*`'),
        },
        'rust': {
            'line_comment': re.compile(r'//(.*)$', re.MULTILINE),
            'block_comment': re.compile(r'/\*(.*?)\*/', re.DOTALL),
            'doc_comment': re.compile(r'///(.*)$', re.MULTILINE),
            'string': re.compile(r'"([^"\\]|\\.)*"'),
        },
    }

    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'javascript',
        '.tsx': 'javascript',
        '.java': 'java',
        '.go': 'go',
        '.rs': 'rust',
        '.c': 'javascript',  # C-style comments
        '.cpp': 'javascript',
        '.cc': 'javascript',
        '.h': 'javascript',
        '.hpp': 'javascript',
    }

    @staticmethod
    def detect_language(file_path: Path) -> Optional[str]:
        """Detect language from file extension."""
        suffix = file_path.suffix.lower()
        return CodeParser.LANGUAGE_EXTENSIONS.get(suffix)

    @staticmethod
    def contains_non_ascii(text: str) -> bool:
        """
        Check if text contains CJK (Chinese, Japanese, Korean) characters.

        This specifically targets CJK Unified Ideographs range (U+4E00 to U+9FFF)
        which covers most Chinese characters. For broader CJK support including
        Japanese kana and Korean hangul, extend the range check.
        """
        # Check for CJK Unified Ideographs (most Chinese characters)
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
            # Also check for Hiragana and Katakana (Japanese)
            if '\u3040' <= char <= '\u30ff':
                return True
            # And Hangul (Korean)
            if '\uac00' <= char <= '\ud7af':
                return True
        return False

    @staticmethod
    def extract_comments_and_docstrings(content: str, language: str) -> list[CodeElement]:
        """
        Extract comments and docstrings from source code.

        Args:
            content: Source code content
            language: Programming language

        Returns:
            List of CodeElement objects
        """
        elements = []
        patterns = CodeParser.PATTERNS.get(language, {})

        lines = content.split('\n')

        # Extract line comments
        if 'line_comment' in patterns:
            for match in patterns['line_comment'].finditer(content):
                comment_text = match.group(1).strip()
                if CodeParser.contains_non_ascii(comment_text):
                    # Find line number
                    line_num = content[:match.start()].count('\n')
                    elements.append(CodeElement(
                        type=ElementType.COMMENT,
                        text=comment_text,
                        start_line=line_num,
                        end_line=line_num,
                        start_col=match.start() - content.rfind('\n', 0, match.start()) - 1,
                        end_col=match.end() - content.rfind('\n', 0, match.end()) - 1,
                        original_text=lines[line_num] if line_num < len(lines) else ""
                    ))

        # Extract block comments / docstrings
        for pattern_name in ['block_comment', 'docstring', 'javadoc', 'doc_comment']:
            if pattern_name in patterns:
                for match in patterns[pattern_name].finditer(content):
                    # Get the actual comment text (group 1 or 2 for docstrings)
                    comment_text = match.group(1) if match.group(1) else (match.group(2) or "")
                    comment_text = comment_text.strip()

                    if CodeParser.contains_non_ascii(comment_text):
                        start_line = content[:match.start()].count('\n')
                        end_line = content[:match.end()].count('\n')

                        element_type = ElementType.DOCSTRING if 'doc' in pattern_name else ElementType.COMMENT

                        elements.append(CodeElement(
                            type=element_type,
                            text=comment_text,
                            start_line=start_line,
                            end_line=end_line,
                            start_col=match.start() - content.rfind('\n', 0, match.start()) - 1,
                            end_col=match.end() - content.rfind('\n', 0, match.end()) - 1,
                            original_text=match.group(0)
                        ))

        return elements

    @staticmethod
    def extract_all_translatable(content: str, language: str) -> list[CodeElement]:
        """
        Extract ALL translatable elements including strings and identifiers.

        This is more aggressive and may break code - use with caution!
        """
        # Start with comments and docstrings
        elements = CodeParser.extract_comments_and_docstrings(content, language)

        # Build set of positions already covered by docstrings/comments to avoid duplicates
        covered_ranges = set()
        for elem in elements:
            # Mark character positions as covered
            start_pos = sum(len(line) + 1 for i, line in enumerate(content.split('\n')[:elem.start_line]))
            end_pos = sum(len(line) + 1 for i, line in enumerate(content.split('\n')[:elem.end_line + 1]))
            covered_ranges.add((start_pos, end_pos))

        # Add string literals (excluding those already matched as docstrings)
        patterns = CodeParser.PATTERNS.get(language, {})
        if 'string' in patterns:
            for match in patterns['string'].finditer(content):
                # Check if this match overlaps with any covered range
                match_start = match.start()
                match_end = match.end()

                is_covered = any(
                    match_start >= start and match_end <= end
                    for start, end in covered_ranges
                )

                if not is_covered:
                    string_text = match.group(0)[1:-1]  # Remove quotes
                    if CodeParser.contains_non_ascii(string_text):
                        line_num = content[:match.start()].count('\n')
                        lines = content.split('\n')
                        elements.append(CodeElement(
                            type=ElementType.STRING_LITERAL,
                            text=string_text,
                            start_line=line_num,
                            end_line=line_num,
                            start_col=match.start() - content.rfind('\n', 0, match.start()) - 1,
                            end_col=match.end() - content.rfind('\n', 0, match.end()) - 1,
                            original_text=lines[line_num] if line_num < len(lines) else ""
                        ))

        return elements
