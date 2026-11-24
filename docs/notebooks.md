# Python notebooks

## Installed setup

- `~/.config/nvim` resolves to this repository: `/home/lima.linux/workspace/myneovim`.
- Neovim 0.12.6, LazyVim, lazy.nvim; plugin revisions are recorded in `lazy-lock.json`.
- Jupytext.nvim is the only `.ipynb` conversion handler. It loads before initial file reads and uses `py:percent`, with Python filetype.
- Existing Python tooling remains: Pyright, Ruff, blink.cmp, venv-selector (`<leader>cv`), and Python Treesitter.
- Provider: `~/.local/share/nvim/notebook-provider/bin/python`, Python 3.12.3. Its directory is added to Neovim's PATH before plugins load, so Jupytext works without activating a shell venv.
- Required provider packages: pynvim 0.6.0, jupyter-client 8.10.0, nbformat 5.11.1, Jupytext 1.19.6.
- Optional provider packages installed: Pillow 13.0.0, Plotly 7.1.0, Kaleido 1.5.0. They are not required for text execution or notebook persistence. CairoSVG was tested and removed because system Cairo is unavailable.
- Registered project kernel: `incognia-analysis-hub`, using the existing `~/workspace/incognia-analysis-hub/.venv/bin/python` (Python 3.12.3, existing ipykernel 7.3.0). No project packages or interpreters were changed.
- Other discovered virtual environments include copied macOS paths and an unavailable Python 3.13 interpreter; these were left untouched. No Python 3.9 environment was found. Python 3.9 can still be used as a separate project kernel.

Reproduce provider installation and plugin registration from this repository:

```sh
./scripts/setup-notebooks.sh          # required dependencies
./scripts/setup-notebooks.sh --rich   # optional provider image/Plotly extras too
```

The setup requires `uv`, Python >=3.10, and the active configuration symlink. It never replaces a different configuration automatically. It does not install project-kernel packages.

**Compatibility adaptations:**

- Jupytext.nvim's normal same-stem `.py` scratch file is redirected to a private temporary file. An unrelated or paired Python script is never used as conversion scratch.
- Its reader accepts Python notebooks without kernelspec metadata and propagates conversion errors. Normal read events are supplied for this LazyVim version's LSP loading.
- Its writer is replaced with guarded, atomic content conversion followed by separate Molten export. Writing an ipynb buffer to another filename is disabled; save and copy the notebook explicitly instead.
- NotebookNavigator's Molten bridge is adapted to submit the exact inclusive cell body, without appending a marker when executing the last cell. Navigation and manipulation still use Navigator.
- Molten's Lazy build applies version-checked patches in `scripts/patch_molten.py`: thread-safe extmark destructor cleanup, refusal to export running/queued results, preservation of untouched imported output records, optional-renderer text fallback, and a `MoltenKernelSpec(id)` API that distinguishes runtime IDs from real kernelspec names. It then runs the supported `:UpdateRemotePlugins` workflow. The installed Molten checkout consequently has intentional local modifications. Updates fail clearly if patch contexts change; review the adapters/patch before updating the pinned plugins.

## Open an existing notebook

```sh
nvim path/to/notebook.ipynb
```

1. The buffer contains Python `# %%` cells and commented Markdown.
2. Press `<localleader>ni` to select a registered kernel, or run `:MoltenInit incognia-analysis-hub`.
3. Saved outputs import once when that kernel is ready. Opening/importing never executes code. The imported output does not restore Python variables.
4. Run complete cells with `<localleader>nr`; use `<localleader>nA` for all code cells in source order. Markdown/raw cells and comment-only metadata headers are skipped.
5. Wait for execution to finish, then `:write` or `:wq`.

Keep a single kernel attached to each notebook for automatic import/export. `:MoltenDeinit` detaches it; initialization thereafter does not repeatedly import outputs into the same buffer. Reopen the buffer to deliberately restore from disk.

## Pair a Python script

