-- Options are automatically loaded before lazy.nvim startup
-- Default options that are always set: https://github.com/LazyVim/LazyVim/blob/main/lua/lazyvim/config/options.lua
-- Add any additional options here
vim.g.lazyvim_picker = "telescope"

-- Provider dependencies are independent of the interpreter selected for a project.
local provider = vim.fn.stdpath("data") .. "/notebook-provider/bin"
vim.g.python3_host_prog = provider .. "/python"
vim.env.PATH = provider .. ":" .. vim.env.PATH
-- This Molten version writes connection files under Jupyter's data directory,
-- not JUPYTER_RUNTIME_DIR. Ensure its private runtime directory exists (Linux).
local jupyter_data = vim.env.JUPYTER_DATA_DIR
  or ((vim.env.XDG_DATA_HOME or vim.fn.expand("~/.local/share")) .. "/jupyter")
vim.fn.mkdir(jupyter_data .. "/runtime", "p", 448)
