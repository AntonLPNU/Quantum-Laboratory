"""Static coverage for public documentation of the scientific Python entry points."""
import ast
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = [*sorted((ROOT / "quantum_lab").glob("*.py")), ROOT / "app.py", *sorted((ROOT / "scripts").glob("*.py"))]


class SourceDocumentationTests(unittest.TestCase):
    def test_scientific_modules_and_public_api_have_docstrings(self):
        missing = []
        for path in SOURCE_FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            relative = path.relative_to(ROOT).as_posix()
            if not ast.get_docstring(tree):
                missing.append(f"{relative}: module docstring")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                    if not ast.get_docstring(node):
                        missing.append(f"{relative}: {node.name}")
                    if isinstance(node, ast.ClassDef):
                        for member in node.body:
                            if isinstance(member, (ast.FunctionDef, ast.AsyncFunctionDef)) and not member.name.startswith("_") and not ast.get_docstring(member):
                                missing.append(f"{relative}: {node.name}.{member.name}")
        self.assertEqual(missing, [], "Undocumented public source symbols:\n" + "\n".join(missing))

    def test_bibtex_keys_match_the_offline_handbook_registry(self):
        registry = (ROOT / "frontend/src/docs/references.ts").read_text(encoding="utf-8")
        bibliography = (ROOT / "docs/references.bib").read_text(encoding="utf-8")
        registry_ids = set(re.findall(r"^  ([a-z][a-z0-9-]*): \{", registry, re.MULTILINE))
        bibtex_ids = re.findall(r"@[a-z]+\s*\{\s*([^,\s]+)", bibliography, re.IGNORECASE)
        self.assertEqual(len(bibtex_ids), len(set(bibtex_ids)), "BibTeX citation keys must be unique")
        self.assertEqual(set(bibtex_ids), registry_ids, "BibTeX and in-app source IDs must match")


if __name__ == "__main__":
    unittest.main()
