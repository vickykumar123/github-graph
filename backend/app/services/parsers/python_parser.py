import ast
from typing import List, Dict, Optional
from app.services.parsers.base_parser import BaseParser

class PythonParser(BaseParser):
    """
    Parser for Python files using AST (Abstract Syntax Tree).

    Extracts function definitions, class definitions, and import statements.
    """

    # Register this parser for Python language
    SUPPORTED_LANGUAGES = ['python']

    def parse(self, code: str, file_path) -> Dict:
        """Parse Python code and extract functions, classes, and imports.

        Args:
            code: The Python source code as a string.
            file_path: The path of the file being parsed.
        Returns:
            A dictionary with:
            - functions: Flat list of ALL functions (standalone + methods) with parent_class
            - classes: Nested structure with methods inside
            - imports: List of import statements
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            print(f"Syntax error in file {file_path}: {e}")
            return {
                "functions": [],
                "classes": [],
                "imports": [],
                "parse_error": str(e)
            }

        # Extract classes first (with nested methods)
        classes = self._extract_classes(tree)

        # Extract ALL functions (flat list with parent_class)
        functions = self._extract_functions(tree, classes)

        # Extract imports
        imports = self._extract_imports(tree)

        return {
            "functions": functions,
            "classes": classes,
            "imports": imports,
            "parse_error": None
        }
        
    def _extract_functions(self, tree: ast.AST, classes: List[Dict]) -> List[Dict]:
        """
        Extract ALL function definitions (FLAT list including methods).

        This creates a searchable flat list of ALL functions, with each
        function knowing which class it belongs to (if any).

        Returns list of function objects with:
        - name: Function name
        - line_start: Starting line number
        - line_end: Ending line number
        - parameters: List of parameter names
        - parent_class: Class name if method, None if standalone
        - is_method: True if inside class, False otherwise
        - return_type: Return type annotation (if any)
        - docstring: Function docstring
        - is_async: Whether function is async
        - signature: Full function signature
        """
        functions = []

        # Create a mapping of line ranges to class names for quick lookup
        class_ranges = {}
        for cls in classes:
            for line in range(cls['line_start'], cls['line_end'] + 1):
                class_ranges[line] = cls['name']

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Determine if this function is inside a class
                parent_class = class_ranges.get(node.lineno)
                is_method = parent_class is not None

                # Generate signature
                params = self._extract_parameters(node)
                return_type = self._extract_return_type(node)
                signature = f"{node.name}({', '.join(params)})"
                if return_type:
                    signature += f" -> {return_type}"

                func_info = {
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "parameters": params,
                    "parent_class": parent_class,  # ✅ Link to parent class
                    "is_method": is_method,        # ✅ Flag if method
                    "return_type": return_type,
                    "docstring": ast.get_docstring(node),
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                    "signature": signature         # ✅ Full signature
                }
                functions.append(func_info)

        return functions
    
    def _extract_classes(self, tree: ast.AST) -> List[Dict]:
        """
        Extract all class definitions from AST with nested methods.

        Returns list of class objects with:
        - name: Class name
        - line_start: Starting line number
        - line_end: Ending line number
        - docstring: Class docstring
        - methods: List of method objects (NESTED structure)
        - base_classes: List of parent classes
        """
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Extract FULL method details (not just names)
                methods = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_info = {
                            "name": item.name,
                            "line_start": item.lineno,
                            "line_end": item.end_lineno,
                            "parameters": self._extract_parameters(item),
                            "return_type": self._extract_return_type(item),
                            "docstring": ast.get_docstring(item),
                            "is_async": isinstance(item, ast.AsyncFunctionDef),
                            "is_static": self._is_static_method(item),
                            "is_class_method": self._is_class_method(item),
                            "is_private": item.name.startswith('_') and not item.name.startswith('__'),
                            "is_dunder": item.name.startswith('__') and item.name.endswith('__')
                        }
                        methods.append(method_info)

                # Extract base classes (inheritance)
                base_classes = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        base_classes.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        base_classes.append(self._get_full_name(base))

                class_info = {
                    "name": node.name,
                    "line_start": node.lineno,
                    "line_end": node.end_lineno,
                    "docstring": ast.get_docstring(node),
                    "methods": methods,  # ✅ Full method objects, not just names
                    "base_classes": base_classes
                }
                classes.append(class_info)

        return classes
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
          """
          Extract all import statements.

          Returns list of imported module names:
          - "import os" → ["os"]
          - "from pathlib import Path" → ["pathlib"]
          - "from app.services import github_service" → ["app.services.github_service"]
          """
          imports = []

          for node in ast.walk(tree):
              if isinstance(node, ast.Import):
                  # Handle: import os, sys
                  for alias in node.names:
                      imports.append(alias.name)

              elif isinstance(node, ast.ImportFrom):
                  # Handle: from pathlib import Path
                  module = node.module or ''

                  # If it's "from . import X", we need to handle relative imports
                  if node.level > 0:
                      # Relative import (e.g., from ..utils import helper)
                      # We'll store this as-is for now
                      prefix = '.' * node.level
                      imports.append(f"{prefix}{module}" if module else prefix)
                  else:
                      # Absolute import
                      imports.append(module)

          # Remove duplicates and empty strings
          imports = list(set(filter(None, imports)))

          return imports

    def _extract_parameters(self, node: ast.FunctionDef) -> List[str]:
          """Extract parameter names from function definition"""
          params = []

          # Regular arguments
          for arg in node.args.args:
              params.append(arg.arg)

          # *args
          if node.args.vararg:
              params.append(f"*{node.args.vararg.arg}")

          # **kwargs
          if node.args.kwarg:
              params.append(f"**{node.args.kwarg.arg}")

          return params

    def _extract_return_type(self, node: ast.FunctionDef) -> Optional[str]:
          """Extract return type annotation if present"""
          if node.returns:
              return ast.unparse(node.returns)
          return None

    def _is_top_level(self, node: ast.FunctionDef, tree: ast.AST) -> bool:
          """
          Check if function is defined at module level (not nested inside class/function).

          For simplicity, we consider a function top-level if it's directly in the module body.
          """
          # Find module node
          module = None
          for n in ast.walk(tree):
              if isinstance(n, ast.Module):
                  module = n
                  break

          if module and node in module.body:
              return True
          return False

    def _get_full_name(self, node: ast.Attribute) -> str:
          """
          Get full name from attribute node.

          Example: ast.FunctionDef → "ast.FunctionDef"
          """
          try:
              return ast.unparse(node)
          except:
              return "Unknown"

    def _is_static_method(self, node: ast.FunctionDef) -> bool:
        """Check if function has @staticmethod decorator"""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == 'staticmethod':
                return True
        return False

    def _is_class_method(self, node: ast.FunctionDef) -> bool:
        """Check if function has @classmethod decorator"""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == 'classmethod':
                return True
        return False