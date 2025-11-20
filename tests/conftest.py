"""Pytest configuration and shared fixtures."""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
import tempfile
import shutil

from code_translator.translator import LocalTranslator, TranslationConfig
from code_translator.config import Config


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def sample_python_code():
    """Sample Python code with Chinese comments."""
    return '''#!/usr/bin/env python3
"""这是一个测试模块"""

def add(a, b):
    """计算两个数的和"""
    # 返回相加结果
    return a + b

def multiply(x, y):
    # 这里执行乘法
    result = x * y
    return result  # 返回结果

# 主函数
if __name__ == "__main__":
    print("测试")
'''


@pytest.fixture
def sample_javascript_code():
    """Sample JavaScript code with Chinese comments."""
    return '''// 这是一个JavaScript文件
/**
 * 计算总和
 * @param {number} a - 第一个数
 * @param {number} b - 第二个数
 */
function sum(a, b) {
    // 返回和
    return a + b;
}

/* 这是一个块注释 */
const result = sum(5, 3);
'''


@pytest.fixture
def sample_java_code():
    """Sample Java code with Chinese comments."""
    return '''/**
 * 这是一个Java类
 */
public class Calculator {
    // 加法方法
    public int add(int a, int b) {
        return a + b;  // 返回和
    }

    /**
     * 减法方法
     * @param a 被减数
     * @param b 减数
     */
    public int subtract(int a, int b) {
        return a - b;
    }
}
'''


@pytest.fixture
def sample_code_no_chinese():
    """Sample code without Chinese characters."""
    return '''def hello():
    """Say hello."""
    # Print greeting
    return "Hello, World!"
'''


@pytest.fixture
def mock_translator():
    """Mock translator that returns predictable results."""
    translator = Mock(spec=LocalTranslator)

    # Simple mock: just prefix with "TRANSLATED: "
    def mock_translate(text, context=None):
        if not text:
            return text
        return f"TRANSLATED: {text[:20]}..."

    translator.translate.side_effect = mock_translate
    translator.translate_batch.return_value = [
        "TRANSLATED: comment 1",
        "TRANSLATED: comment 2",
    ]

    return translator


@pytest.fixture
def mock_ollama(monkeypatch):
    """Mock ollama module to avoid requiring Ollama service."""
    mock_ollama_module = MagicMock()

    # Mock show() to simulate model exists
    mock_ollama_module.show.return_value = {"model": "qwen2.5:1.5b"}

    # Mock generate() to return fake translations
    def mock_generate(model, prompt, options=None):
        # Extract the text after "Text to translate:"
        if "Text to translate:" in prompt:
            text = prompt.split("Text to translate:")[1].split("Translation:")[0].strip()
            # Return a simple "translation"
            return {"response": f"Translated: {text[:30]}..."}
        return {"response": "Translated text"}

    mock_ollama_module.generate.side_effect = mock_generate
    mock_ollama_module.pull.return_value = None
    mock_ollama_module.ResponseError = Exception

    # Patch the ollama import
    monkeypatch.setattr("code_translator.translator.ollama", mock_ollama_module)

    return mock_ollama_module


@pytest.fixture
def translation_config():
    """Default translation configuration."""
    return TranslationConfig(
        model="qwen2.5:1.5b",
        source_lang="Chinese",
        target_lang="English",
        temperature=0.3,
    )


@pytest.fixture
def app_config():
    """Default application configuration."""
    return Config(
        model="qwen2.5:1.5b",
        source_lang="Chinese",
        target_lang="English",
        translate_all=False,
        dry_run=True,
        max_workers=2,
    )


@pytest.fixture
def sample_config_toml(temp_dir):
    """Create a sample config TOML file."""
    config_content = """[translation]
model = "test-model:1b"
source_lang = "Japanese"
target_lang = "English"
temperature = 0.5

[processing]
translate_all = true
max_workers = 8
"""
    config_path = temp_dir / ".code-translator.toml"
    config_path.write_text(config_content)
    return config_path
