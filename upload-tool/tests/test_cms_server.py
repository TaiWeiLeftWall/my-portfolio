import ast
import unittest
from pathlib import Path

SERVER = Path(__file__).resolve().parents[1] / "cms_server.py"


class ServerEntryTests(unittest.TestCase):
    def test_runtime_definitions_precede_main_entry(self):
        tree = ast.parse(SERVER.read_text(encoding="utf-8-sig"))
        main_index = next(
            index
            for index, node in enumerate(tree.body)
            if isinstance(node, ast.If) and "__name__" in ast.unparse(node.test)
        )
        names = {
            node.name: index
            for index, node in enumerate(tree.body)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        self.assertLess(names["validate_date"], main_index)
        self.assertLess(names["validate_enum"], main_index)


if __name__ == "__main__":
    unittest.main()
