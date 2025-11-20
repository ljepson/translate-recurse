"""Ollama-based translation engine."""

import ollama
from typing import Optional
from dataclasses import dataclass


@dataclass
class TranslationConfig:
    """Configuration for translation."""
    model: str = "qwen2.5:1.5b"
    source_lang: str = "Chinese"
    target_lang: str = "English"
    temperature: float = 0.3  # Lower = more deterministic


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
            text: Text to translate
            context: Optional context about what this text is (e.g., "Python comment", "docstring")

        Returns:
            Translated text
        """
        if not text.strip():
            return text

        # Build prompt
        context_info = f" This is a {context}." if context else ""
        prompt = (
            f"Translate the following {self.config.source_lang} text to {self.config.target_lang}. "
            f"Preserve all formatting, line breaks, and special characters.{context_info}\n\n"
            f"Text to translate:\n{text}\n\n"
            f"Translation:"
        )

        try:
            response = ollama.generate(
                model=self.config.model,
                prompt=prompt,
                options={
                    "temperature": self.config.temperature,
                    "num_predict": len(text) * 2,  # Estimate max output length
                }
            )

            translation = response['response'].strip()
            return translation

        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Return original on error

    def translate_batch(self, texts: list[tuple[str, Optional[str]]]) -> list[str]:
        """
        Translate multiple texts.

        Args:
            texts: List of (text, context) tuples

        Returns:
            List of translated texts in same order
        """
        return [self.translate(text, context) for text, context in texts]
