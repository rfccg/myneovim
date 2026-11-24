import importlib.util
import tempfile
import threading
import types
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "patch_molten", Path(__file__).parents[1] / "scripts/patch_molten.py"
)
patcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(patcher)


class PatchTests(unittest.TestCase):
    def test_patch_is_idempotent_and_rejects_changed_upstream(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "rplugin/python3/molten"
            root.mkdir(parents=True)
            position = root / "position.py"
            position.write_text(patcher.OLD)
            export = root / "ipynb.py"
            export.write_text(patcher.EXPORT_OLD + patcher.PRESERVE_OLD)
            (root / "outputchunks.py").write_text(patcher.RENDER_OLD)
            (root / "__init__.py").write_text(patcher.SPEC_OLD)
            patcher.patch(directory)
            self.assertEqual(position.read_text(), patcher.NEW)
            self.assertEqual(
                export.read_text(), patcher.EXPORT_NEW + patcher.PRESERVE_NEW
            )
            patcher.patch(directory)
            position.write_text("upstream changed")
            with self.assertRaisesRegex(RuntimeError, "review"):
                patcher.patch(directory)

    def test_destructor_schedules_thread_safe_cleanup(self):
        callbacks, deletions = [], []
        main = threading.current_thread()

        def delete(*args):
            self.assertIs(threading.current_thread(), main)
            deletions.append(args)

        nvim = types.SimpleNamespace(
            api=types.SimpleNamespace(
                buf_is_valid=lambda _: True, buf_del_extmark=delete
            ),
            async_call=callbacks.append,
        )
        namespace = {}
        exec("class Position:\n" + patcher.NEW, namespace)  # noqa: S102 - trusted local patch regression test
        position = namespace["Position"]()
        position.nvim = nvim
        position.bufno, position.extmark_namespace, position.extmark_id = 1, 2, 3
        thread = threading.Thread(target=position.__del__)
        thread.start()
        thread.join()
        self.assertEqual(deletions, [])
        self.assertEqual(len(callbacks), 1)
        callbacks.pop()()
        self.assertEqual(deletions, [(1, 2, 3)])
