# 💤 LazyVim

A starter template for [LazyVim](https://github.com/LazyVim/LazyVim).
Refer to the [documentation](https://lazyvim.github.io/installation) to get started.

## Python notebooks

[Notebook setup and operations](docs/notebooks.md): Molten execution, Jupytext percent-format conversion,
NotebookNavigator cells, paired-script synchronization, output persistence, mappings, and verification.

[Approved design](docs/notebook-design.md). Install isolated provider dependencies with
`./scripts/setup-notebooks.sh` (optional rich-output packages: `--rich`).

## Markdown preview in Lima

Install Node.js and npm in the guest. For an existing plugin install, start
Neovim in a guest SSH session with neither `DISPLAY` nor `WAYLAND_DISPLAY`
set. Run `:Lazy build markdown-preview.nvim` once, then restart Neovim.

In a Markdown buffer, press `<leader>cp`. In a Linux SSH session without a
GUI display, Neovim prints the URL instead of opening a browser. Find it again
with `:messages` and open it on your host. The preview listens on guest
`127.0.0.1:18765`; if Lima does not forward it automatically, forward that
port over SSH. Only one Neovim session can use this preview port at a time.
Press `<leader>cp` again to close the preview, or use `:MarkdownPreviewStop`
to release the port. Use `<leader>um` for in-editor rendering.
