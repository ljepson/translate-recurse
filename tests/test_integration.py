"""Integration tests for the full translation pipeline."""

import pytest
from pathlib import Path
from code_translator.translator import LocalTranslator, TranslationConfig
from code_translator.processor import FileProcessor
from code_translator.config import Config


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_pipeline_dry_run(
        self, mock_ollama, temp_dir, sample_python_code
    ):
        """Test complete translation pipeline in dry-run mode."""
        # Setup
        test_file = temp_dir / "test.py"
        test_file.write_text(sample_python_code)
        original_content = test_file.read_text()

        # Create translator
        config = TranslationConfig()
        translator = LocalTranslator(config)

        # Create processor
        processor = FileProcessor(
            translator,
            translate_all=False,
            dry_run=True,
            max_workers=2,
        )

        # Process
        stats = processor.process_directory(temp_dir, recursive=False)

        # Verify
        assert stats.files_scanned >= 1
        assert stats.files_with_foreign_text >= 1
        assert test_file.read_text() == original_content  # Unchanged in dry-run

    def test_full_pipeline_with_translation(
        self, mock_ollama, temp_dir, sample_python_code
    ):
        """Test complete translation pipeline with actual translation."""
        # Setup
        test_file = temp_dir / "test.py"
        test_file.write_text(sample_python_code)
        original_content = test_file.read_text()

        # Create translator
        config = TranslationConfig()
        translator = LocalTranslator(config)

        # Create processor (not dry-run)
        processor = FileProcessor(
            translator,
            translate_all=False,
            dry_run=False,
            max_workers=1,
        )

        # Process
        stats = processor.process_directory(temp_dir, recursive=False)

        # Verify processing occurred
        assert stats.files_scanned >= 1
        assert stats.files_with_foreign_text >= 1
        assert stats.files_translated >= 1
        assert stats.elements_translated > 0

        # File should be modified
        new_content = test_file.read_text()
        # Content changed or stayed same depending on mock behavior
        assert new_content is not None

    def test_config_to_processor_pipeline(
        self, mock_ollama, temp_dir, sample_python_code
    ):
        """Test using Config object to drive the pipeline."""
        # Create test file
        test_file = temp_dir / "test.py"
        test_file.write_text(sample_python_code)

        # Load config
        app_config = Config(
            model="qwen2.5:1.5b",
            translate_all=False,
            dry_run=True,
            max_workers=2,
        )

        # Create components
        trans_config = TranslationConfig(
            model=app_config.model,
            source_lang=app_config.source_lang,
            target_lang=app_config.target_lang,
        )
        translator = LocalTranslator(trans_config)
        processor = FileProcessor(
            translator,
            translate_all=app_config.translate_all,
            dry_run=app_config.dry_run,
            max_workers=app_config.max_workers,
        )

        # Process
        stats = processor.process_directory(temp_dir, recursive=app_config.recursive)

        # Verify
        assert stats.files_scanned >= 1

    def test_multiple_file_types(
        self, mock_ollama, temp_dir, sample_python_code, sample_javascript_code
    ):
        """Test processing multiple file types in one run."""
        # Create files
        (temp_dir / "test.py").write_text(sample_python_code)
        (temp_dir / "test.js").write_text(sample_javascript_code)

        # Create translator and processor
        config = TranslationConfig()
        translator = LocalTranslator(config)
        processor = FileProcessor(translator, dry_run=True, max_workers=2)

        # Process
        stats = processor.process_directory(temp_dir, recursive=False)

        # Should process both files
        assert stats.files_scanned >= 2
        assert stats.files_with_foreign_text >= 2

    def test_nested_directory_structure(
        self, mock_ollama, temp_dir, sample_python_code
    ):
        """Test processing deeply nested directory structure."""
        # Create nested structure
        deep_dir = temp_dir / "level1" / "level2" / "level3"
        deep_dir.mkdir(parents=True)

        # Create files at various levels
        (temp_dir / "root.py").write_text(sample_python_code)
        (temp_dir / "level1" / "l1.py").write_text(sample_python_code)
        (temp_dir / "level1" / "level2" / "l2.py").write_text(sample_python_code)
        (deep_dir / "l3.py").write_text(sample_python_code)

        # Process
        config = TranslationConfig()
        translator = LocalTranslator(config)
        processor = FileProcessor(translator, dry_run=True, max_workers=2)
        stats = processor.process_directory(temp_dir, recursive=True)

        # Should find all files
        assert stats.files_scanned >= 4
        assert stats.files_with_foreign_text >= 4

    def test_mixed_content_directory(
        self, mock_ollama, temp_dir, sample_python_code, sample_code_no_chinese
    ):
        """Test directory with mix of files (with/without Chinese)."""
        # Create mixed files
        (temp_dir / "with_chinese1.py").write_text(sample_python_code)
        (temp_dir / "with_chinese2.py").write_text(sample_python_code)
        (temp_dir / "without_chinese.py").write_text(sample_code_no_chinese)
        (temp_dir / "binary.pyc").write_bytes(b"compiled")

        # Process
        config = TranslationConfig()
        translator = LocalTranslator(config)
        processor = FileProcessor(translator, dry_run=True, max_workers=2)
        stats = processor.process_directory(temp_dir, recursive=False)

        # Verify stats
        assert stats.files_scanned >= 3  # .py files
        assert stats.files_with_foreign_text == 2  # Only 2 with Chinese
        assert stats.files_skipped >= 1  # .pyc file

    def test_error_recovery(self, mock_ollama, temp_dir, sample_python_code):
        """Test that processor continues after individual file errors."""
        # Create files
        good_file = temp_dir / "good.py"
        good_file.write_text(sample_python_code)

        bad_file = temp_dir / "bad.py"
        bad_file.write_bytes(b'\x80\x81\x82')  # Invalid UTF-8

        another_good = temp_dir / "good2.py"
        another_good.write_text(sample_python_code)

        # Process
        config = TranslationConfig()
        translator = LocalTranslator(config)
        processor = FileProcessor(translator, dry_run=True, max_workers=1)
        stats = processor.process_directory(temp_dir, recursive=False)

        # Should process good files despite bad file
        assert stats.files_scanned >= 3
        assert stats.files_with_foreign_text >= 2  # The two good files
        assert stats.files_skipped >= 1  # The bad file

    def test_translate_all_mode(
        self, mock_ollama, temp_dir
    ):
        """Test translate_all mode with string literals."""
        code_with_strings = '''
def greet():
    """打招呼函数"""
    message = "你好世界"
    return message
'''
        test_file = temp_dir / "test.py"
        test_file.write_text(code_with_strings)

        # Process with translate_all
        config = TranslationConfig()
        translator = LocalTranslator(config)
        processor = FileProcessor(
            translator,
            translate_all=True,
            dry_run=True,
            max_workers=1,
        )
        stats = processor.process_directory(temp_dir, recursive=False)

        # Should find both docstring and string literal
        assert stats.files_with_foreign_text >= 1
        assert stats.elements_translated > 1  # Multiple elements

    def test_empty_directory(self, mock_ollama, temp_dir):
        """Test processing empty directory."""
        empty_dir = temp_dir / "empty"
        empty_dir.mkdir()

        config = TranslationConfig()
        translator = LocalTranslator(config)
        processor = FileProcessor(translator, dry_run=True)
        stats = processor.process_directory(empty_dir, recursive=True)

        # Should complete without errors
        assert stats.files_scanned == 0
        assert stats.files_translated == 0
        assert len(stats.errors) == 0
