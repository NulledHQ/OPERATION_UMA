# src/translation_engines/base_engine.py
import abc # Abstract Base Classes module

class TranslationError(Exception):
    """Custom exception for translation errors."""
    pass

class TranslationEngine(abc.ABC):
    """Abstract base class for all translation engines."""

    @abc.abstractmethod
    def __init__(self, config=None):
        """
        Initialize the engine.
        Args:
            config (dict, optional): Engine-specific configuration.
                                      May include credentials path, API keys, etc.
        """
        pass

    @abc.abstractmethod
    def translate(self, text: str, target_language_code: str, source_language_code: str = None) -> str:
        """
        Translate the given text.

        Args:
            text (str): The text to translate.
            target_language_code (str): The ISO 639-1 code of the target language.
                                        Engine implementations must handle variations (e.g., 'en' vs 'EN-US').
            source_language_code (str, optional): The ISO 639-1 code of the source language.
                                                 If None, the engine should attempt auto-detection.

        Returns:
            str: The translated text.

        Raises:
            TranslationError: If translation fails for any reason (API error, network issue, etc.).
            ValueError: If input parameters are invalid (e.g., empty target code).
        """
        pass

    # Recommended method for subclasses to implement
    @abc.abstractmethod
    def is_available(self) -> bool:
        """
        Check if the engine is properly configured and ready to use.
        This should be implemented by subclasses to check for required libraries,
        credentials, API keys, network connectivity during init, etc.

        Returns:
            bool: True if the engine is available, False otherwise.
        """
        # Default implementation is False, forcing subclasses to implement check
        return False