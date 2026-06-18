"""
Phase 2 — AST Analysis Schemas.

Structured data models for Python AST extraction results.
"""
from typing import Optional
from pydantic import BaseModel


class FunctionDef(BaseModel):
    """A parsed Python function or method."""
    node_id: str                    # "func:{file_path}::{qualified_name}"
    name: str                       # bare function name
    qualified_name: str             # "ClassName.method_name" or "func_name"
    file_path: str                  # relative path from repo root
    start_line: int
    end_line: int
    args: list[str]                 # parameter names
    decorators: list[str]           # decorator names
    calls: list[str]                # raw callee names found in body
    docstring: Optional[str] = None
    body_text: str                  # full source of the function
    is_method: bool = False         # True if inside a class
    class_name: Optional[str] = None  # set if is_method


class ClassDef(BaseModel):
    """A parsed Python class."""
    node_id: str                    # "class:{file_path}::{class_name}"
    name: str
    file_path: str
    start_line: int
    end_line: int
    bases: list[str]                # base class names (as written in source)
    methods: list[str]              # method node_ids
    docstring: Optional[str] = None


class ImportStatement(BaseModel):
    """A single import statement in a Python file."""
    file_path: str
    module: str                     # "os.path", "collections", etc.
    names: list[str]                # imported names; ["*"] for wildcard
    is_from_import: bool            # True for "from X import Y"
    alias: Optional[str] = None     # "import numpy as np" → alias="np"
    line: int = 0


class FileAST(BaseModel):
    """Fully parsed AST of a single Python file."""
    file_path: str
    functions: list[FunctionDef]
    classes: list[ClassDef]
    imports: list[ImportStatement]
    module_docstring: Optional[str] = None
    parse_error: Optional[str] = None   # Set if AST parsing failed
    lines: int = 0