For a new pairing:

1. Edit `analysis.py` with `# %%` cells and save it.
2. Run `:NotebookPair` (or `<localleader>nP`). This adds Jupytext pairing metadata to the script and creates `analysis.ipynb`.
3. Select a kernel and run cells. Save normally; `<localleader>ns` explicitly saves and synchronizes.

Pairing refuses an existing same-stem notebook rather than overwriting it. If both files already exist, review/back up both, close their buffers, then establish the pairing explicitly:

```sh
~/.local/share/nvim/notebook-provider/bin/jupytext --set-formats ipynb,py:percent analysis.ipynb
~/.local/share/nvim/notebook-provider/bin/jupytext --sync analysis.ipynb
```

Jupytext CLI synchronization uses timestamps to select inputs; review differences before using it on two independently edited files.

Existing pairing metadata and `jupytext.toml`/`pyproject.toml` configuration are recognized through Jupytext's own path-resolution APIs. Directory prefixes and suffixes are supported, for example:

```toml
# jupytext.toml
formats = "notebooks//ipynb,scripts//py:percent"
```

A Python script is **not** automatically paired merely because a same-name ipynb exists. Only recognized metadata/configuration enables synchronization. This integration supports one Python script plus one ipynb per pairing; use Jupytext CLI for other multi-format pairings.

## Kernels and interpreter selection

Provider Python and project Python have different jobs:

- Provider Python loads Molten and converts notebook files.
- The chosen Jupyter kernel runs notebook code.
- `<leader>cv` / `:VenvSelect` chooses the language-tooling interpreter, independently of the running kernel. Choose the same project environment for accurate completion and diagnostics.

List available kernels:

```sh
~/.local/share/nvim/notebook-provider/bin/jupyter kernelspec list
```

Register another kernel using that project's existing interpreter:

```sh
uv pip install --python /absolute/project/.venv/bin/python ipykernel
/absolute/project/.venv/bin/python -m ipykernel install --user \
  --name my-project --display-name 'Python (my-project)'
```

For Python 3.9, use a compatible ipykernel release (for example `ipykernel<7`) in that project environment; do not replace its interpreter with provider Python. Existing dependency constraints take precedence.

Then use `:MoltenInit my-project`. Existing notebook kernelspec metadata is preserved; a notebook that lacks kernelspec gets the selected registered kernel's spec on save. Selecting a different execution kernel does not silently rewrite an existing kernelspec. Update it deliberately with Jupytext CLI if required.

## Buffer-local mappings

