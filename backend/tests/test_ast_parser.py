"""
Tests for Python AST parser.
"""
import textwrap
from pathlib import Path
import pytest

from app.ast_analysis.python_parser import PythonParser, RepositoryParser


SAMPLE_SOURCE = textwrap.dedent("""\
    \"\"\"Module docstring.\"\"\"
    import os
    from typing import List, Optional
    from .utils import helper

    class Animal:
        \"\"\"Base animal class.\"\"\"

        def __init__(self, name: str):
            self.name = name

        def speak(self) -> str:
            return f"{self.name} speaks"

    class Dog(Animal):
        \"\"\"A dog.\"\"\"

        def speak(self) -> str:
            result = helper(self.name)
            return f"Woof! {result}"

    def standalone_function(x: int, y: int) -> int:
        \"\"\"Add two numbers.\"\"\"
        return x + y

    def caller():
        standalone_function(1, 2)
        d = Dog("Rex")
        d.speak()
""")


@pytest.fixture
def sample_file(tmp_path: Path) -> tuple[Path, str]:
    p = tmp_path / "sample.py"
    p.write_text(SAMPLE_SOURCE)
    return p, "sample.py"


def test_parse_module_docstring(sample_file):
    parser = PythonParser()
    path, rel = sample_file
    result = parser.parse_file(path, rel)
    assert result.module_docstring == "Module docstring."
    assert result.parse_error is None


def test_parse_imports(sample_file):
    parser = PythonParser()
    result = parser.parse_file(*sample_file)
    modules = [imp.module for imp in result.imports]
    assert "os" in modules
    assert "typing" in modules
    assert ".utils" in modules


def test_parse_classes(sample_file):
    parser = PythonParser()
    result = parser.parse_file(*sample_file)
    class_names = [c.name for c in result.classes]
    assert "Animal" in class_names
    assert "Dog" in class_names

    dog = next(c for c in result.classes if c.name == "Dog")
    assert "Animal" in dog.bases
    assert dog.docstring == "A dog."


def test_parse_methods(sample_file):
    parser = PythonParser()
    result = parser.parse_file(*sample_file)
    # Methods are included in functions
    func_names = [f.name for f in result.functions]
    assert "__init__" in func_names
    assert "speak" in func_names
    assert "standalone_function" in func_names

    # Check method metadata
    init_func = next(f for f in result.functions if f.name == "__init__" and f.class_name == "Animal")
    assert init_func.is_method
    assert "name" in init_func.args  # 'self' stripped


def test_parse_function_calls(sample_file):
    parser = PythonParser()
    result = parser.parse_file(*sample_file)
    caller = next(f for f in result.functions if f.name == "caller")
    call_names = caller.calls
    assert any("standalone_function" in c for c in call_names)


def test_parse_syntax_error(tmp_path: Path):
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def broken(:\n    pass\n")
    parser = PythonParser()
    result = parser.parse_file(bad_file, "bad.py")
    assert result.parse_error is not None
    assert "SyntaxError" in result.parse_error


def test_parse_node_ids(sample_file):
    parser = PythonParser()
    result = parser.parse_file(*sample_file)
    func_ids = [f.node_id for f in result.functions]
    assert any("sample.py::standalone_function" in fid for fid in func_ids)
    assert any("sample.py::Dog.speak" in fid for fid in func_ids)
