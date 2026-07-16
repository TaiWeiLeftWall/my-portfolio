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
        self.assertLess(names["public_path"], main_index)
        self.assertLess(names["save_upload"], main_index)
        self.assertLess(names["Handler"], main_index)
        self.assertLess(names["main"], main_index)

    def test_startup_message_uses_loopback_address(self):
        source = SERVER.read_text(encoding="utf-8-sig")
        self.assertIn("PORT = 8090", source)
        self.assertIn('print(f"CMS running at http://127.0.0.1:{PORT}")', source)
        self.assertNotIn("CMS running at http://localhost:", source)


if __name__ == "__main__":
    unittest.main()
