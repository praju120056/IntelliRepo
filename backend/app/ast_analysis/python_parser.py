"""
Phase 2 — Python AST Parser.

Parses Python source files using stdlib `ast` module.
Extracts functions, classes, methods, imports, function calls, and inheritance.
"""
import ast
import textwrap
from pathlib import Path
from typing import Optional

from app.core.logging import get_logger
from app.ast_analysis.schemas import (
    ClassDef,
    FileAST,
    FunctionDef,
    ImportStatement,
)

logger = get_logger(__name__)


def make_func_id(file_path: str, qualified_name: str) -> str:
    return f"func:{file_path}::{qualified_name}"


def make_class_id(file_path: str, class_name: str) -> str:
    return f"class:{file_path}::{class_name}"


class _CallExtractor(ast.NodeVisitor):
    """Walks a function body and collects all called names."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        name = self._extract_call_name(node.func)
        if name:
            self.calls.append(name)
        self.generic_visit(node)

    @staticmethod
    def _extract_call_name(node: ast.expr) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            obj = _CallExtractor._extract_call_name(node.value)
            return f"{obj}.{node.attr}" if obj else node.attr
        return None


class PythonParser:
    """
    Parses a single Python file and returns a FileAST.
    Thread-safe — stateless between calls.
    """

    def parse_file(self, file_path: Path, relative_path: str) -> FileAST:
        """
        Parse one Python file. Returns a FileAST with parse_error set
        if parsing fails, rather than raising.
        """
        try:
            source = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            return FileAST(
                file_path=relative_path,
                functions=[],
                classes=[],
                imports=[],
                parse_error=f"Cannot read file: {exc}",
            )

        try:
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError as exc:
            return FileAST(
                file_path=relative_path,
                functions=[],
                classes=[],
                imports=[],
                parse_error=f"SyntaxError at line {exc.lineno}: {exc.msg}",
                lines=source.count("\n") + 1,
            )

        source_lines = source.splitlines()
        lines = len(source_lines)

        module_docstring = ast.get_docstring(tree)
        imports = self._extract_imports(tree, relative_path)
        classes, functions = self._extract_definitions(tree, source_lines, relative_path)

        return FileAST(
            file_path=relative_path,
            functions=functions,
            classes=classes,
            imports=imports,
            module_docstring=module_docstring,
            lines=lines,
        )

    # ── Import extraction ─────────────────────────────────────────────────────

    def _extract_imports(self, tree: ast.Module, file_path: str) -> list[ImportStatement]:
        imports: list[ImportStatement] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ImportStatement(
                        file_path=file_path,
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        is_from_import=False,
                        alias=alias.asname,
                        line=node.lineno,
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                # Handle relative imports (e.g., "from . import utils")
                if node.level:
                    module = "." * node.level + module
                names = [a.name for a in node.names]
                imports.append(ImportStatement(
                    file_path=file_path,
                    module=module,
                    names=names,
                    is_from_import=True,
                    line=node.lineno,
                ))

        return imports

    # ── Definition extraction ─────────────────────────────────────────────────

    def _extract_definitions(
        self,
        tree: ast.Module,
        source_lines: list[str],
        file_path: str,
    ) -> tuple[list[ClassDef], list[FunctionDef]]:
        classes: list[ClassDef] = []
        functions: list[FunctionDef] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cls, methods = self._parse_class(node, source_lines, file_path)
                classes.append(cls)
                functions.extend(methods)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = self._parse_function(node, source_lines, file_path)
                functions.append(func)

        return classes, functions

    def _parse_class(
        self,
        node: ast.ClassDef,
        source_lines: list[str],
        file_path: str,
    ) -> tuple[ClassDef, list[FunctionDef]]:
        """Parse a class node and its methods."""
        class_id = make_class_id(file_path, node.name)
        docstring = ast.get_docstring(node)

        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{getattr(base.value, 'id', '?')}.{base.attr}")

        methods: list[FunctionDef] = []
        method_ids: list[str] = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{node.name}.{item.name}"
                func = self._parse_function(
                    item, source_lines, file_path,
                    is_method=True,
                    class_name=node.name,
                    qualified_name=qualified,
                )
                methods.append(func)
                method_ids.append(func.node_id)

        cls = ClassDef(
            node_id=class_id,
            name=node.name,
            file_path=file_path,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            bases=bases,
            methods=method_ids,
            docstring=docstring,
        )
        return cls, methods

    def _parse_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        source_lines: list[str],
        file_path: str,
        is_method: bool = False,
        class_name: Optional[str] = None,
        qualified_name: Optional[str] = None,
    ) -> FunctionDef:
        """Parse a function or method node."""
        qname = qualified_name or node.name
        node_id = make_func_id(file_path, qname)

        # Args — collect all parameter names
        args_node = node.args
        arg_names = [a.arg for a in args_node.args]
        if args_node.vararg:
            arg_names.append(f"*{args_node.vararg.arg}")
        if args_node.kwarg:
            arg_names.append(f"**{args_node.kwarg.arg}")
        # Remove 'self' and 'cls' for clarity, they add noise in summaries
        arg_names = [a for a in arg_names if a not in ("self", "cls")]

        # Decorators
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{getattr(dec.value, 'id', '?')}.{dec.attr}")
            elif isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Name):
                    decorators.append(dec.func.id)
                elif isinstance(dec.func, ast.Attribute):
                    decorators.append(dec.func.attr)

        # Docstring
        docstring = ast.get_docstring(node)

        # Function body as source text
        end_line = node.end_lineno or node.lineno
        body_lines = source_lines[node.lineno - 1 : end_line]
        body_text = textwrap.dedent("\n".join(body_lines))

        # Extract all function calls inside the body
        extractor = _CallExtractor()
        extractor.visit(node)

        return FunctionDef(
            node_id=node_id,
            name=node.name,
            qualified_name=qname,
            file_path=file_path,
            start_line=node.lineno,
            end_line=end_line,
            args=arg_names,
            decorators=decorators,
            calls=extractor.calls,
            docstring=docstring,
            body_text=body_text,
            is_method=is_method,
            class_name=class_name,
        )


class RepositoryParser:
    """Orchestrates parsing across all Python files in a repository."""

    def __init__(self) -> None:
        self._parser = PythonParser()

    def parse_repository(
        self,
        repo_root: Path,
        python_files: list[str],
    ) -> list[FileAST]:
        """
        Parse all Python files in the repository.

        Args:
            repo_root: Absolute path to cloned repo root.
            python_files: List of relative file paths to parse.

        Returns:
            List of FileAST objects (one per file).
        """
        results: list[FileAST] = []
        total = len(python_files)

        for i, rel_path in enumerate(python_files, start=1):
            abs_path = repo_root / rel_path
            logger.info(f"  Parsing [{i}/{total}] {rel_path}")

            file_ast = self._parser.parse_file(abs_path, rel_path)
            if file_ast.parse_error:
                logger.warning(f"  [yellow]Parse error in {rel_path}:[/] {file_ast.parse_error}")
            results.append(file_ast)

        logger.info(
            f"[green]Parsing complete:[/] {total} files, "
            f"{sum(1 for r in results if not r.parse_error)} succeeded, "
            f"{sum(1 for r in results if r.parse_error)} failed"
        )
        return results
