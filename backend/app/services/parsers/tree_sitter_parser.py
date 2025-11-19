from typing import List, Dict, Optional
from app.services.parsers.base_parser import BaseParser

try:
    from tree_sitter import Language, Parser
    from tree_sitter_language_pack import get_parser
    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False
    print("⚠️ tree-sitter not available. Install with: pip install tree-sitter tree-sitter-language-pack")


class TreeSitterParser(BaseParser):
    """
    Generic parser using tree-sitter for multiple languages.

    Supports: JavaScript, TypeScript, Go, Java, Rust, C/C++, PHP
    """

    # Register this parser for multiple languages
    SUPPORTED_LANGUAGES = [
        'javascript',
        'typescript',
        'tsx',  # TypeScript + JSX
        'jsx',  # JavaScript + JSX
        'go',
        'java',
        'rust',
        'cpp',
        'c',
        'php'
    ]

    # Language-specific query patterns for extracting functions
    FUNCTION_QUERIES = {
        'javascript': """
            (function_declaration
                name: (identifier) @function.name
                parameters: (formal_parameters) @function.params) @function.def

            (arrow_function) @function.def

            (method_definition
                name: (property_identifier) @function.name
                parameters: (formal_parameters) @function.params) @function.def
        """,
        'typescript': """
            (function_declaration
                name: (identifier) @function.name
                parameters: (formal_parameters) @function.params) @function.def

            (arrow_function) @function.def

            (method_definition
                name: (property_identifier) @function.name
                parameters: (formal_parameters) @function.params) @function.def
        """,
        'go': """
            (function_declaration
                name: (identifier) @function.name
                parameters: (parameter_list) @function.params) @function.def

            (method_declaration
                name: (field_identifier) @function.name
                parameters: (parameter_list) @function.params) @function.def
        """,
        'java': """
            (method_declaration
                name: (identifier) @function.name
                parameters: (formal_parameters) @function.params) @function.def

            (constructor_declaration
                name: (identifier) @function.name
                parameters: (formal_parameters) @function.params) @function.def
        """,
        'rust': """
            (function_item
                name: (identifier) @function.name
                parameters: (parameters) @function.params) @function.def
        """,
        'cpp': """
            (function_definition
                declarator: (function_declarator
                    declarator: (identifier) @function.name
                    parameters: (parameter_list) @function.params)) @function.def
        """,
        'c': """
            (function_definition
                declarator: (function_declarator
                    declarator: (identifier) @function.name
                    parameters: (parameter_list) @function.params)) @function.def
        """,
        'php': """
            (function_definition
                name: (name) @function.name
                parameters: (formal_parameters) @function.params) @function.def

            (method_declaration
                name: (name) @function.name
                parameters: (formal_parameters) @function.params) @function.def
        """
    }

    # Class query patterns
    CLASS_QUERIES = {
        'javascript': """
            (class_declaration
                name: (identifier) @class.name) @class.def
        """,
        'typescript': """
            (class_declaration
                name: (type_identifier) @class.name) @class.def

            (interface_declaration
                name: (type_identifier) @class.name) @class.def
        """,
        'go': """
            (type_declaration
                (type_spec
                    name: (type_identifier) @class.name)) @class.def
        """,
        'java': """
            (class_declaration
                name: (identifier) @class.name) @class.def

            (interface_declaration
                name: (identifier) @class.name) @class.def
        """,
        'rust': """
            (struct_item
                name: (type_identifier) @class.name) @class.def

            (enum_item
                name: (type_identifier) @class.name) @class.def

            (trait_item
                name: (type_identifier) @class.name) @class.def
        """,
        'cpp': """
            (class_specifier
                name: (type_identifier) @class.name) @class.def

            (struct_specifier
                name: (type_identifier) @class.name) @class.def
        """,
        'c': """
            (struct_specifier
                name: (type_identifier) @class.name) @class.def
        """,
        'php': """
            (class_declaration
                name: (name) @class.name) @class.def

            (interface_declaration
                name: (name) @class.name) @class.def
        """
    }

    # Import query patterns
    IMPORT_QUERIES = {
        'javascript': """
            (import_statement
                source: (string) @import.source)
        """,
        'typescript': """
            (import_statement
                source: (string) @import.source)
        """,
        'go': """
            (import_spec
                path: (interpreted_string_literal) @import.source)
        """,
        'java': """
            (import_declaration
                (scoped_identifier) @import.source)
        """,
        'rust': """
            (use_declaration
                argument: (_) @import.source)
        """,
        'cpp': """
            (preproc_include
                path: (_) @import.source)
        """,
        'c': """
            (preproc_include
                path: (_) @import.source)
        """,
        'php': """
            (use_declaration
                (name) @import.source)
        """
    }

    def __init__(self):
        if not TREE_SITTER_AVAILABLE:
            raise ImportError("tree-sitter is not installed")

    def parse(self, code: str, file_path: str) -> Dict:
        """
        Parse code using tree-sitter.

        Args:
            code: Source code as string
            file_path: File path (for detecting language)

        Returns:
            Dictionary with:
            - functions: Flat list of ALL functions (standalone + methods) with parent_class
            - classes: Nested structure with methods inside
            - imports: List of import statements
        """
        # Detect language from file extension
        language = self._detect_language(file_path)

        if not language:
            return {
                "functions": [],
                "classes": [],
                "imports": [],
                "parse_error": "Could not detect language from file path"
            }

        try:
            # Get parser for language
            # Note: get_parser returns a Parser object directly
            parser = get_parser(language)

            # Parse the code
            tree = parser.parse(bytes(code, "utf8"))
            root_node = tree.root_node

            # Extract classes first (with nested methods)
            classes = self._extract_classes_ts(root_node, code, language)

            # Extract ALL functions (flat list with parent_class)
            functions = self._extract_functions_ts(root_node, code, language, classes)

            # Extract imports
            imports = self._extract_imports_ts(root_node, code, language)

            return {
                "functions": functions,
                "classes": classes,
                "imports": imports,
                "parse_error": None
            }

        except Exception as e:
            print(f"⚠️ Error parsing {file_path}: {e}")
            return {
                "functions": [],
                "classes": [],
                "imports": [],
                "parse_error": str(e)
            }

    def _detect_language(self, file_path: str) -> Optional[str]:
        """Detect language from file extension"""
        if file_path.endswith('.js'):
            return 'javascript'
        elif file_path.endswith('.jsx'):
            return 'javascript'
        elif file_path.endswith('.ts'):
            return 'typescript'
        elif file_path.endswith('.tsx'):
            return 'typescript'
        elif file_path.endswith('.go'):
            return 'go'
        elif file_path.endswith('.java'):
            return 'java'
        elif file_path.endswith('.rs'):
            return 'rust'
        elif file_path.endswith(('.cpp', '.cc', '.cxx', '.hpp', '.h')):
            return 'cpp'
        elif file_path.endswith('.c'):
            return 'c'
        elif file_path.endswith('.php'):
            return 'php'
        return None

    def _extract_functions_ts(self, root_node, code: str, language: str, classes: List[Dict]) -> List[Dict]:
        """
        Extract ALL functions using tree-sitter (FLAT list including methods).

        Creates a searchable flat list with parent_class links.
        """
        functions = []

        # Create a mapping of line ranges to class names for quick lookup
        class_ranges = {}
        for cls in classes:
            for line in range(cls['line_start'], cls['line_end'] + 1):
                class_ranges[line] = cls['name']

        # Traverse tree to find all functions
        self._traverse_functions(root_node, code, language, functions, class_ranges)

        return functions

    def _traverse_functions(self, node, code: str, language: str, functions: List, class_ranges: Dict):
        """Recursively traverse tree to find ALL functions (standalone + methods)"""
        # Function node types by language
        function_types = {
            'javascript': ['function_declaration', 'method_definition', 'arrow_function'],
            'typescript': ['function_declaration', 'method_definition', 'arrow_function'],
            'go': ['function_declaration', 'method_declaration'],
            'java': ['method_declaration', 'constructor_declaration'],
            'rust': ['function_item'],
            'cpp': ['function_definition'],
            'c': ['function_definition'],
            'php': ['function_definition', 'method_declaration']
        }

        if node.type in function_types.get(language, []):
            line_start = node.start_point[0] + 1

            # Determine if this function is inside a class
            parent_class = class_ranges.get(line_start)
            is_method = parent_class is not None

            func_name = self._extract_node_name(node, code)
            params = self._extract_method_params(node, code, language)

            # Generate signature
            signature = f"{func_name}({', '.join(params)})"

            func_info = {
                "name": func_name,
                "line_start": line_start,
                "line_end": node.end_point[0] + 1,
                "parameters": params,
                "parent_class": parent_class,  # ✅ Link to parent class
                "is_method": is_method,        # ✅ Flag if method
                "docstring": None,
                "signature": signature          # ✅ Full signature
            }
            functions.append(func_info)

        # Recurse into children
        for child in node.children:
            self._traverse_functions(child, code, language, functions, class_ranges)

    def _extract_classes_ts(self, root_node, code: str, language: str) -> List[Dict]:
        """Extract classes using tree-sitter with nested methods"""
        classes = []
        self._traverse_classes(root_node, code, language, classes)
        return classes

    def _traverse_classes(self, node, code: str, language: str, classes: List):
        """Recursively traverse tree to find classes and extract nested methods"""
        class_types = {
            'javascript': ['class_declaration'],
            'typescript': ['class_declaration', 'interface_declaration'],
            'go': ['type_declaration'],
            'java': ['class_declaration', 'interface_declaration'],
            'rust': ['struct_item', 'enum_item', 'trait_item'],
            'cpp': ['class_specifier', 'struct_specifier'],
            'c': ['struct_specifier'],
            'php': ['class_declaration', 'interface_declaration']
        }

        # Method node types by language
        method_types = {
            'javascript': ['method_definition'],
            'typescript': ['method_definition', 'method_signature'],
            'go': ['method_declaration'],
            'java': ['method_declaration', 'constructor_declaration'],
            'rust': ['function_item'],  # Methods inside impl blocks
            'cpp': ['function_definition'],
            'c': [],  # C doesn't have methods
            'php': ['method_declaration']
        }

        if node.type in class_types.get(language, []):
            # Extract methods NESTED inside this class
            methods = []
            for child in node.children:
                # Look for class body
                if child.type in ['class_body', 'declaration_list', 'field_declaration_list']:
                    for method_node in child.children:
                        if method_node.type in method_types.get(language, []):
                            method_info = {
                                "name": self._extract_node_name(method_node, code),
                                "line_start": method_node.start_point[0] + 1,
                                "line_end": method_node.end_point[0] + 1,
                                "parameters": self._extract_method_params(method_node, code, language),
                                "docstring": None
                            }
                            methods.append(method_info)

            class_info = {
                "name": self._extract_node_name(node, code),
                "line_start": node.start_point[0] + 1,
                "line_end": node.end_point[0] + 1,
                "methods": methods,  # ✅ NESTED methods with full details
                "docstring": None
            }
            classes.append(class_info)

        for child in node.children:
            self._traverse_classes(child, code, language, classes)

    def _extract_imports_ts(self, root_node, code: str, language: str) -> List[str]:
        """Extract imports using tree-sitter"""
        imports = []
        self._traverse_imports(root_node, code, language, imports)
        return list(set(imports))  # Remove duplicates

    def _traverse_imports(self, node, code: str, language: str, imports: List):
        """Recursively traverse tree to find imports"""
        import_types = {
            'javascript': ['import_statement'],
            'typescript': ['import_statement'],
            'go': ['import_declaration'],
            'java': ['import_declaration'],
            'rust': ['use_declaration'],
            'cpp': ['preproc_include'],
            'c': ['preproc_include'],
            'php': ['namespace_use_declaration']
        }

        if node.type in import_types.get(language, []):
            import_text = code[node.start_byte:node.end_byte]
            # Extract the actual module name from the import statement
            imports.append(import_text.strip())

        for child in node.children:
            self._traverse_imports(child, code, language, imports)

    def _extract_node_name(self, node, code: str) -> str:
        """Extract name from a node"""
        for child in node.children:
            if 'identifier' in child.type or child.type == 'name':
                return code[child.start_byte:child.end_byte]
        return "anonymous"

    def _extract_method_params(self, node, code: str, language: str) -> List[str]:
        """
        Extract parameter names from a function/method node.

        This is a simplified extraction - just gets parameter count for now.
        Full parameter name extraction would require language-specific logic.
        """
        params = []

        # Parameter list node types by language
        param_list_types = {
            'javascript': ['formal_parameters'],
            'typescript': ['formal_parameters'],
            'go': ['parameter_list'],
            'java': ['formal_parameters'],
            'rust': ['parameters'],
            'cpp': ['parameter_list'],
            'c': ['parameter_list'],
            'php': ['formal_parameters']
        }

        param_types = param_list_types.get(language, [])

        for child in node.children:
            if child.type in param_types:
                # Extract parameter names from the parameter list
                for param_node in child.children:
                    if 'identifier' in param_node.type or param_node.type in ['required_parameter', 'optional_parameter']:
                        param_text = code[param_node.start_byte:param_node.end_byte]
                        # Clean up parameter text (remove types, defaults, etc.)
                        param_name = param_text.split(':')[0].split('=')[0].strip()
                        if param_name and param_name not in [',', '(', ')', '{', '}']:
                            params.append(param_name)

        return params
