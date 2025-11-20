"""Tests for the parser module."""

import pytest
from code_translator.parser import CodeParser, ElementType, CodeElement


class TestCodeParser:
    """Test the CodeParser class."""

    def test_detect_language_python(self):
        """Test Python file detection."""
        from pathlib import Path
        assert CodeParser.detect_language(Path("test.py")) == "python"
        assert CodeParser.detect_language(Path("/path/to/file.py")) == "python"

    def test_detect_language_javascript(self):
        """Test JavaScript/TypeScript file detection."""
        from pathlib import Path
        assert CodeParser.detect_language(Path("test.js")) == "javascript"
        assert CodeParser.detect_language(Path("test.jsx")) == "javascript"
        assert CodeParser.detect_language(Path("test.ts")) == "javascript"
        assert CodeParser.detect_language(Path("test.tsx")) == "javascript"

    def test_detect_language_unsupported(self):
        """Test unsupported file types."""
        from pathlib import Path
        assert CodeParser.detect_language(Path("test.txt")) is None
        assert CodeParser.detect_language(Path("test.md")) is None
        assert CodeParser.detect_language(Path("README")) is None

    def test_contains_non_ascii_chinese(self):
        """Test detection of Chinese characters."""
        assert CodeParser.contains_non_ascii("这是中文")
        assert CodeParser.contains_non_ascii("Hello 世界")
        assert CodeParser.contains_non_ascii("测试")

    def test_contains_non_ascii_english(self):
        """Test that English text is not flagged."""
        assert not CodeParser.contains_non_ascii("Hello World")
        assert not CodeParser.contains_non_ascii("def test():")
        assert not CodeParser.contains_non_ascii("// comment")

    def test_extract_python_line_comments(self, sample_python_code):
        """Test extraction of Python line comments."""
        elements = CodeParser.extract_comments_and_docstrings(
            sample_python_code, "python"
        )

        # Should find comments with Chinese text
        comment_texts = [e.text for e in elements if e.type == ElementType.COMMENT]
        assert any("返回相加结果" in text for text in comment_texts)
        assert any("这里执行乘法" in text for text in comment_texts)
        assert any("主函数" in text for text in comment_texts)

    def test_extract_python_docstrings(self, sample_python_code):
        """Test extraction of Python docstrings."""
        elements = CodeParser.extract_comments_and_docstrings(
            sample_python_code, "python"
        )

        docstring_texts = [e.text for e in elements if e.type == ElementType.DOCSTRING]
        assert any("这是一个测试模块" in text for text in docstring_texts)
        assert any("计算两个数的和" in text for text in docstring_texts)

    def test_extract_javascript_comments(self, sample_javascript_code):
        """Test extraction of JavaScript comments."""
        elements = CodeParser.extract_comments_and_docstrings(
            sample_javascript_code, "javascript"
        )

        assert len(elements) > 0

        # Check for line comment
        comment_texts = [e.text for e in elements]
        assert any("JavaScript文件" in text for text in comment_texts)
        assert any("返回和" in text for text in comment_texts)

    def test_extract_java_comments(self, sample_java_code):
        """Test extraction of Java comments."""
        elements = CodeParser.extract_comments_and_docstrings(
            sample_java_code, "java"
        )

        assert len(elements) > 0
        comment_texts = [e.text for e in elements]
        assert any("Java类" in text for text in comment_texts)
        assert any("加法方法" in text for text in comment_texts)

    def test_no_extraction_without_chinese(self, sample_code_no_chinese):
        """Test that English-only code yields no elements."""
        elements = CodeParser.extract_comments_and_docstrings(
            sample_code_no_chinese, "python"
        )

        # Should be empty because no Chinese characters
        assert len(elements) == 0

    def test_extract_all_translatable(self, sample_python_code):
        """Test extraction with translate_all mode."""
        # Add a string literal with Chinese
        code_with_string = sample_python_code + '\nmessage = "测试消息"\n'

        elements = CodeParser.extract_all_translatable(code_with_string, "python")

        # Should include comments, docstrings, AND string literals
        assert len(elements) > 0

        # Check that we have different element types
        types = {e.type for e in elements}
        assert ElementType.COMMENT in types or ElementType.DOCSTRING in types

    def test_code_element_attributes(self, sample_python_code):
        """Test that CodeElement has correct attributes."""
        elements = CodeParser.extract_comments_and_docstrings(
            sample_python_code, "python"
        )

        assert len(elements) > 0

        element = elements[0]
        assert hasattr(element, 'type')
        assert hasattr(element, 'text')
        assert hasattr(element, 'start_line')
        assert hasattr(element, 'end_line')
        assert hasattr(element, 'start_col')
        assert hasattr(element, 'end_col')
        assert hasattr(element, 'original_text')

        # Check types
        assert isinstance(element.start_line, int)
        assert isinstance(element.end_line, int)
        assert element.start_line >= 0
        assert element.end_line >= element.start_line

    def test_empty_file(self):
        """Test parsing empty file."""
        elements = CodeParser.extract_comments_and_docstrings("", "python")
        assert len(elements) == 0

    def test_file_with_only_code(self):
        """Test file with only code, no comments."""
        code = "def add(a, b):\n    return a + b\n"
        elements = CodeParser.extract_comments_and_docstrings(code, "python")
        assert len(elements) == 0

    def test_multiline_docstring(self):
        """Test multiline docstring extraction."""
        code = '''"""
这是第一行
这是第二行
这是第三行
"""
def test():
    pass
'''
        elements = CodeParser.extract_comments_and_docstrings(code, "python")
        assert len(elements) == 1
        assert elements[0].type == ElementType.DOCSTRING
        assert elements[0].end_line > elements[0].start_line
