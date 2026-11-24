# Notebook design

Status: PRD and technical plan approved in this session.

## Requirements

- Edit Python notebooks as percent-format Python without replacing existing Python tooling.
- Support direct ipynb editing and explicitly paired Python scripts.
- Separate provider dependencies, kernel environments, content synchronization, and results.
- Preserve metadata and existing applicable results; never execute on open or import.
- Guard failures, dirty companions, recursive hooks, duplicate cell ambiguity, and partial exports.
- Provide buffer-local execution, navigation, kernel, output, and synchronization mappings.
- Keep text usable without graphical dependencies; report optional rendering prerequisites.

## Architecture

- `lua/config/options.lua`: provider interpreter/PATH before plugin startup; private Jupyter runtime directory.
- `lua/plugins/notebooks.lua`: early Lazy specs and conditional image.nvim.
- `lua/config/notebooks.lua`: notebook mappings, guarded save orchestration, one-time import after kernel readiness, and narrowly scoped upstream adapters.
- `scripts/notebook.py`: Jupytext-native pairing/config resolution and atomic metadata-preserving content writes. JSON IPC, no notebook execution.
- `scripts/patch_molten.py`: version-checked build patches for thread-safe extmark destruction, refusing incomplete output export, untouched imported-output fidelity, renderer fallback, and real kernelspec lookup; then supported `UpdateRemotePlugins` registration.
- Unit tests cover pairing/path resolution, metadata/results preservation, duplicates, and ordinary scripts. Embedded Neovim tests cover real conversion, kernels, output, dirty companions, persistence, and in-flight saves.

## Decisions and constraints

- No Quarto/otter or second ipynb handler; Python buffers already receive Python LSP/completion/Treesitter.
- Jupytext metadata/config determines pairing; a coincidental same-stem ipynb does not.
- One Python script plus one ipynb per pairing. Multi-format/multi-script pairings fail clearly rather than partially synchronize.
- Explicit save is authoritative for source text; no newest-mtime merge that might replace the current buffer.
- Molten export is staged and only committed after an actual successful write. Content writes and output writes are distinct; a failed export does not roll back saved source.
- Run-all uses individual Navigator-selected cells through an adapted Molten bridge. Upstream whole-file run-all cannot reliably export to individual notebook cells.
- Rich-output dependencies are optional. Unknown terminals default to text.
- Existing project interpreters are not upgraded or rewritten.

## Validation

See [notebook operations](notebooks.md) for commands, evidence, manual checks, and known upstream limitations.
