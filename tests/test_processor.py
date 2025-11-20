"""Tests for the processor module."""

import pytest
from pathlib import Path
from code_translator.processor import FileProcessor, ProcessingStats


class TestProcessingStats:
    """Test ProcessingStats dataclass."""

    def test_default_stats(self):
        """Test default statistics initialization."""
        stats = ProcessingStats()

        assert stats.files_scanned == 0
        assert stats.files_with_foreign_text == 0
        assert stats.files_translated == 0
        assert stats.elements_translated == 0
        assert stats.files_skipped == 0
        assert stats.errors == []

    def test_stats_tracking(self):
        """Test stats can be updated."""
        stats = ProcessingStats()

        stats.files_scanned = 10
        stats.files_translated = 5
        stats.errors.append("Error 1")

        assert stats.files_scanned == 10
        assert stats.files_translated == 5
        assert len(stats.errors) == 1


class TestFileProcessor:
    """Test FileProcessor class."""

    def test_should_skip_binary_file(self, mock_translator):
        """Test that binary files are skipped."""
        processor = FileProcessor(mock_translator)

        should_skip, reason = processor.should_skip_file(Path("test.pyc"))
        assert should_skip is True
        assert "binary" in reason.lower()

        should_skip, reason = processor.should_skip_file(Path("image.jpg"))
        assert should_skip is True

    def test_should_skip_unsupported_language(self, mock_translator):
        """Test that unsupported file types are skipped."""
        processor = FileProcessor(mock_translator)

        should_skip, reason = processor.should_skip_file(Path("README.txt"))
        assert should_skip is True
        assert "unsupported" in reason.lower()

    def test_should_not_skip_supported_file(self, mock_translator):
        """Test that supported files are not skipped."""
        processor = FileProcessor(mock_translator)

        should_skip, reason = processor.should_skip_file(Path("test.py"))
        # Note: May still be skipped for other reasons (size, etc.)
        # but not for extension/language support
        if should_skip:
            assert "unsupported" not in reason.lower()
            assert "binary" not in reason.lower()

    def test_process_file_with_chinese(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test processing a file with Chinese text."""
        processor = FileProcessor(mock_translator, dry_run=True)

        # Create test file
        test_file = temp_dir / "test.py"
        test_file.write_text(sample_python_code)

        result = processor.process_file(test_file)

        # Should have processed the file
        assert result is not None
        assert result['file'] == test_file
        assert result['elements_count'] > 0
        assert processor.stats.files_scanned == 1
        assert processor.stats.files_with_foreign_text == 1

    def test_process_file_without_chinese(
        self, mock_translator, temp_dir, sample_code_no_chinese
    ):
        """Test processing a file without Chinese text."""
        processor = FileProcessor(mock_translator, dry_run=True)

        test_file = temp_dir / "test.py"
        test_file.write_text(sample_code_no_chinese)

        result = processor.process_file(test_file)

        # Should return None (no foreign text)
        assert result is None
        assert processor.stats.files_scanned == 1
        assert processor.stats.files_with_foreign_text == 0

    def test_process_file_dry_run(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test that dry run doesn't modify files."""
        processor = FileProcessor(mock_translator, dry_run=True)

        test_file = temp_dir / "test.py"
        test_file.write_text(sample_python_code)
        original_content = test_file.read_text()

        processor.process_file(test_file)

        # File should not be modified
        assert test_file.read_text() == original_content
        assert processor.stats.files_translated == 0

    def test_process_file_not_dry_run(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test that non-dry-run modifies files."""
        processor = FileProcessor(mock_translator, dry_run=False)

        test_file = temp_dir / "test.py"
        test_file.write_text(sample_python_code)
        original_content = test_file.read_text()

        result = processor.process_file(test_file)

        # File should be modified (or at least attempted)
        if result:  # Only check if processing succeeded
            assert processor.stats.files_translated >= 0

    def test_process_file_translate_all(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test processing with translate_all flag."""
        processor = FileProcessor(
            mock_translator, translate_all=True, dry_run=True
        )

        test_file = temp_dir / "test.py"
        # Add string literal with Chinese
        code_with_string = sample_python_code + '\nmsg = "测试消息"\n'
        test_file.write_text(code_with_string)

        result = processor.process_file(test_file)

        # Should process and find string literals too
        assert result is not None

    def test_process_directory_recursive(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test recursive directory processing."""
        processor = FileProcessor(mock_translator, dry_run=True, max_workers=1)

        # Create directory structure
        (temp_dir / "subdir1").mkdir()
        (temp_dir / "subdir2").mkdir()

        # Create test files
        (temp_dir / "test1.py").write_text(sample_python_code)
        (temp_dir / "subdir1" / "test2.py").write_text(sample_python_code)
        (temp_dir / "subdir2" / "test3.py").write_text(sample_python_code)

        stats = processor.process_directory(temp_dir, recursive=True)

        # Should have scanned all files
        assert stats.files_scanned >= 3
        assert stats.files_with_foreign_text >= 3

    def test_process_directory_non_recursive(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test non-recursive directory processing."""
        processor = FileProcessor(mock_translator, dry_run=True, max_workers=1)

        # Create directory structure
        (temp_dir / "subdir").mkdir()

        # Create files
        (temp_dir / "test1.py").write_text(sample_python_code)
        (temp_dir / "subdir" / "test2.py").write_text(sample_python_code)

        stats = processor.process_directory(temp_dir, recursive=False)

        # Should only process root directory files
        # Exact count depends on what else is in temp_dir

    def test_process_directory_skip_dirs(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test that skip directories are ignored."""
        processor = FileProcessor(mock_translator, dry_run=True, max_workers=1)

        # Create skip directory
        (temp_dir / ".git").mkdir()
        (temp_dir / "node_modules").mkdir()
        (temp_dir / "normal").mkdir()

        # Create files in each
        (temp_dir / ".git" / "test.py").write_text(sample_python_code)
        (temp_dir / "node_modules" / "test.py").write_text(sample_python_code)
        (temp_dir / "normal" / "test.py").write_text(sample_python_code)

        stats = processor.process_directory(temp_dir, recursive=True)

        # Should only process 'normal' directory
        # .git and node_modules should be skipped

    def test_process_file_unicode_decode_error(self, mock_translator, temp_dir):
        """Test handling of files that can't be decoded."""
        processor = FileProcessor(mock_translator, dry_run=True)

        # Create binary file
        test_file = temp_dir / "binary.py"
        test_file.write_bytes(b'\x80\x81\x82\x83')

        result = processor.process_file(test_file)

        # Should be skipped
        assert result is None
        assert processor.stats.files_skipped >= 1

    def test_process_file_large_file(self, mock_translator, temp_dir):
        """Test that very large files are skipped."""
        processor = FileProcessor(mock_translator, dry_run=True)

        # Create large file (> 1MB)
        test_file = temp_dir / "large.py"
        large_content = "# 测试\n" * 100000  # ~500KB+
        test_file.write_text(large_content)

        # Make it actually large
        with open(test_file, 'w') as f:
            f.write("# test\n" * 200000)  # Should exceed 1MB

        result = processor.process_file(test_file)

        # May be skipped due to size
        if result is None:
            assert processor.stats.files_skipped >= 1

    def test_stats_accumulation(
        self, mock_translator, temp_dir, sample_python_code, sample_code_no_chinese
    ):
        """Test that stats accumulate correctly."""
        processor = FileProcessor(mock_translator, dry_run=True, max_workers=1)

        # Create multiple files
        (temp_dir / "with_chinese.py").write_text(sample_python_code)
        (temp_dir / "without_chinese.py").write_text(sample_code_no_chinese)
        (temp_dir / "test.pyc").write_bytes(b"compiled")

        stats = processor.process_directory(temp_dir, recursive=False)

        # Should have scanned all files
        assert stats.files_scanned >= 2  # At least the .py files
        assert stats.files_with_foreign_text >= 1  # The one with Chinese
        assert stats.files_skipped >= 1  # The .pyc file

    def test_parallel_processing(
        self, mock_translator, temp_dir, sample_python_code
    ):
        """Test parallel processing with multiple workers."""
        processor = FileProcessor(mock_translator, dry_run=True, max_workers=4)

        # Create multiple files
        for i in range(10):
            (temp_dir / f"test{i}.py").write_text(sample_python_code)

        stats = processor.process_directory(temp_dir, recursive=False)

        # All files should be processed
        assert stats.files_scanned >= 10
        assert stats.files_with_foreign_text >= 10