LazyVim leader is Space; localleader is backslash (`\`). Notebook mappings use `<localleader>n` (for example, `\ni` selects a kernel), leaving `<leader>n` available for notification history. Mappings are available in Python buffers; existing mappings are not overwritten.

| Mapping | Action |
| --- | --- |
| `<localleader>ni` | Initialize/select kernel |
| `<localleader>nr` | Run current cell; in Visual mode, run selection |
| `<localleader>nn` | Run cell and advance; at EOF Navigator creates a new cell |
| `<localleader>nA` | Run all code cells as separate Molten cells |
| `<localleader>np` / `<localleader>nj` | Previous / next cell |
| `<localleader>nx` | Interrupt kernel |
| `<localleader>nR` | Restart kernel, retaining displayed results (`:MoltenRestart!` clears them) |
| `<localleader>no` | Enter the full output window; scroll there, `q` to leave |
| `<localleader>nh` | Open supported `text/html` output in browser |
| `<localleader>nv` | Open image with Pillow's external viewer |
| `<localleader>ns` | Save and explicitly synchronize a recognized notebook |
| `<localleader>nP` | Establish a new script/notebook pairing |
| `<localleader>na` / `<localleader>nb` | Add cell below / split cell |

`<localleader>nA` deliberately does **not** call Navigator's upstream `run_all_cells()`: that function submits the whole buffer as one Molten cell, which cannot reliably export to individual notebook cells.

## What saving does

1. Resolve pairing metadata/configuration. Ordinary unpaired Python files keep normal writes and create no notebook.
2. Refuse to overwrite a modified companion buffer. For paired Python, the Python write itself has already completed, but synchronization/export stops with an error. Save or discard the companion deliberately and save again.
3. Convert current source to the ipynb, retaining notebook metadata, kernelspec, cell IDs, and existing outputs where Jupytext can match unchanged cells. In paired ipynb editing, update the paired script too. Current buffer text is authoritative; this is not a newest-timestamp merge.
4. If one kernel is attached, export Molten results into a temporary notebook and replace the target only after a successful exporter write. Conversion completes before export. Running/queued execution, unmatched spans, ambiguous duplicate code, or multiple kernels stop output export with a visible error.

**Content synchronization and output export are separate operations, not a single transaction.** If export fails, source may already be saved; existing applicable results remain in the notebook. The Python view never contains execution results. Results live in the companion `.ipynb` (or the `.ipynb` being edited), not a separate sidecar.

Wait for cells to finish before saving. If an ipynb save fails, the buffer stays modified. A Python script may already be saved even when synchronization/export reports an error.

### Persistence limitations and safe workflow

Molten import/export is experimental and matches source, not stable notebook cell IDs:

- Untouched imported output records (including stdout/stderr stream names, execution-result counts, HTML, widget MIME data, and unknown MIME bundles) are preserved without reserializing through Molten's display model. Newly executed stream/expression results can still be normalized by Molten into `display_data`; their visible results persist, but their original output-event type is not guaranteed.
- Export ignores comments. Duplicate code cells can put output on the wrong duplicate. This integration conservatively blocks export whenever duplicate normalized code exists, even though upstream can handle some fully executed duplicate sequences. Make executable code distinct, save, then rerun complete cells.
- Visual selections, line execution, or overlapping ranges may not correspond to complete notebook cells. They remain useful for scratch execution, but export can fail. Clear such spans with `:MoltenDelete!`, then run complete cells with `<localleader>nA` and save.
- Editing source after executing it does not prove that its old result is still valid. Rerun changed cells and their dependent cells before saving; safest is run-all and wait. Molten cannot guarantee semantic freshness of results.
- Imports match exact lines in sequence. Unusual whitespace, repeated/mixed text, or manually changed cell boundaries can prevent exact restoration. Check Molten's imported-cell count; the notebook's results remain on disk. Do not rerun merely to view saved output unless you intend execution.
- Jupytext comments IPython magics by default. Prefer valid Python equivalents such as `get_ipython().run_line_magic('matplotlib', 'inline')` when executing through Navigator. This keeps the buffer suitable for Python language tools.
- Multi-kernel export, multi-script/multi-format pairing, concurrent edits by external programs, and cross-file multi-write transactions are not supported safely. Review diffs/back up notebooks before restructuring them.

## Rich output

Inline text is enabled (12-line limit); the scrollable full-output window is limited to 30 rows and 120 columns.

**Current environment:** `TERM_PROGRAM=herdr`, tmux 3.4 installed but no active tmux session, no ImageMagick `magick`, no X11/Wayland display, and no browser/image launcher (`xdg-open`, Firefox, Chromium) found. Kitty protocol support cannot be inferred from this terminal name. Therefore image.nvim is disabled; no inline-image display is claimed.

- Static PNG results from Matplotlib were generated, exported, and verified as valid PNG data. They remain viewable in another notebook frontend even without Neovim image display.
- The conditional image.nvim spec enables Kitty graphics plus `magick_cli` on recognized Kitty/WezTerm/Ghostty terminals when `magick` is installed and tmux is absent. Restart Neovim and run `:Lazy install` after changing terminals/dependencies. Other terminals require explicit capability verification and configuration.
- With tmux, first verify protocol support, tmux >=3.3 and `set -g allow-passthrough on`; the current conservative condition still disables images under tmux until reviewed.
- `<localleader>nv` uses Pillow's `Image.show()`. It needs an accessible graphical viewer; the headless workspace currently has none. On a graphical Linux host install `xdg-utils` plus a viewer, or open the notebook on your desktop.
- `<localleader>nh` supports HTML output only. It needs a browser launcher. Molten defaults to `xdg-open`; set `vim.g.molten_open_cmd` to a single executable path for a different launcher. Automatic browser opening is disabled.
- Plotly/Kaleido are installed in the provider, but current Kaleido also requires Chrome. The actual PNG conversion test fails with `Kaleido requires Google Chrome to be installed`. Install a compatible Chrome/Chromium and set `BROWSER_PATH` if needed, then test rendering. `plotly_get_chrome` may not offer builds for this Linux ARM64 platform. Plotly itself must also be available in the project kernel that creates figures.
- Static Plotly PNG rendering has **no** browser interactions. HTML opened in a browser can retain browser-only Plotly interactions.
- For SVG transparency, install system Cairo (Ubuntu: `libcairo2`), then `uv pip install --python ~/.local/share/nvim/notebook-provider/bin/python cairosvg`. It is optional; PNG/text persistence does not depend on it.
- Live ipywidgets and Python-backed interactive controls require a separate connected Jupyter frontend (such as JupyterLab). Molten/HTML preview does not implement the widget communication frontend.

## Verification

Run from this repository:

```sh
~/.local/share/nvim/notebook-provider/bin/python -m unittest discover -s tests -v
~/.local/share/nvim/notebook-provider/bin/python tests/integration.py
nvim --headless '+checkhealth provider molten' '+qa!'
```

The integration suite uses the registered `incognia-analysis-hub` project kernel for state-sharing tests and creates a disposable, separate ipykernel/Matplotlib environment and kernelspec for other tests. It removes its temporary notebooks and kernel environment afterward. It requires `uv`, package access/cache, and the existing project kernel.

Automated checks cover startup/commands, readable percent conversion, Python filetype/Treesitter, attached Pyright and blink.cmp, shared state, text/error virtual output, individual-cell run-all, save/reopen/import without execution, metadata/kernelspec, paired script synchronization, dirty-companion protection, ordinary Python saves, PNG generation/persistence, refusing in-flight output export, full fidelity of untouched saved output bundles, Plotly text fallback without Chrome, and simultaneous buffers whose Molten runtime IDs acquire suffixes.

Latest verification: **8 unit tests and 8 embedded-Neovim integration tests passed**. Ruff, StyLua, shell syntax, `git diff --check`, and a repeat `setup-notebooks.sh --rich` run passed. The second clean-context code review returned **APPROVED**.

Provider/Molten health checks pass required dependencies. Optional warnings remain for CairoSVG/pnglatex/pyperclip and unrelated clipboard/Node/Perl/Ruby providers. Health checks only detect Plotly/Kaleido package presence; actual rendering additionally needs Chrome.

**Manual terminal checks still required:** rendered image visibility/placement, output-window navigation, completion popup usability, browser/graphical viewer launch, interrupt/restart interaction, and tmux passthrough. Headless tests cannot prove these visual behaviors.

## Upstream references

- [Molten](https://github.com/benlubas/molten-nvim)
- [Molten notebook setup](https://github.com/benlubas/molten-nvim/blob/main/docs/Notebook-Setup.md)
- [Molten import/export matching](https://github.com/benlubas/molten-nvim/blob/main/docs/Advanced-Functionality.md)
- [jupytext.nvim](https://github.com/GCBallesteros/jupytext.nvim)
- [NotebookNavigator](https://github.com/GCBallesteros/NotebookNavigator.nvim)
- [Jupytext paired notebooks](https://jupytext.readthedocs.io/en/latest/paired-notebooks.html)
- [image.nvim terminal/dependency requirements](https://github.com/3rd/image.nvim)
