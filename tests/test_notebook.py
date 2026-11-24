"""Run with notebook-provider/bin/python -m unittest discover -s tests -v."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import jupytext
import nbformat

spec = importlib.util.spec_from_file_location(
    "notebook", Path(__file__).parents[1] / "scripts/notebook.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class NotebookTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def test_unpaired_is_not_a_notebook(self):
        script = self.root / "ordinary.py"
        script.write_text("x = 1\n")
        result = helper.dispatch(
            {"mode": "write", "path": str(script), "text": "x = 2"}
        )
        self.assertIsNone(result["target"])
        self.assertFalse(script.with_suffix(".ipynb").exists())

    def test_pair_and_round_trip_outputs_metadata(self):
        script = self.root / "paired.py"
        script.write_text("# %%\nx = 1\n# %%\nprint(x)\n")
        info = helper.dispatch(
            {"mode": "pair", "path": str(script), "text": script.read_text()}
        )
        helper.dispatch(
            {"mode": "write", "path": str(script), "text": script.read_text()}
        )
        target = Path(info["target"])
        notebook = nbformat.read(target, as_version=4)
        notebook.metadata["custom"] = {"keep": True}
        notebook.metadata["kernelspec"] = {
            "name": "project",
            "display_name": "Project",
            "language": "python",
        }
        notebook.cells[1].outputs = [
            nbformat.v4.new_output("stream", name="stdout", text="1\n")
        ]
        notebook.cells[1].execution_count = 2
        nbformat.write(notebook, target)
        helper.dispatch(
            {"mode": "write", "path": str(script), "text": script.read_text()}
        )
        saved = nbformat.read(target, as_version=4)
        self.assertTrue(saved.metadata.custom.keep)
        self.assertEqual(saved.metadata.kernelspec.name, "project")
        self.assertEqual(saved.cells[1].outputs[0].text, "1\n")
        self.assertEqual(saved.cells[1].execution_count, 2)

    def test_config_resolves_different_directories(self):
        (self.root / "jupytext.toml").write_text(
            'formats = "notebooks//ipynb,scripts//py:percent"\n'
        )
        script = self.root / "scripts/demo.py"
        script.parent.mkdir()
        script.write_text("# %%\nprint(42)\n")
        info = helper.dispatch(
            {"mode": "write", "path": str(script), "text": script.read_text()}
        )
        self.assertEqual(info["target"], str(self.root / "notebooks/demo.ipynb"))
        self.assertTrue(Path(info["target"]).exists())

    def test_duplicate_export_blocked(self):
        path = self.root / "duplicate.ipynb"
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[
                    nbformat.v4.new_code_cell("print(1) # first"),
                    nbformat.v4.new_code_cell("print(1) # second"),
                ]
            ),
            path,
        )
        with self.assertRaisesRegex(ValueError, "duplicate"):
            helper.dispatch({"mode": "check", "path": str(path)})

    def test_existing_companion_not_overwritten_by_pair(self):
        script = self.root / "demo.py"
        script.write_text("x = 1")
        script.with_suffix(".ipynb").write_text("do not overwrite")
        with self.assertRaisesRegex(ValueError, "already exists"):
            helper.dispatch(
                {"mode": "pair", "path": str(script), "text": script.read_text()}
            )
        self.assertEqual(script.with_suffix(".ipynb").read_text(), "do not overwrite")

    def test_ipynb_updates_paired_script(self):
        path = self.root / "demo.ipynb"
        notebook = nbformat.v4.new_notebook(cells=[nbformat.v4.new_code_cell("x = 1")])
        notebook.metadata["jupytext"] = {"formats": "ipynb,py:percent"}
        nbformat.write(notebook, path)
        text = jupytext.writes(notebook, fmt="py:percent").replace("x = 1", "x = 2")
        helper.dispatch({"mode": "write", "path": str(path), "text": text})
        self.assertIn("x = 2", path.with_suffix(".py").read_text())
        self.assertEqual(nbformat.read(path, as_version=4).cells[0].source, "x = 2")
