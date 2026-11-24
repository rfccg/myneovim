#!/usr/bin/env python3
"""Apply pinned Molten compatibility and persistence fixes before registration.

Python may collect DynamicPosition objects on a Jupyter background thread.
Nvim.async_call is pynvim's supported thread-safe API. Also avoid synchronous
RPC from a destructor during buffer unload or provider shutdown.
Fail closed if upstream changes this method; do not silently patch new code.
"""

import sys
from pathlib import Path

OLD = """    def __del__(self) -> None:
        # Note, this will not fail if the extmark doesn't exist
        self.nvim.funcs.nvim_buf_del_extmark(self.bufno, self.extmark_namespace, self.extmark_id)
"""
NEW = """    def __del__(self) -> None:
        # myneovim: schedule destructor RPC on pynvim's event-loop thread.
        nvim = self.nvim
        bufno, namespace, mark = self.bufno, self.extmark_namespace, self.extmark_id

        def cleanup():
            try:
                if nvim.api.buf_is_valid(bufno):
                    nvim.api.buf_del_extmark(bufno, namespace, mark)
            except Exception:
                pass  # Buffer/provider may already have shut down.

        try:
            nvim.async_call(cleanup)
        except Exception:
            pass
"""


PRESERVE_OLD = """                matched = True
                outputs = ["""
PRESERVE_NEW = """                matched = True
                # myneovim: imported output is a view, not a lossless serialization.
                # Jupytext already preserved the original records for unchanged cells.
                if output.output.old:
                    break
                outputs = ["""

RENDER_OLD = """        except ImportError:
            continue

    if chunk is None and data is not None:"""
RENDER_NEW = """        except ImportError:
            continue
        except Exception:
            # myneovim: missing Chrome/Cairo/TeX must not block other MIME types.
            # The complete original MIME bundle remains in chunk.jupyter_data.
            continue

    if chunk is None and data is not None:"""

SPEC_OLD = """    @pynvim.function("MoltenAvailableKernels", sync=True)"""
SPEC_NEW = (
    """    @pynvim.function("MoltenKernelSpec", sync=True)
    def function_kernel_spec(self, args):
        # myneovim: runtime IDs may be suffixed; return the actual kernelspec.
        kernel = self.molten_kernels.get(args[0])
        if kernel is None:
            return {}
        manager = kernel.runtime.kernel_manager
        spec = manager.kernel_spec
        return {"name": manager.kernel_name, "display_name": spec.display_name,
                "language": spec.language}

"""
    + SPEC_OLD
)

EXPORT_OLD = """    nb_cells = list(filter(lambda x: x["cell_type"] == "code", nb["cells"]))
"""
EXPORT_NEW = (
    """    # myneovim: never persist incomplete or queued execution as finished output.
    if any(output.output.status in (OutputStatus.HOLD, OutputStatus.RUNNING)
           for _, output in molten_cells):
        notify_error(nvim, "Execution is still running or queued; wait, then save again.")
        return

"""
    + EXPORT_OLD
)


def replace_once(path, old, new):
    content = path.read_text()
    if new in content:
        return
    if content.count(old) != 1:
        raise RuntimeError(
            f"Molten {path.name} changed: review scripts/patch_molten.py before registration"
        )
    path.write_text(content.replace(old, new))


def patch(directory):
    root = Path(directory) / "rplugin/python3/molten"
    replace_once(root / "position.py", OLD, NEW)
    replace_once(root / "ipynb.py", EXPORT_OLD, EXPORT_NEW)
    replace_once(root / "ipynb.py", PRESERVE_OLD, PRESERVE_NEW)
    replace_once(root / "outputchunks.py", RENDER_OLD, RENDER_NEW)
    replace_once(root / "__init__.py", SPEC_OLD, SPEC_NEW)


if __name__ == "__main__":
    patch(sys.argv[1])
