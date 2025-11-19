from abc import ABC, abstractmethod
from typing import Dict, List, Optional

class BaseParser(ABC):
    """
    Abstract base class for all language parsers.

    Any new language parser must inherit from this class and implement
    the parse() method.

    This ensures a consistent interface across all parsers and makes
    the system easily extensible.
    """

    # Class variable to store parser registry
    _registry = {}

    def __init_subclass__(cls, **kwargs):
        """
        Automatically register parser when subclass is created.

        This is Python magic that runs when a class inherits from BaseParser.
        It allows parsers to self-register without manual registration.
        """
        super().__init_subclass__(**kwargs)

        # Get the languages this parser supports
        if hasattr(cls, 'SUPPORTED_LANGUAGES'):
            for language in cls.SUPPORTED_LANGUAGES:
                BaseParser._registry[language.lower()] = cls
                print(f"📝 Registered parser for: {language}")

    @abstractmethod
    def parse(self, code: str, file_path: str) -> Dict:
        """
        Parse source code and extract structured information.

        Args:
            code: Source code as string
            file_path: File path (for error reporting)

        Returns:
            Dictionary with parsed information:
            {
                "functions": [         # Flat list: ALL functions (standalone + methods)
                    {
                        "name": "function_name",
                        "line_start": 10,
                        "line_end": 15,
                        "parameters": ["param1", "param2"],
                        "parent_class": "ClassName",  # null if standalone function
                        "is_method": True,            # True if inside class
                        "docstring": "Function description",
                        "signature": "function_name(param1, param2)"
                    }
                ],
                "classes": [           # Nested structure: Classes with methods
                    {
                        "name": "ClassName",
                        "line_start": 5,
                        "line_end": 20,
                        "docstring": "Class description",
                        "methods": [   # Methods nested inside class
                            {
                                "name": "method_name",
                                "line_start": 10,
                                "line_end": 15,
                                "parameters": ["self", "param1"],
                                "docstring": "Method description"
                            }
                        ]
                    }
                ],
                "imports": [...],      # List of import statements
                "parse_error": None    # Error message if parsing failed
            }
        """
        pass

    @classmethod
    def get_parser(cls, language: str) -> Optional['BaseParser']:
        """
        Get parser instance for a specific language.

        Args:
            language: Language name (e.g., "python", "javascript")

        Returns:
            Parser instance or None if language not supported
        """
        parser_class = cls._registry.get(language.lower())
        if parser_class:
            return parser_class()
        return None

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """
        Get list of all supported languages.

        Returns:
            List of language names
        """
        return list(cls._registry.keys())

    @classmethod
    def is_supported(cls, language: str) -> bool:
        """
        Check if a language is supported.

        Args:
            language: Language name

        Returns:
            True if language is supported, False otherwise
        """
        return language.lower() in cls._registry

    def _extract_function_signature(self, node) -> str:
        """
        Helper method to extract function signature.
        Can be overridden by subclasses.
        """
        return ""

    def _extract_docstring(self, node) -> Optional[str]:
        """
        Helper method to extract docstring from node.
        Can be overridden by subclasses.
        """
        return None
