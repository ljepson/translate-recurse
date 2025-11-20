"""Ollama-based translation engine."""

import ollama
from typing import Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class TranslationConfig:
    """Configuration for translation."""
    model: str = "qwen2.5:1.5b"
    source_lang: str = "Chinese"
    target_lang: str = "English"
    temperature: float = 0.3  # 0.3 provides a good balance between consistency and translation quality for translation tasks. Lower values make output more deterministic; higher values increase creativity but may reduce accuracy.
    max_text_length: int = 10000  # Maximum characters per translation
    max_num_predict: int = 4096  # Cap output tokens to prevent API issues


@dataclass
class TranslationResult:
    """Result of a translation attempt."""
    text: str
    success: bool
    error: Optional[str] = None


class LocalTranslator:
    """Fast local LLM translator using Ollama."""

    def __init__(self, config: TranslationConfig):
        self.config = config
        self._verify_model()

    def _verify_model(self) -> None:
        """Check if the model is available, pull if not."""
        try:
            ollama.show(self.config.model)
        except ollama.ResponseError:
            print(f"Model {self.config.model} not found locally. Pulling...")
            ollama.pull(self.config.model)
            print(f"Successfully pulled {self.config.model}")

    def translate(self, text: str, context: Optional[str] = None) -> str:
        """
        Translate text from source to target language.

        Args:
            text: Text to translate (max self.config.max_text_length chars)
            context: Optional context about what this text is (e.g., "Python comment", "docstring")

        Returns:
            Translated text, or original text if translation fails
        """
        if not text.strip():
            return text

        # Validate input length
        if len(text) > self.config.max_text_length:
            print(f"Warning: Text too long ({len(text)} chars), truncating to {self.config.max_text_length}")
            text = text[:self.config.max_text_length]

        # Build prompt
        context_info = f" This is a {context}." if context else ""
        prompt = (
            f"Translate the following {self.config.source_lang} text to {self.config.target_lang}. "
            f"Preserve all formatting, line breaks, and special characters.{context_info}\n\n"
            f"Text to translate:\n{text}\n\n"
            f"Translation:"
        )

        try:
            # Cap num_predict to prevent excessive resource usage
            # Estimate 2x input length, but cap at max_num_predict
            num_predict = min(len(text) * 2, self.config.max_num_predict)

            response = ollama.generate(
                model=self.config.model,
                prompt=prompt,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": num_predict,
                }
            )

            translation = response['response'].strip()
            return translation

        except Exception as e:
            print(f"Translation error for text '{text[:50]}...': {e}")
            return text  # Return original on error

    def translate_with_result(self, text: str, context: Optional[str] = None) -> TranslationResult:
        """
        Translate text and return detailed result with success/error info.

        Args:
            text: Text to translate
            context: Optional context about what this text is

        Returns:
            TranslationResult with translated text and status
        """
        if not text.strip():
            return TranslationResult(text=text, success=True)

        # Validate input length
        if len(text) > self.config.max_text_length:
            return TranslationResult(
                text=text,
                success=False,
                error=f"Text too long ({len(text)} > {self.config.max_text_length} chars)"
            )

        # Build prompt
        context_info = f" This is a {context}." if context else ""
        prompt = (
            f"Translate the following {self.config.source_lang} text to {self.config.target_lang}. "
            f"Preserve all formatting, line breaks, and special characters.{context_info}\n\n"
            f"Text to translate:\n{text}\n\n"
            f"Translation:"
        )

        try:
            num_predict = min(len(text) * 2, self.config.max_num_predict)

            response = ollama.generate(
                model=self.config.model,
                prompt=prompt,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": num_predict,
                }
            )

            translation = response['response'].strip()
            return TranslationResult(text=translation, success=True)

        except Exception as e:
            error_msg = f"Translation failed: {str(e)}"
            return TranslationResult(text=text, success=False, error=error_msg)

    def translate_batch(
        self,
        texts: list[tuple[str, Optional[str]]],
        max_workers: int = 4
    ) -> list[str]:
        """
        Translate multiple texts in parallel for improved throughput.

        Args:
            texts: List of (text, context) tuples
            max_workers: Number of parallel translation threads

        Returns:
            List of translated texts in same order as input
        """
        if not texts:
            return []

        # Use ThreadPoolExecutor for parallel translations
        results = [None] * len(texts)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all translation tasks
            future_to_index = {
                executor.submit(self.translate, text, context): i
                for i, (text, context) in enumerate(texts)
            }

            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    # If translation failed, use original text
                    results[index] = texts[index][0]
                    print(f"Batch translation failed for item {index}: {e}")

        return results
