"""Disposable end-to-end tests against the actual ~/.config/nvim configuration."""

import base64
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import nbformat
import pynvim


class Integration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory(prefix="nvim notebooks ")
        cls.root = Path(cls.directory.name)
        kernel = cls.root / "kernel/bin/python"
        subprocess.run(
            ["uv", "venv", "--python", "/usr/bin/python3", str(cls.root / "kernel")],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(kernel),
                "ipykernel",
                "matplotlib",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                str(kernel),
                "-m",
                "ipykernel",
                "install",
                "--prefix",
                str(cls.root),
                "--name",
                "nvim-notebook-test",
            ],
            check=True,
            capture_output=True,
        )
        cls.previous_jupyter_path = os.environ.get("JUPYTER_PATH")
        os.environ["JUPYTER_PATH"] = str(cls.root / "share/jupyter") + (
            ":" + cls.previous_jupyter_path if cls.previous_jupyter_path else ""
        )
        cls.nvim = pynvim.attach("child", argv=["nvim", "--embed", "--headless"])
        cls.nvim.exec_lua("vim.wait(300)")
        cls.nvim.exec_lua("""
          _G.test_notifications = {}
          vim.notify = function(msg, level)
            table.insert(_G.test_notifications, {tostring(msg), level or 0})
          end
        """)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.nvim.command("qa!")
        except EOFError:
            pass
        cls.nvim.close()
        if cls.previous_jupyter_path is None:
            os.environ.pop("JUPYTER_PATH", None)
        else:
            os.environ["JUPYTER_PATH"] = cls.previous_jupyter_path
        cls.directory.cleanup()

    def edit(self, path):
        self.nvim.command("edit " + self.nvim.funcs.fnameescape(str(path)))
        self.nvim.exec_lua("vim.wait(300)")

    def wait(self, milliseconds=2500):
        self.nvim.exec_lua("vim.wait(...)", milliseconds)

    def output_text(self, output):
        return output.get("text", output.get("data", {}).get("text/plain"))

    def save(self):
        self.nvim.command("write")
        self.wait(200)

    def errors(self):
        return self.nvim.exec_lua(
            "return vim.tbl_filter(function(n) return n[2] == vim.log.levels.ERROR end, test_notifications)"
        )

    def tearDown(self):
        outcome = self._outcome.result
        if any(test is self for test, _ in outcome.errors + outcome.failures):
            print("Neovim messages:", self.nvim.command_output("messages"))
            print("Notifications:", self.nvim.exec_lua("return test_notifications"))

    def test_01_startup(self):
        self.assertEqual(self.nvim.funcs.has("python3"), 1)
        for command in (
            "MoltenInit",
            "MoltenExportOutput",
            "MoltenEvaluateVisual",
            "NotebookPair",
            "NotebookSync",
        ):
            self.assertEqual(self.nvim.funcs.exists(":" + command), 2, command)
        self.assertEqual(
            self.nvim.exec_lua(
                "return require('notebook-navigator').config.repl_provider"
            ),
            "molten",
        )
        self.assertEqual(self.errors(), [])
        notification = self.nvim.funcs.maparg("<leader>n", "n", False, True)
        self.assertIn("notification", notification["desc"].lower())
        script = self.root / "mapping-check.py"
        script.write_text("# %%\nprint('mapping check')\n")
        self.edit(script)
        for suffix in (
            "i",
            "r",
            "n",
            "A",
            "p",
            "j",
            "x",
            "R",
            "o",
            "h",
            "v",
            "s",
            "P",
            "a",
            "b",
        ):
            mapping = self.nvim.funcs.maparg(
                "<localleader>n" + suffix, "n", False, True
            )
            self.assertEqual(mapping.get("buffer"), 1, suffix)
            self.assertTrue(mapping.get("desc", "").startswith("Notebook:"), suffix)
            self.assertEqual(self.nvim.funcs.maparg("<leader>n" + suffix, "n"), "")
        visual = self.nvim.funcs.maparg("<localleader>nr", "x", False, True)
        self.assertEqual(visual.get("buffer"), 1)
        self.assertEqual(
            self.nvim.funcs.maparg("<leader>n", "n", False, True)["desc"],
            notification["desc"],
        )
        self.nvim.command("bwipeout!")

    def test_02_ipynb_execution_and_persistence(self):
        path = self.root / "existing notebook.ipynb"
        notebook = nbformat.v4.new_notebook(
            cells=[
                nbformat.v4.new_markdown_cell("Notebook test"),
                nbformat.v4.new_code_cell("shared = 40"),
                nbformat.v4.new_code_cell("print(shared + 2)"),
                nbformat.v4.new_code_cell("raise ValueError('expected test error')"),
            ],
            metadata={
                "custom": {"keep": True},
                "kernelspec": {
                    "name": "incognia-analysis-hub",
                    "display_name": "Project",
                    "language": "python",
                },
            },
        )
        nbformat.write(notebook, path)
        # A same-stem Python file must never be used as conversion scratch.
        companion = path.with_suffix(".py")
        companion.write_text("# unrelated script\nprotect = True\n")
        self.edit(path)
        self.assertEqual(self.nvim.current.buffer.options["filetype"], "python")
        self.assertIn("# %%", "\n".join(self.nvim.current.buffer[:]))
        self.assertNotIn('"nbformat"', "\n".join(self.nvim.current.buffer[:]))
        self.assertEqual(companion.read_text(), "# unrelated script\nprotect = True\n")
        self.assertTrue(
            self.nvim.exec_lua("return pcall(vim.treesitter.get_parser, 0, 'python')")
        )
        self.assertTrue(
            self.nvim.exec_lua(
                "return vim.wait(10000, function() return #vim.lsp.get_clients({bufnr=0, name='pyright'}) > 0 end, 100)"
            )
        )
        self.assertTrue(self.nvim.exec_lua("return require('blink.cmp') ~= nil"))
        self.nvim.command("MoltenInit incognia-analysis-hub")
        self.wait()
        before = list(self.nvim.current.buffer[:])
        self.nvim.exec_lua("require('config.notebooks').run_all()")
        self.wait(5000)
        self.assertEqual(
            before,
            list(self.nvim.current.buffer[:]),
            "Execution should not append cell markers",
        )
        self.save()
        saved = nbformat.read(path, as_version=4)
        self.assertEqual(self.output_text(saved.cells[2].outputs[0]), "42\n")
        self.assertEqual(saved.cells[3].outputs[0].ename, "ValueError")
        self.assertTrue(saved.metadata.custom.keep)
        self.assertEqual(saved.metadata.kernelspec.name, "incognia-analysis-hub")
        self.assertEqual(companion.read_text(), "# unrelated script\nprotect = True\n")
        # Inline output exists as virtual lines, not only in the notebook file.
        marks = self.nvim.exec_lua(
            "return vim.api.nvim_buf_get_extmarks(0, -1, 0, -1, {details=true})"
        )
        self.assertTrue(any(mark[3].get("virt_lines") for mark in marks))
        self.nvim.command("bwipeout!")
        self.edit(path)
        self.assertEqual(self.nvim.funcs.MoltenRunningKernels(True), [])
        self.nvim.command("MoltenInit incognia-analysis-hub")
        self.wait()
        self.assertTrue(self.nvim.current.buffer.vars.get("notebook_imported"))
        # Import did not execute: the fresh kernel must not contain shared.
        self.nvim.current.buffer[:] = list(self.nvim.current.buffer[:]) + [
            "# %%",
            "print('shared' in globals())",
        ]
        self.nvim.current.window.cursor = (len(self.nvim.current.buffer), 0)
        self.nvim.exec_lua("require('notebook-navigator').run_cell()")
        self.wait()
        self.save()
        saved = nbformat.read(path, as_version=4)
        self.assertEqual(self.output_text(saved.cells[-1].outputs[0]), "False\n")
        self.assertEqual(self.output_text(saved.cells[2].outputs[0]), "42\n")
        self.assertEqual(self.errors(), [])
        self.nvim.command("bwipeout!")

    def test_03_pair_and_unpaired(self):
        script = self.root / "paired.py"
        script.write_text("# %%\nprint('paired result')\n")
        self.edit(script)
        self.nvim.command("NotebookPair")
        target = script.with_suffix(".ipynb")
        self.assertTrue(
            target.exists(), self.nvim.exec_lua("return test_notifications")
        )
        self.nvim.command("MoltenInit nvim-notebook-test")
        self.wait()
        self.nvim.exec_lua("require('config.notebooks').run_all()")
        self.wait()
        self.save()
        self.assertEqual(
            self.output_text(nbformat.read(target, as_version=4).cells[0].outputs[0]),
            "paired result\n",
        )
        # A dirty ipynb companion must block synchronization, not clobber its edits.
        self.nvim.command("badd " + self.nvim.funcs.fnameescape(str(target)))
        companion_buf = self.nvim.funcs.bufnr(str(target))
        self.nvim.funcs.bufload(companion_buf)
        self.nvim.api.buf_set_lines(companion_buf, 0, 0, False, ["# unsaved companion"])
        before = target.read_bytes()
        self.nvim.exec_lua("test_notifications = {}")
        self.save()
        self.assertEqual(target.read_bytes(), before)
        self.assertTrue(any("unsaved companion" in str(err) for err in self.errors()))
        self.nvim.command(f"bwipeout! {companion_buf}")
        self.nvim.command("bwipeout!")
        ordinary = self.root / "ordinary.py"
        ordinary.write_text("x = 1\n")
        self.edit(ordinary)
        self.nvim.current.buffer[:] = ["x = 2"]
        self.nvim.exec_lua("test_notifications = {}")
        self.save()
        self.assertEqual(ordinary.read_text(), "x = 2\n")
        self.assertFalse(ordinary.with_suffix(".ipynb").exists())
        self.assertEqual(self.errors(), [])
        self.nvim.command("bwipeout!")

    def test_04_static_png_persistence(self):
        path = self.root / "plot.ipynb"
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[
                    nbformat.v4.new_code_cell(
                        "get_ipython().run_line_magic('matplotlib', 'inline')\nimport matplotlib.pyplot as plt\nplt.plot([1, 2], [3, 4])\nplt.show()"
                    )
                ],
                metadata={
                    "kernelspec": {
                        "name": "nvim-notebook-test",
                        "display_name": "Test",
                        "language": "python",
                    }
                },
            ),
            path,
        )
        self.edit(path)
        self.nvim.command("MoltenInit nvim-notebook-test")
        self.wait()
        self.nvim.exec_lua("require('config.notebooks').run_all()")
        self.wait(6000)
        self.save()
        outputs = nbformat.read(path, as_version=4).cells[0].outputs
        png = next(
            o.data["image/png"] for o in outputs if "image/png" in o.get("data", {})
        )
        self.assertTrue(base64.b64decode(png).startswith(b"\x89PNG"))
        self.assertEqual(self.errors(), [])
        self.nvim.command("bwipeout!")

    def test_05_running_output_export_is_blocked(self):
        path = self.root / "running.ipynb"
        cell = nbformat.v4.new_code_cell(
            "import time\ntime.sleep(3)\nprint('finished')"
        )
        cell.execution_count = 1
        cell.outputs = [
            nbformat.v4.new_output("stream", name="stdout", text="previous result\n")
        ]
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[cell],
                metadata={
                    "kernelspec": {
                        "name": "nvim-notebook-test",
                        "display_name": "Test",
                        "language": "python",
                    }
                },
            ),
            path,
        )
        self.edit(path)
        self.nvim.command("MoltenInit nvim-notebook-test")
        self.wait()
        self.nvim.exec_lua("require('config.notebooks').run_all()")
        self.wait(200)
        with self.assertRaisesRegex(
            pynvim.api.common.NvimError, "output export failed"
        ):
            self.nvim.command("write")
        self.assertEqual(
            self.output_text(nbformat.read(path, as_version=4).cells[0].outputs[0]),
            "previous result\n",
        )
        self.wait(4000)
        self.nvim.exec_lua("test_notifications = {}")
        self.save()
        self.assertEqual(
            self.output_text(nbformat.read(path, as_version=4).cells[0].outputs[0]),
            "finished\n",
        )
        self.assertEqual(self.errors(), [])
        self.nvim.command("bwipeout!")

    def test_06_imported_output_fidelity_and_plotly_fallback(self):
        path = self.root / "rich saved.ipynb"
        cell = nbformat.v4.new_code_cell("print('do not execute on import')")
        cell.execution_count = 17
        cell.outputs = [
            nbformat.v4.new_output("stream", name="stdout", text="saved stdout\n"),
            nbformat.v4.new_output("stream", name="stderr", text="saved stderr\n"),
            nbformat.v4.new_output(
                "execute_result",
                execution_count=17,
                data={
                    "text/plain": "saved result",
                    "application/json": {"keep": [1, 2]},
                },
                metadata={"custom": True},
            ),
            nbformat.v4.new_output(
                "display_data",
                data={
                    "application/vnd.plotly.v1+json": {
                        "data": [{"type": "scatter", "x": [1, 2], "y": [3, 4]}],
                        "layout": {},
                    },
                    "text/plain": "Plotly fallback text",
                    "text/html": "<b>saved HTML</b>",
                },
                metadata={"isolated": True},
            ),
            nbformat.v4.new_output(
                "display_data",
                data={
                    "application/vnd.jupyter.widget-view+json": {
                        "model_id": "preserve-opaque-widget",
                        "version_major": 2,
                        "version_minor": 0,
                    },
                },
            ),
            nbformat.v4.new_output(
                "error",
                ename="ValueError",
                evalue="saved",
                traceback=["saved traceback"],
            ),
        ]
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[cell],
                metadata={
                    "kernelspec": {
                        "name": "nvim-notebook-test",
                        "display_name": "Test",
                        "language": "python",
                    }
                },
            ),
            path,
        )
        for _ in range(2):
            self.nvim.exec_lua("test_notifications = {}")
            self.edit(path)
            self.nvim.command("MoltenInit nvim-notebook-test")
            self.wait()
            self.assertTrue(self.nvim.current.buffer.vars.get("notebook_imported"))
            self.save()
            saved = nbformat.read(path, as_version=4).cells[0]
            self.assertEqual(saved.outputs, cell.outputs)
            self.assertEqual(saved.execution_count, 17)
            self.assertEqual(self.errors(), [])
            self.nvim.command("bwipeout!")

    def test_07_suffixed_runtime_id_uses_actual_kernelspec(self):
        buffers = []
        for name in ("first", "second"):
            script = self.root / (name + ".py")
            script.write_text("# %%\nprint('new notebook')\n")
            self.edit(script)
            self.nvim.command("NotebookPair")
            buffers.append(self.nvim.current.buffer.number)
            self.assertNotIn(
                "kernelspec",
                nbformat.read(script.with_suffix(".ipynb"), as_version=4).metadata,
            )
            self.nvim.command("MoltenInit nvim-notebook-test")
            self.wait()
            active = self.nvim.funcs.MoltenRunningKernels(True)
            if name == "second":
                self.assertNotEqual(active[0], "nvim-notebook-test")
            self.save()
            saved = nbformat.read(script.with_suffix(".ipynb"), as_version=4)
            self.assertEqual(saved.metadata.kernelspec.name, "nvim-notebook-test")
        for buf in buffers:
            self.nvim.command(f"bwipeout! {buf}")

    def test_08_failed_import_can_retry(self):
        path = self.root / "retry.ipynb"
        cell = nbformat.v4.new_code_cell("print('saved')")
        cell.execution_count = 1
        cell.outputs = [nbformat.v4.new_output("stream", name="stdout", text="saved\n")]
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[cell],
                metadata={
                    "kernelspec": {
                        "name": "nvim-notebook-test",
                        "display_name": "Test",
                        "language": "python",
                    }
                },
            ),
            path,
        )
        self.edit(path)
        self.nvim.command("MoltenInit nvim-notebook-test")
        self.wait()
        state = self.nvim.exec_lua("""
          vim.b.notebook_imported = nil
          local command = vim.cmd
          vim.cmd = function(value)
            if value:match('^MoltenImportOutput') then error('injected import failure') end
            return command(value)
          end
          local ok = pcall(require('config.notebooks').import, vim.api.nvim_get_current_buf())
          vim.cmd = command
          return {ok, vim.b.notebook_imported == true, vim.b.notebook_importing == true}
        """)
        self.assertEqual(state, [False, False, False])
        self.nvim.exec_lua(
            "require('config.notebooks').import(vim.api.nvim_get_current_buf())"
        )
        self.assertTrue(self.nvim.current.buffer.vars.get("notebook_imported"))
        self.nvim.command("bwipeout!")


if __name__ == "__main__":
    unittest.main(verbosity=2)
